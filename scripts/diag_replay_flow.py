"""diag_replay_flow.py — Stage 188, headless smoke анимированного боя.

ЧТО ЭТО: «робот-тестировщик» боя. Он запускает тот же код, что играет
анимационный бой на экране (CombatReplayMixin._update_battle), но БЕЗ окна —
виртуальный видеодрайвер SDL dummy. Для каждого сценария он:

  1) прогоняет FightSystem.fight() — как игра после каунтдауна;
  2) запоминает финальное HP бойцов у ДВИЖКА;
  3) откатывает бойцов в полное HP (как _start_combat_replay) и проигрывает
     лог событий покадрово, как на экране;
  4) проверяет: endgame («Победа/Поражение») ДОСТИГНУТ за лимит времени,
     HP зеркала совпадает с движком (DoT не тикает дважды), seq не зависла
     в RUN_BACK/HOLD, текст endgame соответствует winner.

Регрессии, которые ловит: тупик RUN_BACK (бой замирал после 1-й атаки),
тупик HOLD (смертельный удар не открывал endgame), двойной DoT-урон.

Запуск: python scripts/diag_replay_flow.py   (exit 0 = всё ок, 1 = FAIL)
"""
from __future__ import annotations

import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
try:  # кириллица PASS/FAIL-строк в консоли Windows
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

import pygame  # noqa: E402

pygame.init()
pygame.display.set_mode((1, 1))

from pockie_rpg.combat.fight import FightSystem  # noqa: E402
from pockie_rpg.combat.fighter import Fighter  # noqa: E402
from pockie_rpg.config import BattleMode  # noqa: E402
from pockie_rpg.ui.combat_replay import CombatReplayMixin  # noqa: E402

DT = 1.0 / 60.0
SPEED = 10.0          # ускоряем симуляцию (кнопка «x10»)
SIM_LIMIT_SEC = 600.0  # лимит ИГРОВОГО времени до endgame


class StubAnimator:
    def __init__(self) -> None:
        self.action = "idle"

    def update(self, dt, am) -> None: ...
    def set_action(self, a, am) -> None: self.action = a
    def set_flip(self, f) -> None: ...


class _StubFxBase:
    def __init__(self) -> None:
        self.active = False

    def update(self, dt, am=None) -> None: ...
    def activate(self, am=None) -> None: self.active = True
    def deactivate(self) -> None: self.active = False
    def render(self, *a, **k) -> None: ...


class StubParticles(_StubFxBase):
    def spawn_hit(self, *a, **k) -> None: ...
    def spawn(self, *a, **k) -> None: ...
    def spawn_text(self, *a, **k) -> None: ...
    def clear(self) -> None: ...


class StubProjectile(_StubFxBase):
    """Снаряд «летит» один кадр — достаточно для ranged-ветки seq."""

    def __init__(self) -> None:
        super().__init__()
        self.started = False

    def start(self, **kw) -> None:
        self.active = True
        self.started = True

    def update(self, dt, am=None) -> None:
        self.active = False


class Harness(CombatReplayMixin):
    """Минимальный «экран боя»: только то, что нужно _update_battle."""

    def __init__(self, pf: Fighter, ef: Fighter, replay) -> None:
        self._battle_speed = SPEED
        self._player_animator = StubAnimator()
        self._enemy_animator = StubAnimator()
        self._player_fighter = pf
        self._enemy_fighter = ef
        self._active_attack_seq = None
        self._player_hit_timer = 0.0
        self._enemy_hit_timer = 0.0
        self._enemy_shake_timer = 0.0
        self._player_hp_display = float(pf.hp)
        self._player_mp_display = float(pf.mp)
        self._enemy_hp_display = float(ef.hp)
        self._enemy_mp_display = float(ef.mp)
        self._particles = StubParticles()
        self._damage_numbers = StubParticles()
        self._player_ice = _StubFxBase()
        self._enemy_ice = _StubFxBase()
        self._player_shield = _StubFxBase()
        self._enemy_shield = _StubFxBase()
        self._player_cloud = _StubFxBase()
        self._enemy_cloud = _StubFxBase()
        self._player_poison = _StubFxBase()
        self._enemy_poison = _StubFxBase()
        self._cast_effect = _StubFxBase()
        self._projectile_effect = StubProjectile()
        self._countdown_active = False
        self._combat_replay = replay
        self._replay_event_idx = 0
        self._replay_timer = 0.0
        # Stage 189 — watchdog-поля (в игре их создаёт _start_combat_replay).
        self._watchdog_event_time = 0.0
        self._watchdog_last_event_idx = 0
        self._watchdog_last_seq_phase = None
        self._watchdog_reports = 0
        # Stage 190 — владение ATTACK-событием текущей seq.
        self._seq_applied_event_idx = -1
        self._endgame_active = False
        self._endgame_phase = "text"
        self._endgame_text = ""
        self._endgame_text_timer = 0.0
        self._battle_mode = BattleMode.NORMAL
        self._world_boss_active = False
        self._world_boss_damage_dealt = 0
        self._combat_log_lines: list[str] = []
        self.player = type("P", (), {"level": 3})()
        self.asset_manager = object()

    def _add_log_line(self, text: str) -> None:
        self._combat_log_lines.append(text)

    def _apply_endgame_rewards(self) -> None:  # награды вне скоупа diag
        ...


def _fighter(**kw) -> Fighter:
    base = dict(
        name="Ичиго", role_id=1, is_player=True, hp=500, mp=100,
        max_hp=500, max_mp=100, min_atk=30, max_atk=40, speed=1.0, skills=(),
    )
    base.update(kw)
    return Fighter(**base)


def _reset_mirrors(pf: Fighter, ef: Fighter) -> None:
    for f in (pf, ef):
        f.hp = f.max_hp
        f.mp = f.max_mp
        f.is_alive = True
        f.status.clear()


def _expected_text(winner: int) -> str:
    return "Победа" if winner == 0 else "Поражение"


def run_scenario(
    tag: str,
    pf: Fighter,
    ef: Fighter,
    expected_winner: int,
    pre_status=None,
) -> tuple[bool, str]:
    """Прогнать один сценарий; вернуть (ok, сообщение)."""
    system = FightSystem(pf, ef)
    replay = system.fight()
    engine_final = (pf.hp, ef.hp)
    if replay.winner != expected_winner:
        return False, (
            f"winner={replay.winner}, ожидался {expected_winner} "
            f"(сценарий сконструирован неверно)"
        )

    _reset_mirrors(pf, ef)
    if pre_status is not None:
        pre_status(pf, ef)

    h = Harness(pf, ef, replay)
    game_t = 0.0
    while game_t < SIM_LIMIT_SEC:
        h._update_battle(DT)
        game_t += DT * SPEED
        if h._endgame_active:
            break

    seq = h._active_attack_seq
    seq_ok = seq is None or seq.phase in ("DONE", "PARKED")  # Stage 192 — PARKED = победитель у поверженного врага
    hp_ok = (h._player_fighter.hp == engine_final[0]
             and h._enemy_fighter.hp == engine_final[1])
    endgame_ok = h._endgame_active
    text_ok = h._endgame_text == _expected_text(expected_winner)
    # Stage 189 — на здоровых боях страж зависания обязан молчать.
    wd_ok = getattr(h, "_watchdog_reports", 0) == 0

    problems = []
    if not endgame_ok:
        problems.append(f"endgame НЕ достигнут за {SIM_LIMIT_SEC:.0f}с игры")
    if not hp_ok:
        problems.append(
            f"HP зеркала ({h._player_fighter.hp}/{h._enemy_fighter.hp}) "
            f"!= движку ({engine_final[0]}/{engine_final[1]})"
        )
    if not seq_ok:
        problems.append(f"seq зависла в фазе {seq.phase}")
    if not text_ok:
        problems.append(
            f"текст «{h._endgame_text}» != «{_expected_text(expected_winner)}»"
        )
    if not wd_ok:
        problems.append(
            f"страж сработал {h._watchdog_reports} раз на здоровом бою"
        )
    ok = not problems
    msg = "OK" if ok else "; ".join(problems)
    return ok, msg


def _find_ranged_seed(max_seeds: int = 100) -> tuple[int, object] | None:
    """Сценарий 6: нужен лог, где Огненный шар реально сработал."""
    for seed in range(max_seeds):
        random.seed(seed)
        pf = _fighter(skills=(10001,), mp=100)
        ef = _fighter(name="Самурай", role_id=2, is_player=False, hp=3000, max_hp=3000)
        replay = FightSystem(pf, ef).fight()
        if any(fv.is_ranged == 1 for fv in replay.values):
            return seed, (pf, ef, replay)
    return None


def main() -> int:
    scenarios: list[tuple[str, object, int, object | None]] = []

    # 1. Обычный бой: игрок быстрее (SPEED LAW), несколько ходов.
    random.seed(11)
    pf = _fighter(speed=3.0)
    ef = _fighter(name="Самурай", role_id=2, is_player=False, hp=220, max_hp=220)
    scenarios.append(("1 обычный_бой (победа по SPEED LAW)", (pf, ef), 0, None))

    # 2. Смерть с одной атаки игрока (HOLD-путь, «стойка победителя»).
    random.seed(2)
    pf = _fighter(min_atk=900, max_atk=900)
    ef = _fighter(name="Самурай", role_id=2, is_player=False)
    scenarios.append(("2 смерть_с_одной_атаки (HOLD -> Победа)", (pf, ef), 0, None))

    # 3. Враг ваншотит игрока (HOLD-путь за врага).
    random.seed(3)
    pf = _fighter(hp=10, max_hp=10)
    ef = _fighter(name="Самурай", role_id=2, is_player=False, min_atk=900, max_atk=900)
    scenarios.append(("3 поражение_с_одной_атаки (HOLD -> Поражение)", (pf, ef), 1, None))

    # 4. Яд на ОБОИХ заранее: тик должен примениться РОВНО ОДИН раз.
    random.seed(4)
    pf = _fighter(hp=400, max_hp=400)
    ef = _fighter(name="Цветок", role_id=10102, is_player=False, hp=400, max_hp=400)

    def _poison_both(p: Fighter, e: Fighter) -> None:
        params = {"dmg_pct_max_hp": 0.05}
        p.status.apply("poison", 4, dict(params))
        e.status.apply("poison", 4, dict(params))

    scenarios.append(("4 яд_на_обоих (инвариант HP)", (pf, ef), 0, _poison_both))

    # 5. Заморозка врага до боя: CANT_MOVE + разрушение глыбы + усиление.
    random.seed(5)
    pf = _fighter()
    ef = _fighter(name="Самурай", role_id=2, is_player=False, hp=300, max_hp=300)

    def _freeze_enemy(_p: Fighter, e: Fighter) -> None:
        e.status.apply("freeze", 2, {"damage_taken_multiplier": 2.0})

    scenarios.append(("5 заморозка_врага (CANT_MOVE/shatter)", (pf, ef), 0, _freeze_enemy))

    # 6. Дальний бой (Огненный шар): ищем seed, где снаряд сработал.
    found = _find_ranged_seed()
    if found is None:
        print("FAIL 6 дальний_бой: за 100 seed'ов Огненный шар не сработал")
        return 1
    seed6, (pf, ef, replay6) = found

    def _run_ranged() -> tuple[bool, str]:
        engine_final = (pf.hp, ef.hp)
        _reset_mirrors(pf, ef)
        h = Harness(pf, ef, replay6)
        game_t = 0.0
        while game_t < SIM_LIMIT_SEC:
            h._update_battle(DT)
            game_t += DT * SPEED
            if h._endgame_active:
                break
        seq = h._active_attack_seq
        problems = []
        if not h._endgame_active:
            problems.append(f"endgame НЕ достигнут за {SIM_LIMIT_SEC:.0f}с игры")
        if not h._projectile_effect.started:
            problems.append("снаряд не был запущен (ranged-путь не выполнен)")
        if not (h._player_fighter.hp == engine_final[0]
                and h._enemy_fighter.hp == engine_final[1]):
            problems.append(
                f"HP зеркала ({h._player_fighter.hp}/{h._enemy_fighter.hp}) "
                f"!= движку ({engine_final[0]}/{engine_final[1]})"
            )
        if seq is not None and seq.phase not in ("DONE", "PARKED"):
            problems.append(f"seq зависла в фазе {seq.phase}")
        if getattr(h, "_watchdog_reports", 0) != 0:
            problems.append("страж сработал на здоровом бою")
        ok = not problems
        return ok, "OK" if ok else "; ".join(problems)

    ok6, msg6 = _run_ranged()
    print(f"{'PASS' if ok6 else 'FAIL'}  6 дальний_бой (Fireball, seed={seed6}): {msg6}")

    # 7. Щит у игрока: поглощение урона должно совпасть с движком.
    random.seed(7)
    pf = _fighter(hp=300, max_hp=300)
    ef = _fighter(name="Самурай", role_id=2, is_player=False, hp=300, max_hp=300)

    def _shield_player(p: Fighter, _e: Fighter) -> None:
        p.status.apply("shield", 4, {"amount": 300})

    scenarios.append(("7 щит_у_игрока (поглощение)", (pf, ef), 0, _shield_player))

    # 8. Грозовая туча на враге (автор — игрок): CLOUD_STRIKE тикает 1 раз.
    random.seed(8)
    pf = _fighter()
    ef = _fighter(name="Самурай", role_id=2, is_player=False, hp=400, max_hp=400)

    def _cloud_enemy(_p: Fighter, e: Fighter) -> None:
        e.status.apply("thunder_cloud", 3, {"caster_role_id": 1, "cloud_dmg_multiplier": 0.6})

    scenarios.append(("8 туча_на_враге (CLOUD_STRIKE)", (pf, ef), 0, _cloud_enemy))

    # 9. Явный SPEED LAW: 5.9 vs 1.0, живучие бойцы — длинный лог.
    random.seed(9)
    pf = _fighter(speed=5.9, hp=2000, max_hp=2000)
    ef = _fighter(name="Самурай", role_id=2, is_player=False, hp=1500, max_hp=1500)
    scenarios.append(("9 speed_law 5.9 vs 1.0", (pf, ef), 0, None))

    # 10. Ничья по MAX_BOUT: крошечный урон, оба живы — endgame без DIE.
    random.seed(10)
    pf = _fighter(hp=10**9, max_hp=10**9, min_atk=0, max_atk=0)
    ef = _fighter(
        name="Самурай", role_id=2, is_player=False,
        hp=10**9, max_hp=10**9, min_atk=0, max_atk=0,
    )
    scenarios.append(("10 ничья MAX_BOUT (без смертей)", (pf, ef), -1, None))

    failures = 0
    for tag, (pf, ef), winner, pre in scenarios:
        ok, msg = run_scenario(tag, pf, ef, winner, pre)
        print(f"{'PASS' if ok else 'FAIL'}  {tag}: {msg}")
        if not ok:
            failures += 1

    print("-" * 60)
    total = len(scenarios) + 1  # + ranged-сценарий 6
    if failures == 0 and ok6:
        print(f"ALL PASS ({total}/{total} сценариев)")
        return 0
    print(f"FAILED: {failures + (0 if ok6 else 1)}/{total}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
