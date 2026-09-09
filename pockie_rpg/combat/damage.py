"""Damage pipeline + skill execution (combat layer)."""
from __future__ import annotations

import random

from pockie_rpg.combat.events import EventType, FightValue
from pockie_rpg.combat.fighter import Fighter
from pockie_rpg.combat.skill_registry import SkillDef, get_skill


def rand_int(lo: int, hi: int) -> int:
    """Inclusive random integer in [lo, hi]."""
    if hi <= lo:
        return lo
    return random.randint(lo, hi)


def get_damage(attacker: Fighter) -> int:
    """Base damage roll: rand_int(min_atk, max_atk) inclusive."""
    return rand_int(attacker.min_atk, attacker.max_atk)


def get_hit(attacker: Fighter, target: Fighter) -> int:
    """Stage 103 — Pockie Ninja original hit chance formula.

    Final_Hit% = 100 - (Defender_Dodge% - Attacker_Hit%)
              = 100 - Defender_Dodge% + Attacker_Hit%

    Where each rating unit = 0.0625% (1/16 step). Ratings are flat integers
    with NO CAP, so percentages CAN exceed 100% (overcap is allowed).

    Hard caps (per task spec):
        HIT_FLOOR_PCT = 5%  (defender can NEVER fully evade — always 5% leak)
        HIT_CAP_PCT   = 100% (no overflow above guaranteed hit)

    The ``attacker.hit_chance`` and ``target.dodge_chance`` fields store
    RATINGS (int, no cap), NOT percentages. They are computed in
    Fighter.from_role / from_player_state via:
        Hit_Rating   = floor(STR / bmv_price_str) + flat_gear_hit - STR_THRESHOLD
        Dodge_Rating = floor(AGI / bmv_price_agi) + flat_gear_dodge

    Examples (per task spec):
        Attacker Hit=0, Defender Dodge=0:
            → 100 - 0 + 0 = 100% (always hits, baseline)
        Attacker Hit=0, Defender Dodge=1920 (=120%):
            → 100 - 120 + 0 = -20% → floored to 5% (defender 95% evades)
        Attacker Hit=800 (=50%), Defender Dodge=1920 (=120%):
            → 100 - 120 + 50 = 30% (overcap hit pierced some dodge)
        Attacker Hit=480 (=30%), Defender Dodge=160 (=10%):
            → 100 - 10 + 30 = 120% → capped to 100%
    """
    from pockie_rpg.config import combat_hit_chance

    # Stage 103 — fields store RATINGS, pass directly to combat_hit_chance.
    return combat_hit_chance(attacker.hit_chance, target.dodge_chance)


def apply_damage_pipeline(base_damage: int, attacker: Fighter, target: Fighter) -> tuple[int, bool, bool]:
    """Stage 137 — ОРИГИНАЛ (вики + тултипы 75 лвл), 3-stage pipeline.

    Crit → ЗАЩИТА(def − break) → Block(block − antiblock).

    Stage 1 — CRIT (Attacker Crit vs Defender Const):
        Final_Crit_Chance% = crit%/16 − tough%/16
        Damage_After_Crit = Base * (150 + crit*0.125 − tough*0.125)/100

    Stage 2 — ЗАЩИТА (Defender Defence vs Attacker Defence Break):
        Оба — гиперболы x/(x+1354), вычитание процентов:
        Final_Mitigation% = def/(def+1354) − break/(break+1354)
        При равных статах гасятся ровно в ноль; overcap не усиливает урон.

    Stage 3 — BLOCK (Defender Block vs Attacker Антиблок):
        Final_Block_Chance% = block%/16 − antiblock%/16
        Успех → −40% урона (×0.60).

    КАПОВ НА РЕЙТИНГИ НЕТ (5000/10000+ валидны).
    """
    from pockie_rpg.config import (
        apply_block_stage,
        apply_crit_stage,
        apply_defense_stage,
    )
    # Аудит 2026-09 — прямой доступ вместо getattr(..., 0): getattr-дефолт
    # маскировал опечатку в имени поля (переименуешь crit_rating → бой
    # молча считал 0 крита). Опечатка теперь падает с AttributeError сразу.
    attacker_crit = attacker.crit_rating
    defender_tough = target.tough_rating
    defender_defense = target.defense
    attacker_defbreak = attacker.pierce_rating
    defender_block = target.block_rating
    attacker_antiblock = attacker.antiblock_rating

    # Stage 1 — Crit
    dmg, is_crit = apply_crit_stage(base_damage, attacker_crit, defender_tough)
    # Stage 137 — ЗАЩИТА: def% − break% (гиперболы, K=1354).
    dmg = apply_defense_stage(dmg, defender_defense, attacker_defbreak)
    # Stage 137 — BLOCK: block%/16 − antiblock%/16.
    dmg, is_block = apply_block_stage(dmg, defender_block, attacker_antiblock)
    return max(0, dmg), is_crit, is_block


def _apply_freeze_amplification(target: Fighter, dmg: int) -> tuple[bool, int]:
    if not target.status.has("freeze"):
        return False, dmg
    freeze_effect = target.status.get_effect("freeze")
    if freeze_effect is None:
        return False, dmg
    dmg_mult = freeze_effect.params.get("damage_taken_multiplier", 1.0)
    if dmg_mult <= 1.0:
        return False, dmg
    return True, int(dmg * dmg_mult)


def compute_attack(attacker: Fighter, target: Fighter) -> FightValue:
    """Full basic-attack pipeline -> FightValue event."""
    fv = FightValue(
        role=0 if attacker.is_player else 1,
        target=0 if target.is_player else 1,
        event=EventType.ATTACK,
        skill_name="Базовая атака",
    )

    base_dmg = get_damage(attacker)
    hit_chance = get_hit(attacker, target)
    # Stage 88 — Fix 2.1: use rand_int(1, 100) so hit_chance maps exactly to
    # the percentage of rolls that hit (e.g. hit_chance=95 → rolls 1..95 hit =
    # 95/100 = 95%). Previously rand_int(0, 100) gave 101 outcomes, making
    # hit_chance=95 actually hit 96/101 ≈ 95.05% of the time.
    if rand_int(1, 100) > hit_chance:
        fv.is_hit = 0
        fv.damage = 0
        fv.log_text = f"{attacker.name} промахнулся по {target.name}"
        return fv

    fv.is_hit = 1
    # Stage 104/133 — 4-stage damage pipeline (Crit → ЗАЩИТА → Block → Pierce).
    dmg, is_crit, is_block = apply_damage_pipeline(base_dmg, attacker, target)
    if is_crit:
        fv.is_crit = 1
    dmg = max(0, dmg)

    freeze_consumed, dmg = _apply_freeze_amplification(target, dmg)

    actual = target.take_damage(dmg)
    fv.damage = actual
    fv.shield_absorbed = target.shield_absorbed_last

    if freeze_consumed:
        fv.freeze_shattered = 1
        target.status.remove("freeze")

    crit_text = " КРИТ!" if fv.is_crit else ""
    block_text = " БЛОК!" if is_block else ""
    freeze_text = " Глыба разрушена!" if freeze_consumed else ""
    # Stage 190/191 — щит обязан быть виден в логе: иначе удар «в щит»
    # выглядит необъяснимым «0 урона». Формат без склонения имён:
    # полное поглощение — через тире (штатный глиф лога), частичное —
    # скобкой-приложением к обычной формуле.
    if actual <= 0 and fv.shield_absorbed > 0:
        fv.log_text = (
            f"{attacker.name} бьёт {target.name} — щит поглотил весь удар "
            f"({fv.shield_absorbed} урона){crit_text}{block_text}{freeze_text}"
        )
    else:
        shield_text = (
            f" (щит поглотил {fv.shield_absorbed})" if fv.shield_absorbed > 0 else ""
        )
        fv.log_text = f"{attacker.name} бьёт {target.name} на {actual} урона{crit_text}{block_text}{freeze_text}{shield_text}"
    return fv


_EFFECT_PARAM_EXCLUDE_KEYS: frozenset[str] = frozenset({
    "chance",
    "duration",
    "duration_min",
    "duration_max",
})


def _compute_effect_duration(params: dict) -> int:
    """Compute duration (turns) for an on_hit_effect; supports min/max random."""
    if "duration_min" in params and "duration_max" in params:
        return random.randint(int(params["duration_min"]), int(params["duration_max"]))
    return int(params.get("duration", 1))


def _build_effect_params(params: dict) -> dict:
    """Extract effect-specific params (excludes chance/duration/duration_min/max)."""
    return {k: v for k, v in params.items() if k not in _EFFECT_PARAM_EXCLUDE_KEYS}


def apply_skill_effects(
    skill: SkillDef, attacker: Fighter, target: Fighter
) -> tuple[list[str], dict[str, int]]:
    """Apply all on_hit_effects from a skill to the appropriate fighters.

    Effects are applied to:
      - ATTACKER (self): if effect_name == "extra_turn" or skill.is_self_buff
      - TARGET (defender): otherwise

    Stage 88 — Fix 2.2: now returns a tuple ``(applied_names, durations)``
    where ``durations`` maps each applied effect_name to the duration that
    was computed and passed to StatusManager.apply(). Callers (specifically
    ``_set_effect_markers``) MUST use this duration instead of recomputing
    via ``_compute_effect_duration`` — otherwise the FightValue marker can
    report a different duration than what the engine's StatusManager actually
    received, causing UI/engine desync.

    Returns:
        Tuple of (list of applied effect names, dict mapping name → duration).
    """
    applied: list[str] = []
    durations: dict[str, int] = {}
    for effect_name, params in skill.on_hit_effects.items():
        chance = params.get("chance", 1.0)
        if random.random() >= chance:
            continue
        duration = _compute_effect_duration(params)
        effect_params = _build_effect_params(params)
        if effect_name == "thunder_cloud":
            effect_params["caster_role_id"] = attacker.role_id
        recipient = attacker if (effect_name == "extra_turn" or skill.is_self_buff) else target
        recipient.status.apply(effect_name, duration, effect_params)
        applied.append(effect_name)
        durations[effect_name] = duration
    return applied, durations


def _set_effect_markers(
    fv: FightValue,
    effect_name: str,
    skill: SkillDef,
    duration: int | None = None,
) -> None:
    """Set the FightValue marker for a single applied effect.

    Stage 88 — Fix 2.2: ``duration`` is now passed in from the caller (the
    value computed once in ``apply_skill_effects`` and propagated via the
    returned durations dict). If None, falls back to recomputing (backward
    compat for any caller that doesn't pass it).
    """
    if effect_name == "freeze":
        fv.is_frozen = 1
    elif effect_name == "extra_turn":
        fv.is_extra_turn = 1
    elif effect_name == "poison":
        fv.poison_applied = 1
    elif effect_name == "shield":
        fv.is_shield = 1
        fv.shield_applied = 1
    elif effect_name == "thunder_cloud":
        fv.cloud_applied = 1
        # Use the duration passed from apply_skill_effects (Fix 2.2) —
        # avoids recomputing and potentially getting a different value.
        if duration is not None:
            fv.cloud_duration = duration
        else:
            cloud_params = skill.on_hit_effects.get("thunder_cloud", {})
            fv.cloud_duration = _compute_effect_duration(cloud_params)


def execute_skill(
    skill: SkillDef,
    attacker: Fighter,
    target: Fighter,
) -> FightValue:
    """Execute a skill: damage pipeline + on_hit_effects. Data-driven.

    For self-buff skills with damage_multiplier <= 0, skips damage and applies
    effects to the attacker. Otherwise applies damage to the target then
    applies on_hit_effects via apply_skill_effects().
    """
    fv = FightValue(
        role=0 if attacker.is_player else 1,
        target=0 if target.is_player else 1,
        event=EventType.ATTACK,
        skill_name=skill.name,
        dec_mp=skill.mp_cost,
        is_ranged=1 if skill.is_ranged else 0,
        is_self_buff=1 if skill.is_self_buff else 0,
    )

    if skill.is_self_buff and skill.damage_multiplier <= 0.0:
        applied_effects, effect_durations = apply_skill_effects(skill, attacker, target)
        for effect_name in applied_effects:
            _set_effect_markers(fv, effect_name, skill, effect_durations.get(effect_name))
        effects_text = _build_effects_suffix_self_buff(applied_effects)
        fv.log_text = f"{attacker.name} использует {skill.name}!{effects_text}"
        return fv

    # Stage 124 — NO-DAMAGE skills (damage_multiplier <= 0 but NOT self_buff).
    # Crystal Blade: applies freeze to target WITHOUT dealing damage.
    # The skill still plays the attack animation (run forward, strike) but
    # deals 0 damage — only the on_hit_effects (freeze) are applied.
    if not skill.is_self_buff and skill.damage_multiplier <= 0.0:
        applied_effects, effect_durations = apply_skill_effects(skill, attacker, target)
        for effect_name in applied_effects:
            _set_effect_markers(fv, effect_name, skill, effect_durations.get(effect_name))
        fv.is_hit = 1  # The strike connects (applies effect), but deals 0 damage.
        fv.damage = 0
        effects_suffix = _build_effects_suffix(applied_effects)
        fv.log_text = (
            f"{attacker.name} использует {skill.name}! "
            f"Урон не нанесён.{effects_suffix}"
        )
        return fv

    base_dmg = get_damage(attacker)
    if skill.damage_multiplier != 1.0:
        base_dmg = int(base_dmg * skill.damage_multiplier)

    hit_chance = get_hit(attacker, target)
    # Stage 88 — Fix 2.1: same off-by-one fix as compute_attack (1..100 roll).
    if rand_int(1, 100) > hit_chance:
        fv.is_hit = 0
        fv.damage = 0
        fv.log_text = (
            f"{attacker.name} использует {skill.name}! "
            f"Промах по {target.name}."
        )
        return fv

    fv.is_hit = 1
    # Stage 104/133 — 4-stage damage pipeline (Crit → ЗАЩИТА → Block → Pierce).
    dmg, is_crit, is_block = apply_damage_pipeline(base_dmg, attacker, target)
    if is_crit:
        fv.is_crit = 1
    dmg = max(0, dmg)

    freeze_consumed, dmg = _apply_freeze_amplification(target, dmg)

    actual = target.take_damage(dmg)
    fv.damage = actual
    fv.shield_absorbed = target.shield_absorbed_last

    if freeze_consumed:
        fv.freeze_shattered = 1
        target.status.remove("freeze")

    applied_effects, effect_durations = apply_skill_effects(skill, attacker, target)
    for effect_name in applied_effects:
        _set_effect_markers(fv, effect_name, skill, effect_durations.get(effect_name))

    crit_text = " КРИТ!" if fv.is_crit else ""
    block_text = " БЛОК!" if is_block else ""
    mult_text = (
        f" (×{skill.damage_multiplier})" if skill.damage_multiplier != 1.0 else ""
    )
    effects_suffix = _build_effects_suffix(applied_effects)
    # Stage 124 — indicate freeze consumption.
    freeze_text = " Глыба разрушена!" if freeze_consumed else ""
    # Stage 190/191 — щит в логе скиллов (формат без склонения, единый
    # с базовой атакой: тире при полном поглощении, скобка при частичном).
    if actual <= 0 and fv.shield_absorbed > 0:
        fv.log_text = (
            f"{attacker.name} использует {skill.name}! "
            f"{target.name} — щит поглотил весь удар "
            f"({fv.shield_absorbed} урона){crit_text}{block_text}{freeze_text}"
        )
    else:
        shield_text = (
            f" (щит поглотил {fv.shield_absorbed})" if fv.shield_absorbed > 0 else ""
        )
        fv.log_text = (
            f"{attacker.name} использует {skill.name}! "
            f"{target.name} получает {actual} урона{mult_text}{crit_text}{block_text}{effects_suffix}{freeze_text}{shield_text}"
        )

    return fv


def _build_effects_suffix(applied_effects: list[str]) -> str:
    """Build the log-text suffix for a damage-dealing skill's effects."""
    if not applied_effects:
        return ""
    parts: list[str] = []
    for name in applied_effects:
        if name == "freeze":
            parts.append("замораживается в глыбе")
        elif name == "extra_turn":
            parts.append("получает дополнительный ход")
        elif name == "poison":
            parts.append("отравлен")
        elif name == "burn":
            parts.append("подожжён")
        elif name == "thunder_cloud":
            parts.append("обложен грозовой тучей")
        elif name == "shield":
            parts.append("щит активирован")
        else:
            parts.append(name)
    return " и " + "! и ".join(parts) + "!"


def _build_effects_suffix_self_buff(applied_effects: list[str]) -> str:
    """Build the log-text suffix for a self-buff skill's effects."""
    if not applied_effects:
        return ""
    parts: list[str] = []
    for name in applied_effects:
        if name == "shield":
            parts.append("на себя накладывается щит")
        elif name == "extra_turn":
            parts.append("получает дополнительный ход")
        else:
            parts.append(f"активирует {name}")
    return " " + ", ".join(parts) + "."


def try_skill(
    skill_id: int,
    attacker: Fighter,
    target: Fighter,
) -> FightValue | None:
    """Attempt to trigger a skill by its skill_id. Returns None if not triggered.

    Trigger conditions (all must be true):
      1. skill_id is in SKILL_REGISTRY.
      2. attacker.mp >= skill.mp_cost.
      3. random roll < skill.trigger_chance.

    Stage 123 — ADMIN PANEL OVERRIDE: if the global `_skill_chance_overrides`
    dict (set by the F8 admin panel) contains an entry for `skill_id`, that
    value (0.0-1.0) is used instead of `skill.trigger_chance`. This lets the
    user test skill behavior at different chances without modifying the
    registry. The dict is None by default (no overrides) — production runs
    are unaffected.
    """
    skill = get_skill(skill_id)
    if skill is None:
        return None
    if attacker.mp < skill.mp_cost:
        return None
    # Stage 123 — check admin panel override.
    chance = skill.trigger_chance
    if _skill_chance_overrides and skill_id in _skill_chance_overrides:
        chance = _skill_chance_overrides[skill_id]
    if random.random() >= chance:
        return None
    attacker.mp -= skill.mp_cost
    return execute_skill(skill, attacker, target)


# Stage 123 — Global skill chance overrides (set by F8 admin panel).
# When this dict is non-empty, try_skill() uses these values instead of
# the registry defaults. This is a module-level global so damage.py can
# read it without a circular import with the UI layer.
_skill_chance_overrides: dict[int, float] = {}


def set_skill_chance_overrides(overrides: dict[int, float]) -> None:
    """Stage 123 — Update the global skill chance overrides.

    Called by the F8 admin panel when the user adjusts a skill chance.
    """
    global _skill_chance_overrides
    _skill_chance_overrides = dict(overrides)
