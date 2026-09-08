"""QuickBattleRendererMixin — quick battle selection modal + result modal.

Stage 96 — extracted from `render_map.py` (MapRendererMixin) as a focused
mixin so the parent module shrinks. The class has no `__init__`; it inherits
`self` (screen, fonts, asset_manager, target_mob_id, player, _quick_battle_*,
_click_rects, etc.) from PygameUI.

Stage 114 — result modal redesigned: text list replaced with graphical
Loot Grid (icon slots with rarity backgrounds + count badges).
"""
from __future__ import annotations

import os

import pygame

from pockie_rpg.config import RARITY_RGB, RARITY_SLOT_BG, SCREEN_HEIGHT, SCREEN_WIDTH
from pockie_rpg.ui.animator import ClickRect


class QuickBattleRendererMixin:
    """Renders the quick-battle selection modal (×10 / ×1 / animated) and result modal."""

    def _render_quick_battle_modal(self) -> None:
        """Render the quick battle selection modal (×10 / ×1)."""
        from pockie_rpg.game.state import ENEMY_MOBS
        enemy = ENEMY_MOBS.get(self.target_mob_id)
        if enemy is None:
            self._quick_battle_modal_open = False
            return

        # Stage 165 — подложки больше НЕТ (блюр давал «резкую вспышку»):
        # окно поверх НЕИЗМЕННОЙ живой сцены (как «Карта мира»/магазин).

        modal_w = 440
        modal_h = 300
        modal_x = (SCREEN_WIDTH - modal_w) // 2
        modal_y = (SCREEN_HEIGHT - modal_h) // 2

        pygame.draw.rect(self.screen, (24, 24, 27), (modal_x, modal_y, modal_w, modal_h), border_radius=12)
        pygame.draw.rect(self.screen, (234, 179, 8), (modal_x, modal_y, modal_w, 4), border_radius=2)

        title_surf = self.font_subtitle.render(f"Сражение: {enemy.name}", True, (234, 179, 8))
        self.screen.blit(title_surf, (modal_x + (modal_w - title_surf.get_width()) // 2, modal_y + 20))
        level_surf = self.font_small.render(f"Уровень {enemy.level}", True, (250, 204, 21))
        self.screen.blit(level_surf, (modal_x + (modal_w - level_surf.get_width()) // 2, modal_y + 50))

        # Stage 167 — карточки УМЕНЬШЕНЫ (112×138, было 130×160) и цвета
        # приглушены (пользователь: «не такие яркие»): тёмно-красный /
        # тёмно-синий / тёмно-зелёный вместо кричащих базовых.
        card_w = 112
        card_h = 138
        card_gap = 12
        cards_total_w = 3 * card_w + 2 * card_gap
        cards_x = modal_x + (modal_w - cards_total_w) // 2
        cards_y = modal_y + 84

        for i, (label, tag, color, count) in enumerate([
            ("×10 БОЙ", "quick_battle_x10", (140, 45, 45), 10),
            ("×1 БОЙ", "quick_battle_x1", (52, 90, 140), 1),
            ("БОЙ", "quick_battle_animated", (22, 110, 82), 0),
        ]):
            cx = cards_x + i * (card_w + card_gap)
            rect = pygame.Rect(cx, cards_y, card_w, card_h)
            hover = rect.collidepoint(self._mouse_pos)
            mob_defeated = self.target_mob_id in self.player.defeated_mobs
            is_locked = count > 0 and not mob_defeated
            if is_locked:
                bg = (40, 40, 40)
                border_col = (60, 60, 60)
            else:
                bg = tuple(min(255, c + 26) for c in color) if hover else color
                border_col = (208, 208, 214)
            pygame.draw.rect(self.screen, bg, rect, border_radius=10)
            pygame.draw.rect(self.screen, border_col, rect, 2, border_radius=10)
            # Аудит 2026-09 — SysFont (системный матчинг шрифта) каждый кадр
            # в цикле карточек → кэш ScalableRendererMixin._su_font.
            num_font = self._su_font(24, bold=True)
            parts = label.split()
            num_color = (150, 150, 150) if is_locked else (235, 235, 240)
            num_center = (cx + card_w // 2, cards_y + 44)
            if len(parts) > 1:
                num_surf = num_font.render(parts[0], True, num_color)
                self.screen.blit(num_surf, num_surf.get_rect(center=num_center).topleft)
            else:
                # Stage 167 — ИСПРАВЛЕНА «битая иконка» (серый прямоугольник-
                # тофу): глиф скрещенных мечей отсутствует в DejaVu/Arial.
                # Вместо шрифтового символа — треугольник-«плей» примитивами.
                tri = pygame.Surface((26, 26), pygame.SRCALPHA)
                pygame.draw.polygon(tri, num_color, [(5, 2), (23, 13), (5, 24)])
                self.screen.blit(tri, (num_center[0] - 13, num_center[1] - 13))
            if is_locked:
                lock_text = "Сначала победите"
                lock_surf = self.font_small.render(lock_text, True, (150, 150, 150))
                self.screen.blit(lock_surf, (cx + (card_w - lock_surf.get_width()) // 2, cards_y + 76))
                lock2 = self.font_small.render("в аним. бою", True, (150, 150, 150))
                self.screen.blit(lock2, (cx + (card_w - lock2.get_width()) // 2, cards_y + 92))
            else:
                if len(parts) > 1:
                    lbl_surf = self.font_body.render(parts[1], True, (235, 235, 240))
                else:
                    lbl_surf = self.font_body.render("Анимация", True, (235, 235, 240))
                lbl_rect = lbl_surf.get_rect(center=(cx + card_w // 2, cards_y + 76))
                self.screen.blit(lbl_surf, lbl_rect.topleft)
                mult = count if count > 0 else 1
                xp_text = f"XP: +{enemy.xp_reward * mult}"
                xp_surf = self.font_small.render(xp_text, True, (224, 188, 60))
                self.screen.blit(xp_surf, (cx + (card_w - xp_surf.get_width()) // 2, cards_y + 100))
                gold_text = f"Gold: +{enemy.gold_reward * mult}"
                gold_surf = self.font_small.render(gold_text, True, (224, 188, 60))
                self.screen.blit(gold_surf, (cx + (card_w - gold_surf.get_width()) // 2, cards_y + 118))

            if is_locked:
                continue
            if count == 0:
                def _start_animated(_mob_id: str = self.target_mob_id) -> None:
                    self._quick_battle_modal_open = False
                    self._enter_battle()
                self._click_rects.append(ClickRect(tag=tag, rect=rect, on_click=_start_animated))
            else:
                def _start_qb(_count: int = count) -> None:
                    self._run_quick_battle(_count)
                self._click_rects.append(ClickRect(tag=tag, rect=rect, on_click=_start_qb))

        close_w = 100
        close_h = 36
        close_x = modal_x + (modal_w - close_w) // 2
        close_y = modal_y + modal_h - close_h - 16
        close_rect = pygame.Rect(close_x, close_y, close_w, close_h)
        ch = close_rect.collidepoint(self._mouse_pos)
        pygame.draw.rect(self.screen, (127, 29, 29) if ch else (100, 20, 20), close_rect, border_radius=8)
        pygame.draw.rect(self.screen, (255, 255, 255), close_rect, 2, border_radius=8)
        close_surf = self.font_button.render("Отмена", True, (255, 255, 255))
        close_text_rect = close_surf.get_rect(center=close_rect.center)
        self.screen.blit(close_surf, close_text_rect.topleft)
        self._click_rects.append(ClickRect(tag="close_quick_battle", rect=close_rect, on_click=self._close_quick_battle_modal))

    # ------------------------------------------------------------------
    # Stage 114 — LOOT GRID RENDERING HELPERS
    # ------------------------------------------------------------------

    def _load_item_icon_surface(self, icon_filename: str, target_sz: int) -> pygame.Surface | None:
        """Load and cache an item icon scaled to target_sz × target_sz."""
        if not hasattr(self, "_loot_icon_cache"):
            self._loot_icon_cache: dict[str, pygame.Surface] = {}
        # Аудит 2026-09 — кап кэша (файлы лута конечны, но лимит страховочный).
        if len(self._loot_icon_cache) > 256:
            self._loot_icon_cache.clear()
        cache_key = f"{icon_filename}_{target_sz}"
        if cache_key in self._loot_icon_cache:
            return self._loot_icon_cache[cache_key]
        icon_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            "assets", "icons", "items", icon_filename
        )
        try:
            raw = pygame.image.load(icon_path).convert_alpha()
            iw, ih = raw.get_size()
            max_w = target_sz - 6
            max_h = target_sz - 6
            scale = min(max_w / iw, max_h / ih)
            new_w = max(1, int(iw * scale))
            new_h = max(1, int(ih * scale))
            scaled = pygame.transform.smoothscale(raw, (new_w, new_h))
            self._loot_icon_cache[cache_key] = scaled
            return scaled
        except Exception:
            return None

    def _load_gem_icon_surface(self, icon_path: str, target_sz: int) -> pygame.Surface | None:
        """Load and cache a gem icon scaled to target_sz × target_sz."""
        if not hasattr(self, "_loot_gem_cache"):
            self._loot_gem_cache: dict[str, pygame.Surface] = {}
        # Аудит 2026-09 — кап кэша.
        if len(self._loot_gem_cache) > 256:
            self._loot_gem_cache.clear()
        cache_key = f"{icon_path}_{target_sz}"
        if cache_key in self._loot_gem_cache:
            return self._loot_gem_cache[cache_key]
        try:
            raw = pygame.image.load(icon_path).convert_alpha()
            src_size = raw.get_width()
            if src_size > 0 and target_sz != src_size:
                scale = (target_sz - 6) / src_size
                scaled = pygame.transform.rotozoom(raw, 0, scale)
            else:
                scaled = raw
            self._loot_gem_cache[cache_key] = scaled
            return scaled
        except Exception:
            return None

    def _render_loot_slot(self, x: int, y: int, sz: int, icon_surf: pygame.Surface | None,
                          rarity: str = "", count: int = 1, icon_type: str = "item",
                          tooltip_text: str = "",
                          tooltip_lines: list | None = None) -> None:
        """Stage 117/118 — Render a single loot grid slot with rarity background + icon + count badge.

        Stage 117 — hover tooltip (single-line item name).
        Stage 118 — tooltip now supports BOTH formats:
            * `tooltip_text` (legacy str) — single-line simple tooltip (used for gems).
            * `tooltip_lines` (list[tuple[str, tuple[int,int,int]]]) — multiline rich tooltip
              for weapons/armor/boots. Each tuple is (text, color). When provided,
              takes precedence over `tooltip_text`. Lines render top-to-bottom.
              Header line (item name) uses the rarity color border. Stat lines use
              their own colors (green for main stats, blue for secondary).

        Stage 201 — x/y/sz приходят в ДИЗАЙН-координатах; ховер — по
        дизайн-ректу (мышь в дизайн-пространстве), отрисовка — ×_su.
        """
        rect = pygame.Rect(x, y, sz, sz)
        is_hover = rect.collidepoint(self._mouse_pos)
        draw_rect = self._su_rect(x, y, sz, sz)

        # Rarity background.
        bg_color = RARITY_SLOT_BG.get(rarity, (39, 39, 42))
        pygame.draw.rect(self.screen, bg_color, draw_rect, border_radius=self._su(6))
        border_color = RARITY_RGB.get(rarity, (82, 82, 91))
        # Stage 117 — hover highlight: brighter border.
        border_w = self._su(3) if is_hover else self._su(2)
        pygame.draw.rect(self.screen, border_color, draw_rect, border_w, border_radius=self._su(6))

        # Icon.
        if icon_surf is not None:
            iw, ih = icon_surf.get_size()
            self.screen.blit(
                icon_surf,
                (draw_rect.x + (draw_rect.w - iw) // 2,
                 draw_rect.y + (draw_rect.h - ih) // 2),
            )
        else:
            letter = "?"
            letter_surf = self._su_font(13).render(letter, True, (150, 150, 150))
            lr = letter_surf.get_rect(center=draw_rect.center)
            self.screen.blit(letter_surf, lr.topleft)

        # Count badge (bottom-right corner).
        if count > 1:
            badge_text = f"x{count}"
            badge_surf = self._su_font(13).render(badge_text, True, (255, 255, 255))
            bw = badge_surf.get_width() + self._su(6)
            bh = badge_surf.get_height() + self._su(2)
            bx = draw_rect.right - bw - self._su(2)
            by = draw_rect.bottom - bh - self._su(2)
            pygame.draw.rect(self.screen, (0, 0, 0, 180), pygame.Rect(bx, by, bw, bh), border_radius=self._su(4))
            self.screen.blit(badge_surf, (bx + self._su(3), by + self._su(1)))

        # Stage 117/118 — hover tooltip (multiline if provided).
        if is_hover:
            if tooltip_lines:
                self._render_loot_tooltip(x, y, sz, rarity, lines=tooltip_lines)
            elif tooltip_text:
                self._render_loot_tooltip(x, y, sz, rarity, text=tooltip_text)

    def _render_loot_tooltip(self, slot_x: int, slot_y: int, slot_sz: int,
                            rarity: str, text: str = "", lines: list | None = None) -> None:
        """Unified loot tooltip renderer.

        If `lines` is provided, renders a multiline rich tooltip (each line is
        a (text, color) tuple). If only `text` is provided, renders a single-line
        tooltip. The positioning logic (above slot, clamped to screen) is shared.

        Stage 201 — slot_x/slot_y/slot_sz — ДИЗАЙН-координаты; тултип
        рисуется ×_su с шрифтами _su_font.
        """
        rarity_color = RARITY_RGB.get(rarity, (234, 179, 8))
        font = self._su_font(13)
        line_h = font.get_height() + self._su(2)

        if lines:
            rendered = []
            max_w = 0
            for ln_text, ln_color in lines:
                surf = font.render(ln_text, True, ln_color)
                rendered.append(surf)
                if surf.get_width() > max_w:
                    max_w = surf.get_width()
            tip_w = max_w + self._su(16)
            tip_h = line_h * len(rendered) + self._su(8)
            border_w = self._su(2)
            accent_h = self._su(3)
        else:
            text_surf = font.render(text, True, (255, 255, 255))
            rendered = [text_surf]
            tip_w = text_surf.get_width() + self._su(12)
            tip_h = text_surf.get_height() + self._su(6)
            border_w = 1
            accent_h = 0

        tx = self._su(slot_x) + self._su(slot_sz) // 2 - tip_w // 2
        ty = self._su(slot_y) - tip_h - self._su(6)
        if ty < self._su(4):
            ty = self._su(slot_y) + self._su(slot_sz) + self._su(6)
        if tx < self._su(4):
            tx = self._su(4)
        scr_w = self.screen.get_width()
        if tx + tip_w > scr_w - self._su(4):
            tx = scr_w - tip_w - self._su(4)

        tip_rect = pygame.Rect(tx, ty, tip_w, tip_h)
        pygame.draw.rect(self.screen, (15, 15, 18), tip_rect, border_radius=self._su(6))
        pygame.draw.rect(self.screen, rarity_color, tip_rect, border_w, border_radius=self._su(6))
        if accent_h > 0:
            pygame.draw.rect(self.screen, rarity_color,
                             pygame.Rect(tx, ty, tip_w, accent_h), border_radius=self._su(2))
        for i, surf in enumerate(rendered):
            self.screen.blit(surf, (tx + self._su(8), ty + self._su(4) + i * line_h))

    # ------------------------------------------------------------------
    # Stage 114 — REDESIGNED RESULT MODAL WITH LOOT GRID
    # ------------------------------------------------------------------

    def _build_loot_tooltip_lines(self, item_name: str, rarity: str,
                                   item_stats: dict, item_slot: str = "",
                                   item_level: int = 1,
                                   level_requirement: int | None = None) -> list:
        """Stage 118 — Build the multiline tooltip lines for a loot item.

        Mirrors the inventory gear tooltip layout:
            line 1: SLOT_NAME  (rarity color; Stage 177 — без префикса [RARITY])
            line 2: item name (white)
            line 3: "Ур. предмета: N | Требует ур.: M" (dim)
            line 4: separator (dim)
            line 5+: main stat(s) (green)
            line N: separator (dim) — only if secondary stats exist
            line N+1..: secondary stats (blue)

        Args:
            item_name: display name (already includes rarity suffix for non-Grey).
            rarity: "Grey"/"Blue"/"Purple"/"Gold"/"Red".
            item_stats: dict of stat_key → value (e.g., {"min_atk": 3, "max_atk": 6, "crit_rating": 4}).
            item_slot: "weapon"/"body"/"boots"/etc.
            item_level: item_level for stat scaling display.
            level_requirement: equip gate (defaults to item_level).

        Returns:
            list of (text, color) tuples. Each tuple = one rendered line.
        """
        from pockie_rpg.config import RARITY_RGB, SLOT_MAIN_STATS
        rarity_color = RARITY_RGB.get(rarity, (234, 179, 8))
        # Slot label (translated).
        from pockie_rpg.config import SLOT_NAME_RU as slot_name_map
        slot_label = slot_name_map.get(item_slot, item_slot or "Предмет").upper()
        # Stage 177 — только тип предмета, без префикса редкости «[GRAY] …»
        # (цвет виден по рамке/цвету строки, текст не нужен).
        header_text = slot_label

        lines: list[tuple[str, tuple[int, int, int]]] = [
            (header_text, rarity_color),
            (item_name, (255, 255, 255)),
        ]
        # Level requirement line.
        lvl_req = level_requirement if level_requirement is not None else item_level
        if lvl_req != item_level:
            lvl_text = f"Ур. предмета: {item_level} | Требует ур.: {lvl_req}"
        else:
            lvl_text = f"Ур. предмета: {item_level}"
        lines.append((lvl_text, (180, 180, 200)))

        # Stat label translation map (subset of inventory tooltip map).
        from pockie_rpg.config import STAT_LABEL_RU as stat_label_map
        main_keys = SLOT_MAIN_STATS.get(item_slot, ("min_atk", "max_atk"))
        main_stats = {k: v for k, v in item_stats.items() if k in main_keys}
        secondary_stats = {k: v for k, v in item_stats.items() if k not in main_keys}

        # Separator before stats.
        lines.append(("─" * 24, (113, 113, 122)))

        # Main stat block.
        green = (80, 220, 100)
        if item_slot == "weapon" and "min_atk" in main_stats and "max_atk" in main_stats:
            lines.append((f"Атака: {main_stats['min_atk']} - {main_stats['max_atk']}", green))
        else:
            for stat_key, value in main_stats.items():
                label = stat_label_map.get(stat_key, stat_key)
                sign = "+" if value >= 0 else ""
                lines.append((f"{sign}{value}  {label}", green))

        # Separator + secondary stats (only if any exist).
        if secondary_stats:
            blue = (100, 180, 255)
            lines.append(("─" * 24, (113, 113, 122)))
            for stat_key, value in secondary_stats.items():
                label = stat_label_map.get(stat_key, stat_key)
                sign = "+" if value >= 0 else ""
                suffix = "%" if stat_key.endswith("_pct") or stat_key == "atk_mul" else ""
                lines.append((f"{sign}{value}{suffix}  {label}", blue))

        return lines


    def _render_quick_battle_result(self) -> None:
        """Stage 114/119 — Render the quick battle result modal with graphical Loot Grid.

        Stage 119 changes:
          * Uses unified `equipment_drops` list (max 1 per battle, up to 10 in x10).
          * Adds PAGINATION when num_items > MAX_PER_PAGE (28 items = 7 cols × 4 rows).
            Prev/Next arrows below the grid. Page number shown between them.
          * Each loot slot still supports rich tooltip_lines from Stage 118.
        """
        r = self._quick_battle_result
        # Stage 165 — подложки больше НЕТ: окно результата поверх живой сцены.

        # --- Collect ALL loot items into a unified list ---
        from collections import Counter

        from pockie_rpg.config import GEM_ICON_DIR
        from pockie_rpg.data.item_db import get_gem_icon_filename

        loot_items: list[dict] = []  # each: {type, icon_surf, rarity, count, tooltip, tooltip_lines}

        # Gems.
        gems = r.get("gems_dropped", [])
        gem_counts: Counter = Counter()
        for gem in gems:
            gem_counts[(gem["type"], gem["level"])] += 1
        for (g_type, g_level), count in gem_counts.items():
            icon_file = get_gem_icon_filename(g_type, g_level)
            icon_path = str(GEM_ICON_DIR / icon_file)
            icon_surf = self._load_gem_icon_surface(icon_path, 48)
            from pockie_rpg.data.item_db import get_gem
            gem_def = get_gem(g_type)
            gem_name = gem_def.get("name", g_type) if gem_def else g_type
            tooltip = f"{gem_name} L{g_level}"
            loot_items.append({"type": "gem", "icon_surf": icon_surf, "rarity": "Grey",
                                "count": count, "tooltip": tooltip, "tooltip_lines": None})

        # Stage 119 — unified equipment drops (replaces per-type lists).
        # Each entry: {type, name, rarity, item_id, auto_sold?}
        eq_drops = r.get("equipment_drops", [])
        # Dedup by (type, name, rarity) for display, accumulating count.
        eq_counts: Counter = Counter()
        for ed in eq_drops:
            eq_counts[(ed.get("type", "weapon"), ed["name"], ed["rarity"])] += 1

        # Resolve icons + matched_item from generated_weapons.
        # Stage 119 — for auto-sold items, generated_weapons may have been cleaned
        # up. We still need the icon for display, so we look up via item_id stored
        # in the drop dict; if the gen_w entry was already deleted, we fall back to
        # the default icon per type.
        default_icons = {
            "weapon": "weapon_wooden.png",
            "armor":  "vest_ninja.png",
            "boots":  "boots_shinobi.png",
            "ring":   "ring1.png",
            "gloves": "gloves_leather.png",
            "belt":   "belt_fabric.png",
            "head":   "headband_ninja.png",
        }
        default_slots = {
            "weapon": "weapon", "armor": "body",
            "boots":  "boots",  "ring":  "accessory",
            "gloves": "hands",  "belt":  "belt",
            "head":   "head",
        }
        for (eq_type, eq_name, eq_rarity), count in eq_counts.items():
            # Find the original item_id from any of the matching drops.
            item_id = None
            for ed in eq_drops:
                if ed.get("type") == eq_type and ed["name"] == eq_name and ed["rarity"] == eq_rarity:
                    item_id = ed.get("item_id")
                    break
            matched_item = None
            icon_filename = default_icons.get(eq_type, "weapon_wooden.png")
            if item_id is not None:
                matched_item = self.player.generated_weapons.get(item_id)
                if matched_item is not None:
                    icon_filename = matched_item.get("icon_filename", icon_filename)
            icon_surf = self._load_item_icon_surface(icon_filename, 48)
            tooltip_lines = None
            if matched_item is not None:
                tooltip_lines = self._build_loot_tooltip_lines(
                    item_name=eq_name, rarity=eq_rarity,
                    item_stats=matched_item.get("stats", {}),
                    item_slot=matched_item.get("slot", default_slots.get(eq_type, "weapon")),
                    item_level=matched_item.get("item_level", 1),
                    level_requirement=matched_item.get("level_requirement"),
                )
            # Stage 119 — mark auto-sold items so the tooltip reflects it.
            auto_sold = any(
                ed.get("auto_sold") for ed in eq_drops
                if ed.get("type") == eq_type and ed["name"] == eq_name and ed["rarity"] == eq_rarity
            )
            loot_items.append({
                "type": eq_type, "icon_surf": icon_surf,
                "rarity": eq_rarity, "count": count,
                "tooltip": eq_name, "tooltip_lines": tooltip_lines,
                "auto_sold": auto_sold,
            })

        # --- Calculate modal dimensions ---
        modal_w = 420
        header_h = 200
        ok_area_h = 70
        slot_sz = 48
        slot_gap = 8
        max_cols = 7
        # Stage 119 — pagination: max 28 items per page (7 cols × 4 rows).
        items_per_page = max_cols * 4
        num_items = len(loot_items)
        total_pages = max(1, (num_items + items_per_page - 1) // items_per_page)

        # Stage 119 — initialize + clamp current page.
        if not hasattr(self, "_loot_page"):
            self._loot_page = 0
        if self._loot_page >= total_pages:
            self._loot_page = 0
        page = self._loot_page
        page_start = page * items_per_page
        page_end = min(page_start + items_per_page, num_items)
        page_items = loot_items[page_start:page_end]
        page_rows = (len(page_items) + max_cols - 1) // max_cols if page_items else 0
        # Pagination controls add ~30px to grid area when there are >1 page.
        pagination_h = 30 if total_pages > 1 else 0
        grid_h = page_rows * (slot_sz + slot_gap) - slot_gap + 20 + pagination_h if page_items else 0

        modal_h = max(360, min(640, header_h + grid_h + ok_area_h))
        modal_x = (SCREEN_WIDTH - modal_w) // 2
        modal_y = (SCREEN_HEIGHT - modal_h) // 2

        # --- Draw modal background ---
        pygame.draw.rect(self.screen, (24, 24, 27), (modal_x, modal_y, modal_w, modal_h), border_radius=12)
        pygame.draw.rect(self.screen, (234, 179, 8), (modal_x, modal_y, modal_w, 4), border_radius=2)

        # --- Title ---
        title = "Результаты боя" if r["count"] == 1 else f"Результаты ×{r['count']}"
        title_surf = self.font_subtitle.render(title, True, (234, 179, 8))
        self.screen.blit(title_surf, (modal_x + (modal_w - title_surf.get_width()) // 2, modal_y + 16))

        # --- Stats lines ---
        y = modal_y + 56
        lines = [
            (f"Побед: {r['wins']}/{r['count']}", (34, 197, 94)),
            (f"Поражений: {r['losses']}/{r['count']}", (220, 38, 38)),
            ("", None),
            (f"XP: +{r['xp_gained']}", (250, 204, 21)),
            (f"Золото: +{r['gold_gained']}", (250, 204, 21)),
        ]
        if r["level_before"] != r["level_after"]:
            lines.append(("", None))
            lines.append((f"Уровень: {r['level_before']} → {r['level_after']}", (234, 179, 8)))
        for text, color in lines:
            if not text:
                y += 8
                continue
            s = self.font_body.render(text, True, color or (244, 244, 245))
            self.screen.blit(s, (modal_x + (modal_w - s.get_width()) // 2, y))
            y += 24

        # --- Loot Grid (paginated) ---
        if loot_items:
            # Stage 119 — label shows total count + current page indicator.
            if total_pages > 1:
                loot_label_text = f"Полученный лут ({num_items} шт, стр. {page + 1}/{total_pages}):"
            else:
                loot_label_text = f"Полученный лут ({num_items} шт):"
            loot_label = self.font_small.render(loot_label_text, True, (234, 179, 8))
            self.screen.blit(loot_label, (modal_x + (modal_w - loot_label.get_width()) // 2, y))
            y += 24

            grid_y_start = y
            total_grid_w = max_cols * slot_sz + (max_cols - 1) * slot_gap
            grid_x_start = modal_x + (modal_w - total_grid_w) // 2

            for idx, loot in enumerate(page_items):
                col = idx % max_cols
                row = idx // max_cols
                sx = grid_x_start + col * (slot_sz + slot_gap)
                sy = grid_y_start + row * (slot_sz + slot_gap)
                # Stage 119 — for auto-sold items, override tooltip_lines.
                tooltip_lines = loot.get("tooltip_lines")
                if loot.get("auto_sold") and tooltip_lines:
                    tooltip_lines = list(tooltip_lines) + [
                        ("─" * 24, (113, 113, 122)),
                        ("[АВТО-ПРОДАНО]", (220, 38, 38)),
                    ]
                self._render_loot_slot(
                    sx, sy, slot_sz, loot["icon_surf"],
                    loot["rarity"], loot["count"], loot["type"],
                    loot.get("tooltip", ""),
                    tooltip_lines,
                )

            # Stage 119 — pagination controls (prev / page indicator / next).
            if total_pages > 1:
                y = grid_y_start + page_rows * (slot_sz + slot_gap) + 4
                arrow_w = 40
                arrow_h = 22
                arrow_gap = 16
                # Centered: [‹ Prev] [1/3] [Next ›]
                page_text = f"{page + 1} / {total_pages}"
                page_surf = self.font_small.render(page_text, True, (234, 179, 8))
                page_w = page_surf.get_width()
                total_w = arrow_w * 2 + page_w + arrow_gap * 2
                start_x = modal_x + (modal_w - total_w) // 2

                # Prev button.
                prev_rect = pygame.Rect(start_x, y, arrow_w, arrow_h)
                prev_hover = prev_rect.collidepoint(self._mouse_pos) and page > 0
                prev_bg = (60, 50, 10) if prev_hover else (40, 40, 45)
                prev_fg = (255, 255, 255) if prev_hover else (180, 180, 185)
                if page == 0:
                    prev_bg = (30, 30, 33)
                    prev_fg = (80, 80, 85)
                pygame.draw.rect(self.screen, prev_bg, prev_rect, border_radius=4)
                if prev_hover:
                    pygame.draw.rect(self.screen, (234, 179, 8), prev_rect, 1, border_radius=4)
                prev_text = self.font_small.render("‹", True, prev_fg)
                self.screen.blit(prev_text, prev_text.get_rect(center=prev_rect.center))
                if page > 0:
                    def _go_prev(_p: int = page):
                        self._loot_page = max(0, _p - 1)
                    self._click_rects.append(ClickRect(tag="loot_prev", rect=prev_rect, on_click=_go_prev))

                # Page indicator.
                page_x = start_x + arrow_w + arrow_gap
                self.screen.blit(page_surf, (page_x + (page_w - page_surf.get_width()) // 2,
                                              y + (arrow_h - page_surf.get_height()) // 2))

                # Next button.
                next_x = page_x + page_w + arrow_gap
                next_rect = pygame.Rect(next_x, y, arrow_w, arrow_h)
                next_hover = next_rect.collidepoint(self._mouse_pos) and page < total_pages - 1
                next_bg = (60, 50, 10) if next_hover else (40, 40, 45)
                next_fg = (255, 255, 255) if next_hover else (180, 180, 185)
                if page >= total_pages - 1:
                    next_bg = (30, 30, 33)
                    next_fg = (80, 80, 85)
                pygame.draw.rect(self.screen, next_bg, next_rect, border_radius=4)
                if next_hover:
                    pygame.draw.rect(self.screen, (234, 179, 8), next_rect, 1, border_radius=4)
                next_text = self.font_small.render("›", True, next_fg)
                self.screen.blit(next_text, next_text.get_rect(center=next_rect.center))
                if page < total_pages - 1:
                    def _go_next(_p: int = page, _tp: int = total_pages):
                        self._loot_page = min(_tp - 1, _p + 1)
                    self._click_rects.append(ClickRect(tag="loot_next", rect=next_rect, on_click=_go_next))
        else:
            no_loot = self.font_small.render("(нет выпавших предметов)", True, (113, 113, 122))
            self.screen.blit(no_loot, (modal_x + (modal_w - no_loot.get_width()) // 2, y))

        # --- OK Button (always at the bottom) ---
        ok_w = 160
        ok_h = 44
        ok_x = modal_x + (modal_w - ok_w) // 2
        ok_y = modal_y + modal_h - ok_h - 20
        ok_rect = pygame.Rect(ok_x, ok_y, ok_w, ok_h)
        ok_hover = ok_rect.collidepoint(self._mouse_pos)
        pygame.draw.rect(self.screen, (52, 211, 153) if ok_hover else (16, 185, 129), ok_rect, border_radius=10)
        ok_text = self.font_button.render("ОК", True, (0, 0, 0))
        ok_text_rect = ok_text.get_rect(center=ok_rect.center)
        self.screen.blit(ok_text, ok_text_rect.topleft)
        self._click_rects.append(ClickRect(tag="close_qb_result", rect=ok_rect, on_click=self._close_quick_battle_result))
