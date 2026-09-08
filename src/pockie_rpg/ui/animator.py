"""Idle + attack-sequence animators for the UI."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pygame

from pockie_rpg.config import (
    ACTION_FPS,
    ATTACK_SEQ_ATTACK_DURATION,
    ATTACK_SEQ_RUN_FORWARD_DURATION,
    BLUE_SWORDSMAN_ACTION_BY_NAME,
    BLUE_SWORDSMAN_ACTIONS,
    BODY_SPRITE_H,
    BODY_SPRITE_W,
    ENEMY_ACTION_NAME_MAP,
    ICHIGO_ACTION_BY_NAME,
    ICHIGO_ACTIONS,
    IDLE_FPS,
    SAMURAI_ACTION_BY_NAME,
    SAMURAI_ACTIONS,
)
from pockie_rpg.ui.assets import AssetManager


@dataclass
class ClickRect:
    """A registered clickable rectangle on screen.

    Stage 150 — native: rect задан в НАТИВНЫХ координатах (Hi-DPI, ×UI_SCALE)
    мигрированным рендером; hit-тест сравнивает его с native-позицией мыши.
    По умолчанию False (legacy: дизайн-координаты 1280×720).

    Stage 174 — priority: rect проверяется ПЕРВЫМ в _handle_click (два прохода).
    Нужен HUD/модалкам, нарисованным ПОВЕРХ элементов карты: раньше побеждал
    первый совпавший rect (зарегистрированный раньше), и страж Лас Ночеса
    «съедал» клики трекера заданий, лежащего на его спрайте.
    """

    tag: str
    rect: pygame.Rect
    on_click: Callable[[], None]
    native: bool = False
    priority: bool = False


@dataclass(slots=True)
class AttackSequence:
    """Multi-phase attack sequence: RUN_FORWARD -> ATTACK -> RUN_BACK -> DONE.

    Position is linearly interpolated between phase endpoints. The animator
    (IdleAnimator) is owned by PygameUI; this dataclass tracks the position +
    phase + flip state. Damage info is captured at start and applied at the
    ATTACK midpoint by PygameUI._apply_attack_damage.

    For ranged skills (is_ranged=1), reach_x and strike_x are forced to
    base_x (no movement) and the RUN_FORWARD phase is skipped.
    """

    is_player: bool = True
    phase: str = "DONE"
    phase_timer: float = 0.0
    phase_duration: float = 0.0
    base_x: int = 0
    reach_x: int = 0
    strike_x: int = 0
    current_x: int = 0
    flip: bool = True
    pending_damage: int = 0
    pending_is_hit: int = 0
    pending_is_crit: int = 0
    pending_is_parry: int = 0  # Stage 50 — for floating "Парри!" text
    pending_log_text: str = ""
    damage_applied: bool = False
    pending_skill_name: str = ""
    pending_is_frozen: int = 0
    pending_is_ranged: int = 0
    pending_is_self_buff: int = 0
    pending_is_extra_turn: int = 0
    pending_poison_applied: int = 0
    pending_shield_applied: int = 0
    pending_cloud_applied: int = 0
    pending_cloud_duration: int = 0
    # Stage 188 — сколько щит движка поглотил на этом ударе (fv уже после
    # поглощения); зеркало списывает эту сумму со своего щита.
    pending_shield_absorbed: int = 0
    active: bool = False

    def start(
        self,
        is_player: bool,
        base_x: int,
        reach_x: int,
        strike_x: int,
        initial_flip: bool,
        damage: int = 0,
        is_hit: int = 0,
        is_crit: int = 0,
        is_parry: int = 0,
        log_text: str = "",
        skill_name: str = "",
        is_frozen: int = 0,
        is_ranged: int = 0,
        is_self_buff: int = 0,
        is_extra_turn: int = 0,
        poison_applied: int = 0,
        shield_applied: int = 0,
        cloud_applied: int = 0,
        cloud_duration: int = 0,
        shield_absorbed: int = 0,
    ) -> None:
        """Initialize a new attack sequence for the given attacker."""
        self.is_player = is_player
        self.base_x = base_x
        if is_ranged:
            self.reach_x = base_x
            self.strike_x = base_x
        else:
            self.reach_x = reach_x
            self.strike_x = strike_x
        self.current_x = base_x
        self.flip = initial_flip
        if is_ranged:
            self.phase = "ATTACK"
            self.phase_duration = ATTACK_SEQ_ATTACK_DURATION
        else:
            self.phase = "RUN_FORWARD"
            self.phase_duration = ATTACK_SEQ_RUN_FORWARD_DURATION
        self.phase_timer = 0.0
        self.pending_damage = damage
        self.pending_is_hit = is_hit
        self.pending_is_crit = is_crit
        self.pending_is_parry = is_parry
        self.pending_log_text = log_text
        self.pending_skill_name = skill_name
        self.pending_is_frozen = is_frozen
        self.pending_is_ranged = is_ranged
        self.pending_is_self_buff = is_self_buff
        self.pending_is_extra_turn = is_extra_turn
        self.pending_poison_applied = poison_applied
        self.pending_shield_applied = shield_applied
        self.pending_cloud_applied = cloud_applied
        self.pending_cloud_duration = cloud_duration
        self.pending_shield_absorbed = shield_absorbed
        self.damage_applied = False
        self.active = True

    def is_done(self) -> bool:
        """Return True when the sequence has reached DONE or PARKED.

        Stage 192 — PARKED: победитель остаётся у поверженного врага на всё
        время endgame; ранний return в _update_battle не должен блокировать
        endgame-апдейт, поэтому PARKED считается «готовой» фазой. Рендер при
        этом читает current_x (strike_x) — спрайт не телепортируется на базу.
        """
        return self.phase in ("DONE", "PARKED")

    def holds_position(self) -> bool:
        """Stage 192 — True пока рендер обязан читать current_x (не DONE).

        PARKED возвращает True: спрайт победителя стоит на strike_x у
        поверженного врага до самого выхода из боя.
        """
        return self.phase != "DONE"


@dataclass(slots=True)
class IdleAnimator:
    """Frame-cycling animator for one fighter with action state machine.

    Switches between action folders (idle/attack/run/hit/death/etc.) via
    set_action(). Death actions freeze on the last frame after one play.
    Player (Ichigo) and enemy (samurai) use different action maps.
    """

    folder: str
    flip: bool
    phase: float
    is_player: bool
    role_id: int = 0
    action: str = "idle"
    frame_index: int = 0
    frame_timer: float = 0.0
    frame_period: float = 1.0 / IDLE_FPS
    _frozen: bool = False
    idle_folder: str = ""

    def set_action(
        self,
        action_name: str,
        asset_manager: AssetManager,
    ) -> None:
        """Switch to a different action (idle/attack/hit/death/run)."""
        if action_name == self.action and self.folder:
            return

        new_folder: str = self.folder
        new_fps: int = ACTION_FPS.get(action_name, IDLE_FPS)

        if self.is_player:
            action_id = ICHIGO_ACTION_BY_NAME.get(action_name)
            if action_id is not None and action_id in ICHIGO_ACTIONS:
                new_folder = ICHIGO_ACTIONS[action_id]["folder"]
            else:
                new_folder = self.idle_folder or self.folder
        else:
            mapped_name = ENEMY_ACTION_NAME_MAP.get(action_name, action_name)
            if self.role_id == 10002:  # Blue Swordsman (Синий мечник)
                action_id = BLUE_SWORDSMAN_ACTION_BY_NAME.get(mapped_name)
                if action_id is not None and action_id in BLUE_SWORDSMAN_ACTIONS:
                    new_folder = BLUE_SWORDSMAN_ACTIONS[action_id]["folder"]
                else:
                    new_folder = self.idle_folder or self.folder
            elif self.role_id == 10004:  # Black Samurai (Черный самурай)
                from pockie_rpg.config import BLACK_SAMURAI_ACTION_BY_NAME, BLACK_SAMURAI_ACTIONS
                action_id = BLACK_SAMURAI_ACTION_BY_NAME.get(mapped_name)
                if action_id is not None and action_id in BLACK_SAMURAI_ACTIONS:
                    new_folder = BLACK_SAMURAI_ACTIONS[action_id]["folder"]
                else:
                    new_folder = self.idle_folder or self.folder
            elif self.role_id == 10102:  # Flower mob
                from pockie_rpg.config import FLOWER_ACTION_BY_NAME, FLOWER_ACTIONS
                action_id = FLOWER_ACTION_BY_NAME.get(mapped_name)
                if action_id is not None and action_id in FLOWER_ACTIONS:
                    new_folder = FLOWER_ACTIONS[action_id]["folder"]
                else:
                    new_folder = self.idle_folder or self.folder
            else:
                action_id = SAMURAI_ACTION_BY_NAME.get(mapped_name)
                if action_id is not None and action_id in SAMURAI_ACTIONS:
                    new_folder = SAMURAI_ACTIONS[action_id]["folder"]
                else:
                    new_folder = self.idle_folder or self.folder

        if self.is_player:
            new_flip = asset_manager.needs_flip_for_player(new_folder)
        else:
            new_flip = asset_manager.needs_flip_for_enemy(new_folder)

        self.folder = new_folder
        self.flip = new_flip
        self.action = action_name
        self.frame_index = 0
        self.frame_timer = 0.0
        self.frame_period = 1.0 / max(1, new_fps)
        self._frozen = False

    def set_flip(self, flip: bool) -> None:
        """Override the flip state at runtime (used by AttackSequence)."""
        self.flip = flip

    def update(self, dt: float, asset_manager: AssetManager) -> None:
        """Advance frame cycling. Death actions freeze on the last frame."""
        if self._frozen:
            return

        self.frame_timer += dt
        while self.frame_timer >= self.frame_period:
            self.frame_timer -= self.frame_period
            frame_count = asset_manager.get_motion_frame_count(self.folder)
            if frame_count == 0:
                return
            next_idx = self.frame_index + 1
            if next_idx >= frame_count:
                if self.action in ("death", "death_fall", "death_floor"):
                    self.frame_index = frame_count - 1
                    self._frozen = True
                    return
                next_idx = next_idx % frame_count
            self.frame_index = next_idx

    def get_breathing_offset(self) -> int:
        """Return 0 (programmatic breathing removed; SWF frames contain motion)."""
        return 0

    def get_sprite(self, asset_manager: AssetManager) -> pygame.Surface:
        """Return the current frame, scaled + flipped."""
        return asset_manager.get_motion_sprite(
            self.folder,
            self.frame_index,
            BODY_SPRITE_W,
            BODY_SPRITE_H,
            flip=self.flip,
        )
