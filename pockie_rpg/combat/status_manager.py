"""Status Manager — dynamic status effects on a fighter (Layer B).

Per Stage 11 refactor: replaces hardcoded `can_move`/`frozen_duration`
fields with a dynamic `status_effects` dict. Engine processes effects
generically at turn start (DoT, skip-turn) and turn end (decrement durations).

Supported statuses:
  - "frozen": skip turn (ice block). Duration = turns.
  - "stun": skip turn. Duration = turns.
  - "poison": DoT damage per turn. params: {"dmg_pct_max_hp": float} OR
    {"dmg_per_turn": int}. Decrement in on_turn_end.
  - "burn": DoT damage per turn. params: {"dmg_per_turn": int}.
  - "shield": absorbs damage. params: {"amount": int}. Decrement amount in
    Fighter.take_damage when absorbing; remove when amount <= 0. Decrement
    duration in on_turn_end (max turns active).
  - "thunder_cloud": DoT damage per turn + migration. params: {"caster_role_id":
    int, "cloud_dmg_multiplier": float}. Tick + decrement + migrate in
    on_turn_start (NOT on_turn_end — exempted via NO_END_DECREMENT_STATUSES).
  - "extra_turn": self-buff. Consume via consume_extra_turn (not decrement).
  - Future: "bleed", "paralyze", "silence", etc. — just add to SKIP_STATUSES
    or DOT_STATUSES.

Per §4.3: imports ONLY stdlib (no ui/config imports — pure data layer).

Stage 13 (NEW):
  * on_turn_start signature changed to:
      on_turn_start(fighter, opponent=None) -> list[FightValue]
    Now returns FightValue events (POISON_DAMAGE, CLOUD_STRIKE) instead of
    plain strings, so FightSystem can emit them directly to the fight log.
  * Added SHIELD_STATUSES + CLOUD_STATUSES categories.
  * thunder_cloud processed in on_turn_start: tick damage (0.6 × caster's
    base damage), decrement duration, 50% migration to opponent. Exempted
    from on_turn_end decrement (NO_END_DECREMENT_STATUSES) to avoid double-
    decrement.
  * poison DoT now supports dmg_pct_max_hp param (5% of max HP) in addition
    to the legacy dmg_per_turn.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pockie_rpg.combat.events import EventType, FightValue

if TYPE_CHECKING:
    from pockie_rpg.combat.fighter import Fighter


# Statuses that cause turn skip (fighter can't act).
# Note: "freeze" is the effect name (key in SkillDef.on_hit_effects).
# It's applied to StatusManager as status "freeze".
SKIP_STATUSES: tuple[str, ...] = ("freeze", "frozen", "stun", "paralyze")

# Statuses that deal damage-over-time at turn start.
DOT_STATUSES: tuple[str, ...] = ("poison", "burn")

# Statuses that grant an EXTRA TURN (fighter attacks again immediately).
# Stage 12 — "extra_turn" from Lightning Step skill. Applied to the ATTACKER
# (not the defender). When active, FightSystem skips the next_atk_time
# increment so the fighter keeps the lowest next_atk_time and gets selected
# again next tick. Duration is consumed (1 → 0) after the extra turn is used.
EXTRA_TURN_STATUSES: tuple[str, ...] = ("extra_turn",)

# Stage 13 — Statuses whose duration is managed in on_turn_start (NOT in
# on_turn_end) to avoid double-decrement. thunder_cloud is decremented
# during the tick in on_turn_start (per spec: "длительность уменьшается на 1"
# after the strike). If we also decremented in on_turn_end, the duration
# would tick twice per turn.
#
# Stage 125 — REVERTED Stage 122: freeze/frozen/stun/paralyze REMOVED from
# this set. They are now decremented normally by the fighter's OWN
# on_turn_end() (even during CANT_MOVE skip-turn). This removes the
# just_applied hack and the decrement_control_durations() side-channel.
# The freeze is removed in two ways:
#   1. SHATTER: when an attacker hits a frozen target (compute_attack
#      multiplies damage ×2.0 then calls status.remove("freeze")).
#   2. EXPIRE: when the frozen fighter's own turn comes (CANT_MOVE), they
#      skip the turn, on_turn_end() decrements freeze duration → 0 → removed.
#
# Stage 126 — REVERTED Stage 125: freeze/frozen/stun/paralyze ADDED BACK
# to this set. They are NO LONGER decremented by on_turn_end(). Instead,
# they are decremented by the GLOBAL _global_freeze_decrement() called on
# BOTH fighters at the end of EVERY turn. This implements the rule:
# "duration -= 1 in the end of ANY turn, regardless of who was the attacker."
# The just_applied flag skips the decrement on the turn of application.
NO_END_DECREMENT_STATUSES: frozenset[str] = frozenset({
    "thunder_cloud", "extra_turn",
    "freeze", "frozen", "stun", "paralyze",
})

# Chance that a thunder_cloud migrates to the opponent after each tick.
# Per spec: "50% шанс, что туча перелетит на другого персонажа".
THUNDER_CLOUD_MIGRATE_CHANCE: float = 0.50

# Stage 170 — defensive fallback for the cloud tick damage when the caster
# Fighter can't be resolved (no opponent / unknown role_id). Value kept from
# the former inline default (магическое число → именованная константа).
CLOUD_DMG_FALLBACK: int = 10


def _rand_int(lo: int, hi: int) -> int:
    """Inclusive random integer in [lo, hi]. Kept local to avoid circular
    import with combat.damage (which imports status_manager transitively
    via Fighter)."""
    if hi <= lo:
        return lo
    return random.randint(lo, hi)


@dataclass
class StatusEffect:
    """A single active status effect on a fighter.

    Stage 126 — `just_applied` flag: True when the status was applied during
    the CURRENT turn. Used by the GLOBAL decrement to skip the decrement on
    the turn the status was applied (so freeze duration=2 applied on turn N
    is NOT decremented until the END of turn N+1).
    """

    name: str               # "frozen", "poison", etc.
    duration: int           # turns remaining
    params: dict[str, object] = field(default_factory=dict)
    just_applied: bool = True  # Stage 126 — skip first global decrement


class StatusManager:
    """Manages all status effects on a single fighter.

    Replaces the old Fighter.can_move / Fighter.frozen_duration fields.
    The engine calls on_turn_start() and on_turn_end() each turn.
    """

    def __init__(self) -> None:
        self._effects: dict[str, StatusEffect] = {}

    # -----------------------------------------------------------------
    # Queries
    # -----------------------------------------------------------------

    def has(self, name: str) -> bool:
        """Check if a specific status is active."""
        return name in self._effects

    def can_act(self) -> bool:
        """Returns False if fighter has any skip-status (frozen/stun/paralyze)."""
        for skip_status in SKIP_STATUSES:
            if skip_status in self._effects:
                return False
        return True

    def has_extra_turn(self) -> bool:
        """Stage 12 — Returns True if fighter has an extra-turn pending."""
        for extra_status in EXTRA_TURN_STATUSES:
            if extra_status in self._effects:
                return True
        return False

    def consume_extra_turn(self) -> bool:
        """Stage 12 — Remove the extra_turn status. Returns True if consumed."""
        for extra_status in EXTRA_TURN_STATUSES:
            if extra_status in self._effects:
                del self._effects[extra_status]
                return True
        return False

    def get_active(self) -> list[str]:
        """Return list of all active status names (for UI debuff icons)."""
        return list(self._effects.keys())

    def get_effect(self, name: str) -> StatusEffect | None:
        """Get a specific StatusEffect (for params access)."""
        return self._effects.get(name)

    def get_duration(self, name: str) -> int:
        """Get remaining duration of a status (0 if not active)."""
        effect = self._effects.get(name)
        return effect.duration if effect else 0

    def set_duration(self, name: str, duration: int) -> None:
        """Forcefully set the duration of a status (apply if not present)."""
        if name not in self._effects:
            self._effects[name] = StatusEffect(name=name, duration=duration)
        else:
            self._effects[name].duration = duration

    # -----------------------------------------------------------------
    # Mutations
    # -----------------------------------------------------------------

    def apply(self, name: str, duration: int, params: dict | None = None) -> None:
        """Apply or refresh a status effect.

        If the status already exists with a longer duration, don't overwrite
        (don't refresh). If new duration is longer or status is new, apply.

        Stage 13 — for "shield" status: if the shield is being refreshed,
        we ADD to the existing amount (so a fresh cast doesn't overwrite a
        partially-depleted shield with the full initial amount — instead,
        the amounts stack: shield 200 + new cast 300 = 500). This is the
        INFERRED design choice for stacking shields (matches user expectation:
        "накладывает на себя статус shield (300)" — the new amount is added).
        """
        # Stage 13 — shield stacking: if a shield is already active and a new
        # shield is applied, ADD the amounts (defensive — player expects their
        # fresh cast to refresh the shield, not overwrite a depleted one).
        if name == "shield" and name in self._effects:
            existing = self._effects[name]
            existing_amount = existing.params.get("amount", 0)
            new_amount = (params or {}).get("amount", 0)
            existing.params["amount"] = existing_amount + new_amount
            # Refresh duration if new is longer.
            if duration > existing.duration:
                existing.duration = duration
            return
        if name in self._effects:
            existing = self._effects[name]
            # Only refresh if new duration is longer.
            if duration > existing.duration:
                existing.duration = duration
                if params:
                    existing.params = dict(params)
            return
        # Аудит 2026-09 — КОПИЯ params по значению: раньше dict хранился по
        # ссылке — combat_replay-данные мутировались при поглощении щита
        # (take_damage уменьшает params["amount"] на копии замка).
        self._effects[name] = StatusEffect(
            name=name, duration=duration, params=dict(params or {})
        )

    def clear(self) -> None:
        """Remove all statuses (used on death or battle reset)."""
        self._effects.clear()

    def remove(self, name: str) -> bool:
        """Remove a specific status. Returns True if it was present."""
        if name in self._effects:
            del self._effects[name]
            return True
        return False

    # -----------------------------------------------------------------
    # Stage 126 — GLOBAL freeze duration decrement
    # -----------------------------------------------------------------

    def decrement_freeze_durations(self) -> list[str]:
        """Stage 126 — Decrement ALL control debuff durations on THIS fighter.

        Called by FightSystem at the end of EVERY turn (both CANT_MOVE skip
        and normal attack), on BOTH fighters. This implements the rule:
        "duration -= 1 in the end of ANY turn in the while-loop, regardless
        of who was the attacker."

        just_applied handling:
          * If a control status was applied THIS turn (just_applied=True):
            reset the flag to False and DON'T decrement (the turn of
            application is not counted as a turn of waiting).
          * Else: duration -= 1; if 0, remove the status.

        Returns:
            list of expired status names (for event emission + log).
        """
        expired: list[str] = []
        for name in SKIP_STATUSES:
            effect = self._effects.get(name)
            if effect is None:
                continue
            if effect.just_applied:
                # Applied this turn — give it a full turn before first decrement.
                effect.just_applied = False
                continue
            effect.duration -= 1
            if effect.duration <= 0:
                expired.append(name)
                del self._effects[name]
        return expired

    # -----------------------------------------------------------------
    # Turn processing (called by FightSystem)
    # -----------------------------------------------------------------

    def on_turn_start(
        self,
        fighter: "Fighter",
        opponent: "Fighter | None" = None,
        apply_damage: bool = True,
    ) -> list[FightValue]:
        """Called at start of fighter's turn.

        Stage 13 — signature CHANGED: now takes `opponent` (needed for
        thunder_cloud migration + caster lookup) and returns a list of
        FightValue events (instead of plain strings). FightSystem emits
        these events directly to the fight log BEFORE the main attack.

        Stage 122 — DoT NOW TICKS EVEN IF FROZEN. Previously, on_turn_start
        returned early if the fighter had a skip-status (frozen/stun), which
        meant poison/burn didn't tick during freeze. Per user spec: "Если
        персонаж заморожен, он не должен атаковать, но яд на нем тикать обязан
        по стандартным правилам". Now DoT (poison/burn/thunder_cloud) ticks
        regardless of frozen status — the CANT_MOVE check is done AFTER
        on_turn_start in the fight loop.

        Stage 188 — «сухой» режим (apply_damage=False): длительности и события
        считаются, НО take_damage НЕ вызывается. Нужен UI-реплею: он вызывает
        on_turn_start на ЗЕРКАЛЕ бойца при обработке BEGIN_ATTACK, а сам урон
        приходит позже отдельным POISON_DAMAGE/CLOUD_STRIKE событием из лога —
        иначе тик срабатывал дважды (бар падал от яда вдвое быстрее движка).

        Processing order:
          1. Apply poison DoT (5% of max HP per spec). Emit POISON_DAMAGE.
          2. Apply burn DoT (legacy dmg_per_turn param). Emit POISON_DAMAGE
             (re-uses the same event type for DoT ticks — could add a
             BURN_DAMAGE event later if needed).
          3. Process thunder_cloud: tick damage (0.6 × caster's base damage,
             where caster is identified via status params["caster_role_id"]),
             decrement duration, 50% chance to migrate to opponent. Emit
             CLOUD_STRIKE.

        Args:
            fighter: the Fighter this status manager belongs to (for DoT).
            opponent: the opposing Fighter (for thunder_cloud migration +
                caster lookup). May be None in tests / standalone calls
                (cloud tick damage uses a fallback if caster can't be found).
            apply_damage: Stage 188 — False = dry-run (no take_damage; урон
                в событиях всё равно рассчитан, mirror-HP не трогается).

        Returns:
            list of FightValue events (POISON_DAMAGE, CLOUD_STRIKE) to emit
            to the fight log BEFORE the main attack this turn.
        """
        events: list[FightValue] = []

        # Stage 122 — REMOVED the early return for skip-statuses.
        # DoT (poison/burn/thunder_cloud) now ticks EVEN IF the fighter is
        # frozen. The CANT_MOVE check (skip attack) is handled by the
        # FightSystem AFTER on_turn_start returns.

        # --- Poison DoT ---
        # Per spec: "В начале каждого своего хода отравленный боец получает
        # урон в размере 5% от своего максимального HP." Stored in params
        # as {"dmg_pct_max_hp": 0.05}. Legacy format: {"dmg_per_turn": int}.
        poison = self._effects.get("poison")
        if poison is not None:
            dmg_pct = poison.params.get("dmg_pct_max_hp", 0.0)
            if dmg_pct > 0:
                dmg = int(fighter.max_hp * dmg_pct)
            else:
                dmg = int(poison.params.get("dmg_per_turn", 0))
            if dmg > 0:
                if apply_damage:
                    # Stage 88 — Fix 2.3: use the ACTUAL damage dealt (after shield
                    # absorption) instead of the nominal dmg. If the poisoned fighter
                    # has an active shield, take_damage absorbs part of the DoT and
                    # returns only the HP damage actually dealt. Showing the nominal
                    # value would make the damage number disagree with the HP bar.
                    actual = fighter.take_damage(dmg)
                else:
                    actual = dmg
                events.append(FightValue(
                    role=0 if fighter.is_player else 1,
                    target=0 if fighter.is_player else 1,
                    event=EventType.POISON_DAMAGE,
                    damage=actual,
                    shield_absorbed=fighter.shield_absorbed_last,
                    is_poison=1,
                    log_text=f"{fighter.name} получает {actual} урона от яда.",
                ))

        # --- Burn DoT (legacy support) ---
        burn = self._effects.get("burn")
        if burn is not None:
            dmg = int(burn.params.get("dmg_per_turn", 0))
            if dmg > 0:
                if apply_damage:
                    # Stage 88 — Fix 2.3: use actual damage (shield absorption).
                    actual = fighter.take_damage(dmg)
                else:
                    actual = dmg
                events.append(FightValue(
                    role=0 if fighter.is_player else 1,
                    target=0 if fighter.is_player else 1,
                    event=EventType.POISON_DAMAGE,
                    damage=actual,
                    shield_absorbed=fighter.shield_absorbed_last,
                    is_poison=1,
                    log_text=f"{fighter.name} получает {actual} урона от ожога.",
                ))

        # --- Thunder Cloud DoT + migration (Stage 13) ---
        # Per spec: "В начале хода каждого бойца, если у него активен статус
        # thunder_cloud: боец получает урон от удара молнией (0.6 от базового
        # урона автора тучи). Длительность тучи уменьшается на 1. Если
        # длительность > 0 — 50% шанс, что туча перелетит на оппонента."
        cloud = self._effects.get("thunder_cloud")
        if cloud is not None:
            cloud_dmg = self._compute_cloud_damage(fighter, opponent, cloud)
            actual = 0
            if cloud_dmg > 0:
                if apply_damage:
                    # Stage 88 — Fix 2.3: use actual damage (shield absorption).
                    actual = fighter.take_damage(cloud_dmg)
                else:
                    actual = cloud_dmg
                events.append(FightValue(
                    role=0 if fighter.is_player else 1,
                    target=0 if fighter.is_player else 1,
                    event=EventType.CLOUD_STRIKE,
                    damage=actual,
                    shield_absorbed=fighter.shield_absorbed_last,
                    is_cloud_strike=1,
                    log_text=(
                        f"{fighter.name} получает {actual} урона от удара "
                        f"молнии тучи."
                    ),
                ))
            # Decrement duration (per spec).
            cloud.duration -= 1
            if cloud.duration <= 0:
                # Cloud disappears.
                del self._effects["thunder_cloud"]
            elif opponent is not None and random.random() < THUNDER_CLOUD_MIGRATE_CHANCE:
                # Migrate to opponent: copy params (preserving caster info),
                # apply on opponent, remove from current fighter.
                # NOTE: we use a fresh params dict copy so the opponent's
                # status is independent (no shared mutable state).
                params_copy = dict(cloud.params)
                opponent.status.apply("thunder_cloud", cloud.duration, params_copy)
                del self._effects["thunder_cloud"]

        return events

    def _compute_cloud_damage(
        self,
        fighter: "Fighter",
        opponent: "Fighter | None",
        cloud: StatusEffect,
    ) -> int:
        """Compute the thunder_cloud tick damage (0.6 × caster's base damage).

        The caster is identified via cloud.params["caster_role_id"]. We look
        up the caster's Fighter (either fighter or opponent) to get their
        min_atk/max_atk for the random damage roll.

        If the caster can't be found (opponent is None or role_ids don't
        match), falls back to a fixed value stored in
        cloud.params["cloud_dmg_fallback"] (default 10) — INFERRED defensive
        fallback per rule 10 (no None / no crash).
        """
        caster_role_id = cloud.params.get("caster_role_id", 0)
        cloud_mult = float(cloud.params.get("cloud_dmg_multiplier", 0.6))
        caster: "Fighter | None" = None
        if opponent is not None:
            if fighter.role_id == caster_role_id:
                caster = fighter
            elif opponent.role_id == caster_role_id:
                caster = opponent
            # Аудит 2026-09 — раньше: caster = opponent (defensive fallback).
            # Если role_id не совпал ни с кем, урон считался от min/max_atk
            # САМОЙ ЖЕРТВЫ (била саму себя её же статами). Теперь caster
            # остаётся None → честный fallback cloud_dmg_fallback ниже.
        if caster is not None:
            base_dmg = _rand_int(caster.min_atk, caster.max_atk)
            return max(0, int(base_dmg * cloud_mult))
        # Fallback if no opponent / caster (defensive per rule 10).
        return int(cloud.params.get("cloud_dmg_fallback", CLOUD_DMG_FALLBACK))

    def on_turn_end(self) -> list[str]:
        """Called at end of fighter's turn. Decrements all durations
        (except NO_END_DECREMENT_STATUSES which are managed in on_turn_start).

        Returns list of expired status names (for log: "frozen растаял").
        """
        expired: list[str] = []
        for name in list(self._effects.keys()):
            # Stage 13 — skip statuses already decremented in on_turn_start
            # (thunder_cloud is decremented during its tick).
            if name in NO_END_DECREMENT_STATUSES:
                continue
            self._effects[name].duration -= 1
            if self._effects[name].duration <= 0:
                expired.append(name)
                del self._effects[name]
        return expired
