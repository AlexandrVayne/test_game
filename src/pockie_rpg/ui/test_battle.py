"""TestBattleMixin — debug TEST_BATTLE state (manual skill trigger UI)."""
from __future__ import annotations

import math
import random

import pygame

from pockie_rpg.combat.damage import execute_skill
from pockie_rpg.combat.skill_registry import get_skill
from pockie_rpg.config import (
    BANNER_H,
    BANNER_TOP_INSET,
    BANNER_W,
    BATTLE_SPEED_DEFAULT,
    ENEMY_HIT_SHAKE_AMPLITUDE,
    ENEMY_SPRITE_X,
    HUD_DIVIDER_COLOR,
    HUD_HEIGHT,
    LOG_BAR_H,
    LOG_BG_ALPHA,
    LOG_BG_COLOR,
    PLAYER_SPRITE_X,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    TEST_BATTLE_INTRO_LOG,
    TEST_BATTLE_TRIGGER_LOG,
    TEST_EXIT_BTN_BG,
    TEST_EXIT_BTN_BG_HOVER,
    TEST_EXIT_BTN_FG,
    TEST_EXIT_BTN_H,
    TEST_EXIT_BTN_W,
    TEST_SKILL_BTN_BG,
    TEST_SKILL_BTN_BG_HOVER,
    TEST_SKILL_BTN_BORDER,
    TEST_SKILL_BTN_BORDER_HOVER,
    TEST_SKILL_BTN_COST_COLOR,
    TEST_SKILL_BTN_COST_FONT,
    TEST_SKILL_BTN_GAP,
    TEST_SKILL_BTN_NAME_COLOR,
    TEST_SKILL_BTN_NAME_FONT,
    TEST_SKILL_BTN_SIZE,
    TEST_SKILL_BTN_Y,
    TEXT_DIM,
    TEXT_WHITE,
    GameState,
)
from pockie_rpg.game.state import ENEMY_MOBS, ROLES, STARTER_SUITS
from pockie_rpg.ui.animator import ClickRect, IdleAnimator


class TestBattleMixin:
    """Debug TEST_BATTLE state: manual skill triggering + immortal enemy."""

    def _enter_test_battle(self) -> None:
        """Transition MAP -> TEST_BATTLE (debug mode)."""
        from pockie_rpg.combat.fighter import Fighter

        suit = STARTER_SUITS.get(self.player.suit_id)
        enemy = ENEMY_MOBS.get(self.target_mob_id)
        if suit is None or enemy is None:
            return

        player_role = ROLES.get(self.player.role_id)
        enemy_role = ROLES.get(enemy.role_id)
        if player_role is None or enemy_role is None:
            return

        self._player_fighter = Fighter.from_role(
            player_role,
            is_player=True,
            level=self.player.level,
            skills=player_role.skills,
        )
        self._enemy_fighter = Fighter.from_role(
            enemy_role,
            is_player=False,
            level=enemy.level,
            hp_mul=enemy.hp_mul,
            atk_mul=enemy.atk_mul,
        )

        player_flip = self.asset_manager.needs_flip_for_player(suit.motion_folder)
        self._player_animator = IdleAnimator(
            folder=suit.motion_folder,
            flip=player_flip,
            phase=0.0,
            is_player=True,
            action="idle",
            idle_folder=suit.motion_folder,
        )
        enemy_motion_folder = "samurai_idle"
        enemy_flip = self.asset_manager.needs_flip_for_enemy(
            enemy_motion_folder, mob_id=enemy.mob_id
        )
        self._enemy_animator = IdleAnimator(
            folder=enemy_motion_folder,
            flip=enemy_flip,
            phase=math.pi,
            is_player=False,
            action="idle",
            idle_folder=enemy_motion_folder,
        )

        self._player_hp_display = float(self._player_fighter.hp)
        self._player_mp_display = float(self._player_fighter.mp)
        self._enemy_hp_display = float(self._enemy_fighter.hp)
        self._enemy_mp_display = float(self._enemy_fighter.mp)

        self._active_attack_seq = None
        self._player_hit_timer = 0.0
        self._enemy_hit_timer = 0.0
        self._enemy_shake_timer = 0.0

        self._countdown_active = False
        self._countdown_timer = 0.0
        self._countdown_phase_idx = 0

        self._combat_replay = None
        self._replay_event_idx = 0
        self._replay_timer = 0.0
        self._endgame_active = False
        self._endgame_text = ""
        self._endgame_phase = "text"
        self._endgame_text_timer = 0.0

        self._combat_log_lines.clear()
        self._combat_log_expanded = False
        self._combat_log_height_display = float(LOG_BAR_H)
        self._speed_buttons_y_offset = 0.0
        self._add_log_line(TEST_BATTLE_INTRO_LOG)

        self._char_sheet_open = False
        self._char_sheet_closing = False
        self._char_sheet_anim_t = 0.0
        self._char_sheet_origin = "left"

        self._battle_speed = float(BATTLE_SPEED_DEFAULT)
        self._particles.clear()
        self._damage_numbers.clear()
        self._player_ice.deactivate()
        self._enemy_ice.deactivate()
        self._player_shield.deactivate()
        self._enemy_shield.deactivate()
        self._player_cloud.deactivate()
        self._enemy_cloud.deactivate()
        self._player_poison.deactivate()
        self._enemy_poison.deactivate()
        self._cast_effect.deactivate()
        self._projectile_effect.deactivate()

        # Stage 161 — F9-бой тоже показывает блюр экрана локации вокруг окна.
        self._capture_battle_bg_snapshot()
        self.state = GameState.TEST_BATTLE

    def _exit_test_battle(self) -> None:
        """Transition TEST_BATTLE -> MAP."""

        self.state = GameState.MAP
        self._player_animator = None
        self._enemy_animator = None
        self._player_fighter = None
        self._enemy_fighter = None
        self._active_attack_seq = None
        self._player_hit_timer = 0.0
        self._enemy_hit_timer = 0.0
        self._enemy_shake_timer = 0.0
        self._countdown_active = False
        self._countdown_timer = 0.0
        self._countdown_phase_idx = 0
        self._combat_replay = None
        self._replay_event_idx = 0
        self._replay_timer = 0.0
        self._endgame_active = False
        self._endgame_text = ""
        self._endgame_phase = "text"
        self._endgame_text_timer = 0.0
        self._combat_log_lines.clear()
        self._combat_log_expanded = False
        self._combat_log_height_display = float(LOG_BAR_H)
        self._speed_buttons_y_offset = 0.0
        self._char_sheet_open = False
        self._char_sheet_closing = False
        self._char_sheet_anim_t = 0.0
        self._char_sheet_origin = "left"

        self._battle_speed = float(BATTLE_SPEED_DEFAULT)
        self._particles.clear()
        self._damage_numbers.clear()
        self._player_ice.deactivate()
        self._enemy_ice.deactivate()
        self._player_shield.deactivate()
        self._enemy_shield.deactivate()
        self._player_cloud.deactivate()
        self._enemy_cloud.deactivate()
        self._player_poison.deactivate()
        self._enemy_poison.deactivate()
        self._cast_effect.deactivate()
        self._projectile_effect.deactivate()

    def _update_test_battle(self, dt: float) -> None:
        """Per-frame update for TEST_BATTLE state."""
        speed_dt = dt * self._battle_speed

        if self._player_animator is not None:
            self._player_animator.update(speed_dt, self.asset_manager)
        if self._enemy_animator is not None:
            self._enemy_animator.update(speed_dt, self.asset_manager)

        if self._active_attack_seq is not None:
            self._update_attack_sequence(speed_dt)

        if self._player_hit_timer > 0.0:
            self._player_hit_timer = max(0.0, self._player_hit_timer - speed_dt)
            if self._player_hit_timer == 0.0 and self._player_animator is not None:
                if (
                    self._player_fighter is not None
                    and self._player_fighter.is_alive
                    and not (self._active_attack_seq is not None and self._active_attack_seq.is_player)
                ):
                    self._player_animator.set_action("idle", self.asset_manager)
        if self._enemy_hit_timer > 0.0:
            self._enemy_hit_timer = max(0.0, self._enemy_hit_timer - speed_dt)
            if self._enemy_hit_timer == 0.0 and self._enemy_animator is not None:
                if (
                    self._enemy_fighter is not None
                    and self._enemy_fighter.is_alive
                    and not (self._active_attack_seq is not None and not self._active_attack_seq.is_player)
                ):
                    self._enemy_animator.set_action("idle", self.asset_manager)
        if self._enemy_shake_timer > 0.0:
            self._enemy_shake_timer = max(0.0, self._enemy_shake_timer - speed_dt)

        self._update_hp_mp_display(speed_dt)

        self._particles.update(speed_dt)
        self._damage_numbers.update(speed_dt)
        self._player_ice.update(speed_dt, self.asset_manager)
        self._enemy_ice.update(speed_dt, self.asset_manager)
        self._sync_effect_overlays()
        self._player_shield.update(speed_dt, self.asset_manager)
        self._enemy_shield.update(speed_dt, self.asset_manager)
        self._player_cloud.update(speed_dt, self.asset_manager)
        self._enemy_cloud.update(speed_dt, self.asset_manager)
        self._player_poison.update(speed_dt, self.asset_manager)
        self._enemy_poison.update(speed_dt, self.asset_manager)
        self._cast_effect.update(speed_dt, self.asset_manager)
        self._projectile_effect.update(speed_dt, self.asset_manager)

        if self._player_fighter is not None:
            self._player_fighter.mp = self._player_fighter.max_mp

        if self._enemy_fighter is not None:
            if self._enemy_fighter.hp < 1 or not self._enemy_fighter.is_alive:
                self._enemy_fighter.hp = self._enemy_fighter.max_hp
                self._enemy_fighter.is_alive = True

    def _render_test_battle(self) -> None:
        """Render TEST_BATTLE state (skill buttons + exit btn + log)."""
        from pockie_rpg.config import BATTLE_BACKGROUND

        bg = self.asset_manager.get_background(BATTLE_BACKGROUND)
        self.screen.blit(bg, (0, 0))

        self._render_hud()
        self._render_side_banners()

        player_seq = (
            self._active_attack_seq
            if (self._active_attack_seq is not None and self._active_attack_seq.is_player)
            else None
        )
        enemy_seq = (
            self._active_attack_seq
            if (self._active_attack_seq is not None and not self._active_attack_seq.is_player)
            else None
        )
        enemy_shake = 0
        if self._enemy_shake_timer > 0.0:
            enemy_shake = random.randint(
                -ENEMY_HIT_SHAKE_AMPLITUDE, ENEMY_HIT_SHAKE_AMPLITUDE
            )
        self._render_fighter(
            self._player_animator,
            PLAYER_SPRITE_X,
            is_player=True,
            attack_seq=player_seq,
            shake_offset=0,
        )
        self._render_fighter(
            self._enemy_animator,
            ENEMY_SPRITE_X,
            is_player=False,
            attack_seq=enemy_seq,
            shake_offset=enemy_shake,
        )

        self._particles.render(self.screen)
        self._damage_numbers.render(self.screen)
        self._cast_effect.render(self.screen, self.asset_manager)
        self._projectile_effect.render(self.screen, self.asset_manager)

        self._click_rects = []

        self._render_test_skill_buttons()
        self._render_test_exit_button()

        if not self._char_sheet_open:
            banner_top = HUD_HEIGHT + BANNER_TOP_INSET
            banner_h = BANNER_H
            left_banner = pygame.Rect(0, banner_top, BANNER_W, banner_h)
            right_banner = pygame.Rect(
                SCREEN_WIDTH - BANNER_W, banner_top, BANNER_W, banner_h
            )
            self._click_rects.append(
                ClickRect(
                    tag="open_player_sheet",
                    rect=left_banner,
                    on_click=lambda: self._open_char_sheet("player", "left"),
                )
            )
            self._click_rects.append(
                ClickRect(
                    tag="open_enemy_sheet",
                    rect=right_banner,
                    on_click=lambda: self._open_char_sheet("enemy", "right"),
                )
            )

        h = int(self._combat_log_height_display)
        log_rect = pygame.Rect(0, SCREEN_HEIGHT - h, SCREEN_WIDTH, h)
        log_surf = pygame.Surface((SCREEN_WIDTH, h), pygame.SRCALPHA)
        log_surf.fill((LOG_BG_COLOR[0], LOG_BG_COLOR[1], LOG_BG_COLOR[2], LOG_BG_ALPHA))
        self.screen.blit(log_surf, log_rect.topleft)
        pygame.draw.line(
            self.screen,
            HUD_DIVIDER_COLOR,
            (0, log_rect.top),
            (SCREEN_WIDTH, log_rect.top),
            1,
        )
        if self._combat_log_lines:
            recent_line = self._combat_log_lines[-1]
            text_surf = self.font_small.render(recent_line, True, TEXT_WHITE)
            text_rect = text_surf.get_rect(center=(SCREEN_WIDTH // 2, log_rect.centery))
            self.screen.blit(text_surf, text_rect)
        esc_surf = self.font_small.render("ESC — выход из теста", True, TEXT_DIM)
        self.screen.blit(
            esc_surf,
            (
                SCREEN_WIDTH - esc_surf.get_width() - 16,
                log_rect.centery - esc_surf.get_height() // 2,
            ),
        )

    def _render_test_skill_buttons(self) -> None:
        """Render the skill buttons row at the center of the screen."""
        player_role = ROLES.get(self.player.role_id)
        if player_role is None:
            return
        skill_ids = list(player_role.skills)
        if not skill_ids:
            return

        btn_size = TEST_SKILL_BTN_SIZE
        gap = TEST_SKILL_BTN_GAP
        n = len(skill_ids)
        row_w = n * btn_size + (n - 1) * gap
        row_x = (SCREEN_WIDTH - row_w) // 2
        row_y = TEST_SKILL_BTN_Y

        # Аудит 2026-09 — SysFont × 2 каждый кадр → кэш _su_font
        # (ключ включает размер — legacy/nativ не сталкиваются).
        name_font = self._su_font(TEST_SKILL_BTN_NAME_FONT, bold=True)
        cost_font = self._su_font(TEST_SKILL_BTN_COST_FONT)

        for i, skill_id in enumerate(skill_ids):
            skill = get_skill(skill_id)
            if skill is None:
                continue
            btn_x = row_x + i * (btn_size + gap)
            btn_rect = pygame.Rect(btn_x, row_y, btn_size, btn_size)
            is_hover = btn_rect.collidepoint(self._mouse_pos)

            bg_color = TEST_SKILL_BTN_BG_HOVER if is_hover else TEST_SKILL_BTN_BG
            border_color = (
                TEST_SKILL_BTN_BORDER_HOVER if is_hover else TEST_SKILL_BTN_BORDER
            )
            pygame.draw.rect(self.screen, bg_color, btn_rect, border_radius=8)
            pygame.draw.rect(self.screen, border_color, btn_rect, 2, border_radius=8)

            icon = self.asset_manager.get_skill_icon(skill_id, btn_size - 8)
            icon_x = btn_x + (btn_size - icon.get_width()) // 2
            icon_y = row_y + 4
            self.screen.blit(icon, (icon_x, icon_y))

            name_surf = name_font.render(skill.name, True, TEST_SKILL_BTN_NAME_COLOR)
            name_x = btn_x + (btn_size - name_surf.get_width()) // 2
            name_y = row_y + btn_size + 2
            self.screen.blit(name_surf, (name_x, name_y))

            cost_text = f"{skill.mp_cost} MP"
            cost_surf = cost_font.render(cost_text, True, TEST_SKILL_BTN_COST_COLOR)
            cost_x = btn_x + (btn_size - cost_surf.get_width()) // 2
            cost_y = name_y + name_surf.get_height()
            self.screen.blit(cost_surf, (cost_x, cost_y))

            def _on_click(_sid: int = skill_id) -> None:
                self._trigger_test_skill(_sid)
            self._click_rects.insert(
                0,
                ClickRect(
                    tag=f"test_skill_{skill_id}",
                    rect=btn_rect,
                    on_click=_on_click,
                )
            )

    def _render_test_exit_button(self) -> None:
        """Render the 'ВЫЙТИ' exit button at the top-right of the screen."""
        btn_x = SCREEN_WIDTH - BANNER_W - 16 - TEST_EXIT_BTN_W
        btn_y = HUD_HEIGHT + 12
        btn_rect = pygame.Rect(btn_x, btn_y, TEST_EXIT_BTN_W, TEST_EXIT_BTN_H)
        is_hover = btn_rect.collidepoint(self._mouse_pos)
        bg_color = TEST_EXIT_BTN_BG_HOVER if is_hover else TEST_EXIT_BTN_BG
        pygame.draw.rect(self.screen, bg_color, btn_rect, border_radius=8)
        pygame.draw.rect(self.screen, (255, 255, 255), btn_rect, 2, border_radius=8)
        text_surf = self.font_button.render("ВЫЙТИ", True, TEST_EXIT_BTN_FG)
        text_rect = text_surf.get_rect(center=btn_rect.center)
        self.screen.blit(text_surf, text_rect.topleft)
        self._click_rects.insert(
            0,
            ClickRect(
                tag="test_exit",
                rect=btn_rect,
                on_click=self._exit_test_battle,
            )
        )

    def _trigger_test_skill(self, skill_id: int) -> None:
        """Trigger a skill in TEST_BATTLE mode (called when user clicks)."""
        if self._player_fighter is None or self._enemy_fighter is None:
            return
        skill = get_skill(skill_id)
        if skill is None:
            return

        self._active_attack_seq = None

        if self._player_fighter.mp >= skill.mp_cost:
            self._player_fighter.mp -= skill.mp_cost

        pre_skill_enemy_hp = self._enemy_fighter.hp
        pre_skill_enemy_alive = self._enemy_fighter.is_alive

        fv = execute_skill(skill, self._player_fighter, self._enemy_fighter)

        self._enemy_fighter.hp = pre_skill_enemy_hp
        self._enemy_fighter.is_alive = pre_skill_enemy_alive

        log_text = fv.log_text or ""
        if log_text:
            log_text = TEST_BATTLE_TRIGGER_LOG + log_text
        attack_info = {
            "damage": fv.damage,
            "is_hit": fv.is_hit,
            "is_crit": fv.is_crit,
            "log_text": log_text,
            "skill_name": skill.name,
            "is_frozen": fv.is_frozen,
            "is_ranged": fv.is_ranged,
            "is_self_buff": fv.is_self_buff,
            "is_extra_turn": fv.is_extra_turn,
            "poison_applied": fv.poison_applied,
            "shield_applied": fv.shield_applied,
            "cloud_applied": fv.cloud_applied,
            "cloud_duration": fv.cloud_duration,
        }
        self._start_attack_sequence(0, attack_info)
