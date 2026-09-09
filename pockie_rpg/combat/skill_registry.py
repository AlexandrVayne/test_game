"""Skill Registry — centralized skill database (Layer B, data-driven).

Per Stage 11 architectural refactor: ALL skills defined here as data.
The combat engine (FightSystem) iterates a fighter's skill deck and looks
up each skill in this registry — NO hardcoded skill-specific if/else.

To add a new skill: just add a new entry to SKILL_REGISTRY. The engine
will automatically handle it (MP check, trigger chance, damage multiplier,
on_hit_effects). No engine code changes needed.

Per §4.3: imports ONLY stdlib + config (no ui imports).

Stage 13 (NEW SkillDef fields):
  * is_ranged: bool = False — True = ranged skill (caster doesn't run
    forward, casts from position). UI replay skips RUN_FORWARD/RUN_BACK
    phases of the AttackSequence. Used by Fireball, Thunderstorm.
  * effect_folder: str = "" — animation folder to play during cast
    (e.g., "fireball_effect", "storm_cloud_effect"). UI can render this
    overlay on the target during the cast animation. Empty = no overlay.
  * is_self_buff: bool = False — True = apply on_hit_effects to the
    ATTACKER, not the target. Used by Crystal Shield (shield on self).
    Lightning Step's "extra_turn" is also a self-buff (handled by the
    effect_name in execute_skill).

Stage 14 (BALANCE TUNING): trigger chances re-tuned for a more
reasonable rate of at least-one-skill-per-turn. With 6 skills at the
Stage 13 chances (15-25% each), the probability of at least one
triggering per turn was ~74% — too chaotic. New chances (10-15% each)
bring the probability down to ~55% per turn — a more readable cadence.
Old → New trigger_chance:
  * 12006 Crystal Blade:   0.25 → 0.15
  * 15005 Lightning Step:   0.20 → 0.10
  * 10001 Fireball:         0.20 → 0.15
  * 14001 Thunderstorm:     0.15 → 0.10
  * 18003 Poison:           0.20 → 0.15
  * 14002 Crystal Shield:   0.20 → 0.10
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class SkillDef:
    """Immutable skill definition. All parameters for a skill.

    Attributes:
        skill_id: unique integer ID (e.g., 12006).
        name: display name (e.g., "Кристальный клинок").
        description: tooltip text for UI.
        mp_cost: MP consumed on trigger.
        trigger_chance: 0.0-1.0, chance per turn (when MP >= cost).
        damage_multiplier: base damage × this (1.0 = normal, 1.4 = +40%).
        on_hit_effects: dict of effect_name → params dict.
            Applied to defender AFTER damage, IF attack hits.
            Example: {"freeze": {"chance": 0.40, "duration": 2}}
            Supported effect names: "freeze", "stun", "poison", "burn",
            "shield", "heal", "vampiric", "extra_turn", "thunder_cloud"
            (future: "bleed", "paralyze", "silence", etc.).
        is_ranged: True = ranged skill (no run forward, cast from position).
            UI replay skips RUN_FORWARD / RUN_BACK phases of AttackSequence.
            Stage 13 NEW field.
        effect_folder: animation folder to play during cast (e.g.,
            "fireball_effect"). Empty = no overlay animation. Stage 13 NEW.
        is_self_buff: True = apply on_hit_effects to the ATTACKER, not the
            target. Stage 13 NEW. (Lightning Step's "extra_turn" is also a
            self-buff, but it's already handled via effect_name in
            execute_skill — this field is a separate hint for UI to skip
            damage application to the target.)
    """

    skill_id: int
    name: str
    description: str
    mp_cost: int = 0
    trigger_chance: float = 0.0
    damage_multiplier: float = 1.0
    on_hit_effects: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Stage 13 NEW — ranged / animation / self-buff flags.
    is_ranged: bool = False
    effect_folder: str = ""
    is_self_buff: bool = False


# ---------------------------------------------------------------------------
# THE SKILL REGISTRY — ALL skills in ONE place.
# Add new skills here. Engine auto-discovers via get_skill().
# ---------------------------------------------------------------------------

SKILL_REGISTRY: dict[int, SkillDef] = {
    12006: SkillDef(
        skill_id=12006,
        name="Кристальный клинок",
        description=(
            "Кристальный клинок: расходует 35 MP, НЕ наносит урон. "
            "Накладывает Заморозку на врага (100% шанс) на 2 хода. "
            "Замороженный враг не может двигаться или атаковать и "
            "получает 200% урона от следующей атаки."
        ),
        mp_cost=35,
        # Stage 14 — trigger chance 0.25 → 0.15 (balance tuning).
        trigger_chance=0.15,
        # Stage 124 — NO damage. Crystal Blade only applies freeze.
        damage_multiplier=0.0,
        on_hit_effects={
            # Stage 124 — 100% chance, duration=1, damage_taken_multiplier=2.0.
            # The freeze status carries a "damage_taken_multiplier" param that
            # compute_attack() reads to amplify incoming damage. After the
            # amplified hit lands, the freeze is removed (consumed).
            "freeze": {
                "chance": 1.0,
                "duration": 2,
                "damage_taken_multiplier": 2.0,
            },
        },
    ),
    # Stage 12 — Lightning Step (Шаг молнии): extra turn skill.
    15005: SkillDef(
        skill_id=15005,
        name="Шаг молнии",
        description=(
            "Шаг молнии: расходует 40 MP, наносит базовый урон и даёт "
            "атакующему дополнительный ход (следующая атака сразу после этой)."
        ),
        mp_cost=40,
        # Stage 14 — trigger chance 0.20 → 0.10 (balance tuning).
        trigger_chance=0.10,           # 10% per turn (was 20%)
        damage_multiplier=1.0,        # base damage (no multiplier)
        on_hit_effects={
            "extra_turn": {"chance": 1.0, "duration": 1},
        },
        # Stage 13 — Lightning Step is ranged (self-buff: extra turn —
        # fighter doesn't run forward to grant the extra turn). Melee
        # damage IS applied to the target (it's a real attack).
        # NOTE: we keep is_ranged=False here because Lightning Step DOES
        # deal melee damage (the extra_turn buff is in addition to the
        # attack). The UI will still run forward for the strike.
        is_ranged=False,
        is_self_buff=False,
    ),
    # -----------------------------------------------------------------
    # Stage 13 — 4 NEW SKILLS
    # -----------------------------------------------------------------
    # Skill 1: Fireball (Огненный шар) — pure damage ranged nuke.
    # Spec: "Тратит 35 MP. Наносит повышенный урон (множитель 1.6).
    #        Никаких дебаффов и ожогов не накладывает. Чистый, мощный урон."
    10001: SkillDef(
        skill_id=10001,
        name="Огненный шар",
        description=(
            "Огненный шар: расходует 35 MP, наносит мощный урон (×1.6). "
            "Чистый урон, без дебаффов и ожогов. Кастуется с места."
        ),
        mp_cost=35,
        # Stage 14 — trigger chance 0.20 → 0.15 (balance tuning).
        trigger_chance=0.15,           # 15% per turn (was 20%)
        damage_multiplier=1.6,        # +60% damage
        on_hit_effects={},             # pure damage — no debuffs
        is_ranged=True,                # caster doesn't run forward
        effect_folder="effects/fireball",
    ),
    # Skill 2: Thunderstorm (Грозовая туча) — DoT + migration debuff.
    # Spec: "Тратит 55 MP. Шанс каста 15%. На цель вешается статус
    #        thunder_cloud на 2-4 хода. Туча сразу наносит первый удар
    #        молнией (0.6 от базового урона). В начале хода каждого бойца
    #        с активной тучей: боец получает 0.6 урона от автора тучи,
    #        длительность уменьшается на 1, при длительности > 0 — 50% шанс
    #        что туча перелетит на оппонента (с сохранением длительности)."
    14001: SkillDef(
        skill_id=14001,
        name="Грозовая туча",
        description=(
            "Грозовая туча: расходует 55 MP, наносит первый удар молнией "
            "(×0.6 базового урона) и вешает на цель тучу грозы на 2-4 хода. "
            "В начале каждого хода цель получает удар молнией (×0.6), "
            "туча может перелететь на другого бойца (50% шанс)."
        ),
        mp_cost=55,
        # Stage 14 — trigger chance 0.15 → 0.10 (balance tuning).
        trigger_chance=0.10,           # 10% per turn (was 15%)
        damage_multiplier=0.6,        # first strike = 0.6 × base
        on_hit_effects={
            "thunder_cloud": {
                "chance": 1.0,         # always apply on hit
                "duration_min": 2,     # random duration 2-4 turns
                "duration_max": 4,
                "cloud_dmg_multiplier": 0.6,  # 0.6 × caster's base damage per tick
            },
        },
        is_ranged=True,
        effect_folder="effects/storm_cloud",
    ),
    # Skill 3: Poison Dart (Яд) — DoT (5% max HP per turn).
    # Spec: "Снижает ману на 25. Наносит 1.0 базового урона. С шансом 70%
    #        накладывает на цель статус poison на 3 хода. В начале каждого
    #        своего хода отравленный боец получает урон 5% от макс HP."
    # Stage 16 — duration 3 → 4 per user request (was 3). The poison overlay
    # now stays visible for the entire 4-turn duration (continuous EffectOverlay
    # via _sync_effect_overlays polling fighter.status.has("poison")).
    18003: SkillDef(
        skill_id=18003,
        name="Яд",
        description=(
            "Яд: расходует 25 MP, наносит базовый урон и с шансом 70% "
            "отравляет врага на 4 хода. Отравленный боец получает 5% "
            "от своего максимального HP урона в начале каждого хода."
        ),
        mp_cost=25,
        # Stage 14 — trigger chance 0.20 → 0.15 (balance tuning).
        trigger_chance=0.15,           # 15% per turn (was 20%)
        damage_multiplier=1.0,        # base damage
        on_hit_effects={
            "poison": {
                "chance": 0.70,         # 70% chance to apply
                "duration": 4,          # Stage 16 — 4 turns (was 3)
                "dmg_pct_max_hp": 0.05, # 5% of max HP per tick
            },
        },
        # Spec doesn't explicitly say ranged or melee. Treat as melee
        # (dart is thrown at close range). Can be changed to ranged if
        # the user prefers — INFERRED design choice.
        is_ranged=False,
        effect_folder="effects/poison",
    ),
    # Skill 4: Crystal Shield (Купол) — self-buff shield.
    # Spec: "Защитный навык. Снижает ману на 40. Урон врагу не наносится.
    #        Накладывает на себя статус shield (щит 300 HP). В пайплайне
    #        урона, если у цели активен щит, входящий урон сначала
    #        поглощается щитом. Когда прочность щита падает до 0, статус
    #        снимается."
    14002: SkillDef(
        skill_id=14002,
        name="Купол",
        description=(
            "Купол: расходует 40 MP, накладывает на себя щит прочностью "
            "300 единиц. Входящий урон сначала поглощается щитом; когда "
            "прочность падает до 0, щит снимается. Урон врагу не наносится."
        ),
        mp_cost=40,
        # Stage 14 — trigger chance 0.20 → 0.10 (balance tuning).
        trigger_chance=0.10,           # 10% per turn (was 20%)
        damage_multiplier=0.0,        # no enemy damage — self-buff only
        on_hit_effects={
            "shield": {
                "chance": 1.0,          # always apply on trigger
                "amount": 300,         # shield absorbs 300 damage
                "duration": 4,         # 4 turns max (in case shield not depleted)
            },
        },
        is_ranged=False,
        is_self_buff=True,             # applies to attacker, not target
        effect_folder="effects/shield_dome",
    ),
}


def get_skill(skill_id: int) -> SkillDef | None:
    """Look up a skill by ID. Returns None if not in registry."""
    return SKILL_REGISTRY.get(skill_id)


def get_skill_by_name(name: str) -> SkillDef | None:
    """Look up a skill by its display name. Returns None if not found.

    Stage 14 — added for the UI to find a SkillDef from a FightValue's
    `skill_name` field (the UI replay only has the name, not the ID).
    Used to look up `effect_folder` so the CastEffect overlay can be
    triggered for ranged / self-buff skills with cast animations.

    Names are unique per the SkillDef contract (each skill has a distinct
    display name). The first match wins (defensive — there shouldn't be
    duplicates).
    """
    for skill in SKILL_REGISTRY.values():
        if skill.name == name:
            return skill
    return None
