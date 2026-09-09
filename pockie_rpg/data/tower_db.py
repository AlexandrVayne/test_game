"""Tower Mode data definitions (Layer A, data-driven).

Per TOWER_MODE_IMPLEMENTATION.md §3 — defines the 100-floor Tower PvE mode.

This module is PURE DATA — frozen dataclasses + a prebuilt registry. It does
NOT import pygame, ui, or game.state. It imports only stdlib (dataclasses).
The UI layer reads TOWER_FLOORS / TOWER_BOSSES via the get_tower_floor /
get_tower_boss helpers.

Design constraints (per the implementation doc):
  - Floors 1-99 use the standard turn-based autobattle + replay.
  - Every 10th floor (10, 20, ..., 100) is a boss floor.
  - Floor 100 is the final boss.
  - All enemies reuse existing ENEMY_DB entries (samurai/flower/etc).
  - Bosses reuse existing skill_ids from combat.skill_registry.
  - World Boss is unaffected — Tower has its own state.

Stage 89 (this file) implements the first vertical slice:
  - 100 floor definitions generated via a builder.
  - 10 boss definitions with curated skill decks + modifiers.
  - TowerReward dataclass (gold + tower_shards + xp + items + materials + title).
  - Helper functions: get_tower_floor, get_tower_boss, is_boss_floor.
"""
from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TOWER_MAX_FLOOR: int = 100
TOWER_BOSS_FLOORS: frozenset[int] = frozenset(range(10, TOWER_MAX_FLOOR + 1, 10))

# Stage 89 — placeholder material IDs (per §7.3 of the implementation doc).
# Real icons come later; the UI renders these as colored squares with a letter.
# Stage 204 — TOWER_MATERIAL_IDS кортеж удалён (0 чтений; иконки материалов
# читаются по отдельным TOWER_MATERIAL_* константам).
TOWER_MATERIAL_FIRE: str = "tower_fire_core"
TOWER_MATERIAL_ICE: str = "tower_ice_core"
TOWER_MATERIAL_LIGHTNING: str = "tower_lightning_core"
TOWER_MATERIAL_SHADOW: str = "tower_shadow_core"
TOWER_MATERIAL_ANCIENT: str = "tower_ancient_core"

# Stage 89 — modifier IDs (per §5). First version implements only the ones
# the runtime can apply pre-battle; the rest are metadata-only stubs.
# Stage 204 — TOWER_MODIFIERS удалён (0 чтений: модификаторы боссов
# применяются генератором напрямую).


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TowerReward:
    """Reward for clearing a tower floor.

    All fields use immutable types (tuple, not list) so reward definitions
    stay frozen. `materials` is a tuple of (material_id, amount) pairs.
    """

    gold: int = 0
    tower_shards: int = 0
    xp: int = 0
    items: tuple[str, ...] = ()
    materials: tuple[tuple[str, int], ...] = ()
    title_id: str | None = None


@dataclass(frozen=True, slots=True)
class TowerFloor:
    """A single tower floor definition."""

    floor: int
    enemy_id: str           # references EnemyTemplate.enemy_id in ENEMY_DB
    is_boss: bool = False
    recommended_level: int = 1
    hp_multiplier: float = 1.0
    attack_multiplier: float = 1.0
    modifiers: tuple[str, ...] = ()
    first_clear_reward: TowerReward = TowerReward()
    repeat_reward: TowerReward = TowerReward()


@dataclass(frozen=True, slots=True)
class TowerBoss:
    """A tower boss definition (every 10th floor).

    `enemy_id` references an existing EnemyTemplate (visual + base stats).
    `skills` is the boss's skill deck — passed explicitly to
    Fighter.from_role(..., skills=...) so the boss uses these skills instead
    of the default role.skills.
    """

    boss_id: str
    floor: int
    display_name: str
    enemy_id: str
    skills: tuple[int, ...]
    modifiers: tuple[str, ...] = ()
    description: str = ""
    first_clear_reward: TowerReward = TowerReward()
    repeat_reward: TowerReward = TowerReward()


# ---------------------------------------------------------------------------
# Boss definitions (per §4 plan)
# ---------------------------------------------------------------------------

# Skill IDs (from combat/skill_registry.py):
#   12006 = Кристальный клинок (Crystal Blade — freeze)
#   15005 = Шаг молнии (Lightning Step — extra turn)
#   10001 = Огненный шар (Fireball — ranged)
#   14001 = Грозовая туча (Thunderstorm — cloud DoT)
#   18003 = Яд (Poison Dart — poison)
#   14002 = Купол (Crystal Shield — shield)

TOWER_BOSSES: dict[int, TowerBoss] = {
    10: TowerBoss(
        boss_id="tower_boss_10",
        floor=10,
        display_name="Страж льда",
        enemy_id="samurai_1",
        skills=(12006,),
        modifiers=("boss_fast_start",),
        description="Первый страж башни. Быстро начинает бой.",
        first_clear_reward=TowerReward(gold=300, tower_shards=150, xp=400,
                                       materials=((TOWER_MATERIAL_ICE, 2),)),
        repeat_reward=TowerReward(gold=100, tower_shards=30, xp=80),
    ),
    20: TowerBoss(
        boss_id="tower_boss_20",
        floor=20,
        display_name="Цветок-хранитель",
        enemy_id="flower_1",
        skills=(18003,),
        modifiers=("boss_poison_resistance",),
        description="Отравляет противника и устойчив к яду сам.",
        first_clear_reward=TowerReward(gold=500, tower_shards=250, xp=800,
                                       materials=((TOWER_MATERIAL_SHADOW, 2),)),
        repeat_reward=TowerReward(gold=150, tower_shards=50, xp=120),
    ),
    30: TowerBoss(
        boss_id="tower_boss_30",
        floor=30,
        display_name="Синий стрелок",
        enemy_id="samurai_2",
        skills=(15005,),
        modifiers=("boss_fast_start",),
        description="Получает дополнительный ход после атаки.",
        first_clear_reward=TowerReward(gold=750, tower_shards=350, xp=1400,
                                       materials=((TOWER_MATERIAL_LIGHTNING, 2),)),
        repeat_reward=TowerReward(gold=200, tower_shards=70, xp=150),
    ),
    40: TowerBoss(
        boss_id="tower_boss_40",
        floor=40,
        display_name="Чёрный страж",
        enemy_id="samurai_3",
        skills=(14002,),
        modifiers=("boss_shield_at_half_hp",),
        description="Активирует щит при низком HP.",
        first_clear_reward=TowerReward(gold=1000, tower_shards=500, xp=2200,
                                       materials=((TOWER_MATERIAL_SHADOW, 3),)),
        repeat_reward=TowerReward(gold=300, tower_shards=100, xp=200),
    ),
    50: TowerBoss(
        boss_id="tower_boss_50",
        floor=50,
        display_name="Грозовой цветок",
        enemy_id="flower_1",
        skills=(18003, 14001),
        modifiers=("boss_poison_resistance", "boss_shield_at_half_hp"),
        description="Яд + грозовая туча. Опасная комбинация.",
        first_clear_reward=TowerReward(gold=1500, tower_shards=750, xp=4000,
                                       materials=((TOWER_MATERIAL_LIGHTNING, 3),
                                                  (TOWER_MATERIAL_SHADOW, 2))),
        repeat_reward=TowerReward(gold=400, tower_shards=150, xp=300),
    ),
    60: TowerBoss(
        boss_id="tower_boss_60",
        floor=60,
        display_name="Огненный самурай",
        enemy_id="samurai_4",
        skills=(10001,),
        modifiers=("boss_enrage_at_half_hp",),
        description="Дальний бой + ярость при низком HP.",
        first_clear_reward=TowerReward(gold=2000, tower_shards=1000, xp=6000,
                                       materials=((TOWER_MATERIAL_FIRE, 3),)),
        repeat_reward=TowerReward(gold=500, tower_shards=200, xp=400),
    ),
    70: TowerBoss(
        boss_id="tower_boss_70",
        floor=70,
        display_name="Молниеносный клинок",
        enemy_id="samurai_2",
        skills=(15005, 12006),
        modifiers=("boss_fast_start",),
        description="Замораживает и атакует дважды.",
        first_clear_reward=TowerReward(gold=2500, tower_shards=1250, xp=9000,
                                       materials=((TOWER_MATERIAL_LIGHTNING, 4),)),
        repeat_reward=TowerReward(gold=600, tower_shards=250, xp=500),
    ),
    80: TowerBoss(
        boss_id="tower_boss_80",
        floor=80,
        display_name="Двухфазный страж",
        enemy_id="samurai_3",
        skills=(14002, 14001),
        modifiers=("boss_shield_at_half_hp", "boss_second_phase"),
        description="Защитная купол + грозовая туча. Две фазы боя.",
        first_clear_reward=TowerReward(gold=3000, tower_shards=1500, xp=13000,
                                       materials=((TOWER_MATERIAL_ICE, 3),
                                                  (TOWER_MATERIAL_LIGHTNING, 3))),
        repeat_reward=TowerReward(gold=800, tower_shards=300, xp=600),
    ),
    90: TowerBoss(
        boss_id="tower_boss_90",
        floor=90,
        display_name="Комбинированный босс",
        enemy_id="samurai_12",
        skills=(10001, 18003, 14002),
        modifiers=("boss_enrage_at_half_hp", "boss_poison_resistance"),
        description="Огонь + яд + щит. Финальная проверка перед вершиной.",
        first_clear_reward=TowerReward(gold=4000, tower_shards=2000, xp=18000,
                                       materials=((TOWER_MATERIAL_FIRE, 3),
                                                  (TOWER_MATERIAL_SHADOW, 3),
                                                  (TOWER_MATERIAL_ANCIENT, 2))),
        repeat_reward=TowerReward(gold=1000, tower_shards=400, xp=800),
    ),
    100: TowerBoss(
        boss_id="tower_boss_100",
        floor=100,
        display_name="Владыка башни",
        enemy_id="samurai_12",
        skills=(10001, 18003, 14002, 14001, 15005, 12006),
        modifiers=("boss_fast_start", "boss_shield_at_half_hp",
                   "boss_enrage_at_half_hp", "boss_second_phase"),
        description="Финальный босс башни. Обладает всеми навыками.",
        first_clear_reward=TowerReward(gold=5000, tower_shards=3000, xp=25000,
                                       materials=((TOWER_MATERIAL_ANCIENT, 5),),
                                       title_id="tower_conqueror"),
        repeat_reward=TowerReward(gold=1500, tower_shards=600, xp=1000),
    ),
}


# ---------------------------------------------------------------------------
# Floor definitions (100 floors via builder)
# ---------------------------------------------------------------------------


def _build_floors() -> dict[int, TowerFloor]:
    """Build the 100-floor registry.

    Non-boss floors cycle through existing enemy IDs with scaling
    hp/attack multipliers. Boss floors use the TOWER_BOSSES registry
    for their skill deck + modifiers but still reference the same
    enemy_id for visuals + base stats.
    """
    floors: dict[int, TowerFloor] = {}

    # Cycle of enemy IDs for normal floors (per §3.3 — reuse existing enemies).
    normal_enemy_cycle: tuple[str, ...] = (
        "samurai_1",   # floors 1-9 (early)
        "samurai_2",   # floors 11-19
        "samurai_3",   # floors 21-29
        "samurai_4",   # floors 31-39
        "flower_1",    # floors 41-49
        "samurai_6",   # floors 51-59
        "samurai_8",   # floors 61-69
        "samurai_10",  # floors 71-79
        "samurai_11",  # floors 81-89
        "samurai_12",  # floors 91-99
    )

    for floor in range(1, TOWER_MAX_FLOOR + 1):
        if floor in TOWER_BOSS_FLOORS:
            boss = TOWER_BOSSES[floor]
            # Boss floor: use the boss's enemy_id + multipliers scaled by floor.
            hp_mul = 1.0 + (floor // 10) * 0.5      # +50% per 10 floors
            atk_mul = 1.0 + (floor // 10) * 0.3     # +30% per 10 floors
            floors[floor] = TowerFloor(
                floor=floor,
                enemy_id=boss.enemy_id,
                is_boss=True,
                recommended_level=max(1, floor),
                hp_multiplier=hp_mul,
                attack_multiplier=atk_mul,
                modifiers=boss.modifiers,
                first_clear_reward=boss.first_clear_reward,
                repeat_reward=boss.repeat_reward,
            )
        else:
            # Normal floor: pick enemy from cycle, scale by floor.
            cycle_idx = (floor - 1) // 10
            cycle_idx = min(cycle_idx, len(normal_enemy_cycle) - 1)
            enemy_id = normal_enemy_cycle[cycle_idx]
            # Scale HP/atk gently with floor (within the 10-floor bracket).
            bracket_pos = (floor % 10) if (floor % 10) != 0 else 10
            hp_mul = 1.0 + (bracket_pos - 1) * 0.08      # +8% per floor in bracket
            atk_mul = 1.0 + (bracket_pos - 1) * 0.05     # +5% per floor in bracket
            # Rewards scale with floor.
            gold = 20 + floor * 3
            shards = 10 + floor // 3
            xp = 30 + floor * 5
            floors[floor] = TowerFloor(
                floor=floor,
                enemy_id=enemy_id,
                is_boss=False,
                recommended_level=max(1, floor),
                hp_multiplier=hp_mul,
                attack_multiplier=atk_mul,
                first_clear_reward=TowerReward(gold=gold, tower_shards=shards, xp=xp),
                repeat_reward=TowerReward(gold=gold // 3, tower_shards=shards // 4, xp=xp // 4),
            )

    return floors


TOWER_FLOORS: dict[int, TowerFloor] = _build_floors()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def get_tower_floor(floor: int) -> TowerFloor | None:
    """Return the TowerFloor definition for ``floor``, or None if out of range."""
    return TOWER_FLOORS.get(floor)


def get_tower_boss(floor: int) -> TowerBoss | None:
    """Return the TowerBoss definition for ``floor``, or None if not a boss floor."""
    return TOWER_BOSSES.get(floor)


def get_tower_reward(floor: int, *, first_clear: bool) -> TowerReward:
    """Return the appropriate reward for clearing ``floor``.

    Args:
        floor: the floor number (1-100).
        first_clear: True if this is the player's first clear of this floor
            (uses first_clear_reward), False for repeat clears (repeat_reward).
    """
    tf = TOWER_FLOORS.get(floor)
    if tf is None:
        return TowerReward()
    return tf.first_clear_reward if first_clear else tf.repeat_reward
