"""Stage 70 — Titles system (Звания).

Звания — это_titles that the player can activate to get stat bonuses.
Each title has:
  - id: unique string identifier.
  - name: display name (Russian).
  - description: what the title represents.
  - stats: dict of stat bonuses (summed with player's stats when active).
  - requirement: TBD (Stage 70+ — for now all titles are activatable).

The player can have ONE active title at a time (or None). The active title's
stats are added to the player's CharacterStats via recalc_stats().

Stage 70 — 12 titles, ranging from "Новичок" (starter) to "Легенда Шиноби"
(endgame). Stats scale with title tier.

Stage 170 — 13-е звание tower_conqueror «Покоритель Башни» (награда за
первое прохождение 100-го этажа Башни; tower_db ссылался на него, а
TITLES_DB не знал — get_title возвращал None). Статы умеренные,
чуть ниже legend.
"""
from __future__ import annotations

# Title bonuses are flat stat additions. They're applied in
# PlayerState.recalc_stats() via get_gear_bonuses() (Stage 70 extension).
# Keys match CharacterStats / gear bonus keys.
TITLES_DB: dict[str, dict] = {
    "novice": {
        "id": "novice",
        "name": "Новичок",
        "description": "Только начинаешь свой путь.",
        "tier": 1,
        "stats": {
            "max_hp": 20,
        },
    },
    "apprentice": {
        "id": "apprentice",
        "name": "Ученик",
        "description": "Изучаешь основы боя.",
        "tier": 2,
        "stats": {
            "max_hp": 50,
            "strength": 1,
        },
    },
    "warrior": {
        "id": "warrior",
        "name": "Воин",
        "description": "Проверенный в боях.",
        "tier": 3,
        "stats": {
            "max_hp": 100,
            "strength": 2,
            "agility": 1,
        },
    },
    "hunter": {
        "id": "hunter",
        "name": "Охотник",
        "description": "Преследуешь врагов.",
        "tier": 4,
        "stats": {
            "max_hp": 150,
            "agility": 3,
            "hit_chance": 5,
        },
    },
    "defender": {
        "id": "defender",
        "name": "Защитник",
        "description": "Несокрушимый страж.",
        "tier": 5,
        "stats": {
            "max_hp": 250,
            "stamina": 3,
            "defense": 20,
        },
    },
    "berserker": {
        "id": "berserker",
        "name": "Берсерк",
        "description": "Ярость ведёт тебя.",
        "tier": 6,
        "stats": {
            "max_hp": 200,
            "strength": 5,
            "crit_chance": 5,
        },
    },
    "assassin": {
        "id": "assassin",
        "name": "Ассасин",
        "description": "Смерть из тени.",
        "tier": 7,
        "stats": {
            "agility": 6,
            "crit_chance": 8,
            "dodge_chance": 5,
        },
    },
    "monk": {
        "id": "monk",
        "name": "Монах",
        "description": "Гармония тела и духа.",
        "tier": 8,
        "stats": {
            "max_hp": 300,
            "max_mp": 100,
            "stamina": 4,
            "defense": 30,
        },
    },
    "ronin": {
        "id": "ronin",
        "name": "Ронин",
        "description": "Самурай без господина.",
        "tier": 9,
        "stats": {
            "max_hp": 400,
            "strength": 6,
            "agility": 4,
            "stamina": 3,
        },
    },
    "shadow_master": {
        "id": "shadow_master",
        "name": "Мастер Теней",
        "description": "Невидимый, но смертоносный.",
        "tier": 10,
        "stats": {
            "agility": 8,
            "dodge_chance": 10,
            "crit_chance": 10,
            "hit_chance": 8,
        },
    },
    "warlord": {
        "id": "warlord",
        "name": "Военачальник",
        "description": "Ведёшь за собой армии.",
        "tier": 11,
        "stats": {
            "max_hp": 500,
            "strength": 8,
            "stamina": 5,
            "defense": 40,
        },
    },
    "legend": {
        "id": "legend",
        "name": "Легенда Шиноби",
        "description": "Твоё имя знают все.",
        "tier": 12,
        "stats": {
            "max_hp": 800,
            "max_mp": 200,
            "strength": 10,
            "agility": 8,
            "stamina": 6,
            "defense": 50,
            "crit_chance": 12,
            "dodge_chance": 8,
        },
    },
    # Stage 170 — награда за первое прохождение 100-го этажа Башни
    # (tower_db.first_clear_reward.title_id="tower_conqueror").
    "tower_conqueror": {
        "id": "tower_conqueror",
        "name": "Покоритель Башни",
        "description": "Все 100 этажей покорены.",
        "tier": 13,
        "stats": {
            "max_hp": 650,
            "max_mp": 150,
            "strength": 8,
            "stamina": 6,
            "defense": 45,
            "crit_chance": 10,
        },
    },
}

# Ordered list of title IDs (by tier ascending).
TITLE_ORDER: list[str] = [
    "novice", "apprentice", "warrior", "hunter", "defender",
    "berserker", "assassin", "monk", "ronin", "shadow_master",
    "warlord", "legend", "tower_conqueror",
]


def get_title(title_id: str) -> dict | None:
    """Look up a title by id. Returns None if not found."""
    return TITLES_DB.get(title_id)


def get_title_stats(title_id: str | None) -> dict:
    """Return the stat bonuses for a title (or empty dict if None/unknown)."""
    if title_id is None:
        return {}
    title = TITLES_DB.get(title_id)
    if title is None:
        return {}
    return dict(title.get("stats", {}))


def get_all_titles() -> list[dict]:
    """Return all titles in tier order (novice → legend)."""
    return [TITLES_DB[tid] for tid in TITLE_ORDER if tid in TITLES_DB]
