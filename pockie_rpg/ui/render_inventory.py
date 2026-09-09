"""InventoryRendererMixin — inventory + equipment modal + drag-and-drop.

Extracted verbatim from render_map.py (Stage 89 refactor-96a). The methods
here are copies of the original implementations; PygameUI inherits from
this mixin so `self` is bound to the full UI instance.

Stage 151 — Hi-DPI: весь рендер пишется в ДИЗАЙН-координатах (1280×720),
а каждый Rect/draw/blit проходит через self._su() (= ×self._render_scale).
Legacy-фаза: _render_scale=1.0 → поведение идентично доСтадж-151.
Native-фаза (мигрированный инвентарь на 2К): _render_scale=UI_SCALE →
чёткий рендер без финального растяжения. Grid-геометрия (_inv_layout,
_inv_grid_params) хранится в НАТИВНЫХ координатах — drag-математика
(_finish_drag) согласована через self._inv_native_pos().
"""
from __future__ import annotations

import os

import pygame

from pockie_rpg.config import ASSETS_DIR, SCREEN_HEIGHT, SCREEN_WIDTH
from pockie_rpg.ui.animator import ClickRect

# Stage 163 — ЗАГЛУШКИ ПУСТЫХ СЛОТОВ экипировки: item_id-представитель
# каждого слота (стартовое снаряжение), чья иконка рисуется полупрозрачно
# (~35% альфы) на пустом слоте. Чисто визуальная подсказка «что сюда
# кладётся»: ничего не даёт, не кликается, не снимается. Костюм всегда
# надет (outfit не снимается), но заглушка на случай пустого слота — тоже.
GEAR_SLOT_PLACEHOLDER_IDS: dict[str, str] = {
    "weapon": "weapon_wooden",
    "head": "headband_ninja",
    "body": "vest_ninja",
    "hands": "gloves_leather",
    "belt": "belt_fabric",
    "boots": "boots_shinobi",
    "accessory": "ring_jade2",
    "accessory2": "amulet_clan",
    "outfit": "suit_ichigo",
}

# Прозрачность заглушки (0-255): силуэт должен ЕЛЕ читаться (Stage 165:
# пользователь — «ещё менее заметнее»). 90 было слишком ярко.
GEAR_SLOT_PLACEHOLDER_ALPHA: int = 52


class InventoryRendererMixin:
    """Renders the inventory + equipment modal and handles drag-and-drop.

    Stage 152 — хелперы `_su`/`_su_font` переехали в `ui/scaling.py`
    (`ScalableRendererMixin`, общий с кузницей и следующими экранами).
    """

    def _render_inventory_modal(self) -> None:
        """Render the inventory + equipment modal (Stage 36 — no dimming, no context menu).

        Stage 143 — 8 колонок; вкладки-страницы I/II/III (римские, плашки);
        слот костюма квадратный; подписи слотов отдельной строкой ПОД слотом
        (фикс наложений «ОРУЖИЕ»/«И»); «Слоты: N/8» удалён; кнопки правой
        панели в едином стиле-плашках: Создать/Гардероб/Продать/Сорт
        (+ суб-меню качества при «Продать»); авто-прод удалён.
        Stage 148 — ЛИПКИЙ layout (позиции предметов не сортируются сами);
        счётчики качества в суб-меню «Продать»; призрак drag по item_span.
        Stage 151 — Hi-DPI: все координаты через self._su() (дизайн → рендер).
        Stage 167 — 12 колонок (было 16): окно 624 → 491 (сетка 335 + панель
        кнопок 118 — кнопки СУЖЕНЫ на ~20% без потери качества: текст
        векторный, рендерится под фактический размер). Вкладки-страницы
        1..10 (римские заменили арабские — 10 табов шириной 30px).
        """
        from pockie_rpg.data.item_db import get_equipment

        # Stage 36 — no background dimming (user request).

        modal_w = 491   # Stage 167 — сетка 12×27 (335) + панель 118 (было 624: 447+147)
        modal_h = 541   # Stage 145 — сетка 8×27 (231)
        # Stage 157 — перетаскиваемое окно: позиция из общего реестра
        # (persist в сейве); по умолчанию — центр (кламп 64..664).
        modal_x, modal_y = self._window_pos("inventory", modal_w, modal_h)
        # Stage 161 — верхний кламп от сжатой панели (52 + 4).
        modal_y = max(56, min(modal_y, 664 - modal_h))
        # Stage 29 — save modal rect for click-outside-to-close hit-testing.
        # Stage 151 — хранится в НАТИВНЫХ координатах.
        self._inventory_modal_rect = pygame.Rect(
            self._su(modal_x), self._su(modal_y),
            self._su(modal_w), self._su(modal_h),
        )
        pygame.draw.rect(self.screen, (24, 24, 27),
                         (self._su(modal_x), self._su(modal_y),
                          self._su(modal_w), self._su(modal_h)), border_radius=12)
        # Stage 37 — removed full yellow border, keep only the top accent bar.
        pygame.draw.rect(self.screen, (234, 179, 8),
                         (self._su(modal_x), self._su(modal_y),
                          self._su(modal_w), self._su(4)), border_radius=2)
        # Stage 157/158 — общая шапка: регистрация окна + drag + persist +
        # ВЫНОСНОЙ крестик справа от окна (внутренний Х мешал).
        # Название не рисуем (в шапке звание-плашка ниже).
        self._render_window_titlebar(
            "inventory", self._inventory_modal_rect, "",
            (234, 179, 8), True, open_attr="_inventory_modal_open",
            on_close=self._close_inventory_modal,
        )

        # Stage 144 — текст «Инвентарь» УДАЛЁН из шапки; вместо него плашка
        # звания по центру шапки (была над спрайтом — теперь в шапке окна).
        active_title_id = getattr(self.player, "active_title", None)
        from pockie_rpg.data.titles_db import get_title
        if active_title_id:
            title_def = get_title(active_title_id)
            title_text = title_def["name"] if title_def else None
        else:
            title_text = None
        t_surf = self._su_font(18).render(
            f"[ {title_text} ]" if title_text else "[ Нет звания ]",
            True, (234, 179, 8) if title_text else (161, 161, 170),
        )
        tw = t_surf.get_width() + self._su(24)
        th = self._su(26)
        t_rect = pygame.Rect(self._su(modal_x) + (self._su(modal_w) - tw) // 2,
                             self._su(modal_y + 8), tw, th)
        t_hover = t_rect.collidepoint(self._mouse_pos)
        t_bg = (60, 50, 10) if (t_hover and title_text) else (40, 40, 45)
        pygame.draw.rect(self.screen, t_bg, t_rect, border_radius=6)
        pygame.draw.rect(self.screen, (234, 179, 8) if (t_hover and title_text) else (82, 82, 91),
                        t_rect, 1, border_radius=6)
        self.screen.blit(t_surf, t_surf.get_rect(center=t_rect.center))
        self._click_rects.append(ClickRect(
            tag="open_titles_modal", rect=t_rect, on_click=self._open_titles_modal,
        ))

        # Top section: character sprite + 7 gear slots around it.
        # Stage 143 — top_h 226→238: слоты с зазорами 10 (подписи ПОД слотами
        # отдельной строкой — фикс наложения «ОРУЖИЕ» на соседние слоты).
        top_h = 238
        top_rect = pygame.Rect(self._su(modal_x + 8), self._su(modal_y + 44),
                               self._su(modal_w - 16), self._su(top_h))
        # Stage 152 — вертикальная виньетка вместо плоского (31,31,34): градиент
        # собирается один раз в полосу 1×N и кэшируется по размеру rect.
        self._blit_panel_gradient(top_rect)
        pygame.draw.rect(self.screen, (63, 63, 70), top_rect, 1, border_radius=8)

        # Character sprite — centered, up to 2.0× scale.
        # Stage 152 — ПЕРФ: раньше image.load + smoothscale выполнялись КАЖДЫЙ
        # КАДР при открытом инвентаре (диск + ресемпл 60 раз/сек). Теперь два
        # кэша: сырая загрузка (`_char_pose_raw`, None = провал загрузки, больше
        # не пытаемся) и отмасштабированный результат по (w, h).
        char_cx = modal_x + modal_w // 2
        char_cy = modal_y + 44 + top_h // 2
        char_img = self._char_pose_surface(top_h - 40)
        if char_img is not None:
            self.screen.blit(char_img, (self._su(char_cx) - char_img.get_width() // 2,
                                        self._su(char_cy) - char_img.get_height() // 2))
        else:
            fallback = self._su_font(16).render("[Character]", True, (150, 150, 155))
            self.screen.blit(fallback, (self._su(char_cx) - fallback.get_width() // 2,
                                        self._su(char_cy)))

        # Stage 144 — плашка звания перенесена в ШАПКУ окна (старая над
        # спрайтом удалена).

        # 7 gear slots — weapon takes 2× vertical height (long weapon).
        # Stage 145 — ДВА мелких слота accessory (24px, вдвое уже стандартного)
        # под кольца/амулеты.
        # Stage 161 — НОВАЯ СХЕМА (макет пользователя, размеры слотов прежние):
        #   колонка 1: ОРУЖИЕ (2×) → ПОЯС → ОБУВЬ
        #   колонка 2 (справа от оружия): КОСТЮМ
        #   спрайт игрока — по центру
        #   правая колонка: КОЛЬЦО+АМУЛЕТ (пара 24px) → ГОЛОВА → ТЕЛО → РУКИ
        slot_size = 48
        weapon_h = slot_size * 2 + 6  # 2 slots tall + gap
        slot_y_gap = 8
        sprite_half = 62  # Stage 145 — отодвинуто от спрайта на ~13%
        slot_x_left = char_cx - sprite_half - (slot_size * 2 + 10)  # 2 колонки слева
        left_col2_x = slot_x_left + slot_size + 10
        slot_x_right = char_cx + sprite_half  # правая колонка вплотную к спрайту
        slot_y_start = modal_y + 60

        # Layout (Stage 161):
        #   col1 — weapon (2× высоты), под ним пояс и обувь;
        #   col2 — костюм (один, рядом с оружием);
        #   правая колонка — пара мелких слотов (кольцо|амулет) в верхнем ряду,
        #   ниже — голова, тело, руки с тем же шагом 56.
        gear_layout: dict[str, pygame.Rect] = {}
        gear_layout["weapon"] = pygame.Rect(self._su(slot_x_left), self._su(slot_y_start),
                                            self._su(slot_size), self._su(weapon_h))
        gear_layout["outfit"] = pygame.Rect(self._su(left_col2_x), self._su(slot_y_start),
                                            self._su(slot_size), self._su(slot_size))
        gear_layout["belt"] = pygame.Rect(
            self._su(slot_x_left), self._su(slot_y_start + weapon_h + slot_y_gap),
            self._su(slot_size), self._su(slot_size))
        gear_layout["boots"] = pygame.Rect(
            self._su(slot_x_left),
            self._su(slot_y_start + weapon_h + slot_y_gap + (slot_size + slot_y_gap)),
            self._su(slot_size), self._su(slot_size))
        # Пара accessory в ВЕРХНЕМ ряду правой колонки (кольцо слева, амулет справа).
        acc_size = 24
        acc_gap = 4
        acc_y = slot_y_start
        gear_layout["accessory"] = pygame.Rect(self._su(slot_x_right), self._su(acc_y),
                                               self._su(acc_size), self._su(acc_size))
        gear_layout["accessory2"] = pygame.Rect(
            self._su(slot_x_right + acc_size + acc_gap), self._su(acc_y),
            self._su(acc_size), self._su(acc_size)
        )
        right_slots = ["head", "body", "hands"]
        for i, sname in enumerate(right_slots):
            sy = slot_y_start + acc_size + slot_y_gap + i * (slot_size + slot_y_gap)
            gear_layout[sname] = pygame.Rect(self._su(slot_x_right), self._su(sy),
                                             self._su(slot_size), self._su(slot_size))

        # Store layout for drag-and-drop hit-testing.
        self._gear_layout = gear_layout

        hovered_gear_item_id: str | None = None
        drag_source_slot: str | None = (
            self._drag_source[1] if (self._drag_source and self._drag_source[0] == "gear") else None
        )
        drag_source_inv_idx: int | None = (
            self._drag_source[1] if (self._drag_source and self._drag_source[0] == "inv") else None
        )

        for slot_name, rect in gear_layout.items():
            is_hover = rect.collidepoint(self._mouse_pos)
            is_drop_target = is_hover and self._drag_item_id is not None
            is_drag_source = (slot_name == drag_source_slot)
            bg = (70, 70, 80) if is_drop_target else ((55, 55, 60) if is_hover else (39, 39, 42))
            pygame.draw.rect(self.screen, bg, rect, border_radius=4)
            border_color = (234, 179, 8) if (is_hover or is_drop_target) else (82, 82, 91)
            pygame.draw.rect(self.screen, border_color, rect,
                             self._su(2) if (is_hover or is_drop_target) else 1, border_radius=4)
            item_id = self.player.equipped_gear.get(slot_name)
            if item_id and not is_drag_source:
                # Stage 109 — use get_item_definition for generated weapons support.
                gear = self.player.get_item_definition(item_id) if hasattr(self, "player") else get_equipment(item_id)
                if gear:
                    self._blit_gear_icon(gear, rect)
                    # Stage 116 — enchant level per-item-id (not per-slot).
                    enchant_lvl = self.player.gear_enchants.get(item_id, 0) if hasattr(self.player, "gear_enchants") else 0
                    if enchant_lvl >= 20:
                        pygame.draw.rect(self.screen, (180, 80, 220), rect,
                                         self._su(3), border_radius=4)
                    elif enchant_lvl >= 10:
                        pygame.draw.rect(self.screen, (234, 179, 8), rect,
                                         self._su(2), border_radius=4)
                    # Stage 166 — ступень заточки костюма-инстанса: «+N»
                    # жёлтым снизу справа (как в слотах синтеза).
                    outfit_plus = self.player._outfit_plus_of(item_id, self.player)
                    if outfit_plus > 0:
                        op_surf = self._su_font(13).render(f"+{outfit_plus}", True, (234, 179, 8))
                        self.screen.blit(op_surf,
                                         (rect.right - op_surf.get_width() - self._su(2),
                                          rect.bottom - op_surf.get_height() - self._su(2)))
                if is_hover and self._drag_item_id is None:
                    hovered_gear_item_id = item_id
            elif not item_id:
                # Stage 163 — полупрозрачная иконка-заглушка вместо точки
                # и текстовых подписей: видно, ЧТО кладётся в пустой слот.
                self._blit_slot_placeholder(slot_name, rect)
            # Stage 163 — текстовые подписи слотов («ОРУЖИЕ», «ПОЯС», …)
            # УДАЛЕНЫ по запросу пользователя: назначение слота показывает
            # иконка-заглушка (на пустых) / сам предмет (на заполненных).

        # Stage 143 — «Слоты: N/8» УДАЛЁН по требованию.

        # Bottom section: inventory grid — weapon items span 2 vertical cells.
        # Stage 144 — inv_rect: сетка + панель 132 у правого края окна.
        inv_y = modal_y + 44 + top_h + 24
        inv_h = 231  # Stage 145 — 8 мини-рядов 27px + паддинги
        inv_rect_d = pygame.Rect(modal_x + 8, inv_y, modal_w - 16, inv_h)
        # Stage 151 — нативный rect (для геометрии сетки и хиттестов).
        inv_rect = pygame.Rect(self._su(inv_rect_d.x), self._su(inv_rect_d.y),
                               self._su(inv_rect_d.w), self._su(inv_rect_d.h))
        pygame.draw.rect(self.screen, (31, 31, 34), inv_rect, border_radius=8)
        pygame.draw.rect(self.screen, (63, 63, 70), inv_rect, 1, border_radius=8)

        # Строка заголовка над сеткой: слева «Предметы (N)», справа вкладки.
        # Stage 143 — фикс наложения: отдельная полоса высотой 22, ничего не
        # рисуется поверх соседних элементов.
        header_y = inv_y - 22
        inv_label = self._su_font(13).render(
            f"Предметы ({self.player.inv_count()})", True, (161, 161, 170)
        )
        self.screen.blit(inv_label, (self._su(modal_x + 16), self._su(header_y + 5)))

        # Stage 64 — INVENTORY PAGINATION.
        if not hasattr(self, "_inv_current_page"):
            self._inv_current_page = 1
        from pockie_rpg.config import INVENTORY_PAGE_KEYS
        if self._inv_current_page not in INVENTORY_PAGE_KEYS:
            self._inv_current_page = 1

        # Stage 144 — вкладки-страницы (Stage 167 — 10 страниц, арабские
        # цифры: 10 табов 30px влезают в строку заголовка; римские VIII/IX
        # не влезали бы), единый стиль плашек; прижаты к правому краю.
        n_pages = len(INVENTORY_PAGE_KEYS)
        tab_w = 30
        tab_h = 20
        tab_gap = 4
        tab_x0 = inv_rect_d.right - (n_pages * tab_w + (n_pages - 1) * tab_gap)
        self._inv_tab_rects: dict[int, pygame.Rect] = {}
        for p in INVENTORY_PAGE_KEYS:
            tx = tab_x0 + (p - 1) * (tab_w + tab_gap)
            t_rect = pygame.Rect(self._su(tx), self._su(header_y),
                                 self._su(tab_w), self._su(tab_h))
            self._inv_tab_rects[p] = t_rect
            is_active = (self._inv_current_page == p)
            t_hover = t_rect.collidepoint(self._mouse_pos)
            is_drop_target = t_hover and self._drag_item_id is not None and not is_active
            if is_active:
                bg = (60, 50, 10)
                border = (234, 179, 8)
                fg = (234, 179, 8)
                border_w = 2
            elif t_hover or is_drop_target:
                bg = (50, 44, 16)
                border = (234, 179, 8)
                fg = (255, 235, 150)
                border_w = 1
            else:
                bg = (40, 40, 45)
                border = (82, 82, 91)
                fg = (180, 180, 185)
                border_w = 1
            pygame.draw.rect(self.screen, bg, t_rect, border_radius=5)
            pygame.draw.rect(self.screen, border, t_rect,
                             self._su(border_w), border_radius=5)
            t_lbl = self._su_font(13, bold=True).render(str(p), True, fg)
            self.screen.blit(t_lbl, t_lbl.get_rect(center=t_rect.center))
            _p = p
            self._click_rects.append(ClickRect(
                tag=f"inv_page_{p}",
                rect=t_rect,
                on_click=lambda x=_p: self._set_inv_page(x),
            ))

        # Stage 64 — read the current page's slot list (live reference).
        page_slots = self.player.inv_page_slots(self._inv_current_page)
        # Build (slot_idx, item_id) pairs for non-empty slots, preserving order.
        # Stage 183 — стак-слоты (dict) распаковываются через slot_item_id.
        page_items = [
            (i, self.player.slot_item_id(iid))
            for i, iid in enumerate(page_slots)
            if iid is not None
        ]

        # Stage 37 — inventory grid starts at the very top of the inv_rect.
        # Stage 68 — uses INV_COLS / INV_MAX_ROWS from config (single source).
        # Stage 141 — INV_CELL 57 (иконки 51×51 ровно 1:1) + INV_GAP 2 из config.
        # Stage 151 — ГЕОМЕТРИЯ СЕТКИ в НАТИВНЫХ координатах (ячейка/зазор
        # через _su) — layout-rect'ы, drag-зона и _finish_drag согласованы.
        from pockie_rpg.config import INV_CELL, INV_COLS, INV_GAP, INV_MAX_ROWS
        inv_grid_x = self._su(inv_rect_d.x + 8)
        inv_grid_y = self._su(inv_rect_d.y + 4)
        inv_cols = INV_COLS
        inv_gap = self._su(INV_GAP)
        inv_cell = self._su(INV_CELL)
        inv_max_rows = INV_MAX_ROWS

        # Stage 28/145 — layout: МИНИ-СЛОТЫ 16×8; спаны предметов:
        # оружие 2×3, броня 2×2, кольца/амулеты/расходники 1×1 (item_span).
        # Stage 148 — STICKY-LAYOUT: «прилипающие» позиции.
        # Stage 164 — якорная память — СПИСОК позиций на item_id (раньше —
        # одна позиция на id). ДУБЛИКАТЫ (6× suit_ichigo из стартового
        # набора) делили один якорь: любой drag перезаписывал его, и ВСЕ
        # копии пересортировывались (жалоба пользователя). Теперь каждая
        # копия держит свою позицию: drag обновляет позицию ТОЛЬКО
        # перетащенного экземпляра (по его текущей клетке layout'а),
        # чужие не двигаются. «Сорт» — по-прежнему единственный
        # авто-перепаковщик (чистит память целиком).
        from pockie_rpg.config import item_span
        if not hasattr(self, "_inv_item_anchor_memory"):
            self._inv_item_anchor_memory: dict[str, list[tuple[int, int]]] = {}
        anchor_memory = self._inv_item_anchor_memory

        occupied: set[tuple[int, int]] = set()
        inv_layout: list[tuple[int, pygame.Rect, tuple[int, int]]] = []  # (slot_idx, rect, span(w,h))

        def _try_place(slot_idx: int, item_id: str, force_col: int | None = None,
                       force_row: int | None = None, remember: bool = False) -> bool:
            gear = self.player.get_item_definition(item_id) if hasattr(self, "player") else get_equipment(item_id)
            span = item_span(gear) if gear else (1, 1)
            span_w, span_h = span
            if force_col is not None and force_row is not None:
                if (force_col + span_w <= inv_cols and force_row + span_h <= inv_max_rows
                        and all((force_col + dx, force_row + dy) not in occupied
                                for dx in range(span_w) for dy in range(span_h))):
                    sx = inv_grid_x + force_col * (inv_cell + inv_gap)
                    sy = inv_grid_y + force_row * (inv_cell + inv_gap)
                    cell_w = inv_cell * span_w + inv_gap * (span_w - 1)
                    cell_h = inv_cell * span_h + inv_gap * (span_h - 1)
                    inv_layout.append((slot_idx, pygame.Rect(sx, sy, cell_w, cell_h), span))
                    for dx in range(span_w):
                        for dy in range(span_h):
                            occupied.add((force_col + dx, force_row + dy))
                    return True
                return False
            for row in range(inv_max_rows - span_h + 1):
                for col in range(inv_cols - span_w + 1):
                    if all((col + dx, row + dy) not in occupied
                           for dx in range(span_w) for dy in range(span_h)):
                        sx = inv_grid_x + col * (inv_cell + inv_gap)
                        sy = inv_grid_y + row * (inv_cell + inv_gap)
                        cell_w = inv_cell * span_w + inv_gap * (span_w - 1)
                        cell_h = inv_cell * span_h + inv_gap * (span_h - 1)
                        inv_layout.append((slot_idx, pygame.Rect(sx, sy, cell_w, cell_h), span))
                        for dx in range(span_w):
                            for dy in range(span_h):
                                occupied.add((col + dx, row + dy))
                        if remember:
                            # Stage 164 — список позиций: КАЖДАЯ копия (в т.ч.
                            # дубликаты) запоминает свою клетку.
                            self._inv_anchor_add(item_id, (col, row))
                        return True
            return False

        # 1) Предметы с якорями из ПАМЯТИ ПО item_id — на свои прежние
        #    визуальные позиции. Stage 164 — якорей может быть несколько
        #    (дубликаты): берём первую свободную позицию из списка.
        for slot_idx, item_id in page_items:
            for anchor in anchor_memory.get(item_id, ()):
                if _try_place(slot_idx, item_id, anchor[0], anchor[1]):
                    break
        # 2) Остальные — авто (первый подходящий угол); Stage 148 — позиция
        #    сразу ФИКСИРУЕТСЯ (липкий layout: на след. кадре не сдвинется).
        for slot_idx, item_id in page_items:
            if any(entry[0] == slot_idx for entry in inv_layout):
                continue
            _try_place(slot_idx, item_id, remember=True)

        # Store inventory layout for drag hit-testing.
        self._inv_layout = inv_layout
        self._inv_grid_rect = inv_rect
        self._inv_grid_params = (inv_grid_x, inv_grid_y, inv_cols, inv_gap, inv_cell, inv_max_rows)

        # Stage 146/147 — DRAG-ЗОНА СПАНА: якорная мини-ячейка под курсором +
        # зона спана предмета. Свободна → ЗОЛОТО (можно бросить); занята
        # другим предметом → КРАСНАЯ РАМКА (нельзя). Если якорь попал на
        # предмет-ЦЕЛЬ (чужой предмет) → цель подсвечивается РАМКОЙ для свапа.
        drag_span_cells: set[tuple[int, int]] = set()
        drag_zone_blocked = False
        drag_swap_target_idx: int | None = None
        if self._drag_item_id is not None:
            drag_item = self.player.get_item_definition(self._drag_item_id)
            d_span_w, d_span_h = item_span(drag_item) if drag_item else (1, 1)
            mx_rel = self._mouse_pos[0] - inv_grid_x
            my_rel = self._mouse_pos[1] - inv_grid_y
            anchor_col = int(mx_rel // (inv_cell + inv_gap))
            anchor_row = int(my_rel // (inv_cell + inv_gap))
            if 0 <= anchor_col < inv_cols and 0 <= anchor_row < inv_max_rows:
                cells = [
                    (anchor_col + dx, anchor_row + dy)
                    for dx in range(d_span_w) for dy in range(d_span_h)
                    if anchor_col + dx < inv_cols and anchor_row + dy < inv_max_rows
                ]
                # Чужие предметы в зоне? Якорь (клетка под курсором) на чужом
                # предмете → СВАП с ним; якорь на пустой клетке, но спан цепляет
                # чужие → КРАСНАЯ зона (место занято).
                foreign = set()
                anchor_owner: int | None = None
                for s_idx, s_rect, s_span in inv_layout:
                    if s_idx == drag_source_inv_idx:
                        continue
                    sc = (s_rect.x - inv_grid_x) // (inv_cell + inv_gap)
                    sr = (s_rect.y - inv_grid_y) // (inv_cell + inv_gap)
                    for dx in range(s_span[0]):
                        for dy in range(s_span[1]):
                            if (sc + dx, sr + dy) in cells:
                                foreign.add(s_idx)
                            if (sc + dx, sr + dy) == (anchor_col, anchor_row):
                                anchor_owner = s_idx
                if anchor_owner is not None:
                    # Stage 148 — свап ТОЛЬКО при РАВНЫХ спанах: предмет-цель
                    # встаёт на старое место источника и должен туда влезть
                    # (кольцо 1×1 ↔ броня 2×2 = красная зона, иначе цель
                    # улетала бы в авто-упаковку = «сортировка»).
                    f_entry = next(e for e in inv_layout if e[0] == anchor_owner)
                    if f_entry[2] == (d_span_w, d_span_h):
                        drag_swap_target_idx = anchor_owner
                    else:
                        drag_zone_blocked = True
                        drag_span_cells = set(cells)
                elif foreign:
                    drag_zone_blocked = True
                    drag_span_cells = set(cells)
                else:
                    drag_span_cells = set(cells)

        # Draw empty cells first (background grid), then items on top.
        # Stage 146/147 — золото = можно бросить; красная рамка = занято.
        for row in range(inv_max_rows):
            for col in range(inv_cols):
                if (col, row) in occupied:
                    continue
                sx = inv_grid_x + col * (inv_cell + inv_gap)
                sy = inv_grid_y + row * (inv_cell + inv_gap)
                srect = pygame.Rect(sx, sy, inv_cell, inv_cell)
                in_drag_zone = (col, row) in drag_span_cells
                if in_drag_zone:
                    if drag_zone_blocked:
                        bg = (60, 26, 26)  # тёмно-красный — место занято.
                        border = (220, 60, 60)
                    else:
                        bg = (234, 179, 8)  # золотом — можно бросить.
                        border = (255, 220, 80)
                    pygame.draw.rect(self.screen, bg, srect, border_radius=4)
                    pygame.draw.rect(self.screen, border, srect, 1, border_radius=4)
                    continue
                pygame.draw.rect(self.screen, (31, 31, 34), srect, border_radius=4)
                pygame.draw.rect(self.screen, (50, 50, 55), srect, 1, border_radius=4)

        # Draw items.
        # Stage 64 — read item_id from the live page_slots so any drag mutation
        # is reflected immediately on the next render.
        # Stage 146 — предмет-источник не рисуется; Stage 147 — предмет-ЦЕЛЬ
        # свапа подсвечивается СИНЕЙ РАМКОЙ (якорь drag на нём, спаны равны).
        for slot_idx, rect, span in inv_layout:
            entry = page_slots[slot_idx]
            if entry is None:
                continue  # defensive: was removed between layout + draw.
            item_id = self.player.slot_item_id(entry)
            if item_id is None:
                continue  # defensive: malformed stack slot.
            is_drag_source = (slot_idx == drag_source_inv_idx)
            is_hover = rect.collidepoint(self._mouse_pos)
            if is_drag_source:
                continue  # источник «в руке» — не рисуем на месте.
            is_swap_target = (slot_idx == drag_swap_target_idx)
            if is_hover and not is_swap_target:
                bg = (55, 55, 60)
            else:
                bg = (45, 45, 50)
            pygame.draw.rect(self.screen, bg, rect, border_radius=4)
            if is_swap_target:
                border_color = (96, 165, 250)  # синяя рамка — цель свапа.
                border_w = 3
            elif is_hover:
                border_color = (234, 179, 8)
                border_w = 2
            else:
                border_color = (82, 82, 91)
                border_w = 1
            pygame.draw.rect(self.screen, border_color, rect,
                             self._su(border_w), border_radius=4)
            # Stage 109 — use get_item_definition for generated weapons support.
            gear = self.player.get_item_definition(item_id) if hasattr(self, "player") else get_equipment(item_id)
            if gear:
                self._blit_gear_icon(gear, rect)
            else:
                placeholder = self._su_font(18, bold=True).render("?", True, (113, 113, 122))
                pr = placeholder.get_rect(center=rect.center)
                self.screen.blit(placeholder, pr.topleft)
            # Stage 166 — ступень заточки костюма-инстанса в сетке инвентаря:
            # «+N» жёлтым СНИЗУ СПРАВА (как в слотах синтеза — запрос).
            inv_plus = self.player._outfit_plus_of(item_id, self.player)
            if inv_plus > 0:
                ip_surf = self._su_font(13).render(f"+{inv_plus}", True, (234, 179, 8))
                self.screen.blit(ip_surf,
                                 (rect.right - ip_surf.get_width() - self._su(3),
                                  rect.bottom - ip_surf.get_height() - self._su(3)))
            # Stage 183 — счётчик СТАКА расходников снизу справа (тёмная
            # подложка + белая цифра; рисуется при count > 1).
            stack_n = self.player.slot_count(entry)
            if stack_n > 1:
                # Stage 184 — цифра стака: тёмная подложка убрана (запрос),
                # шрифт уменьшен 11 → 9; лёгкая чёрная обводка для читаемости
                # на светлой иконке.
                cnt_text = self._su_font(9, bold=True).render(
                    str(stack_n), True, (255, 255, 255),
                )
                cnt_x = rect.right - cnt_text.get_width() - self._su(3)
                cnt_y = rect.bottom - cnt_text.get_height() - self._su(2)
                outline = self._su_font(9, bold=True).render(
                    str(stack_n), True, (0, 0, 0),
                )
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    self.screen.blit(
                        outline, (cnt_x + self._su(dx), cnt_y + self._su(dy)),
                    )
                self.screen.blit(cnt_text, (cnt_x, cnt_y))
            if is_hover and self._drag_item_id is None:
                hovered_gear_item_id = item_id

        # Stage 29 — close button removed; click outside the modal closes it.
        # Stage 30 — small red "X" close button in the top-right corner.
        # Stage 158 — внутренний крестик УДАЛЁН: выносной рисует шапка
        # (self._render_window_titlebar on_close) — не перехватывает клики
        # контента и drag-зоны.

        # Stage 144 — ПРАВАЯ ПАНЕЛЬ: прижата к ПРАВОМУ КРАЮ окна инвентаря.
        # Порядок: Создать / Гардероб / Продать (+суб-меню качества) / Сорт.
        # Stage 167 — кнопки сужены до 118 (−20% от 147; окно 491 подобрано
        # ровно под это: btn_w = modal_w − 373), текст не сжат — качество 1:1.
        grid_w = INV_COLS * (INV_CELL + INV_GAP) - INV_GAP
        btn_panel_x = inv_rect_d.x + 8 + grid_w + 6
        btn_w = inv_rect_d.right - 8 - btn_panel_x
        btn_h = 30
        btn_gap_y = 8
        panel_y0 = inv_rect_d.y + 4

        def _plate(rect, label, on_click, tag, accent=(234, 179, 8)):
            """Stage 143 — единая плашка-кнопка: zinc фон, hover золотая рамка."""
            hover = rect.collidepoint(self._mouse_pos)
            bg = (60, 50, 10) if hover else (40, 40, 45)
            pygame.draw.rect(self.screen, bg, rect, border_radius=6)
            pygame.draw.rect(self.screen, accent if hover else (82, 82, 91),
                            rect, self._su(2) if hover else 1, border_radius=6)
            lbl = self._su_font(18, bold=True).render(
                label, True, (255, 255, 255) if hover else (220, 220, 225))
            self.screen.blit(lbl, lbl.get_rect(center=rect.center))
            self._click_rects.append(ClickRect(tag=tag, rect=rect, on_click=on_click))
            return hover

        def _su_rect(x, y, w, h) -> pygame.Rect:
            return pygame.Rect(self._su(x), self._su(y), self._su(w), self._su(h))

        _plate(
            _su_rect(btn_panel_x, panel_y0, btn_w, btn_h),
            "Создать", self._open_synth_modal, "open_synth_modal",
        )
        _plate(
            _su_rect(btn_panel_x, panel_y0 + (btn_h + btn_gap_y), btn_w, btn_h),
            "Гардероб", self._open_wardrobe_modal, "open_wardrobe_modal",
            accent=(167, 139, 250),
        )
        sell_btn_rect = _su_rect(
            btn_panel_x, panel_y0 + (btn_h + btn_gap_y) * 2, btn_w, btn_h
        )
        sell_open = getattr(self, "_inv_sell_menu_open", False)
        sell_hover = sell_btn_rect.collidepoint(self._mouse_pos)
        sbg = (60, 50, 10) if (sell_hover or sell_open) else (40, 40, 45)
        pygame.draw.rect(self.screen, sbg, sell_btn_rect, border_radius=6)
        pygame.draw.rect(self.screen, (220, 60, 60) if (sell_hover or sell_open) else (82, 82, 91),
                        sell_btn_rect, self._su(2) if (sell_hover or sell_open) else 1, border_radius=6)
        s_lbl = self._su_font(18, bold=True).render(
            "Продать", True,
            (255, 255, 255) if (sell_hover or sell_open) else (220, 220, 225))
        self.screen.blit(s_lbl, s_lbl.get_rect(center=sell_btn_rect.center))
        self._click_rects.append(ClickRect(
            tag="inv_sell_menu", rect=sell_btn_rect,
            on_click=self._toggle_sell_menu,
        ))

        # Суб-меню качества — Stage 145: ВСПЛЫВАЕТ СПРАВА ОТ ОКНА (за краем),
        # а не вниз внутри панели (кнопка «Сорт» больше не уезжает).
        # Stage 148 — СЧЁТЧИКИ КАЧЕСТВА: у каждой плашки «N× Имя» — сколько
        # продаваемых предметов этого качества сейчас в инвентаре (по всем
        # страницам; sell_price>0 — стартовые с ценой 0 не считаются).
        if sell_open:
            from pockie_rpg.config import RARITY_RGB
            rarity_names_ru = {
                "Grey": "Серые", "Blue": "Синие", "Purple": "Фиолетовые",
                "Gold": "Золотые", "Red": "Красные",
            }
            from pockie_rpg.config import INVENTORY_PAGE_KEYS
            from pockie_rpg.data.item_db import get_sell_price
            rarity_counts: dict[str, int] = {rar: 0 for rar in rarity_names_ru}
            for _pg in INVENTORY_PAGE_KEYS:
                for _iid in self.player.inv_page_slots(_pg):
                    if _iid is None:
                        continue
                    # Stage 183 — распаковка стака.
                    _sid = self.player.slot_item_id(_iid)
                    if _sid is None:
                        continue
                    _it = self.player.get_item_definition(_sid)
                    if _it is None:
                        continue
                    _rar = _it.get("rarity", "")
                    if _rar not in rarity_counts:
                        continue
                    _pr = _it.get("sell_price", 0)
                    if _pr <= 0:
                        _pr = get_sell_price(_sid)
                    if _pr > 0:
                        rarity_counts[_rar] += 1
            # Позиция: правее правого края окна, выровнено по кнопке «Продать».
            menu_x = modal_x + modal_w + 6
            menu_w = 150
            # Кламп: если справа нет места — влево от окна.
            if menu_x + menu_w > SCREEN_WIDTH:
                menu_x = modal_x - menu_w - 6
            menu_y = panel_y0 + (btn_h + btn_gap_y) * 2
            menu_h = 5 * 24 + 8
            # Подложка-плашка меню (тень + фон).
            shadow = pygame.Surface((self._su(menu_w + 4), self._su(menu_h + 4)), pygame.SRCALPHA)
            shadow.fill((0, 0, 0, 130))
            self.screen.blit(shadow, (self._su(menu_x - 2), self._su(menu_y - 2)))
            pygame.draw.rect(self.screen, (24, 24, 27),
                             _su_rect(menu_x, menu_y, menu_w, menu_h), border_radius=8)
            pygame.draw.rect(self.screen, (82, 82, 91),
                             _su_rect(menu_x, menu_y, menu_w, menu_h), 1, border_radius=8)
            for i, rar in enumerate(("Grey", "Blue", "Purple", "Gold", "Red")):
                sub_rect = _su_rect(menu_x + 6, menu_y + 4 + i * 24, menu_w - 12, 22)
                sub_hover = sub_rect.collidepoint(self._mouse_pos)
                rbg = (50, 36, 30) if sub_hover else (34, 30, 28)
                pygame.draw.rect(self.screen, rbg, sub_rect, border_radius=4)
                pygame.draw.rect(self.screen, RARITY_RGB[rar], sub_rect, 1, border_radius=4)
                cnt = rarity_counts[rar]
                r_lbl = self._su_font(13).render(rarity_names_ru[rar], True, RARITY_RGB[rar])
                c_lbl = self._su_font(13).render(f"{cnt}", True,
                                               (255, 255, 255) if cnt else (113, 113, 122))
                # Имя слева, счётчик в правой части плашки (кликабельная зона вся).
                self.screen.blit(r_lbl, (sub_rect.x + self._su(6), r_lbl.get_rect(
                    centery=sub_rect.centery).y))
                self.screen.blit(c_lbl, c_lbl.get_rect(
                    right=sub_rect.right - self._su(8), centery=sub_rect.centery))
                _r = rar
                self._click_rects.append(ClickRect(
                    tag=f"inv_sell_rarity_{rar}",
                    rect=sub_rect,
                    on_click=lambda r=_r: self._sell_all_rarity(r),
                ))

        _plate(
            _su_rect(btn_panel_x, panel_y0 + (btn_h + btn_gap_y) * 3, btn_w, btn_h),
            "Сорт", self._sort_inventory, "inv_sort",
        )

        # Stage 142 — gem-секция УДАЛЕНА по требованию (самоцветы видны
        # в кузнице: вкладка гема + сокеты гира; инвентарь компактнее).

        # Tooltip (only when not dragging).
        if hovered_gear_item_id is not None and self._drag_item_id is None:
            self._render_gear_tooltip(hovered_gear_item_id, modal_x + modal_w)

        # Stage 164 — призрак drag'а рисуется ПОСЛЕДНИМ общим overlay
        # (pygame_ui._render_drag_ghost_topmost): он должен быть ПОВЕРХ
        # синтеза/гардероба и любых других окон (раньше прятался за ними).

        # Stage 147 — РАМКА ЦЕЛИ-СВАПА поверх ВСЕХ слоёв (включая drag-иконку):
        # синий контур + маркер сверху — игрок видит, куда встанет свап.
        if drag_swap_target_idx is not None:
            swap_rect = next(
                (r for i, r, _ in inv_layout if i == drag_swap_target_idx), None
            )
            if swap_rect is not None:
                pygame.draw.rect(self.screen, (96, 165, 250), swap_rect,
                                 self._su(3), border_radius=4)
                marker = pygame.Surface((swap_rect.w, self._su(6)), pygame.SRCALPHA)
                marker.fill((96, 165, 250, 230))
                self.screen.blit(marker, (swap_rect.x, swap_rect.y - self._su(4)))

    def _blit_panel_gradient(self, rect: pygame.Rect) -> None:
        """Stage 152 — вертикальная виньетка панели (кэш по размеру rect).

        Градиент строится один раз в полосу 1×INV_TOP_PANEL_GRAD_STEPS, затем
        smoothscale до размера rect и кладётся в кэш — per-frame построчной
        отрисовки нет. Скругление даёт нижний слой (сплошной цвет со средним
        тоном + border_radius), градиент блитится внутрь с отступом 1px, поэтому
        углы остаются чистыми.
        """
        from pockie_rpg.config import (
            INV_TOP_PANEL_GRAD_BOTTOM,
            INV_TOP_PANEL_GRAD_STEPS,
            INV_TOP_PANEL_GRAD_TOP,
        )
        size = (max(1, rect.w - 2), max(1, rect.h - 2))
        cache = getattr(self, "_panel_gradient_cache", None)
        if cache is None:
            cache = self._panel_gradient_cache = {}
        grad = cache.get(size)
        if grad is None:
            steps = max(2, INV_TOP_PANEL_GRAD_STEPS)
            strip = pygame.Surface((1, steps))
            for i in range(steps):
                t = i / (steps - 1)
                strip.set_at((0, i), (
                    int(round(INV_TOP_PANEL_GRAD_TOP[0] + (INV_TOP_PANEL_GRAD_BOTTOM[0] - INV_TOP_PANEL_GRAD_TOP[0]) * t)),
                    int(round(INV_TOP_PANEL_GRAD_TOP[1] + (INV_TOP_PANEL_GRAD_BOTTOM[1] - INV_TOP_PANEL_GRAD_TOP[1]) * t)),
                    int(round(INV_TOP_PANEL_GRAD_TOP[2] + (INV_TOP_PANEL_GRAD_BOTTOM[2] - INV_TOP_PANEL_GRAD_TOP[2]) * t)),
                ))
            grad = pygame.transform.smoothscale(strip, size)
            cache[size] = grad
        mid = tuple(
            (INV_TOP_PANEL_GRAD_TOP[i] + INV_TOP_PANEL_GRAD_BOTTOM[i]) // 2 for i in range(3)
        )
        pygame.draw.rect(self.screen, mid, rect, border_radius=8)
        self.screen.blit(grad, (rect.x + 1, rect.y + 1))

    def _char_pose_surface(self, max_design_h: int) -> pygame.Surface | None:
        """Stage 152/206 — кэшированный спрайт персонажа для top-панели.

        Раньше `image.load` + `smoothscale` гонялись КАЖДЫЙ КАДР (диск + ресемпл
        60 раз/сек при открытом инвентаре). Два уровня кэша:
          * `_char_pose_raws[filename]` — сырые поверхности по файлу; None при
            провале загрузки (файлы в `_char_pose_failed` — повторов нет).
          * `_char_pose_scaled_cache[(w, h)]` — финальные размеры (legacy и
            native кэшируются раздельно, т.к. размер включает масштаб).
        Масштаб считается в ДИЗАЙН-пространстве (кап ×2.0), финал ×_render_scale.

        Stage 206 — файл позы приходит от НАДЕТОГО КОСТЮМА
        (Suit.pose_filename: Ичиго — people_002_pose, Абарая — people_013_pose),
        поэтому сырой кэш теперь словарь по имени файла. Отмасштабированный
        кэш остаётся по (w, h): смена костюма меняет и сырую поверхность —
        stale-записи по размеру вытесняются естественным образом (ключ тот же,
        поверхность пересобирается при смене raw — версия raw в ключе).
        """
        from pockie_rpg.game.state import resolve_player_suit

        suit = resolve_player_suit(self.player)
        pose_file = suit.pose_filename if suit else "people_002_pose.png"

        failed = getattr(self, "_char_pose_failed", None)
        if failed is None:
            failed = self._char_pose_failed = set()
        if pose_file in failed:
            return None
        raws = getattr(self, "_char_pose_raws", None)
        if raws is None:
            raws = self._char_pose_raws = {}
        raw = raws.get(pose_file)
        if raw is None:
            char_img_path = os.path.join(
                str(ASSETS_DIR), "icons", "character", pose_file
            )
            try:
                raw = pygame.image.load(char_img_path).convert_alpha()
            except Exception:
                failed.add(pose_file)
                return None
            raws[pose_file] = raw
        if raw.get_height() <= 0:
            failed.add(pose_file)
            return None
        scale = min(max_design_h / raw.get_height(), 2.0)
        new_w = self._su(int(raw.get_width() * scale))
        new_h = self._su(int(raw.get_height() * scale))
        if new_w <= 0 or new_h <= 0:
            return None
        if (new_w, new_h) == raw.get_size():
            return raw
        cache = getattr(self, "_char_pose_scaled_cache", None)
        if cache is None:
            cache = self._char_pose_scaled_cache = {}
        # Stage 206 — ключ включает «поколение» raw-поверхности: при смене
        # файла позы с теми же габаритами кэш не вернёт чужой спрайт.
        raw_gen = id(raw)
        scaled = cache.get((raw_gen, new_w, new_h))
        if scaled is None:
            scaled = pygame.transform.smoothscale(raw, (new_w, new_h))
            cache[(raw_gen, new_w, new_h)] = scaled
        return scaled

    def _blit_slot_placeholder(self, slot_name: str, rect: pygame.Rect) -> None:
        """Stage 163 — полупрозрачная иконка-заглушка на ПУСТОМ слоте.

        Иконка — стартовый предмет-представитель слота
        (GEAR_SLOT_PLACEHOLDER_IDS), рисуется с альфой
        GEAR_SLOT_PLACEHOLDER_ALPHA: силуэт подсказывает назначение слота,
        но явно «пустой». Заглушка — чисто визуальная: не зарегистрирована
        как ClickRect, не снимается, в статы не входит. Размер/семантика
        масштабирования — как в _blit_gear_icon (пад 6, кап апскейла ×1.3,
        без даунскейла при влезании 1:1). Поверхности кэшируются по
        (icon, w, h) — smoothscale раз на размер.
        """
        from pockie_rpg.data.item_db import get_equipment

        ph_item = GEAR_SLOT_PLACEHOLDER_IDS.get(slot_name)
        if not ph_item:
            return
        gear = (self.player.get_item_definition(ph_item)
                if hasattr(self, "player") else get_equipment(ph_item))
        if gear is None:
            return
        icon_filename = gear.get("icon_filename")
        if not icon_filename:
            return
        icon_path = os.path.join(str(ASSETS_DIR), "icons", "items", icon_filename)
        try:
            s = getattr(self, "_render_scale", 1.0)
            if not hasattr(self, "_gear_icon_cache"):
                self._gear_icon_cache: dict[str, pygame.Surface] = {}
            icon = self._gear_icon_cache.get(icon_filename)
            if icon is None:
                loaded = pygame.image.load(icon_path).convert_alpha()
                self._gear_icon_cache[icon_filename] = loaded
                icon = loaded
            iw, ih = icon.get_size()
            design_w = rect.w / s
            design_h = rect.h / s
            max_w = design_w - 6
            max_h = design_h - 6
            scale = min(max_w / iw, max_h / ih)
            if scale > 1.3:
                scale = 1.0
            if scale < 1.0 and iw <= design_w and ih <= design_h:
                scale = 1.0
            new_w = max(1, int(iw * scale * s))
            new_h = max(1, int(ih * scale * s))
            cache = getattr(self, "_slot_placeholder_cache", None)
            if cache is None:
                cache = self._slot_placeholder_cache = {}
            ck = (icon_filename, new_w, new_h)
            ghost = cache.get(ck)
            if ghost is None:
                ghost = pygame.transform.smoothscale(icon, (new_w, new_h)).convert_alpha()
                ghost.set_alpha(GEAR_SLOT_PLACEHOLDER_ALPHA)
                cache[ck] = ghost
            self.screen.blit(ghost, (rect.x + (rect.w - new_w) // 2,
                                     rect.y + (rect.h - new_h) // 2))
        except Exception:
            return  # заглушка необязательна — пустой слот останется пустым.

    def _blit_gear_icon(self, gear: dict, rect: pygame.Rect,
                        with_bg: bool = True, max_upscale: float = 1.3) -> None:
        """Draw the gear's real PNG sprite, preserving aspect ratio (Stage 27).

        Stage 110 — now draws a pastel rarity background BEFORE the icon.
        The background color is determined by gear["rarity"] (if present).
        For static items without rarity, the default dark slot bg is used.

        Stage 151 — Hi-DPI: rect приходит в НАТИВНЫХ координатах; масштаб
        арта считается в ДИЗАЙН-пространстве (rect / _render_scale) — семантика
        Stage 142 (кап апскейла ×1.3) и Stage 149 (без даунскейла 1:1)
        сохраняется, финальный размер = дизайн × _render_scale. Отмасштабир-
        ованные поверхности кэшируются по (файл, w, h) — smoothscale больше
        НЕ выполняется каждый кадр.

        Stage 186 — параметры:
          * with_bg=False — НЕ заливать rect цветом редкости (слоты синтеза:
            фон рисовался ПОВЕРХ сетки 2×3 и «съедал» разметку);
          * max_upscale — кап апскейла в дизайн-пространстве (слоты синтеза:
            1.0 — иконка не увеличивается относительно исходника).
        """
        # Stage 110 — draw rarity background (pastel, soft).
        # Stage 209 — у КОСТЮМОВ качество живёт в поле "quality"
        # (COSTUME_QUALITY_BG — тира серые/синие/фиолетовые/оранжевые);
        # оно приоритетнее item-редкости (у инстансов rarity="Outfit").
        if with_bg:
            from pockie_rpg.config import COSTUME_QUALITY_BG, RARITY_SLOT_BG
            quality = gear.get("quality", "")
            bg_color = COSTUME_QUALITY_BG.get(quality)
            if bg_color is None:
                rarity = gear.get("rarity", "")
                if rarity and rarity in RARITY_SLOT_BG:
                    bg_color = RARITY_SLOT_BG[rarity]
            if bg_color is not None:
                # Fill the slot with the rarity color (rounded rect).
                pygame.draw.rect(self.screen, bg_color, rect, border_radius=4)

        icon_filename = gear.get("icon_filename")
        if not icon_filename:
            self._blit_gear_letter(gear, rect)
            return
        icon_path = os.path.join(str(ASSETS_DIR), "icons", "items", icon_filename)
        try:
            s = getattr(self, "_render_scale", 1.0)
            if not hasattr(self, "_gear_icon_cache"):
                self._gear_icon_cache: dict[str, pygame.Surface] = {}
            icon = self._gear_icon_cache.get(icon_filename)
            if icon is None:
                loaded = pygame.image.load(icon_path).convert_alpha()
                self._gear_icon_cache[icon_filename] = loaded
                icon = loaded
            iw, ih = icon.get_size()
            # Дизайн-пространство: rect/s (минус отступ 6) — как в 720p.
            design_w = rect.w / s
            design_h = rect.h / s
            max_w = design_w - 6
            max_h = design_h - 6
            scale = min(max_w / iw, max_h / ih)
            # Stage 142 — КАП АПСКЕЙЛА мелких иконок: холсты 24×24 (кольца,
            # амулеты) растягивались ×2.13 до края ячейки (мыло, «раздутость»).
            # Апскейл выше ×1.3 (в дизайн-пространстве) запрещён.
            # Stage 186 — кап параметризован (слоты синтеза: 1.0 — размер
            # иконки не увеличивается относительно исходника).
            if scale > max_upscale:
                scale = 1.0
            # Stage 149 — НЕТ ДАУНСКЕЙЛА при влезании 1:1: кольцо 24×24 в
            # мини-ячейке 27px рисовалось ×0.875 (21px) — лишний проход
            # smoothscale = блюр. Если иконка влезает в rect без масштаба —
            # рисуем оригинал (кольцо крупнее на 14% и чётче). Иконки крупнее
            # rect (51×51 в ячейке 27) продолжают даунскейлиться как раньше.
            if scale < 1.0 and iw <= design_w and ih <= design_h:
                scale = 1.0
            # Stage 151 — финальный размер в текущем пространстве рендера.
            new_w = max(1, int(iw * scale * s))
            new_h = max(1, int(ih * scale * s))
            if (new_w, new_h) == icon.get_size():
                scaled = icon
            else:
                # Stage 151 — кэш отмасштабированных иконок (перф: без
                # smoothscale каждый кадр).
                cache = getattr(self, "_gear_icon_scaled_cache", None)
                if cache is None:
                    cache = self._gear_icon_scaled_cache = {}
                scaled = cache.get((icon_filename, new_w, new_h))
                if scaled is None:
                    scaled = pygame.transform.smoothscale(icon, (new_w, new_h))
                    cache[(icon_filename, new_w, new_h)] = scaled
            self.screen.blit(scaled, (rect.x + (rect.w - new_w) // 2,
                                      rect.y + (rect.h - new_h) // 2))
        except Exception:
            self._blit_gear_letter(gear, rect)

    def _blit_gear_letter(self, gear: dict, rect: pygame.Rect) -> None:
        """Fallback: draw a colored circle with the first letter of the gear name."""
        letter = gear.get("name", "?")[0] if gear.get("name") else "?"
        slot = gear.get("slot", "")
        slot_colors = {
            "weapon": (220, 50, 50),
            "armor": (50, 120, 220),
            "boots": (50, 180, 80),
            "amulet": (200, 100, 220),
        }
        color = slot_colors.get(slot, (200, 200, 200))
        pygame.draw.circle(self.screen, color, rect.center, rect.w // 2 - self._su(4))
        letter_surf = self._su_font(18, bold=True).render(letter, True, (255, 255, 255))
        lr = letter_surf.get_rect(center=rect.center)
        self.screen.blit(letter_surf, lr.topleft)

    def _unequip_gear_item(self, slot: str) -> None:
        """Remove the item from an equipped_gear slot back to inventory.

        Stage 40 — outfit slot CANNOT be unequipped (costume must always be worn).
        Stage 64 — routes through inv_add so the item lands in the first free
        slot across pages 1 → 2 → 3.
        """
        if slot == "outfit":
            return  # Outfit cannot be removed — must always be worn.
        item_id = self.player.equipped_gear.get(slot)
        if item_id is None:
            return
        self.player.equipped_gear[slot] = None
        self.player.inv_add(item_id)
        self.player.recalc_stats()
        self.player._cached_hp = self.player.stats.max_hp
        self.player._cached_mp = self.player.stats.max_mp
        self._save_player()

    def _render_gear_tooltip(self, item_id: str, modal_right_x: int) -> None:
        """Render the equipment tooltip to the right of the inventory modal.

        Stage 109 — Bug fix: now uses get_item_definition() instead of
        get_equipment() directly, so it correctly resolves BOTH static items
        (from EQUIPMENT_DB) and procedural generated weapons (from
        PlayerState.generated_weapons, instance IDs like "gen_w_001").

        Stage 109 — Visual layout:
          1. Header: slot label + item name (colored by rarity).
          2. Level requirement + item level line.
          3. Enchant level line.
          4. Main stat block: Атака: min - max (always shown for weapons).
          5. ─── Separator line ─── (only if item has secondary stats).
          6. Secondary stats block (Крит, Множители, etc.).
          For Grey items (0 secondary stats), separator + secondary block
          are NOT rendered — tooltip ends after the main stat.

        Stage 177 — по запросу пользователя: строка «Продажа: N зол.»
        УДАЛЕНА (цена продажи видна только в магазине), префикс редкости
        «[GRAY]/[RED]/…» из шапки удалён — цвет виден по рамке/иконке,
        остаётся только тип предмета («ОРУЖИЕ»).

        Stage 151 — координаты дизайн-пространства, отрисовка через _su().
        """
        from pockie_rpg.data.item_db import get_outfit
        # Stage 40 — check if this is an outfit (special tooltip).
        # Stage 165 — заточенные костюмы-инстансы ("outfit_inst_<n>") тоже
        # направляются в тултип костюма: раньше get_outfit по инстанс-ID
        # возвращал None, и +N-костюмы рисовались общим тултипом снаряжения
        # (без плюса и с немасштабированными статами).
        outfit = get_outfit(item_id)
        if outfit is None and hasattr(self, "player"):
            inst_def = self.player.get_item_definition(item_id)
            if inst_def is not None and (inst_def.get("is_outfit_instance")
                                         or inst_def.get("slot") == "outfit"):
                outfit = inst_def
        if outfit is not None:
            self._render_outfit_tooltip(item_id, outfit, modal_right_x)
            return

        # Stage 181 — БАФ-расходник: специальный тултип (формат ТЗ) вместо
        # экипировочного. is_buff ставит get_buff_item().
        if hasattr(self, "player"):
            buff_def = self.player.get_item_definition(item_id)
        else:
            buff_def = None
        if buff_def is not None and buff_def.get("is_buff"):
            self._render_buff_item_tooltip(item_id, buff_def, modal_right_x)
            return

        # Stage 109 — Bug fix: resolve item via player.get_item_definition()
        # which checks both EQUIPMENT_DB and generated_weapons.
        gear = self.player.get_item_definition(item_id) if hasattr(self, "player") else None
        if gear is None:
            # Fallback for cases where player is not available (legacy callers).
            from pockie_rpg.data.item_db import get_equipment
            gear = get_equipment(item_id)
        if gear is None:
            return

        # Stage 109 — determine rarity color for header.
        from pockie_rpg.config import RARITY_RGB
        rarity = gear.get("rarity", "")
        rarity_color = RARITY_RGB.get(rarity, (234, 179, 8))  # default gold

        tip_w = 240  # Stage 58 — slightly wider to prevent overflow.
        stats = gear.get("stats", {})
        # Stage 115 — split stats using SLOT_MAIN_STATS from config.
        from pockie_rpg.config import SLOT_MAIN_STATS
        slot = gear.get("slot", "")
        main_keys = SLOT_MAIN_STATS.get(slot, ("min_atk", "max_atk"))
        main_stats = {k: v for k, v in stats.items() if k in main_keys}
        secondary_stats = {k: v for k, v in stats.items() if k not in main_keys}
        # Stage 109/146 — dynamic height: иконка сверху (74) + 2 строки (82/98)
        # + статы; минимум 152. Stage 177 — строка «Продажа» удалена (−16).
        stats_count = len(main_stats) + len(secondary_stats)
        has_separator = len(secondary_stats) > 0
        separator_h = 16 if has_separator else 0
        tip_h = max(152, 118 + stats_count * 18 + separator_h + 14)
        tip_x = modal_right_x + 16
        tip_y = (SCREEN_HEIGHT - tip_h) // 2
        if tip_x + tip_w > SCREEN_WIDTH:
            tip_x = modal_right_x - tip_w - 16

        tip_rect = pygame.Rect(self._su(tip_x), self._su(tip_y),
                               self._su(tip_w), self._su(tip_h))
        pygame.draw.rect(self.screen, (15, 15, 18), tip_rect, border_radius=8)
        # Stage 109 — border colored by rarity.
        pygame.draw.rect(self.screen, rarity_color, tip_rect, 2, border_radius=8)
        pygame.draw.rect(self.screen, rarity_color,
                         pygame.Rect(self._su(tip_x), self._su(tip_y),
                                     self._su(tip_w), self._su(4)), border_radius=2)

        from pockie_rpg.config import SLOT_NAME_RU as slot_name_map
        slot_name = slot_name_map.get(gear["slot"], gear["slot"])
        # Stage 177 — только тип предмета, без префикса редкости «[GRAY] …»
        # (цвет редкости и так читается по рамке/иконке).
        slot_label = self._su_font(13).render(slot_name.upper(), True, rarity_color)
        self.screen.blit(slot_label, (self._su(tip_x + 12), self._su(tip_y + 12)))

        # Stage 146 — ИКОНКА предмета в тултипе (справа вверху, 64×64),
        # рамка цвета редкости; текст обтекает её слева.
        icon_zone = pygame.Rect(self._su(tip_x + tip_w - 76), self._su(tip_y + 10),
                                self._su(64), self._su(64))
        icon_plate = pygame.Surface((self._su(68), self._su(68)), pygame.SRCALPHA)
        icon_plate.fill((20, 20, 24, 230))
        self.screen.blit(icon_plate, (icon_zone.x - self._su(2), icon_zone.y - self._su(2)))
        self._blit_gear_icon(gear, icon_zone)
        # Рамка ПОВЕРХ иконки (blit_gear_icon заливает фон зоны).
        pygame.draw.rect(self.screen, rarity_color, icon_zone, 1, border_radius=4)

        name_surf = self._su_font(18, bold=True).render(gear["name"], True, (255, 255, 255))
        self.screen.blit(name_surf, (self._su(tip_x + 12), self._su(tip_y + 32)))

        # Stage 32 — item_level line + Stage 109 level_requirement.
        # Stage 146 — строки после иконки (иконка занимает 10..74 по Y).
        item_level = gear.get("item_level", 1)
        level_req = gear.get("level_requirement", item_level)
        level_text = f"Ур. предмета: {item_level}"
        if level_req != item_level:
            level_text += f" | Требует ур.: {level_req}"
        level_surf = self._su_font(13).render(level_text, True, (180, 180, 200))
        self.screen.blit(level_surf, (self._su(tip_x + 12), self._su(tip_y + 82)))

        # Stage 116 — enchant level per ITEM-ID (works for equipped AND inventory items).
        # Previously only checked equipped items; now checks gear_enchants directly.
        enchant_lvl = 0
        if hasattr(self, "player"):
            enchant_lvl = self.player.gear_enchants.get(item_id, 0)
        if enchant_lvl > 0:
            ench_color = (234, 179, 8) if enchant_lvl >= 10 else (80, 220, 100)
            ench_surf = self._su_font(13).render(f"Заточка: +{enchant_lvl}", True, ench_color)
        else:
            ench_surf = self._su_font(13).render("Заточка: +0", True, (113, 113, 122))
        self.screen.blit(ench_surf, (self._su(tip_x + 12), self._su(tip_y + 98)))

        # Stage 177 — строка «Продажа: N зол.» удалена из тултипа.

        from pockie_rpg.config import STAT_LABEL_RU as stat_label_map

        stat_y = tip_y + 118  # Stage 177 — было 132 (после удаления «Продажа»)

        # Stage 115 — MAIN STAT BLOCK (weapon: "Атака: X - Y", others: individual lines).
        from pockie_rpg.data.item_db import get_enchanted_stat, scale_gear_stat
        if slot == "weapon" and "min_atk" in main_stats and "max_atk" in main_stats:
            min_val = scale_gear_stat(main_stats["min_atk"], item_level)
            max_val = scale_gear_stat(main_stats["max_atk"], item_level)
            min_final = get_enchanted_stat(min_val, enchant_lvl)
            max_final = get_enchanted_stat(max_val, enchant_lvl)
            atk_line = f"Атака: {min_final} - {max_final}"
            atk_color = (80, 220, 100) if enchant_lvl == 0 else (234, 179, 8)
            atk_surf = self._su_font(13).render(atk_line, True, atk_color)
            self.screen.blit(atk_surf, (self._su(tip_x + 12), self._su(stat_y)))
            stat_y += 18
        elif main_stats:
            # Non-weapon items: show main stats individually.
            for stat_key, value in main_stats.items():
                label = stat_label_map.get(stat_key, stat_key)
                scaled = scale_gear_stat(value, item_level)
                final_val = get_enchanted_stat(scaled, enchant_lvl)
                sign = "+" if final_val >= 0 else ""
                line = f"{sign}{final_val}  {label}"
                stat_color = (80, 220, 100) if enchant_lvl == 0 else (234, 179, 8)
                stat_surf = self._su_font(13).render(line, True, stat_color)
                self.screen.blit(stat_surf, (self._su(tip_x + 12), self._su(stat_y)))
                stat_y += 18

        # Stage 109 — SEPARATOR LINE (only if item has secondary stats).
        # Grey items (0 secondary) do NOT show separator or secondary block.
        if has_separator:
            separator = self._su_font(13).render("─" * 22, True, (113, 113, 122))
            self.screen.blit(separator, (self._su(tip_x + 12), self._su(stat_y)))
            stat_y += 18

        # Stage 109 — SECONDARY STATS BLOCK.
        for stat_key, value in secondary_stats.items():
            label = stat_label_map.get(stat_key, stat_key)
            scaled = scale_gear_stat(value, item_level)
            final_val = get_enchanted_stat(scaled, enchant_lvl)
            sign = "+" if final_val >= 0 else ""
            # Stage 109 — secondary stats use % suffix for pct types.
            suffix = "%" if stat_key.endswith("_pct") or stat_key == "atk_mul" else ""
            line = f"{sign}{final_val}{suffix}  {label}"
            stat_color = (100, 180, 255) if enchant_lvl == 0 else (234, 179, 8)
            stat_surf = self._su_font(13).render(line, True, stat_color)
            max_text_w = self._su(tip_w - 24)
            if stat_surf.get_width() > max_text_w:
                while stat_surf.get_width() > max_text_w and len(label) > 2:
                    label = label[:-1]
                    line = f"{sign}{final_val}{suffix}  {label}…"
                    stat_surf = self._su_font(13).render(line, True, stat_color)
            self.screen.blit(stat_surf, (self._su(tip_x + 12), self._su(stat_y)))
            stat_y += 18

    # ------------------------------------------------------------------
    # Stage 164 — якорная память (СПИСОК позиций на item_id): см. докстринг
    # layout'а в _render_inventory_modal. Хелперы — единственные точки
    # изменения памяти (кроме .clear() в «Сорт»).
    # ------------------------------------------------------------------

    _INV_ANCHOR_CAP = 16  # защита от неограниченного роста списка позиций

    def _inv_anchor_positions(self, item_id: str) -> list[tuple[int, int]]:
        mem = self._inv_item_anchor_memory
        lst = mem.get(item_id)
        if lst is None:
            mem[item_id] = lst = []
        return lst

    def _inv_anchor_add(self, item_id: str, pos: tuple[int, int]) -> None:
        lst = self._inv_anchor_positions(item_id)
        if pos not in lst:
            lst.append(pos)
        del lst[self._INV_ANCHOR_CAP:]

    def _inv_anchor_remove(self, item_id: str, pos: tuple[int, int]) -> None:
        """Убрать позицию копии item_id из якорной памяти.

        Stage 164 — вызывается, когда предмет ПОКИДАЕТ инвентарь (в слот
        синтеза): без этого дубликат занимал освободившуюся позицию и
        остальные визуально пересортировывались.
        """
        lst = self._inv_item_anchor_memory.get(item_id)
        if lst and pos in lst:
            lst.remove(pos)

    def _inv_anchor_move(self, item_id: str, old_pos: tuple[int, int],
                         new_pos: tuple[int, int]) -> None:
        """Переместить позицию копии item_id: old_pos → new_pos.

        old_pos ищется по ТЕКУЩЕЙ клетке layout'а — для дубликатов это
        однозначно идентифицирует перетащенный экземпляр (позиции копий
        различны), чужие копии не затрагиваются.
        """
        lst = self._inv_anchor_positions(item_id)
        if old_pos in lst:
            lst.remove(old_pos)
        if new_pos not in lst:
            lst.append(new_pos)
        del lst[self._INV_ANCHOR_CAP:]

    def _try_start_drag(self, pos: tuple[int, int]) -> bool:
        """Check if the cursor is on a draggable item; start dragging if so.

        Returns True if a drag was started (so the caller can skip the
        normal click dispatch).

        Stage 64 — reads items from the *current* page's slot list (not the
        global inventory list). Source is recorded as ("inv", slot_idx, page).

        Stage 151 — pos конвертируется в native (layout'ы нативные).
        """
        pos = self._inv_native_pos(pos)
        if not hasattr(self, "_gear_layout") or not hasattr(self, "_inv_layout"):
            return False

        # Check gear slots first — dragging from a slot unequips the item.
        for slot_name, rect in self._gear_layout.items():
            if rect.collidepoint(pos):
                item_id = self.player.equipped_gear.get(slot_name)
                if item_id is not None:
                    self._drag_item_id = item_id
                    self._drag_source = ("gear", slot_name)
                    return True
                return False  # clicked on an empty slot — don't dispatch click

        # Check inventory cells on the current page.
        page_slots = self.player.inv_page_slots(self._inv_current_page)
        for slot_idx, rect, span in self._inv_layout:
            if rect.collidepoint(pos):
                if 0 <= slot_idx < len(page_slots):
                    # Stage 183 — стак-слот распаковывается в item_id.
                    item_id = self.player.slot_item_id(page_slots[slot_idx])
                    if item_id is not None:
                        self._drag_item_id = item_id
                        # Stage 64 — record page so we can clear the right slot
                        # even if the player switches tabs mid-drag (though
                        # _set_inv_page resets drag state on tab switch anyway).
                        self._drag_source = ("inv", slot_idx, self._inv_current_page)
                        return True
                return False

        return False

    def _finish_drag(self, pos: tuple[int, int]) -> None:
        """Handle mouse-release while dragging — drop on target or cancel.

        Stage 64 — when the source is an inventory slot on the current page,
        dropping on another inventory cell swaps the two slots in place:
            inventory[current_page][i], inventory[current_page][j]
                = inventory[current_page][j], inventory[current_page][i]

        Stage 67 — **cross-page drag**: the source can be on a different page
        than the current one. Dropping on a cell of the current page moves
        (or swaps) the item across pages. Dropping on a tab button (1/2/3)
        moves the item to that page's first empty slot (or swaps if full).

        Stage 151 — pos конвертируется в native (layout'ы нативные).
        Stage 163 — ROOT CAUSE drag'а инвентарь→синтез: rect'ы слотов синтеза
        вычисляются в event-контексте при `_render_scale == 1.0` (вне рендера)
        → всегда в ДИЗАЙН-координатах, а `_inv_native_pos` переводил позицию
        в нативные (×UI_SCALE) — на 2К collidepoint никогда не совпадал и дроп
        молча отменялся. Слоты синтеза хиттестятся по исходной ДИЗАЙН-позиции
        (`pos_design`); остальные ветки (gear/inv/wardrobe — layout'ы, снятые
        при рендере) по-прежнему в нативном пространстве.
        """
        pos_design = pos  # событие всегда приходит в дизайн-координатах.
        pos = self._inv_native_pos(pos)
        item_id = self._drag_item_id
        source = self._drag_source
        # Clear drag state first (so render returns to normal next frame).
        self._drag_item_id = None
        self._drag_source = None
        if item_id is None or source is None:
            return
        if not hasattr(self, "_gear_layout") or not hasattr(self, "_inv_layout"):
            return
        from pockie_rpg.data.item_db import get_equipment

        gear = (self.player.get_item_definition(item_id)
                if hasattr(self, "player") else get_equipment(item_id))
        if gear is None:
            return
        item_slot = gear["slot"]

        # Stage 157 — SYNTH/WARDROBE ПЕРВЫМИ: их модалки рендерятся ПОВЕРХ
        # инвентаря, значит и дропы они ловят раньше (иначе gear-слот под
        # synth-слотом перехватывал бы дроп).

        # Stage 156 — SYNTH: дроп костюма в слот синтеза (drag-and-drop).
        # Stage 164 — слоты принимают предметы ФИЗИЧЕСКИ: костюм УБИРАЕТСЯ
        # из инвентаря (src_slots[src_idx] = None) и кладётся в слот как
        # item_id. Один экземпляр теперь невозможно положить в два слота
        # (прежний баг: loc-ссылка дублировалась во все слоты, а рецепт
        # «Нужны 3 РАЗНЫХ ячейки» держал кнопку «Создать» неактивной).
        # Слоты: 4 (4-й — результат, дроп не принимает). Stage 163 —
        # хиттест по ДИЗАЙН-позиции события (см. docstring выше).
        if getattr(self, "_synth_modal_open", False):
            main_r, cat1_r, cat2_r, res_r = self._synth_slot_rects()
            # Stage 166 — слот РЕЗУЛЬТАТА не принимает дропы: иначе дроп
            # «сквозь» него попадал в инвентарь/слоты под окном.
            if res_r.collidepoint(pos_design):
                return
            for rect, attr in zip(
                (main_r, cat1_r, cat2_r),
                ("_synth_main_item", "_synth_cat1_item", "_synth_cat2_item"),
            ):
                if not rect.collidepoint(pos_design):
                    continue
                # Stage 184 — слоты синтеза принимают и БАФЫ (ветка синтеза
                # бафов опыта); костюмы — как раньше.
                is_buff_item = self.player.slot_item_id(item_id) and (
                    self.player.get_item_definition(item_id) or {}
                ).get("is_buff")
                if self.player._outfit_model_of(item_id, self.player) is None \
                        and not is_buff_item:
                    return  # не костюм и не баф — слоты его не принимают.
                if source[0] != "inv":
                    return
                src_idx = source[1]
                src_page = source[2] if len(source) > 2 else self._inv_current_page
                src_slots = self.player.inv_page_slots(src_page)
                if not (0 <= src_idx < len(src_slots)) \
                        or self.player.slot_item_id(src_slots[src_idx]) != item_id:
                    return
                if getattr(self, attr, None) is not None:
                    return  # слот занят — дроп игнорируется.
                # Stage 164 — якорь уходящего предмета снимается: иначе
                # дубликат занимал освободившуюся позицию и остальные
                # предметы визуально пересортировывались.
                if (src_page == self._inv_current_page
                        and hasattr(self, "_inv_item_anchor_memory")):
                    for s_idx, s_rect, _s in self._inv_layout:
                        if s_idx == src_idx:
                            c = (s_rect.x - self._inv_grid_params[0]) // (self._inv_grid_params[4] + self._inv_grid_params[3])
                            r = (s_rect.y - self._inv_grid_params[1]) // (self._inv_grid_params[4] + self._inv_grid_params[3])
                            self._inv_anchor_remove(item_id, (c, r))
                            break
                # Физический перенос: костюм — ячейка освобождается; баф —
                # списывается 1 ШТ. из стака (стак остаётся в ячейке).
                if is_buff_item:
                    if not self.player.inv_remove(item_id):
                        return
                else:
                    src_slots[src_idx] = None
                setattr(self, attr, item_id)
                self._save_player()
                return

        # Stage 138 — WARDROBE: дроп костюма в слот гардероба (модалка открыта).
        # Stage 156 — фикс двойного удаления: UI раньше сам вынимал предмет
        # из data-слота (src_slots[src_idx] = None), после чего
        # wardrobe_store → inv_remove(item_id) НЕ НАХОДИЛ предмет и
        # возвращал False (дроп в гардероб молча не работал). Теперь UI НЕ
        # трогает data-слот — wardrobe_store сам делает inv_remove.
        if getattr(self, "_wardrobe_modal_open", False) and hasattr(self, "_wardrobe_layout"):
            from pockie_rpg.config import WARDROBE_SLOTS_PER_PAGE
            w_page = getattr(self, "_wardrobe_current_page", 1)
            for w_idx, w_rect in enumerate(self._wardrobe_layout):
                if w_rect.collidepoint(pos):
                    if self.player._outfit_model_of(item_id, self.player) is None:
                        return  # не костюм — отмена.
                    if source[0] == "gear" and source[1] == "outfit":
                        self._unequip_gear_item("outfit")
                    # Stage 167 — слоты пагинированы: индекс страницы →
                    # ГЛОБАЛЬНЫЙ индекс хранилища (5 слотов на страницу).
                    w_slot = (w_page - 1) * WARDROBE_SLOTS_PER_PAGE + w_idx
                    placed = self.player.wardrobe_store(item_id, slot=w_slot)
                    if not placed:
                        # Слот занят/нет места — вернуть в инвентарь.
                        self.player.inv_add(item_id)
                    self._save_player()
                    return

        # Check if dropped on a gear slot.
        for slot_name, rect in self._gear_layout.items():
            if rect.collidepoint(pos):
                # Stage 146 — СТРОГО: ring -> accessory, amulet -> accessory2,
                # прочее -> свой слот. Никаких кросс-дропов.
                valid = False
                if item_slot == "accessory":
                    itype = (gear.get("type") or "").lower()
                    if slot_name == "accessory" and itype != "amulet":
                        valid = True
                    if slot_name == "accessory2" and itype == "amulet":
                        valid = True
                elif slot_name == item_slot:
                    valid = True
                if valid:
                    self._drop_to_slot(item_id, source, slot_name)
                # else: wrong slot type for this item → cancel (no-op).
                self._save_player()
                return

        # Stage 67 — check if dropped on a tab button (cross-page move).
        if hasattr(self, "_inv_tab_rects"):
            for tab_page, tab_rect in self._inv_tab_rects.items():
                if tab_rect.collidepoint(pos):
                    if source[0] == "inv":
                        src_idx = source[1]
                        src_page = source[2] if len(source) > 2 else self._inv_current_page
                        self._move_item_to_page(src_page, src_idx, tab_page)
                        self._save_player()
                    # gear → tab: no-op (unequip already goes to first free slot).
                    return

        # Check if dropped on a specific inventory cell on the current page.
        # Stage 148 — свап инвентарь↔инвентарь ТОЛЬКО при РАВНЫХ спанах
        # (предмет-цель встаёт на старое место источника и должен влезть);
        # разные спаны → отмена (красная зона это подсвечивает).
        page_slots = self.player.inv_page_slots(self._inv_current_page)
        from pockie_rpg.config import item_span as _span_cfg
        for slot_idx, rect, span in self._inv_layout:
            if rect.collidepoint(pos):
                if source[0] == "inv":
                    src_idx = source[1]
                    src_page = source[2] if len(source) > 2 else self._inv_current_page
                    if src_page == self._inv_current_page:
                        if src_idx == slot_idx:
                            return  # dropped back on same slot — no-op.
                        tgt_item = page_slots[slot_idx]
                        # Stage 183 — распаковка стаков для спан-проверок
                        # (слоты могут быть dict {"item_id", "count"}).
                        tgt_id = self.player.slot_item_id(tgt_item)
                        if tgt_id is not None and span != _span_cfg(
                            self.player.get_item_definition(item_id) or {}
                        ):
                            return  # спаны разные — свап невозможен, отмена.
                        # Same-page swap. Stage 148 — якорная память по item_id:
                        # предмет-цель получает СТАРУЮ позицию источника,
                        # перетаскиваемый — позицию цели.
                        # Stage 164 — обновление по СПИСКУ позиций, old_pos =
                        # ТЕКУЩАЯ клетка layout'а: для дубликатов (одинаковый
                        # item_id) обмен копий не меняет множество позиций,
                        # чужие предметы не сдвигаются (жалоба: drag костюма
                        # пересортировывал остальные).
                        tgt_item = page_slots[slot_idx]
                        a_pos = None
                        b_pos = None
                        for s_idx, s_rect, _s in self._inv_layout:
                            c = (s_rect.x - self._inv_grid_params[0]) // (self._inv_grid_params[4] + self._inv_grid_params[3])
                            r = (s_rect.y - self._inv_grid_params[1]) // (self._inv_grid_params[4] + self._inv_grid_params[3])
                            if s_idx == slot_idx:
                                b_pos = (c, r)
                            elif s_idx == src_idx:
                                a_pos = (c, r)
                        tgt_id = self.player.slot_item_id(tgt_item)
                        if tgt_id == item_id:
                            pass  # обмен двух копий одного предмета — позиции те же.
                        elif a_pos is not None and b_pos is not None:
                            self._inv_anchor_move(item_id, a_pos, b_pos)
                            if tgt_id is not None:
                                self._inv_anchor_move(tgt_id, b_pos, a_pos)
                        page_slots[src_idx], page_slots[slot_idx] = (
                            page_slots[slot_idx], page_slots[src_idx]
                        )
                        self._save_player()
                        return
                    # Stage 67 — cross-page swap: move item from source page
                    # to current page's target slot, and the target slot's
                    # item (if any) goes to the source slot.
                    src_slots = self.player.inv_page_slots(src_page)
                    src_item = src_slots[src_idx]
                    tgt_item = page_slots[slot_idx]
                    # Stage 183 — спан-проверка по распакованным item_id.
                    tgt_id = self.player.slot_item_id(tgt_item)
                    src_id = self.player.slot_item_id(src_item)
                    if tgt_id is not None and span != _span_cfg(
                        self.player.get_item_definition(src_id or "") or {}
                    ):
                        return  # Stage 148 — спаны разные, свап невозможен.
                    page_slots[slot_idx] = src_item
                    src_slots[src_idx] = tgt_item  # None | str | dict-стак.
                    # Stage 148 — якорная память: у предмета-цели (уезжает на
                    # другую страницу) якорь снимается — на новой странице он
                    # «прилипнет» заново; перетащенный предмет получает
                    # позицию цели на текущей странице.
                    if hasattr(self, "_inv_item_anchor_memory"):
                        if tgt_id is not None:
                            self._inv_anchor_positions(tgt_id).clear()
                        for s_idx, s_rect, _s in self._inv_layout:
                            if s_idx == slot_idx:
                                c = (s_rect.x - self._inv_grid_params[0]) // (self._inv_grid_params[4] + self._inv_grid_params[3])
                                r = (s_rect.y - self._inv_grid_params[1]) // (self._inv_grid_params[4] + self._inv_grid_params[3])
                                self._inv_anchor_add(src_item, (c, r))
                                break
                    self._save_player()
                    return
                if source[0] == "gear":
                    # From a gear slot into the inventory grid → unequip
                    # (this places the item in the first free slot).
                    self._unequip_gear_item(source[1])
                    return
                return

        # Stage 147 — дроп в ПУСТУЮ зону мини-сетки: перемещение предмета
        # на конкретное место (анкор). Раньше — no-op («предмет возвращался»).
        # Stage 148 — якорь пишется в ПАМЯТЬ ПО item_id (липкий layout).
        if hasattr(self, "_inv_grid_rect") and self._inv_grid_rect.collidepoint(pos):
            if source[0] == "inv":
                src_idx = source[1]
                src_page = source[2] if len(source) > 2 else self._inv_current_page
                src_slots = self.player.inv_page_slots(src_page)
                if not (0 <= src_idx < len(src_slots)) \
                        or self.player.slot_item_id(src_slots[src_idx]) != item_id:
                    return
                # Якорь: мини-ячейка под курсором.
                gx, gy, cols, gap, cell, rows = self._inv_grid_params
                col = int((pos[0] - gx) // (cell + gap))
                row = int((pos[1] - gy) // (cell + gap))
                if not (0 <= col < cols and 0 <= row < rows):
                    return
                drag_item = self.player.get_item_definition(item_id)
                from pockie_rpg.config import item_span as _item_span_cfg
                span = _item_span_cfg(drag_item) if drag_item else (1, 1)
                # Зона влезает в сетку?
                if col + span[0] > cols or row + span[1] > rows:
                    return
                # Занятость: считаем по layout (предметы страницы), исключая источник.
                zone_cells = [
                    (col + dx, row + dy)
                    for dx in range(span[0]) for dy in range(span[1])
                ]
                src_zone = set()
                for s_idx, s_rect, s_span in self._inv_layout:
                    sc = (s_rect.x - gx) // (cell + gap)
                    sr = (s_rect.y - gy) // (cell + gap)
                    if s_idx == src_idx:
                        src_zone = {(sc + dx, sr + dy) for dx in range(s_span[0]) for dy in range(s_span[1])}
                for s_idx, s_rect, s_span in self._inv_layout:
                    if s_idx == src_idx:
                        continue
                    sc = (s_rect.x - gx) // (cell + gap)
                    sr = (s_rect.y - gy) // (cell + gap)
                    for dx in range(s_span[0]):
                        for dy in range(s_span[1]):
                            if (sc + dx, sr + dy) in zone_cells and (sc + dx, sr + dy) not in src_zone:
                                return  # место занято другим предметом.
                # Перемещение: якорь в память по item_id.
                if src_page != self._inv_current_page:
                    # Кросс-страница: забрать из источника, положить в первый
                    # пустой data-слот текущей страницы с якорем.
                    # Stage 183 — перемещается СЫРОЙ слот (стак переносится
                    # целиком, с count).
                    src_entry = src_slots[src_idx]
                    src_slots[src_idx] = None
                    tgt_slots = self.player.inv_page_slots(self._inv_current_page)
                    free_idx = next((i for i, v in enumerate(tgt_slots) if v is None), None)
                    if free_idx is None:
                        src_slots[src_idx] = src_entry
                        return
                    tgt_slots[free_idx] = src_entry
                if hasattr(self, "_inv_item_anchor_memory"):
                    # Stage 164 — перемещение позиции КОПИИ: old_pos = текущая
                    # клетка источника в layout'е (для дубликатов — только
                    # перетащенный экземпляр меняет позицию).
                    src_pos = None
                    for s_idx, s_rect, _s in self._inv_layout:
                        if s_idx == src_idx:
                            c = (s_rect.x - self._inv_grid_params[0]) // (self._inv_grid_params[4] + self._inv_grid_params[3])
                            r = (s_rect.y - self._inv_grid_params[1]) // (self._inv_grid_params[4] + self._inv_grid_params[3])
                            src_pos = (c, r)
                            break
                    if src_page == self._inv_current_page and src_pos is not None:
                        self._inv_anchor_move(item_id, src_pos, (col, row))
                    else:
                        # Кросс-страница: источника нет в layout'е текущей
                        # страницы — просто фиксируем новую позицию.
                        self._inv_anchor_add(item_id, (col, row))
                self._save_player()
                return
            if source[0] == "gear":
                # С гир-слота в сетку — unequip (идёт в первый свободный data-слот).
                self._unequip_gear_item(source[1])
                return
            return

        # Dropped outside any target → cancel (no-op, item stays in source).

    def _move_item_to_page(self, src_page: int, src_idx: int, dest_page: int) -> None:
        """Stage 67 — move an item from (src_page, src_idx) to dest_page.

        Finds the first empty slot on dest_page. If dest_page is full, swaps
        with the item in the first slot of dest_page (so nothing is lost).
        The source slot becomes empty (None) or receives the swapped item.
        """
        dest_slots = self.player.inv_page_slots(dest_page)
        src_slots = self.player.inv_page_slots(src_page)
        src_item = src_slots[src_idx]
        if src_item is None:
            return
        # Find first empty slot on dest_page.
        for i, s in enumerate(dest_slots):
            if s is None:
                dest_slots[i] = src_item
                src_slots[src_idx] = None
                return
        # dest_page is full → swap with slot 0 (rare case, keeps nothing lost).
        dest_slots[0], src_slots[src_idx] = src_item, dest_slots[0]

    def _drop_to_slot(self, item_id: str, source: tuple, target_slot: str) -> None:
        """Move an item from its source into a gear slot.

        source is ('inv', slot_idx, page) or ('gear', slot_name).
        target_slot is the destination slot name (must match item's slot).

        Stage 66 — when source is ('inv', slot_idx, page), passes source_slot
        to equip_gear_item so the old item goes to the exact dragged-from
        slot (preserves slot position — canonical RPG swap behavior).
        """
        if source[0] == "inv":
            # From inventory → equip (handles swap of old item back to inventory).
            # Stage 66 — pass source_slot so the old item goes to the exact
            # dragged-from slot, not the first empty slot.
            src_idx = source[1]
            src_page = source[2] if len(source) > 2 else self._inv_current_page
            self.player.equip_gear_item(
                item_id,
                source_slot=(src_page, src_idx),
            )
        elif source[0] == "gear":
            src_slot = source[1]
            if src_slot == target_slot:
                return  # dropped back on same slot — no-op.
            # Slot → slot: swap items between the two slots.
            old_item = self.player.equipped_gear.get(target_slot)
            self.player.equipped_gear[target_slot] = self.player.equipped_gear[src_slot]
            self.player.equipped_gear[src_slot] = old_item
            self.player.recalc_stats()
            self.player._cached_hp = self.player.stats.max_hp
            self.player._cached_mp = self.player.stats.max_mp

    def _render_dragged_icon(self) -> None:
        """Render the dragged item icon at the cursor tip (Stage 28).

        Stage 148 — размер призрака = СПАН предмета в мини-ячейках
        (item_span): кольца/амулеты 1×1 → 27×27, броня 2×2 → 55×55,
        оружие 2×3 → 56×83. Раньше всё не-оружие рисовалось 48×48 —
        призрак кольца выглядел как 2×2.

        Stage 151 — координаты через _su(); в native-фазе `self._mouse_pos`
        уже нативный (свап в _render_native_overlays). «Живой» курсор
        (get_pos прямо перед отрисовкой) — отдельная идея в реестре.

        Stage 160 — верхний левый угол призрака = КОНЧИК КУРСОРА (без
        оффсета +28 Stage 147) + общая прозрачность DRAG_GHOST_ALPHA:
        подсветка зоны/цели дропа видна сквозь предмет.
        """
        from pockie_rpg.config import INV_CELL, INV_GAP, item_span
        from pockie_rpg.data.item_db import get_equipment
        if self._drag_item_id is None:
            return
        gear = (self.player.get_item_definition(self._drag_item_id)
                if hasattr(self, "player") else get_equipment(self._drag_item_id))
        if gear is None:
            return
        span_w, span_h = item_span(gear) if gear else (1, 1)
        w = self._su(INV_CELL) * span_w + self._su(INV_GAP) * (span_w - 1)
        h = self._su(INV_CELL) * span_h + self._su(INV_GAP) * (span_h - 1)

        def _draw(target: pygame.Surface, rect: pygame.Rect) -> None:
            pygame.draw.rect(target, (234, 179, 8, 60), rect, border_radius=4)
            self._blit_gear_icon(gear, rect)
            # Рамка ПОСЛЕ иконки: rarity-подложка иконки непрозрачна и
            # перекрыла бы рамку, нарисованную раньше (Stage 160).
            pygame.draw.rect(target, (234, 179, 8), rect, self._su(2), border_radius=4)

        self._render_drag_ghost(_draw, w, h)

    def _render_buff_item_tooltip(self, item_id: str, buff_def: dict, modal_right_x: int) -> None:
        """Stage 181/184 — тултип бафа-расходника в инвентаре (формат ТЗ):

            РАСХОДНИК                [иконка]
            Опыт +50%
            ─────────────
            Скорость опыта 50%

        Stage 184 — по запросу пользователя: время активного бафа и подсказка
        про ПКМ из тултипа УДАЛЕНЫ — инвентарный тултип только описывает
        предмет (время видно в тултипе иконки под аватаркой).
        """
        from pockie_rpg.config import get_buff

        su = self._su
        buff = get_buff(item_id)
        if buff is None:
            return

        tip_w = 240
        pad = 12
        f_label = self._su_font(11, bold=True)
        f_title = self._su_font(16, bold=True)
        f_body = self._su_font(12)

        desc = buff_def.get("desc") or buff.get("name", "")
        # Геометрия (дизайн-px): шапка 12..44, иконка 10..74, линия 78,
        # desc 86..102, низ 110.
        tip_h = 110
        tip_x = modal_right_x + 16
        tip_y = (SCREEN_HEIGHT - tip_h) // 2
        if tip_x + tip_w > SCREEN_WIDTH:
            tip_x = modal_right_x - tip_w - 16

        tip_rect = pygame.Rect(su(tip_x), su(tip_y), su(tip_w), su(tip_h))
        pygame.draw.rect(self.screen, (15, 15, 18), tip_rect, border_radius=8)
        pygame.draw.rect(self.screen, (234, 179, 8), tip_rect, 2, border_radius=8)
        pygame.draw.rect(self.screen, (234, 179, 8),
                         pygame.Rect(su(tip_x), su(tip_y), su(tip_w), su(4)), border_radius=2)

        # Иконка справа вверху (как у экипировки).
        icon_zone = pygame.Rect(su(tip_x + tip_w - 76), su(tip_y + 10), su(64), su(64))
        icon_plate = pygame.Surface((su(68), su(68)), pygame.SRCALPHA)
        icon_plate.fill((20, 20, 24, 230))
        self.screen.blit(icon_plate, (icon_zone.x - su(2), icon_zone.y - su(2)))
        self._blit_gear_icon(buff_def, icon_zone)
        pygame.draw.rect(self.screen, (234, 179, 8), icon_zone, 1, border_radius=4)

        type_surf = f_label.render("РАСХОДНИК", True, (160, 160, 170))
        self.screen.blit(type_surf, (su(tip_x + pad), su(tip_y + 12)))
        name_surf = f_title.render(buff_def.get("name", item_id), True, (255, 255, 255))
        self.screen.blit(name_surf, (su(tip_x + pad), su(tip_y + 30)))

        y = tip_y + 78
        pygame.draw.line(self.screen, (70, 70, 78),
                         (su(tip_x + pad), su(y)), (su(tip_x + tip_w - pad), su(y)), 1)
        y += 8
        desc_surf = f_body.render(desc, True, (200, 200, 210))
        self.screen.blit(desc_surf, (su(tip_x + pad), su(y)))

    def _render_outfit_tooltip(self, item_id: str, outfit: dict, modal_right_x: int) -> None:
        """Stage 40 — render a beautiful tooltip for an outfit (costume).

        Stage 151 — координаты дизайн-пространства, отрисовка через _su().
        Stage 165 — формат по образцу пользователя: без слова «Костюм»,
        без строк «Тип/Рост/BMV: С…» и без подсказки о неснимаемости:

            Ичиго (Куросаки) +0            [иконка]
            Треб. уровень                1
            ────────────────────────────
            Сила                        10
            Ловкость                    15
            Выносливость                 8
            ────────────────────────────
            Каждые 30 силы повышают атаку
            на 1% и блок на 1 очко
            ...

        Статы показываются С УЧЁТОМ плюса (+10%/ступень, округление вверх —
        как в бою): у +1 Ичиго будет 11/17/9 вместо базовых 10/15/8.
        Треб. уровень растёт от плюса (outfit_synth_required_level), мин. 1.
        Текст порогов BMV — уменьшенным шрифтом (11) и с переносом строк,
        чтобы влезал в окно и не перекрывал иконку/статы.
        """
        from pockie_rpg.config import (
            COSTUME_QUALITY_RGB,
            outfit_synth_required_level,
            outfit_synth_stat_multiplier,
        )
        # Stage 209 — цвет рамки/заголовка по качеству костюма (серые/
        # синие/фиолетовые/оранжевые); нет качества — прежний фиолетовый.
        quality_rgb = COSTUME_QUALITY_RGB.get(outfit.get("quality", ""),
                                              (180, 100, 220))

        su = self._su
        plus = 0
        if hasattr(self, "player"):
            plus = self.player._outfit_plus_of(item_id, self.player)
        mult = outfit_synth_stat_multiplier(plus)
        base = outfit.get("base_stats", {})
        bmv = outfit.get("bmv") or outfit.get("bmv_price") or {}

        # --- шрифты (тултип: тело 13, пороги BMV 11 — «немного меньше») ---
        f_title = self._su_font(16, bold=True)
        f_body = self._su_font(13)
        f_small = self._su_font(11)

        # --- заголовок: имя БЕЗ слова «Костюм» + плюс ---
        name = str(outfit.get("name", "???"))
        if name.startswith("Костюм "):
            name = name[len("Костюм "):]
        title_text = f"{name} +{plus}"

        req_level = outfit_synth_required_level(plus)

        # --- статы с учётом плюса (округление половина вверх, как в бою) ---
        stat_rows: list[tuple[str, str]] = []
        for stat_key, label in (("strength", "Сила"),
                                ("agility", "Ловкость"),
                                ("stamina", "Выносливость")):
            val = int(base.get(stat_key, 0) * mult + 0.5)
            stat_rows.append((label, str(val)))

        # --- строки порогов BMV с переносом под ширину тултипа ---
        bmv_templates = (
            ("strength", "силы", "повышают атаку на 1% и блок на 1 очко"),
            ("agility", "ловкости", "повышают скорость на 1% и уклонение на 1 очко"),
            ("stamina", "выносливости", "повышают здоровье и чакру на 1%"),
        )
        content_w_px = su(276)  # tip_w 300 − поля 24
        bmv_wrapped: list[str] = []
        for key, word, effect in bmv_templates:
            line = f"Каждые {int(bmv.get(key, 20))} {word} {effect}"
            words = line.split()
            cur = ""
            for w in words:
                cand = f"{cur} {w}" if cur else w
                if f_small.size(cand)[0] <= content_w_px or not cur:
                    cur = cand
                else:
                    bmv_wrapped.append(cur)
                    cur = w
            if cur:
                bmv_wrapped.append(cur)

        # --- геометрия (дизайн-пиксели; иконка 56×56 в правом верхнем углу) ---
        # Stage 165 — ширина 300: заголовок «Ичиго (Куросаки) +0» с плюсом
        # не обрезается (при 264 «+0» срезался в «…»).
        tip_w = 300
        sep1_y = 52
        stats_y = 64          # ниже иконки (иконка 10..66)
        stats_step = 17
        sep2_y = stats_y + len(stat_rows) * stats_step + 8   # 64+51+8 = 123
        bmv_y = sep2_y + 8
        tip_h = bmv_y + len(bmv_wrapped) * 14 + 10

        tip_x = modal_right_x + 16
        tip_y = (SCREEN_HEIGHT - tip_h) // 2
        if tip_x + tip_w > SCREEN_WIDTH:
            tip_x = modal_right_x - tip_w - 16

        tip_rect = pygame.Rect(su(tip_x), su(tip_y), su(tip_w), su(tip_h))
        pygame.draw.rect(self.screen, (15, 15, 18), tip_rect, border_radius=8)
        pygame.draw.rect(self.screen, quality_rgb, tip_rect, 2, border_radius=8)
        pygame.draw.rect(self.screen, quality_rgb,
                         pygame.Rect(su(tip_x), su(tip_y),
                                     su(tip_w), su(4)), border_radius=2)

        # --- ИКОНКА костюма (56×56, правый верхний угол) ---
        icon_zone = pygame.Rect(su(tip_x + tip_w - 68), su(tip_y + 10),
                                su(56), su(56))
        icon_plate = pygame.Surface((su(60), su(60)), pygame.SRCALPHA)
        icon_plate.fill((20, 20, 24, 230))
        self.screen.blit(icon_plate, (icon_zone.x - su(2), icon_zone.y - su(2)))
        pygame.draw.rect(self.screen, quality_rgb, icon_zone, 1, border_radius=4)
        self._blit_gear_icon(outfit, icon_zone)

        # --- заголовок (обрезается до текстовой колонки, левее иконки) ---
        # Stage 209 — заголовок в цвете качества костюма.
        title_max_w = su(tip_w - 88)
        t_surf = f_title.render(title_text, True, quality_rgb)
        while t_surf.get_width() > title_max_w and len(title_text) > 3:
            title_text = title_text[:-1]
            t_surf = f_title.render(title_text + "…", True, quality_rgb)
        self.screen.blit(t_surf, (su(tip_x + 12), su(tip_y + 10)))

        # --- «Треб. уровень» + тир качества (справа, в цвете качества) ---
        from pockie_rpg.config import COSTUME_QUALITY_RU
        req_y = tip_y + 32
        req_lbl = f_body.render("Треб. уровень", True, (160, 160, 170))
        req_val = f_body.render(str(req_level), True, (255, 255, 255))
        self.screen.blit(req_lbl, (su(tip_x + 12), su(req_y)))
        self.screen.blit(req_val, (su(tip_x + tip_w - 78) - req_val.get_width(),
                                   su(req_y)))
        qual_lbl = f_small.render(
            COSTUME_QUALITY_RU.get(outfit.get("quality", ""), ""),
            True, quality_rgb)
        self.screen.blit(qual_lbl,
                         (su(tip_x + 12) + req_lbl.get_width() + su(10),
                          su(req_y + 2)))

        # --- разделитель 1 (не заходит под иконку) ---
        pygame.draw.line(self.screen, (63, 63, 70),
                         (su(tip_x + 8), su(tip_y + sep1_y)),
                         (su(tip_x + tip_w - 78), su(tip_y + sep1_y)), 1)

        # --- статы: метка слева, значение справа (после иконки) ---
        y = tip_y + stats_y
        for label, val_text in stat_rows:
            lbl_surf = f_body.render(label, True, (212, 212, 216))
            val_surf = f_body.render(val_text, True, (255, 255, 255))
            self.screen.blit(lbl_surf, (su(tip_x + 12), su(y)))
            self.screen.blit(val_surf,
                             (su(tip_x + tip_w - 12) - val_surf.get_width(), su(y)))
            y += stats_step

        # --- разделитель 2 ---
        pygame.draw.line(self.screen, (63, 63, 70),
                         (su(tip_x + 8), su(tip_y + sep2_y)),
                         (su(tip_x + tip_w - 8), su(tip_y + sep2_y)), 1)

        # --- пороги BMV (шрифт 11, серый, с переносом строк) ---
        y = tip_y + bmv_y
        for line in bmv_wrapped:
            line_surf = f_small.render(line, True, (150, 150, 158))
            self.screen.blit(line_surf, (su(tip_x + 12), su(y)))
            y += 14
