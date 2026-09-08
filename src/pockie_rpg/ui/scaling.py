"""ScalableRendererMixin — общие хелперы Hi-DPI-масштабирования (Stage 152).

Вынесено из `render_inventory.py` (Stage 151), где `_su`/`_su_font` жили локально:
кузница (Stage 152) и последующие мигрируемые экраны используют те же хелперы,
дублировать их в каждом миксине нельзя.

Семантика: рендер-код пишется в ДИЗАЙН-координатах (1280×720), а каждый
Rect/draw/blit проходит через `self._su()` (= ×`self._render_scale`).
Legacy-фаза: `_render_scale = 1.0` → identity, поведение как до Stage 150.
Native-фаза (мигрированный экран на мониторе 2560×1440): `_render_scale = UI_SCALE`
→ рендер 1:1 в физических пикселях, без финального растяжения.

Порядок кадра и подмену `_render_scale` см. в `pygame_ui._render_native_overlays()`.
Чек-лист миграции экрана — в `RULES.md` (секция «Hi-DPI — правила работы»).

Stage 157 — ОБЩИЕ ПЕРЕТАСКИВАЕМЫЕ ОКНА (`_register_window` / `_window_pos` /
`_begin_window_drag` / `_update_window_drag`): реестр окон с шапками 40px,
позиции persist между кадрами; хранение в сейве — через `window_positions`
в PlayerState (PygameUI синхронизирует `self._window_positions`).
"""
from __future__ import annotations

from collections import OrderedDict

import pygame

from pockie_rpg.config import SCREEN_HEIGHT, SCREEN_WIDTH

# Stage 168 (аудит 5.2) — кап LRU-кэша текста. Статических надписей в игре
# ~сотни; динамические значения (золото, HP) образуют ограниченные множества
# строк. 2048 хватает с запасом, память ~несколько МБ.
_SU_TEXT_CACHE_CAP: int = 2048

WINDOW_TITLEBAR_H: int = 40
# Stage 161 — выносной Х: размер кнопки и гарантированный зазор справа,
# чтобы Х, приклеенный СНАРУЖИ окна, не уезжал за край экрана при drag.
CLOSE_X_SIZE: int = 26


def default_window_pos(w: int, h: int) -> tuple[int, int]:
    """Stage 157 — позиция окна по умолчанию (центр, кламп в экран).

    Stage 161 — нижний кламп от MAP_PANEL_HEIGHT (верхняя панель 52px + 4).
    """
    from pockie_rpg.config import MAP_PANEL_HEIGHT
    x = max(0, min((SCREEN_WIDTH - w) // 2, SCREEN_WIDTH - w))
    y = max(MAP_PANEL_HEIGHT + 4, min((SCREEN_HEIGHT - h) // 2, SCREEN_HEIGHT - h))
    return x, y


def clamp_window_pos(x: int, y: int, w: int, h: int) -> tuple[int, int]:
    """Stage 157 — окно большей частью внутри экрана (шапка всегда доступна).

    Stage 161 — Х-кнопка теперь СНАРУЖИ справа: правый край окна держится
    в экране с запасом CLOSE_X_SIZE, иначе закрыть окно станет невозможно.
    """
    x = max(-w // 2, min(x, SCREEN_WIDTH - CLOSE_X_SIZE - w))
    y = max(0, min(y, SCREEN_HEIGHT - WINDOW_TITLEBAR_H))
    return x, y


def _surface_silhouette(surf: pygame.Surface, alpha: int = 150) -> pygame.Surface:
    """Stage 197 — чёрный силуэт поверхности (альфа -> чёрный) для теней.

    Используется _drop_shadow(source=...) для силуэтных теней иконок
    статусов: непрозрачные пиксели становятся чёрными с заданной альфой,
    прозрачные остаются прозрачными.
    """
    s = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    s.blit(surf, (0, 0))
    s.fill((0, 0, 0, alpha), special_flags=pygame.BLEND_RGBA_MULT)
    return s


class ScalableRendererMixin:
    """Хелперы масштабирования для мигрированных на Hi-DPI экранов."""

    # ------------------------------------------------------------------
    # Stage 157 — общие перетаскиваемые окна (шапка 40px, drag мышью).
    # Реестр: key → (titlebar_rect_fn, w, h). Позиции — ДИЗАЙН-координаты
    # (persist в self._window_positions; PygameUI кладёт их в сейв через
    # PlayerState.window_positions).
    # ------------------------------------------------------------------

    def _window_registry(self) -> dict:
        """Реестр окон: key → dict(titlebar=fn, w, h). Ленивая инициализация."""
        if not hasattr(self, "_windows"):
            self._windows: dict = {}
        return self._windows

    def _register_window(self, key: str, titlebar_fn, w: int, h: int,
                         open_attr: str = "") -> None:
        """Зарегистрировать перетаскиваемое окно (вызывается при рендере).

        titlebar_fn — callable, возвращающий pygame.Rect шапки в ДИЗАЙН-
        координатах. Размеры w/h нужны для клампа при перетаскивании.
        open_attr — имя boolean-флага открытости (ПРАВИЛО 9); при отсутствии
        окно считается открытым всегда (пока зарегистрировано).
        """
        self._window_registry()[key] = {
            "titlebar": titlebar_fn, "w": w, "h": h, "open_attr": open_attr,
        }

    def _window_positions(self) -> dict:
        """Позиции окон {key: (x, y)} — дизайн-координаты.

        Stage 157 — persist в сейве: если есть player с полем
        window_positions (PlayerState), позиции читаются/пишутся ПРЯМО
        туда (debounced autosave через mark_dirty); иначе — runtime-словарь.
        """
        player = getattr(self, "player", None)
        wp = getattr(player, "window_positions", None)
        if isinstance(wp, dict):
            return wp
        if not hasattr(self, "_window_positions_store"):
            self._window_positions_store: dict[str, tuple[int, int]] = {}
        return self._window_positions_store

    def _window_pos(self, key: str, w: int, h: int) -> tuple[int, int]:
        """Позиция окна key (или центр экрана по умолчанию)."""
        pos = self._window_positions().get(key)
        if pos is None:
            pos = default_window_pos(w, h)
        return pos

    def _set_window_pos(self, key: str, x: int, y: int, w: int, h: int) -> None:
        """Сохранить позицию окна (кламп) + mark_dirty для сейва."""
        self._window_positions()[key] = clamp_window_pos(x, y, w, h)
        if hasattr(self, "save_mgr") and self.save_mgr is not None:
            self.save_mgr.mark_dirty()

    def _window_close_buttons(self) -> dict:
        """Stage 159 — реестр квадратных Х-кнопок закрытия.

        key → (rect, on_click, is_native). rect — в координатах рендера
        (нативных в native-фазе, дизайн в legacy); is_native — как у
        ClickRect: хиттест сравнивает с позицией события в СВОЁМ
        пространстве.
        """
        if not hasattr(self, "_window_close_buttons_store"):
            self._window_close_buttons_store: dict = {}
        return self._window_close_buttons_store

    def _handle_window_close_click(self, pos: tuple[int, int]) -> bool:
        """Stage 159 — LMB down по Х-кнопке ОТКРЫТОГО окна → закрыть (True).

        Вызывается ДО _begin_window_drag: Х приклеен к углу шапки, без
        приоритета клик перехватывал бы drag-захват. Позиция события —
        дизайн-координаты; нативные rect'ы конвертируются ×_ui_scale.
        """
        s = getattr(self, "_ui_scale", 1.0)
        for key, (rect, on_close, is_native) in self._window_close_buttons().items():
            spec = self._window_registry().get(key, {})
            open_attr = spec.get("open_attr", "")
            if open_attr and not getattr(self, open_attr, False):
                continue
            test_pos = (
                (int(pos[0] * s), int(pos[1] * s)) if is_native else pos
            )
            if rect.collidepoint(test_pos):
                on_close()
                return True
        return False

    def _begin_window_drag(self, pos: tuple[int, int]) -> bool:
        """LMB down на шапке ОТКРЫТОГО окна → захват (True).

        pos — ДИЗАЙН-координаты события. Захват хранится в
        self._window_drag = (key, dx, dy). Открытость проверяется по
        live-флагу модалки (open_attr) — рендер закрытого окна не
        вызывается, поэтому «замороженный» is_open из последнего кадра
        недостоверен.
        Stage 159 — захват засчитывается по шапке ИЗ РЕЕСТРА (последний
        рендер) ИЛИ по позиции из persist: раньше требовались ОБЕ, и окно
        с клампом рендера (инвентарь: modal_y 64..664-h) переставало
        перетаскиваться после сохранения сырой позиции.
        """
        for key, spec in self._window_registry().items():
            open_attr = spec.get("open_attr", "")
            if open_attr and not getattr(self, open_attr, False):
                continue
            wx, wy = self._window_pos(key, spec["w"], spec["h"])
            live_bar = pygame.Rect(wx, wy, spec["w"], WINDOW_TITLEBAR_H)
            anchor: tuple[int, int] | None = None
            bar = spec["titlebar"]()
            if bar is not None and bar.collidepoint(pos):
                anchor = (bar.x, bar.y)
            elif live_bar.collidepoint(pos):
                anchor = (wx, wy)
            if anchor is None:
                continue
            self._window_drag = (key, pos[0] - anchor[0], pos[1] - anchor[1])
            return True
        return False

    def _update_window_drag(self, pos: tuple[int, int]) -> None:
        """MOUSEMOTION: подвинуть захваченное окно (pos — дизайн-координаты)."""
        drag = getattr(self, "_window_drag", None)
        if drag is None:
            return
        key, dx, dy = drag
        spec = self._window_registry().get(key)
        if spec is None:
            self._window_drag = None
            return
        self._set_window_pos(key, pos[0] - dx, pos[1] - dy, spec["w"], spec["h"])

    def _end_window_drag(self) -> None:
        """LMB up — отпустить шапку (окно остаётся на месте)."""
        self._window_drag = None

    def _window_drag_key(self) -> str | None:
        """Ключ окна, которое сейчас перетаскивают (или None)."""
        drag = getattr(self, "_window_drag", None)
        return drag[0] if drag else None

    def _render_window_titlebar(self, key: str, panel: pygame.Rect,
                                title: str, accent: tuple[int, int, int],
                                is_open: bool,
                                right_text: str = "",
                                open_attr: str = "",
                                on_close=None) -> None:
        """Шапка окна: заголовок ПО ЦЕНТРУ, right_text справа.

        panel — НАТИВНЫЙ rect окна (рендер); хиттест — по self._mouse_pos
        (нативный в native-фазе). Регистрирует окно в реестре для drag.
        Пустой title — заголовок не рисуется (инвентарь: звание-плашка).
        open_attr — имя boolean-флага модалки (live-проверка при grab);
        пустая строка = всегда открыто (пока окно в реестре).
        on_close — callable закрытия: рисует КВАДРАТНЫЙ Х в ПРАВОМ ВЕРХНЕМ
        углу окна вплотную к краям (Stage 159 — был круглый выносной).
        Stage 159 — highlight шапки при hover/drag УБРАН (запрос
        пользователя: фон шапки не подсвечивается).
        Stage 163 — у окна синтеза убрана grip-подсказка «⠿ перетащить»
        (символ брайля рендерился квадратиком — «непрогруженный квадратик»).
        Stage 164 — запрос пользователя: подсказка убрана ВО ВСЕХ окнах,
        заголовок ВСЕГДА по центру шапки. Параметры grip/center_title
        удалены (старое поведение не возвращается).
        """
        su = self._su
        bar = pygame.Rect(panel.x, panel.y, panel.w, su(WINDOW_TITLEBAR_H))
        if right_text:
            rt = self._su_font(13).render(right_text, True, accent)
            self.screen.blit(rt, (panel.right - su(10) - rt.get_width(),
                                  bar.centery - rt.get_height() // 2))
        if title:
            title_surf = self._su_font(18, bold=True).render(title, True, accent)
            t_rect = title_surf.get_rect(centerx=bar.centerx,
                                         centery=bar.centery)
            self.screen.blit(title_surf, t_rect.topleft)
        if on_close is not None:
            self._render_window_close_button(key, panel, on_close)
        # Регистрация в реестре (каждый кадр — актуальная шапка и is_open).
        s = getattr(self, "_render_scale", 1.0)
        design_x = int(round(panel.x / s))
        design_y = int(round(panel.y / s))
        design_bar = pygame.Rect(design_x, design_y,
                                 int(round(panel.w / s)), WINDOW_TITLEBAR_H)
        w_design = int(round(panel.w / s))
        h_design = int(round(panel.h / s))
        self._register_window(
            key, lambda b=design_bar: b, w_design, h_design, open_attr,
        )
        spec = self._window_registry()[key]
        spec["is_open"] = is_open
        # Stage 159 — синхронизация persist с ФАКТИЧЕСКОЙ позицией рендера.
        # Рендеры клампят позицию (инвентарь: modal_y 64..664-h), но сырую
        # позицию не писали — расхождение блокировало захват шапки.
        if self._window_pos(key, w_design, h_design) != (design_x, design_y):
            self._set_window_pos(key, design_x, design_y, w_design, h_design)

    def _render_window_close_button(self, key: str, panel: pygame.Rect,
                                    on_close) -> None:
        """Stage 159 — КВАДРАТНЫЙ Х ЗАКРЫТИЯ у правого верхнего угла окна.

        Stage 161 — по запросу пользователя Х ВЫНЕСЕН ЗА окно: приклеен к
        правому краю СНАРУЖИ (x = panel.right, без зазора), а не внутри.
        Клик обрабатывается с приоритетом над drag-шапкой через
        _handle_window_close_click; реестр кнопок чистится кадром рендера
        (сам метод вызывается только для открытых окон). ClickRect
        дополнительно регистрируется для диспетчера кликов.
        """
        from pockie_rpg.ui.animator import ClickRect
        su = self._su
        size = su(CLOSE_X_SIZE)
        btn = pygame.Rect(panel.right, panel.y, size, size)
        hov = btn.collidepoint(self._mouse_pos)
        bg = (200, 40, 40) if hov else (120, 28, 28)
        pygame.draw.rect(self.screen, bg, btn, border_radius=su(4))
        cx, cy = btn.centerx, btn.centery
        d = size // 2 - su(7)
        pygame.draw.line(self.screen, (255, 255, 255),
                         (cx - d, cy - d), (cx + d, cy + d), su(2))
        pygame.draw.line(self.screen, (255, 255, 255),
                         (cx - d, cy + d), (cx + d, cy - d), su(2))
        is_native = getattr(self, "_render_scale", 1.0) > 1.0
        self._window_close_buttons()[key] = (btn, on_close, is_native)
        self._click_rects.append(ClickRect(
            tag=f"close_x_{key}", rect=btn, on_click=on_close,
            native=is_native,
        ))

    def _render_drag_ghost(self, draw_fn, w: int, h: int) -> None:
        """Stage 160 — полупрозрачный drag-призрак НА КОНЧИКЕ курсора.

        Запрос пользователя: перетаскиваемый предмет должен быть С МАЛОЙ
        прозрачностью и ЧЁТКО на кончике курсора (верхний левый угол
        призрака = self._mouse_pos), а не смещён вправо-вниз (был оффсет
        +28 Stage 147). Прозрачность (DRAG_GHOST_ALPHA) возвращает
        видимость подсветке зоны/цели дропа, которую призрак раньше
        старался не закрывать смещением.

        draw_fn(target_surface, rect) — рисует фон/рамку/иконку в
        SRCALPHA-буфер размера w×h (нативные координаты рендера);
        итоговый буфер блитится с общей альфой. Меняет self.screen на
        время отрисовки — как _render_with_fade.
        """
        from pockie_rpg.config import DRAG_GHOST_ALPHA
        ghost = pygame.Surface((max(1, w), max(1, h)), pygame.SRCALPHA)
        saved_screen = self.screen
        self.screen = ghost
        try:
            draw_fn(ghost, pygame.Rect(0, 0, ghost.get_width(), ghost.get_height()))
        finally:
            self.screen = saved_screen
        ghost.set_alpha(DRAG_GHOST_ALPHA)
        self.screen.blit(ghost, self._mouse_pos)

    def _su(self, v: float) -> int:
        """Дизайн-координата (1280×720) → текущее пространство рендера."""
        s = getattr(self, "_render_scale", 1.0)
        return int(round(v * s))

    def _drop_shadow(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        offset: int = 2,
        alpha: int = 110,
        halo_alpha: int | None = 45,
        halo_spread: int = 1,
        border_radius: int = 4,
        cache_key: str | None = None,
        source: pygame.Surface | None = None,
    ) -> None:
        """Stage 196/197 — единый drop-shadow хелпер (глубина элемента).

        Рисует ПОД элементом (вызывать ДО отрисовки тела): тёмная плашка
        РАЗМЕРОМ ЭЛЕМЕНТА, смещённая на (+offset, +offset) — тень выступает
        за габарит элемента снизу/справа на ``offset`` px (классический
        CSS box-shadow без blur). Опционально мягкий ореол (halo_alpha),
        выступающий ещё на halo_spread.

        source=None — скруглённый прямоугольник (полоски, карточки).
        source=Surface — СИЛУЭТ этой поверхности (альфа → чёрный; иконки
        статусов): тень повторяет форму, а не прямоугольник.

        Кэш _static_surface по (cache_key/геометрии+параметрам) — аллокация
        один раз.

        Args:
            x, y, w, h: прямоугольник ЭЛЕМЕНТА (не тени).
            offset: смещение тени вниз-вправо (px).
            alpha: альфа основной тени (0-255).
            halo_alpha: альфа ореола; None = без ореола.
            halo_spread: на сколько px ореол выступает за основную тень.
            border_radius: скругление плашки (только для прямоугольника).
            cache_key: ключ кэша; None = авто по геометрии+параметрам.
            source: поверхность для силуэтной тени.
        """
        halo = halo_alpha is not None and halo_alpha > 0
        # поверхность больше элемента: слева/сверху offset+halo, справа/снизу
        # тень уходит ещё на offset (+halo_spread).
        pad_left = offset + (halo_spread + 2 if halo else 2)
        pad_top = pad_left
        total_w = w + pad_left + offset + (halo_spread if halo else 0)
        total_h = h + pad_top + offset + (halo_spread if halo else 0)
        key = (
            cache_key
            or f"drop_shadow_{w}x{h}_o{offset}_a{alpha}_h{halo_alpha}_r{border_radius}"
            + ("_sil" if source is not None else "")
        )

        def _draw(s: pygame.Surface) -> None:
            ox = pad_left + offset
            oy = pad_top + offset
            if halo:
                if source is not None:
                    s.blit(
                        _surface_silhouette(source, int(alpha * 0.4)),
                        (ox + halo_spread, oy + halo_spread),
                    )
                else:
                    pygame.draw.rect(
                        s, (0, 0, 0, halo_alpha),
                        pygame.Rect(ox + halo_spread, oy + halo_spread,
                                    w, h),
                        border_radius=border_radius + 2,
                    )
            if source is not None:
                s.blit(_surface_silhouette(source, alpha), (ox, oy))
            else:
                pygame.draw.rect(
                    s, (0, 0, 0, alpha),
                    pygame.Rect(ox, oy, w, h),
                    border_radius=border_radius,
                )

        surf = self._static_surface(key, (total_w, total_h), _draw)
        self.screen.blit(surf, (x - pad_left, y - pad_top))

    def _su_text(self, text: str, size: int, color: tuple[int, int, int],
                 bold: bool = False) -> pygame.Surface:
        """Stage 168 (аудит 5.2) — кэш ОТРИСОВАННОГО текста (LRU).

        `_su_font` кэширует объекты шрифтов, но каждый `font.render()` всё
        равно растеризует глифы и аллоцирует поверхность — на горячих путях
        (карта, бой) одни и те же надписи рендерились 60 раз/сек. Здесь
        поверхность кэшируется по (текст, размер, цвет, жирность, масштаб);
        повторный вызов — O(1) поиск в OrderedDict. Вытеснение — самый
        старый ключ (кап _SU_TEXT_CACHE_CAP).

        ВНИМАНИЕ: возвращённую поверхность НЕЛЬЗЯ мутировать (set_alpha /
        fill / draw) — она разделяется между кадрами. Для динамической альфы
        (gold-flash, fade) рендерите напрямую или снимайте копию (.copy()).
        """
        s = getattr(self, "_render_scale", 1.0)
        key = (text, int(size), tuple(color), bool(bold), round(s, 2))
        cache = getattr(self, "_su_text_cache", None)
        if cache is None:
            cache = self._su_text_cache = OrderedDict()
        surf = cache.get(key)
        if surf is not None:
            cache.move_to_end(key)
            return surf
        surf = self._su_font(size, bold).render(text, True, color)
        cache[key] = surf
        while len(cache) > _SU_TEXT_CACHE_CAP:
            cache.popitem(last=False)
        return surf

    def _static_surface(self, key: str, size: tuple[int, int], draw_fn) -> pygame.Surface:
        """Stage 168 (аудит 5.2) — кэш статических SRCALPHA-поверхностей.

        Горячие пути аллоцировали поверхность + перерисовывали её содержимое
        каждый кадр (фон нижнего бара, иконки золота/купона, тень/кольцо
        бойца, фон боевого лога, затемнения модалок). Здесь draw_fn(surf)
        вызывается ОДИН РАЗ на (key, размер); дальше — только blit.

        draw_fn(surf) рисует содержимое на переданной поверхности (не
        возвращает ничего). Ключ должен включать всё, от чего зависит
        содержимое (цвет заливки и т.п.). Размер кэша ограничен числом
        уникальных ключей — используйте осмысленные имена ("bottom_bar_bg").
        Возвращённую поверхность нельзя мутировать вне draw_fn.
        """
        ck = (key, max(1, int(size[0])), max(1, int(size[1])))
        cache = getattr(self, "_static_surf_cache", None)
        if cache is None:
            cache = self._static_surf_cache = {}
        surf = cache.get(ck)
        if surf is None:
            surf = pygame.Surface((ck[1], ck[2]), pygame.SRCALPHA)
            draw_fn(surf)
            cache[ck] = surf
        return surf

    def _su_font(self, size: int, bold: bool = False) -> pygame.font.Font:
        """Кэшированный шрифт под текущий масштаб рендера.

        Ключ включает масштаб: legacy-фаза (×1) и native-фаза (×UI_SCALE)
        кэшируются РАЗДЕЛЬНО (иначе SysFont(13) и SysFont(26) столкнулись бы).
        """
        s = getattr(self, "_render_scale", 1.0)
        key = (int(size), bool(bold), round(s, 2))
        cache = getattr(self, "_su_font_cache", None)
        if cache is None:
            cache = self._su_font_cache = {}
        f = cache.get(key)
        if f is None:
            f = pygame.font.SysFont("dejavusans,arial", int(round(size * s)), bold=bold)
            cache[key] = f
        return f

    def _su_rect(self, x: float, y: float, w: float, h: float) -> pygame.Rect:
        """`pygame.Rect` из дизайн-координат (все 4 компонента через `_su`)."""
        return pygame.Rect(self._su(x), self._su(y), self._su(w), self._su(h))

    # ------------------------------------------------------------------
    # Stage 153 — ассеты под текущий масштаб (кэш по (ключ, размер рендера))
    # ------------------------------------------------------------------

    def _su_scaled(self, key: str, surf: pygame.Surface, dw: float, dh: float) -> pygame.Surface:
        """Поверхность, отмасштабированная под дизайн-размер `dw×dh` × масштаб.

        Кэш `_su_surface_cache[(key, target_w, target_h)]` — smoothscale не
        выполняется каждый кадр (актуально для фонов 2560×1440 и спрайтов).
        """
        tw = max(1, self._su(dw))
        th = max(1, self._su(dh))
        if surf.get_size() == (tw, th):
            return surf
        cache = getattr(self, "_su_surface_cache", None)
        if cache is None:
            cache = self._su_surface_cache = {}
        ck = (key, tw, th)
        out = cache.get(ck)
        if out is None:
            out = pygame.transform.smoothscale(surf, (tw, th))
            cache[ck] = out
        return out

    def _su_image(self, path: str, dw: float, dh: float) -> pygame.Surface | None:
        """Загрузить PNG с диска ОДИН раз и отмасштабировать под текущий масштаб.

        `None` — файл отсутствует/битый (повторных попыток нет: провал кэшируется).
        Заменяет per-frame `pygame.image.load` в MAP-рендере (Stage 153).
        """
        raw_cache = getattr(self, "_su_image_raw_cache", None)
        if raw_cache is None:
            raw_cache = self._su_image_raw_cache = {}
        if path in raw_cache:
            raw = raw_cache[path]
        else:
            try:
                raw = pygame.image.load(path).convert_alpha()
            except Exception:
                raw = None
            raw_cache[path] = raw
        if raw is None:
            return None
        return self._su_scaled(path, raw, dw, dh)

    def _su_overlay(self, alpha: int) -> pygame.Surface:
        """Полноэкранный SRCALPHA-оверлей под текущее пространство рендера.

        Аналог `asset_manager.get_overlay`, но размер = поверхность рендера
        (в нативной фазе это монитор 2560×1440, а не буфер 1280×720).
        """
        size = self.screen.get_size()
        cache = getattr(self, "_su_overlay_cache", None)
        if cache is None:
            cache = self._su_overlay_cache = {}
        key = (size, int(alpha))
        surf = cache.get(key)
        if surf is None:
            surf = pygame.Surface(size, pygame.SRCALPHA)
            surf.fill((0, 0, 0, int(alpha)))
            cache[key] = surf
        return surf

    def _su_icon_size(
        self,
        iw: int,
        ih: int,
        rect: pygame.Rect,
        pad: float = 6.0,
        upscale_cap: float = 1.3,
    ) -> tuple[int, int]:
        """Финальный размер иконки для `rect` с семантикой Stage 142/149.

        Масштаб считается в ДИЗАЙН-пространстве (`rect` уже нативный — делим на
        `_render_scale`), затем финальный размер умножается на масштаб рендера:
          * Stage 142 — апскейл выше `upscale_cap` запрещён (мелкие холсты 24×24
            не растягиваются до края ячейки → без «мыла»).
          * Stage 149 — если иконка влезает в rect БЕЗ масштаба, даунскейла нет
            (лишний проход smoothscale = блюр).
        """
        s = getattr(self, "_render_scale", 1.0)
        design_w = rect.w / s
        design_h = rect.h / s
        max_w = design_w - pad
        max_h = design_h - pad
        if iw <= 0 or ih <= 0 or max_w <= 0 or max_h <= 0:
            return (max(1, iw), max(1, ih))
        scale = min(max_w / iw, max_h / ih)
        if scale > upscale_cap:
            scale = 1.0
        if scale < 1.0 and iw <= design_w and ih <= design_h:
            scale = 1.0
        return (max(1, int(iw * scale * s)), max(1, int(ih * scale * s)))

    # ------------------------------------------------------------------
    # Stage 152 — общий fade-in модалок (обобщение Stage 136 карты мира)
    # ------------------------------------------------------------------

    def _modal_fade_begin(self, key: str) -> None:
        """Запустить fade-in модалки `key` (альфа с 0.0)."""
        fades = getattr(self, "_modal_fades", None)
        if fades is None:
            fades = self._modal_fades = {}
        fades[key] = 0.0

    def _modal_fade_end(self, key: str) -> None:
        """Сбросить fade модалки `key` (следующее открытие начнётся с 0)."""
        fades = getattr(self, "_modal_fades", None)
        if fades is not None:
            fades[key] = 1.0

    def _modal_fade_tick(self, key: str, dt: float) -> None:
        """Продвинуть альфу модалки `key` за MODAL_FADE_SEC."""
        from pockie_rpg.config import MODAL_FADE_SEC
        fades = getattr(self, "_modal_fades", None)
        if fades is None:
            return
        a = fades.get(key, 1.0)
        if a >= 1.0:
            return
        speed = 1.0 / MODAL_FADE_SEC if MODAL_FADE_SEC > 0 else 1.0
        fades[key] = min(1.0, a + speed * dt)

    def _modal_fade_value(self, key: str) -> float:
        """Текущая альфа модалки `key` (1.0 — анимация завершена/не запускалась).

        ВНИМАНИЕ: имя НЕ `_modal_fade_alpha` — так называется float-поле из
        Stage 128 (`self._modal_fade_alpha`), оно бы затенило метод.
        """
        fades = getattr(self, "_modal_fades", None)
        if fades is None:
            return 1.0
        return fades.get(key, 1.0)

    def _fade_buffer(self, size: tuple[int, int]) -> pygame.Surface:
        """Переиспользуемый SRCALPHA-буфер под fade (кэш по размеру).

        В нативной фазе цель = монитор 2560×1440: аллоцировать такую поверхность
        каждый кадр нельзя, поэтому буфер один на размер и лишь очищается.
        """
        cache = getattr(self, "_fade_buffers", None)
        if cache is None:
            cache = self._fade_buffers = {}
        buf = cache.get(size)
        if buf is None:
            buf = pygame.Surface(size, pygame.SRCALPHA)
            cache[size] = buf
        return buf

    def _render_with_fade(self, key: str, render_fn, *args, **kwargs) -> None:
        """Отрисовать модалку с учётом её fade-альфы.

        alpha >= 1.0 — прямой рендер в `self.screen` (без лишнего буфера).
        Иначе — рендер в переиспользуемый буфер размера цели + blit с альфой.
        ClickRect'ы не трогаются: координаты внутри буфера совпадают с целевыми.
        """
        alpha = self._modal_fade_value(key)
        if alpha >= 1.0:
            render_fn(*args, **kwargs)
            return
        target = self.screen
        buf = self._fade_buffer(target.get_size())
        buf.fill((0, 0, 0, 0))
        self.screen = buf
        try:
            render_fn(*args, **kwargs)
        finally:
            self.screen = target
        buf.set_alpha(int(alpha * 255))
        target.blit(buf, (0, 0))
        buf.set_alpha(255)
