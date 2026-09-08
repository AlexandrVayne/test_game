"""Fight system — main turn-based loop (Layer B).

╔══════════════════════════════════════════════════════════════════════╗
║  СТАДИЯ 120 — ФУНДАМЕНТАЛЬНЫЙ ЗАКОН СКОРОСТИ И ХОДОВ (SPEED LAW)   ║
║                                                                      ║
║  Скорость (Fighter.speed) напрямую управляет ЧАСТОТОЙ ходов          ║
║  персонажа в бою (Multi-turn система). Любой персонаж, чья           ║
║  скорость значительно превышает скорость соперника, имеет            ║
║  ЗАКОННОЕ ПРАВО совершать несколько полноценных атак ПОДРЯД           ║
║  в рамках одного тика времени, пока соперник копит очки действия.    ║
║                                                                      ║
║  ЗАПРЕЩЕНО: замораживать список ходящих один раз за тик.             ║
║  ЗАПРЕЩЕНО: использовать поочерёдный пинг-понг                        ║
║             (attacker.attack → defender.attack).                     ║
║                                                                      ║
║  Динамический цикл: на каждом шаге выбирается боец с максимальным    ║
║  action_points (AP >= 1.0). После удара AP -= 1.0. Это позволяет     ║
║  быстрому бойцу (speed=5.9) сделать 5 ходов подряд, пока его AP      ║
║  не опустится ниже AP медленного (speed=1.0).                         ║
║                                                                      ║
║  Математический маркер (Ичиго speed=5.9, Моб speed=1.0, тик 1):     ║
║    Ход 1: Ичиго AP 5.9→4.9  (5.9 > 1.0)                              ║
║    Ход 2: Ичиго AP 4.9→3.9  (4.9 > 1.0)                              ║
║    Ход 3: Ичиго AP 3.9→2.9  (3.9 > 1.0)                              ║
║    Ход 4: Ичиго AP 2.9→1.9  (2.9 > 1.0)                              ║
║    Ход 5: Ичиго AP 1.9→0.9  (1.9 > 1.0)                              ║
║    Ход 6: Моб   AP 1.0→0.0  (1.0 > 0.9)                              ║
║    Конец тика: ни у кого нет AP >= 1.0.                              ║
╚══════════════════════════════════════════════════════════════════════╝

Stage 11 REFACTOR (data-driven combat):
  * The turn loop is now ABSTRACT — no skill-specific code. It iterates the
    attacker's `skills` tuple (skill deck), trying each skill via the generic
    `try_skill()` function. The first skill that triggers (MP cost met +
    trigger chance passes) is executed; if none trigger, falls back to a
    basic attack.
  * Status effects are handled generically via StatusManager:
      - on_turn_start(fighter, opponent): applies DoT (poison/burn/thunder_cloud),
        checks skip-turn (frozen/stun/paralyze). Returns list of FightValue
        events (POISON_DAMAGE, CLOUD_STRIKE) to emit before the main attack.
        If the fighter can't act, returns empty list — FightSystem emits a
        CANT_MOVE event based on the can_act() check.
      - on_turn_end(): decrements all effect durations (except thunder_cloud
        which is decremented in on_turn_start per spec), removes expired.

Stage 13 (NEW):
  * on_turn_start now takes opponent parameter (for thunder_cloud migration
    + caster lookup). Returns FightValue events to emit BEFORE the main
    attack — these are added to the fight log first.
  * If a skill triggers with fv.is_shield == 1 (shield applied), emit a
    separate SHIELD_APPLIED event afterwards (for UI to render shield dome).
  * If a skill triggers with fv.is_self_buff == 1 (no enemy damage), skip
    the death check on the defender (no damage was dealt).

Stage 120 (CRITICAL ARCHITECTURE FIX):
  * COMPLETELY REMOVED the old per-tick frozen `can_act` list + `act_idx`
    counter. That design starved fast fighters of their multi-turn rights.
  * Replaced with a DYNAMIC inner loop that re-evaluates who can act
    AFTER EVERY single attack, picking the fighter with the highest AP.
  * This enforces the SPEED LAW above: speed=5.9 → 5 consecutive attacks
    before the speed=1.0 opponent gets one.
"""
from __future__ import annotations

import random

from pockie_rpg.combat.damage import compute_attack, try_skill
from pockie_rpg.combat.events import EventType, FightSave, FightValue
from pockie_rpg.combat.fighter import Fighter
from pockie_rpg.combat.formulas import AP_CAP, AP_DEADLOCK_NUDGE
from pockie_rpg.combat.status_manager import SKIP_STATUSES
from pockie_rpg.config import MAX_BOUT


class FightSystem:
    """Turn-based autobattle engine — Stage 120/121 SPEED LAW compliant.

    The battle loop is a TWO-LEVEL structure:

    OUTER TICK LOOP (lines ~140-150):
      while bout < MAX_BOUT and both fighters alive:
          1. ACCUMULATE: fighter0.AP += fighter0.speed
                         fighter1.AP += fighter1.speed
          2. INNER DYNAMIC TURN LOOP (below)
          3. Loop continues until AP depletion or death.

    INNER DYNAMIC TURN LOOP (the SPEED LAW):
      while (fighter0.AP >= 1.0 and fighter0.alive) OR
            (fighter1.AP >= 1.0 and fighter1.alive):

          attacker = pick fighter with HIGHEST current AP
                     (tie-break: higher base `speed` goes first)

          bout += 1

          # Stage 121 — CONTROL EFFECTS CHECK (BEFORE on_turn_start)
          if attacker is frozen/stunned/paralyzed:
              emit CANT_MOVE
              attacker.status.on_turn_end()  # decrement non-control durations
              attacker.action_points -= 1.0  # Stage 191 — skip SPENDS an AP
              if attacker died (DoT): emit DIE, break
              continue  # re-evaluate who acts next

          # Normal turn (attacker NOT under control)
          on_turn_start (DoT: poison/burn/thunder_cloud)
          BEGIN_ATTACK
          try skills → basic attack fallback
          on_turn_end (decrement non-control durations)
          END_ATTACK

          attacker.action_points -= 1.0   # SPENT AFTER the attack

          if extra_turn triggered:
              attacker.action_points += 1.0  # refund for immediate next turn

          if anyone died: break

      Once no fighter has AP >= 1.0, the inner loop exits and the outer
      tick loop accumulates another round of AP. This is what makes a
      speed=5.9 fighter attack 5 times in a row during a single tick
      while a speed=1.0 fighter only attacks once.

    Stage 121 — CONTROL EFFECTS HANDLING (Crystal Blade freeze + extra_turn):
      * Control check (can_act()) moved BEFORE on_turn_start. This is critical
        for SPEED LAW: when Ichigo (speed=5.9) freezes the mob (speed=1.0),
        the mob's turn is skipped via CANT_MOVE + AP -= 1.0 + continue. The
        inner loop re-evaluates priority and gives the next turn to Ichigo
        (who still has AP > mob's AP), continuing his attack streak.
      * Stage 191 — RULE REVERSAL: пропущенный ход СПИСЫВАЕТ очко действия
        (AP -= 1.0 наравне с обычным ходом). Контроль реально стоит темпа:
        при равных скоростях между пропусками влезает ход соперника —
        удар по замороженному РАЗБИВАЕТ глыбу (урон ×2, «Глыба разрушена!»).
        Старое правило Stage 125/126 (банк AP сохранялся) вело к двойному
        пропуску подряд и мёртвому шаттеру при равных скоростях.
      * freeze duration NOT decremented here — управляет глобальный
        декремент (_global_freeze_decrement, Stage 126): в конце КАЖДОГО
        хода любого бойца, с just_applied-защитой хода наложения.
      * DoT (poison/burn/cloud) тикает ДО проверки контроля (Stage 122):
        замороженный получает урон от яда, но не атакует.

    Stage 11 turn sequence (data-driven, ABSTRACT — no skill-specific code):
      1. CONTROL CHECK: if attacker can't act (frozen/stun/paralyze): emit
         CANT_MOVE, call on_turn_end (decrements durations), advance cooldown,
         AP -= 1.0, continue. Otherwise proceed.
      2. STATUS on_turn_start: apply DoT (poison/burn/thunder_cloud), emit
         POISON_DAMAGE / CLOUD_STRIKE BEFORE the main attack.
      3. Emit BEGIN_ATTACK.
      4. Try each skill in the attacker's skill deck (via _try_skills).
         The first skill that triggers (MP cost met + trigger chance passes)
         is executed (damage + on_hit_effects applied generically). If a skill
         triggers and freezes the defender, emit a follow-up CANT_MOVE event
         with is_frozen=1. If a skill triggers and applies a shield, emit a
         follow-up SHIELD_APPLIED event. If a skill triggers an extra_turn,
         emit a follow-up EXTRA_TURN_ATTACK event.
      5. Else (no skill triggered): compute basic attack, emit ATTACK.
      6. STATUS on_turn_end: decrement all effect durations, remove expired.
      7. If defender died: emit DIE, break.
       + Stage 126 — global freeze decrement после КАЖДОГО хода (обоих бойцов,
         с just_applied-защитой хода наложения) + FREEZE_EXPIRED при спадании.
    """

    def __init__(self, fighter0: Fighter, fighter1: Fighter) -> None:
        """fighter0 = player (left), fighter1 = enemy (right)."""
        self.fighter0 = fighter0
        self.fighter1 = fighter1
        self.fight_save = FightSave()

    def fight(self) -> FightSave:
        """Run the full battle to completion. Returns the event log.

        Stage 120 — DYNAMIC MULTI-TURN SPEED LAW (per task spec):
        Each tick, both fighters accumulate action_points by their speed.
        Inner loop picks the fighter with the HIGHEST current AP to act,
        re-evaluating after EVERY attack. This lets a fast fighter
        (speed=5.9) chain multiple attacks in a single tick before
        the slow opponent (speed=1.0) gets one.

        Example (Ichigo speed=5.9, Mob speed=1.0, tick 1):
          AP after accumulate: Ichigo=5.9, Mob=1.0
          Turn 1: Ichigo (5.9 > 1.0) attacks → AP 4.9
          Turn 2: Ichigo (4.9 > 1.0) attacks → AP 3.9
          Turn 3: Ichigo (3.9 > 1.0) attacks → AP 2.9
          Turn 4: Ichigo (2.9 > 1.0) attacks → AP 1.9
          Turn 5: Ichigo (1.9 > 1.0) attacks → AP 0.9
          Turn 6: Mob (1.0 > 0.9) attacks → AP 0.0
          End of tick: no AP >= 1.0 → outer loop accumulates again.
        """
        # Stage 91 — initialize action_points from starting_action_points
        # (defaults to 0.0 for normal fighters; Tower boss_fast_start sets 0.5).
        self.fighter0.action_points = self.fighter0.starting_action_points
        self.fighter1.action_points = self.fighter1.starting_action_points
        # Randomize tiny starting offset so same-speed fighters don't deadlock
        if self.fighter0.speed == self.fighter1.speed and self.fighter0.action_points == self.fighter1.action_points:
            if random.randint(0, 100) < 50:
                self.fighter0.action_points += AP_DEADLOCK_NUDGE

        bout = 0
        # === OUTER TICK LOOP — accumulates AP once per tick ===
        while bout < MAX_BOUT and self.fighter0.is_alive and self.fighter1.is_alive:
            # --- 1. НАКОПЛЕНИЕ ОЧКОВ ДЕЙСТВИЯ (в начале каждого тика) ---
            self.fighter0.action_points += self.fighter0.speed
            self.fighter1.action_points += self.fighter1.speed

            # --- Stage 122 — AP CARRY-OVER CAP (максимум 10.0; Stage 170 —
            # константа AP_CAP в combat/formulas.py) ---
            # Жёсткое ограничение накопления AP. Без капа боец с speed=5.9
            # мог бы накопить AP=30+ за несколько тиков, делая 30+ атак подряд.
            # Кап 10.0 означает максимум 10 атак за тик — достаточно для
            # мультiturn системы, но не даёт бесконечного доминирования.
            if self.fighter0.action_points > AP_CAP:
                self.fighter0.action_points = AP_CAP
            if self.fighter1.action_points > AP_CAP:
                self.fighter1.action_points = AP_CAP

            # --- 2. ДИНАМИЧЕСКИЙ ЦИКЛ ХОДОВ (SPEED LAW) ---
            # Продолжается, пока хотя бы у одного ЖИВОГО бойца AP >= 1.0.
            # Никакого замороженного списка can_act — приоритет пересчитывается
            # на каждой итерации по текущим остаткам AP.
            ticks_this_bout = 0  # защита от бесконечного цикла при speed=0
            while ((self.fighter0.action_points >= 1.0 and self.fighter0.is_alive) or
                   (self.fighter1.action_points >= 1.0 and self.fighter1.is_alive)):

                # --- 3. ВЫБОР ТЕКУЩЕГО АТАКУЮЩЕГО (динамический приоритет) ---
                f0_can = self.fighter0.action_points >= 1.0 and self.fighter0.is_alive
                f1_can = self.fighter1.action_points >= 1.0 and self.fighter1.is_alive

                if f0_can and f1_can:
                    # Оба готовы — ход отдаётся тому, у кого БОЛЬШЕ AP
                    if self.fighter0.action_points > self.fighter1.action_points:
                        attacker = self.fighter0
                        defender = self.fighter1
                    elif self.fighter1.action_points > self.fighter0.action_points:
                        attacker = self.fighter1
                        defender = self.fighter0
                    else:
                        # AP равны — tie-break по базовой speed
                        if self.fighter0.speed >= self.fighter1.speed:
                            attacker = self.fighter0
                            defender = self.fighter1
                        else:
                            attacker = self.fighter1
                            defender = self.fighter0
                elif f0_can:
                    attacker = self.fighter0
                    defender = self.fighter1
                elif f1_can:
                    attacker = self.fighter1
                    defender = self.fighter0
                else:
                    # Никто не может ходить (both dead or AP < 1.0) — выход.
                    break

                if not defender.is_alive:
                    break

                bout += 1
                ticks_this_bout += 1
                if bout > MAX_BOUT:
                    break

                # =========================================================
                # Stage 122 — DoT TICK FIRST (even if frozen), then control check
                # =========================================================
                # on_turn_start вызывается ДО проверки can_act(). Это гарантирует
                # что DoT (poison/burn/thunder_cloud) тикает даже если боец
                # заморожен — per user spec: "Если персонаж заморожен, он не
                # должен атаковать, но яд на нем тикать обязан по стандартным
                # правилам". on_turn_start больше НЕ возвращает early для
                # frozen бойцов (Stage 122 fix в status_manager.py).
                # =========================================================
                start_events = attacker.status.on_turn_start(attacker, defender)
                for dot_fv in start_events:
                    self.fight_save.add(dot_fv)
                    if not attacker.is_alive:
                        self._emit_death(attacker)
                        break
                if not attacker.is_alive:
                    break

                # =========================================================
                # Stage 125 — CONTROL EFFECTS CHECK (AFTER on_turn_start)
                # =========================================================
                # Проверка эффектов контроля/пропуска хода. Если боец скован
                # freeze/stun/paralyze — он пропускает ход. DoT уже тикнул выше.
                #
                # ВАЖНО (Stage 125): длительность контроля декрементируется
                # в on_turn_end() САМОГО замороженного бойца (а НЕ атакующего
                # через стороннюю функцию). Защитник сам управляет своими
                # дебаффами в свой законный (пусть и пропущенный) ход.
                # =========================================================
                if not attacker.status.can_act():
                    active = attacker.status.get_active()
                    reason_statuses = [s for s in SKIP_STATUSES if s in active]
                    reason = ", ".join(reason_statuses) if reason_statuses else "skip"

                    # А) Пропуск фазы атаки/навыка.
                    # Б) Stage 191 — пропущенный ход СПИСЫВАЕТ очко действия:
                    #    контроль реально стоит темпа. При равных скоростях
                    #    это даёт каноничную очерёдность: пропуск → ход
                    #    соперника (удар по замороженному = шаттер ×2!) →
                    #    спад по таймеру. Старое правило Stage 125/126 (банк
                    #    AP сохранялся) вело к двойному пропуску подряд,
                    #    мгновенному удару после спадания и мёртвому шаттеру.
                    self.fight_save.add(FightValue(
                        role=0 if attacker.is_player else 1,
                        target=0 if attacker.is_player else 1,
                        event=EventType.CANT_MOVE,
                        log_text=f"{attacker.name} пропускает ход ({reason})!",
                    ))
                    # Stage 126 — длительности контроля здесь НЕ декрементируются
                    # (freeze/stun в NO_END_DECREMENT_STATUSES); их уменьшает
                    # глобальный декремент ниже. on_turn_end() нужен для
                    # остальных статусов (щит/яд).
                    attacker.status.on_turn_end()
                    # Stage 191 — списание AP за пропуск.
                    attacker.action_points -= 1.0
                    attacker.next_atk_time += attacker.atk_time  # UI compat
                    # Stage 126 — GLOBAL freeze decrement on BOTH fighters.
                    self._global_freeze_decrement()
                    # Д) Проверка смерти (DoT мог убить).
                    if not attacker.is_alive:
                        self._emit_death(attacker)
                        break
                    if not defender.is_alive:
                        break
                    continue

                # Emit BEGIN_ATTACK
                self.fight_save.add(FightValue(
                    role=0 if attacker.is_player else 1,
                    target=0 if defender.is_player else 1,
                    event=EventType.BEGIN_ATTACK,
                    log_text=f"Ход {bout}: {attacker.name} атакует",
                ))

                # --- SKILL TRIGGER (data-driven) ---
                skill_fv = self._try_skills(attacker, defender)
                if skill_fv is not None:
                    self.fight_save.add(skill_fv)
                    if skill_fv.is_frozen == 1:
                        self.fight_save.add(FightValue(
                            role=0 if defender.is_player else 1,
                            target=0 if defender.is_player else 1,
                            event=EventType.CANT_MOVE,
                            log_text=f"{defender.name} заморожен в глыбе и пропускает ход!",
                            is_frozen=1,
                        ))
                    if skill_fv.is_extra_turn == 1:
                        self.fight_save.add(FightValue(
                            role=0 if attacker.is_player else 1,
                            target=0 if defender.is_player else 1,
                            event=EventType.EXTRA_TURN_ATTACK,
                            log_text=f"{attacker.name} получает дополнительный ход!",
                            is_extra_turn=1,
                        ))
                    if skill_fv.is_shield == 1:
                        shielded_role = 0 if attacker.is_player else 1
                        self.fight_save.add(FightValue(
                            role=shielded_role,
                            target=shielded_role,
                            event=EventType.SHIELD_APPLIED,
                            log_text=f"{attacker.name} активирует щит!",
                            is_shield=1,
                        ))
                    if skill_fv.is_self_buff != 1:
                        if not defender.is_alive:
                            self._emit_death(defender)
                            break
                else:
                    fv = compute_attack(attacker, defender)
                    self.fight_save.add(fv)
                    if not defender.is_alive:
                        self._emit_death(defender)
                        break

                # --- STATUS: on_turn_end (decrements non-control durations) ---
                attacker.status.on_turn_end()
                self.fight_save.add(FightValue(
                    role=0 if attacker.is_player else 1,
                    target=0 if defender.is_player else 1,
                    event=EventType.END_ATTACK,
                ))

                # --- 4. СПИСАНИЕ AP ПОСЛЕ УДАРА (SPEED LAW) ---
                attacker.action_points -= 1.0

                # Stage 125 — NO decrement_control_durations on defender.
                # Freeze/stun durations are decremented by the frozen fighter's
                # OWN on_turn_end() when they get their turn (CANT_MOVE skip).

                # Extra turn через AP refund (Stage 121).
                if attacker.status.has_extra_turn():
                    attacker.status.consume_extra_turn()
                    attacker.action_points += 1.0
                else:
                    attacker.next_atk_time += attacker.atk_time

                # Stage 133 — MP regen REMOVED by design decision: nobody
                # regenerates MP in battle anymore. Battles are decided by
                # the starting MP pool only.

                # Stage 126 — GLOBAL freeze decrement on BOTH fighters.
                self._global_freeze_decrement()

                # --- 5. ПРОВЕРКА НА СМЕРТЬ ---
                if not defender.is_alive:
                    break
                if not attacker.is_alive:
                    break

            # Защита от бесконечного цикла: если за весь тик никто не ходил
            # (например, оба бойца имеют speed=0 из-за бага), принудительно
            # инкрементируем bout, чтобы в итоге достичь MAX_BOUT и выйти.
            if ticks_this_bout == 0:
                bout += 1

        # Determine winner
        if not self.fighter1.is_alive and self.fighter0.is_alive:
            self.fight_save.winner = 0  # player won
        elif not self.fighter0.is_alive and self.fighter1.is_alive:
            self.fight_save.winner = 1  # enemy won
        else:
            self.fight_save.winner = -1  # draw (max bout reached)

        self.fight_save.total_rounds = bout
        return self.fight_save

    # -----------------------------------------------------------------
    # Stage 126 — GLOBAL FREEZE DECREMENT
    # -----------------------------------------------------------------

    def _global_freeze_decrement(self) -> None:
        """Stage 126 — Decrement freeze durations on BOTH fighters.

        Called at the end of EVERY turn (both CANT_MOVE skip and normal attack).
        If a freeze expires (duration→0), emit a FREEZE_EXPIRED event so the
        UI replay can deactivate the ice overlay.
        """
        for fighter in (self.fighter0, self.fighter1):
            if not fighter.is_alive:
                continue
            expired = fighter.status.decrement_freeze_durations()
            for status_name in expired:
                self.fight_save.add(FightValue(
                    role=0 if fighter.is_player else 1,
                    target=0 if fighter.is_player else 1,
                    event=EventType.FREEZE_EXPIRED,
                    log_text=f"{fighter.name}: {status_name} рассеялся!",
                ))

    # -----------------------------------------------------------------
    # Stage 11 — DATA-DRIVEN HELPERS (no skill-specific code)
    # -----------------------------------------------------------------

    def _try_skills(self, attacker: Fighter, defender: Fighter) -> FightValue | None:
        """Iterate the attacker's skill deck. Return the first triggered skill, or None.

        Stage 11 — generic, data-driven. Iterates `attacker.skills` (a tuple
        of skill_ids), calling `try_skill(skill_id, attacker, defender)` for
        each. The first skill that triggers (MP cost met + trigger chance
        passes) is executed and its FightValue returned. If no skill triggers,
        returns None — caller falls back to a basic attack.

        No skill_id-specific branching — works for ANY skill in the registry.
        """
        for skill_id in attacker.skills:
            fv = try_skill(skill_id, attacker, defender)
            if fv is not None:
                return fv
        return None

    def _emit_death(self, defender: Fighter) -> None:
        """Emit a DIE event for the fallen defender."""
        self.fight_save.add(FightValue(
            role=0 if defender.is_player else 1,
            event=EventType.DIE,
            log_text=f"{defender.name} повержен!",
        ))
