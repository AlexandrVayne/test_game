"""Daily Quest data definitions (Layer A, data-driven).

Stage 95 — Daily Quests system. 4 quest types that reset daily.
Each quest tracks progress (0/target). When complete, player can claim reward.
Rewards scale: quest 1 < quest 2 < quest 3 < quest 4.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DailyQuestDef:
    """Definition of a single daily quest."""
    quest_id: str
    name: str
    description: str
    target: int          # required count to complete
    reward_gold: int
    reward_xp: int
    reward_shards: int = 0  # Tower shards (0 for non-tower quests)


# Stage 95 — 4 daily quests with escalating rewards.
DAILY_QUESTS: dict[str, DailyQuestDef] = {
    "kill_mobs": DailyQuestDef(
        quest_id="kill_mobs",
        name="Убить мобов",
        description="Победите 30 мобов на локациях.",
        target=30,
        reward_gold=500,
        reward_xp=300,
        reward_shards=0,
    ),
    "tower_floors": DailyQuestDef(
        quest_id="tower_floors",
        name="Пройти этажи Башни",
        description="Пройдите 5 этажей в Лас Ночес.",
        target=5,
        reward_gold=800,
        reward_xp=500,
        reward_shards=50,
    ),
    "world_boss": DailyQuestDef(
        quest_id="world_boss",
        name="Атаковать Мирового Босса",
        description="Атакуйте Мирового Босса 3 раза.",
        target=3,
        reward_gold=1200,
        reward_xp=800,
        reward_shards=100,
    ),
    "arena_fights": DailyQuestDef(
        quest_id="arena_fights",
        name="Сражения на Арене",
        description="Проведите 10 боёв на Арене.",
        target=10,
        reward_gold=2000,
        reward_xp=1200,
        reward_shards=200,
    ),
}

# Quest IDs in display order (escalating rewards).
DAILY_QUEST_ORDER: tuple[str, ...] = (
    "kill_mobs",
    "tower_floors",
    "world_boss",
    "arena_fights",
)


def get_daily_quest(quest_id: str) -> DailyQuestDef | None:
    """Return the quest definition for ``quest_id``, or None."""
    return DAILY_QUESTS.get(quest_id)
