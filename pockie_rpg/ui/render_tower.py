"""TowerRendererMixin - Tower modal + shop + result rendering.

Extracted verbatim from render_map.py during the Stage 96 mixin refactor.
"""
from __future__ import annotations

import pygame

from pockie_rpg.config import SCREEN_HEIGHT, SCREEN_WIDTH
from pockie_rpg.ui.animator import ClickRect


class TowerRendererMixin:
    """Renders Tower modals: main Tower window + Tower Shop + battle result.

    Mixin: inherits ``self`` (screen, fonts, player, _click_rects,
    _mouse_pos, _tower_result, etc.) from the host PygameUI class.
    """

    def _render_tower_modal(self) -> None:
        """Stage 94 — render the Tower as a functional window.

        Shows: current floor + accumulated XP + Continue/Collect buttons.
        Compact design (not a full floor-list modal anymore).
        """
        from pockie_rpg.config import (
            MODAL_CONTENT_PADDING,
            TOWER_ACCENT,
            TOWER_BG,
            TOWER_BORDER,
            TOWER_BOSS_COLOR,
            TOWER_MAX_FLOOR,
            TOWER_SHARD_COLOR,
        )
        from pockie_rpg.data.tower_db import get_tower_boss, get_tower_floor

        pad = MODAL_CONTENT_PADDING
        modal_w = 420
        modal_h = 340
        modal_x = (SCREEN_WIDTH - modal_w) // 2
        modal_y = (SCREEN_HEIGHT - modal_h) // 2

        # Stage 165 — подложки больше НЕТ (блюр давал «резкую вспышку»):
        # окно Башни поверх НЕИЗМЕННОЙ живой сцены (как «Карта мира»/магазин).

        # Solid modal background.
        pygame.draw.rect(self.screen, TOWER_BG, (modal_x, modal_y, modal_w, modal_h), border_radius=12)
        pygame.draw.rect(self.screen, TOWER_BORDER, (modal_x, modal_y, modal_w, modal_h), 2, border_radius=12)
        pygame.draw.rect(self.screen, TOWER_BORDER, (modal_x, modal_y, modal_w, 6), border_radius=3)

        # Title.
        title = self.font_title.render("Башня", True, TOWER_BORDER)
        self.screen.blit(title, title.get_rect(center=(modal_x + modal_w // 2, modal_y + 36)))

        # Current floor info (center).
        cur_floor = self.player.tower_current_floor
        tf = get_tower_floor(cur_floor)
        is_boss = tf.is_boss if tf else False
        floor_text = f"Этаж {cur_floor} / {TOWER_MAX_FLOOR}"
        floor_color = TOWER_BOSS_COLOR if is_boss else TOWER_ACCENT
        floor_surf = self.font_title.render(floor_text, True, floor_color)
        self.screen.blit(floor_surf, floor_surf.get_rect(center=(modal_x + modal_w // 2, modal_y + 80)))

        # Enemy name.
        if tf is not None:
            from pockie_rpg.data.enemy_db import ENEMY_DB
            enemy_tmpl = ENEMY_DB.get(tf.enemy_id)
            enemy_name = enemy_tmpl.name if enemy_tmpl else tf.enemy_id
            if is_boss:
                boss = get_tower_boss(cur_floor)
                enemy_name = boss.display_name if boss else "БОСС"
            enemy_color = TOWER_BOSS_COLOR if is_boss else (180, 180, 200)
            enemy_surf = self.font_button.render(f"Противник: {enemy_name}", True, enemy_color)
            self.screen.blit(enemy_surf, enemy_surf.get_rect(center=(modal_x + modal_w // 2, modal_y + 115)))

        # Accumulated XP display.
        xp_text = f"Накоплено опыта: {self.player.tower_pending_xp}"
        xp_color = (80, 220, 100) if self.player.tower_pending_xp > 0 else (113, 113, 122)
        xp_surf = self.font_button.render(xp_text, True, xp_color)
        self.screen.blit(xp_surf, xp_surf.get_rect(center=(modal_x + modal_w // 2, modal_y + 155)))

        # Record + shards (small, below XP).
        record_text = f"Рекорд: {self.player.tower_highest_floor}/{TOWER_MAX_FLOOR}  ·  ◈ {self.player.tower_shards}"
        record_surf = self.font_small.render(record_text, True, TOWER_SHARD_COLOR)
        self.screen.blit(record_surf, record_surf.get_rect(center=(modal_x + modal_w // 2, modal_y + 185)))

        # Buttons: [Закрыть] (left) [Продолжить] (right) + [Получить] (center, if XP > 0).
        btn_w = 150
        btn_h = 40
        btn_y = modal_y + modal_h - btn_h - pad

        # Close button (left, red).
        close_x = modal_x + pad
        close_rect = pygame.Rect(close_x, btn_y, btn_w, btn_h)
        close_hover = close_rect.collidepoint(self._mouse_pos)
        close_bg = (220, 38, 38) if close_hover else (180, 30, 30)
        pygame.draw.rect(self.screen, close_bg, close_rect, border_radius=6)
        pygame.draw.rect(self.screen, (255, 255, 255), close_rect, 1, border_radius=6)
        close_lbl = self.font_button.render("Закрыть", True, (255, 255, 255))
        self.screen.blit(close_lbl, close_lbl.get_rect(center=close_rect.center))
        self._click_rects.append(ClickRect(tag="tower_close", rect=close_rect, on_click=self._close_tower))

        # Continue button (right, emerald).
        cont_x = modal_x + modal_w - pad - btn_w
        cont_rect = pygame.Rect(cont_x, btn_y, btn_w, btn_h)
        can_enter = self.player.can_enter_tower(cur_floor)
        cont_bg = TOWER_ACCENT if can_enter else (60, 60, 65)
        cont_text_col = (20, 20, 20) if can_enter else (150, 150, 155)
        cont_hover = cont_rect.collidepoint(self._mouse_pos) and can_enter
        if cont_hover:
            cont_bg = (80, 240, 180)
        pygame.draw.rect(self.screen, cont_bg, cont_rect, border_radius=6)
        pygame.draw.rect(self.screen, (255, 255, 255), cont_rect, 1, border_radius=6)
        cont_lbl = self.font_button.render("Продолжить", True, cont_text_col)
        self.screen.blit(cont_lbl, cont_lbl.get_rect(center=cont_rect.center))
        if can_enter:
            self._click_rects.append(ClickRect(tag="tower_continue", rect=cont_rect, on_click=self._tower_continue))

        # Claim XP button (center, if XP > 0).
        if self.player.tower_pending_xp > 0:
            claim_w = 150
            claim_x = modal_x + (modal_w - claim_w) // 2
            claim_y = btn_y - btn_h - 10
            claim_rect = pygame.Rect(claim_x, claim_y, claim_w, btn_h)
            claim_hover = claim_rect.collidepoint(self._mouse_pos)
            claim_bg = (250, 204, 21) if claim_hover else (234, 179, 8)
            pygame.draw.rect(self.screen, claim_bg, claim_rect, border_radius=6)
            pygame.draw.rect(self.screen, (255, 255, 255), claim_rect, 1, border_radius=6)
            claim_lbl = self.font_button.render("Получить", True, (20, 20, 20))
            self.screen.blit(claim_lbl, claim_lbl.get_rect(center=claim_rect.center))
            self._click_rects.append(ClickRect(tag="tower_claim_xp", rect=claim_rect, on_click=self._tower_claim_xp))

    def _render_tower_shop(self) -> None:
        """Render the Tower Shop sub-modal.

        Shows 5 material purchases (available) + 3 consumable placeholders
        (disabled). Per §8: disabled items show a "Скоро" tooltip and do not
        change state on click.
        """
        from pockie_rpg.config import (
            MODAL_CONTENT_PADDING,
            TOWER_BG,
            TOWER_BORDER,
            TOWER_SHARD_COLOR,
            TOWER_SHOP_MODAL_H,
            TOWER_SHOP_MODAL_W,
        )
        from pockie_rpg.data.tower_db import (
            TOWER_MATERIAL_ANCIENT,
            TOWER_MATERIAL_FIRE,
            TOWER_MATERIAL_ICE,
            TOWER_MATERIAL_LIGHTNING,
            TOWER_MATERIAL_SHADOW,
        )

        modal_w = TOWER_SHOP_MODAL_W
        modal_h = TOWER_SHOP_MODAL_H
        modal_x = (SCREEN_WIDTH - modal_w) // 2
        modal_y = (SCREEN_HEIGHT - modal_h) // 2
        pad = MODAL_CONTENT_PADDING

        # Stage 165 — подложки больше НЕТ: окно магазина Башни поверх живой сцены.

        pygame.draw.rect(self.screen, TOWER_BG, (modal_x, modal_y, modal_w, modal_h), border_radius=12)
        pygame.draw.rect(self.screen, TOWER_BORDER, (modal_x, modal_y, modal_w, modal_h), 2, border_radius=12)
        pygame.draw.rect(self.screen, TOWER_BORDER, (modal_x, modal_y, modal_w, 6), border_radius=3)

        title = self.font_title.render("Магазин Башни", True, TOWER_BORDER)
        # Stage 164 — заголовок по ЦЕНТРУ окна (как во всех окнах игры).
        self.screen.blit(title,
                         title.get_rect(midtop=(modal_x + modal_w // 2,
                                                modal_y + 14)))
        shards_text = f"◈ {self.player.tower_shards} осколков"
        shards_surf = self.font_button.render(shards_text, True, TOWER_SHARD_COLOR)
        self.screen.blit(shards_surf, (modal_x + modal_w - shards_surf.get_width() - pad, modal_y + 20))

        # Material items (available for purchase).
        materials = [
            ("Огненное ядро", TOWER_MATERIAL_FIRE, (220, 38, 38), "F", 100),
            ("Ледяное ядро", TOWER_MATERIAL_ICE, (80, 180, 240), "I", 100),
            ("Молниевое ядро", TOWER_MATERIAL_LIGHTNING, (234, 179, 8), "L", 100),
            ("Теневое ядро", TOWER_MATERIAL_SHADOW, (167, 139, 250), "S", 100),
            ("Древнее ядро", TOWER_MATERIAL_ANCIENT, (180, 180, 180), "A", 100),
        ]
        # Placeholder items (disabled).
        placeholders = [
            ("Малое зелье HP", "tower_potion_small", "Восстанавливает HP в Башне.", 150),
            ("Свиток попытки", "tower_scroll_retry", "Добавляет одну попытку Башни.", 300),
            ("Фрагмент костюма", "tower_outfit_fragment", "Заглушка — будет позже.", 500),
        ]

        row_y = modal_y + 60
        row_h = 44
        # Available materials.
        for name, mat_id, color, letter, cost in materials:
            self._render_tower_shop_row(
                modal_x, row_y, modal_w, row_h, name, mat_id,
                f"+1 {name}", cost, color, letter, available=True,
                on_click=lambda m=mat_id, c=cost: self._buy_tower_material(m, c),
            )
            row_y += row_h
        # Disabled placeholders.
        for name, key, desc, cost in placeholders:
            self._render_tower_shop_row(
                modal_x, row_y, modal_w, row_h, name, key,
                desc, cost, (63, 63, 70), "?", available=False,
                on_click=None,
            )
            row_y += row_h

        # Close button.
        btn_w = 140
        btn_h = 36
        close_x = modal_x + modal_w - pad - btn_w
        close_y = modal_y + modal_h - 50
        close_rect = pygame.Rect(close_x, close_y, btn_w, btn_h)
        close_hover = close_rect.collidepoint(self._mouse_pos)
        close_bg = (220, 38, 38) if close_hover else (180, 30, 30)
        pygame.draw.rect(self.screen, close_bg, close_rect, border_radius=6)
        pygame.draw.rect(self.screen, (255, 255, 255), close_rect, 1, border_radius=6)
        close_lbl = self.font_button.render("Закрыть", True, (255, 255, 255))
        self.screen.blit(close_lbl, close_lbl.get_rect(center=close_rect.center))
        self._click_rects.append(ClickRect(tag="tower_shop_close", rect=close_rect, on_click=self._close_tower_shop))

    def _render_tower_shop_row(
        self, modal_x: int, row_y: int, modal_w: int, row_h: int,
        name: str, item_key: str, description: str, cost: int,
        icon_color: tuple[int, int, int], icon_letter: str,
        available: bool, on_click,
    ) -> None:
        """Render a single Tower Shop row (material or placeholder)."""
        from pockie_rpg.config import MODAL_CONTENT_PADDING, TOWER_SHARD_COLOR
        pad = MODAL_CONTENT_PADDING
        row_rect = pygame.Rect(modal_x + pad, row_y, modal_w - 2 * pad, row_h)
        hover = row_rect.collidepoint(self._mouse_pos)
        if available:
            bg = (50, 50, 55) if hover else (40, 40, 45)
            border = (234, 179, 8) if hover else (63, 63, 70)
        else:
            bg = (28, 28, 32)
            border = (50, 50, 55)
        pygame.draw.rect(self.screen, bg, row_rect, border_radius=4)
        pygame.draw.rect(self.screen, border, row_rect, 1, border_radius=4)
        # Icon (colored square with letter).
        icon_size = 28
        icon_rect = pygame.Rect(row_rect.x + 6, row_rect.y + (row_h - icon_size) // 2, icon_size, icon_size)
        pygame.draw.rect(self.screen, icon_color, icon_rect, border_radius=4)
        letter_surf = self.font_button.render(icon_letter, True, (20, 20, 20))
        self.screen.blit(letter_surf, letter_surf.get_rect(center=icon_rect.center))
        # Name + description.
        name_color = (255, 255, 255) if available else (150, 150, 155)
        name_surf = self.font_small.render(name, True, name_color)
        self.screen.blit(name_surf, (row_rect.x + icon_size + 12, row_rect.y + 4))
        desc_color = (180, 180, 200) if available else (113, 113, 122)
        desc_surf = self.font_small.render(description, True, desc_color)
        self.screen.blit(desc_surf, (row_rect.x + icon_size + 12, row_rect.y + 22))
        # Cost + status (right-aligned).
        cost_text = f"{cost}◈"
        cost_color = TOWER_SHARD_COLOR if available else (113, 113, 122)
        cost_surf = self.font_small.render(cost_text, True, cost_color)
        self.screen.blit(cost_surf, (row_rect.right - cost_surf.get_width() - 8, row_rect.y + 4))
        status_text = "Доступно" if available else "Скоро"
        status_color = (80, 220, 100) if available else (113, 113, 122)
        status_surf = self.font_small.render(status_text, True, status_color)
        self.screen.blit(status_surf, (row_rect.right - status_surf.get_width() - 8, row_rect.y + 22))
        # Click handler (only for available items).
        if available and on_click is not None:
            self._click_rects.append(ClickRect(tag=f"tower_buy_{item_key}", rect=row_rect, on_click=on_click))

    def _render_tower_result(self) -> None:
        """Render the Tower battle result modal (shown after _exit_battle)."""
        from pockie_rpg.config import (
            MODAL_CONTENT_PADDING,
            TOWER_ACCENT,
            TOWER_BG,
            TOWER_BOSS_COLOR,
            TOWER_COMPLETED_COLOR,
            TOWER_SHARD_COLOR,
        )
        result = self._tower_result
        if result is None:
            return
        modal_w = 400
        modal_h = 360
        modal_x = (SCREEN_WIDTH - modal_w) // 2
        modal_y = (SCREEN_HEIGHT - modal_h) // 2
        pad = MODAL_CONTENT_PADDING

        # Stage 165 — подложки больше НЕТ: окно результата поверх живой сцены.

        pygame.draw.rect(self.screen, TOWER_BG, (modal_x, modal_y, modal_w, modal_h), border_radius=12)
        border_color = TOWER_ACCENT if result.get("victory") else (220, 38, 38)
        pygame.draw.rect(self.screen, border_color, (modal_x, modal_y, modal_w, modal_h), 2, border_radius=12)
        pygame.draw.rect(self.screen, border_color, (modal_x, modal_y, modal_w, 6), border_radius=3)

        # Title.
        floor = result.get("floor", 0)
        is_boss = result.get("is_boss", False)
        if result.get("victory"):
            title_text = f"Этаж {floor} пройден!"
            if is_boss:
                title_text = f"БОСС этажа {floor} повержен!"
        else:
            title_text = f"Этаж {floor} — поражение"
        title_surf = self.font_title.render(title_text, True, border_color)
        self.screen.blit(title_surf, title_surf.get_rect(center=(modal_x + modal_w // 2, modal_y + 50)))

        # Reward lines.
        row_y = modal_y + 100
        if result.get("victory"):
            # First clear badge.
            if result.get("first_clear"):
                fc_surf = self.font_button.render("★ Первый проход!", True, TOWER_BOSS_COLOR)
                self.screen.blit(fc_surf, fc_surf.get_rect(center=(modal_x + modal_w // 2, row_y)))
                row_y += 30
            # Gold.
            gold = result.get("gold", 0)
            if gold > 0:
                line = self.font_small.render(f"Золото: +{gold}", True, (234, 179, 8))
                self.screen.blit(line, (modal_x + pad + 40, row_y))
                row_y += 22
            # Shards.
            shards = result.get("shards", 0)
            if shards > 0:
                line = self.font_small.render(f"Осколки: +{shards} ◈", True, TOWER_SHARD_COLOR)
                self.screen.blit(line, (modal_x + pad + 40, row_y))
                row_y += 22
            # XP.
            xp = result.get("xp", 0)
            if xp > 0:
                line = self.font_small.render(f"Опыт: +{xp}", True, (80, 220, 100))
                self.screen.blit(line, (modal_x + pad + 40, row_y))
                row_y += 22
            # Materials.
            materials = result.get("materials", {})
            for mat_id, amt in materials.items():
                line = self.font_small.render(f"{mat_id}: +{amt}", True, (180, 180, 200))
                self.screen.blit(line, (modal_x + pad + 40, row_y))
                row_y += 22
            # Items.
            items = result.get("items", [])
            for item in items:
                line = self.font_small.render(f"Предмет: {item}", True, (180, 180, 200))
                self.screen.blit(line, (modal_x + pad + 40, row_y))
                row_y += 22
            # Level up.
            if result.get("leveled_up"):
                lu = self.font_button.render(f"Уровень повышен до {result.get('new_level')}!", True, TOWER_COMPLETED_COLOR)
                self.screen.blit(lu, lu.get_rect(center=(modal_x + modal_w // 2, row_y + 10)))
                row_y += 40
        else:
            # Defeat message.
            msg = self.font_small.render("Этаж не пройден. Попробуй улучшить снаряжение.", True, (220, 180, 180))
            self.screen.blit(msg, msg.get_rect(center=(modal_x + modal_w // 2, row_y + 20)))

        # OK button.
        btn_w = 140
        btn_h = 36
        ok_x = modal_x + (modal_w - btn_w) // 2
        ok_y = modal_y + modal_h - 50
        ok_rect = pygame.Rect(ok_x, ok_y, btn_w, btn_h)
        ok_hover = ok_rect.collidepoint(self._mouse_pos)
        ok_bg = (80, 240, 180) if ok_hover else TOWER_ACCENT
        pygame.draw.rect(self.screen, ok_bg, ok_rect, border_radius=6)
        pygame.draw.rect(self.screen, (255, 255, 255), ok_rect, 1, border_radius=6)
        ok_lbl = self.font_button.render("OK", True, (20, 20, 20))
        self.screen.blit(ok_lbl, ok_lbl.get_rect(center=ok_rect.center))
        self._click_rects.append(ClickRect(tag="tower_result_ok", rect=ok_rect, on_click=self._close_tower_result))
