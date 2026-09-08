"""Stage 109 — Test Panel (Admin/Dev Panel) renderer mixin.

Provides a graphical debug window for testing weapon balance.
Opens via F9 hotkey or a button in the inventory modal.

Features:
- Level selector: 6 buttons (1, 5, 10, 15, 20, 25)
- Rarity selector: 5 colored buttons (Grey, Blue, Purple, Gold, Red)
- "Получить бесплатно" button: calls player.give_test_weapon()
- Preview area showing the generated weapon's stats
- Close button

The panel updates its preview whenever level/rarity selection changes.
"""
from __future__ import annotations

from pockie_rpg.config import (
    MAX_LEVEL,
    RARITY_COLORS,
    RARITY_RGB,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    WEAPON_LEVELS,
    GameState,
)
from pockie_rpg.data.item_db import generate_item

# Stage 171 — панель выросла вниз (560 → 704): секция сейв-слотов; заодно
# разводит ряды скиллов и кнопки «Выдать костюмы»/«Получить», которые
# накладывались при 6 навыках в реестре.
_TEST_PANEL_W: int = 520
_TEST_PANEL_H: int = 704


class TestPanelRendererMixin:
    """Mixin for PygameUI — renders the admin/dev test panel.

    State fields (initialized in PygameUI.__init__):
        self._test_panel_open: bool
        self._test_panel_level: int  (default 1)
        self._test_panel_rarity: str  (default "Grey")
        self._test_panel_preview: dict | None  (cached generated weapon)
        self._test_panel_toast: str | None  (success message, e.g., "Получено!")
        self._test_panel_toast_timer: float  (seconds remaining)

    Click handling:
        _handle_test_panel_click(pos) → bool (True if click was consumed)
    """

    def _init_test_panel_state(self) -> None:
        """Stage 109 — Initialize test panel state. Call from PygameUI.__init__."""
        self._test_panel_open: bool = False
        self._test_panel_level: int = 1
        self._test_panel_rarity: str = "Grey"
        self._test_panel_item_type: str = "weapon"  # Stage 112 — "weapon" or "armor"
        self._test_panel_preview: dict | None = None
        self._test_panel_toast: str | None = None
        self._test_panel_toast_timer: float = 0.0
        # Stage 123 — skill chance overrides (dict: skill_id → float 0.0-1.0).
        # When set, try_skill() uses these instead of the registry defaults.
        self._skill_chance_overrides: dict[int, float] = {}
        # Stage 171 — B1: подтверждение загрузки слота (2 клика; второй —
        # в течение таймера). None = подтверждение не ждётся.
        self._test_panel_slot_confirm: int | None = None
        self._test_panel_slot_confirm_timer: float = 0.0
        self._refresh_test_panel_preview()

    def _toggle_test_panel(self) -> None:
        """Stage 109 — Toggle test panel visibility (F9 hotkey)."""
        self._test_panel_open = not self._test_panel_open
        if self._test_panel_open:
            self._refresh_test_panel_preview()

    def _close_test_panel(self) -> None:
        """Stage 109 — Close the test panel."""
        self._test_panel_open = False

    def _refresh_test_panel_preview(self) -> None:
        """Stage 112 — Regenerate the preview item with current level/rarity/type."""
        try:
            self._test_panel_preview = generate_item(
                self._test_panel_level, self._test_panel_rarity,
                self._test_panel_item_type
            )
        except ValueError:
            self._test_panel_preview = None

    def _render_test_panel(self) -> None:
        """Stage 109 — Render the test panel modal."""
        if not self._test_panel_open:
            return

        import pygame

        # Modal dimensions.
        panel_w = _TEST_PANEL_W
        panel_h = _TEST_PANEL_H
        panel_x = (SCREEN_WIDTH - panel_w) // 2
        panel_y = (SCREEN_HEIGHT - panel_h) // 2

        # Dark overlay background.
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        # Panel background (zinc-900 with gold border).
        panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
        pygame.draw.rect(self.screen, (24, 24, 27), panel_rect, border_radius=12)
        pygame.draw.rect(self.screen, (234, 179, 8), panel_rect, 2, border_radius=12)
        # Top accent bar.
        pygame.draw.rect(self.screen, (234, 179, 8),
                         pygame.Rect(panel_x, panel_y, panel_w, 4), border_radius=2)

        # Title.
        title_surf = self.font_button.render("🔧 Тестовая панель баланса", True, (234, 179, 8))
        self.screen.blit(title_surf, (panel_x + 16, panel_y + 12))

        # Close button (X) top-right.
        close_rect = pygame.Rect(panel_x + panel_w - 36, panel_y + 12, 24, 24)
        pygame.draw.rect(self.screen, (60, 60, 70), close_rect, border_radius=4)
        close_x = self.font_small.render("✕", True, (255, 255, 255))
        self.screen.blit(close_x, (close_rect.x + 6, close_rect.y + 2))
        self._test_panel_close_rect = close_rect

        # --- Item type selector (Stage 112) ---
        type_label = self.font_small.render("Тип предмета:", True, (180, 180, 200))
        self.screen.blit(type_label, (panel_x + 16, panel_y + 44))

        self._test_panel_type_rects: list[tuple[str, pygame.Rect]] = []
        # Stage 128 — added "head" item type (7 buttons: all slots complete).
        type_btns = [("weapon", "Оружие"), ("armor", "Броня"), ("boots", "Обувь"),
                     ("ring", "Кольцо"), ("gloves", "Перчатки"), ("belt", "Пояс"),
                     ("head", "Шлем")]
        t_btn_w = 64
        t_btn_h = 28
        t_btn_gap = 3
        t_start_x = panel_x + (panel_w - len(type_btns) * t_btn_w - (len(type_btns) - 1) * t_btn_gap) // 2
        for i, (t_type, t_label) in enumerate(type_btns):
            bx = t_start_x + i * (t_btn_w + t_btn_gap)
            by = panel_y + 62
            rect = pygame.Rect(bx, by, t_btn_w, t_btn_h)
            is_selected = (t_type == self._test_panel_item_type)
            color = (80, 220, 100) if is_selected else (50, 50, 55)
            pygame.draw.rect(self.screen, color, rect, border_radius=6)
            if is_selected:
                pygame.draw.rect(self.screen, (234, 179, 8), rect, 2, border_radius=6)
            text_color = (0, 0, 0) if is_selected else (200, 200, 210)
            t_surf = self.font_small.render(t_label, True, text_color)
            text_x = bx + (t_btn_w - t_surf.get_width()) // 2
            text_y = by + (t_btn_h - t_surf.get_height()) // 2
            self.screen.blit(t_surf, (text_x, text_y))
            self._test_panel_type_rects.append((t_type, rect))

        # --- Level selector ---
        level_label = self.font_small.render("Уровень:", True, (180, 180, 200))
        self.screen.blit(level_label, (panel_x + 16, panel_y + 100))

        self._test_panel_level_rects: list[tuple[int, pygame.Rect]] = []
        btn_w = 60
        btn_h = 36
        btn_gap = 8
        total_btn_w = len(WEAPON_LEVELS) * btn_w + (len(WEAPON_LEVELS) - 1) * btn_gap
        start_x = panel_x + (panel_w - total_btn_w) // 2
        for i, level in enumerate(WEAPON_LEVELS):
            bx = start_x + i * (btn_w + btn_gap)
            by = panel_y + 120
            rect = pygame.Rect(bx, by, btn_w, btn_h)
            is_selected = (level == self._test_panel_level)
            color = (80, 220, 100) if is_selected else (50, 50, 55)
            pygame.draw.rect(self.screen, color, rect, border_radius=6)
            if is_selected:
                pygame.draw.rect(self.screen, (234, 179, 8), rect, 2, border_radius=6)
            text_color = (0, 0, 0) if is_selected else (200, 200, 210)
            lvl_surf = self.font_small.render(f"L{level}", True, text_color)
            text_x = bx + (btn_w - lvl_surf.get_width()) // 2
            text_y = by + (btn_h - lvl_surf.get_height()) // 2
            self.screen.blit(lvl_surf, (text_x, text_y))
            self._test_panel_level_rects.append((level, rect))

        # --- Rarity selector ---
        rarity_label = self.font_small.render("Редкость:", True, (180, 180, 200))
        self.screen.blit(rarity_label, (panel_x + 16, panel_y + 168))

        self._test_panel_rarity_rects: list[tuple[str, pygame.Rect]] = []
        r_btn_w = 80
        r_btn_h = 36
        r_btn_gap = 8
        total_r_w = len(RARITY_COLORS) * r_btn_w + (len(RARITY_COLORS) - 1) * r_btn_gap
        r_start_x = panel_x + (panel_w - total_r_w) // 2
        for i, (rarity, count) in enumerate(RARITY_COLORS.items()):
            bx = r_start_x + i * (r_btn_w + r_btn_gap)
            by = panel_y + 188
            rect = pygame.Rect(bx, by, r_btn_w, r_btn_h)
            is_selected = (rarity == self._test_panel_rarity)
            base_color = RARITY_RGB[rarity]
            # Darken non-selected buttons.
            if is_selected:
                bg_color = base_color
                text_color = (0, 0, 0)
            else:
                bg_color = tuple(c // 3 for c in base_color)
                text_color = base_color
            pygame.draw.rect(self.screen, bg_color, rect, border_radius=6)
            if is_selected:
                pygame.draw.rect(self.screen, (255, 255, 255), rect, 2, border_radius=6)
            r_surf = self.font_small.render(rarity, True, text_color)
            text_x = bx + (r_btn_w - r_surf.get_width()) // 2
            text_y = by + (r_btn_h - r_surf.get_height()) // 2
            self.screen.blit(r_surf, (text_x, text_y))
            self._test_panel_rarity_rects.append((rarity, rect))

        # --- Preview area ---
        preview_y = panel_y + 240
        preview_label = self.font_small.render("Превью предмета:", True, (180, 180, 200))
        self.screen.blit(preview_label, (panel_x + 16, preview_y))

        if self._test_panel_preview is not None:
            pv = self._test_panel_preview
            stats = pv.get("stats", {})
            rarity = pv.get("rarity", "")
            rarity_color = RARITY_RGB.get(rarity, (234, 179, 8))

            # Weapon name with rarity color.
            name_surf = self.font_button.render(pv["name"], True, rarity_color)
            self.screen.blit(name_surf, (panel_x + 16, preview_y + 20))

            # Main stat display — varies by slot:
            #   weapon: "Атака: X - Y"
            #   body:   "Защита: +X  HP: +Y"
            #   boots:  "Защита: +X  Скорость: +Y"  (Stage 118)
            #   accessory (ring): "Крит: +X  Пробитие: +Y"  (Stage 119)
            slot = pv.get("slot", "")
            if slot == "weapon":
                min_atk = stats.get("min_atk", 0)
                max_atk = stats.get("max_atk", 0)
                atk_surf = self.font_small.render(
                    f"Атака: {min_atk} - {max_atk}", True, (80, 220, 100)
                )
                self.screen.blit(atk_surf, (panel_x + 16, preview_y + 44))
            elif slot == "boots":
                defense = stats.get("defense", 0)
                speed = stats.get("speed", 0)
                def_surf = self.font_small.render(
                    f"Защита: +{defense}  Скорость: +{speed}", True, (80, 220, 100)
                )
                self.screen.blit(def_surf, (panel_x + 16, preview_y + 44))
            elif slot == "accessory":
                # Stage 119 — ring preview (crit_rating + pierce_rating).
                crit = stats.get("crit_rating", 0)
                pierce = stats.get("pierce_rating", 0)
                acc_surf = self.font_small.render(
                    f"Крит: +{crit}  Пробитие: +{pierce}", True, (80, 220, 100)
                )
                self.screen.blit(acc_surf, (panel_x + 16, preview_y + 44))
            elif slot == "hands":
                # Stage 123 — gloves preview (defense + hit_rating).
                defense = stats.get("defense", 0)
                hit = stats.get("hit_rating", 0)
                hands_surf = self.font_small.render(
                    f"Защита: +{defense}  Меткость: +{hit}", True, (80, 220, 100)
                )
                self.screen.blit(hands_surf, (panel_x + 16, preview_y + 44))
            elif slot == "belt":
                # Stage 127 — belt preview (defense + tough_rating).
                defense = stats.get("defense", 0)
                tough = stats.get("tough_rating", 0)
                belt_surf = self.font_small.render(
                    f"Защита: +{defense}  Стойкость: +{tough}", True, (80, 220, 100)
                )
                self.screen.blit(belt_surf, (panel_x + 16, preview_y + 44))
            elif slot == "head":
                # Stage 128 — head preview (defense + max_hp).
                defense = stats.get("defense", 0)
                max_hp = stats.get("max_hp", 0)
                head_surf = self.font_small.render(
                    f"Защита: +{defense}  HP: +{max_hp}", True, (80, 220, 100)
                )
                self.screen.blit(head_surf, (panel_x + 16, preview_y + 44))
            else:
                defense = stats.get("defense", 0)
                max_hp = stats.get("max_hp", 0)
                def_surf = self.font_small.render(
                    f"Защита: +{defense}  HP: +{max_hp}", True, (80, 220, 100)
                )
                self.screen.blit(def_surf, (panel_x + 16, preview_y + 44))

            # Separator line.
            sep_y = preview_y + 66
            separator = self.font_small.render("─" * 30, True, (113, 113, 122))
            self.screen.blit(separator, (panel_x + 16, sep_y))

            # Secondary stats (exclude main stats per slot).
            # Stage 118 — added "boots" main keys: (defense, speed).
            # Stage 119 — added "accessory" main keys: (crit_rating, pierce_rating).
            # Stage 123 — added "hands" main keys: (defense, hit_rating).
            if slot == "weapon":
                main_keys = ("min_atk", "max_atk")
            elif slot == "boots":
                main_keys = ("defense", "speed")
            elif slot == "accessory":
                main_keys = ("crit_rating", "pierce_rating")
            elif slot == "hands":
                main_keys = ("defense", "hit_rating")
            elif slot == "belt":
                main_keys = ("defense", "tough_rating")
            elif slot == "head":
                main_keys = ("defense", "max_hp")
            else:
                main_keys = ("defense", "max_hp")
            secondary = {k: v for k, v in stats.items() if k not in main_keys}
            if secondary:
                stat_y = sep_y + 18
                for stat_key, value in secondary.items():
                    suffix = "%" if stat_key.endswith("_pct") or stat_key == "atk_mul" else ""
                    line = f"+{value}{suffix}  {stat_key}"
                    s_surf = self.font_small.render(line, True, (100, 180, 255))
                    self.screen.blit(s_surf, (panel_x + 16, stat_y))
                    stat_y += 18
            else:
                no_sec = self.font_small.render("(нет доп. статов)", True, (113, 113, 122))
                self.screen.blit(no_sec, (panel_x + 16, sep_y + 18))

        # --- Stage 123 — Skill chance controls ---
        skills_y = panel_y + 360
        skills_label = self.font_small.render("Шансы навыков (для теста):", True, (180, 180, 200))
        self.screen.blit(skills_label, (panel_x + 16, skills_y))

        from pockie_rpg.combat.skill_registry import SKILL_REGISTRY
        self._test_panel_skill_rects: list[tuple[int, str, pygame.Rect]] = []
        skill_btn_w = 24
        skill_btn_h = 20
        skill_row_h = 22
        for i, (skill_id, skill) in enumerate(SKILL_REGISTRY.items()):
            sy = skills_y + 20 + i * skill_row_h
            # Skill name (truncated).
            skill_name = skill.name
            if len(skill_name) > 18:
                skill_name = skill_name[:17] + "…"
            name_surf = self.font_small.render(skill_name, True, (200, 200, 210))
            self.screen.blit(name_surf, (panel_x + 16, sy))

            # Current chance (override or default).
            current_chance = self._skill_chance_overrides.get(
                skill_id, skill.trigger_chance
            )
            chance_text = f"{int(current_chance * 100)}%"
            chance_color = (234, 179, 8) if skill_id in self._skill_chance_overrides else (180, 180, 185)
            chance_surf = self.font_small.render(chance_text, True, chance_color)
            self.screen.blit(chance_surf, (panel_x + 200, sy))

            # "-" button.
            minus_x = panel_x + 260
            minus_rect = pygame.Rect(minus_x, sy, skill_btn_w, skill_btn_h)
            minus_hover = minus_rect.collidepoint(self._mouse_pos)
            m_bg = (60, 30, 30) if minus_hover else (40, 24, 24)
            pygame.draw.rect(self.screen, m_bg, minus_rect, border_radius=4)
            if minus_hover:
                pygame.draw.rect(self.screen, (220, 60, 60), minus_rect, 1, border_radius=4)
            m_text = self.font_small.render("−", True, (255, 200, 200))
            self.screen.blit(m_text, m_text.get_rect(center=minus_rect.center))
            self._test_panel_skill_rects.append((skill_id, "minus", minus_rect))

            # "+" button.
            plus_x = minus_x + skill_btn_w + 6
            plus_rect = pygame.Rect(plus_x, sy, skill_btn_w, skill_btn_h)
            plus_hover = plus_rect.collidepoint(self._mouse_pos)
            p_bg = (30, 60, 30) if plus_hover else (24, 40, 24)
            pygame.draw.rect(self.screen, p_bg, plus_rect, border_radius=4)
            if plus_hover:
                pygame.draw.rect(self.screen, (60, 220, 60), plus_rect, 1, border_radius=4)
            p_text = self.font_small.render("+", True, (200, 255, 200))
            self.screen.blit(p_text, p_text.get_rect(center=plus_rect.center))
            self._test_panel_skill_rects.append((skill_id, "plus", plus_rect))

            # "Reset" button.
            reset_x = plus_x + skill_btn_w + 6
            reset_rect = pygame.Rect(reset_x, sy, 50, skill_btn_h)
            reset_hover = reset_rect.collidepoint(self._mouse_pos)
            r_bg = (40, 40, 45) if not reset_hover else (60, 50, 10)
            pygame.draw.rect(self.screen, r_bg, reset_rect, border_radius=4)
            if reset_hover:
                pygame.draw.rect(self.screen, (234, 179, 8), reset_rect, 1, border_radius=4)
            r_text = self.font_small.render("сброс", True, (200, 200, 210))
            self.screen.blit(r_text, r_text.get_rect(center=reset_rect.center))
            self._test_panel_skill_rects.append((skill_id, "reset", reset_rect))

        # --- "Получить бесплатно" button ---
        spawn_btn_w = 240
        spawn_btn_h = 48
        spawn_btn_x = panel_x + (panel_w - spawn_btn_w) // 2
        spawn_btn_y = panel_y + panel_h - 70
        spawn_rect = pygame.Rect(spawn_btn_x, spawn_btn_y, spawn_btn_w, spawn_btn_h)
        pygame.draw.rect(self.screen, (80, 220, 100), spawn_rect, border_radius=8)
        pygame.draw.rect(self.screen, (234, 179, 8), spawn_rect, 2, border_radius=8)
        spawn_text = self.font_button.render("ПОЛУЧИТЬ БЕСПЛАТНО", True, (0, 0, 0))
        text_x = spawn_btn_x + (spawn_btn_w - spawn_text.get_width()) // 2
        text_y = spawn_btn_y + (spawn_btn_h - spawn_text.get_height()) // 2
        self.screen.blit(spawn_text, (text_x, text_y))
        self._test_panel_spawn_rect = spawn_rect

        # --- Stage 171 — B1: сейв-слоты (rolling saves, dev-кнопки) ---
        from pockie_rpg.game import save_load as save_load_mod
        save_label_y = panel_y + 524
        save_label = self.font_small.render(
            "Сейв-слоты (загрузка с подтверждением):", True, (180, 180, 200))
        self.screen.blit(save_label, (panel_x + 16, save_label_y))

        self._test_panel_slot_rects: list[tuple[int, pygame.Rect]] = []
        slot_btn_w = 150
        slot_btn_h = 30
        slot_gap = 12
        s_total = save_load_mod.ROLLING_SAVE_SLOTS * slot_btn_w \
            + (save_load_mod.ROLLING_SAVE_SLOTS - 1) * slot_gap
        s_x0 = panel_x + (panel_w - s_total) // 2
        for i in range(1, save_load_mod.ROLLING_SAVE_SLOTS + 1):
            rect = pygame.Rect(
                s_x0 + (i - 1) * (slot_btn_w + slot_gap),
                save_label_y + 20, slot_btn_w, slot_btn_h,
            )
            confirming = (
                self._test_panel_slot_confirm == i
                and self._test_panel_slot_confirm_timer > 0
            )
            exists = save_load_mod.rolling_slot_path(i).exists()
            if confirming:
                bg, border = (90, 30, 30), (220, 80, 80)
                label, txt = f"Точно: слот {i}?", (255, 210, 210)
            elif exists:
                bg, border = (40, 40, 45), (82, 82, 91)
                label, txt = f"Слот {i}: загрузить", (200, 200, 210)
            else:
                bg, border = (30, 30, 34), (63, 63, 70)
                label, txt = f"Слот {i}: пусто", (120, 120, 130)
            if rect.collidepoint(self._mouse_pos) and not confirming:
                border = (234, 179, 8)
            pygame.draw.rect(self.screen, bg, rect, border_radius=6)
            pygame.draw.rect(self.screen, border, rect, 1, border_radius=6)
            s_surf = self.font_small.render(label, True, txt)
            self.screen.blit(s_surf, s_surf.get_rect(center=rect.center))
            self._test_panel_slot_rects.append((i, rect))

        # --- Stage 138 — "Выдать тест-костюмы" button (синтез/гардероб) ---
        outfit_btn_w = 240
        outfit_btn_h = 30
        outfit_btn_x = panel_x + (panel_w - outfit_btn_w) // 2
        outfit_btn_y = spawn_btn_y - 40
        outfit_rect = pygame.Rect(outfit_btn_x, outfit_btn_y, outfit_btn_w, outfit_btn_h)
        ob_hover = outfit_rect.collidepoint(self._mouse_pos)
        ob_bg = (60, 50, 10) if ob_hover else (40, 40, 45)
        pygame.draw.rect(self.screen, ob_bg, outfit_rect, border_radius=6)
        pygame.draw.rect(self.screen, (167, 139, 250) if ob_hover else (82, 82, 91),
                         outfit_rect, 1, border_radius=6)
        ob_text = self.font_small.render("Выдать 4 тест-костюма (синтез)", True,
                                         (255, 255, 255) if ob_hover else (200, 200, 210))
        self.screen.blit(ob_text, ob_text.get_rect(center=outfit_rect.center))
        self._test_panel_outfit_rect = outfit_rect

        # --- Toast notification ---
        if self._test_panel_toast and self._test_panel_toast_timer > 0:
            toast_color = (80, 220, 100)
            toast_surf = self.font_small.render(self._test_panel_toast, True, toast_color)
            toast_x = panel_x + (panel_w - toast_surf.get_width()) // 2
            toast_y = spawn_btn_y + spawn_btn_h + 8
            self.screen.blit(toast_surf, (toast_x, toast_y))

    def _handle_test_panel_click(self, pos: tuple[int, int]) -> bool:
        """Stage 109 — Handle clicks in the test panel.

        Returns True if the click was consumed (inside the panel),
        False if the click was outside (so caller can close the panel).
        """
        if not self._test_panel_open:
            return False

        import pygame

        # Close button.
        if hasattr(self, "_test_panel_close_rect") and self._test_panel_close_rect.collidepoint(pos):
            self._close_test_panel()
            return True

        # Stage 112 — Item type buttons.
        for t_type, rect in getattr(self, "_test_panel_type_rects", []):
            if rect.collidepoint(pos):
                self._test_panel_item_type = t_type
                self._refresh_test_panel_preview()
                return True

        # Level buttons.
        for level, rect in getattr(self, "_test_panel_level_rects", []):
            if rect.collidepoint(pos):
                self._test_panel_level = level
                self._refresh_test_panel_preview()
                return True

        # Rarity buttons.
        for rarity, rect in getattr(self, "_test_panel_rarity_rects", []):
            if rect.collidepoint(pos):
                self._test_panel_rarity = rarity
                self._refresh_test_panel_preview()
                return True

        # Spawn button.
        if hasattr(self, "_test_panel_spawn_rect") and self._test_panel_spawn_rect.collidepoint(pos):
            self._spawn_test_weapon()
            return True

        # Stage 138 — test outfits button (синтез/гардероб тест).
        if hasattr(self, "_test_panel_outfit_rect") and self._test_panel_outfit_rect.collidepoint(pos):
            self._spawn_test_outfits()
            return True

        # Stage 171 — B1: сейв-слоты (первый клик — подтверждение, второй —
        # в течение таймера — загрузка).
        for n, rect in getattr(self, "_test_panel_slot_rects", []):
            if rect.collidepoint(pos):
                if (self._test_panel_slot_confirm == n
                        and self._test_panel_slot_confirm_timer > 0):
                    self._test_panel_slot_confirm = None
                    self._test_panel_slot_confirm_timer = 0.0
                    self._load_from_save_slot(n)
                else:
                    self._test_panel_slot_confirm = n
                    self._test_panel_slot_confirm_timer = 4.0
                    self._test_panel_toast = f"Слот {n}: нажмите ещё раз для загрузки"
                    self._test_panel_toast_timer = 4.0
                return True

        # Stage 123 — Skill chance +/-/reset buttons.
        for skill_id, action, rect in getattr(self, "_test_panel_skill_rects", []):
            if rect.collidepoint(pos):
                self._adjust_skill_chance(skill_id, action)
                return True

        # Click inside panel bounds (but not on any button) — consume.
        # Click outside panel — close it.
        panel_x = (SCREEN_WIDTH - _TEST_PANEL_W) // 2
        panel_y = (SCREEN_HEIGHT - _TEST_PANEL_H) // 2
        panel_rect = pygame.Rect(panel_x, panel_y, _TEST_PANEL_W, _TEST_PANEL_H)
        if panel_rect.collidepoint(pos):
            return True  # consume clicks inside panel
        else:
            self._close_test_panel()
            return True

    def _adjust_skill_chance(self, skill_id: int, action: str) -> None:
        """Stage 123 — Adjust skill trigger chance for testing.

        Args:
            skill_id: the skill to adjust.
            action: "plus" (+5%), "minus" (-5%), or "reset" (to default).
        """
        from pockie_rpg.combat.damage import set_skill_chance_overrides
        from pockie_rpg.combat.skill_registry import get_skill
        skill = get_skill(skill_id)
        if skill is None:
            return
        default = skill.trigger_chance
        current = self._skill_chance_overrides.get(skill_id, default)
        if action == "plus":
            current = min(1.0, current + 0.05)
            self._skill_chance_overrides[skill_id] = current
        elif action == "minus":
            current = max(0.0, current - 0.05)
            self._skill_chance_overrides[skill_id] = current
        elif action == "reset":
            self._skill_chance_overrides.pop(skill_id, None)
            current = default
        # Push the overrides to the damage module (global state).
        set_skill_chance_overrides(self._skill_chance_overrides)
        # Show toast.
        pct = int(current * 100)
        self._test_panel_toast = f"{skill.name}: {pct}%"
        self._test_panel_toast_timer = 1.5

    def _spawn_test_weapon(self) -> None:
        """Stage 112 — Spawn the selected item (weapon or armor) into player's inventory."""
        gen_id = self.player.give_test_item(
            self._test_panel_level, self._test_panel_rarity,
            self._test_panel_item_type
        )
        if gen_id is not None:
            self._test_panel_toast = f"✓ Получено: {gen_id} → инвентарь"
            self._test_panel_toast_timer = 2.0
            self._save_player()
        else:
            self._test_panel_toast = "✗ Инвентарь полон!"
            self._test_panel_toast_timer = 2.0

    def _spawn_test_outfits(self) -> None:
        """Stage 138 — выдать 4 тест-костюма для проверки синтеза/гардероба."""
        added = 0
        for outfit_id in ("suit_ichigo", "suit_ichigo", "suit_samurai_tank", "suit_ninja_evasion"):
            if self.player.inv_add(outfit_id):
                added += 1
        if added:
            self._test_panel_toast = f"✓ Выдано костюмов: {added}"
            self._save_player()
        else:
            self._test_panel_toast = "✗ Инвентарь полон!"
        self._test_panel_toast_timer = 2.0

    def _load_from_save_slot(self, n: int) -> None:
        """Stage 171 — B1: dev-загрузка слота сейва (F9, только на карте).

        Порядок: flush текущего прогресса (страховка в primary/.bak) →
        load_from_slot → подмена игрока + перепривязка провайдера синтеза →
        mark_dirty (загруженное состояние становится «живым»). Боевые
        стейты (Fighter/аниматоры) живут только внутри боя, поэтому вне
        карты загрузка блокируется с сообщением.
        """
        from pockie_rpg.game import save_load as save_load_mod
        if self.state != GameState.MAP:
            self._test_panel_toast = "Загрузка слота доступна только на карте"
            self._test_panel_toast_timer = 2.5
            return
        self.save_mgr.flush()
        player = save_load_mod.load_from_slot(n)
        if player is None:
            self._test_panel_toast = f"Слот {n}: пуст или повреждён"
            self._test_panel_toast_timer = 2.5
            return
        self.player = player
        if self.player.level < 1:
            self.player.level = 1
        if self.player.level > MAX_LEVEL:
            self.player.level = MAX_LEVEL
        if self.player.xp < 0:
            self.player.xp = 0
        if self.player.gold < 0:
            self.player.gold = 0
        self.save_mgr.set_player(self.player)
        self._bind_synth_slots_provider(self.player)
        self.save_mgr.mark_dirty()
        self._test_panel_toast = (
            f"Загружен слот {n}: ур. {self.player.level}, "
            f"золото {self.player.gold}"
        )
        self._test_panel_toast_timer = 3.5

    def _update_test_panel_toast(self, dt: float) -> None:
        """Stage 109 — Update toast timer (call from main update loop)."""
        if self._test_panel_toast_timer > 0:
            self._test_panel_toast_timer -= dt
            if self._test_panel_toast_timer <= 0:
                self._test_panel_toast = None
                self._test_panel_toast_timer = 0.0
        # Stage 171 — B1: таймер подтверждения загрузки слота.
        if self._test_panel_slot_confirm is not None:
            self._test_panel_slot_confirm_timer -= dt
            if self._test_panel_slot_confirm_timer <= 0:
                self._test_panel_slot_confirm = None
                self._test_panel_slot_confirm_timer = 0.0
