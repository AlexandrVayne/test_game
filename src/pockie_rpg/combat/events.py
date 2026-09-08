"""Combat events — event log for fight replay (Layer B).

Per §4.3: imports `config.EventType` only.
Per §9.3: FightValue mutable (filled by damage pipeline).

Stage 4 simplified: BEGIN_ATTACK, ATTACK, HIT, DIE events only.

Stage 10: added CANT_MOVE event (code 3 per §5.6) — emitted when a fighter
is frozen by Crystal Blade and skips their turn. Also added `is_frozen`
field on FightValue (1 = freeze succeeded, used by UI to trigger the
ice block overlay during replay).

Stage 10.1: added `dec_mp` field on FightValue — set to the MP cost deducted
from the attacker when a skill (Crystal Blade) triggers. The UI replay
reads this field to mirror the MP deduction on its runtime Fighter mirror
(Fighter.mp). Without this field, the UI's fighter.mp stayed at max even
after Crystal Blade triggers, so the MP bar never decreased.

Stage 13 (NEW): four new event types + FightValue fields for the 4 new skills:
  * CLOUD_STRIKE (22) — thunder_cloud tick damage at turn start. fv.role = the
    fighter that took damage (cloud target), fv.damage = tick damage dealt,
    fv.is_cloud_strike = 1. The caster is identified via the status params
    {"caster_role_id": int} stored on the cloud status.
  * POISON_DAMAGE (23) — poison DoT tick at turn start. fv.role = the poisoned
    fighter, fv.damage = tick damage (= 5% of max HP), fv.is_poison = 1.
  * SHIELD_APPLIED (24) — shield status applied (crystal_shield skill). fv.role
    = the shielded fighter, fv.is_shield = 1, fv.shield_absorbed = shield
    amount (initial, e.g., 300). UI can render a "shield dome" overlay.
  * FightValue.is_ranged (int) — 1 = ranged skill (no run forward, cast from
    position). UI skips AttackSequence RUN_FORWARD/RUN_BACK phases.
  * FightValue.is_self_buff (int) — 1 = self-buff skill (applies to attacker,
    not target). UI doesn't apply damage to the target.
  * FightValue.is_poison / is_cloud_strike / is_shield — markers for the new
    DoT / status-applied events (UI replay uses these to trigger overlays).
  * FightValue.shield_absorbed (int) — amount of damage absorbed by a shield
    on the most recent take_damage call (for UI feedback, e.g., a "blocked"
    damage number).

Stage 16.1 (BUGFIX — combat replay status sync):
  * FightValue.poison_applied / shield_applied / cloud_applied (int) — set to
    1 on the ATTACK FightValue when execute_skill applies the corresponding
    status. The UI replay reads these to MIRROR the status application onto
    its own runtime Fighter objects (which were cleared at replay start in
    _start_combat_replay). Without this mirror, EffectOverlays (shield dome,
    poison bubbles, storm cloud, ice block) NEVER activate in normal BATTLE
    mode — only the hardcoded Crystal Blade freeze was handled (now removed).
  * FightValue.cloud_duration (int) — the rolled thunder_cloud duration (2-4)
    set by execute_skill, so the UI applies the SAME duration the engine
    rolled (rather than a default of 3). The duration is randomized per cast
    in execute_skill via _compute_effect_duration, so it MUST be carried on
    the FightValue for the UI to mirror it exactly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class EventType(IntEnum):
    """Fight event types (per §5.6 — simplified subset).

    Stage 10 (NEW): CANT_MOVE = 3 — emitted when a fighter is frozen by
    Crystal Blade and skips their turn. Also emitted once immediately
    after the Crystal Blade ATTACK event to signal the freeze visually
    (ice block overlay appears on the frozen defender).

    Stage 12 (NEW): EXTRA_TURN_ATTACK = 21 — emitted when a fighter
    triggers Lightning Step (extra_turn effect) and attacks twice in a
    row. The FightSystem skips the next_atk_time increment for this turn
    so the same fighter is selected again next tick. The UI replay can
    use this to render a special "extra turn" indicator above the fighter.

    Stage 13 (NEW):
      * CLOUD_STRIKE = 22 — thunder_cloud tick damage (Грозовая туча).
        Emitted at the start of a fighter's turn if they have a
        "thunder_cloud" status. fv.role = the struck fighter, fv.damage
        = 0.6 × caster's base damage.
      * POISON_DAMAGE = 23 — poison DoT tick (Яд). Emitted at the start
        of a fighter's turn if they have a "poison" status. fv.role = the
        poisoned fighter, fv.damage = 5% of max HP.
      * SHIELD_APPLIED = 24 — shield status applied (Купол / Crystal Shield).
        Emitted when a fighter gains a "shield" status via crystal_shield.
        fv.role = the shielded fighter, fv.shield_absorbed = initial amount.
    """

    BEGIN_ATTACK = 1     # turn starts
    END_ATTACK = 2       # turn ends
    CANT_MOVE = 3        # Stage 10 — fighter is frozen, skips turn (per §5.6)
    ATTACK = 14          # main attack landed (USER_SKILL in §5.6)
    DIE = 20             # fighter died
    EXTRA_TURN_ATTACK = 21  # Stage 12 — Lightning Step, fighter attacks again
    CLOUD_STRIKE = 22    # Stage 13 — thunder_cloud tick damage
    POISON_DAMAGE = 23   # Stage 13 — poison DoT tick
    SHIELD_APPLIED = 24  # Stage 13 — shield status applied (Crystal Shield)
    FREEZE_EXPIRED = 26  # Stage 126 — freeze expired by global duration decrement


@dataclass(slots=True)
class FightValue:
    """One event in the fight log (mutable — filled by damage pipeline).

    Per §5.6 FightValue structure — simplified for Stage 4.
    Stage 10: added `is_frozen` field — set to 1 when Crystal Blade's
    freeze effect succeeds (used by the UI replay to trigger the ice
    block overlay on the defender).

    Stage 10.1: added `dec_mp` field — set to the MP cost deducted from
    the attacker when Crystal Blade triggers (e.g., 100 for Crystal Blade).
    The UI replay applies this to its runtime Fighter mirror
    (Fighter.mp = max(0, Fighter.mp - fv.dec_mp)) so the MP bar
    decreases correctly. Default 0 (no MP cost for basic attacks).

    Stage 13 (NEW):
      * is_ranged (int) — 1 = ranged skill (no run forward). UI replay
        plays the cast animation without RUN_FORWARD / RUN_BACK phases.
      * is_self_buff (int) — 1 = self-buff skill (effects apply to the
        attacker, not the target). UI replay doesn't apply damage to the
        target (skill.damage_multiplier may be 0.0).
      * is_poison (int) — 1 = poison DoT tick event (POISON_DAMAGE).
      * is_cloud_strike (int) — 1 = thunder cloud tick event (CLOUD_STRIKE).
      * is_shield (int) — 1 = shield status applied event (SHIELD_APPLIED).
      * shield_absorbed (int) — for ATTACK events: amount of damage absorbed
        by the target's shield on this strike (UI can show a "blocked"
        feedback). For SHIELD_APPLIED events: the initial shield amount.
    """

    role: int = 0                # 0 = player, 1 = enemy (attacker)
    target: int = 0              # 0 = player, 1 = enemy (defender)
    event: EventType = EventType.BEGIN_ATTACK
    damage: int = 0              # damage dealt to target
    is_hit: int = 0              # 1 = hit, 0 = miss/dodge
    is_crit: int = 0              # 1 = critical hit
    is_parry: int = 0            # 1 = parried (semi-implemented "Парри!" UI feature — readers in combat_replay; DO NOT remove)
    skill_name: str = ""          # display name (e.g., "Базовая атака")
    log_text: str = ""            # human-readable text for combat log
    is_frozen: int = 0           # Stage 10 — 1 = Crystal Blade freeze succeeded
    dec_mp: int = 0              # Stage 10.1 — MP cost deducted from attacker
    is_extra_turn: int = 0       # Stage 12 — 1 = Lightning Step extra turn granted
    # Stage 13 — ranged / self-buff / DoT / shield markers.
    is_ranged: int = 0           # 1 = ranged skill (no run forward)
    is_self_buff: int = 0        # 1 = self-buff (effects on attacker, not target)
    is_poison: int = 0           # 1 = poison DoT tick (POISON_DAMAGE event)
    is_cloud_strike: int = 0     # 1 = thunder cloud tick (CLOUD_STRIKE event)
    is_shield: int = 0           # 1 = shield status applied (SHIELD_APPLIED event)
    shield_absorbed: int = 0     # amount absorbed by shield (UI feedback)
    # Stage 16.1 — "applied" markers on the ATTACK FightValue. These signal
    # that the combat engine applied the corresponding status to a Fighter
    # during execute_skill, so the UI replay can MIRROR the application onto
    # its own runtime Fighter objects (which were cleared at replay start).
    # Without these markers + the UI mirror, the EffectOverlays never activate
    # in normal BATTLE mode (only Crystal Blade freeze was handled via a
    # hardcoded skill_name check — now removed in favor of these generic flags).
    #   * poison_applied: 1 = poison status applied to the DEFENDER.
    #   * shield_applied: 1 = shield status applied (to the ATTACKER for
    #     self-buff skills like Crystal Shield, or to the target otherwise).
    #   * cloud_applied: 1 = thunder_cloud status applied to the DEFENDER.
    #   * cloud_duration: the rolled duration (2-4) for thunder_cloud, so the
    #     UI applies the SAME duration the engine rolled (not a default).
    poison_applied: int = 0      # Stage 16.1 — poison status applied to defender
    shield_applied: int = 0      # Stage 16.1 — shield status applied
    cloud_applied: int = 0       # Stage 16.1 — thunder_cloud status applied to defender
    cloud_duration: int = 0      # Stage 16.1 — thunder_cloud duration (random 2-4)
    # Stage 125 — FREEZE_SHATTER marker on ATTACK events. Set to 1 when the
    # attack consumed (shattered) a freeze status on the target via the
    # damage_taken_multiplier mechanic. The UI replay reads this to trigger
    # the ice-block shatter animation in sync with the damage number.
    freeze_shattered: int = 0    # Stage 125 — 1 = freeze consumed by this attack


@dataclass
class FightSave:
    """Full fight log — list of FightValue events + winner."""

    values: list[FightValue] = field(default_factory=list)
    winner: int = -1              # 0 = player won, 1 = enemy won, -1 = draw
    total_rounds: int = 0

    def add(self, fv: FightValue) -> None:
        self.values.append(fv)

    def __len__(self) -> int:
        return len(self.values)
