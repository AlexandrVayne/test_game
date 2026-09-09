"""Data models for Pockie RPG.

Layer A (UI-agnostic). Imports ONLY stdlib (per §4.3).
All records are frozen + slots dataclasses (per §9.3) — immutable, memory-efficient.

Stage 4: Role expanded with full character sheet stats (defense, parry, tough,
neglect_def, etc.) per §5.8 INFERRED derivations for the character sheet window.
"""
from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# ROLE (character class definition — full stat sheet)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Role:
    """A character class definition (e.g., Ichigo role_id=1).

    Mirrors a subset of `roles_init.json` fields used at runtime.
    Primary stats хранятся в НАТУРАЛЬНЫХ единицах (конверсия ×100 сделана в
    roles_db при загрузке).

    Производные статы — свойства ниже, ЕДИНЫЕ для всех бойцов:
      - min_atk  = 10 + strength * 5
      - max_atk  = int(min_atk * 1.5)
      - defense  = stamina * 1

    Stage 11 NEW: `skills` field — a tuple of skill_ids this role can use
    (skill deck). The FightSystem iterates this tuple on each of the
    fighter's turns, trying each skill in order (first trigger wins).
    Empty tuple = basic attack only. This is the data-driven replacement
    for the hardcoded `try_crystal_blade` logic in Stage 10.

    Cleanup: legacy direct-% поля (dodge_chance, hit_chance, crit_mul,
    crit_attach, parry_chance, pierce, crit_chance) и производные свойства
    (parry_mul, tough, neglect_def, rebound, vampiric_*, dec_damage,
    effective_tough) удалены — боевая математика Stage 103/137 считает
    рейтинги из strength/agility/stamina.
    """

    # Identity
    role_id: int
    name: str

    # Primary attributes (natural units) — THESE drive all derived stats
    strength: int
    agility: int
    stamina: int

    # Resources (base values, scaled by level in Fighter.from_role)
    max_hp: int
    max_mp: int

    # Turn frequency — now derived: max(400, 1500 - agility * 5)
    atk_time: int

    skills: tuple[int, ...] = ()

    # ---------- Derived properties (computed from primary stats) ----------

    @property
    def min_atk(self) -> int:
        """10 + strength * 5 (unified formula for all fighters)."""
        return 10 + self.strength * 5

    @property
    def max_atk(self) -> int:
        """min_atk * 1.5 (unified formula for all fighters)."""
        return int(self.min_atk * 1.5)

    @property
    def defense(self) -> int:
        """stamina * 1"""
        return self.stamina


@dataclass(frozen=True, slots=True)
class EnemyDef:
    """Enemy definition (unified with EnemyTemplate).

    Stage 130 — unified: EnemyDef is now the single enemy dataclass.
    enemy_db.py imports this directly instead of defining its own.
    roles_db.py builds ENEMY_MOBS from ENEMY_DB without field-by-field copy.
    """

    enemy_id: str = ""
    mob_id: str = ""
    name: str = ""
    level: int = 1
    role_id: int = 0
    hp_mul: float = 1.0
    atk_mul: float = 1.0
    xp_reward: int = 0
    gold_reward: int = 0
    is_stub: bool = False
    skills: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class Suit:
    """A starter suit definition (cosmetic + skill link).

    `motion_folder` is the directory under `assets/extracted/` containing
    idle/attack/hit/death frames for this suit (per §10.9).
    """

    suit_id: str            # e.g., "i290001"
    name: str               # display name, e.g., "Ичиго"
    role_id: int
    motion_folder: str      # e.g., "ichigo/idle" (under assets/extracted/)
    avatar_filename: str    # e.g., "userface_0_1_role.gif"
    # Stage 206 — спрайт в полный рост для инвентаря (assets/icons/character/).
    # Дефолт — классическая поза Ичиго; cloth14 переопределяет.
    pose_filename: str = "people_002_pose.png"


@dataclass(frozen=True, slots=True)
class CharacterStats:
    """Stage 103 — Pockie Ninja original combat math result.

    Combines a player's base primary attributes (STR/AGI/STA) with bonuses
    from equipped gear (EQUIPMENT_DB) + gems + outfit base_stats. Then derives
    all secondary combat stats via the Stage 103 formulas (per task spec):

    1. PRIMARY STATS (base 10/10/10 + outfit base_stats + gear + gems):
        total_strength = base_strength + outfit_base + gear_str + gem_str
        total_agility  = base_agility  + outfit_base + gear_agi + gem_agi
        total_stamina  = base_stamina  + outfit_base + gear_sta + gem_sta

    2. RATINGS (flat integers, NO CAP):
        Dodge_Rating = floor(AGI / bmv_price_agi) + flat_gear_dodge
        Hit_Rating   = floor(STR / bmv_price_str) + flat_gear_hit - STR_THRESHOLD
                       (min 0; STR_THRESHOLD=150)
        Tough_Rating = floor(STR/bmv_str) + floor(STA/bmv_sta) + flat_gear_tough
        Crit_Rating  = gear_crit_rating + gem_crit_rating (no STR contribution)

    3. PERCENT (1 rating = 0.0625% = 1/16 step, NO CAP):
        Real_Pct_Dodge = Dodge_Rating * 0.0625
        Real_Pct_Hit   = Hit_Rating   * 0.0625

    4. COMBAT HIT CHANCE (in damage.py::get_hit):
        Final_Hit% = 100 - (Defender_Dodge% - Attacker_Hit%)
        Hard caps: [5%, 100%]

    5. SPEED (linear, no cap):
        speed = 1.0 + (AGI / bmv_price_agi + gear_speed) / 100

    6. BASE FORMULAS (linear):
        min_atk = 10 + STR*5 + gear_min + gem_min
        max_atk = min_atk * 1.5 + gear_max
        max_hp  = 100 + STA*20 + gear_hp + gem_hp
        defense = 5 + STA*2 + gear_def + gem_def
        max_mp  = base_max_mp + gear_mp

    BMV-Прирост (level-up growth) is stored per-stat for UI display:
        "Ловкость 41 (+1.35) | Макс (+1.65)"
    """

    total_strength: int
    total_agility: int
    total_stamina: int
    max_hp: int
    max_mp: int
    defense: int
    min_atk: int
    max_atk: int
    atk_time: int
    hit_rating_ui: int = 0   # Stage 103 — raw hit rating for UI (floor(STR/bmv) - threshold)
    dodge_rating_ui: int = 0 # Stage 103 — raw dodge rating for UI (floor(AGI/bmv))
    speed: float = 1.0       # Stage 103 — speed multiplier (1.0 = baseline)
    # Stage 52/103 — RATINGS (flat integers, NO CAP).
    crit_rating: int = 0         # crit rating (gear_crit + gem_crit, no STR contribution)
    tough_rating: int = 0        # tough rating (STR//bmv_str + STA//bmv_sta + gear + gem)
    # Stage 104 — BLOCK & PIERCE RATINGS (flat integers, NO CAP).
    block_rating_ui: int = 0     # block rating (floor(STR/bmv_str) + gear_block)
    pierce_rating_ui: int = 0    # pierce rating (gear_pierce + gem_pierce, no STR contribution)
    # Stage 137 — АНТИБЛОК rating (flat, /16% — снимает чужой блок; НЕТ КАПА).
    antiblock_rating_ui: int = 0
    # Stage 103 — BMV-Цена (costume-driven, lower = each stat more effective).
    bmv_price_str: int = 20    # STR cost (suit_ichigo=30)
    bmv_price_agi: int = 20    # AGI cost (suit_ichigo=10)
    bmv_price_sta: int = 20    # STA cost (suit_ichigo=20)
    # Stage 103 — BMV-Прирост (level-up growth per stat, current/max for UI).
    growth_str: float = 0.3       # current STR growth per level
    growth_agi: float = 0.4       # current AGI growth per level
    growth_sta: float = 0.25      # current STA growth per level
    growth_str_max: float = 0.5   # max STR growth (UI display)
    growth_agi_max: float = 0.6   # max AGI growth (UI display)
    growth_sta_max: float = 0.4   # max STA growth (UI display)
    # Stage 169 (аудит 4.4) — legacy-алиасы bmv_str/bmv_agi/bmv_sta и
    # atk_mul_pct/max_hp_mul_pct/def_mul_pct УДАЛЕНЫ (0 чтений; единственный
    # писатель — recalc_stats). BMV-цены — только bmv_price_*.
