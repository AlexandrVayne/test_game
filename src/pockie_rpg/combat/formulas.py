"""Combat formulas — математика боя Pockie Ninja (Stage 168 / аудит 5.1).

Вынесено из `config.py` (был god-module на 2891 строку: UI-константы, энумы,
TowerDB И ~1000 строк боевых формул в одном файле). Теперь боевая математика
живёт в combat-пакете, где ей место по домену.

ВАЖНО (обратно-совместимость): `config.py` в КОНЦЕ файла ре-экспортирует все
имена этого модуля, поэтому ВСЕ существующие импорты вида

    from pockie_rpg.config import calc_hit_rating, RATING_PCT_STEP, ...

продолжают работать без правок. НОВЫЙ код должен импортировать напрямую:

    from pockie_rpg.combat.formulas import calc_hit_rating

Модуль НЕ импортирует ничего из pockie_rpg (только stdlib) — это ломает
циклическую зависимость «combat → config → combat» и позволяет config.py
безопасно ре-экспортировать эти имена.

Содержимое (без изменений логики, дословно из config.py Stage 103/104/137):
  * RATINGS (плоские целые, БЕЗ капа): dodge/hit/tough/block/pierce/crit.
  * RATING → PERCENT по шагам: ШАГ_А=0.0625 (крит-шанс/блок/антиблок),
    ШАГ_Б=0.125 (крит-урон/стойкость), гипербола K=1354 (защита/пробивание).
  * HIT CHANCE: 100 − (dodge% − hit%), кламп [5, 100].
  * DAMAGE PIPELINE: Crit → Защита (def − break) → Блок (block − antiblock).
"""
from __future__ import annotations

# ===========================================================================
# Stage 103 — POCKIE NINJA ORIGINAL COMBAT MATH (per task spec)
# ===========================================================================
#
# Strictly implements the original Pockie Ninja combat system:
#
# 1. PRIMARY STATS + BMV-Прирост (level-up growth):
#    Each Costume has BMV_Прирост per primary stat (STR/AGI/STA).
#    On every level-up: stat += growth.current.
#    UI shows: "Ловкость 41 (+1.35) | Макс (+1.65)".
#
# 2. RATINGS (flat integers, NO CAP):
#    Dodge_Rating = floor(AGI / bmv_price_agi) + flat_gear_dodge
#        Example: AGI=249, bmv_price_agi=11 → floor(249/11) = 22
#    Hit_Rating   = floor(STR / bmv_price_str) + flat_gear_hit - STR_THRESHOLD
#        If STR < STR_THRESHOLD (150) and no flat_gear → 0.
#        floor() truncates fractional parts.
#
# 3. RATING → PERCENT (1/16 = 0.0625):
#    1 rating unit = 0.0625% (mathematical step 1/16).
#    No caps on percentage stacking — player can collect 150%+ dodge/hit.
#
# 4. COMBAT HIT CHANCE (linear difference, hard caps):
#    Final_Hit% = 100 - (Defender_Dodge% - Attacker_Hit%)
#    Hard caps: [HIT_FLOOR_PCT=5%, HIT_CAP_PCT=100%]

# Rating → Percent conversion. 1 rating unit = 1/16 % = 0.0625%.
RATING_PCT_STEP: float = 0.0625
RATING_PCT_DIVISOR: int = 16  # = 1 / 0.0625

# Stage 104 — Three fixed math steps (ШАГ) for rating→% conversion.
# ШАГ_А (Global Base Step) = 0.0625% — used for Crit Chance, Toughness Chance Reduction, Block Chance.
# ШАГ_Б (Crit Damage Step) = 0.125%  — used for Crit Damage Bonus, Toughness Damage Reduction.
CRIT_CHANCE_STEP: float = 0.0625       # ШАГ_А — crit chance, tough chance reduction, block chance
CRIT_DAMAGE_STEP: float = 0.125        # ШАГ_Б — crit damage bonus, tough damage reduction

# Stage 137 — ОРИГИНАЛ (вики + тултипы 75 лвл): пара Блок/Антиблок идёт через /16
# (тот же ШАГ_А), а пара Защита/Пробивание защиты — ГИПЕРБОЛА с K=1354
# (def=1604 → -54.23%, break=2072 → +60.48% — сверено с тултипами оригинала
# до сотых). КАПОВ НЕТ: рейтинги могут быть 5000/10000+.
DEFENSE_BREAK_CONSTANT: int = 1354    # K гиперболы пары Защита/Пробивание

# Stage 104 — Damage pipeline constants.
CRIT_BASE_CHANCE_PCT: int = 0          # base crit chance = 0% (no natural crit)
CRIT_BASE_DAMAGE_PCT: int = 150        # base crit damage = 150% of current damage
BLOCK_DAMAGE_MULTIPLIER: float = 0.60  # successful block reduces damage to 60% (i.e. -40%)

# Stage 170 — AP-механика FightSystem (fight.py; значения из магических чисел
# Stage 122, перенесены без изменения).
AP_CAP: float = 20.0                   # кап банка AP за тик; должен быть >= максимальной скорости бойца, иначе скорость обрезается
AP_DEADLOCK_NUDGE: float = 0.01        # сдвиг при равных AP/speed (anti-deadlock)

# Stage 105 — Flat/Percentage separation for rating calculation.
#
#   *_rating (Flat):      flat rating bonuses from gear/gems.
#                         Added directly to Base_Flat (Step 1).
#   *_pct (Percentage):   percentage multipliers from gear/buffs.
#                         Summed into Pct_Sum (Step 2), then multiplied.
#                         These are NOT added to final % chance — they
#                         amplify the FLAT rating base.
#
# Formula (per task spec):
#   Base_Flat    = stats_contribution + gear_flat + gem_flat
#   Pct_Sum      = sum(*_pct from all gear + active buffs)
#   Final_Rating = floor(Base_Flat * (1 + Pct_Sum / 100))
#   Real_Pct     = Final_Rating * ШАГ (e.g., 0.0625 for Dodge/Crit/Block/Hit)
#
# Multiplicativity rule: % bonuses are EFFECTIVE only when Base_Flat is
# already high (from stats + flat gear + gems). Low base → bonus burns
# in the floor truncation.
#
# Example (per task spec):
#   Base_Flat = 22 (AGI rating) + 28 (gem flat) = 50
#   Pct_Sum   = 10% (boots) + 5% (scroll buff) = 15%
#   Final     = floor(50 * 1.15) = floor(57.5) = 57
#   Real_Pct  = 57 * 0.0625 = 3.56% (display)
#
# Zero-base protection (per task spec):
#   Base_Flat = 5, Pct_Sum = +10% → floor(5 * 1.1) = floor(5.5) = 5
#   Bonus burns (base too small).

# Names of the 8 rating characteristics (used by apply_pct_bonus and recalc).
RATING_STAT_KEYS: tuple[str, ...] = (
    "dodge", "hit", "tough", "crit", "block", "pierce", "antiblock",
)


def apply_pct_bonus(base_flat: int, pct_sum: float) -> int:
    """Stage 105 — Apply percentage multiplier to flat rating base.

    Final_Rating = floor(Base_Flat * (1 + Pct_Sum / 100))

    Floor truncation (per task spec): fractional part is ALWAYS discarded.
    This means small bases "burn" the percentage bonus (e.g., base=5, +10%
    → 5*1.1=5.5 → floor = 5, bonus lost).

    Args:
        base_flat: the flat rating sum (stats + gear_flat + gem_flat).
        pct_sum:   total percentage from all gear *_pct keys + active buffs.
                   Can be negative (debuffs), zero (no bonus), or positive.

    Returns:
        Final integer rating (>= 0). Never negative.

    Examples (per task spec):
        apply_pct_bonus(50, 15.0) → floor(50 * 1.15) = floor(57.5) = 57
        apply_pct_bonus(5, 10.0)  → floor(5 * 1.1) = floor(5.5) = 5 (burned)
        apply_pct_bonus(0, 100.0) → 0 (zero base — no bonus can apply)
        apply_pct_bonus(100, 0.0) → 100 (no bonus)
        apply_pct_bonus(100, -20.0) → floor(100 * 0.8) = 80 (debuff)
    """
    if base_flat <= 0:
        return 0
    if pct_sum == 0:
        return base_flat
    multiplier = 1.0 + (pct_sum / 100.0)
    if multiplier <= 0:
        # Total debuff exceeds 100% — clamp to 0 (rating cannot go negative).
        return 0
    final = int(base_flat * multiplier)  # int() truncates toward zero = floor for positive
    return max(0, final)


def collect_rating_pct(bonuses: dict, stat_key: str) -> float:
    """Stage 106 — Collect percentage modifiers (multipliers) for a rating stat.

    IRON RULE (per task spec): ANY '%' sign on items/buffs is ALWAYS a
    MULTIPLIER for the flat rating base. NO item may add/subtract pure % to
    the final combat chance. Percentages from gear affect ONLY the flat
    rating base BEFORE it is converted to combat probability.

    Collects ALL percentage sources for the given stat:
      - NEW Stage 105 keys: `<stat>_pct` (e.g., dodge_pct, crit_pct)
      - LEGACY keys: old gear databases used different names for the same
        concept (percentage multiplier). These are ALSO treated as multipliers
        (NOT converted to flat rating):
          dodge     → dodge_mul
          hit       → hit_chance
          crit      → crit_chance
          block     → parry_chance
          pierce    → pierce
          tough     → (no legacy alias)

    Legacy keys are SUMMED with new *_pct keys, then the total is applied as
    a multiplier to Base_Flat in apply_pct_bonus (Step B of recalc).

    Args:
        bonuses: the gear bonuses dict (from PlayerState.get_gear_bonuses()).
        stat_key: one of RATING_STAT_KEYS ("dodge", "hit", etc.).

    Returns:
        Float percentage sum (e.g., 15.0 means +15% multiplier).

    Example (per task spec):
        bonuses = {"dodge_mul": 5}  # boots +5% Множ. уклона (legacy key)
        collect_rating_pct(bonuses, "dodge") → 5.0
        # Then in recalc: Base_Flat=22, Pct_Sum=5.0
        # Final_Rating = floor(22 * 1.05) = floor(23.1) = 23
        # Real_Pct = 23 * 0.0625 = 1.4375 ≈ 1.44% (was 1.38% without bonus)
    """
    pct = float(bonuses.get(f"{stat_key}_pct", 0))
    # Stage 106 — legacy % keys are ALSO multipliers (NOT flat).
    # This fixes the critical bug where dodge_mul: 5 was converted to
    # +80 flat rating (= +5% direct to final chance) instead of being
    # a +5% multiplier on the base.
    legacy_aliases = {
        "dodge":  "dodge_mul",     # old +% dodge multiplier
        "hit":    "hit_chance",    # old +% hit chance
        "crit":   "crit_chance",   # old +% crit chance
        "block":  "parry_chance",  # old +% parry chance
        "pierce": "pierce",        # old +% pierce
        # tough has no legacy alias.
    }
    legacy_key = legacy_aliases.get(stat_key)
    if legacy_key:
        pct += float(bonuses.get(legacy_key, 0))
    return pct


# Hit chance hard caps.
BASE_HIT_CHANCE: int = 100   # baseline — everyone hits by default
HIT_FLOOR_PCT: int = 5       # hard floor — defender can never fully evade
HIT_CAP_PCT: int = 100       # hard cap — no overflow

# STR threshold for Hit Rating — STR below this gives 0 hit (unless gear bonus).
STR_THRESHOLD_FOR_HIT: int = 150

# Default BMV-price values for fighters without an outfit (mobs, world boss).
DEFAULT_BMV_PRICE_STR: int = 20
DEFAULT_BMV_PRICE_AGI: int = 20
DEFAULT_BMV_PRICE_STA: int = 20

# Default BMV-Прирост (level-up growth) for fighters without an outfit (mobs).
# Mobs use PlayerState-defined LEVEL_UP_* (kept for backward compat with saves).
# These are fallback values for Fighters built directly from Role (no PlayerState).
DEFAULT_GROWTH_STR: float = 0.3
DEFAULT_GROWTH_AGI: float = 0.4
DEFAULT_GROWTH_STA: float = 0.25
DEFAULT_GROWTH_STR_MAX: float = 0.5
DEFAULT_GROWTH_AGI_MAX: float = 0.6
DEFAULT_GROWTH_STA_MAX: float = 0.4

# Base speed (action_points multiplier baseline). speed = 1.0 + bonuses.
SPEED_BASE_FLOAT: float = 1.0

# === PRIMARY STAT CONVERSIONS (live formulas) =============================
STR_TO_ATK: float = 5.0        # attack per 1 STR (base linear scaling)
STA_TO_HP: float = 20.0        # max_hp per 1 STA (base linear scaling)
STA_TO_DEF: float = 2.0        # defense per 1 STA (base linear scaling)


def rating_to_percent(rating: int) -> float:
    """Stage 103 — convert flat rating to Real Percentage.

    1 rating unit = 0.0625% (1/16 step).
    NO CAP — player can stack >150% dodge/hit if gear allows.

    Examples:
        0  → 0.0%
        16 → 1.0%
        22 → 1.375% ≈ 1.38%
        100 → 6.25%
        1920 → 120.0% (overcap is allowed)
    """
    return rating * RATING_PCT_STEP


def combat_hit_chance(attacker_hit_rating: int, defender_dodge_rating: int) -> int:
    """Stage 103 — Final hit chance per original Pockie Ninja formula.

    Formula:
        Final_Hit% = 100 - (Defender_Dodge% - Attacker_Hit%)
                  = 100 - Defender_Dodge% + Attacker_Hit%

    Where each rating unit = 0.0625% (1/16 step). Ratings are flat integers
    with NO CAP, so percentages CAN exceed 100% (overcap is allowed).

    Hard caps (per task spec — anti-immortality protection):
        HIT_FLOOR_PCT = 5% (defender can NEVER fully evade — always 5% leak)
        HIT_CAP_PCT   = 100% (no overflow above guaranteed hit)

    Examples (per task spec):
        Attacker Hit=0, Defender Dodge=0
            → 100 - 0 + 0 = 100% (always hits, baseline)
        Attacker Hit=0, Defender Dodge=1920 (=120%)
            → 100 - 120 + 0 = -20% → floored to 5% (defender 95% evades)
        Attacker Hit=800 (=50%), Defender Dodge=1920 (=120%)
            → 100 - 120 + 50 = 30% (overcap hit pierced some dodge)
        Attacker Hit=480 (=30%), Defender Dodge=160 (=10%)
            → 100 - 10 + 30 = 120% → capped to 100%
    """
    hit_pct = attacker_hit_rating * RATING_PCT_STEP
    dodge_pct = defender_dodge_rating * RATING_PCT_STEP
    final = BASE_HIT_CHANCE - (dodge_pct - hit_pct)
    return max(HIT_FLOOR_PCT, min(HIT_CAP_PCT, int(final)))


def calc_dodge_rating(
    agility: int,
    bmv_price_agi: int,
    flat_gear_dodge: int = 0,
) -> int:
    """Stage 103 — Dodge Rating per original Pockie Ninja formula.

        Dodge_Rating = floor(AGI / bmv_price_agi) + flat_gear_dodge

    Floor division (truncates fractional parts). NO CAP on result.

    Args:
        agility: total AGI (base + outfit + gems).
        bmv_price_agi: costume's BMV-Цена for AGI (lower = each AGI more effective).
            For mobs/no-outfit, DEFAULT_BMV_PRICE_AGI (20) is used.
        flat_gear_dodge: flat dodge rating bonuses from gear/gems (Topaz etc.).

    Example (per task spec):
        AGI=249, bmv_price_agi=11, flat=0 → floor(249/11) + 0 = 22
    """
    if bmv_price_agi <= 0:
        bmv_price_agi = DEFAULT_BMV_PRICE_AGI
    return (agility // bmv_price_agi) + flat_gear_dodge


def calc_hit_rating(
    strength: int,
    bmv_price_str: int,
    flat_gear_hit: int = 0,
    str_threshold: int = STR_THRESHOLD_FOR_HIT,
) -> int:
    """Stage 103 — Hit Rating per original Pockie Ninja formula.

        Hit_Rating = floor(STR / bmv_price_str) + flat_gear_hit - STR_THRESHOLD

    Where STR_THRESHOLD is a minimum STR requirement (typically 150-200).
    If STR < threshold AND flat_gear_hit == 0 → Hit_Rating = 0.

    Floor division (truncates fractional parts). NO CAP on result.
    Minimum 0 (Hit_Rating cannot be negative).

    Args:
        strength: total STR (base + outfit + gems).
        bmv_price_str: costume's BMV-Цена for STR (lower = each STR more effective).
            For mobs/no-outfit, DEFAULT_BMV_PRICE_STR (20) is used.
        flat_gear_hit: flat hit rating bonuses from gear/gems (Amethyst etc.).
        str_threshold: minimum STR to get any hit rating from STR alone.

    Examples:
        STR=140, bmv_price_str=20, flat=0  → floor(140/20) + 0 - 150 = 7 - 150 = -143 → 0
        STR=300, bmv_price_str=20, flat=0  → 15 + 0 - 150 = -135 → 0 (still below gear!)
        STR=4000, bmv_price_str=20, flat=0 → 200 + 0 - 150 = 50 → 50 hit_rating
        STR=140, bmv_price_str=20, flat=80 → 7 + 80 - 150 = -63 → 0
        STR=300, bmv_price_str=20, flat=200 → 15 + 200 - 150 = 65 → 65 hit_rating
    """
    if bmv_price_str <= 0:
        bmv_price_str = DEFAULT_BMV_PRICE_STR
    raw = (strength // bmv_price_str) + flat_gear_hit - str_threshold
    return max(0, raw)


def calc_speed(agility: int, bmv_price_agi: int, gear_speed: int = 0) -> float:
    """Stage 103 — Speed multiplier (BMV-Цена for AGI, linear, no cap).

        speed = 1.0 + (AGI / bmv_price_agi + gear_speed) / 100

    Each bmv_price_agi points of AGI = +1% speed. NO CAP.

    Example (bmv_price_agi=10, AGI=300, gear_speed=0):
        speed = 1.0 + 30/100 = 1.30 (×1.30 action_points rate)

    Returns float multiplier (1.0 = baseline, 1.30 = +30% etc).
    """
    if bmv_price_agi <= 0:
        bmv_price_agi = DEFAULT_BMV_PRICE_AGI
    bonus_pct = (agility / bmv_price_agi) + gear_speed
    return SPEED_BASE_FLOAT + bonus_pct / 100.0


def calc_tough_rating(
    strength: int, stamina: int,
    bmv_price_str: int, bmv_price_sta: int,
    flat_gear_tough: int = 0,
) -> int:
    """Stage 103 — Tough Rating = floor(STR/bmv_str) + floor(STA/bmv_sta) + gear.

    Flat integer, NO CAP. Reduces attacker's crit CHANCE and crit DAMAGE
    (see apply_crit_stage: chance/16 вычитание, урон 150 + crit*0.125 − tough*0.125).
    """
    if bmv_price_str <= 0:
        bmv_price_str = DEFAULT_BMV_PRICE_STR
    if bmv_price_sta <= 0:
        bmv_price_sta = DEFAULT_BMV_PRICE_STA
    return (strength // bmv_price_str) + (stamina // bmv_price_sta) + flat_gear_tough


# === Stage 104 — BLOCK & PIERCE RATINGS + DAMAGE PIPELINE ===================

def calc_block_rating(
    strength: int,
    bmv_price_str: int,
    flat_gear_block: int = 0,
) -> int:
    """Stage 104 — Block Rating per original Pockie Ninja formula.

        Block_Rating = floor(STR / bmv_price_str) + flat_gear_block

    Block partially depends on STR (via BMV-Цена for STR, same as Hit).
    NO STR_THRESHOLD (unlike Hit) — block can be > 0 at any STR.
    Floor division (truncates fractional parts). NO CAP.

    Args:
        strength: total STR (base + outfit + gems).
        bmv_price_str: costume's BMV-Цена for STR.
        flat_gear_block: flat block rating from gear/gems.

    Example:
        STR=300, bmv_price_str=30, flat=0 → floor(300/30) + 0 = 10
        Real_Block_Chance% = 10 * 0.0625 = 0.625%
    """
    if bmv_price_str <= 0:
        bmv_price_str = DEFAULT_BMV_PRICE_STR
    return (strength // bmv_price_str) + flat_gear_block


def calc_pierce_rating(flat_gear_pierce: int = 0) -> int:
    """Stage 104 — Pierce Rating = flat_gear_pierce (gear/gems only, no STR).

    Pierce is independent of primary stats — formed exclusively from
    flat bonuses of equipment and stones. NO CAP.

    Example:
        flat_gear_pierce=36 → 36 pierce_rating → 36 * 0.072 = 2.592% ≈ 2.59%
    """
    return max(0, flat_gear_pierce)


# === Stage 104 — Rating → Percent conversion functions (3 steps) ===========

def rating_to_crit_chance(rating: int) -> float:
    """Stage 104 — Real Crit Chance % = Crit_Rating * ШАГ_А (0.0625).

    NO CAP — can exceed 100% (overcap allowed).
    """
    return rating * CRIT_CHANCE_STEP


def rating_to_crit_damage(rating: int) -> float:
    """Stage 104 — Real Crit Damage % = Crit_Rating * ШАГ_Б (0.125).

    This is the BONUS added to base 150% crit damage.
    NO CAP.
    """
    return rating * CRIT_DAMAGE_STEP


def rating_to_tough_chance_reduction(rating: int) -> float:
    """Stage 104 — Toughness reduces attacker's Crit Chance %.

    Срез_Шанса_Крита_Врага = Tough_Rating * ШАГ_А (0.0625).
    NO CAP.
    """
    return rating * CRIT_CHANCE_STEP


def rating_to_tough_damage_reduction(rating: int) -> float:
    """Stage 104 — Toughness reduces attacker's Crit Damage %.

    Срез_Урона_Крита_Врага = Tough_Rating * ШАГ_Б (0.125).
    NO CAP.
    """
    return rating * CRIT_DAMAGE_STEP


def rating_to_block_chance(rating: int) -> float:
    """Stage 104 — Real Block Chance % = Block_Rating * ШАГ_А (0.0625).

    NO CAP — can exceed 100% (overcap allowed).
    """
    return rating * CRIT_CHANCE_STEP


def rating_to_antiblock_pct(rating: int) -> float:
    """Stage 137 — ОРИГИНАЛ (вики): Антиблок = rating/16 % (тот же /16).

    Пара Блок/Антиблок: block% − antiblock% = финальный шанс блока.
    НЕТ КАПА (overcap разрешён — вычитание может уйти в минус = блок
    полностью снят).
    """
    return rating * RATING_PCT_STEP


# === Stage 137 — DAMAGE PIPELINE (оригинал, вики) ============================
#
# After Hit/Dodge check passes, sequential stages to BaseDamage:
#
#   Stage 1 — CRIT (Attacker Crit vs Defender Const):
#     Final_Crit_Chance% = crit/16% − tough/16%   [оба /16, вычитание]
#     Damage_After_Crit = BaseDamage * (150 + crit*0.125 − tough*0.125) / 100
#
#   Stage 2 — ЗАЩИТА (Defender Defence vs Attacker Defence Break):
#     Final_Mitigation% = def/(def+1354)% − break/(break+1354)%  [гиперболы]
#     Damage_After_Defense = Damage_After_Crit * (1 − Final_Mitigation)
#
#   Stage 3 — BLOCK (Defender Block vs Attacker Антиблок):
#     Final_Block_Chance% = block/16% − antiblock/16%             [оба /16]
#     Damage_After_Block = Damage_After_Defense * 0.60  (-40%)
#
# КАПОВ НЕТ: любой рейтинг может быть 5000/10000+; overcap разрешён везде,
# кроме итоговых вероятностей (roll 1..100).


def apply_crit_stage(
    base_damage: int,
    attacker_crit_rating: int,
    defender_tough_rating: int,
    roll: int | None = None,
) -> tuple[int, bool]:
    """Stage 104 — Stage 1: Crit calculation (Attacker Crit vs Defender Toughness).

    Returns (damage_after_crit, is_crit_bool).

    Args:
        base_damage: the base damage roll (rand_int(min_atk, max_atk)).
        attacker_crit_rating: attacker's flat crit rating (gear + gems, no STR).
        defender_tough_rating: defender's flat tough rating (STR//bmv + STA//bmv + gear).
        roll: pre-generated random 1..100 (for testing). If None, generates internally.
    """
    if roll is None:
        import random as _random
        roll = _random.randint(1, 100)

    # Final crit chance = attacker crit chance% - defender tough chance reduction%
    crit_chance = rating_to_crit_chance(attacker_crit_rating) - \
                  rating_to_tough_chance_reduction(defender_tough_rating)
    if crit_chance <= 0:
        return base_damage, False

    # Compare roll (int 1..100) with chance (float). E.g., chance=6.25%,
    # roll=3 → 3 <= 6.25 → crit. roll=7 → 7 > 6.25 → no crit.
    if roll > crit_chance:
        return base_damage, False

    # Crit triggered — compute crit damage multiplier
    # Damage = BaseDamage * (150 + attacker_crit_dmg% - defender_tough_dmg_reduction%) / 100
    crit_dmg_pct = rating_to_crit_damage(attacker_crit_rating) - \
                   rating_to_tough_damage_reduction(defender_tough_rating)
    total_crit_pct = CRIT_BASE_DAMAGE_PCT + crit_dmg_pct
    if total_crit_pct <= 0:
        # Defender tough fully negates crit damage bonus — crit does base damage
        return base_damage, True
    damage_after_crit = int(base_damage * total_crit_pct / 100)
    return damage_after_crit, True


def apply_block_stage(
    damage_after_defense: int,
    defender_block_rating: int,
    attacker_antiblock_rating: int,
    roll: int | None = None,
) -> tuple[int, bool]:
    """Stage 137 — ОРИГИНАЛ: Блок (Defender) vs Антиблок (Attacker), оба /16.

    Final_Block_Chance% = block%/16 − antiblock%/16 (простое вычитание,
    отрицательный результат = блок полностью снят). Overcap разрешён.
    Successful block reduces damage by 40% (multiplier 0.60).

    Returns (damage_after_block, is_block_bool).
    """
    if roll is None:
        import random as _random
        roll = _random.randint(1, 100)

    block_chance = rating_to_block_chance(defender_block_rating) - \
                    rating_to_antiblock_pct(attacker_antiblock_rating)
    if block_chance <= 0:
        return damage_after_defense, False

    if roll > block_chance:
        return damage_after_defense, False

    damage_after_block = int(damage_after_defense * BLOCK_DAMAGE_MULTIPLIER)
    return damage_after_block, True


# Stage 137 — pipeline order: Crit → ЗАЩИТА (def − break) → Block (block − antiblock).
def apply_defense_stage(
    damage_after_crit: int,
    defender_defense: int,
    attacker_defense_break: int = 0,
) -> int:
    """Stage 137 — ОРИГИНАЛ: защита минус пробивание (вычитание процентов).

    Оба стата — гиперболы с K=1354 (верифицировано тултипами 75 лвл):
        mitigation_def%   = def / (def + 1354)        [def=1604 → 54.23%]
        defbreak%         = break / (break + 1354)    [break=2072 → 60.48%]
    Final_Mitigation% = mitigation_def% − defbreak%  (может быть ≤ 0 →
    пробивание перевешивает защиту, урон НЕ усиливается выше базы).

    Проверка на данных оригинала: def=1604 vs break=2072:
        54.23% − 60.48% = −6.25% → урон проходит почти полностью.
    """
    mitigation = defender_defense / (defender_defense + DEFENSE_BREAK_CONSTANT)
    if attacker_defense_break > 0:
        mitigation -= attacker_defense_break / (attacker_defense_break + DEFENSE_BREAK_CONSTANT)
    if mitigation <= 0:
        return damage_after_crit
    return int(damage_after_crit * (1 - mitigation))


# === Stage 103 — ATK multiplier helper (live, Stage 107 scheme) =============

def calc_atk_mul_pct(strength: int, bmv_str: int) -> int:
    """Stage 107 — Скрытый_Процент_Силы = floor(STR / bmv_str).

    Returns integer percent (e.g., 0 for STR=20, bmv=30 → floor(20/30)=0).
    This is the hidden STR-driven attack multiplier from original Pockie Ninja.

    Combined with gear_atk_mul (e.g., +5% from weapon) into atk_mul_pct,
    then applied as a multiplier to Total_Flat_Min/Max in recalc_stats.

    Args:
        strength: total STR (base + outfit + gems).
        bmv_str: costume's BMV-Цена for STR (suit_ichigo=30).

    Returns:
        Integer percent (>= 0). E.g., STR=20, bmv=30 → 0. STR=60, bmv=30 → 2.

    Example:
        calc_atk_mul_pct(20, 30) → floor(20/30) = 0  (hidden STR% = 0)
        calc_atk_mul_pct(60, 30) → floor(60/30) = 2  (hidden STR% = 2%)
        calc_atk_mul_pct(300, 30) → floor(300/30) = 10  (hidden STR% = 10%)
    """
    if bmv_str <= 0:
        bmv_str = DEFAULT_BMV_PRICE_STR
    return strength // bmv_str


def calc_crit_rating(strength: float, gear_crit: int = 0) -> int:
    """Stage 103 — Crit rating = gear_crit (no STR contribution, flat, no cap).

    STR no longer gives crit rating. Main source is gear/gems/enchants.
    Kept for backward-compat — just returns gear_crit (STR parameter ignored).
    """
    return int(gear_crit)
