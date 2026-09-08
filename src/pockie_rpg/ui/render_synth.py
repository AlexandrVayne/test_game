"""SynthRendererMixin + WardrobeRendererMixin — Stage 138 / пересборка Stage 156/157.

ПРАВИЛО 9: boolean-флаги _synth_modal_open / _wardrobe_modal_open внутри
GameState.MAP. Синтез: главный + 2 катализатора → шанс +N+1 (провал сжигает
катализаторы). Гардероб: 5 слотов-хранилищ под костюмы + кнопка «Вынуть».

Stage 156 — НАТИВНЫЙ рендер (раньше: буфер 1280×720 → растяжение ×2 = «мыло»):
координаты через self._su(), шрифты через self._su_font(), затемнение через
_su_overlay(). ЕДИНЫЙ размер окон SYNTHWARD_MODAL_W/H.

Stage 157 — ОБЩИЕ перетаскиваемые окна (ScalableRendererMixin): локальная
drag-механика удалена, окна регистрируются через _render_window_titlebar /
_window_pos("synth"|"wardrobe"). Позиции persist в сейве
(PlayerState.window_positions).

Stage 157 — DRAG-AND-DROP МЕЖДУ СЛОТАМИ СИНТЕЗА: предметы можно не только
класть в слоты из инвентаря, но и ПЕРЕТАСКИВАТЬ между слотами
(главный ↔ катализатор ×2) — «в руке» удерживается loc, дроп в другой слот
меняет их местами/перемещает. Клик по заполненному слоту по-прежнему очищает.

Stage 162 — ОКНА НЕ ЗАТЕМНЯЮТ ФОН и НЕ ЗАКРЫВАЮТСЯ КЛИКОМ ВНЕ: игрок
перетаскивает костюмы из инвентаря в слоты, фон должен оставаться видимым.

Stage 163 — СИНТЕЗ КОМПАКТНЕЕ И ЧИЩЕ (запрос пользователя): из шапки убрана
grip-подсказка «⠿ перетащить» (и квадратик-символ), заголовок «Синтез» — по
ЦЕНТРУ окна; удалены поле превью-ошибки («Заполните все 3 слота») и поле шанса
(«—») — сообщения об ошибках по-прежнему показываются строкой результата при
нажатии «Создать». Окно: 480×360 → 400×248 (контент — 4 слота 72px + 3 зазора
24px = 360px, поля 20px слева/справа).

Stage 166 — РЕЗУЛЬТАТ ОСТАЁТСЯ В СЛОТЕ (запрос пользователя):
* успешный синтез кладёт созданный инстанс +N+1 в СЛОТ РЕЗУЛЬТАТА
  (_synth_result_item), а НЕ в инвентарь; забрать — клик (ЛКМ/ПКМ) по
  слоту результата (или закрытие окна возвращает всё в инвентарь);
* под слотом результата — краткий текст «(костюм +N)» БЕЗ требуемого
  уровня (длинные ошибки переносятся/обрезаются — раньше вылезали за
  окно); синтезировать можно ЛЮБЫЕ уровни (гейт уровня снят в state),
  носить — строго по требованию (equip_gear_item);
* слоты синтеза получили ЯЧЕЙКИ 2×3 (как мини-сетка инвентаря), костюм
  центрируется в слоте; при наведении на заполненный слот — тултип
  костюма (как в инвентаре).

Stage 164 — СИНТЕЗ КАК РАБОЧИЙ СТОЛ (запросы пользователя):
* слоты хранят САМИ ПРЕДМЕТЫ (item_id), а не ссылки на ячейки инвентаря:
  при дропе костюм ФИЗИЧЕСКИ уходит из инвентаря — один экземпляр нельзя
  положить в два слота (прежний баг: loc-ссылка дублировалась, рецепт
  «Нужны 3 РАЗНЫХ ячейки» держал кнопку «Создать» неактивной);
* клик или ПКМ по заполненному слоту ВОЗВРАЩАЕТ костюм в инвентарь;
* закрытие окна тоже возвращает всё в инвентарь (потерь нет);
* под слотом РЕЗУЛЬТАТ при трёх заполненных слотах пишется ШАНС %
  удачного синтеза (или причина, почему рецепт невалиден);
* drag-призрак (иконка «в руке») рисуется ПОВЕРХ всех окон —
  см. pygame_ui._render_drag_ghost_topmost.
"""
from __future__ import annotations

import pygame

from pockie_rpg.config import WARDROBE_PAGES, WARDROBE_SLOTS_PER_PAGE
from pockie_rpg.ui.animator import ClickRect

SYNTH_MODAL_W: int = 400       # Stage 163 — было 640 (162: 480): 4 слота 72 + 3×24 = 360 + поля 20
SYNTH_MODAL_H: int = 248      # Stage 163 — было 440 (161: 360): убраны поля превью/шанса
SYNTHWARD_MODAL_W: int = 480  # гардероб (Stage 162): контент 464px
SYNTHWARD_MODAL_H: int = 484  # гардероб: 5 слотов (70 + 5×78) + пагинация снизу (Stage 167)
SYNTH_SLOT_W: int = 44        # Stage 186 — сетка 2×18+зазор + 2×3px отступ
SYNTH_SLOT_H: int = 64        # Stage 186 — 3×18+2 зазора + 2×3px отступ
SYNTH_CELL = 18               # ячейка (как мини-сетка инвентаря)
SYNTH_CELL_GAP = 2            # зазор ячеек
SYNTH_SLOT_PAD = 3            # Stage 186 — минимальный отступ сетки от края слота
SYNTH_SLOT_COLORS = {
    "main": (234, 179, 8),
    "cat": (100, 180, 255),
    "result": (80, 220, 100),
}

SYNTH_WINDOW_KEY = "synth"
WARDROBE_WINDOW_KEY = "wardrobe"


class SynthRendererMixin:
    """Модалка синтеза костюмов (ПРАВИЛО 9: флаг _synth_modal_open).

    Stage 164 — слоты хранят item_id (_synth_main_item/_synth_cat1_item/
    _synth_cat2_item); предмет физически вне инвентаря, пока в слоте.
    """

    # Атрибуты слотов синтеза (порядок = главный, кат.1, кат.2).
    _SYNTH_SLOT_ATTRS = ("_synth_main_item", "_synth_cat1_item", "_synth_cat2_item")
    # Stage 166 — слот результата хранит созданный инстанс +N+1 (не принимает
    # drag; забрать — клик). Возврат в инвентарь — всеми тремя путями
    # (клик/ПКМ/закрытие) через _synth_collect_result.
    _SYNTH_RESULT_ATTR = "_synth_result_item"
    _SYNTH_RETURN_ATTRS = _SYNTH_SLOT_ATTRS + (_SYNTH_RESULT_ATTR,)

    def _synth_window_pos(self) -> tuple[int, int]:
        """Stage 157 — позиция окна синтеза (общий реестр, persist в сейве)."""
        return self._window_pos(SYNTH_WINDOW_KEY, SYNTH_MODAL_W, SYNTH_MODAL_H)

    def _open_synth_modal(self) -> None:
        self._synth_modal_open = True
        # Stage 164 — всё, что осталось в слотах (окно закрывали при полном
        # инвентаре), возвращается в инвентарь; окно открывается пустым.
        self._synth_return_all_to_inventory()
        self._synth_main_item = None
        self._synth_cat1_item = None
        self._synth_cat2_item = None
        # Stage 171 — слот результата НЕ стирается принудительно: если
        # вернуть его в инвентарь не удалось (нет места), он остаётся
        # в слоте — как и обещает _synth_return_all_to_inventory.
        self._synth_result_msg = ""
        self._synth_success_flash = 0.0

    def _close_synth_modal(self) -> None:
        # Stage 164 — костюмы из слотов возвращаются в инвентарь (потерь
        # нет ни при крестике, ни при Escape, ни при выходе из игры).
        # Stage 166 — включая результат синтеза из слота результата.
        self._synth_return_all_to_inventory()
        self._synth_modal_open = False
        self._synth_slot_drag = None

    def _synth_return_all_to_inventory(self) -> None:
        """Stage 164/166 — вернуть предметы из всех слотов синтеза в инвентарь.

        Stage 166 — сюда входит и слот РЕЗУЛЬТАТА (_synth_result_item).
        Слот очищается ТОЛЬКО при успешном inv_add: если инвентарь полон,
        предмет остаётся в слоте (не теряется) и вернётся при следующем
        открытии окна/выходе из игры, когда место освободится.
        """
        changed = False
        for attr in self._SYNTH_RETURN_ATTRS:
            item_id = getattr(self, attr, None)
            if item_id is None:
                continue
            if self.player is not None and self.player.inv_add(item_id):
                setattr(self, attr, None)
                changed = True
        if changed:
            self._save_player()

    def _bind_synth_slots_provider(self, player) -> None:
        """Stage 171 — B3: UI отдаёт state живые слоты синтеза на момент сейва.

        Провайдер (callable) вызывается to_dict'ом В МОМЕНТ сохранения —
        ссылки на инстансы в слотах не теряются ни при каком порядке
        мутаций (слоты физически вне инвентаря, Stage 164/166).
        """
        if player is None:
            return
        player.synth_slots_provider = lambda: (
            getattr(self, "_synth_main_item", None),
            getattr(self, "_synth_cat1_item", None),
            getattr(self, "_synth_cat2_item", None),
            getattr(self, self._SYNTH_RESULT_ATTR, None),
        )

    def _synth_modal_rect(self) -> pygame.Rect:
        """Дизайн-rect окна (панельный хиттест закрытия — в дизайне)."""
        x, y = self._synth_window_pos()
        return pygame.Rect(x, y, SYNTH_MODAL_W, SYNTH_MODAL_H)

    # ------------------------------------------------------------------
    # Слоты / логика выбора.
    # ------------------------------------------------------------------

    def _synth_collect_result(self) -> None:
        """Stage 166 — забрать результат синтеза из слота результата в инвентарь.

        Если в инвентаре нет места — предмет ОСТАЁТСЯ в слоте (не теряется),
        игрок видит сообщение «Нет места в инвентаре».
        """
        item_id = getattr(self, self._SYNTH_RESULT_ATTR, None)
        if item_id is None:
            return
        if self.player is not None and self.player.inv_add(item_id):
            setattr(self, self._SYNTH_RESULT_ATTR, None)
            self._synth_result_msg = ""
            self._save_player()
        else:
            self._synth_result_msg = "Нет места в инвентаре"

    def _synth_pick_item(self, pos: tuple[int, int]) -> None:
        """Клик по заполненному слоту — вернуть костюм в инвентарь.

        Stage 157 — перенос между слотами начинается удержанием + движением
        (см. _synth_slot_drag_begin/_synth_slot_drag_finish); клик без
        движения обрабатывается в _synth_slot_drag_finish.
        Stage 164 — предмет физически возвращается в инвентарь (раньше
        слот просто очищался — предмет был ссылками в инвентаре).
        Stage 166 — клик по СЛОТУ РЕЗУЛЬТАТА забирает костюм в инвентарь.
        """
        main_r, cat1_r, cat2_r, res_r = self._synth_slot_rects()
        if res_r.collidepoint(pos):
            self._synth_collect_result()
            return
        for rect, attr in zip((main_r, cat1_r, cat2_r), self._SYNTH_SLOT_ATTRS):
            if rect.collidepoint(pos):
                item_id = getattr(self, attr, None)
                if item_id is not None and self.player is not None \
                        and self.player.inv_add(item_id):
                    setattr(self, attr, None)
                    self._save_player()
                return

    def _synth_slot_drag_begin(self, pos: tuple[int, int]) -> bool:
        """Stage 157 — LMB down на ЗАПОЛНЕННОМ слоте синтеза → запомнить.

        Возвращает True, если слот-источник найден (клик не диспетчируется).
        Сам перенос стартует в _synth_slot_drag_motion при движении > порога.
        Stage 166 — слот результата drag НЕ начинает (забирание — кликом).
        """
        main_r, cat1_r, cat2_r, _res_r = self._synth_slot_rects()
        for rect, attr in zip((main_r, cat1_r, cat2_r), self._SYNTH_SLOT_ATTRS):
            if rect.collidepoint(pos) and getattr(self, attr, None) is not None:
                self._synth_slot_drag = (attr, pos)
                return True
        return False

    def _synth_slot_drag_motion(self, pos: tuple[int, int]) -> None:
        """Stage 157 — MOUSEMOTION: движение > порога превращает удержание
        слота в перенос (лок «в руке»)."""
        drag = getattr(self, "_synth_slot_drag", None)
        if drag is None or len(drag) != 2:
            return
        attr, origin = drag
        dx = pos[0] - origin[0]
        dy = pos[1] - origin[1]
        if (dx * dx + dy * dy) >= (self._DRAG_THRESHOLD * self._DRAG_THRESHOLD):
            self._synth_slot_drag = (attr, origin, True)

    def _synth_slot_drag_active(self) -> bool:
        """Stage 157 — идёт ли перенос между слотами (loc «в руке»)?"""
        drag = getattr(self, "_synth_slot_drag", None)
        return drag is not None and len(drag) == 3

    def _synth_slot_drag_finish(self, pos: tuple[int, int]) -> None:
        """Stage 157/164 — LMB up: дроп item в другой слот (перемещение/обмен).

        Без движения (клик) — костюм ВОЗВРАЩАЕТСЯ В ИНВЕНТАРЬ (Stage 164;
        раньше слот просто очищался). Дроп в СВОЙ слот при активном переносе
        = отмена (item остаётся). Дроп мимо слотов — отмена.
        """
        drag = getattr(self, "_synth_slot_drag", None)
        self._synth_slot_drag = None
        if drag is None:
            return
        attr_src = drag[0]
        if not self._synth_slot_drag_active_was(drag):
            # Клик без движения — прежний UX: вернуть костюм в инвентарь.
            item_id = getattr(self, attr_src, None)
            if item_id is not None and self.player is not None \
                    and self.player.inv_add(item_id):
                setattr(self, attr_src, None)
                self._save_player()
            return
        main_r, cat1_r, cat2_r, _res_r = self._synth_slot_rects()
        for rect, attr in zip((main_r, cat1_r, cat2_r), self._SYNTH_SLOT_ATTRS):
            if rect.collidepoint(pos):
                if attr == attr_src:
                    return  # дроп на место — отмена.
                # Перемещение/обмен item между слотами.
                src_item = getattr(self, attr_src)
                tgt_item = getattr(self, attr)
                setattr(self, attr, src_item)
                setattr(self, attr_src, tgt_item)
                return
        # Дроп мимо слотов — отмена (item остаётся).

    def _synth_slot_drag_active_was(self, drag) -> bool:
        """Stage 157 — был ли drag «активным переносом» (3-элементный кортеж)."""
        return drag is not None and len(drag) == 3

    def _synth_slot_rects(self) -> tuple[pygame.Rect, pygame.Rect, pygame.Rect, pygame.Rect]:
        """Stage 161 — 4 слота ОДНИМ рядом: ГЛАВНЫЙ + КАТ.1 + КАТ.2 = РЕЗУЛЬТАТ.

        Раньше result считался как main_r.right + 24 — совпадал с координатой
        КАТ.1 и рисовался ПОВЕРХ него (жалоба пользователя «второй слот как
        будто наложен на что-то ещё»). Теперь все 4 слота равномерно в ряд.
        """
        panel = self._synth_modal_rect()
        y = panel.y + 80
        cx = panel.centerx
        gap = 24
        total = SYNTH_SLOT_W * 4 + gap * 3
        x0 = cx - total // 2
        sw = self._su(SYNTH_SLOT_W)
        sh = self._su(SYNTH_SLOT_H)
        step = self._su(SYNTH_SLOT_W + gap)
        main_r = pygame.Rect(self._su(x0), self._su(y), sw, sh)
        cat1_r = pygame.Rect(main_r.x + step, main_r.y, sw, sh)
        cat2_r = pygame.Rect(cat1_r.x + step, main_r.y, sw, sh)
        result_r = pygame.Rect(cat2_r.x + step, main_r.y, sw, sh)
        return main_r, cat1_r, cat2_r, result_r

    def _synth_do(self) -> None:
        """Кнопка «Создать»: выполнить синтез + сообщение (Stage 164 — item_id).

        Stage 184 — если в главном слоте БАФ ОПЫТА — ветка buff_synth
        (3 одинаковых → 1 следующий вид, шансы 75/50/25). Провал: сгорают
        ВСЕ 3 бафа (цена попытки); успех: баф результата в слоте результата.
        Для костюмов — прежняя логика (провал: катализаторы сгорают, главный
        остаётся).
        """
        if getattr(self, "_synth_result_item", None) is not None:
            self._synth_collect_result()
            if getattr(self, "_synth_result_item", None) is not None:
                self._synth_result_msg = "Сначала заберите результат из слота"
                return
        main_id = self._synth_main_item
        from pockie_rpg.config import get_buff

        if main_id is not None and get_buff(main_id) is not None:
            res = self.player.buff_synth_execute(
                main_id, self._synth_cat1_item, self._synth_cat2_item,
            )
            self._save_player()
            if res["success"]:
                self._synth_result_msg = "Успех! Заберите баф из слота результата"
                self._synth_success_flash = 1.0
                self._synth_main_item = None
                self._synth_cat1_item = None
                self._synth_cat2_item = None
                self._synth_result_item = res.get("result_id")
            elif res.get("error"):
                self._synth_result_msg = res["error"]
            else:
                self._synth_result_msg = "Провал: все 3 бафа сгорели"
                self._synth_main_item = None
                self._synth_cat1_item = None
                self._synth_cat2_item = None
            return

        pv = self.player.synth_preview(self._synth_main_item, self._synth_cat1_item, self._synth_cat2_item)
        if not pv["ok"]:
            self._synth_result_msg = pv["error"]
            return
        res = self.player.synth_execute(self._synth_main_item, self._synth_cat1_item, self._synth_cat2_item)
        self._save_player()
        if res["success"]:
            self._synth_result_msg = "Успех! Заберите костюм из слота результата"
            self._synth_success_flash = 1.0
            self._synth_main_item = None
            self._synth_cat1_item = None
            self._synth_cat2_item = None
            self._synth_result_item = res.get("result_id")
        elif res.get("error"):
            self._synth_result_msg = res["error"]
        else:
            self._synth_result_msg = "Провал: катализаторы сгорели"
            self._synth_cat1_item = None
            self._synth_cat2_item = None

    # ------------------------------------------------------------------
    # Рендер.
    # ------------------------------------------------------------------

    def _draw_synth_slot_grid(self, rect: pygame.Rect) -> None:
        """Stage 184/186 — сетка 2×3 внутри слота, ЦЕНТРИРОВАНА с минимальным
        отступом (SYNTH_SLOT_PAD=3px) от краёв слота (запрос пользователя).

        Слот 44×64 = сетка 38×58 + по 3px с каждой стороны. Ячейки — чисто
        визуальная разметка, на хиттесты не влияют.
        """
        su = self._su
        cell = su(SYNTH_CELL)
        gap = su(SYNTH_CELL_GAP)
        cols, rows = 2, 3
        grid_w = cols * cell + (cols - 1) * gap
        grid_h = rows * cell + (rows - 1) * gap
        gx = rect.x + (rect.w - grid_w) // 2
        gy = rect.y + (rect.h - grid_h) // 2
        for row in range(rows):
            for col in range(cols):
                cr = pygame.Rect(gx + col * (cell + gap),
                                 gy + row * (cell + gap), cell, cell)
                pygame.draw.rect(self.screen, (31, 31, 34), cr, border_radius=3)
                pygame.draw.rect(self.screen, (50, 50, 55), cr, 1, border_radius=3)

    @staticmethod
    def _synth_fit_lines(text: str, font: pygame.font.Font, max_w: int) -> list[str]:
        """Stage 166 — вписать текст в max_w: ≤ 2 строки, хвост — с «…».

        Под слотом результата раньше рисовалась ОДНА строка ошибки, которая
        вылезала за край окна («Костюм +2 требует ур. 10» и т.п.). Теперь
        длинный текст переносится на 2-ю строку, а всё, что не влезло,
        обрезается с многоточием.
        """
        if font.size(text)[0] <= max_w:
            return [text]
        lines: list[str] = []
        cur = ""
        for word in text.split():
            cand = f"{cur} {word}" if cur else word
            if font.size(cand)[0] <= max_w or not cur:
                cur = cand
            else:
                lines.append(cur)
                if len(lines) == 2:
                    break
                cur = word
        if len(lines) < 2 and cur:
            lines.append(cur)
        if not lines:
            lines = [text]
        tail = lines[-1]
        if font.size(tail)[0] > max_w:
            while tail and font.size(tail + "…")[0] > max_w:
                tail = tail[:-1]
            lines[-1] = tail + "…"
        return lines[:2]

    def _render_synth_modal(self) -> None:
        su = self._su
        panel = self._synth_modal_rect()
        # Stage 162 — фон НЕ затемняется (запрос пользователя): инвентарь
        # за окном остаётся видимым, из него перетаскиваются костюмы.
        panel_r = pygame.Rect(su(panel.x), su(panel.y), su(panel.w), su(panel.h))
        pygame.draw.rect(self.screen, (24, 24, 27), panel_r, border_radius=12)
        pygame.draw.rect(self.screen, (234, 179, 8),
                        (panel_r.x, panel_r.y, panel_r.w, su(4)), border_radius=2)
        # Stage 157/158 — общая шапка (drag + persist) + выносной крестик.
        # Stage 163/164 — заголовок по ЦЕНТРУ окна, grip-подсказки нет
        # (поведение по умолчанию _render_window_titlebar).
        self._render_window_titlebar(
            SYNTH_WINDOW_KEY, panel_r, "Синтез",
            (234, 179, 8), self._synth_modal_open,
            open_attr="_synth_modal_open",
            on_close=self._close_synth_modal,
        )

        # Слоты ОДНИМ рядом: [ГЛАВНЫЙ] + [КАТ.1] + [КАТ.2] = [РЕЗУЛЬТАТ].
        main_r, cat1_r, cat2_r, result_r = self._synth_slot_rects()
        eq_y = main_r.y + main_r.h // 2
        plus_x1 = main_r.right + su(6)
        plus_x2 = cat1_r.right + su(6)
        eq_x = cat2_r.right + su(6)
        # Stage 164 — слоты хранят item_id; предмет физически вне инвентаря.
        slot_entries = (
            (main_r, "ГЛАВНЫЙ", "_synth_main_item"),
            (cat1_r, "КАТ. 1", "_synth_cat1_item"),
            (cat2_r, "КАТ. 2", "_synth_cat2_item"),
        )
        is_dragging = self._drag_item_id is not None
        # Stage 157 — drag МЕЖДУ слотами синтеза (item «в руке»).
        slot_drag = getattr(self, "_synth_slot_drag", None)
        slot_drag_attr = slot_drag[0] if slot_drag else None
        # Stage 166 — item заполненного слота ПОД КУРСОРОМ (для тултипа).
        hover_item: str | None = None
        for rect, label, attr in slot_entries:
            hover = rect.collidepoint(self._mouse_pos)
            drop_target = hover and is_dragging
            # Подсветка при переносе между слотами: цель золотая.
            swap_target = (hover and slot_drag is not None
                           and attr != slot_drag_attr)
            is_src = (attr == slot_drag_attr)
            bg = (55, 55, 60) if hover else (39, 39, 42)
            if drop_target:
                bg = (60, 50, 10)
            if swap_target:
                bg = (60, 50, 10)
            pygame.draw.rect(self.screen, bg, rect, border_radius=6)
            color = SYNTH_SLOT_COLORS["main"] if label == "ГЛАВНЫЙ" else SYNTH_SLOT_COLORS["cat"]
            border_col = color if (hover or drop_target or swap_target) else (82, 82, 91)
            if swap_target:
                border_col = (96, 165, 250)
            pygame.draw.rect(self.screen, border_col, rect,
                             2 if (hover or drop_target or swap_target) else 1,
                             border_radius=6)
            # Stage 166 — ячейки 2×3 внутри слота (разметка как в инвентаре).
            self._draw_synth_slot_grid(rect)
            lbl = self._su_font(12).render(label, True, color)
            self.screen.blit(lbl, lbl.get_rect(midtop=(rect.centerx, rect.y - su(14))))
            key = getattr(self, attr, None)
            if key is not None:
                # Источник слот-drag'а рисуем полупрозрачно («в руке»).
                if is_src and slot_drag is not None:
                    ghost = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
                    ghost.fill((39, 39, 42, 140))
                    self.screen.blit(ghost, rect.topleft)
                gear = self.player.get_item_definition(key)
                if gear:
                    # Stage 186 — БЕЗ фона редкости и БЕЗ апскейла: иконка
                    # остаётся натурального размера, сетка 2×3 видна вокруг.
                    self._blit_gear_icon(gear, rect, with_bg=False, max_upscale=1.0)
                    plus = self.player._outfit_plus_of(key, self.player)
                    if plus > 0:
                        p_surf = self._su_font(13).render(f"+{plus}", True, (234, 179, 8))
                        self.screen.blit(p_surf, (rect.right - p_surf.get_width() - su(2),
                                                  rect.bottom - su(18)))
                    if hover and not is_src:
                        hover_item = key
        # Результат-слот (не принимает drag; Stage 166 — хранит результат
        # синтеза +N+1, забрать — кликом ЛКМ/ПКМ).
        res_hover = result_r.collidepoint(self._mouse_pos)
        pygame.draw.rect(self.screen, (55, 55, 60) if res_hover else (39, 39, 42),
                         result_r, border_radius=6)
        pygame.draw.rect(self.screen, SYNTH_SLOT_COLORS["result"] if res_hover else (82, 82, 91),
                         result_r, 2 if res_hover else 1, border_radius=6)
        r_lbl = self._su_font(12).render("РЕЗУЛЬТАТ", True, SYNTH_SLOT_COLORS["result"])
        self.screen.blit(r_lbl, r_lbl.get_rect(midtop=(result_r.centerx, result_r.y - su(14))))
        self._draw_synth_slot_grid(result_r)
        result_key = getattr(self, "_synth_result_item", None)
        if result_key is not None:
            res_gear = self.player.get_item_definition(result_key)
            if res_gear:
                # Stage 186 — как в слотах: без фона, натуральный размер.
                self._blit_gear_icon(res_gear, result_r, with_bg=False, max_upscale=1.0)
                res_plus = self.player._outfit_plus_of(result_key, self.player)
                if res_plus > 0:
                    rp_surf = self._su_font(13).render(f"+{res_plus}", True, (234, 179, 8))
                    self.screen.blit(rp_surf,
                                     (result_r.right - rp_surf.get_width() - su(2),
                                      result_r.bottom - su(18)))
                if res_hover:
                    hover_item = result_key
        elif slot_drag is None and not is_dragging:
            placeholder = self._su_font(13).render("?", True, (82, 82, 91))
            self.screen.blit(placeholder, placeholder.get_rect(center=result_r.center))
        # Знаки «+», «+», «=» между слотами.
        for x, sym in ((plus_x1, "+"), (plus_x2, "+"), (eq_x, "=")):
            sym_surf = self._su_font(18, bold=True).render(sym, True, (180, 180, 188))
            self.screen.blit(sym_surf, sym_surf.get_rect(midbottom=(x + su(6), eq_y + su(8))))

        # Превью рецепта (валидация + шанс) — Stage 164: считается ОДИН раз.
        # Stage 166 — текст под слотом РЕЗУЛЬТАТА (запрос пользователя):
        # * при валидном рецепте — «(костюм +N)» (что получится, БЕЗ
        #   требуемого уровня) и «Шанс: N%»;
        # * при ошибке — текст ошибки (переносится на 2 строки/обрезается —
        #   раньше вылезал за край окна);
        # * когда результат уже лежит в слоте — «(костюм +N)» этого костюма.
        # Stage 184 — ветка БАФОВ: «(Опыт +100%)» + шанс 75/50/25.
        main_id_preview = self._synth_main_item
        from pockie_rpg.config import get_buff as _gb
        if main_id_preview is not None and _gb(main_id_preview) is not None:
            preview = self.player.buff_synth_preview(
                main_id_preview, self._synth_cat1_item, self._synth_cat2_item,
            )
        else:
            preview = self.player.synth_preview(
                self._synth_main_item, self._synth_cat1_item, self._synth_cat2_item,
            )
        all_filled = (self._synth_main_item is not None
                      and self._synth_cat1_item is not None
                      and self._synth_cat2_item is not None)
        under_lines: list[tuple[str, tuple[int, int, int]]] = []
        if result_key is not None:
            res_def = self.player.get_item_definition(result_key)
            if res_def is not None and res_def.get("is_buff"):
                under_lines.append((f"({res_def.get('name', '')})", (234, 179, 8)))
            else:
                r_plus = self.player._outfit_plus_of(result_key, self.player)
                under_lines.append((f"(костюм +{r_plus})", (234, 179, 8)))
        elif all_filled:
            if preview["ok"]:
                if preview.get("result_id") is not None:
                    # Ветка бафов: result_id = следующий баф.
                    res_def = self.player.get_item_definition(preview["result_id"])
                    under_lines.append(
                        (f"({res_def.get('name', '')})", (234, 179, 8)))
                else:
                    under_lines.append(
                        (f"(костюм +{preview['result_plus']})", (234, 179, 8)))
                under_lines.append(
                    (f"Шанс: {preview['chance']}%", (80, 220, 100)))
            else:
                under_lines.append((preview["error"], (248, 113, 113)))
        if under_lines:
            f_under = self._su_font(12)
            max_line_w = su(panel.w - 12)
            y = result_r.bottom + su(4)
            for line_txt, line_col in under_lines:
                for ln in self._synth_fit_lines(line_txt, f_under, max_line_w):
                    ln_surf = f_under.render(ln, True, line_col)
                    lx = result_r.centerx - ln_surf.get_width() // 2
                    lx = max(su(panel.x + 6),
                             min(lx, su(panel.right - 6) - ln_surf.get_width()))
                    self.screen.blit(ln_surf, (lx, y))
                    y += su(14)

        # Иконка «в руке» при переносе между слотами — рисуется ПОСЛЕДНЕЙ
        # общим overlay (Stage 164, _render_drag_ghost_topmost), чтобы быть
        # ПОВЕРХ окна (жалоба: костюм пропадал за окном синтеза).

        # Сообщение результата / кнопка «Создать».
        self._synth_success_flash = max(0.0, self._synth_success_flash - 0.02)
        if self._synth_result_msg:
            msg_color = (80, 220, 100) if self._synth_result_msg.startswith("Успех") else (248, 113, 113)
            msg = self._su_font(13).render(self._synth_result_msg, True, msg_color)
            self.screen.blit(msg, msg.get_rect(midbottom=(panel_r.centerx, panel_r.bottom - su(58))))
        do_btn = pygame.Rect(panel_r.centerx - su(70), panel_r.bottom - su(46),
                             su(140), su(32))
        do_hover = do_btn.collidepoint(self._mouse_pos)
        can_do = preview["ok"] if preview else False
        do_bg = (60, 50, 10) if (do_hover and can_do) else ((40, 40, 45) if not can_do else (50, 44, 14))
        pygame.draw.rect(self.screen, do_bg, do_btn, border_radius=8)
        pygame.draw.rect(self.screen, (234, 179, 8) if (do_hover and can_do) else (82, 82, 91),
                         do_btn, su(2), border_radius=8)
        do_lbl = self._su_font(18, bold=True).render("Создать", True,
                                                     (255, 255, 255) if can_do else (113, 113, 122))
        self.screen.blit(do_lbl, do_lbl.get_rect(center=do_btn.center))
        if can_do:
            self._click_rects.append(ClickRect(tag="synth_do", rect=do_btn, on_click=self._synth_do))

        # Stage 161 — лента «Ваши костюмы» УДАЛЕНА (запрос пользователя):
        # наполнение слотов — ТОЛЬКО перетаскиванием предметов из инвентаря
        # (дроп обрабатывает _finish_drag в render_inventory.py).
        # Stage 158 — внутренний крестик УДАЛЁН (выносной рисует шапка).

        # Stage 166 — тултип костюма при наведении на ЗАПОЛНЕННЫЙ слот
        # (главный/катализаторы) или слот результата — тот же, что в
        # инвентаре (маршрут _render_gear_tooltip → outfit-ветка).
        # Во время любого drag'а тултип не показывается.
        if hover_item is not None and self._drag_item_id is None \
                and slot_drag is None:
            self._render_gear_tooltip(hover_item, panel.right)

    def _render_synth_slot_drag_ghost(self) -> None:
        """Stage 164 — призрак предмета «в руке» при переносе между слотами.

        Вынесен из _render_synth_modal: рисуется общим topmost-overlay
        (pygame_ui._render_drag_ghost_topmost) ПОВЕРХ всех окон — иначе
        призрак прятался за гардероб/другие окна.
        """
        su = self._su
        slot_drag = getattr(self, "_synth_slot_drag", None)
        if slot_drag is None:
            return
        item_id = getattr(self, slot_drag[0], None)
        if not item_id:
            return
        gear = self.player.get_item_definition(item_id)
        if not gear:
            return
        # Stage 160 — призрак на кончике курсора + прозрачность
        # (единый хелпер с инвентарём).
        ghost_size = su(72)

        def _draw_slot_ghost(target, rect):
            pygame.draw.rect(target, (234, 179, 8, 60), rect, border_radius=6)
            # Stage 186 — без фона редкости, натуральный размер.
            self._blit_gear_icon(gear, rect, with_bg=False, max_upscale=1.0)
            pygame.draw.rect(target, (234, 179, 8), rect, su(2), border_radius=6)

        self._render_drag_ghost(_draw_slot_ghost, ghost_size, ghost_size)

    def _handle_synth_right_click(self, pos: tuple[int, int]) -> bool:
        """Stage 164 — ПКМ по заполненному слоту синтеза: костюм возвращается
        в инвентарь (запрос пользователя).

        Stage 166 — ПКМ по слоту РЕЗУЛЬТАТА забирает результат в инвентарь.
        pos — ДИЗАЙН-координаты события (слоты в event-контексте дизайн-ные,
        см. _handle_synth_click). Возвращает True, если клик проглочен
        (попал в слот — даже пустой), False — пусть обрабатывает инвентарь.
        """
        main_r, cat1_r, cat2_r, res_r = self._synth_slot_rects()
        if res_r.collidepoint(pos):
            self._synth_collect_result()
            return True
        for rect, attr in zip((main_r, cat1_r, cat2_r), self._SYNTH_SLOT_ATTRS):
            if rect.collidepoint(pos):
                item_id = getattr(self, attr, None)
                if item_id is not None and self.player is not None \
                        and self.player.inv_add(item_id):
                    setattr(self, attr, None)
                    self._save_player()
                return True
        return False

    def _handle_synth_click(self, pos: tuple[int, int]) -> None:
        """Клик при открытой модалке синтеза: слоты-клики, остальное — мимо.

        pos — ДИЗАЙН-координаты события; слоты в event-контексте тоже
        дизайн-координатные (`_render_scale == 1.0` вне рендера) — Stage 163:
        прежняя конвертация ×UI_SCALE ломала хиттест на 2К.
        Stage 162 — клик ВНЕ окна больше НЕ закрывает его (drag костюмов
        из инвентаря); закрытие — крестик/Escape. _synth_pick_item сам
        проверяет попадание в слоты и мимо них ничего не делает.
        """
        self._synth_pick_item(pos)


class WardrobeRendererMixin:
    """Модалка гардероба (ПРАВИЛО 9: флаг _wardrobe_modal_open)."""

    def _wardrobe_window_pos(self) -> tuple[int, int]:
        """Stage 157 — позиция окна гардероба (общий реестр, persist)."""
        return self._window_pos(WARDROBE_WINDOW_KEY, SYNTHWARD_MODAL_W, SYNTHWARD_MODAL_H)

    def _open_wardrobe_modal(self) -> None:
        self._wardrobe_modal_open = True
        # Stage 167 — пагинация: окно открывается на 1-й странице.
        self._wardrobe_current_page = 1

    def _close_wardrobe_modal(self) -> None:
        self._wardrobe_modal_open = False

    def _wardrobe_modal_rect(self) -> pygame.Rect:
        x, y = self._wardrobe_window_pos()
        # Stage 156 — ЕДИНЫЙ размер с окном синтеза.
        return pygame.Rect(x, y, SYNTHWARD_MODAL_W, SYNTHWARD_MODAL_H)

    def _wardrobe_slot_rects(self) -> list[pygame.Rect]:
        panel = self._wardrobe_modal_rect()
        out = []
        slot_sz = 64
        # Stage 164 — подсказка над слотами удалена: ряд начинается выше
        # (раньше y+70, резервируя строку подсказки).
        y = panel.y + 56
        for i in range(WARDROBE_SLOTS_PER_PAGE):
            out.append(pygame.Rect(self._su(panel.x + 24),
                                    self._su(y + i * (slot_sz + 14)),
                                    self._su(slot_sz), self._su(slot_sz)))
        return out

    def _render_wardrobe_modal(self) -> None:
        su = self._su
        panel = self._wardrobe_modal_rect()
        # Stage 162 — фон НЕ затемняется (см. _render_synth_modal).
        panel_r = pygame.Rect(su(panel.x), su(panel.y), su(panel.w), su(panel.h))
        pygame.draw.rect(self.screen, (24, 24, 27), panel_r, border_radius=12)
        pygame.draw.rect(self.screen, (167, 139, 250),
                        (panel_r.x, panel_r.y, panel_r.w, su(4)), border_radius=2)
        # Stage 157/158 — общая шапка (drag + persist) + выносной крестик.
        self._render_window_titlebar(
            WARDROBE_WINDOW_KEY, panel_r, "Гардероб",
            (167, 139, 250), self._wardrobe_modal_open,
            open_attr="_wardrobe_modal_open",
            on_close=self._close_wardrobe_modal,
        )
        # Stage 164 — текст-подсказка над слотами УДАЛЕН (запрос
        # пользователя); слоты подняты на её место.

        slot_rects = self._wardrobe_slot_rects()
        self._wardrobe_layout = slot_rects
        # Stage 167 — пагинация: страница клампится в 1..WARDROBE_PAGES.
        w_page = getattr(self, "_wardrobe_current_page", 1)
        if not (1 <= w_page <= WARDROBE_PAGES):
            w_page = self._wardrobe_current_page = 1
        page_base = (w_page - 1) * WARDROBE_SLOTS_PER_PAGE
        for i, rect in enumerate(slot_rects):
            w_idx = page_base + i
            item_id = (self.player.wardrobe[w_idx]
                       if w_idx < len(self.player.wardrobe) else None)
            is_drag_target = rect.collidepoint(self._mouse_pos) and self._drag_item_id is not None
            hov = rect.collidepoint(self._mouse_pos)
            bg = (234, 179, 8) if is_drag_target else ((55, 55, 60) if hov else (39, 39, 42))
            pygame.draw.rect(self.screen, bg, rect, border_radius=6)
            pygame.draw.rect(self.screen, (167, 139, 250) if (hov or is_drag_target) else (82, 82, 91),
                            rect, 2 if (hov or is_drag_target) else 1, border_radius=6)
            num = self._su_font(11).render(str(i + 1), True, (150, 150, 158))
            # Stage 164 — нумерация СЛЕВА от слота (была сверху по центру).
            self.screen.blit(num, num.get_rect(midright=(rect.x - su(8), rect.centery)))
            name_x = rect.right + su(16)
            if item_id:
                gear = self.player.get_item_definition(item_id)
                if gear:
                    self._blit_gear_icon(gear, rect)
                    plus = self.player._outfit_plus_of(item_id, self.player)
                    name = gear.get("name", "?")
                    if plus > 0:
                        name = f"{name} +{plus}"
                    n_surf = self._su_font(14).render(name, True, (220, 220, 225))
                    # Stage 156 — длинные имена обрезаются с «…» до зоны кнопки.
                    max_name_w = su(240) - su(16)
                    if n_surf.get_width() > max_name_w:
                        while n_surf.get_width() > max_name_w - su(14) and len(name) > 3:
                            name = name[:-1]
                            n_surf = self._su_font(14).render(name + "…", True, (220, 220, 225))
                    self.screen.blit(n_surf, (name_x, rect.y + su(4)))
                    from pockie_rpg.config import outfit_synth_stat_multiplier
                    mult = outfit_synth_stat_multiplier(plus)
                    bs = gear.get("base_stats", {})
                    stats_line = "Сила +{:.0f} · Ловк +{:.0f} · Вын +{:.0f}".format(
                        bs.get("strength", 0) * mult,
                        bs.get("agility", 0) * mult,
                        bs.get("stamina", 0) * mult,
                    )
                    st_surf = self._su_font(12).render(stats_line, True, (150, 150, 158))
                    self.screen.blit(st_surf, (name_x, rect.y + su(26)))
                    # Кнопка «Вынуть» — Stage 164: ВЫРОВНЕНА по ПРАВОМУ краю
                    # окна (раньше x зависела от зоны имени — кнопка «висела»).
                    take_rect = pygame.Rect(panel_r.right - su(24) - su(80),
                                             rect.y + su(8), su(80), su(26))
                    th = take_rect.collidepoint(self._mouse_pos)
                    t_bg = (60, 50, 10) if th else (40, 40, 45)
                    pygame.draw.rect(self.screen, t_bg, take_rect, border_radius=6)
                    pygame.draw.rect(self.screen, (167, 139, 250) if th else (82, 82, 91),
                                    take_rect, 1, border_radius=6)
                    t_lbl = self._su_font(14).render("Вынуть", True,
                                                     (255, 255, 255) if th else (200, 200, 205))
                    self.screen.blit(t_lbl, t_lbl.get_rect(center=take_rect.center))
                    slot_ref = w_idx
                    self._click_rects.append(ClickRect(
                        tag=f"wardrobe_take_{w_idx}",
                        rect=take_rect,
                        on_click=lambda s=slot_ref: self._wardrobe_take_slot(s),
                    ))
        # Stage 167 — ПАГИНАЦИЯ снизу окна: 5 плашек-страниц (как вкладки
        # инвентаря), по центру. Клик переключает страницу слотов.
        pg_w, pg_h, pg_gap = 30, 24, 6
        row_w = su(WARDROBE_PAGES * pg_w + (WARDROBE_PAGES - 1) * pg_gap)
        pg_x0 = panel_r.centerx - row_w // 2
        pg_y = panel_r.bottom - su(40)
        self._wardrobe_page_rects: dict[int, pygame.Rect] = {}
        for p in range(1, WARDROBE_PAGES + 1):
            p_rect = pygame.Rect(pg_x0 + (p - 1) * su(pg_w + pg_gap), pg_y,
                                 su(pg_w), su(pg_h))
            self._wardrobe_page_rects[p] = p_rect
            is_active = (p == w_page)
            p_hover = p_rect.collidepoint(self._mouse_pos)
            if is_active:
                pbg, pborder, pfg, pfw = (60, 50, 10), (167, 139, 250), (167, 139, 250), 2
            elif p_hover:
                pbg, pborder, pfg, pfw = (50, 44, 16), (167, 139, 250), (220, 210, 255), 1
            else:
                pbg, pborder, pfg, pfw = (40, 40, 45), (82, 82, 91), (180, 180, 185), 1
            pygame.draw.rect(self.screen, pbg, p_rect, border_radius=5)
            pygame.draw.rect(self.screen, pborder, p_rect, su(pfw), border_radius=5)
            p_lbl = self._su_font(13, bold=True).render(str(p), True, pfg)
            self.screen.blit(p_lbl, p_lbl.get_rect(center=p_rect.center))
            _p = p
            self._click_rects.append(ClickRect(
                tag=f"wardrobe_page_{p}",
                rect=p_rect,
                on_click=lambda x=_p: setattr(self, "_wardrobe_current_page", x),
            ))
        # Stage 158 — внутренний крестик УДАЛЁН (выносной рисует шапка).

    def _wardrobe_take_slot(self, i: int) -> None:
        item_id = self.player.wardrobe_take(i)
        if item_id is None:
            return
        self._save_player()

    # Stage 162 — _handle_wardrobe_click удалён: закрытие по клику вне окна
    # убрано (мешало drag костюмов из инвентаря); диспетчер кликов — в
    # pygame_ui._handle_click (крестики/кнопки «Вынуть» через ClickRect).
