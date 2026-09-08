"""Equipment database — single source of truth for all gear (Layer A).

Stage 36 — added sell_price field to each item (scales with item_level).
Each item has item_level (default 1). Stats scale linearly: base * (1 + (item_level-1)*0.15).
Per RULE 15 (Single Equipment Standard): equipped_gear is the ONLY equipment dict.
"""
from __future__ import annotations


def scale_gear_stat(base_value: int, item_level: int) -> int:
    """Scale a gear stat by item_level (linear +15% per level above 1).

    Formula: scaled = base * (1 + (item_level - 1) * 0.15)
    """
    if item_level <= 1:
        return int(base_value)
    return int(base_value * (1 + (item_level - 1) * 0.15))


def get_sell_price(item_id: str) -> int:
    """Stage 36 — calculate sell price for an item (scales with item_level).

    Sell price = base_sell_price * (1 + (item_level - 1) * 0.15).
    Stage 187 — БАФЫ: цена из BUFF_DB[sell_price] (item_id = buff_id).
    Костюмы-инстансы (outfit_inst_N) считаются в UI (_get_sell_price) —
    их плюс живёт в PlayerState.outfit_instances.
    """
    from pockie_rpg.config import BUFF_DB
    buff = BUFF_DB.get(item_id)
    if buff is not None:
        return int(buff.get("sell_price", 0))

    item = EQUIPMENT_DB.get(item_id)
    if item is None:
        return 0
    base = item.get("sell_price", 10)
    item_level = item.get("item_level", 1)
    return scale_gear_stat(base, item_level)


EQUIPMENT_DB: dict[str, dict] = {
    # Stage 110 — WEAPON TEMPLATES (cleaned: only ID, name, level, min/max atk, icon).
    # Secondary stats are now generated DYNAMICALLY by generate_item() based on rarity.
    # Old hardcoded atk_mul/crit_rating/etc. have been REMOVED from all weapon templates.
    "weapon_wooden": {
        "name": "Деревянный меч",
        "slot": "weapon",
        "item_level": 1,
        "stats": {"min_atk": 3, "max_atk": 6},
        "icon_filename": "weapon_wooden.png",
        "sell_price": 15,
    },
    # Stage 172 — награда квеста «Материк Сакура окутан тьмой».
    # sell_price=0 — награду за сюжетный квест нельзя продать (цель квеста
    # «Первые шаги» требует надеть его; продажа сделала бы квест невыполнимым).
    "weapon_novice": {
        "name": "Оружие для новичка",
        "slot": "weapon",
        "item_level": 1,
        "stats": {"min_atk": 4, "max_atk": 8},
        "icon_filename": "weapon_wooden.png",
        "sell_price": 0,
    },
    "weapon_blunt2": {
        "name": "Булава новичка",
        "slot": "weapon",
        "item_level": 5,
        "stats": {"min_atk": 7, "max_atk": 13},
        "icon_filename": "weapon_blunt2.gif",
        "sell_price": 50,
    },
    "weapon_blunt3": {
        "name": "Стальная булава",
        "slot": "weapon",
        "item_level": 10,
        "stats": {"min_atk": 12, "max_atk": 22},
        "icon_filename": "weapon_blunt3.gif",
        "sell_price": 120,
    },
    "weapon_blunt4": {
        "name": "Боевой молот",
        "slot": "weapon",
        "item_level": 15,
        "stats": {"min_atk": 18, "max_atk": 32},
        "icon_filename": "weapon_blunt4.gif",
        "sell_price": 250,
    },
    "weapon_blunt5": {
        "name": "Молот разрушения",
        "slot": "weapon",
        "item_level": 20,
        "stats": {"min_atk": 26, "max_atk": 45},
        "icon_filename": "weapon_blunt5.gif",
        "sell_price": 500,
    },
    "weapon_blunt6": {
        "name": "Легендарный молот",
        "slot": "weapon",
        "item_level": 25,
        "stats": {"min_atk": 35, "max_atk": 60},
        "icon_filename": "weapon_blunt6.gif",
        "sell_price": 1000,
    },
    # Stage 112 — ARMOR TEMPLATES (cleaned: only defense + max_hp as main stats).
    # Secondary stats are now generated DYNAMICALLY by generate_item() based on rarity.
    "body_cloth2": {
        "name": "Кожаная броня",
        "slot": "body",
        "item_level": 5,
        "stats": {"defense": 12, "max_hp": 35},
        "icon_filename": "body_cloth2.gif",
        "sell_price": 50,
    },
    "body_cloth3": {
        "name": "Кольчуга",
        "slot": "body",
        "item_level": 10,
        "stats": {"defense": 22, "max_hp": 65},
        "icon_filename": "body_cloth3.gif",
        "sell_price": 120,
    },
    "body_cloth4": {
        "name": "Латы стража",
        "slot": "body",
        "item_level": 15,
        "stats": {"defense": 35, "max_hp": 105},
        "icon_filename": "body_cloth4.gif",
        "sell_price": 250,
    },
    "body_cloth5": {
        "name": "Доспех войны",
        "slot": "body",
        "item_level": 20,
        "stats": {"defense": 52, "max_hp": 155},
        "icon_filename": "body_cloth5.gif",
        "sell_price": 500,
    },
    "body_cloth6": {
        "name": "Легендарный доспех",
        "slot": "body",
        "item_level": 25,
        "stats": {"defense": 75, "max_hp": 220},
        "icon_filename": "body_cloth6.gif",
        "sell_price": 1000,
    },
    # Stage 118 — BOOTS TEMPLATES (5 levels: L5/L10/L15/L20/L25).
    # Same pattern as body armor: only main stats (defense + speed) baked in.
    # Secondary stats are generated DYNAMICALLY by generate_item() based on rarity.
    # L1 starter is the existing "boots_shinobi" entry above (kept for backward-compat).
    "boots_shoes2": {
        "name": "Туфли ловкости",
        "slot": "boots",
        "item_level": 5,
        "stats": {"defense": 3, "speed": 12},
        "icon_filename": "boots_shoes2.gif",
        "sell_price": 50,
    },
    "boots_shoes3": {
        "name": "Сапоги странника",
        "slot": "boots",
        "item_level": 10,
        "stats": {"defense": 6, "speed": 22},
        "icon_filename": "boots_shoes3.gif",
        "sell_price": 120,
    },
    "boots_shoes4": {
        "name": "Поножи стража",
        "slot": "boots",
        "item_level": 15,
        "stats": {"defense": 10, "speed": 35},
        "icon_filename": "boots_shoes4.gif",
        "sell_price": 250,
    },
    "boots_shoes5": {
        "name": "Сапоги войны",
        "slot": "boots",
        "item_level": 20,
        "stats": {"defense": 15, "speed": 52},
        "icon_filename": "boots_shoes5.gif",
        "sell_price": 500,
    },
    "boots_shoes6": {
        "name": "Легендарные поножи",
        "slot": "boots",
        "item_level": 25,
        "stats": {"defense": 22, "speed": 75},
        "icon_filename": "boots_shoes6.gif",
        "sell_price": 1000,
    },
    # Stage 119 — RING TEMPLATES (5 levels: L5/L10/L15/L20/L25).
    # Same pattern as body armor + boots: only main stats (crit_rating + pierce_rating)
    # baked in. Secondary stats are generated DYNAMICALLY by generate_item() based
    # on rarity. Rings share the "accessory" slot with the existing "amulet_clan"
    # (L1 starter, kept for backward-compat with existing save files).
    # NOTE: L5 uses ring1.png as a placeholder icon because the user forgot to
    # upload icon_equip_ring2.s110.gif. Replace ring_jade2.png with the real
    # ring2 sprite when available.
    "ring_jade2": {
        "name": "Кольцо нефрита",
        "slot": "accessory",
        "type": "ring",
        "item_level": 5,
        "stats": {"crit_rating": 5, "pierce_rating": 2},
        "icon_filename": "ring_jade2.png",
        "sell_price": 50,
    },
    "ring_jade3": {
        "name": "Кольцо клана",
        "slot": "accessory",
        "type": "ring",
        "item_level": 10,
        "stats": {"crit_rating": 10, "pierce_rating": 4},
        "icon_filename": "ring_jade3.gif",
        "sell_price": 120,
    },
    "ring_jade4": {
        "name": "Кольцо стража",
        "slot": "accessory",
        "type": "ring",
        "item_level": 15,
        "stats": {"crit_rating": 17, "pierce_rating": 6},
        "icon_filename": "ring_jade4.gif",
        "sell_price": 250,
    },
    "ring_jade5": {
        "name": "Кольцо войны",
        "slot": "accessory",
        "type": "ring",
        "item_level": 20,
        "stats": {"crit_rating": 26, "pierce_rating": 9},
        "icon_filename": "ring_jade5.gif",
        "sell_price": 500,
    },
    "ring_jade6": {
        "name": "Легендарное кольцо",
        "slot": "accessory",
        "type": "ring",
        "item_level": 25,
        "stats": {"crit_rating": 38, "pierce_rating": 13},
        "icon_filename": "ring_jade6.gif",
        "sell_price": 1000,
    },
    # Stage 123 — GLOVES TEMPLATES (5 levels: L5/L10/L15/L20/L25).
    # Main stats: defense + hit_rating (hands slot, per SLOT_MAIN_STATS).
    # L1 uses existing static "gloves_leather" (kept for backward-compat saves).
    "gloves_mitten2": {
        "name": "Перчатки ловкости",
        "slot": "hands",
        "item_level": 5,
        "stats": {"defense": 5, "hit_rating": 5},
        "icon_filename": "gloves_mitten2.gif",
        "sell_price": 50,
    },
    "gloves_mitten3": {
        "name": "Перчатки клана",
        "slot": "hands",
        "item_level": 10,
        "stats": {"defense": 10, "hit_rating": 10},
        "icon_filename": "gloves_mitten3.gif",
        "sell_price": 120,
    },
    "gloves_mitten4": {
        "name": "Перчатки стража",
        "slot": "hands",
        "item_level": 15,
        "stats": {"defense": 17, "hit_rating": 17},
        "icon_filename": "gloves_mitten4.gif",
        "sell_price": 250,
    },
    "gloves_mitten5": {
        "name": "Перчатки войны",
        "slot": "hands",
        "item_level": 20,
        "stats": {"defense": 26, "hit_rating": 26},
        "icon_filename": "gloves_mitten5.gif",
        "sell_price": 500,
    },
    "gloves_mitten6": {
        "name": "Легендарные перчатки",
        "slot": "hands",
        "item_level": 25,
        "stats": {"defense": 38, "hit_rating": 38},
        "icon_filename": "gloves_mitten6.gif",
        "sell_price": 1000,
    },
    # Stage 127 — BELT TEMPLATES (5 levels: L5/L10/L15/L20/L25).
    # Main stats: defense + tough_rating (belt slot, per SLOT_MAIN_STATS).
    # L1 uses existing static "belt_fabric" (kept for backward-compat saves).
    "belt_jade2": {
        "name": "Пояс ловкости",
        "slot": "belt",
        "item_level": 5,
        "stats": {"defense": 5, "tough_rating": 5},
        "icon_filename": "belt_jade2.gif",
        "sell_price": 50,
    },
    "belt_jade3": {
        "name": "Пояс клана",
        "slot": "belt",
        "item_level": 10,
        "stats": {"defense": 10, "tough_rating": 10},
        "icon_filename": "belt_jade3.gif",
        "sell_price": 120,
    },
    "belt_jade4": {
        "name": "Пояс стража",
        "slot": "belt",
        "item_level": 15,
        "stats": {"defense": 17, "tough_rating": 17},
        "icon_filename": "belt_jade4.gif",
        "sell_price": 250,
    },
    "belt_jade5": {
        "name": "Пояс войны",
        "slot": "belt",
        "item_level": 20,
        "stats": {"defense": 26, "tough_rating": 26},
        "icon_filename": "belt_jade5.gif",
        "sell_price": 500,
    },
    "belt_jade6": {
        "name": "Легендарный пояс",
        "slot": "belt",
        "item_level": 25,
        "stats": {"defense": 38, "tough_rating": 38},
        "icon_filename": "belt_jade6.gif",
        "sell_price": 1000,
    },
    # Stage 128 — HEAD TEMPLATES (5 levels: L5/L10/L15/L20/L25).
    # Main stats: defense + max_hp (head slot, per SLOT_MAIN_STATS).
    # L1 uses existing static "headband_ninja" (kept for backward-compat saves).
    "head_helm2": {
        "name": "Шлем ловкости",
        "slot": "head",
        "item_level": 5,
        "stats": {"defense": 7, "max_hp": 35},
        "icon_filename": "head_helm2.gif",
        "sell_price": 50,
    },
    "head_helm3": {
        "name": "Шлем клана",
        "slot": "head",
        "item_level": 10,
        "stats": {"defense": 13, "max_hp": 65},
        "icon_filename": "head_helm3.gif",
        "sell_price": 120,
    },
    "head_helm4": {
        "name": "Шлем стража",
        "slot": "head",
        "item_level": 15,
        "stats": {"defense": 21, "max_hp": 105},
        "icon_filename": "head_helm4.gif",
        "sell_price": 250,
    },
    "head_helm5": {
        "name": "Шлем войны",
        "slot": "head",
        "item_level": 20,
        "stats": {"defense": 32, "max_hp": 155},
        "icon_filename": "head_helm5.gif",
        "sell_price": 500,
    },
    "head_helm6": {
        "name": "Легендарный шлем",
        "slot": "head",
        "item_level": 25,
        "stats": {"defense": 45, "max_hp": 220},
        "icon_filename": "head_helm6.gif",
        "sell_price": 1000,
    },
    "headband_ninja": {
        "name": "Повязка шиноби",
        "slot": "head",
        "item_level": 1,
        "stats": {"max_hp": 100, "max_hp_mul": 5},  # Stage 48: +5% HP
        "icon_filename": "headband_ninja.png",
        "sell_price": 12,
    },
    "vest_ninja": {
        "name": "Жилет ниндзя",
        "slot": "body",
        "item_level": 1,
        "stats": {"defense": 5, "max_hp": 15},  # Stage 112: cleaned, only main stats
        "icon_filename": "vest_ninja.png",
        "sell_price": 18,
    },
    "gloves_leather": {
        "name": "Кожаные перчатки",
        "slot": "hands",
        "item_level": 1,
        "stats": {"hit_chance": 5},
        "icon_filename": "gloves_leather.png",
        "sell_price": 10,
    },
    "belt_fabric": {
        "name": "Тканевый пояс",
        "slot": "belt",
        "item_level": 1,
        # "parry_chance" — legacy-алиас множителя блока (collect_rating_pct("block")).
        # Мёртвый ключ "toughness" удалён (не имел алиаса, в бою не работал).
        "stats": {"parry_chance": 3},
        "icon_filename": "belt_fabric.png",
        "sell_price": 10,
    },
    "boots_shinobi": {
        "name": "Сандалии ниндзя",
        "slot": "boots",
        "item_level": 1,
        "stats": {"speed": 3, "dodge_mul": 5},  # Stage 48: +5% dodge (legacy → flat rating)
        "icon_filename": "boots_shinobi.png",
        "sell_price": 12,
    },
    # Stage 105 — new item demonstrating *_pct (percentage multiplier) keys.
    # These multiply the accumulated flat rating base (Step 2 of recalc).
    # Bonus is effective ONLY when Base_Flat > 0 (multiplicativity rule).
    "boots_wind": {
        "name": "Сапоги ветра",
        "slot": "boots",
        "item_level": 10,
        "stats": {"speed": 5, "dodge_pct": 10},  # Stage 105: +10% to total Dodge_Rating
        "icon_filename": "boots_shinobi.png",  # placeholder icon
        "sell_price": 200,
    },
    "gloves_assassin": {
        "name": "Перчатки ассасина",
        "slot": "hands",
        "item_level": 10,
        "stats": {"crit_pct": 8, "hit_pct": 5},  # Stage 105: +8% Crit, +5% Hit
        "icon_filename": "gloves_leather.png",  # placeholder icon
        "sell_price": 200,
    },
    "amulet_clan": {
        "name": "Амулет клана",
        "slot": "accessory",
        "type": "amulet",
        "item_level": 1,
        # "pierce" — legacy-алиас множителя пробивания (collect_rating_pct("pierce")).
        "stats": {"max_mp": 15, "max_hp": 30, "pierce": 5},
        "icon_filename": "amulet_clan.png",
        "sell_price": 20,
    },
    "suit_ichigo": {
        "name": "Костюм Ичиго",
        "slot": "outfit",
        "item_level": 1,
        "stats": {},
        "icon_filename": "suit_ichigo.png",
        # Stage 187 — продажа костюмов разрешена (микро-меню; 50 зол).
        # В массовую продажу костюмы по-прежнему НЕ попадают.
        "sell_price": 50,
    },
}

# Stage 39 — Outfit slots (separate from gear).
GEAR_SLOTS: list[str] = ["weapon", "head", "body", "hands", "belt", "boots", "accessory"]
OUTFIT_SLOTS: list[str] = ["outfit"]


# ---------------------------------------------------------------------------
# Stage 103 — OUTFITS_DB (Pockie Ninja original costume system)
# ---------------------------------------------------------------------------
# Each outfit provides TWO BMV coefficients per primary stat (STR/AGI/STA):
#
# 1. BMV-Цена (bmv_price) — how many stat units needed for 1 rating point.
#    Used to compute Dodge/Hit/Tough ratings via floor division.
#    LOWER bmv_price = each stat unit MORE effective.
#    Example (suit_ichigo bmv_price.agility=10):
#        AGI=249 → floor(249/10) = 24 dodge_rating
#        Real_Pct_Dodge = 24 * 0.0625 = 1.5%
#
# 2. BMV-Прирост (growth) — how much the stat grows per level-up.
#    Each level-up: stat += growth.current.
#    UI shows: "Ловкость 41 (+1.35) | Макс (+1.65)" — current (max).
#    growth.current: actual per-level growth at current outfit tier.
#    growth.max: maximum possible growth (for upgradeable outfits).
#
# Costume archetypes (build diversity):
#   - suit_ichigo       (agility_dps):     bmv_price 30/10/20 — balanced AGI
#   - suit_samurai_tank (strength_tank):  bmv_price 15/30/15 — STR/STA heavy
#   - suit_ninja_evasion(agility_evasion):bmv_price 40/5/30  — extreme AGI
#   - suit_ogre_brute   (stamina_bruiser):bmv_price 20/40/10  — STA-heavy
#
# Each costume also has base_stats (added to player's 10/10/10 base on equip).

OUTFITS_DB: dict[str, dict] = {
    "suit_ichigo": {
        "name": "Костюм Ичиго (Куросаки)",
        "type": "agility",
        "archetype": "agility_dps",
        "base_stats": {"strength": 10, "agility": 15, "stamina": 8},
        # Stage 103 — BMV-Цена (cost) per stat.
        "bmv_price": {"strength": 30, "agility": 10, "stamina": 20},
        # Stage 103 — BMV-Прирост (growth) per level-up: {current, max} per stat.
        "growth": {
            "strength": {"current": 0.6, "max": 1.0},
            "agility":  {"current": 1.35, "max": 1.65},
            "stamina":  {"current": 0.5, "max": 0.8},
        },
        # Legacy aliases (Stage 102 backward-compat).
        "bmv": {"strength": 30, "agility": 10, "stamina": 20},
        "growth_bonus": {"strength": 0.6, "agility": 1.35, "stamina": 0.5},
        "icon_filename": "suit_ichigo.png",
    },
    "suit_samurai_tank": {
        "name": "Костюм Самурая-танка",
        "type": "strength",
        "archetype": "strength_tank",
        "base_stats": {"strength": 15, "agility": 5, "stamina": 15},
        "bmv_price": {"strength": 15, "agility": 30, "stamina": 15},
        "growth": {
            "strength": {"current": 1.5, "max": 2.0},
            "agility":  {"current": 0.3, "max": 0.5},
            "stamina":  {"current": 1.2, "max": 1.6},
        },
        "bmv": {"strength": 15, "agility": 30, "stamina": 15},
        "growth_bonus": {"strength": 1.5, "agility": 0.3, "stamina": 1.2},
        "icon_filename": "suit_ichigo.png",  # placeholder icon
    },
    "suit_ninja_evasion": {
        "name": "Костюм Ниндзя (Уворот)",
        "type": "agility",
        "archetype": "agility_evasion",
        "base_stats": {"strength": 5, "agility": 20, "stamina": 8},
        "bmv_price": {"strength": 40, "agility": 5, "stamina": 30},
        "growth": {
            "strength": {"current": 0.3, "max": 0.5},
            "agility":  {"current": 2.0, "max": 2.5},
            "stamina":  {"current": 0.5, "max": 0.8},
        },
        "bmv": {"strength": 40, "agility": 5, "stamina": 30},
        "growth_bonus": {"strength": 0.3, "agility": 2.0, "stamina": 0.5},
        "icon_filename": "suit_ichigo.png",
    },
    "suit_ogre_brute": {
        "name": "Костюм Огра (Громила)",
        "type": "stamina",
        "archetype": "stamina_bruiser",
        "base_stats": {"strength": 12, "agility": 5, "stamina": 18},
        "bmv_price": {"strength": 20, "agility": 40, "stamina": 10},
        "growth": {
            "strength": {"current": 0.8, "max": 1.2},
            "agility":  {"current": 0.3, "max": 0.5},
            "stamina":  {"current": 1.7, "max": 2.2},
        },
        "bmv": {"strength": 20, "agility": 40, "stamina": 10},
        "growth_bonus": {"strength": 0.8, "agility": 0.3, "stamina": 1.7},
        "icon_filename": "suit_ichigo.png",
    },
}


def get_outfit(outfit_id: str) -> dict | None:
    """Look up an outfit definition from OUTFITS_DB by id."""
    return OUTFITS_DB.get(outfit_id)


def get_equipment(item_id: str) -> dict | None:
    """Look up an equipment definition from EQUIPMENT_DB by id."""
    return EQUIPMENT_DB.get(item_id)


# ---------------------------------------------------------------------------
# Stage 47 — FORGE (Кузница): enchant system
# ---------------------------------------------------------------------------

def get_enchant_cost(current_level: int) -> int:
    """Gold cost to upgrade from current_level to current_level+1.

    Formula: BASE * (current_level + 1) ^ GROWTH
    Example: 0→1 = 100*1^1.15 = 100, 5→6 = 100*6^1.15 = 843, 19→20 = 100*20^1.15 = 3257
    """
    from pockie_rpg.config import ENCHANT_COST_BASE, ENCHANT_COST_GROWTH
    return int(ENCHANT_COST_BASE * (current_level + 1) ** ENCHANT_COST_GROWTH)


def get_enchanted_stat(base_value: int, enchant_level: int) -> int:
    """Apply enchant bonus to a single stat value.

    Formula: base * (1 + enchant_level * ENCHANT_STAT_MULTIPLIER)
    Example (weapon_wooden atk 3, ENCHANT_STAT_MULTIPLIER=0.5):
        enchant 0:  3 * 1.0 = 3
        enchant 1:  3 * 1.5 = 4
        enchant 5:  3 * 3.5 = 10
        enchant 10: 3 * 6.0 = 18
        enchant 20: 3 * 11.0 = 33
    """
    from pockie_rpg.config import ENCHANT_STAT_MULTIPLIER
    return int(base_value * (1 + enchant_level * ENCHANT_STAT_MULTIPLIER))


def get_item_stats_with_enchant(item_id: str, enchant_level: int, player=None) -> dict[str, int]:
    """Stage 115 — Get all stats of an item after applying item_level + enchant.

    Stage 115 — now accepts optional `player` parameter to resolve generated
    items via player.get_item_definition(). Falls back to EQUIPMENT_DB for
    static items when player is None.

    Returns a dict of {stat_key: final_value} (e.g., {"min_atk": 10, "max_atk": 18}).
    """
    # Stage 115 — resolve item via player if available (supports generated items).
    if player is not None and hasattr(player, "get_item_definition"):
        item = player.get_item_definition(item_id)
    else:
        item = EQUIPMENT_DB.get(item_id)
    if item is None:
        return {}
    item_level = item.get("item_level", 1)
    result: dict[str, int] = {}
    for stat, base_val in item.get("stats", {}).items():
        scaled = scale_gear_stat(base_val, item_level)
        enchanted = get_enchanted_stat(scaled, enchant_level)
        result[stat] = enchanted
    return result


def is_stackable_item(item_id: str) -> bool:
    """Stage 183 — расходники (бафы) стакаются в одной ячейке инвентаря.

    Оружие/броня — уникальные предметы (каждый инстанс ценен) — НЕ стакаются.
    Бафы — безликие расходники: N копий = одна ячейка с цифрой.
    """
    from pockie_rpg.config import BUFF_DB
    return item_id in BUFF_DB


def get_buff_item(item_id: str) -> dict | None:
    """Stage 180 — resolve a buff consumable id (BUFF_DB) to a display dict.

    Бафы — расходники, НЕ лежат в EQUIPMENT_DB: инвентарю/тултипам нужен
    псевдо-предмет с именем и иконкой. rarity="Grey" безопасен для
    RARITY_SLOT_BG; "is_buff": True — маркер для будущей UI-логики
    (контекст «Активировать» вместо «Надеть»).
    """
    from pockie_rpg.config import BUFF_DB
    buff = BUFF_DB.get(item_id)
    if buff is None:
        return None
    return {
        "name": buff.get("name", item_id),
        "slot": "consumable",
        "item_level": 1,
        "rarity": "Grey",
        "icon_filename": buff.get("icon_filename"),
        "stats": {},
        "sell_price": 0,
        "level_requirement": 1,
        "is_buff": True,
        "desc": buff.get("desc", ""),
    }


def starter_items() -> list[str]:
    """Return item_ids that a new player starts with in inventory."""
    return ["weapon_wooden", "headband_ninja", "vest_ninja", "gloves_leather",
            "belt_fabric", "boots_shinobi", "amulet_clan",
            "weapon_blunt2", "weapon_blunt3", "weapon_blunt4", "weapon_blunt5", "weapon_blunt6",
            "body_cloth2", "body_cloth3", "body_cloth4", "body_cloth5", "body_cloth6",
            # Stage 118 — boots templates added to starter inventory.
            "boots_shoes2", "boots_shoes3", "boots_shoes4", "boots_shoes5", "boots_shoes6",
            # Stage 119 — ring templates added to starter inventory.
            "ring_jade2", "ring_jade3", "ring_jade4", "ring_jade5", "ring_jade6",
            # Stage 123 — gloves templates added to starter inventory.
            "gloves_mitten2", "gloves_mitten3", "gloves_mitten4", "gloves_mitten5", "gloves_mitten6",
            # Stage 127 — belt templates added to starter inventory.
            "belt_jade2", "belt_jade3", "belt_jade4", "belt_jade5", "belt_jade6",
            # Stage 128 — head templates added to starter inventory.
            "head_helm2", "head_helm3", "head_helm4", "head_helm5", "head_helm6",
            # Stage 160 — 6 костюмов Ичиго в стартовом комплекте: тест синтеза
            # (главный + 2 катализатора той же модели = одна попытка; 6 штук
            # дают две полные попытки либо цепочку с переносом +N).
            "suit_ichigo", "suit_ichigo", "suit_ichigo",
            "suit_ichigo", "suit_ichigo", "suit_ichigo",
            # Stage 180/181 — бафы для теста: по 3 штуки каждого вида опыта
            # (проверка активации, стакания и обновления времени).
            "buff_xp_50", "buff_xp_50", "buff_xp_50",
            "buff_xp_100", "buff_xp_100", "buff_xp_100",
            "buff_xp_150", "buff_xp_150", "buff_xp_150",
            "buff_xp_200", "buff_xp_200", "buff_xp_200",
            "buff_atk_10", "buff_atk_25"]


# ---------------------------------------------------------------------------
# Stage 108/169 — PROCEDURAL ITEM GENERATION (per task spec)
# ---------------------------------------------------------------------------
# generate_item(level, rarity, item_type) создаёт dict предмета:
#   - фиксированные главные статы из <TYPE>_BALANCE_TABLE (Stage 169 —
#     одна spec-таблица _GENERATOR_SPECS вместо 7 копипаст-функций);
#   - случайные вторичные статы из SECONDARY_STAT_POOL (без дубликатов);
#   - level_requirement (надеть можно не раньше уровня);
#   - rarity (Grey/Blue/Purple/Gold/Red) для раскраски UI.
#
# Rarity → secondary stat count:
#   Grey=0, Blue=1, Purple=2, Gold=3, Red=4
#
# Rolled values use the level-specific flat_min/flat_max and pct_min/pct_max
# ranges from the item type's balance table.

import random as _random

from pockie_rpg.config import (
    ARMOR_BALANCE_TABLE,
    ARMOR_TEMPLATE_MAP,
    BELT_BALANCE_TABLE,
    BELT_TEMPLATE_MAP,
    BOOTS_BALANCE_TABLE,
    BOOTS_TEMPLATE_MAP,
    GLOVES_BALANCE_TABLE,
    GLOVES_TEMPLATE_MAP,
    HEAD_BALANCE_TABLE,
    HEAD_TEMPLATE_MAP,
    RARITY_COLORS,
    RING_BALANCE_TABLE,
    RING_TEMPLATE_MAP,
    SECONDARY_STAT_POOL,
    WEAPON_BALANCE_TABLE,
    WEAPON_LEVELS,
    WEAPON_TEMPLATE_MAP,
)

# ---------------------------------------------------------------------------
# Stage 169 (аудит 4.3) — ЕДИНЫЙ процедурный генератор предметов.
# ---------------------------------------------------------------------------
# Раньше здесь было 7 копипаст-функций generate_weapon/armor/boots/ring/
# gloves/belt/head (~450 строк), отличавшихся ТОЛЬКО таблицей баланса,
# шаблоном, слотом, набором главных статов и базой цены продажи. Теперь —
# таблица спецификаций _GENERATOR_SPECS + одна функция generate_item().
# Порядок обращений к RNG сохранён (shuffle → randint на каждую вторичную
# стату), поэтому выпадающие предметы идентичны прежним (дифф-фаззинг
# scripts/diag_stage169_gen.py, 1050 кейсов).
#
# Rarity → количество вторичных статов: Grey=0, Blue=1, Purple=2, Gold=3, Red=4.
# Цена продажи: balance[sell_base] * 10 * _RARITY_SELL_MULTIPLIER[rarity].

_RARITY_SELL_MULTIPLIER: dict[str, int] = {
    "Grey": 1, "Blue": 2, "Purple": 4, "Gold": 8, "Red": 16,
}

_GENERATOR_SPECS: dict[str, dict] = {
    "weapon": {
        "table": WEAPON_BALANCE_TABLE, "templates": WEAPON_TEMPLATE_MAP,
        "main_stats": ("min_atk", "max_atk"), "sell_base": "min_atk",
        "slot": "weapon", "fallback_name": "Оружие L{n}",
        "fallback_icon": "weapon_wooden.png",
        # item_type в dict НЕ пишется — 1:1 с прежним generate_weapon()
        # (ключ отсутствовал в сгенерированном оружии всегда).
        "item_type": None,
    },
    "armor": {
        "table": ARMOR_BALANCE_TABLE, "templates": ARMOR_TEMPLATE_MAP,
        "main_stats": ("defense", "max_hp"), "sell_base": "defense",
        "slot": "body", "fallback_name": "Броня L{n}",
        "fallback_icon": "vest_ninja.png", "item_type": "armor",
    },
    "boots": {
        "table": BOOTS_BALANCE_TABLE, "templates": BOOTS_TEMPLATE_MAP,
        "main_stats": ("defense", "speed"), "sell_base": "defense",
        "slot": "boots", "fallback_name": "Обувь L{n}",
        "fallback_icon": "boots_shinobi.png", "item_type": "boots",
    },
    "ring": {
        "table": RING_BALANCE_TABLE, "templates": RING_TEMPLATE_MAP,
        "main_stats": ("crit_rating", "pierce_rating"), "sell_base": "crit_rating",
        "slot": "accessory", "fallback_name": "Кольцо L{n}",
        "fallback_icon": "ring1.png", "item_type": "ring",
    },
    "gloves": {
        "table": GLOVES_BALANCE_TABLE, "templates": GLOVES_TEMPLATE_MAP,
        "main_stats": ("defense", "hit_rating"), "sell_base": "defense",
        "slot": "hands", "fallback_name": "Перчатки L{n}",
        "fallback_icon": "gloves_leather.png", "item_type": "gloves",
    },
    "belt": {
        "table": BELT_BALANCE_TABLE, "templates": BELT_TEMPLATE_MAP,
        "main_stats": ("defense", "tough_rating"), "sell_base": "defense",
        "slot": "belt", "fallback_name": "Пояс L{n}",
        "fallback_icon": "belt_fabric.png", "item_type": "belt",
    },
    "head": {
        "table": HEAD_BALANCE_TABLE, "templates": HEAD_TEMPLATE_MAP,
        "main_stats": ("defense", "max_hp"), "sell_base": "defense",
        "slot": "head", "fallback_name": "Шлем L{n}",
        "fallback_icon": "headband_ninja.png", "item_type": "head",
    },
}


def generate_item(item_level: int, rarity: str, item_type: str = "weapon") -> dict:
    """Stage 112/118/119/123 — процедурная генерация предмета любого слота.

    Args:
        item_level: int from WEAPON_LEVELS (1, 5, 10, 15, 20, 25).
        rarity: str from RARITY_COLORS ("Grey", "Blue", "Purple", "Gold", "Red").
        item_type: "weapon", "armor", "boots", "ring", "gloves", "belt", "head".

    Returns:
        Item dict: name (суффикс [Rarity] вне Grey), slot, item_level,
        level_requirement, rarity, stats (главные из баланса + случайные
        вторичные по редкости, без дубликатов и без пересечения с главными),
        icon_filename, sell_price, generated=True, template_id — и item_type
        (кроме weapon, как в прежних функциях).
    """
    spec = _GENERATOR_SPECS.get(item_type)
    if spec is None:
        raise ValueError(
            f"Unknown item_type '{item_type}'. Use "
            f"'{', '.join(_GENERATOR_SPECS)}'."
        )
    if item_level not in WEAPON_LEVELS:
        raise ValueError(
            f"Invalid item_level {item_level} for '{item_type}'. "
            f"Must be one of {WEAPON_LEVELS}."
        )
    if rarity not in RARITY_COLORS:
        raise ValueError(
            f"Invalid rarity '{rarity}'. Must be one of {list(RARITY_COLORS.keys())}."
        )

    balance = spec["table"][item_level]
    stat_count = RARITY_COLORS[rarity]

    # Базовый шаблон (имя + иконка) из EQUIPMENT_DB.
    template_id = spec["templates"][item_level]
    template = EQUIPMENT_DB.get(template_id, {})
    base_name = template.get("name", spec["fallback_name"].format(n=item_level))
    icon_filename = template.get("icon_filename", spec["fallback_icon"])

    # Шаг 1 — фиксированные главные статы из таблицы баланса.
    stats: dict[str, int] = {k: balance[k] for k in spec["main_stats"]}

    # Шаг 2 — случайные вторичные статы (без дубликатов; главные исключены
    # из пула, чтобы не молча перезаписать главный стат).
    if stat_count > 0:
        main_stat_keys = set(stats.keys())
        pool = [s for s in SECONDARY_STAT_POOL if s[0] not in main_stat_keys]
        _random.shuffle(pool)
        chosen = pool[:stat_count]
        for gear_key, stat_type, _label in chosen:
            if stat_type == "flat":
                value = _random.randint(balance["flat_min"], balance["flat_max"])
            else:
                value = _random.randint(balance["pct_min"], balance["pct_max"])
            stats[gear_key] = value

    # Цена продажи: база ×10 × множитель редкости.
    sell_price = balance[spec["sell_base"]] * 10 * _RARITY_SELL_MULTIPLIER.get(rarity, 1)

    display_name = f"{base_name} [{rarity}]" if rarity != "Grey" else base_name

    item = {
        "name": display_name,
        "slot": spec["slot"],
        "item_level": item_level,
        "level_requirement": item_level,
        "rarity": rarity,
        "stats": stats,
        "icon_filename": icon_filename,
        "sell_price": sell_price,
        "generated": True,
        "template_id": template_id,
    }
    if spec["item_type"] is not None:
        item["item_type"] = spec["item_type"]
    return item




# ---------------------------------------------------------------------------
# Stage 51 — GEM SYSTEM (Камни)
# ---------------------------------------------------------------------------
# Gems are colored stones that can be inserted into weapon/gear gem slots
# (max 3 slots per item). Each gem provides a flat stat bonus that scales
# with the gem's level (1-10). Gems can be upgraded (Камни tab) or synthesized
# (Синтез tab: 2 gems of same type+level → 1 gem of level+1).

GEMS_DB: dict[str, dict] = {
    "gem_red": {
        "name": "Рубин",
        "color": (220, 60, 60),       # red
        "stat_key": "strength",        # bonus to STR
        "stat_label": "Сила",
        "base_bonus": 5,              # L1=5, L2=7, L3=9... (3 + level*2)
        "growth": 2,                  # +2 per level
        "icon_prefix": "gem_red",     # icon: gem_red_1.gif ... gem_red_10.gif
    },
    "gem_blue": {
        "name": "Сапфир",
        "color": (60, 120, 220),      # blue
        "stat_key": "defense",        # bonus to defense
        "stat_label": "Защита",
        "base_bonus": 50,             # L1=50, L2=150, L3=300... (50 * n*(n+1)/2)
        "growth": "triangular",       # special: 50 * n*(n+1)/2
        "icon_prefix": "gem_blue",
    },
    "gem_green": {
        "name": "Изумруд",
        "color": (60, 200, 100),      # green
        "stat_key": "agility",        # bonus to AGI
        "stat_label": "Ловкость",
        "base_bonus": 5,              # L1=5, L2=7, L3=9... (3 + level*2)
        "growth": 2,
        "icon_prefix": "gem_green",
    },
    "gem_yellow": {
        "name": "Топаз",
        "color": (230, 200, 60),      # yellow
        "stat_key": "stamina",        # bonus to STA
        "stat_label": "Выносливость",
        "base_bonus": 5,              # L1=5, L2=7, L3=9... (3 + level*2)
        "growth": 2,
        "icon_prefix": "gem_yellow",
    },
    "gem_orange": {
        "name": "Янтарь",
        "color": (230, 140, 60),      # orange
        "stat_key": "crit_rating",    # bonus to crit rating
        "stat_label": "Крит",
        "base_bonus": 5,              # L1=5, L2=7, L3=9... (3 + level*2)
        "growth": 2,
        "icon_prefix": "gem_orange",
    },
}


def get_gem(gem_type: str) -> dict | None:
    """Look up a gem definition by type id (e.g., 'gem_red')."""
    return GEMS_DB.get(gem_type)


def get_gem_stat_bonus(gem_type: str, level: int) -> int:
    """Return the stat bonus a gem provides at the given level.

    Stage 53 — new gem stat formulas:
      STR/AGI/STA/Crit (red/green/yellow/orange): 3 + level*2 (L1=5, L2=7, L3=9...)
      Defense (blue/sapphire): 50 * level * (level+1) / 2 (L1=50, L2=150, L3=300...)
    """
    gem = GEMS_DB.get(gem_type)
    if gem is None:
        return 0
    base = gem["base_bonus"]
    growth = gem.get("growth", 0)
    if growth == "triangular":
        # Defense: base * n*(n+1)/2 (triangular number × base)
        return base * level * (level + 1) // 2
    # Stage 169 (аудит 4.4) — линейный рост БЕРЁТСЯ ИЗ БД: base_bonus=5,
    # growth=2 → L1=5, L2=7, L3=9... (математически идентично прежнему
    # захардкоженному 3 + level*2; теперь правка БД реально меняет бонус).
    return base + (level - 1) * growth


def get_gem_icon_filename(gem_type: str, level: int) -> str:
    """Return the icon filename for a gem at the given level (1-10).

    Example: gem_red L3 → 'gem_red_3.gif'
    """
    gem = GEMS_DB.get(gem_type)
    if gem is None:
        return ""
    prefix = gem.get("icon_prefix", gem_type)
    return f"{prefix}_{level}.gif"


def get_gem_upgrade_cost(current_level: int) -> int:
    """Gold cost to upgrade a gem from current_level to current_level+1.

    Formula: BASE * (current_level) ^ GROWTH.
    Example: 1→2 = 50*1^1.3 = 50, 5→6 = 50*5^1.3 = 406.
    """
    from pockie_rpg.config import GEM_UPGRADE_COST_BASE, GEM_UPGRADE_COST_GROWTH
    if current_level < 1:
        current_level = 1
    return int(GEM_UPGRADE_COST_BASE * (current_level ** GEM_UPGRADE_COST_GROWTH))


def get_gem_upgrade_chance(current_level: int) -> int:
    """Success chance (%) to upgrade from current_level to current_level+1.

    Level 1→2 = 100%, then -10% per level (floor 10%).
    """
    from pockie_rpg.config import (
        GEM_UPGRADE_CHANCE_BASE,
        GEM_UPGRADE_CHANCE_DECAY,
        GEM_UPGRADE_CHANCE_FLOOR,
    )
    if current_level < 1:
        return GEM_UPGRADE_CHANCE_BASE
    chance = GEM_UPGRADE_CHANCE_BASE - (current_level - 1) * GEM_UPGRADE_CHANCE_DECAY
    return max(GEM_UPGRADE_CHANCE_FLOOR, chance)


def get_synthesis_result_level(gem_a_level: int, gem_b_level: int) -> int | None:
    """Synthesis: 2 gems of SAME level → 1 gem of level+1.

    Returns the resulting level, or None if the levels don't match.
    """
    if gem_a_level != gem_b_level:
        return None
    return gem_a_level + 1
