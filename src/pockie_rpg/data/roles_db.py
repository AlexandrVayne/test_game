"""Role definitions, starter suits, and enemy mob registry (Layer A → data).

Stage 96 — extracted from game/state.py to reduce file size.
All Role definitions, STARTER_SUITS, ENEMY_MOBS, and the legacy mob key map
live here. state.py imports from this module.
"""
from __future__ import annotations

from pockie_rpg.data.enemy_db import ENEMY_DB as _ENEMY_DB
from pockie_rpg.data.models import EnemyDef, Role, Suit

# ---------------------------------------------------------------------------
# ROLE DEFINITIONS (Stage 4 — full character sheet stats)
# ---------------------------------------------------------------------------

ROLE_ICHIGO: Role = Role(
    role_id=1,
    name="Ичиго",
    strength=24,
    agility=24,
    stamina=20,
    max_hp=500,
    max_mp=300,
    atk_time=980,
    skills=(12006, 15005, 10001, 14001, 18003, 14002),
)

ROLE_SAMURAI: Role = Role(
    role_id=10001,
    name="Самурай",
    strength=16,
    agility=12,
    stamina=16,
    max_hp=1100,
    max_mp=50,
    atk_time=1380,
    skills=(),
)

ROLE_SAMURAI_2: Role = Role(
    role_id=10002,
    name="Синий мечник",
    strength=22,
    agility=16,
    stamina=22,
    max_hp=1300,
    max_mp=100,
    atk_time=1350,
    skills=(),
)

ROLE_SAMURAI_3: Role = Role(
    role_id=10004,
    name="Черный самурай",
    strength=28,
    agility=20,
    stamina=28,
    max_hp=1600,
    max_mp=150,
    atk_time=1320,
    skills=(),
)

ROLE_FLOWER: Role = Role(
    role_id=10102,
    name="Цветок",
    strength=18,
    agility=22,
    stamina=12,
    max_hp=800,
    max_mp=80,
    atk_time=1200,
    skills=(18003,),
)

ROLES: dict[int, Role] = {
    1: ROLE_ICHIGO,
    10001: ROLE_SAMURAI,
    10002: ROLE_SAMURAI_2,
    10004: ROLE_SAMURAI_3,
    10102: ROLE_FLOWER,
}


# ---------------------------------------------------------------------------
# STARTER SUITS
# ---------------------------------------------------------------------------

STARTER_SUITS: dict[str, Suit] = {
    "i290001": Suit(
        suit_id="i290001",
        name="Ичиго",
        role_id=1,
        motion_folder="ichigo/idle",
        avatar_filename="userface_0_1_role.gif",
    ),
    # Stage 206 — костюм cloth14 (пользователь: это Рендзи АБАРАИ, не Сакура;
    # Stage 211 — написание «Рендзи» по запросу пользователя).
    # Надетый костюм suit_cloth14 переключает аватар/имя/позу инвентаря на
    # эту запись (resolve_player_suit); анимации боя — через motion_skin.
    "i290014": Suit(
        suit_id="i290014",
        name="Рендзи Абараи",
        role_id=1,
        motion_folder="cloth14/idle",
        avatar_filename="userface_0_14_role.gif",
        pose_filename="people_013_pose.png",
    ),
}


def resolve_player_suit(player) -> Suit | None:
    """Stage 206 — ЭФФЕКТИВНЫЙ костюм игрока (аватар/имя/поза от одежды).

    Правило пользователя: «все статы, аватарки, анимации привязаны к своему
    костюму». Статы и анимации уже резолвятся от equipped_outfit
    (_refresh_stats / _player_skin_actions); эта функция доводит до той же
    модели ВНЕШНИЙ ОБЛИК:

      1. equipped_outfit (модель или outfit_inst_N) → OUTFITS_DB[outfit_id];
      2. у записи костюма есть "suit_id" → STARTER_SUITS[suit_id];
      3. нет связи/костюм не надет → классический suit из player.suit_id.

    Возвращает Suit или None (только если реестр пуст — не должен случаться).
    """
    from pockie_rpg.data.item_db import get_outfit

    model = getattr(player, "equipped_outfit", None)
    if isinstance(model, str) and model.startswith("outfit_inst_"):
        inst = player.outfit_instances.get(model)
        model = inst.get("outfit_id") if inst else None
    outfit = get_outfit(model) if isinstance(model, str) else None
    linked = outfit.get("suit_id") if outfit else None
    suit = STARTER_SUITS.get(linked) if linked else None
    if suit is not None:
        return suit
    return STARTER_SUITS.get(getattr(player, "suit_id", "")) \
        or next(iter(STARTER_SUITS.values()), None)


# ---------------------------------------------------------------------------
# ENEMY MOBS (backward-compat dict derived from ENEMY_DB)
# ---------------------------------------------------------------------------

_LEGACY_MOB_KEY_MAP: dict[str, str] = {
    "mob_1": "samurai_1", "mob_2": "samurai_2", "mob_3": "samurai_3",
    "mob_4": "samurai_4", "mob_5": "samurai_5", "mob_6": "samurai_6",
    "mob_7": "samurai_7", "mob_8": "samurai_8", "mob_9": "samurai_9",
    "mob_10": "samurai_10", "mob_11": "samurai_11", "mob_12": "samurai_12",
    "flower_1": "flower_1",
}


def _build_enemy_mobs_from_db() -> "dict[str, EnemyDef]":
    """Build the backward-compat ENEMY_MOBS dict from ENEMY_DB."""
    mobs: dict[str, EnemyDef] = {}
    for legacy_key, enemy_id in _LEGACY_MOB_KEY_MAP.items():
        tmpl = _ENEMY_DB.get(enemy_id)
        if tmpl is None:
            continue
        mobs[legacy_key] = EnemyDef(
            enemy_id=tmpl.enemy_id or enemy_id,
            mob_id=legacy_key,
            name=tmpl.name,
            level=tmpl.level,
            role_id=tmpl.role_id,
            hp_mul=tmpl.hp_mul,
            atk_mul=tmpl.atk_mul,
            xp_reward=tmpl.xp_reward,
            gold_reward=tmpl.gold_reward,
            is_stub=tmpl.is_stub,
            skills=tmpl.skills,
        )
    return mobs


ENEMY_MOBS: dict[str, EnemyDef] = _build_enemy_mobs_from_db()
