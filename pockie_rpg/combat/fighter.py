"""Combat Fighter — mutable runtime mirror of Role (Layer B).

Per §4.3: imports `config.SkillType`, `data.loader`, `data.models`;
TYPE_CHECKING: `combat.buffs.ActiveBuff`.
Per §9.3: mutable (NOT frozen) — HP/MP/atk_time change during battle.

Stage 4 simplified: basic attack only (no skills/buffs yet).

Stage 10: added `can_move` + `frozen_duration` fields + `tick_stun()` method
to support the Crystal Blade skill's freeze effect. When a fighter is frozen
by Crystal Blade, `can_move` is set to 0 and `frozen_duration` is set to 1.
On their next turn, they skip (no attack) and `tick_stun()` decrements
`frozen_duration` — when it reaches 0, `can_move` is reset to 1 (ice melts).

Stage 11 REFACTOR (data-driven combat): replaced the hardcoded `can_move` /
`frozen_duration` fields with a `status: StatusManager` field (composition).
This lets ANY status (frozen, poison, stun, burn, shield, paralyze, etc.) be
applied to any fighter WITHOUT changing the Fighter class — just call
`fighter.status.apply(name, duration, params)`. The FightSystem turn loop
calls `status.on_turn_start(fighter)` / `status.on_turn_end()` generically.

Also added `skills: tuple[int, ...]` — the fighter's skill deck (list of
skill_ids). The FightSystem iterates this tuple on each of the fighter's
turns, looking up each skill in combat.skill_registry.SKILL_REGISTRY and
applying its on_hit_effects generically via StatusManager. No more hardcoded
`if skill_id == 12006` checks.

Backward compat: `can_move` and `frozen_duration` are kept as read/write
properties that proxy to the StatusManager (so existing UI code that does
`fighter.can_move = 0` / `fighter.frozen_duration = 2` / `fighter.tick_stun()`
still works). `tick_stun()` is kept as a method that calls `status.on_turn_end()`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from pockie_rpg.combat.status_manager import StatusManager
from pockie_rpg.config import CRYSTAL_BLADE_FREEZE_DURATION
from pockie_rpg.data.models import Role


@dataclass(slots=True)
class Fighter:
    """Mutable combatant. Mirrors a Role with runtime HP/MP state.

    Stage 11 — freeze state is now managed by `status: StatusManager`
    (composition). The legacy `can_move` / `frozen_duration` fields are
    kept as backward-compat properties that proxy to the StatusManager.
    The `skills` tuple is the fighter's skill deck (looked up in
    combat.skill_registry.SKILL_REGISTRY by the FightSystem).
    """

    # Identity
    name: str
    role_id: int
    is_player: bool          # True = player (left), False = enemy (right)
    level: int = 1

    # Resources (mutable)
    hp: int = 0
    mp: int = 0
    max_hp: int = 0
    max_mp: int = 0

    # Combat stats (mutable — buffs can modify, but Stage 4 has no buffs)
    min_atk: int = 0
    max_atk: int = 0
    defense: int = 0
    dodge_chance: int = 0    # Stage 49 — % to dodge (from rating)
    hit_chance: int = 90    # Stage 49 — % to hit (from rating)
    # Stage 52 — CRIT RATING & TOUGH RATING (flat, no cap).
    crit_rating: int = 0     # crit rating (gear + gems, no STR contribution in Stage 103/104)
    tough_rating: int = 0    # tough rating (STR//bmv_str + STA//bmv_sta + gear + gems)
    # Stage 104 — BLOCK & PIERCE RATINGS (flat, no cap).
    block_rating: int = 0    # block rating (floor(STR/bmv_str) + gear_block)
    pierce_rating: int = 0   # pierce rating (gear_pierce + gem_pierce, no STR)
    antiblock_rating: int = 0  # Stage 137 — антиблок (снимает чужой блок, /16%, no cap)

    # Stage 49 — SPEED SYSTEM (action points): replaces atk_time/next_atk_time.
    # speed: 1.0-10.0 (higher = faster, more attacks per time unit)
    # action_points: accumulated each tick by speed; when >= 1.0, fighter can act.
    speed: float = 1.0
    action_points: float = 0.0
    # Stage 91 — starting_action_points: pre-battle head start.
    # FightSystem.fight() initializes action_points from this field (not 0.0),
    # so a fighter with starting_action_points=0.5 gets a half-turn head start.
    # Used by Tower boss_fast_start modifier. Default 0.0 (no head start).
    starting_action_points: float = 0.0

    # Turn system (per §5.4) — kept for backward compat (UI/replay code).
    atk_time: int = 1000     # ms — turn frequency
    next_atk_time: int = 0   # countdown counter

    # State flags
    is_alive: bool = True

    # Stage 11 — StatusManager (replaces hardcoded can_move/frozen_duration).
    # Manages all status effects dynamically: frozen, poison, stun, burn, etc.
    # The FightSystem calls status.on_turn_start(fighter) at the start of
    # each turn (applies DoT, checks skip-turn) and status.on_turn_end() at
    # the end (decrements durations, removes expired).
    status: StatusManager = field(default_factory=StatusManager)

    # Stage 11 — skill deck: tuple of skill_ids this fighter can use.
    # The FightSystem iterates this tuple on each of the fighter's turns,
    # looking up each skill in combat.skill_registry.SKILL_REGISTRY. The
    # first skill whose MP cost is met + trigger chance passes is executed
    # (damage + on_hit_effects applied generically via StatusManager).
    # Default empty tuple = basic attack only (no skills).
    skills: tuple[int, ...] = ()

    # Stage 13 — transient field updated by take_damage each call: the
    # amount of damage absorbed by an active "shield" status on the most
    # recent call. Used by execute_skill/compute_attack to populate
    # FightValue.shield_absorbed for UI feedback ("blocked X"). Reset to
    # 0 at the start of each take_damage call.
    shield_absorbed_last: int = 0

    # ---------- Factory ----------

    @classmethod
    def from_role(
        cls,
        role: Role,
        is_player: bool,
        level: int = 1,
        hp_mul: float = 1.0,
        atk_mul: float = 1.0,
        skills: tuple[int, ...] | None = None,
    ) -> "Fighter":
        """Build a Fighter from a Role definition.

        Args:
            role: source Role with stats.
            is_player: True for player (left side), False for enemy (right).
            level: character level.
            hp_mul: multiplier on max_hp (for enemies).
            atk_mul: multiplier on min/max_atk (for enemies).
            skills: skill deck — tuple of skill_ids this fighter can use.
                If None, defaults to role.skills (Stage 11 — the Role's
                skill deck is the source of truth for which skills a
                fighter of that role can use).

        Stage 14 — for the PLAYER, callers pass `tuple(player.active_skills)`
        here so the fighter's skill deck reflects the user's pre-battle
        toggles (disabled skills are NOT tried by the FightSystem). Enemies
        don't have an `active_skills` filter — they always use role.skills.
        """
        max_hp = int(role.max_hp * hp_mul)
        max_mp = role.max_mp
        min_atk = int(role.min_atk * atk_mul)
        max_atk = int(role.max_atk * atk_mul)
        # Stage 11 — default the skill deck to the Role's skills tuple.
        if skills is None:
            skills = role.skills
        # Stage 103 — BMV-Цена-driven ratings (DEFAULT_BMV_PRICE=20/20/20 for mobs).
        # hit_chance/dodge_chance fields STORE RATINGS (int, no cap). The
        # damage.py::get_hit() calls combat_hit_chance(hit_rating, dodge_rating)
        # which uses the linear formula (per task spec):
        #   Final_Hit% = 100 - (Defender_Dodge% - Attacker_Hit%)
        #             = 100 - dodge_rating*0.0625 + hit_rating*0.0625
        # Hard caps: [5%, 100%].
        from pockie_rpg.config import (
            DEFAULT_BMV_PRICE_AGI,
            DEFAULT_BMV_PRICE_STA,
            DEFAULT_BMV_PRICE_STR,
            calc_block_rating,
            calc_crit_rating,
            calc_dodge_rating,
            calc_hit_rating,
            calc_pierce_rating,
            calc_speed,
            calc_tough_rating,
        )
        _crit_rating = calc_crit_rating(role.strength, 0)  # gear_crit=0 for mobs
        _tough_rating = calc_tough_rating(
            role.strength, role.stamina,
            DEFAULT_BMV_PRICE_STR, DEFAULT_BMV_PRICE_STA, 0,
        )
        _speed = calc_speed(role.agility, DEFAULT_BMV_PRICE_AGI, 0)
        # Stage 103 — derive hit/dodge RATINGS via Pockie Ninja formulas.
        # Hit_Rating = floor(STR/bmv_str) - STR_THRESHOLD (min 0).
        # Dodge_Rating = floor(AGI/bmv_agi).
        _hit_rating = calc_hit_rating(role.strength, DEFAULT_BMV_PRICE_STR, 0)
        _dodge_rating = calc_dodge_rating(role.agility, DEFAULT_BMV_PRICE_AGI, 0)
        # Stage 104 — derive BLOCK & PIERCE RATINGS.
        # Block_Rating = floor(STR / bmv_str) + flat_gear (no threshold).
        # Pierce_Rating = flat_gear only (no STR). Mobs have 0 pierce (no gear).
        _block_rating = calc_block_rating(role.strength, DEFAULT_BMV_PRICE_STR, 0)
        _pierce_rating = calc_pierce_rating(0)
        return cls(
            name=role.name,
            role_id=role.role_id,
            is_player=is_player,
            level=level,
            hp=max_hp,
            mp=max_mp,
            max_hp=max_hp,
            max_mp=max_mp,
            min_atk=min_atk,
            max_atk=max_atk,
            defense=role.defense,
            dodge_chance=_dodge_rating,  # Stage 102 — now stores RATING (int)
            hit_chance=_hit_rating,     # Stage 102 — now stores RATING (int)
            atk_time=role.atk_time,
            next_atk_time=role.atk_time,  # first turn at full cycle
            is_alive=True,
            status=StatusManager(),  # Stage 11 — fresh, no effects.
            skills=skills,           # Stage 11 — skill deck from Role.
            crit_rating=_crit_rating,
            tough_rating=_tough_rating,
            speed=_speed,
            action_points=0.0,
            # Stage 104 — BLOCK & PIERCE RATINGS.
            block_rating=_block_rating,
            pierce_rating=_pierce_rating,
        )

    @classmethod
    def from_player_state(cls, player, role: Role) -> "Fighter":
        """Build a Fighter from a PlayerState with grown stats + equipment bonuses.

        Stage 22 — uses PlayerState.recalc_stats() as the canonical source of
        derived combat stats. The recalc applies Stage 22 EQUIPMENT_DB gear
        bonuses from `equipped_gear` (weapon/armor/boots/amulet) directly onto
        base primary attributes, then derives max_hp / defense / min_atk /
        max_atk / atk_time / max_mp via the clean formulas.
        """
        stats = player.recalc_stats()
        max_hp = stats.max_hp
        max_mp = stats.max_mp
        min_atk = stats.min_atk
        max_atk = stats.max_atk
        defense = stats.defense
        atk_time = stats.atk_time
        # Stage 102 — Fighter.hit_chance/dodge_chance now store RATINGS (not %).
        # Use stats.hit_rating_ui / dodge_rating_ui which are the raw ratings.
        # Fallback to combat_hit_chance(0, 0) baseline for old saves.
        dodge_rating = getattr(stats, 'dodge_rating_ui', 0)
        hit_rating = getattr(stats, 'hit_rating_ui', 0)
        # Stage 52 — crit/tough ratings from stats.
        crit_rating = stats.crit_rating
        tough_rating = stats.tough_rating
        # Stage 104 — BLOCK & PIERCE RATINGS from stats.
        block_rating = getattr(stats, 'block_rating_ui', 0)
        pierce_rating = getattr(stats, 'pierce_rating_ui', 0)
        # Stage 137 — АНТИБЛОК rating (снимает чужой блок, /16%).
        antiblock_rating = getattr(stats, 'antiblock_rating_ui', 0)
        # Stage 49/102 — speed from stats (action points system, BMV-driven).
        speed = stats.speed if hasattr(stats, 'speed') else 1.0
        # Stage 88 — Fix 2.6: always use player.active_skills as-is (even if
        # empty). An empty list means the user intentionally disabled all
        # skills (basic-attack-only build). Previously `if player.active_skills`
        # treated [] as falsy and fell back to role.skills, making it impossible
        # to disable all skills. The from_dict migration ensures [] only appears
        # when the user explicitly chose it (old saves without the key get the
        # full role set).
        skills = tuple(player.active_skills) if player.active_skills is not None else role.skills
        return cls(
            name=player.name,
            role_id=player.role_id,
            is_player=True,
            level=player.level,
            hp=max_hp,
            mp=max_mp,
            max_hp=max_hp,
            max_mp=max_mp,
            min_atk=min_atk,
            max_atk=max_atk,
            defense=defense,
            dodge_chance=dodge_rating,  # Stage 102 — RATING (not %)
            hit_chance=hit_rating,      # Stage 102 — RATING (not %)
            atk_time=atk_time,
            next_atk_time=atk_time,
            is_alive=True,
            status=StatusManager(),
            skills=skills,
            crit_rating=crit_rating,
            tough_rating=tough_rating,
            speed=speed,
            action_points=0.0,
            # Stage 104 — BLOCK & PIERCE RATINGS.
            block_rating=block_rating,
            pierce_rating=pierce_rating,
            antiblock_rating=antiblock_rating,  # Stage 137
        )

    # ---------- Combat helpers ----------

    def take_damage(self, dmg: int) -> int:
        """Apply damage to HP. Returns actual HP damage dealt (clamped to HP).

        Stage 13 — SHIELD ABSORPTION: if the fighter has an active "shield"
        status (e.g., from crystal_shield skill), the incoming damage is
        absorbed by the shield FIRST. The shield's "amount" param is reduced
        by the absorbed amount; if it reaches 0, the shield status is removed
        (shield broken). The remaining damage (if any) applies to HP as
        normal. The amount absorbed is stored in `shield_absorbed_last` so
        the damage pipeline can populate FightValue.shield_absorbed for UI
        feedback (e.g., a "blocked" damage number).

        Per spec: "Если у цели активен щит, входящий урон сначала поглощается
        щитом. Когда прочность щита падает до 0, статус снимается."
        """
        # Reset the transient shield-absorbed tracker.
        self.shield_absorbed_last = 0
        if not self.is_alive:
            return 0
        # Stage 13 — absorb from shield first.
        if dmg > 0 and self.status.has("shield"):
            shield_effect = self.status.get_effect("shield")
            if shield_effect is not None:
                shield_amount = int(shield_effect.params.get("amount", 0))
                if shield_amount > 0:
                    absorbed = min(dmg, shield_amount)
                    dmg -= absorbed
                    shield_amount -= absorbed
                    shield_effect.params["amount"] = shield_amount
                    self.shield_absorbed_last = absorbed
                    if shield_amount <= 0:
                        # Shield broken — remove the status.
                        self.status.remove("shield")
        # Apply remaining damage to HP.
        if dmg <= 0:
            return 0
        actual = min(dmg, self.hp)
        self.hp -= actual
        if self.hp <= 0:
            self.hp = 0
            self.is_alive = False
        return actual

    def take_log_damage(self, dmg: int, shield_absorbed: int = 0) -> None:
        """Stage 188 — применить урон ИЗ ЛОГА РЕПЛЕЯ без повторного щита.

        FightValue.damage уже ПОСЛЕ поглощения щитом в движке, а
        FightValue.shield_absorbed — сколько щит съел на этом ударе. Зеркало
        должно списать эту сумму со СВОЕГО щита (сняв статус при исчерпании,
        чтобы купол исчез вместе с движковым) и снизить HP НАПРЯМУЮ.
        Обычный take_damage здесь нельзя: его щит поглотил бы урон второй
        раз, и HP-бар стоял бы выше движка (нашёл diag-сценарий «щит»).
        """
        if not self.is_alive:
            return
        if shield_absorbed > 0 and self.status.has("shield"):
            shield_effect = self.status.get_effect("shield")
            if shield_effect is not None:
                amount = int(shield_effect.params.get("amount", 0)) - shield_absorbed
                if amount <= 0:
                    self.status.remove("shield")
                else:
                    shield_effect.params["amount"] = amount
        if dmg <= 0:
            return
        actual = min(dmg, self.hp)
        self.hp -= actual
        if self.hp <= 0:
            self.hp = 0
            self.is_alive = False

    # -----------------------------------------------------------------
    # Stage 11 — data-driven status accessors
    # -----------------------------------------------------------------

    @property
    def can_act(self) -> bool:
        """Stage 11 — True if the fighter can take a turn (not frozen/stunned).

        Replaces the implicit `can_move == 1` check in Stage 10.
        """
        return self.status.can_act()

    # -----------------------------------------------------------------
    # Stage 11 — backward-compat properties (proxy to StatusManager)
    # -----------------------------------------------------------------
    # These keep existing code working that reads/writes the Stage 10
    # `can_move` / `frozen_duration` fields directly. They proxy to the
    # StatusManager so the data is consistent with the new architecture.
    #
    # `can_move` (int: 1=movable, 0=frozen) ↔ status.can_act()
    # `frozen_duration` (int: turns remaining) ↔ status.get_duration("freeze")
    #
    # Writing `fighter.can_move = 0` applies a "freeze" status with the
    # current frozen_duration (default 2 if not yet set). Writing
    # `fighter.can_move = 1` removes the "freeze" status (ice melts).
    # Writing `fighter.frozen_duration = N` applies a "freeze" status with
    # duration N (or removes it if N == 0).

    @property
    def can_move(self) -> int:
        """Backward compat: 1 if the fighter can act, 0 if frozen/stunned.

        Stage 11 — proxies to status.can_act(). Kept as a property so
        existing UI code that reads `fighter.can_move` still works.
        """
        return 1 if self.status.can_act() else 0

    @can_move.setter
    def can_move(self, value: int) -> None:
        """Backward compat: set 0 to freeze, 1 to thaw.

        Stage 11 — proxies to status.apply("freeze", ...) / status.remove("freeze").
        If freezing (value == 0) and frozen_duration is currently 0, defaults
        to a 2-turn freeze (matches the Stage 10.1 Crystal Blade freeze duration).
        """
        if value == 0:
            # Apply frozen status. Use the current frozen_duration if set,
            # otherwise default to the Crystal Blade freeze duration
            # (Stage 170 — константа вместо магической двойки).
            duration = self.frozen_duration
            if duration <= 0:
                duration = CRYSTAL_BLADE_FREEZE_DURATION
            self.status.apply("freeze", duration)
        else:
            # Thaw: remove the frozen status.
            self.status.remove("freeze")

    @property
    def frozen_duration(self) -> int:
        """Backward compat: remaining frozen turns (0 if not frozen).

        Stage 11 — proxies to status.get_duration("freeze").
        """
        return self.status.get_duration("freeze")

    @frozen_duration.setter
    def frozen_duration(self, value: int) -> None:
        """Backward compat: set the frozen duration in turns.

        Stage 11 — forcefully sets the frozen duration via status.set_duration
        (overrides any existing freeze, even if shorter). Setting to 0 removes
        the frozen status (ice melts).
        """
        if value > 0:
            self.status.set_duration("freeze", value)
        else:
            self.status.remove("freeze")

    def tick_stun(self) -> None:
        """Backward compat: decrement all status durations (was frozen-only).

        Stage 11 — proxies to status.on_turn_end(). This decrements ALL
        active effects (frozen, poison, burn, etc.) by 1 turn, removing
        any that reach 0. In Stage 10 this only decremented frozen_duration;
        the new behavior is a superset (frozen is still decremented, but
        other effects are too — which is the intended data-driven behavior).

        No-op if the fighter has no active status effects.
        """
        self.status.on_turn_end()

    def __repr__(self) -> str:
        return f"Fighter({self.name}, hp={self.hp}/{self.max_hp}, alive={self.is_alive}, status={self.status})"
