"""Effect overlays: ice block, generic looping overlays, cast + projectile effects."""
from __future__ import annotations

from dataclasses import dataclass

import pygame

from pockie_rpg.config import (
    CAST_FIREBALL_FPS,
    CAST_FIREBALL_H,
    CAST_FIREBALL_W,
    CAST_FIREBALL_Y_OFFSET,
    CAST_POISON_FPS,
    CAST_POISON_H,
    CAST_POISON_W,
    CAST_POISON_Y_OFFSET,
    CAST_SHIELD_DOME_FPS,
    CAST_SHIELD_DOME_H,
    CAST_SHIELD_DOME_W,
    CAST_SHIELD_DOME_Y_OFFSET,
    CAST_STORM_CLOUD_FPS,
    CAST_STORM_CLOUD_H,
    CAST_STORM_CLOUD_W,
    CAST_STORM_CLOUD_Y_OFFSET,
    FIREBALL_OVERLAY_FOLDER,
    ICE_BLOCK_FOLDER,
    ICE_BLOCK_FPS,
    ICE_BLOCK_RENDER_H,
    ICE_BLOCK_RENDER_W,
    POISON_OVERLAY_FOLDER,
    SHIELD_DOME_FOLDER,
    STORM_CLOUD_FOLDER,
)
from pockie_rpg.ui.assets import AssetManager


class IceBlockEffect:
    """Ice block animation overlay rendered on top of a frozen fighter."""

    def __init__(self) -> None:
        self.frame_index: int = 0
        self.frame_timer: float = 0.0
        self.frame_period: float = 1.0 / max(1, ICE_BLOCK_FPS)
        self.active: bool = False
        self._frame_count: int = -1

    def activate(self, asset_manager: AssetManager) -> None:
        """Start the ice block animation. Idempotent."""
        if self._frame_count < 0:
            self._frame_count = asset_manager.get_motion_frame_count(ICE_BLOCK_FOLDER)
        if self._frame_count > 0 and not self.active:
            self.active = True
            self.frame_index = 0
            self.frame_timer = 0.0

    def deactivate(self) -> None:
        """Stop the ice block animation."""
        self.active = False
        self.frame_index = 0
        self.frame_timer = 0.0

    def update(self, dt: float, asset_manager: AssetManager) -> None:
        """Advance the frame cycling while the effect is active."""
        if not self.active:
            return
        if self._frame_count < 0:
            self._frame_count = asset_manager.get_motion_frame_count(ICE_BLOCK_FOLDER)
        if self._frame_count <= 0:
            self.active = False
            return
        self.frame_timer += dt
        while self.frame_timer >= self.frame_period:
            self.frame_timer -= self.frame_period
            self.frame_index = (self.frame_index + 1) % self._frame_count

    def render(
        self,
        screen: pygame.Surface,
        cx: int,
        cy: int,
        asset_manager: AssetManager,
        scale: float = 1.0,
    ) -> None:
        """Render the current ice block frame centered on (cx, cy).

        Stage 201 — ``scale``: размер спрайта эффекта ×scale (позиция (cx, cy)
        приходит уже в пространстве рендера от вызывающего).
        """
        if not self.active or self._frame_count <= 0:
            return
        sprite = asset_manager.get_motion_sprite(
            ICE_BLOCK_FOLDER,
            self.frame_index,
            max(1, int(round(ICE_BLOCK_RENDER_W * scale))),
            max(1, int(round(ICE_BLOCK_RENDER_H * scale))),
            flip=False,
            preserve_aspect=False,
        )
        rect = sprite.get_rect(center=(cx, cy))
        screen.blit(sprite, rect.topleft)


class EffectOverlay:
    """Generic looping overlay animation rendered on top of a fighter.

    Used for shield dome, storm cloud, and poison overlays. Activated when
    the corresponding status is applied; deactivated when the status expires.
    """

    def __init__(
        self,
        folder: str,
        fps: int,
        render_w: int,
        render_h: int,
    ) -> None:
        self.folder: str = folder
        self.fps: int = max(1, fps)
        self.render_w: int = render_w
        self.render_h: int = render_h
        self.frame_index: int = 0
        self.frame_timer: float = 0.0
        self.frame_period: float = 1.0 / self.fps
        self.active: bool = False
        self._frame_count: int = -1

    def activate(self, asset_manager: AssetManager) -> None:
        """Start the overlay animation. Idempotent."""
        if self._frame_count < 0:
            self._frame_count = asset_manager.get_motion_frame_count(self.folder)
        if self._frame_count > 0 and not self.active:
            self.active = True
            self.frame_index = 0
            self.frame_timer = 0.0

    def deactivate(self) -> None:
        """Stop the overlay animation."""
        self.active = False
        self.frame_index = 0
        self.frame_timer = 0.0

    def update(self, dt: float, asset_manager: AssetManager) -> None:
        """Advance frame cycling while active."""
        if not self.active:
            return
        if self._frame_count < 0:
            self._frame_count = asset_manager.get_motion_frame_count(self.folder)
        if self._frame_count <= 0:
            self.active = False
            return
        self.frame_timer += dt
        while self.frame_timer >= self.frame_period:
            self.frame_timer -= self.frame_period
            self.frame_index = (self.frame_index + 1) % self._frame_count

    def render(
        self,
        screen: pygame.Surface,
        cx: int,
        cy: int,
        asset_manager: AssetManager,
        scale: float = 1.0,
    ) -> None:
        """Render the current overlay frame centered on (cx, cy).

        Stage 201 — ``scale``: размер спрайта эффекта ×scale (позиция
        (cx, cy) приходит уже в пространстве рендера от вызывающего).
        """
        if not self.active or self._frame_count <= 0:
            return
        sprite = asset_manager.get_motion_sprite(
            self.folder,
            self.frame_index,
            max(1, int(round(self.render_w * scale))),
            max(1, int(round(self.render_h * scale))),
            flip=False,
            preserve_aspect=False,
        )
        rect = sprite.get_rect(center=(cx, cy))
        screen.blit(sprite, rect.topleft)


@dataclass
class CastEffect:
    """One-shot cast animation played when a skill triggers.

    Plays once then deactivates (no looping). The animation folder is set
    per-cast (via .start()), so the same instance can replay different
    skills' animations.
    """

    folder: str = ""
    active: bool = False
    frame_index: int = 0
    frame_timer: float = 0.0
    fps: int = 10
    render_w: int = 200
    render_h: int = 200
    target_x: int = 0
    target_y: int = 0
    _frame_count: int = -1

    def start(
        self,
        folder: str,
        x: int,
        y: int,
        asset_manager: AssetManager,
        fps: int = 10,
        render_w: int = 200,
        render_h: int = 200,
    ) -> None:
        """Activate a one-shot cast animation."""
        self.folder = folder
        self.target_x = x
        self.target_y = y
        self.fps = max(1, fps)
        self.render_w = render_w
        self.render_h = render_h
        self._frame_count = asset_manager.get_motion_frame_count(folder)
        if self._frame_count > 0:
            self.active = True
            self.frame_index = 0
            self.frame_timer = 0.0
        else:
            self.active = False

    def deactivate(self) -> None:
        """Stop the cast effect immediately."""
        self.active = False
        self.frame_index = 0
        self.frame_timer = 0.0

    def update(self, dt: float, asset_manager: AssetManager) -> None:
        """Advance the frame timer; play once then deactivate."""
        if not self.active:
            return
        if self._frame_count < 0:
            self._frame_count = asset_manager.get_motion_frame_count(self.folder)
        if self._frame_count <= 0:
            self.active = False
            return
        period = 1.0 / self.fps
        self.frame_timer += dt
        while self.frame_timer >= period:
            self.frame_timer -= period
            self.frame_index += 1
            if self.frame_index >= self._frame_count:
                self.active = False
                return

    def render(
        self,
        screen: pygame.Surface,
        asset_manager: AssetManager,
        scale: float = 1.0,
    ) -> None:
        """Render the current cast-effect frame centered on (target_x, target_y).

        Stage 201 — ``scale``: позиция и размер масштабируются при отрисовке
        (target_x/render_w остаются в дизайн-координатах).
        """
        if not self.active or self._frame_count <= 0:
            return
        sprite = asset_manager.get_motion_sprite(
            self.folder,
            self.frame_index,
            max(1, int(round(self.render_w * scale))),
            max(1, int(round(self.render_h * scale))),
            flip=False,
            preserve_aspect=False,
        )
        x = int(self.target_x * scale) - sprite.get_width() // 2
        y = int(self.target_y * scale) - sprite.get_height() // 2
        screen.blit(sprite, (x, y))


@dataclass
class ProjectileEffect:
    """Projectile animation that travels from start to end position.

    Used for fireball: starts at the caster, flies to the target, then
    explodes at the end (last 30% of frames anchored at the target).
    Plays once, then self-deactivates.
    """

    folder: str = ""
    active: bool = False
    frame_index: int = 0
    frame_timer: float = 0.0
    fps: int = 15
    render_w: int = 200
    render_h: int = 200
    start_x: int = 0
    start_y: int = 0
    end_x: int = 0
    end_y: int = 0
    _frame_count: int = -1
    flip: bool = False
    CAST_HOLD_FRAMES: int = 4

    def start(
        self,
        folder: str,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        asset_manager: AssetManager,
        fps: int = 15,
        render_w: int = 200,
        render_h: int = 200,
        flip: bool = False,
    ) -> None:
        """Activate a one-shot projectile animation."""
        self.folder = folder
        self.start_x = start_x
        self.start_y = start_y
        self.end_x = end_x
        self.end_y = end_y
        self.fps = max(1, fps)
        self.render_w = render_w
        self.render_h = render_h
        self.flip = flip
        self._frame_count = asset_manager.get_motion_frame_count(folder)
        if self._frame_count > 0:
            self.active = True
            self.frame_index = 0
            self.frame_timer = 0.0
        else:
            self.active = False

    def deactivate(self) -> None:
        """Stop the projectile effect immediately."""
        self.active = False
        self.frame_index = 0
        self.frame_timer = 0.0

    def update(self, dt: float, asset_manager: AssetManager) -> None:
        """Advance the frame timer; play once then deactivate."""
        if not self.active:
            return
        if self._frame_count < 0:
            self._frame_count = asset_manager.get_motion_frame_count(self.folder)
        if self._frame_count <= 0:
            self.active = False
            return
        period = 1.0 / self.fps
        self.frame_timer += dt
        while self.frame_timer >= period:
            self.frame_timer -= period
            self.frame_index += 1
            if self.frame_index >= self._frame_count:
                self.active = False
                return

    def render(
        self,
        screen: pygame.Surface,
        asset_manager: AssetManager,
        scale: float = 1.0,
    ) -> None:
        """Render the current projectile frame at the interpolated position.

        Phase 1 (frames 0..CAST_HOLD_FRAMES-1): anchored at caster position.
        Phase 2 (frames CAST_HOLD_FRAMES..N-2): linear travel from caster to target.
        Phase 3 (frame N-1): anchored at target (explosion).

        Stage 201 — ``scale``: позиция и размер масштабируются при отрисовке
        (start_x/end_x/render_w остаются в дизайн-координатах).
        """
        if not self.active or self._frame_count <= 0:
            return

        hold = min(self.CAST_HOLD_FRAMES, self._frame_count - 1)
        if self.frame_index < hold:
            x = self.start_x
            y = self.start_y
        elif self.frame_index < self._frame_count - 1:
            travel_frames = max(1, self._frame_count - 1 - hold)
            travel_progress = (self.frame_index - hold) / travel_frames
            x = int(self.start_x + (self.end_x - self.start_x) * travel_progress)
            y = int(self.start_y + (self.end_y - self.start_y) * travel_progress)
        else:
            x = self.end_x
            y = self.end_y

        sprite = asset_manager.get_motion_sprite(
            self.folder,
            self.frame_index,
            max(1, int(round(self.render_w * scale))),
            max(1, int(round(self.render_h * scale))),
            flip=self.flip,
            preserve_aspect=False,
        )
        blit_x = int(x * scale) - sprite.get_width() // 2
        blit_y = int(y * scale) - sprite.get_height() // 2
        screen.blit(sprite, (blit_x, blit_y))


_CAST_EFFECT_PARAMS: dict[int, tuple[str, int, int, int, int]] = {
    10001: (
        FIREBALL_OVERLAY_FOLDER,
        CAST_FIREBALL_FPS,
        CAST_FIREBALL_W,
        CAST_FIREBALL_H,
        CAST_FIREBALL_Y_OFFSET,
    ),
    14001: (
        STORM_CLOUD_FOLDER,
        CAST_STORM_CLOUD_FPS,
        CAST_STORM_CLOUD_W,
        CAST_STORM_CLOUD_H,
        CAST_STORM_CLOUD_Y_OFFSET,
    ),
    14002: (
        SHIELD_DOME_FOLDER,
        CAST_SHIELD_DOME_FPS,
        CAST_SHIELD_DOME_W,
        CAST_SHIELD_DOME_H,
        CAST_SHIELD_DOME_Y_OFFSET,
    ),
    18003: (
        POISON_OVERLAY_FOLDER,
        CAST_POISON_FPS,
        CAST_POISON_W,
        CAST_POISON_H,
        CAST_POISON_Y_OFFSET,
    ),
}


_CONTINUOUS_OVERLAY_FOLDERS: frozenset[str] = frozenset({
    SHIELD_DOME_FOLDER,
    POISON_OVERLAY_FOLDER,
    STORM_CLOUD_FOLDER,
})


_FIREBALL_SKILL_ID: int = 10001
