"""ForgeRendererMixin — Кузница modal (enchant + gems + synthesis tabs).

Extracted verbatim from render_map.py (Stage 89 refactor-96a). The methods
here are copies of the original implementations; PygameUI inherits from
this mixin so `self` is bound to the full UI instance.

Stage 152 — Hi-DPI: весь рендер пишется в ДИЗАЙН-координатах (1280×720), а
каждый Rect/blit/шрифт проходит через `self._su()` / `self._su_font()`
(`ui/scaling.py`). Legacy-фаза: `_render_scale=1.0` → поведение идентично
доStage-152. Native-фаза (2К): `_render_scale=UI_SCALE` → рендер 1:1 в
физических пикселях. Кузница не хранит layout между кадрами — достаточно
ClickRect'ов, которые в нативной фазе помечаются `native=True` автоматически.
"""
from __future__ import annotations

import pygame

from pockie_rpg.config import MODAL_CONTENT_PADDING
from pockie_rpg.ui.animator import ClickRect

# Stage 152 — размеры шрифтов кузницы в ДИЗАЙН-пространстве (соответствуют
# прежним self.font_title / font_button / font_small из pygame_ui).
_F_TITLE = (28, True)
_F_BUTTON = (18, True)
_F_SMALL = (13, False)


class ForgeRendererMixin:
    """Renders the Forge (Кузница) modal with 3 tabs: enchant, gems, synthesis."""

    def _f_title(self) -> pygame.font.Font:
        return self._su_font(*_F_TITLE)

    def _f_button(self) -> pygame.font.Font:
        return self._su_font(*_F_BUTTON)

    def _f_small(self) -> pygame.font.Font:
        return self._su_font(*_F_SMALL)

    def _render_forge_modal(self) -> None:
        """Stage 51 — render the Forge (Кузница) modal with 3 tabs.

        Tabs: 0=Заточка (enchant), 1=Камни (gems), 2=Синтез (synthesis).
        Stage 157 — перетаскиваемое окно (общий реестр, persist в сейве).
        """
        modal_w = 960
        modal_h = 580
        # Stage 157 — позиция из реестра окон (persist в сейве).
        modal_x, modal_y = self._window_pos("forge", modal_w, modal_h)

        # Backdrop (dark overlay over the MAP). Stage 152 — в нативной фазе
        # затемняем всю поверхность монитора, а не буфер 1280×720.
        # Stage 168 (аудит 5.2) — шейд из кэша по размеру (была аллокация/кадр).
        shade = self._static_surface(
            "forge_shade", self.screen.get_size(), lambda s: s.fill((0, 0, 0, 140)),
        )
        self.screen.blit(shade, (0, 0))

        # Modal panel.
        modal_rect = self._su_rect(modal_x, modal_y, modal_w, modal_h)
        pygame.draw.rect(self.screen, (20, 20, 24), modal_rect, border_radius=10)

        pygame.draw.rect(self.screen, (234, 179, 8),
                         self._su_rect(modal_x, modal_y, modal_w, 6), border_radius=3)

        # Stage 157/158 — общая шапка: drag + persist + ВЫНОСНОЙ крестик.
        # Заголовок слева, золото справа — всё в зоне шапки.
        self._render_window_titlebar(
            "forge", modal_rect, "Кузница",
            (234, 179, 8), True,
            right_text=f"Золото: {self.player.gold}",
            open_attr="_forge_modal_open",
            on_close=self._close_forge_modal,
        )

        # Stage 51 — tab buttons (Заточка / Камни / Синтез).
        tab_names = ["Заточка", "Камни", "Синтез"]
        tab_w = 110
        tab_h = 32
        tab_gap = 6
        tabs_total_w = 3 * tab_w + 2 * tab_gap
        tab_x0 = modal_x + (modal_w - tabs_total_w) // 2
        tab_y = modal_y + 50
        for i, name in enumerate(tab_names):
            tx = tab_x0 + i * (tab_w + tab_gap)
            tab_rect = self._su_rect(tx, tab_y, tab_w, tab_h)
            is_active = (self._forge_active_tab == i)
            hover = tab_rect.collidepoint(self._mouse_pos)
            if is_active:
                bg = (234, 179, 8)
                fg = (20, 20, 20)
            elif hover:
                bg = (60, 50, 10)
                fg = (255, 255, 255)
            else:
                bg = (40, 40, 45)
                fg = (180, 180, 185)
            pygame.draw.rect(self.screen, bg, tab_rect, border_radius=6)
            pygame.draw.rect(self.screen, (234, 179, 8) if is_active else (80, 80, 85),
                             tab_rect, self._su(2) if is_active else self._su(1), border_radius=6)
            tab_surf = self._f_button().render(name, True, fg)
            tab_rect_center = tab_surf.get_rect(center=tab_rect.center)
            self.screen.blit(tab_surf, tab_rect_center.topleft)
            _tab_idx = i
            self._click_rects.append(ClickRect(
                tag=f"forge_tab_{i}",
                rect=tab_rect,
                on_click=lambda t=_tab_idx: self._set_forge_tab(t),
            ))

        # Stage 158 — внутренняя close-кнопка УДАЛЁНА (выносной крестик
        # рисует шапка справа от окна).

        # Content area (below tabs).
        content_y = tab_y + tab_h + 10
        content_h = modal_y + modal_h - content_y - 10
        # Clip drawing to content area via a sub-surface rect (simple approach: just draw within bounds).
        if self._forge_active_tab == 0:
            self._render_forge_enchant_tab(modal_x, content_y, modal_w, content_h)
        elif self._forge_active_tab == 1:
            self._render_forge_gems_tab(modal_x, content_y, modal_w, content_h)
        elif self._forge_active_tab == 2:
            self._render_forge_synthesis_tab(modal_x, content_y, modal_w, content_h)

    def _render_forge_enchant_tab(self, modal_x: int, content_y: int, modal_w: int, content_h: int) -> None:
        """Stage 51/115 — forge tab 0: enchant (заточка).

        Stage 115 — now uses player.get_item_definition() instead of
        get_equipment() so generated items (gen_w_*) are visible and
        enchantable. Also passes player to get_item_stats_with_enchant().
        """
        from pockie_rpg.config import MAX_ENCHANT
        from pockie_rpg.data.item_db import (
            get_enchant_cost,
            get_item_stats_with_enchant,
        )
        subtitle = self._f_small().render(
            f"Заточка усиливает статы предмета. Максимум: +{MAX_ENCHANT}", True, (180, 180, 200)
        )
        self.screen.blit(subtitle, (self._su(modal_x + MODAL_CONTENT_PADDING),
                                    self._su(content_y + 4)))

        slots_order = ["weapon", "head", "body", "hands", "belt", "boots", "accessory"]
        slot_display = {
            "weapon": "Оружие", "head": "Голова", "body": "Броня",
            "hands": "Перчатки", "belt": "Пояс", "boots": "Обувь",
            "accessory": "Аксессуар",
        }
        card_w = 200
        card_h = 200
        card_gap = 10
        cards_per_row = 4
        total_w = cards_per_row * card_w + (cards_per_row - 1) * card_gap
        start_x = modal_x + (modal_w - total_w) // 2
        start_y = content_y + 28

        for i, slot in enumerate(slots_order):
            row = i // cards_per_row
            col = i % cards_per_row
            cx = start_x + col * (card_w + card_gap)
            cy = start_y + row * (card_h + card_gap)
            item_id = self.player.equipped_gear.get(slot)
            # Stage 116 — enchant level per-item-id (not per-slot).
            enchant_lvl = self.player.gear_enchants.get(item_id, 0) if item_id and hasattr(self.player, "gear_enchants") else 0

            card_rect = self._su_rect(cx, cy, card_w, card_h)
            pygame.draw.rect(self.screen, (30, 30, 35), card_rect, border_radius=8)
            border_col = (234, 179, 8) if enchant_lvl > 0 else (60, 60, 65)
            pygame.draw.rect(self.screen, border_col, card_rect, self._su(2), border_radius=8)

            # Stage 87 — equipment icon (56×56) in top-RIGHT of the card.
            # Slot label + item name stay on the left (original layout). The
            # +N enchant number renders as a gold badge overlay in the top-right
            # corner of the icon. Stats list + upgrade button keep their
            # original positions — all fits inside the 200×200 card.
            icon_size = 56
            icon_rect = self._su_rect(cx + card_w - icon_size - 12, cy + 8, icon_size, icon_size)
            pygame.draw.rect(self.screen, (20, 20, 24), icon_rect, border_radius=6)
            pygame.draw.rect(self.screen, (63, 63, 70), icon_rect, self._su(1), border_radius=6)

            slot_lbl = self._f_small().render(slot_display.get(slot, slot).upper(), True, (234, 179, 8))
            self.screen.blit(slot_lbl, (self._su(cx + 10), self._su(cy + 8)))

            if item_id is None:
                # Empty slot — show faded slot letter inside icon_rect.
                empty_letter = slot_display.get(slot, "?")[0]
                empty_font = self._f_title().render(empty_letter, True, (82, 82, 91))
                empty_rect = empty_font.get_rect(center=icon_rect.center)
                self.screen.blit(empty_font, empty_rect.topleft)
                empty_surf = self._f_small().render("(пусто)", True, (113, 113, 122))
                self.screen.blit(empty_surf, (self._su(cx + 10), self._su(cy + 28)))
                # Stats section is empty; jump straight to upgrade button.
            else:
                # Stage 115 — use get_item_definition for generated items.
                item = self.player.get_item_definition(item_id)
                if item is not None:
                    # Real icon via _blit_gear_icon (handles scaling + fallback).
                    self._blit_gear_icon(item, icon_rect)
                    name_surf = self._f_small().render(item["name"], True, (255, 255, 255))
                    # Stage 87 — truncate name if it would overlap the icon.
                    max_name_w = icon_rect.x - self._su(cx + 10) - self._su(6)
                    if name_surf.get_width() > max_name_w and max_name_w > self._su(20):
                        ell = self._f_small().render("…", True, (255, 255, 255))
                        crop_w = max_name_w - ell.get_width()
                        if crop_w > self._su(10):
                            sub = name_surf.subsurface((0, 0, crop_w, name_surf.get_height()))
                            combined = pygame.Surface((max_name_w, name_surf.get_height()), pygame.SRCALPHA)
                            combined.blit(sub, (0, 0))
                            combined.blit(ell, (crop_w, 0))
                            name_surf = combined
                    self.screen.blit(name_surf, (self._su(cx + 10), self._su(cy + 28)))

                    # Stage 117 — +N badge BELOW the icon (was on top, overlapping it).
                    ench_color = (234, 179, 8) if enchant_lvl >= 10 else (80, 220, 100) if enchant_lvl > 0 else (113, 113, 122)
                    ench_text = f"+{enchant_lvl}" if enchant_lvl > 0 else "—"
                    ench_surf = self._f_small().render(ench_text, True, ench_color)
                    # Pill positioned BELOW the icon, not overlapping it.
                    pill_w = ench_surf.get_width() + self._su(8)
                    pill_h = ench_surf.get_height() + self._su(2)
                    pill_x = icon_rect.centerx - pill_w // 2
                    pill_y = icon_rect.bottom + self._su(4)
                    pill_rect = pygame.Rect(pill_x, pill_y, pill_w, pill_h)
                    pygame.draw.rect(self.screen, (20, 20, 24), pill_rect, border_radius=6)
                    pygame.draw.rect(self.screen, ench_color, pill_rect, self._su(1), border_radius=6)
                    self.screen.blit(ench_surf, ench_surf.get_rect(center=pill_rect.center))

                    stats = get_item_stats_with_enchant(item_id, enchant_lvl, self.player)
                    # Stage 116 — only show MAIN stats in forge (not secondary).
                    from pockie_rpg.config import SLOT_MAIN_STATS
                    main_keys = SLOT_MAIN_STATS.get(item.get("slot", ""), ())
                    from pockie_rpg.config import STAT_LABEL_RU as stat_label_map
                    stat_y = cy + 52
                    # Stage 119 — show "current → next (+delta)" preview when item
                    # is enchantable (i.e., enchant_lvl < MAX_ENCHANT).
                    # Compute next-level stats once per item card.
                    show_preview = (item_id is not None and enchant_lvl < MAX_ENCHANT)
                    next_stats = None
                    if show_preview:
                        from pockie_rpg.data.item_db import get_item_stats_with_enchant as _gise
                        next_stats = _gise(item_id, enchant_lvl + 1, self.player)
                    for stat_key, val in stats.items():
                        # Stage 116 — skip secondary stats in forge display.
                        if main_keys and stat_key not in main_keys:
                            continue
                        label = stat_label_map.get(stat_key, stat_key)
                        # Stage 119 — diff preview: "X → Y (+Z)".
                        if show_preview and next_stats and stat_key in next_stats:
                            next_val = next_stats[stat_key]
                            delta = next_val - val
                            if delta > 0:
                                line = f"+{val} → +{next_val} (+{delta}) {label}"
                            else:
                                line = f"+{val} {label}"
                            s_color = (80, 220, 100) if enchant_lvl == 0 else (234, 179, 8)
                            s_surf = self._f_small().render(line, True, s_color)
                            # Render delta in a brighter color overlay (yellow accent).
                            self.screen.blit(s_surf, (self._su(cx + 10), self._su(stat_y)))
                            stat_y += 16
                        else:
                            line = f"+{val} {label}"
                            s_color = (80, 220, 100) if enchant_lvl == 0 else (234, 179, 8)
                            s_surf = self._f_small().render(line, True, s_color)
                            self.screen.blit(s_surf, (self._su(cx + 10), self._su(stat_y)))
                            stat_y += 16

            btn_w = card_w - 20
            btn_h = 30
            btn_x = cx + 10
            btn_y = cy + card_h - btn_h - 10
            btn_rect = self._su_rect(btn_x, btn_y, btn_w, btn_h)
            # Stage 116 — disable button when slot is empty.
            if item_id is None:
                btn_bg = (40, 40, 45)
                btn_text_col = (113, 113, 122)
                btn_label = "(пусто)"
            elif enchant_lvl >= MAX_ENCHANT:
                btn_bg = (50, 50, 55)
                btn_text_col = (150, 150, 155)
                btn_label = "МАКС"
            else:
                cost = get_enchant_cost(enchant_lvl)
                can_afford = self.player.gold >= cost
                hover = btn_rect.collidepoint(self._mouse_pos)
                if not can_afford:
                    btn_bg = (50, 30, 30)
                    btn_text_col = (200, 100, 100)
                elif hover:
                    btn_bg = (234, 179, 8)
                    btn_text_col = (20, 20, 20)
                else:
                    btn_bg = (180, 83, 9)
                    btn_text_col = (255, 255, 255)
                btn_label = f"Улучшить ({cost} зол.)"
            pygame.draw.rect(self.screen, btn_bg, btn_rect, border_radius=6)
            pygame.draw.rect(self.screen, (255, 255, 255), btn_rect, self._su(1), border_radius=6)
            btn_text_surf = self._f_small().render(btn_label, True, btn_text_col)
            btn_text_rect = btn_text_surf.get_rect(center=btn_rect.center)
            self.screen.blit(btn_text_surf, btn_text_rect)

            # Stage 116 — only register click handler when item is equipped and enchantable.
            if item_id is not None and enchant_lvl < MAX_ENCHANT:
                _slot = slot
                self._click_rects.append(ClickRect(
                    tag=f"forge_upgrade_{slot}",
                    rect=btn_rect,
                    on_click=lambda s=_slot: self._upgrade_gear_item(s),
                ))

    def _render_forge_gems_tab(self, modal_x: int, content_y: int, modal_w: int, content_h: int) -> None:
        """Stage 55 — forge tab 1: Камни (gems) with real icon grid + scroll.

        Left panel: gear slot selector (7 slots) + 3 gem slots for the selected item.
        Right panel: gem inventory grid (icon slots with scroll) + upgrade button.
        """
        from pockie_rpg.config import GEM_ICON_DIR, MAX_GEM_LEVEL, MAX_GEM_SLOTS_PER_ITEM
        from pockie_rpg.data.item_db import (
            get_equipment,
            get_gem,
            get_gem_icon_filename,
            get_gem_stat_bonus,
            get_gem_upgrade_chance,
            get_gem_upgrade_cost,
        )

        subtitle = self._f_small().render(
            "Камни: кликни камень, затем слот. Колесо мыши — прокрутка.", True, (180, 180, 200)
        )
        self.screen.blit(subtitle, (self._su(modal_x + MODAL_CONTENT_PADDING),
                                    self._su(content_y + 4)))

        # === Left panel: gear slots ===
        left_w = 360
        left_x = modal_x + MODAL_CONTENT_PADDING
        left_y = content_y + 28
        pygame.draw.rect(self.screen, (28, 28, 32),
                         self._su_rect(left_x, left_y, left_w, content_h - 36), border_radius=8)
        title = self._f_button().render("Снаряжение", True, (234, 179, 8))
        self.screen.blit(title, (self._su(left_x + 12), self._su(left_y + 8)))

        slots_order = ["weapon", "head", "body", "hands", "belt", "boots", "accessory"]
        slot_display = {
            "weapon": "Оружие", "head": "Голова", "body": "Броня",
            "hands": "Перчатки", "belt": "Пояс", "boots": "Обувь",
            "accessory": "Аксессуар",
        }
        row_h = 36
        for i, slot in enumerate(slots_order):
            ry = left_y + 36 + i * row_h
            sel_rect = self._su_rect(left_x + 8, ry, left_w - 16, row_h - 4)
            is_selected = (self._forge_selected_slot == slot)
            hover = sel_rect.collidepoint(self._mouse_pos)
            if is_selected:
                bg = (60, 50, 10)
            elif hover:
                bg = (50, 50, 55)
            else:
                bg = (40, 40, 45)
            pygame.draw.rect(self.screen, bg, sel_rect, border_radius=4)
            item_id = self.player.equipped_gear.get(slot)
            label = slot_display.get(slot, slot)
            # Stage 87 — equipment mini-icon (28×28) on the left of the row.
            mini_icon_size = self._su(28)
            mini_icon_rect = pygame.Rect(
                sel_rect.x + self._su(4),
                sel_rect.y + (sel_rect.h - mini_icon_size) // 2,
                mini_icon_size, mini_icon_size,
            )
            pygame.draw.rect(self.screen, (20, 20, 24), mini_icon_rect, border_radius=4)
            pygame.draw.rect(self.screen, (63, 63, 70) if not is_selected else (234, 179, 8),
                             mini_icon_rect, self._su(1), border_radius=4)
            item_obj = get_equipment(item_id) if item_id else None
            if item_obj is not None:
                self._blit_gear_icon(item_obj, mini_icon_rect)
            else:
                # Empty slot — faded slot letter circle.
                letter = label[0] if label else "?"
                letter_surf = self._f_small().render(letter, True, (82, 82, 91))
                self.screen.blit(letter_surf, letter_surf.get_rect(center=mini_icon_rect.center))
            if item_obj is not None:
                label = f"{label}: {item_obj['name']}"
            else:
                label = f"{label}: (пусто)"
            lbl_surf = self._f_small().render(label, True, (255, 255, 255) if is_selected else (200, 200, 205))
            # Truncate label if it would overflow the row width.
            max_lbl_w = sel_rect.w - mini_icon_size - self._su(16)
            if lbl_surf.get_width() > max_lbl_w:
                # Crop with ellipsis "…".
                ell = self._f_small().render("…", True, (255, 255, 255) if is_selected else (200, 200, 205))
                crop_w = max_lbl_w - ell.get_width()
                if crop_w > self._su(10):
                    lbl_surf = lbl_surf.subsurface((0, 0, crop_w, lbl_surf.get_height()))
                    # Combine via blit on a new surface.
                    combined = pygame.Surface((max_lbl_w, lbl_surf.get_height()), pygame.SRCALPHA)
                    combined.blit(lbl_surf, (0, 0))
                    combined.blit(ell, (crop_w, 0))
                    lbl_surf = combined
            self.screen.blit(lbl_surf, (sel_rect.x + mini_icon_size + self._su(8),
                                        sel_rect.y + (sel_rect.h - lbl_surf.get_height()) // 2))
            _slot = slot
            self._click_rects.append(ClickRect(
                tag=f"forge_gem_slot_{slot}",
                rect=sel_rect,
                on_click=lambda s=_slot: self._forge_select_gear_slot(s),
            ))

        # === Gem slots for the selected gear item (3 slots, with real icons) ===
        gem_slot_y = left_y + 36 + 7 * row_h + 12
        gem_slot_title = self._f_small().render(f"Слоты камней ({slot_display.get(self._forge_selected_slot, '')}):", True, (234, 179, 8))
        self.screen.blit(gem_slot_title, (self._su(left_x + 12), self._su(gem_slot_y)))
        gem_slot_size = 56
        gem_slot_gap = 8
        for i in range(MAX_GEM_SLOTS_PER_ITEM):
            gx = left_x + 12 + i * (gem_slot_size + gem_slot_gap)
            gy = gem_slot_y + 22
            gs_rect = self._su_rect(gx, gy, gem_slot_size, gem_slot_size)
            gem_id = self.player.gear_gem_slots.get(self._forge_selected_slot, [None, None, None])[i] if self._forge_selected_slot else None
            gem_inst = self.player.get_gem_instance(gem_id) if gem_id else None
            if gem_inst:
                # Load real gem icon.
                icon_file = get_gem_icon_filename(gem_inst["type"], gem_inst["level"])
                icon_path = str(GEM_ICON_DIR / icon_file)
                self._draw_gem_icon(gs_rect, icon_path, gem_inst["level"])
                _si = i
                _slot = self._forge_selected_slot
                self._click_rects.append(ClickRect(
                    tag=f"forge_unsocket_{i}",
                    rect=gs_rect,
                    on_click=lambda s=_slot, k=_si: self._forge_unsocket_gem(s, k),
                ))
            else:
                pygame.draw.rect(self.screen, (35, 35, 40), gs_rect, border_radius=6)
                border = (234, 179, 8) if self._forge_selected_gem else (80, 80, 85)
                pygame.draw.rect(self.screen, border, gs_rect, self._su(1), border_radius=6)
                plus_surf = self._f_button().render("+", True, (120, 120, 125))
                self.screen.blit(plus_surf, plus_surf.get_rect(center=gs_rect.center))
                if self._forge_selected_gem is not None:
                    _si = i
                    self._click_rects.append(ClickRect(
                        tag=f"forge_socket_{i}",
                        rect=gs_rect,
                        on_click=lambda k=_si: self._forge_socket_selected_gem(k),
                    ))

        # === Right panel: gem inventory grid (icon slots with scroll) ===
        right_w = modal_w - left_w - 48
        right_x = left_x + left_w + 16
        right_y = left_y
        panel_h = content_h - 36
        pygame.draw.rect(self.screen, (28, 28, 32),
                         self._su_rect(right_x, right_y, right_w, panel_h), border_radius=8)
        inv_title = self._f_button().render("Камни в инвентаре", True, (234, 179, 8))
        self.screen.blit(inv_title, (self._su(right_x + 12), self._su(right_y + 8)))

        # Stage 58 — grid: 13 columns of 36px icons, sorted by type+level.
        icon_size = 36
        icon_gap = 4
        grid_cols = 13
        grid_x0 = right_x + 8
        grid_y0 = right_y + 36
        grid_avail_h = panel_h - 36 - 56
        grid_rows = grid_avail_h // (icon_size + icon_gap)

        # Scroll offset.
        if not hasattr(self, "_forge_gem_scroll"):
            self._forge_gem_scroll = 0

        # Stage 57 — sort gems by type (alphabetical) then level (ascending).
        sorted_gems = sorted(self.player.gem_inventory, key=lambda g: (g["type"], g["level"]))

        total_items = len(sorted_gems)
        max_scroll = max(0, (total_items - 1) // (grid_cols * grid_rows)) if grid_rows > 0 else 0
        if self._forge_gem_scroll < 0:
            self._forge_gem_scroll = 0
        if self._forge_gem_scroll > max_scroll:
            self._forge_gem_scroll = max_scroll

        items_per_page = grid_cols * grid_rows
        start_idx = self._forge_gem_scroll * items_per_page
        visible_gems = sorted_gems[start_idx:start_idx + items_per_page]

        for idx, gem in enumerate(visible_gems):
            row = idx // grid_cols
            col = idx % grid_cols
            ix = grid_x0 + col * (icon_size + icon_gap)
            iy = grid_y0 + row * (icon_size + icon_gap)
            slot_rect = self._su_rect(ix, iy, icon_size, icon_size)
            is_selected = (self._forge_selected_gem == gem["id"])
            hover = slot_rect.collidepoint(self._mouse_pos)

            # Stage 56 — check if this gem is socketed (in any gear slot).
            is_socketed = False
            for s, slots_list in self.player.gear_gem_slots.items():
                if gem["id"] in slots_list:
                    is_socketed = True
                    break

            # Slot background.
            if is_selected:
                bg = (60, 50, 10)
            elif is_socketed:
                bg = (35, 30, 25)  # dimmer for socketed gems
            elif hover:
                bg = (50, 50, 55)
            else:
                bg = (40, 40, 45)
            pygame.draw.rect(self.screen, bg, slot_rect, border_radius=4)

            # Load real gem icon (dim if socketed).
            icon_file = get_gem_icon_filename(gem["type"], gem["level"])
            icon_path = str(GEM_ICON_DIR / icon_file)
            self._draw_gem_icon(slot_rect, icon_path, gem["level"], socketed=is_socketed)

            # Selection border.
            if is_selected:
                pygame.draw.rect(self.screen, (234, 179, 8), slot_rect, self._su(2), border_radius=4)
            elif hover and not is_socketed:
                pygame.draw.rect(self.screen, (120, 120, 130), slot_rect, self._su(1), border_radius=4)
            elif is_socketed:
                # Small indicator that gem is in use.
                pygame.draw.rect(self.screen, (80, 80, 60), slot_rect, self._su(1), border_radius=4)

            # Tooltip on hover.
            if hover:
                gem_def = get_gem(gem["type"])
                name = gem_def["name"] if gem_def else gem["type"]
                bonus = get_gem_stat_bonus(gem["type"], gem["level"])
                stat_lbl = gem_def["stat_label"] if gem_def else ""
                status = " [вставлен]" if is_socketed else ""
                tooltip_text = f"{name} +{gem['level']}\n+{bonus} {stat_lbl}{status}"
                self._render_gem_tooltip(ix, iy, tooltip_text)

            _gid = gem["id"]
            self._click_rects.append(ClickRect(
                tag=f"forge_gem_inv_{gem['id']}",
                rect=slot_rect,
                on_click=lambda g=_gid: self._forge_select_gem(g),
            ))

        # Scroll indicator.
        if total_items > items_per_page:
            scroll_text = f"{start_idx + 1}-{min(start_idx + items_per_page, total_items)} / {total_items}"
            scroll_surf = self._f_small().render(scroll_text, True, (150, 150, 155))
            self.screen.blit(scroll_surf, (self._su(right_x + right_w - 12) - scroll_surf.get_width(),
                                           self._su(right_y + 8)))
            # Scroll up/down buttons.
            up_rect = self._su_rect(right_x + right_w - 30, right_y + 36 + grid_avail_h + 4, 24, 20)
            dn_rect = self._su_rect(right_x + right_w - 60, right_y + 36 + grid_avail_h + 4, 24, 20)
            up_hover = up_rect.collidepoint(self._mouse_pos)
            dn_hover = dn_rect.collidepoint(self._mouse_pos)
            pygame.draw.rect(self.screen, (80, 80, 85) if up_hover else (50, 50, 55), up_rect, border_radius=4)
            pygame.draw.rect(self.screen, (80, 80, 85) if dn_hover else (50, 50, 55), dn_rect, border_radius=4)
            up_s = self._f_small().render("↑", True, (255, 255, 255))
            dn_s = self._f_small().render("↓", True, (255, 255, 255))
            self.screen.blit(up_s, up_s.get_rect(center=up_rect.center))
            self.screen.blit(dn_s, dn_s.get_rect(center=dn_rect.center))
            self._click_rects.append(ClickRect(tag="forge_gem_scroll_up", rect=up_rect, on_click=lambda: self._scroll_gems(-1)))
            self._click_rects.append(ClickRect(tag="forge_gem_scroll_dn", rect=dn_rect, on_click=lambda: self._scroll_gems(1)))

        # === Upgrade button for selected gem ===
        if self._forge_selected_gem is not None:
            gem = self.player.get_gem_instance(self._forge_selected_gem)
            if gem is not None:
                uy = right_y + panel_h - 76
                info = f"Выбран: {get_gem(gem['type'])['name'] if get_gem(gem['type']) else gem['type']} +{gem['level']}"
                info_surf = self._f_small().render(info, True, (255, 255, 255))
                self.screen.blit(info_surf, (self._su(right_x + 12), self._su(uy)))
                if gem["level"] >= MAX_GEM_LEVEL:
                    up_surf = self._f_small().render("МАКС УРОВЕНЬ", True, (150, 150, 155))
                    self.screen.blit(up_surf, (self._su(right_x + 12), self._su(uy + 22)))
                else:
                    cost = get_gem_upgrade_cost(gem["level"])
                    chance = get_gem_upgrade_chance(gem["level"])
                    can_afford = self.player.gold >= cost
                    btn_w = right_w - 24
                    btn_h = 36
                    btn_rect = self._su_rect(right_x + 12, uy + 22, btn_w, btn_h)
                    hover = btn_rect.collidepoint(self._mouse_pos)
                    if not can_afford:
                        bg = (50, 30, 30)
                        fg = (200, 100, 100)
                    elif hover:
                        bg = (234, 179, 8)
                        fg = (20, 20, 20)
                    else:
                        bg = (180, 83, 9)
                        fg = (255, 255, 255)
                    pygame.draw.rect(self.screen, bg, btn_rect, border_radius=6)
                    label = f"Улучшить ({cost} зол., {chance}%)"
                    lbl_surf = self._f_small().render(label, True, fg)
                    self.screen.blit(lbl_surf, lbl_surf.get_rect(center=btn_rect.center))
                    _gid = self._forge_selected_gem
                    self._click_rects.append(ClickRect(
                        tag="forge_upgrade_gem",
                        rect=btn_rect,
                        on_click=lambda g=_gid: self._forge_upgrade_gem(g),
                    ))

        # === Debug buttons: individual + spam ===
        dbg_y = right_y + panel_h - 34
        dbg_label = self._f_small().render("Тест:", True, (150, 150, 155))
        self.screen.blit(dbg_label, (self._su(right_x + 12), self._su(dbg_y)))
        dbg_x = right_x + 50
        for gtype in ["gem_red", "gem_blue", "gem_green", "gem_yellow", "gem_orange"]:
            gdef = get_gem(gtype)
            if gdef is None:
                continue
            swatch = self._su_rect(dbg_x, dbg_y, 24, 20)
            pygame.draw.rect(self.screen, gdef["color"], swatch, border_radius=3)
            hover = swatch.collidepoint(self._mouse_pos)
            if hover:
                pygame.draw.rect(self.screen, (255, 255, 255), swatch, self._su(2), border_radius=3)
            _gt = gtype
            self._click_rects.append(ClickRect(
                tag=f"forge_debug_add_{gtype}",
                rect=swatch,
                on_click=lambda g=_gt: self._forge_debug_add_gem(g),
            ))
            dbg_x += 30

        # Spam button.
        spam_rect = self._su_rect(right_x + right_w - 90, dbg_y, 80, 20)
        spam_hover = spam_rect.collidepoint(self._mouse_pos)
        pygame.draw.rect(self.screen, (234, 179, 8) if spam_hover else (180, 83, 9), spam_rect, border_radius=4)
        spam_text = self._f_small().render("+10 камней", True, (20, 20, 20) if spam_hover else (255, 255, 255))
        self.screen.blit(spam_text, spam_text.get_rect(center=spam_rect.center))
        self._click_rects.append(ClickRect(tag="forge_spam_gems", rect=spam_rect, on_click=self._forge_spam_gems))

    def _draw_gem_icon(self, rect: pygame.Rect, icon_path: str, level: int, socketed: bool = False) -> None:
        """Draw a gem icon (GIF) scaled to fit rect, with level badge.

        Stage 56 — uses rotozoom for better pixel-art scaling + LRU cache.
        If socketed=True, the icon is dimmed (50% alpha) to indicate it's in use.

        Stage 152 — Hi-DPI: `rect` приходит в НАТИВНЫХ координатах. Размер арта
        считается через `_su_icon_size` (кап апскейла ×1.3 в ДИЗАЙН-пространстве
        + без даунскейла при влезании 1:1 — семантика Stage 142/149), поэтому
        гемы 24px не мылятся. Ключ кэша включает масштаб рендера.
        """
        if not hasattr(self, "_gem_icon_cache"):
            self._gem_icon_cache = {}
        # Аудит 2026-09 — кап кэша: ключ включает rect.w/rect.h/масштаб, при
        # ресайзе окна ключи плодились без предела. 256 — с запасом на все
        # типы/уровни/размеры гемов; переполнение — полный reset (кэш
        # восстанавливается за 1 кадр, потери нет).
        if len(self._gem_icon_cache) > 256:
            self._gem_icon_cache.clear()
        s = getattr(self, "_render_scale", 1.0)
        cache_key = f"{icon_path}_{rect.w}_{rect.h}_{round(s, 2)}"
        if cache_key not in self._gem_icon_cache:
            try:
                raw = pygame.image.load(icon_path).convert_alpha()
                # Stage 152 — целевой размер по семантике инвентаря (pad=0:
                # гем занимает слот целиком, как до Stage 152).
                tw, th = self._su_icon_size(
                    raw.get_width(), raw.get_height(), rect, pad=0.0,
                )
                if (tw, th) != raw.get_size():
                    # Stage 56 — rotozoom gives best quality for pixel art upscaling.
                    src_size = raw.get_width()
                    if src_size > 0:
                        scaled = pygame.transform.rotozoom(raw, 0, tw / src_size)
                        if scaled.get_size() != (tw, th):
                            scaled = pygame.transform.scale(scaled, (tw, th))
                    else:
                        scaled = raw
                else:
                    scaled = raw
                self._gem_icon_cache[cache_key] = scaled
            except (pygame.error, FileNotFoundError):
                self._gem_icon_cache[cache_key] = None

        icon_surf = self._gem_icon_cache.get(cache_key)
        if icon_surf is not None:
            # Stage 152 — центрируем: арт может быть меньше слота (кап апскейла).
            pos = (
                rect.x + (rect.w - icon_surf.get_width()) // 2,
                rect.y + (rect.h - icon_surf.get_height()) // 2,
            )
            if socketed:
                # Dim the icon to indicate it's socketed (in use).
                dim = icon_surf.copy()
                dim.set_alpha(80)
                self.screen.blit(dim, pos)
            else:
                self.screen.blit(icon_surf, pos)
        else:
            # Fallback: colored square.
            pygame.draw.rect(self.screen, (100, 100, 200), rect, border_radius=4)

        # Level badge (top-right corner).
        lvl_bg = pygame.Rect(rect.right - self._su(16), rect.y, self._su(16), self._su(12))
        pygame.draw.rect(self.screen, (0, 0, 0), lvl_bg, border_radius=2)
        lvl_surf = self._f_small().render(f"{level}", True, (234, 179, 8))
        self.screen.blit(lvl_surf, lvl_surf.get_rect(center=lvl_bg.center))

    def _render_gem_tooltip(self, x: int, y: int, text: str) -> None:
        """Render a small tooltip box above the gem icon.

        Stage 152 — x/y приходят в ДИЗАЙН-координатах (как и раньше), геометрия
        и шрифт проходят через _su/_su_font.
        """
        lines = text.split("\n")
        font = self._f_small()
        line_h = self._su(16)
        tt_w = max(font.size(ln)[0] for ln in lines) + self._su(16)
        tt_h = len(lines) * line_h + self._su(8)
        tt_x = self._su(x)
        tt_y = self._su(y) - tt_h - self._su(4)
        if tt_y < 0:
            tt_y = self._su(y + 48 + 4)
        tt_rect = pygame.Rect(tt_x, tt_y, tt_w, tt_h)
        pygame.draw.rect(self.screen, (15, 15, 18), tt_rect, border_radius=6)
        pygame.draw.rect(self.screen, (234, 179, 8), tt_rect, self._su(1), border_radius=6)
        for i, line in enumerate(lines):
            ls = font.render(line, True, (255, 255, 255))
            self.screen.blit(ls, (tt_x + self._su(8), tt_y + self._su(4) + i * line_h))

    def _render_forge_synthesis_tab(self, modal_x: int, content_y: int, modal_w: int, content_h: int) -> None:
        """Stage 56 — forge tab 2: Синтез (synthesis) with real gem icons.

        Center: 2 input slots (A + B) + result preview (all with real icons).
        Bottom: gem inventory grid (icon slots, click to place into A or B).
        """
        from pockie_rpg.config import GEM_ICON_DIR, MAX_GEM_LEVEL
        from pockie_rpg.data.item_db import (
            get_gem,
            get_gem_icon_filename,
            get_gem_stat_bonus,
            get_synthesis_result_level,
        )

        subtitle = self._f_small().render(
            "Синтез: 2 камня одного типа и уровня → 1 камень уровня +1 (60% шанс).", True, (180, 180, 200)
        )
        self.screen.blit(subtitle, (self._su(modal_x + MODAL_CONTENT_PADDING),
                                    self._su(content_y + 4)))

        # Center synthesis area.
        center_y = content_y + 36
        slot_size = 80
        gap = 20
        total_w = 3 * slot_size + 2 * gap + 80
        start_x = modal_x + (modal_w - total_w) // 2

        # Slot A (with real icon).
        ax = start_x
        a_rect = self._su_rect(ax, center_y, slot_size, slot_size)
        self._draw_synthesis_slot(a_rect, self._forge_synthesis_a, "A")
        if self._forge_synthesis_a is not None:
            self._click_rects.append(ClickRect(tag="synth_clear_a", rect=a_rect, on_click=self._forge_synthesis_clear_a))

        # "+" label.
        plus_surf = self._f_title().render("+", True, (234, 179, 8))
        plus_x = self._su(ax + slot_size) + (self._su(gap) - plus_surf.get_width()) // 2
        self.screen.blit(plus_surf, (plus_x,
                                     self._su(center_y) + (self._su(slot_size) - plus_surf.get_height()) // 2))

        # Slot B (with real icon).
        bx = ax + slot_size + gap
        b_rect = self._su_rect(bx, center_y, slot_size, slot_size)
        self._draw_synthesis_slot(b_rect, self._forge_synthesis_b, "B")
        if self._forge_synthesis_b is not None:
            self._click_rects.append(ClickRect(tag="synth_clear_b", rect=b_rect, on_click=self._forge_synthesis_clear_b))

        # "=" label.
        eq_surf = self._f_title().render("=", True, (234, 179, 8))
        eq_x = self._su(bx + slot_size) + (self._su(gap) - eq_surf.get_width()) // 2
        self.screen.blit(eq_surf, (eq_x,
                                   self._su(center_y) + (self._su(slot_size) - eq_surf.get_height()) // 2))

        # Result slot (preview with real icon).
        rx = bx + slot_size + gap
        r_rect = self._su_rect(rx, center_y, slot_size, slot_size)
        ga = self.player.get_gem_instance(self._forge_synthesis_a) if self._forge_synthesis_a else None
        gb = self.player.get_gem_instance(self._forge_synthesis_b) if self._forge_synthesis_b else None
        result_info = None
        if ga and gb and ga["type"] == gb["type"]:
            result_level = get_synthesis_result_level(ga["level"], gb["level"])
            if result_level is not None and result_level <= MAX_GEM_LEVEL:
                result_info = (ga["type"], result_level)
        if result_info:
            # Draw result with real icon.
            icon_file = get_gem_icon_filename(result_info[0], result_info[1])
            icon_path = str(GEM_ICON_DIR / icon_file)
            self._draw_gem_icon(r_rect, icon_path, result_info[1])
        else:
            pygame.draw.rect(self.screen, (35, 35, 40), r_rect, border_radius=8)
            q_surf = self._f_title().render("?", True, (113, 113, 122))
            self.screen.blit(q_surf, q_surf.get_rect(center=r_rect.center))

        # Synthesize button.
        synth_btn_y = center_y + slot_size + 20
        synth_btn_w = 220
        synth_btn_h = 40
        synth_btn_x = modal_x + (modal_w - synth_btn_w) // 2
        synth_btn_rect = self._su_rect(synth_btn_x, synth_btn_y, synth_btn_w, synth_btn_h)
        can_synth = (result_info is not None)
        hover = synth_btn_rect.collidepoint(self._mouse_pos)
        if not can_synth:
            bg = (50, 50, 55)
            fg = (150, 150, 155)
        elif hover:
            bg = (234, 179, 8)
            fg = (20, 20, 20)
        else:
            bg = (180, 83, 9)
            fg = (255, 255, 255)
        pygame.draw.rect(self.screen, bg, synth_btn_rect, border_radius=8)
        synth_label = self._f_button().render("Синтез (60%)", True, fg)
        self.screen.blit(synth_label, synth_label.get_rect(center=synth_btn_rect.center))
        if can_synth:
            self._click_rects.append(ClickRect(tag="synth_do", rect=synth_btn_rect, on_click=self._forge_do_synthesis))

        # Status text.
        status_y = synth_btn_y + synth_btn_h + 8
        if ga and gb and ga["type"] != gb["type"]:
            status = "Разные типы камней — нельзя синтезировать."
            status_col = (220, 100, 100)
        elif ga and gb and ga["level"] != gb["level"]:
            status = "Разные уровни — нельзя синтезировать."
            status_col = (220, 100, 100)
        elif ga and gb and result_info and result_info[1] > MAX_GEM_LEVEL:
            status = "Результат превысит максимум."
            status_col = (220, 100, 100)
        elif ga and gb and result_info:
            status = f"Готово: {get_gem(ga['type'])['name']} +{result_info[1]}"
            status_col = (80, 220, 100)
        else:
            status = "Выберите 2 камня одного типа и уровня."
            status_col = (180, 180, 200)
        status_surf = self._f_small().render(status, True, status_col)
        self.screen.blit(status_surf, status_surf.get_rect(
            center=(self._su(modal_x + modal_w // 2), self._su(status_y))))

        # === Bottom: gem inventory GRID (icon slots, click to place into A or B) ===
        inv_y = status_y + 24
        inv_title = self._f_small().render("Камни (кликните, чтобы добавить в слот):", True, (234, 179, 8))
        self.screen.blit(inv_title, (self._su(modal_x + MODAL_CONTENT_PADDING), self._su(inv_y)))

        # Stage 58 — grid layout for synthesis: 13 columns, sorted, scrollable.
        icon_size = 36
        icon_gap = 4
        grid_cols = 13
        grid_x0 = modal_x + MODAL_CONTENT_PADDING
        grid_y0 = inv_y + 22
        grid_avail_h = content_y + content_h - grid_y0 - 10
        grid_rows = grid_avail_h // (icon_size + icon_gap)

        # Scroll.
        if not hasattr(self, "_forge_synth_scroll"):
            self._forge_synth_scroll = 0

        # Stage 57 — sort gems by type then level.
        sorted_gems = sorted(self.player.gem_inventory, key=lambda g: (g["type"], g["level"]))

        total_items = len(sorted_gems)
        items_per_page = grid_cols * grid_rows
        max_scroll = max(0, (total_items - 1) // items_per_page) if items_per_page > 0 else 0
        if self._forge_synth_scroll < 0:
            self._forge_synth_scroll = 0
        if self._forge_synth_scroll > max_scroll:
            self._forge_synth_scroll = max_scroll
        start_idx = self._forge_synth_scroll * items_per_page
        visible_gems = sorted_gems[start_idx:start_idx + items_per_page]

        for idx, gem in enumerate(visible_gems):
            row = idx // grid_cols
            col = idx % grid_cols
            ix = grid_x0 + col * (icon_size + icon_gap)
            iy = grid_y0 + row * (icon_size + icon_gap)
            slot_rect = self._su_rect(ix, iy, icon_size, icon_size)
            in_use = (gem["id"] == self._forge_synthesis_a or gem["id"] == self._forge_synthesis_b)
            hover = slot_rect.collidepoint(self._mouse_pos)

            if in_use:
                bg = (60, 50, 10)
            elif hover:
                bg = (50, 50, 55)
            else:
                bg = (40, 40, 45)
            pygame.draw.rect(self.screen, bg, slot_rect, border_radius=4)

            icon_file = get_gem_icon_filename(gem["type"], gem["level"])
            icon_path = str(GEM_ICON_DIR / icon_file)
            self._draw_gem_icon(slot_rect, icon_path, gem["level"], socketed=in_use)

            if in_use:
                pygame.draw.rect(self.screen, (234, 179, 8), slot_rect, self._su(2), border_radius=4)
            elif hover:
                pygame.draw.rect(self.screen, (120, 120, 130), slot_rect, self._su(1), border_radius=4)

            if hover:
                gem_def = get_gem(gem["type"])
                name = gem_def["name"] if gem_def else gem["type"]
                bonus = get_gem_stat_bonus(gem["type"], gem["level"])
                stat_lbl = gem_def["stat_label"] if gem_def else ""
                status = " [выбран]" if in_use else ""
                tooltip_text = f"{name} +{gem['level']}\n+{bonus} {stat_lbl}{status}"
                self._render_gem_tooltip(ix, iy, tooltip_text)

            _gid = gem["id"]
            self._click_rects.append(ClickRect(
                tag=f"synth_gem_{gem['id']}",
                rect=slot_rect,
                on_click=lambda g=_gid: self._forge_select_gem(g),
            ))

    def _draw_synthesis_slot(self, rect: pygame.Rect, gem_id: str | None, label: str) -> None:
        """Stage 56 — draw a synthesis input slot with real gem icon.

        Stage 152 — `rect` приходит уже в нативных координатах (см. вызовы).
        """
        from pockie_rpg.config import GEM_ICON_DIR
        from pockie_rpg.data.item_db import get_gem_icon_filename
        if gem_id is not None:
            gem = self.player.get_gem_instance(gem_id)
            if gem is not None:
                # Draw with real icon.
                icon_file = get_gem_icon_filename(gem["type"], gem["level"])
                icon_path = str(GEM_ICON_DIR / icon_file)
                self._draw_gem_icon(rect, icon_path, gem["level"])
                return
        pygame.draw.rect(self.screen, (35, 35, 40), rect, border_radius=8)
        lbl_surf = self._f_title().render(label, True, (113, 113, 122))
        self.screen.blit(lbl_surf, lbl_surf.get_rect(center=rect.center))
