"""Enemy Database — centralized enemy templates (Layer A, data-driven).

Per Stage 11 refactor: ALL enemy definitions in ONE place. Each enemy
references a Role (stat source) + a Skill Deck (list of skill_ids).

To add a new enemy: just add a new entry to ENEMY_DB. The engine
auto-loads it. No code changes needed.

Per §4.3: imports ONLY stdlib (no config/ui imports).
"""
from __future__ import annotations

from pockie_rpg.data.models import EnemyDef as EnemyTemplate
from pockie_rpg.data.models import EnemyExactStats

# ---------------------------------------------------------------------------
# THE ENEMY DATABASE — ALL enemies in ONE place.
# Add new enemies here. MAP screen auto-discovers them.
# ---------------------------------------------------------------------------

ENEMY_DB: dict[str, EnemyTemplate] = {
    "samurai_1": EnemyTemplate(
        enemy_id="samurai_1",
        name="Самурай",
        level=1,
        role_id=10001,            # ROLE_SAMURAI
        hp_mul=1.0,
        atk_mul=1.0,
        xp_reward=50,
        gold_reward=25,
        is_stub=False,
        skills=(),                # basic attack only (no skills yet)
    ),
    "samurai_2": EnemyTemplate(
        enemy_id="samurai_2",
        name="Синий мечник",
        level=5,
        role_id=10002,
        hp_mul=1.0,
        atk_mul=1.0,
        xp_reward=120,
        gold_reward=60,
        is_stub=False,
        skills=(),
    ),
    "samurai_3": EnemyTemplate(
        enemy_id="samurai_3",
        name="Черный самурай",
        level=10,
        role_id=10004,
        hp_mul=1.0,
        atk_mul=1.0,
        xp_reward=250,
        gold_reward=120,
        is_stub=False,
        skills=(),
    ),
    # --- Stage 46: Location 2 mobs (L10/L15/L20) ---
    # Final stats: hp 900/1260/1700, atk 50-85 / 66-110 / 85-140
    "samurai_4": EnemyTemplate(
        enemy_id="samurai_4",
        name="Самурай 4",
        level=15,
        role_id=10001,
        hp_mul=2.5,        # 360*2.5 = 900
        atk_mul=2.1,       # 24*2.1=50, 40*2.1=84
        xp_reward=200,
        gold_reward=100,
        is_stub=False,
        skills=(),
    ),
    "samurai_5": EnemyTemplate(
        enemy_id="samurai_5",
        name="Самурай 5",
        level=15,
        role_id=10002,
        hp_mul=2.5,        # 500*2.5 = 1250
        atk_mul=2.0,       # 33*2=66, 55*2=110
        xp_reward=400,
        gold_reward=200,
        is_stub=False,
        skills=(),
    ),
    "samurai_6": EnemyTemplate(
        enemy_id="samurai_6",
        name="Самурай 6",
        level=20,
        role_id=10004,
        hp_mul=2.4,        # 700*2.4 = 1680
        atk_mul=2.0,       # 42*2=84, 70*2=140
        xp_reward=600,
        gold_reward=300,
        is_stub=False,
        skills=(),
    ),
    # --- Stage 79: Flower mob (Location 2, level 10) ---
    # Glass-cannon: high dodge, low HP. role_id=10102 (ROLE_FLOWER).
    # Stats: hp 800, atk ~27-45, dodge 22%, hit 79%, crit 10%.
    "flower_1": EnemyTemplate(
        enemy_id="flower_1",
        name="Цветок",
        level=10,
        role_id=10102,          # ROLE_FLOWER
        hp_mul=1.0,            # 800 (base role max_hp)
        atk_mul=1.0,           # role base atk
        xp_reward=220,
        gold_reward=110,
        is_stub=False,
        skills=(18003,),       # Stage 80 — Poison Dart (Яд)
    ),
    # --- Stage 46: Location 3 mobs (L20/L25/L30) ---
    # Final stats: hp 2200/2900/3800, atk 110-185 / 145-240 / 190-315
    "samurai_7": EnemyTemplate(
        enemy_id="samurai_7",
        name="Самурай 7",
        level=20,
        role_id=10001,
        hp_mul=6.1,        # 360*6.1 = 2196
        atk_mul=4.6,       # 24*4.6=110, 40*4.6=184
        xp_reward=800,
        gold_reward=400,
        is_stub=False,
        skills=(),
    ),
    "samurai_8": EnemyTemplate(
        enemy_id="samurai_8",
        name="Самурай 8",
        level=25,
        role_id=10002,
        hp_mul=5.8,        # 500*5.8 = 2900
        atk_mul=4.4,       # 33*4.4=145, 55*4.4=242
        xp_reward=1500,
        gold_reward=750,
        is_stub=False,
        skills=(),
    ),
    "samurai_9": EnemyTemplate(
        enemy_id="samurai_9",
        name="Самурай 9",
        level=30,
        role_id=10004,
        hp_mul=5.4,        # 700*5.4 = 3780
        atk_mul=4.5,       # 42*4.5=189, 70*4.5=315
        xp_reward=2200,
        gold_reward=1100,
        is_stub=False,
        skills=(),
    ),
    # --- Stage 46: Location 4 mobs (L30/L35/L40) ---
    # Final stats: hp 5200/6800/8800, atk 260-430 / 340-560 / 440-720
    "samurai_10": EnemyTemplate(
        enemy_id="samurai_10",
        name="Самурай 10",
        level=30,
        role_id=10001,
        hp_mul=14.4,       # 360*14.4 = 5184
        atk_mul=10.8,      # 24*10.8=259, 40*10.8=432
        xp_reward=2500,
        gold_reward=1200,
        is_stub=False,
        skills=(),
    ),
    "samurai_11": EnemyTemplate(
        enemy_id="samurai_11",
        name="Самурай 11",
        level=35,
        role_id=10002,
        hp_mul=13.6,       # 500*13.6 = 6800
        atk_mul=10.3,      # 33*10.3=340, 55*10.3=566
        xp_reward=4000,
        gold_reward=2000,
        is_stub=False,
        skills=(),
    ),
    "samurai_12": EnemyTemplate(
        enemy_id="samurai_12",
        name="Самурай 12",
        level=40,
        role_id=10004,
        hp_mul=12.6,       # 700*12.6 = 8820
        atk_mul=10.5,      # 42*10.5=441, 70*10.5=735
        xp_reward=6000,
        gold_reward=3000,
        is_stub=False,
        skills=(),
    ),
    # -----------------------------------------------------------------
    # Stage 213 — ЛАС НОЧЕС, враги 1-10 (этажи башни 1-10).
    # Статы = данные оригинала (запрос пользователя: «Сделай им такие
    # статы и имена. Аватарки и анимации мы изменим потом»). Ровно поэтому:
    #   - exact (EnemyExactStats) — числа НАПРЯМУЮ, формулы от Role не
    #     применяются; множители этажей башни на exact не действуют;
    #   - role_id=10001 (Самурай) для всех — ВИЗУАЛ пока прежний
    #     (samurai/idle через _tower_enemy_motion_folder), смена аватарок
    #     и анимаций — отдельная задача пользователя;
    #   - «Пробитие» №1 в дампе = pierce, «Пробитие» №2 (рядом с Блоком)
    #     = antiblock (а.блок) — соответствует панели статов (Проб/Защит,
    #     А.Блок/Блок, Хит/Уворот, Крит/Стойк).
    # Хит-парность с дампом: (Ур., ОЗ, Чакра, Атака, Защ., Скорость,
    # Проб, А.Блок, Блок, Метк., Уклон., Крит, Стойк.).
    # -----------------------------------------------------------------
    "ln_rudobon_1": EnemyTemplate(
        enemy_id="ln_rudobon_1",
        name="Рудобон",
        level=1,
        role_id=10001,
        xp_reward=50,
        gold_reward=25,
        is_stub=False,
        skills=(),
        exact=EnemyExactStats(
            max_hp=124, max_mp=124, min_atk=20, max_atk=25,
            defense=10, speed=1.26,
            pierce=10, antiblock=10, block=10,
            hit=10, dodge=10, crit=10, tough=10,
        ),
    ),
    "ln_hollow_1": EnemyTemplate(
        enemy_id="ln_hollow_1",
        name="Пустой-людоед",
        level=1,
        role_id=10001,
        xp_reward=55,
        gold_reward=28,
        is_stub=False,
        skills=(),
        exact=EnemyExactStats(
            max_hp=143, max_mp=143, min_atk=23, max_atk=28,
            defense=24, speed=1.00,
            pierce=10, antiblock=10, block=10,
            hit=10, dodge=480, crit=30, tough=10,
        ),
    ),
    "ln_rudobon_2": EnemyTemplate(
        enemy_id="ln_rudobon_2",
        name="Рудобон",
        level=2,
        role_id=10001,
        xp_reward=70,
        gold_reward=35,
        is_stub=False,
        skills=(),
        exact=EnemyExactStats(
            max_hp=233, max_mp=233, min_atk=24, max_atk=29,
            defense=32, speed=1.06,
            pierce=10, antiblock=10, block=10,
            hit=10, dodge=10, crit=36, tough=10,
        ),
    ),
    "ln_hollow_2": EnemyTemplate(
        enemy_id="ln_hollow_2",
        name="Пустой-людоед",
        level=2,
        role_id=10001,
        xp_reward=80,
        gold_reward=40,
        is_stub=False,
        skills=(),
        exact=EnemyExactStats(
            max_hp=121, max_mp=121, min_atk=37, max_atk=46,
            defense=64, speed=1.12,
            pierce=10, antiblock=10, block=10,
            hit=10, dodge=10, crit=42, tough=10,
        ),
    ),
    "ln_rudobon_3": EnemyTemplate(
        enemy_id="ln_rudobon_3",
        name="Рудобон",
        level=3,
        role_id=10001,
        xp_reward=95,
        gold_reward=48,
        is_stub=False,
        skills=(),
        exact=EnemyExactStats(
            max_hp=135, max_mp=135, min_atk=33, max_atk=41,
            defense=74, speed=1.06,
            pierce=10, antiblock=480, block=10,
            hit=10, dodge=10, crit=48, tough=10,
        ),
    ),
    "ln_hollow_4": EnemyTemplate(
        enemy_id="ln_hollow_4",
        name="Пустой-людоед",
        level=4,
        role_id=10001,
        xp_reward=120,
        gold_reward=60,
        is_stub=False,
        skills=(),
        exact=EnemyExactStats(
            max_hp=119, max_mp=119, min_atk=29, max_atk=35,
            defense=76, speed=0.50,
            pierce=10, antiblock=10, block=10,
            hit=10, dodge=10, crit=72, tough=10,
        ),
    ),
    "ln_rudobon_4": EnemyTemplate(
        enemy_id="ln_rudobon_4",
        name="Рудобон",
        level=4,
        role_id=10001,
        xp_reward=130,
        gold_reward=65,
        is_stub=False,
        skills=(),
        exact=EnemyExactStats(
            max_hp=119, max_mp=119, min_atk=72, max_atk=89,
            defense=76, speed=1.25,
            pierce=10, antiblock=10, block=10,
            hit=10, dodge=10, crit=72, tough=10,
        ),
    ),
    "ln_hollow_5": EnemyTemplate(
        enemy_id="ln_hollow_5",
        name="Пустой-людоед",
        level=5,
        role_id=10001,
        xp_reward=160,
        gold_reward=80,
        is_stub=False,
        skills=(),
        exact=EnemyExactStats(
            max_hp=147, max_mp=73, min_atk=19, max_atk=24,
            defense=115, speed=1.00,
            pierce=10, antiblock=10, block=10,
            hit=10, dodge=10, crit=76, tough=10,
        ),
    ),
    "ln_rudobon_6": EnemyTemplate(
        enemy_id="ln_rudobon_6",
        name="Рудобон",
        level=6,
        role_id=10001,
        xp_reward=200,
        gold_reward=100,
        is_stub=False,
        skills=(),
        exact=EnemyExactStats(
            max_hp=260, max_mp=260, min_atk=38, max_atk=46,
            defense=92, speed=1.11,
            pierce=10, antiblock=10, block=10,
            hit=10, dodge=10, crit=84, tough=10,
        ),
    ),
    "ln_rei_6": EnemyTemplate(
        enemy_id="ln_rei_6",
        name="Рэй",
        level=6,
        role_id=10001,
        xp_reward=240,
        gold_reward=120,
        is_stub=False,
        skills=(),
        exact=EnemyExactStats(
            max_hp=326, max_mp=326, min_atk=62, max_atk=72,
            defense=155, speed=1.05,
            pierce=10, antiblock=42, block=10,
            hit=42, dodge=10, crit=0, tough=53,
        ),
    ),
    # -----------------------------------------------------------------
    # FUTURE ENEMIES (Stage 12+) — just add entries here.
    # -----------------------------------------------------------------
    # "fire_ninja": EnemyTemplate(
    #     enemy_id="fire_ninja",
    #     name="Огненный ниндзя",
    #     level=10,
    #     role_id=10002,  # new Role for fire ninja
    #     hp_mul=1.3,
    #     atk_mul=1.4,
    #     xp_reward=200,
    #     gold_reward=100,
    #     is_stub=False,
    #     skills=(11804,),  # has "Огненный шар" skill
    # ),
}
