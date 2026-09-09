"""WorldBossRendererMixin — World Boss sprite + HP bar + click area on MAP.

Stage 96 — extracted from `render_map.py` (MapRendererMixin) as a focused
mixin so the parent module shrinks. The class has no `__init__`; it inherits
`self` (screen, font_small, player, _click_rects, _boss_anim_cache, etc.)
from PygameUI.

Stage 153 — Hi-DPI: босс рисуется ВНУТРИ `_render_map`, поэтому мигрирован
вместе с MAP: дизайн-координаты + `_su`/`_su_font`/`_su_scaled`.
"""
from __future__ import annotations

import math
import os
import time

import pygame

from pockie_rpg.config import HP_PULSE_FREQ_HZ, HP_PULSE_MAX, HP_PULSE_MIN
from pockie_rpg.ui.animator import ClickRect
from pockie_rpg.ui.render_map import _fmt_hp  # Stage 169 — одна реализация вместо копии


class WorldBossRendererMixin:
    """Renders the World Boss animated sprite + compact HP bar on the MAP screen."""

    def _get_boss_sprite(self) -> pygame.Surface:
        """Stage 74/75/78 — get the current boss animation frame.

        Uses the 8-frame idle animation extracted from n28007.s27786.swf.
        Cycles at ~6 FPS (matching idle animation speed).

        Stage 78 — frames pre-cached as convert_alpha() in __init__ (no lag).
        """
        if not hasattr(self, "_boss_anim_cache") or not self._boss_anim_cache:
            # Fallback to static sprite. Stage 153 — кэшируем (раньше
            # image.load выполнялся КАЖДЫЙ КАДР, если preload не удался).
            cached = getattr(self, "_boss_static_fallback", None)
            if cached is not None:
                return cached
            import os
            static_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                "assets", "icons", "character", "people_410_pose.png"
            )
            try:
                surf = pygame.image.load(static_path).convert_alpha()
            except Exception:
                surf = pygame.Surface((213, 228), pygame.SRCALPHA)
                surf.fill((180, 30, 30, 200))
            self._boss_static_fallback = surf
            return surf
        return self._boss_anim_cache[self._boss_anim_frame % len(self._boss_anim_cache)]

    def _preload_boss_anim(self) -> None:
        """Stage 78 — pre-load boss animation frames as convert_alpha().

        Called in __init__ to avoid lag on first render.
        """
        folder = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            "assets", "extracted", "world_boss", "idle"
        )
        self._boss_anim_cache = []
        self._boss_anim_timer = 0.0
        self._boss_anim_frame = 0
        for i in range(1, 9):
            path = os.path.join(folder, f"{i}.png")
            try:
                img = pygame.image.load(path).convert_alpha()
                self._boss_anim_cache.append(img)
            except Exception:
                pass

    def _update_boss_anim(self, dt: float) -> None:
        """Stage 74 — advance boss animation frame timer."""
        if not hasattr(self, "_boss_anim_cache") or not self._boss_anim_cache:
            return
        self._boss_anim_timer += dt
        frame_period = 1.0 / 6.0  # 6 FPS
        if self._boss_anim_timer >= frame_period:
            self._boss_anim_timer = 0.0
            self._boss_anim_frame = (self._boss_anim_frame + 1) % len(self._boss_anim_cache)

    def _render_world_boss_sprite_only(self, boss: dict) -> None:
        """Stage 74 — render boss sprite + HP bar WITHOUT click rect (during endgame).

        Stage 153 — Hi-DPI: дизайн-координаты + _su/_su_font/_su_scaled.
        """
        from pockie_rpg.config import (
            SPRITE_BASE_Y,
            WORLD_BOSS_MAP_SPRITE_X,
        )
        boss_img = self._get_boss_sprite()
        new_w, new_h = boss_img.get_size()
        boss_x = WORLD_BOSS_MAP_SPRITE_X
        boss_y = SPRITE_BASE_Y - new_h
        sprite = self._su_scaled(
            f"__boss_frame__:{getattr(self, '_boss_anim_frame', 0)}", boss_img, new_w, new_h,
        )
        # Shadow.
        shadow_surf = pygame.Surface((self._su(new_w), self._su(12)), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surf, (0, 0, 0, 100), shadow_surf.get_rect())
        self.screen.blit(shadow_surf, (self._su(boss_x - new_w // 2), self._su(SPRITE_BASE_Y - 6)))
        # Sprite.
        self.screen.blit(sprite, (self._su(boss_x - new_w // 2), self._su(boss_y)))
        # Flash.
        if hasattr(self, "_boss_flash_timer") and self._boss_flash_timer > 0:
            flash_alpha = int(120 * self._boss_flash_timer)
            flash_surf = pygame.Surface(sprite.get_size(), pygame.SRCALPHA)
            flash_surf.fill((255, 220, 80, flash_alpha))
            self.screen.blit(flash_surf, (self._su(boss_x - new_w // 2), self._su(boss_y)))
        # HP bar (compact — Stage 78: 200×14).
        bar_w = 200
        bar_h = 14
        bar_x = boss_x - bar_w // 2
        bar_y = boss_y - bar_h - 8
        bar_rect = self._su_rect(bar_x, bar_y, bar_w, bar_h)
        pygame.draw.rect(self.screen, (20, 20, 24), bar_rect, border_radius=3)
        pygame.draw.rect(self.screen, (60, 60, 65), bar_rect, self._su(1), border_radius=3)
        hp_pct = boss["current_hp"] / boss["max_hp"] if boss["max_hp"] > 0 else 0
        fill_w = int(bar_w * hp_pct)
        if hp_pct > 0.5:
            hp_color = (80, 220, 100)
        elif hp_pct > 0.25:
            hp_color = (234, 179, 8)
        else:
            hp_color = (220, 38, 38)
        if fill_w > 0:
            pygame.draw.rect(self.screen, hp_color,
                             self._su_rect(bar_x, bar_y, fill_w, bar_h), border_radius=3)
        # HP text — Stage 78/80: format as K via module-level _fmt_hp().
        hp_text = f"Lv.{boss.get('level', 1)}  {_fmt_hp(boss['current_hp'])}/{_fmt_hp(boss['max_hp'])}"
        hp_surf = self._su_font(13).render(hp_text, True, (255, 255, 255))
        self.screen.blit(hp_surf, hp_surf.get_rect(center=bar_rect.center))
        # attempts indicator for first occurrence — see lines below

    def _render_world_boss_on_map(self, boss: dict) -> None:
        """Stage 74 — render the World Boss animated sprite + compact HP bar.

        Stage 74 changes:
        - Uses 8-frame idle animation (extracted from n28007.s27786.swf).
        - HP bar reduced from 800×24 to 300×16 (compact, fits above sprite).
        - Flash effect on instant fight.
        - Click rect = sprite area.

        Stage 153 — Hi-DPI: дизайн-координаты + _su/_su_font/_su_scaled.
        """
        from pockie_rpg.config import (
            SPRITE_BASE_Y,
            WORLD_BOSS_MAP_SPRITE_X,
        )
        boss_img = self._get_boss_sprite()
        new_w, new_h = boss_img.get_size()
        # Position: right of center, standing on the ground.
        boss_x = WORLD_BOSS_MAP_SPRITE_X
        boss_y = SPRITE_BASE_Y - new_h
        sprite = self._su_scaled(
            f"__boss_frame__:{getattr(self, '_boss_anim_frame', 0)}", boss_img, new_w, new_h,
        )
        # Click rect = sprite area.
        boss_rect = self._su_rect(boss_x - new_w // 2, boss_y, new_w, new_h)
        # Shadow.
        shadow_surf = pygame.Surface((self._su(new_w), self._su(12)), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surf, (0, 0, 0, 100), shadow_surf.get_rect())
        self.screen.blit(shadow_surf, (self._su(boss_x - new_w // 2), self._su(SPRITE_BASE_Y - 6)))
        # Draw boss sprite (animated).
        self.screen.blit(sprite, (self._su(boss_x - new_w // 2), self._su(boss_y)))
        # Flash effect.
        if hasattr(self, "_boss_flash_timer") and self._boss_flash_timer > 0:
            flash_alpha = int(120 * self._boss_flash_timer)
            flash_surf = pygame.Surface(sprite.get_size(), pygame.SRCALPHA)
            flash_surf.fill((255, 220, 80, flash_alpha))
            self.screen.blit(flash_surf, (self._su(boss_x - new_w // 2), self._su(boss_y)))
        # Compact HP bar (Stage 78: 200×14, was 300×16).
        bar_w = 200
        bar_h = 14
        bar_x = boss_x - bar_w // 2
        bar_y = boss_y - bar_h - 8
        bar_rect = self._su_rect(bar_x, bar_y, bar_w, bar_h)
        pygame.draw.rect(self.screen, (20, 20, 24), bar_rect, border_radius=3)
        pygame.draw.rect(self.screen, (60, 60, 65), bar_rect, self._su(1), border_radius=3)
        hp_pct = boss["current_hp"] / boss["max_hp"] if boss["max_hp"] > 0 else 0
        fill_w = int(bar_w * hp_pct)
        if hp_pct > 0.5:
            hp_color = (80, 220, 100)
        elif hp_pct > 0.25:
            hp_color = (234, 179, 8)
        else:
            hp_color = (220, 38, 38)
            # Stage 87 — pulse when boss HP < 25% (same 1 Hz pattern as player HP).
            phase = (math.sin(self._hp_pulse_timer * 2.0 * math.pi * HP_PULSE_FREQ_HZ) + 1.0) * 0.5
            pulse_factor = HP_PULSE_MIN + (HP_PULSE_MAX - HP_PULSE_MIN) * phase
            hp_color = tuple(min(255, int(c * pulse_factor)) for c in hp_color)
        if fill_w > 0:
            pygame.draw.rect(self.screen, hp_color,
                             self._su_rect(bar_x, bar_y, fill_w, bar_h), border_radius=3)
        hp_text = f"Lv.{boss.get('level', 1)}  {_fmt_hp(boss['current_hp'])}/{_fmt_hp(boss['max_hp'])}"
        font = self._su_font(13)
        hp_surf = font.render(hp_text, True, (255, 255, 255))
        hp_x = bar_rect.x + (bar_rect.w - hp_surf.get_width()) // 2
        hp_y = bar_rect.y + (bar_rect.h - hp_surf.get_height()) // 2
        hp_outline = font.render(hp_text, True, (0, 0, 0))
        for ox, oy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            self.screen.blit(hp_outline, (hp_x + self._su(ox), hp_y + self._su(oy)))
        self.screen.blit(hp_surf, (hp_x, hp_y))
        # Attempts indicator + timer (Stage 77/78 — uses module-level `import time`).
        attempts = self.player.world_boss_attempts
        ts = getattr(self.player, "world_boss_next_attempt_ts", None)
        if attempts >= 3 or ts is None:
            attempts_text = f"Попытки: {attempts}/3"
            att_color = (80, 220, 100)
        elif attempts > 0:
            remaining = max(0, ts - time.time())
            mins = int(remaining) // 60
            secs = int(remaining) % 60
            attempts_text = f"Попытки: {attempts}/3 ({mins:02d}:{secs:02d})"
            att_color = (234, 179, 8)
        else:
            if ts is not None:
                remaining = max(0, ts - time.time())
                mins = int(remaining) // 60
                secs = int(remaining) % 60
                attempts_text = f"Попытки: 0/3 (+1 через {mins:02d}:{secs:02d})"
            else:
                attempts_text = "Попытки: 0/3"
            att_color = (220, 38, 38)
        att_surf = font.render(attempts_text, True, att_color)
        # Draw with outline for readability.
        outline_surf = font.render(attempts_text, True, (0, 0, 0))
        att_x = self._su(boss_x) - att_surf.get_width() // 2
        att_y = self._su(SPRITE_BASE_Y + 20)
        for ox, oy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            self.screen.blit(outline_surf, (att_x + self._su(ox), att_y + self._su(oy)))
        self.screen.blit(att_surf, (att_x, att_y))
        # Stage 76 — ALWAYS register click rect (even when attempts=0).
        # _enter_world_boss_fight handles the attempts check + auto-reset.
        self._click_rects.append(ClickRect(
            tag="enter_world_boss",
            rect=boss_rect,
            on_click=self._enter_world_boss_fight,
        ))
