"""CombatReplayMixin — combat replay + attack sequence + status sync.

Mixed into PygameUI. Provides the per-frame battle update loop, the
event-by-event combat replay, the multi-phase AttackSequence driver,
and the status/effect overlay synchronization.
"""
from __future__ import annotations

from pockie_rpg.combat.events import EventType
from pockie_rpg.combat.fight import FightSystem
from pockie_rpg.combat.skill_registry import get_skill_by_name
from pockie_rpg.config import (
    ATTACK_SEQ_ATTACK_DURATION,
    ATTACK_SEQ_ENEMY_REACH_X,
    ATTACK_SEQ_ENEMY_STRIKE_X,
    ATTACK_SEQ_HOLD_ENDGAME_DELAY,
    ATTACK_SEQ_PAUSE_DURATION,
    ATTACK_SEQ_PLAYER_REACH_X,
    ATTACK_SEQ_PLAYER_STRIKE_X,
    ATTACK_SEQ_RUN_BACK_DURATION,
    CAST_FIREBALL_CAST_OFFSET_X,
    CAST_FIREBALL_FPS,
    CAST_FIREBALL_H,
    CAST_FIREBALL_W,
    CAST_FIREBALL_Y_OFFSET,
    CRYSTAL_BLADE_FREEZE_DURATION,
    DAMAGE_NUMBER_IMPACT_Y_OFFSET,
    ENDGAME_TEXT_DURATION,
    ENEMY_SPRITE_X,
    EVENT_DELAY_ATTACK,
    EVENT_DELAY_BEGIN_ATTACK,
    EVENT_DELAY_CANT_MOVE,
    EVENT_DELAY_DIE,
    EVENT_DELAY_DOT,
    EVENT_DELAY_END_ATTACK,
    EVENT_DELAY_EXTRA_TURN,
    EVENT_DELAY_SHIELD,
    HIT_REACTION_DURATION,
    PARTICLE_IMPACT_Y_OFFSET,
    PLAYER_SPRITE_X,
    SPRITE_BASE_Y,
    TURN_EVENT_DELAY,
    BattleMode,
)
from pockie_rpg.game.state import ENEMY_MOBS, ROLES
from pockie_rpg.ui.effects import (
    _CONTINUOUS_OVERLAY_FOLDERS,
    _FIREBALL_SKILL_ID,
)


class CombatReplayMixin:
    """Battle-state update pipeline + combat replay + AttackSequence driver.

    Depends on PygameUI providing: asset_manager, _player_fighter,
    _enemy_fighter, _player_animator, _enemy_animator, _active_attack_seq,
    _combat_replay, _replay_event_idx, _replay_timer, _countdown_*,
    _endgame_*, _battle_speed, _particles, _damage_numbers, _player_*,
    _enemy_* (ice/shield/cloud/poison overlays), _cast_effect,
    _projectile_effect, _combat_log_lines, font_small, _add_log_line.
    """

    def _update_battle(self, dt: float) -> None:
        """Per-frame update for BATTLE state."""
        speed_dt = dt * self._battle_speed
        if self._player_animator is not None:
            self._player_animator.update(speed_dt, self.asset_manager)
        if self._enemy_animator is not None:
            self._enemy_animator.update(speed_dt, self.asset_manager)

        if self._active_attack_seq is not None:
            self._update_attack_sequence(speed_dt)

        if self._player_hit_timer > 0.0:
            self._player_hit_timer = max(0.0, self._player_hit_timer - speed_dt)
            if self._player_hit_timer == 0.0 and self._player_animator is not None:
                if (
                    self._player_fighter is not None
                    and self._player_fighter.is_alive
                    and not (self._active_attack_seq is not None and self._active_attack_seq.is_player)
                ):
                    self._player_animator.set_action("idle", self.asset_manager)
        if self._enemy_hit_timer > 0.0:
            self._enemy_hit_timer = max(0.0, self._enemy_hit_timer - speed_dt)
            if self._enemy_hit_timer == 0.0 and self._enemy_animator is not None:
                if (
                    self._enemy_fighter is not None
                    and self._enemy_fighter.is_alive
                    and not (self._active_attack_seq is not None and not self._active_attack_seq.is_player)
                ):
                    self._enemy_animator.set_action("idle", self.asset_manager)
        if self._enemy_shake_timer > 0.0:
            self._enemy_shake_timer = max(0.0, self._enemy_shake_timer - speed_dt)

        self._update_hp_mp_display(speed_dt)

        self._particles.update(speed_dt)
        self._damage_numbers.update(speed_dt)
        self._player_ice.update(speed_dt, self.asset_manager)
        self._enemy_ice.update(speed_dt, self.asset_manager)
        self._sync_effect_overlays()
        self._player_shield.update(speed_dt, self.asset_manager)
        self._enemy_shield.update(speed_dt, self.asset_manager)
        self._player_cloud.update(speed_dt, self.asset_manager)
        self._enemy_cloud.update(speed_dt, self.asset_manager)
        self._player_poison.update(speed_dt, self.asset_manager)
        self._enemy_poison.update(speed_dt, self.asset_manager)
        self._cast_effect.update(speed_dt, self.asset_manager)
        self._projectile_effect.update(speed_dt, self.asset_manager)

        if self._active_attack_seq is not None and not self._active_attack_seq.is_done():
            self._update_battle_watchdog(speed_dt)
            return

        if self._countdown_active:
            self._update_countdown(speed_dt)
            return

        if self._combat_replay is not None and not self._endgame_active:
            self._update_combat_replay(speed_dt)
            return

        if self._endgame_active:
            self._update_endgame(speed_dt)

    def _update_battle_watchdog(self, dt: float) -> None:
        """Stage 189 — страж зависания реплея.

        Проблема: тупики прошлого (RUN_BACK/HOLD Stage 188) выглядели в игре
        как «тишина» — спрайты стоят, ходы не идут, помощи ноль. diag ловит
        это ДО релиза, но регрессии бывают. Сторож меряет игровое время
        (с учётом кнопок x1-x4) с последнего ПРОГРЕССА реплея:
          * прогресс = обработанное событие, завершённая seq, смена фазы seq
            или старт endgame;
          * если боя жив, endgame не начался, а прогресса нет дольше
            BATTLE_WATCHDOG_TIMEOUT — пишем отчёт в _combat_debug_lines
            (виден в F10, при включённом F12 уходит в data/combat_debug.txt).
        Сторож НИЧЕГО не чинит сам (авто-починка может замаскировать баг) —
        только сигнализирует. Отчёты кэпятся BATTLE_WATCHDOG_REPORT_MAX.
        """
        from pockie_rpg.config import (
            BATTLE_WATCHDOG_REPORT_MAX,
            BATTLE_WATCHDOG_TIMEOUT,
        )

        if self._combat_replay is None or self._endgame_active:
            return
        if self._countdown_active:
            return

        seq = self._active_attack_seq
        seq_active = seq is not None and not seq.is_done()

        # Прогресс-сигналы сбрасывают «часы простоя» (Stage 189).
        # ВАЖНО: только РЕАЛЬНЫЕ изменения (индекс события/фаза seq),
        # иначе часы никогда не тикают. Отсутствие seq — НЕ прогресс само
        # по себе: между событиями законно нет seq, а тупик «seq зависла
        # навсегда» ловится сменой фазы (её нет) + event_idx (тот же).
        progressed = (
            self._replay_event_idx != self._watchdog_last_event_idx
            or (seq_active and seq.phase != self._watchdog_last_seq_phase)
        )
        if progressed:
            self._watchdog_event_time = 0.0
        else:
            self._watchdog_event_time += dt

        self._watchdog_last_event_idx = self._replay_event_idx
        self._watchdog_last_seq_phase = seq.phase if seq_active else None

        if self._watchdog_event_time >= BATTLE_WATCHDOG_TIMEOUT:
            if self._watchdog_reports < BATTLE_WATCHDOG_REPORT_MAX:
                pf = self._player_fighter
                ef = self._enemy_fighter
                seq_info = (
                    f"{seq.phase}@x={seq.current_x}"
                    if seq is not None
                    else "none"
                )
                report = (
                    f"[WATCHDOG] нет прогресса {BATTLE_WATCHDOG_TIMEOUT:.0f}с: "
                    f"event_idx={self._replay_event_idx}/{len(self._combat_replay.values)} "
                    f"seq={seq_info} "
                    f"P_hp={pf.hp if pf else '?'}/{pf.max_hp if pf else '?'} "
                    f"E_hp={ef.hp if ef else '?'}/{ef.max_hp if ef else '?'} "
                    f"(см. diag_replay_flow.py)"
                )
                # Stage 189 — рапорт в debug-журнал боя (F12/F10); getattr-
                # фолбэк для headless-харнессов без этого атрибута.
                dbg_lines = getattr(self, "_combat_debug_lines", None)
                if dbg_lines is None:
                    self._combat_debug_lines = []
                    dbg_lines = self._combat_debug_lines
                if report not in dbg_lines:
                    dbg_lines.append(report)
                    self._watchdog_reports += 1            # Сброс ТОЛЬКО после срабатывания — иначе часы не накопят порог.
            self._watchdog_event_time = 0.0

    def _sync_effect_overlays(self) -> None:
        """Activate/deactivate effect overlays based on runtime Fighter status.

        Stage 125 — REMOVED freeze/ice block sync from this method. The ice
        overlay is now driven by EVENTS (not by polling status.has() every
        frame). See _process_replay_event() for the event-driven activation:
          * ATTACK with is_frozen=1 → ice_effect.activate()
          * ATTACK with freeze_shattered=1 → ice_effect.deactivate()
          * CANT_MOVE with is_frozen=1 → ice_effect.activate()
          * CANT_MOVE with is_frozen=0 (thaw) → ice_effect.deactivate()
        """
        if self._player_fighter is not None:
            p = self._player_fighter
            if p.status.has("shield"):
                self._player_shield.activate(self.asset_manager)
            else:
                self._player_shield.deactivate()
            if p.status.has("thunder_cloud"):
                self._player_cloud.activate(self.asset_manager)
            else:
                self._player_cloud.deactivate()
            if p.status.has("poison"):
                self._player_poison.activate(self.asset_manager)
            else:
                self._player_poison.deactivate()
            # Stage 125 — NO freeze sync here (event-driven).
        else:
            self._player_shield.deactivate()
            self._player_cloud.deactivate()
            self._player_poison.deactivate()
        if self._enemy_fighter is not None:
            e = self._enemy_fighter
            if e.status.has("shield"):
                self._enemy_shield.activate(self.asset_manager)
            else:
                self._enemy_shield.deactivate()
            if e.status.has("thunder_cloud"):
                self._enemy_cloud.activate(self.asset_manager)
            else:
                self._enemy_cloud.deactivate()
            if e.status.has("poison"):
                self._enemy_poison.activate(self.asset_manager)
            else:
                self._enemy_poison.deactivate()
            # Stage 125 — NO freeze sync here (event-driven).
        else:
            self._enemy_shield.deactivate()
            self._enemy_cloud.deactivate()
            self._enemy_poison.deactivate()

    def _update_countdown(self, dt: float) -> None:
        """Advance countdown timer; transition to combat replay when complete."""
        from pockie_rpg.config import COUNTDOWN_PHASES
        if self._countdown_phase_idx >= len(COUNTDOWN_PHASES):
            self._countdown_active = False
            self._start_combat_replay()
            return

        self._countdown_timer += dt
        _, phase_duration = COUNTDOWN_PHASES[self._countdown_phase_idx]
        if self._countdown_timer >= phase_duration:
            self._countdown_timer = 0.0
            self._countdown_phase_idx += 1
            if self._countdown_phase_idx >= len(COUNTDOWN_PHASES):
                self._countdown_active = False
                self._start_combat_replay()

    def _start_combat_replay(self) -> None:
        """Run FightSystem.fight() and store result for event-by-event replay."""
        if self._player_fighter is None or self._enemy_fighter is None:
            return

        system = FightSystem(self._player_fighter, self._enemy_fighter)
        replay = system.fight()
        self._combat_replay = replay
        self._replay_event_idx = 0
        self._replay_timer = 0.0
        # Stage 189 — сторож зависания: часы и маркеры прогресса.
        self._watchdog_event_time = 0.0
        self._watchdog_last_event_idx = 0
        self._watchdog_last_seq_phase = None
        self._watchdog_reports = 0
        # Stage 190 — индекс ATTACK-события, которое применяет текущая seq.
        self._seq_applied_event_idx = -1

        self._player_fighter.hp = self._player_fighter.max_hp
        self._player_fighter.is_alive = True
        self._player_fighter.next_atk_time = self._player_fighter.atk_time
        self._player_fighter.status.clear()
        self._player_fighter.mp = self._player_fighter.max_mp
        self._enemy_fighter.hp = self._enemy_fighter.max_hp
        self._enemy_fighter.is_alive = True
        self._enemy_fighter.next_atk_time = self._enemy_fighter.atk_time
        self._enemy_fighter.status.clear()
        self._enemy_fighter.mp = self._enemy_fighter.max_mp

        self._player_ice.deactivate()
        self._enemy_ice.deactivate()
        self._player_shield.deactivate()
        self._enemy_shield.deactivate()
        self._player_cloud.deactivate()
        self._enemy_cloud.deactivate()
        self._player_poison.deactivate()
        self._enemy_poison.deactivate()
        self._cast_effect.deactivate()
        self._projectile_effect.deactivate()

        self._player_hp_display = float(self._player_fighter.hp)
        self._player_mp_display = float(self._player_fighter.mp)
        self._enemy_hp_display = float(self._enemy_fighter.hp)
        self._enemy_mp_display = float(self._enemy_fighter.mp)

        self._combat_log_lines.clear()
        self._add_log_line("Бой начинается! Ичиго против Самурая.")

    def _get_event_delay(self, event) -> float:
        """Stage 70 — return the delay for this event type.

        Each event type has its own cinematic delay (defined in config.py).
        Returns TURN_EVENT_DELAY as fallback for unknown event types.
        """
        ev = event.event
        if ev == EventType.ATTACK:
            return EVENT_DELAY_ATTACK
        elif ev == EventType.DIE:
            return EVENT_DELAY_DIE
        elif ev == EventType.BEGIN_ATTACK:
            return EVENT_DELAY_BEGIN_ATTACK
        elif ev == EventType.END_ATTACK:
            return EVENT_DELAY_END_ATTACK
        elif ev == EventType.CANT_MOVE:
            return EVENT_DELAY_CANT_MOVE
        elif ev == EventType.EXTRA_TURN_ATTACK:
            return EVENT_DELAY_EXTRA_TURN
        elif ev in (EventType.POISON_DAMAGE, EventType.CLOUD_STRIKE):
            return EVENT_DELAY_DOT
        elif ev == EventType.SHIELD_APPLIED:
            return EVENT_DELAY_SHIELD
        return TURN_EVENT_DELAY  # fallback

    def _update_combat_replay(self, dt: float) -> None:
        """Advance replay timer; process next event when delay elapses.

        Stage 42 — visual death trigger: if a fighter's HP reaches 0 AND the
        displayed HP bar has lerped close to 0 (<= 1.0), skip the remaining
        delay and immediately start endgame. This prevents the "phantom idle"
        where HP bar is empty but the timer keeps ticking.

        Stage 70 — INDIVIDUAL EVENT DELAYS. Each event type now has its own
        delay (EVENT_DELAY_ATTACK=0.2s beat after seq — Stage 189, EVENT_DELAY_DIE=2.0s, etc.) instead
        of the flat 1.08s for all events. The next event's delay is looked
        up BEFORE processing it, so the timer waits the right amount.
        """
        if self._combat_replay is None:
            return
        if self._replay_event_idx >= len(self._combat_replay):
            self._start_endgame()
            return

        # Stage 42/71 — visual death check: if either fighter is dead (hp <= 0)
        # and the displayed HP has caught up (<= 1.0), trigger death animation
        # THEN skip to endgame. Stage 71 fix: previously this skipped the DIE
        # event entirely, so the death animation never played. Now we set the
        # death action on the animator before starting endgame.
        #
        # Баг-фикс 2026-09 (симуляционный аудит боёв): обнуление ЧУЖОГО
        # HP-дисплея удалено — при смерти Ичиго бар ВРАГА схлопывался в ноль
        # (иллюзия «враг тоже упал» + окно «Поражение»). Бар победителя
        # остаётся на его реальном HP. Двухстрочный дубль в ветке смерти
        # врага удалён симметрично.
        if self._player_fighter is not None and not self._player_fighter.is_alive:
            if self._player_hp_display <= 1.0:
                # Stage 71 — trigger death animation before endgame.
                if self._player_animator is not None and self._player_animator.action not in ("death", "death_fall", "death_floor"):
                    self._player_animator.set_action("death", self.asset_manager)
                self._player_hp_display = 0.0
                self._start_endgame()
                return
        if self._enemy_fighter is not None and not self._enemy_fighter.is_alive:
            if self._enemy_hp_display <= 1.0:
                # Stage 71 — trigger death animation before endgame.
                if self._enemy_animator is not None and self._enemy_animator.action not in ("death", "death_fall", "death_floor"):
                    self._enemy_animator.set_action("death", self.asset_manager)
                self._enemy_hp_display = 0.0
                self._start_endgame()
                return

        # Stage 70 — look up the delay for the NEXT event.
        next_event = self._combat_replay.values[self._replay_event_idx]
        event_delay = self._get_event_delay(next_event)

        self._replay_timer += dt
        self._watchdog_event_time += dt
        if self._replay_timer >= event_delay:
            self._replay_timer = 0.0
            event = next_event
            self._process_combat_event(event)
            self._replay_event_idx += 1
            self._watchdog_event_time = 0.0

            # Stage 43 — combat debug logging.
            if getattr(self, "_combat_debug", False):
                pf = self._player_fighter
                ef = self._enemy_fighter
                dbg = (f"[{self._replay_event_idx-1}] ev={event.event.name} "
                       f"role={event.role} tgt={event.target} "
                       f"dmg={event.damage} hit={event.is_hit} crit={event.is_crit} "
                       f"P_hp={pf.hp if pf else '?'}/{pf.max_hp if pf else '?'} "
                       f"E_hp={ef.hp if ef else '?'}/{ef.max_hp if ef else '?'} "
                       f"P_mp={pf.mp if pf else '?'}/{pf.max_mp if pf else '?'} "
                       f"E_mp={ef.mp if ef else '?'}/{ef.max_mp if ef else '?'} "
                       f"P_disp={self._player_hp_display:.1f} "
                       f"E_disp={self._enemy_hp_display:.1f} "
                       f"txt={event.log_text}")
                self._combat_debug_lines.append(dbg)

            if event.event == EventType.DIE:
                self._replay_event_idx = len(self._combat_replay)
                if self._active_attack_seq is None or self._active_attack_seq.is_done():
                    self._start_endgame()
                return

            if self._replay_event_idx >= len(self._combat_replay):
                if self._active_attack_seq is None or self._active_attack_seq.is_done():
                    self._start_endgame()

    def _peek_attack_info(self, attacker_role: int) -> dict:
        """Look ahead in the FightSave for the next ATTACK event by this attacker."""
        _DEFAULTS = {
            "damage": 0, "is_hit": 0, "is_crit": 0, "is_parry": 0, "log_text": "",
            "skill_name": "", "is_frozen": 0,
            "is_ranged": 0, "is_self_buff": 0,
            "is_extra_turn": 0, "poison_applied": 0, "shield_applied": 0,
            "cloud_applied": 0, "cloud_duration": 0,
            "shield_absorbed": 0,
            "event_idx": -1,  # Stage 190 — индекс ATTACK-события (-1 = не найдено)
        }
        if self._combat_replay is None:
            return dict(_DEFAULTS)
        for i in range(self._replay_event_idx, len(self._combat_replay)):
            fv = self._combat_replay.values[i]
            if fv.event == EventType.ATTACK and fv.role == attacker_role:
                return {
                    "damage": fv.damage,
                    "is_hit": fv.is_hit,
                    "is_crit": fv.is_crit,
                    "is_parry": getattr(fv, "is_parry", 0),
                    "log_text": fv.log_text,
                    "skill_name": fv.skill_name,
                    "is_frozen": fv.is_frozen,
                    "is_ranged": fv.is_ranged,
                    "is_self_buff": fv.is_self_buff,
                    "is_extra_turn": fv.is_extra_turn,
                    "poison_applied": fv.poison_applied,
                    "shield_applied": fv.shield_applied,
                    "cloud_applied": fv.cloud_applied,
                    "cloud_duration": fv.cloud_duration,
                    "shield_absorbed": fv.shield_absorbed,
                    "event_idx": i,
                }
            if fv.event == EventType.BEGIN_ATTACK and i > self._replay_event_idx:
                break
        return dict(_DEFAULTS)

    def _process_combat_event(self, fv) -> None:
        """Apply a single combat event to the world state."""
        if self._player_animator is None or self._enemy_animator is None:
            return
        if self._player_fighter is None or self._enemy_fighter is None:
            return

        defender_fighter = (
            self._enemy_fighter if fv.role == 0 else self._player_fighter
        )

        if fv.event == EventType.BEGIN_ATTACK:
            attacker_fighter = self._player_fighter if fv.role == 0 else self._enemy_fighter
            defender_fighter = self._enemy_fighter if fv.role == 0 else self._player_fighter
            if attacker_fighter is not None and defender_fighter is not None:
                # Stage 188 — «сухой» тик (apply_damage=False): на ЗЕРКАЛЕ
                # синхронизируем ТОЛЬКО длительности/миграцию статусов.
                # Урон применит ниже POISON_DAMAGE/CLOUD_STRIKE-событие из
                # лога — иначе DoT срабатывал дважды (зеркало умирало раньше
                # движка, а лог дублировал строки тика).
                attacker_fighter.status.on_turn_start(
                    attacker_fighter, defender_fighter, apply_damage=False,
                )
            attack_info = self._peek_attack_info(fv.role)
            self._start_attack_sequence(fv.role, attack_info)
            if fv.log_text:
                self._add_log_line(fv.log_text)

        elif fv.event == EventType.ATTACK:
            # Stage 190 — OWNERSHIP-гейт: seq «забирает» своё событие ATTACK
            # по индексу (_seq_applied_event_idx проставляется в
            # _start_attack_sequence из подглядывания _peek_attack_info).
            # Урон и статусы применяет РОВНО ОДНА точка: seq (в момент удара)
            # ИЛИ это событие (фолбэк). Старый гейт `_active_attack_seq is
            # None` не работал никогда: ссылка на seq не чистится после
            # завершения, и self-buff'ы (Купол) навсегда теряли применение —
            # купол не появлялся на экране, а удары «в щит» выглядели
            # необъяснимым «0 урона».
            handled_by_seq = (
                getattr(self, "_seq_applied_event_idx", -1) == self._replay_event_idx
            )
            if not handled_by_seq and fv.is_hit and (
                fv.damage > 0 or fv.shield_absorbed > 0
            ):
                # Stage 188 — take_log_damage: fv.damage уже после щита
                # движка. Stage 190 — вызываем и при damage=0 (полное
                # поглощение щитом): зеркало должно списать absorbed,
                # иначе купол висит с полным запасом, когда движковый пуст.
                defender_fighter.take_log_damage(fv.damage, fv.shield_absorbed)
                # Аудит 2026-09 (вариант C) — путь без seq: мгновенная смерть.
                if not defender_fighter.is_alive:
                    self._kill_visuals(defender_fighter, defender_fighter.is_player)
                if defender_fighter.is_alive and fv.damage > 0:
                    self._trigger_hit_reaction(fv.target)
                # Stage 190 — обратная связь «щит поглотил»: полные поглощения
                # не дают ни цифры урона, ни реакции — без этой плашки удар
                # «в щит» выглядит как баг («бьёт на 0 урона»).
                if fv.shield_absorbed > 0:
                    impact_x = float(
                        ENEMY_SPRITE_X if fv.role == 0 else PLAYER_SPRITE_X
                    )
                    self._damage_numbers.spawn_text(
                        f"Щит поглотил {fv.shield_absorbed}!",
                        impact_x,
                        float(SPRITE_BASE_Y + DAMAGE_NUMBER_IMPACT_Y_OFFSET - 60),
                        color=(150, 205, 255),
                        font_size=44,
                        life=2.0,
                    )
                # Stage 71 — track damage dealt BY the player to the World Boss.
                if fv.role == 0 and self._world_boss_active:
                    self._world_boss_damage_dealt += fv.damage
            attacker_fighter = (
                self._player_fighter if fv.role == 0 else self._enemy_fighter
            )
            if fv.dec_mp > 0:
                attacker_fighter.mp = max(0, attacker_fighter.mp - fv.dec_mp)
            # Stage 125 — FREEZE SHATTER for ALL attacks (basic + skill).
            # If this attack consumed a freeze (freeze_shattered=1), remove
            # the freeze from the runtime defender AND deactivate the ice overlay.
            if fv.freeze_shattered == 1:
                defender_f = self._enemy_fighter if fv.role == 0 else self._player_fighter
                if defender_f is not None:
                    defender_f.status.remove("freeze")
                ice_effect = self._enemy_ice if fv.role == 0 else self._player_ice
                ice_effect.deactivate()
            # Stage 188/190 — статусы скилла применяет РОВНО ОДНА точка: seq
            # в _apply_attack_damage (в момент удара, владеет событием по
            # индексу) — ИЛИ этот фолбэк для событий БЕЗ seq (self-buff'ы
            # вроде Купола: seq для них не создаётся). Раньше гейт был
            # `_active_attack_seq is None` — он не срабатывал никогда
            # (протухшая ссылка), и Купол не доходил до зеркала.
            if (
                not handled_by_seq
                and fv.skill_name
                and fv.skill_name != "Базовая атака"
            ):
                attacker_f = self._player_fighter if fv.role == 0 else self._enemy_fighter
                defender_f = self._enemy_fighter if fv.role == 0 else self._player_fighter
                if fv.is_frozen == 1 and defender_f is not None:
                    # Stage 125 — apply freeze with the ACTUAL params from the skill
                    # (including damage_taken_multiplier=2.0) so the runtime fighter
                    # carries the same freeze as the engine.
                    skill = get_skill_by_name(fv.skill_name) if fv.skill_name else None
                    if skill and "freeze" in skill.on_hit_effects:
                        freeze_params = skill.on_hit_effects["freeze"]
                        duration = freeze_params.get("duration", 1)
                        effect_params = {k: v for k, v in freeze_params.items() if k not in ("chance", "duration")}
                    else:
                        duration = CRYSTAL_BLADE_FREEZE_DURATION
                        effect_params = {}
                    defender_f.status.apply("freeze", duration, effect_params)
                    ice_effect = self._enemy_ice if fv.role == 0 else self._player_ice
                    ice_effect.activate(self.asset_manager)
                # Stage 125 — FREEZE SHATTER: if this attack consumed a freeze,
                # remove it from the runtime fighter AND deactivate the ice overlay.
                if fv.freeze_shattered == 1 and defender_f is not None:
                    defender_f.status.remove("freeze")
                    ice_effect = self._enemy_ice if fv.role == 0 else self._player_ice
                    ice_effect.deactivate()
                if fv.poison_applied == 1 and defender_f is not None:
                    skill = get_skill_by_name(fv.skill_name)
                    if skill and "poison" in skill.on_hit_effects:
                        params = skill.on_hit_effects["poison"]
                        duration = params.get("duration", 4)
                        effect_params = {k: v for k, v in params.items() if k not in ("chance", "duration")}
                        defender_f.status.apply("poison", duration, effect_params)
                if fv.shield_applied == 1 and attacker_f is not None:
                    skill = get_skill_by_name(fv.skill_name)
                    if skill and "shield" in skill.on_hit_effects:
                        params = skill.on_hit_effects["shield"]
                        duration = params.get("duration", 4)
                        effect_params = {k: v for k, v in params.items() if k not in ("chance", "duration")}
                        attacker_f.status.apply("shield", duration, effect_params)
                if fv.cloud_applied == 1 and defender_f is not None:
                    duration = getattr(fv, "cloud_duration", 3) or 3
                    defender_f.status.apply("thunder_cloud", duration, {"caster_role_id": attacker_f.role_id if attacker_f else 0})
                if fv.is_extra_turn == 1 and attacker_f is not None:
                    attacker_f.status.apply("extra_turn", 1)
            # Stage 190 — лог-строка события: если seq владеет событием,
            # лог уже добавлен ею (pending_log_text в момент удара).
            if fv.log_text and not handled_by_seq:
                self._add_log_line(fv.log_text)

        elif fv.event == EventType.CANT_MOVE:
            frozen_fighter = (
                self._player_fighter if fv.role == 0 else self._enemy_fighter
            )
            frozen_animator = (
                self._player_animator if fv.role == 0 else self._enemy_animator
            )
            ice_effect = self._player_ice if fv.role == 0 else self._enemy_ice
            if (
                frozen_animator is not None
                and frozen_fighter.is_alive
                and not (
                    self._active_attack_seq is not None
                    and self._active_attack_seq.is_player == (fv.role == 0)
                    and not self._active_attack_seq.is_done()
                )
            ):
                frozen_animator.set_action("idle", self.asset_manager)
            if fv.is_frozen == 1:
                frozen_fighter.can_move = 0
                frozen_fighter.frozen_duration = CRYSTAL_BLADE_FREEZE_DURATION
                ice_effect.activate(self.asset_manager)
            else:
                frozen_fighter.tick_stun()
                if frozen_fighter.can_move == 1:
                    ice_effect.deactivate()
            if fv.log_text:
                self._add_log_line(fv.log_text)

        elif fv.event == EventType.FREEZE_EXPIRED:
            # Stage 126 — freeze expired by global duration decrement.
            # Deactivate the ice overlay for this fighter.
            ice_effect = self._player_ice if fv.role == 0 else self._enemy_ice
            ice_effect.deactivate()
            expired_fighter = (
                self._player_fighter if fv.role == 0 else self._enemy_fighter
            )
            if expired_fighter is not None:
                expired_fighter.status.remove("freeze")
            if fv.log_text:
                self._add_log_line(fv.log_text)

        elif fv.event == EventType.DIE:
            dying_animator = (
                self._player_animator if fv.role == 0 else self._enemy_animator
            )
            # Аудит 2026-09 (вариант C) — death-анимация могла УЖЕ быть
            # запущена мгновенной смертью (_kill_visuals) при смертельном
            # ударе; повторный set_action перезапустил бы её с первого кадра.
            if dying_animator is not None and dying_animator.action not in (
                    "death", "death_fall", "death_floor"):
                dying_animator.set_action("death", self.asset_manager)
            if (
                self._active_attack_seq is not None
                and self._active_attack_seq.is_player == (fv.role == 0)
            ):
                self._active_attack_seq = None
            if fv.role == 0:
                self._player_ice.deactivate()
                self._player_shield.deactivate()
                self._player_cloud.deactivate()
                self._player_poison.deactivate()
            else:
                self._enemy_ice.deactivate()
                self._enemy_shield.deactivate()
                self._enemy_cloud.deactivate()
                self._enemy_poison.deactivate()
            self._cast_effect.deactivate()
            self._projectile_effect.deactivate()
            if fv.log_text:
                self._add_log_line(fv.log_text)

        elif fv.event == EventType.END_ATTACK:
            attacker_fighter = self._player_fighter if fv.role == 0 else self._enemy_fighter
            if attacker_fighter is not None:
                attacker_fighter.status.on_turn_end()

        elif fv.event == EventType.CLOUD_STRIKE:
            struck_fighter = (
                self._player_fighter if fv.role == 0 else self._enemy_fighter
            )
            if struck_fighter is not None and fv.damage > 0:
                # Stage 188 — take_log_damage: урон из лога уже после щита.
                struck_fighter.take_log_damage(fv.damage, fv.shield_absorbed)
                # Аудит 2026-09 (вариант C) — DoT-смерть (туча): мгновенная
                # визуальная смерть (у DoT нет attack_seq).
                if not struck_fighter.is_alive:
                    self._kill_visuals(struck_fighter, struck_fighter.is_player)
                impact_x = float(PLAYER_SPRITE_X if fv.role == 0 else ENEMY_SPRITE_X)
                dn_y = float(SPRITE_BASE_Y + DAMAGE_NUMBER_IMPACT_Y_OFFSET)
                self._damage_numbers.spawn(
                    damage=fv.damage,
                    x=impact_x,
                    y=dn_y,
                    is_crit=False,
                )
                # Stage 71 — track DoT damage dealt TO the boss (role=1 = boss struck).
                if fv.role == 1 and self._world_boss_active:
                    self._world_boss_damage_dealt += fv.damage
            if fv.log_text:
                self._add_log_line(fv.log_text)

        elif fv.event == EventType.POISON_DAMAGE:
            poisoned_fighter = (
                self._player_fighter if fv.role == 0 else self._enemy_fighter
            )
            if poisoned_fighter is not None and fv.damage > 0:
                # Stage 188 — take_log_damage: урон из лога уже после щита.
                poisoned_fighter.take_log_damage(fv.damage, fv.shield_absorbed)
                # Аудит 2026-09 (вариант C) — DoT-смерть (яд): мгновенная
                # визуальная смерть.
                if not poisoned_fighter.is_alive:
                    self._kill_visuals(poisoned_fighter, poisoned_fighter.is_player)
                impact_x = float(PLAYER_SPRITE_X if fv.role == 0 else ENEMY_SPRITE_X)
                dn_y = float(SPRITE_BASE_Y + DAMAGE_NUMBER_IMPACT_Y_OFFSET)
                self._damage_numbers.spawn(
                    damage=fv.damage,
                    x=impact_x,
                    y=dn_y,
                    is_crit=False,
                    is_poison=True,
                )
                # Stage 71 — track DoT damage dealt TO the boss (role=1 = boss poisoned).
                if fv.role == 1 and self._world_boss_active:
                    self._world_boss_damage_dealt += fv.damage
            if fv.log_text:
                self._add_log_line(fv.log_text)

        elif fv.event == EventType.SHIELD_APPLIED:
            if fv.log_text:
                self._add_log_line(fv.log_text)

        elif fv.event == EventType.EXTRA_TURN_ATTACK:
            attacker_fighter = self._player_fighter if fv.role == 0 else self._enemy_fighter
            if attacker_fighter is not None:
                attacker_fighter.status.remove("extra_turn")
            if fv.log_text:
                self._add_log_line(fv.log_text)

    def _start_attack_sequence(self, attacker_role: int, attack_info: dict) -> None:
        """Begin a multi-phase AttackSequence for the attacker."""
        from pockie_rpg.ui.animator import AttackSequence

        is_player = (attacker_role == 0)
        animator = self._player_animator if is_player else self._enemy_animator
        if animator is None:
            return

        self._maybe_start_cast_effect(
            skill_name=attack_info.get("skill_name", ""),
            attacker_role=attacker_role,
            is_self_buff=attack_info.get("is_self_buff", 0),
            is_ranged=attack_info.get("is_ranged", 0),
        )

        is_self_buff = attack_info.get("is_self_buff", 0)
        if is_self_buff == 1:
            # Stage 190 — self-buff БЕЗ seq: владение событием остаётся у
            # ATTACK-фолбэка (он применит статусы). _seq_applied_event_idx
            # здесь НЕ трогаем.
            if attack_info.get("log_text", ""):
                self._add_log_line(attack_info["log_text"])
            return

        # Stage 190 — seq забирает своё ATTACK-событие по индексу: урон и
        # статусы применит она в момент удара, фолбэк-обработчик события
        # увидит handled_by_seq=True и пропустит применение.
        self._seq_applied_event_idx = attack_info.get("event_idx", -1)

        if is_player:
            base_x = PLAYER_SPRITE_X
            reach_x = ATTACK_SEQ_PLAYER_REACH_X
            strike_x = ATTACK_SEQ_PLAYER_STRIKE_X
        else:
            base_x = ENEMY_SPRITE_X
            reach_x = ATTACK_SEQ_ENEMY_REACH_X
            strike_x = ATTACK_SEQ_ENEMY_STRIKE_X

        is_ranged = attack_info.get("is_ranged", 0)
        # Stage 207 — исходный флип атакующего от ВНУТРЕННЕГО фейсинга его
        # скина (set_action вычисляет через needs_flip_for_player/enemy).
        # Хардкод «игрок → True / враг → False» был верен только для Ичиго
        # (intrinsic LEFT) и разворачивал pre-flipped cloth14 (intrinsic
        # RIGHT) спиной к врагу на беге/атаке.
        animator.set_action("attack" if is_ranged == 1 else "run", self.asset_manager)
        initial_flip = animator.flip

        seq = AttackSequence()
        seq.start(
            is_player=is_player,
            base_x=base_x,
            reach_x=reach_x,
            strike_x=strike_x,
            initial_flip=initial_flip,
            damage=attack_info.get("damage", 0),
            is_hit=attack_info.get("is_hit", 0),
            is_crit=attack_info.get("is_crit", 0),
            is_parry=attack_info.get("is_parry", 0),
            log_text=attack_info.get("log_text", ""),
            skill_name=attack_info.get("skill_name", ""),
            is_frozen=attack_info.get("is_frozen", 0),
            is_ranged=attack_info.get("is_ranged", 0),
            is_self_buff=is_self_buff,
            is_extra_turn=attack_info.get("is_extra_turn", 0),
            poison_applied=attack_info.get("poison_applied", 0),
            shield_applied=attack_info.get("shield_applied", 0),
            cloud_applied=attack_info.get("cloud_applied", 0),
            cloud_duration=attack_info.get("cloud_duration", 0),
            shield_absorbed=attack_info.get("shield_absorbed", 0),
        )
        self._active_attack_seq = seq

    def _maybe_start_cast_effect(
        self,
        skill_name: str,
        attacker_role: int,
        is_self_buff: int,
        is_ranged: int,
    ) -> None:
        """Start a one-shot cast/projectile effect overlay if the skill has one."""
        from pockie_rpg.config import FIREBALL_OVERLAY_FOLDER

        if not skill_name:
            return
        skill = get_skill_by_name(skill_name)
        if skill is None or not skill.effect_folder:
            return

        if skill.effect_folder in _CONTINUOUS_OVERLAY_FOLDERS:
            return

        if skill.skill_id == _FIREBALL_SKILL_ID:
            if attacker_role == 0:
                # Player casts toward the enemy (right): spawn in front (+X).
                start_x = PLAYER_SPRITE_X + CAST_FIREBALL_CAST_OFFSET_X
                end_x = ENEMY_SPRITE_X
                flip = True
            else:
                # Enemy casts toward the player (left): spawn in front (−X).
                start_x = ENEMY_SPRITE_X - CAST_FIREBALL_CAST_OFFSET_X
                end_x = PLAYER_SPRITE_X
                flip = False
            start_y = SPRITE_BASE_Y + CAST_FIREBALL_Y_OFFSET
            end_y = SPRITE_BASE_Y + CAST_FIREBALL_Y_OFFSET
            self._projectile_effect.start(
                folder=FIREBALL_OVERLAY_FOLDER,
                start_x=start_x,
                start_y=start_y,
                end_x=end_x,
                end_y=end_y,
                asset_manager=self.asset_manager,
                fps=CAST_FIREBALL_FPS,
                render_w=CAST_FIREBALL_W,
                render_h=CAST_FIREBALL_H,
                flip=flip,
            )
            return

        return

    def _update_attack_sequence(self, dt: float) -> None:
        """Advance the active AttackSequence through its phases."""
        from pockie_rpg.ui.animator import AttackSequence  # noqa: F401

        seq = self._active_attack_seq
        if seq is None or not seq.active:
            return

        animator = self._player_animator if seq.is_player else self._enemy_animator
        if animator is None:
            return

        seq.phase_timer += dt

        if seq.phase == "RUN_FORWARD":
            progress = min(1.0, seq.phase_timer / max(0.001, seq.phase_duration))
            seq.current_x = int(seq.base_x + (seq.reach_x - seq.base_x) * progress)
            if seq.phase_timer >= seq.phase_duration:
                # Stage 97 — PAUSE phase: sprite fixes near enemy before strike.
                seq.phase = "PAUSE"
                seq.phase_timer = 0.0
                seq.phase_duration = ATTACK_SEQ_PAUSE_DURATION
                # Switch to idle animation during pause (character stands still).
                animator.set_action("idle", self.asset_manager)
                animator.set_flip(seq.flip)

        elif seq.phase == "PAUSE":
            # Stage 97 — hold position at reach_x during pause.
            seq.current_x = seq.reach_x
            if seq.phase_timer >= seq.phase_duration:
                seq.phase = "ATTACK"
                seq.phase_timer = 0.0
                seq.phase_duration = ATTACK_SEQ_ATTACK_DURATION
                animator.set_action("attack", self.asset_manager)
                animator.set_flip(seq.flip)

        elif seq.phase == "ATTACK":
            progress = min(1.0, seq.phase_timer / max(0.001, seq.phase_duration))
            seq.current_x = int(seq.reach_x + (seq.strike_x - seq.reach_x) * progress)
            if seq.pending_is_ranged == 1:
                if not seq.damage_applied and not self._projectile_effect.active:
                    self._apply_attack_damage(seq)
                    seq.damage_applied = True
                    seq.phase = "DONE"
                    seq.active = False
                    # Stage 207 — возврат к базовому флипу скина (НЕ хардкод).
                    default_flip = animator.base_flip(self.asset_manager)
                    animator.set_action("idle", self.asset_manager)
                    animator.set_flip(default_flip)
                    seq.flip = default_flip
                    seq.current_x = seq.base_x
            else:
                if not seq.damage_applied and progress >= 0.5:
                    self._apply_attack_damage(seq)
                    seq.damage_applied = True
                    # Аудит 2026-09 (вариант C fix 2) — СМЕРТЕЛЬНЫЙ УДАР:
                    # seq переходит в HOLD (не DONE!): рендер читает
                    # seq.current_x пока seq жив и не DONE — при мгновенном
                    # DONE спрайт телепортировался бы на base_x. HOLD держит
                    # бойца у поверженного врага до самого endgame; seq
                    # финализируется (DONE) в _start_endgame.
                    defender_after = (
                        self._enemy_fighter if seq.is_player else self._player_fighter
                    )
                    if defender_after is not None and not defender_after.is_alive:
                        seq.phase = "HOLD"
                        seq.phase_timer = 0.0
                        animator.set_action("idle", self.asset_manager)
                        seq.current_x = seq.strike_x
                        return
                if seq.phase_timer >= seq.phase_duration:
                    seq.phase = "RUN_BACK"
                    seq.phase_timer = 0.0
                    seq.phase_duration = ATTACK_SEQ_RUN_BACK_DURATION
                    if animator.skin_actions is not None:
                        # Stage 208 — скины не зеркалятся НИГДЕ (RULES П13):
                        # на беге домой спрайт остаётся лицом к врагу
                        # (пре-флипнутые ассеты рисуются как есть).
                        seq.flip = False
                    else:
                        seq.flip = not seq.flip
                    animator.set_action("run", self.asset_manager)
                    animator.set_flip(seq.flip)

        # Stage 188 — восстановленный обработчик RUN_BACK: без него seq
        # навсегда зависала в фазе (is_done()=False → early return в
        # _update_battle блокировал реплей; бой замирал после 1-й атаки).
        elif seq.phase == "RUN_BACK":
            progress = min(1.0, seq.phase_timer / max(0.001, seq.phase_duration))
            seq.current_x = int(seq.strike_x + (seq.base_x - seq.strike_x) * progress)
            if seq.phase_timer >= seq.phase_duration:
                seq.phase = "DONE"
                seq.active = False
                seq.current_x = seq.base_x
                # Stage 207 — возврат к базовому флипу скина (НЕ хардкод);
                # прежний seq.flip = not seq.flip здесь перезаписывается.
                default_flip = animator.base_flip(self.asset_manager)
                animator.set_action("idle", self.asset_manager)
                animator.set_flip(default_flip)
                seq.flip = default_flip

        elif seq.phase == "HOLD":
            # Аудит 2026-09 (вариант C fix 2) — «стойка победителя» после
            # смертельного удара: боец стоит у поверженного врага
            # (current_x = strike_x). Stage 188 — HOLD ранее был тупиком
            # (endgame достижим только через заблокированный _update_combat_
            # replay): теперь после паузы ATTACK_SEQ_HOLD_ENDGAME_DELAY сек
            # запускается endgame.
            seq.current_x = seq.strike_x
            if seq.phase_timer >= ATTACK_SEQ_HOLD_ENDGAME_DELAY:
                # Stage 192 — победитель ОСТАЁТСЯ у поверженного врага на всё
                # время endgame: фаза PARKED держит спрайт на strike_x (рендер
                # читает current_x пока фаза != DONE). Спрайт вернётся на базу
                # только при выходе из боя или в новом раунде гантлета.
                seq.phase = "PARKED"
                seq.active = False
                self._start_endgame()

    def _kill_visuals(self, fighter, is_player: bool) -> None:
        """Аудит 2026-09 (вариант C) — мгновенная визуальная смерть бойца
        в момент СМЕРТЕЛЬНОГО удара (не дожидаясь DIE-события из лога):
        HP-бар → 0, death-анимация, оверлеи статусов выключаются.

        Дублирует логику ветки DIE + visual death check, но вызывается
        СРАЗУ после take_damage. Защита от повторного запуска death-анимации
        (set_action на уже мёртвом — no-op по action-имени).
        """
        if is_player:
            self._player_hp_display = 0.0
            if self._player_animator is not None and self._player_animator.action not in (
                    "death", "death_fall", "death_floor"):
                self._player_animator.set_action("death", self.asset_manager)
            self._player_ice.deactivate()
            self._player_shield.deactivate()
            self._player_cloud.deactivate()
            self._player_poison.deactivate()
        else:
            self._enemy_hp_display = 0.0
            if self._enemy_animator is not None and self._enemy_animator.action not in (
                    "death", "death_fall", "death_floor"):
                self._enemy_animator.set_action("death", self.asset_manager)
            self._enemy_ice.deactivate()
            self._enemy_shield.deactivate()
            self._enemy_cloud.deactivate()
            self._enemy_poison.deactivate()

    def _apply_attack_damage(self, seq) -> None:
        """Apply the pending damage + statuses to the defender at ATTACK midpoint."""
        if self._player_fighter is None or self._enemy_fighter is None:
            return

        defender_fighter = (
            self._enemy_fighter if seq.is_player else self._player_fighter
        )
        defender_role = 1 if seq.is_player else 0

        # Position for floating text (above the defender).
        defender_x = ENEMY_SPRITE_X if seq.is_player else PLAYER_SPRITE_X
        text_x = float(defender_x)
        text_y = float(SPRITE_BASE_Y + DAMAGE_NUMBER_IMPACT_Y_OFFSET - 60)

        if seq.pending_is_hit and (
            seq.pending_damage > 0 or seq.pending_shield_absorbed > 0
        ):
            # Stage 188/190 — take_log_damage: pending_damage уже после щита
            # движка (fv.damage), pending_shield_absorbed — сколько щит съел.
            # Stage 190 — вызываем и при damage=0 (полное поглощение):
            # иначе зеркало не списывает щит и купол висит с полным запасом,
            # когда движковый уже пуст.
            defender_fighter.take_log_damage(
                seq.pending_damage, seq.pending_shield_absorbed,
            )
            # Аудит 2026-09 (вариант C) — СМЕРТЕЛЬНЫЙ УДАР: визуальная смерть
            # врага СРАЗУ (бар в 0 + death-анимация), не дожидаясь DIE-события
            # (2.0 сек) и обрубания seq. Stage 188 — endgame запускает сама
            # HOLD-фаза seq по таймеру ATTACK_SEQ_HOLD_ENDGAME_DELAY
            # (visual death check заблокирован early-return seq — здесь он
            # бы не сработал).
            # ВАЖНО: второй аргумент — КТО УМИРАЕТ (защитник), не атакующий.
            if not defender_fighter.is_alive:
                self._kill_visuals(defender_fighter, defender_fighter.is_player)

        if seq.pending_log_text:
            self._add_log_line(seq.pending_log_text)

        # Stage 190 — обратная связь «щит поглотил»: при ПОЛНОМ поглощении
        # (damage=0) нет ни цифры урона, ни реакции — удар «в щит» выглядел
        # как баг. Плашка у защитника объясняет «0 урона».
        if seq.pending_is_hit and seq.pending_shield_absorbed > 0:
            self._damage_numbers.spawn_text(
                f"Щит поглотил {seq.pending_shield_absorbed}!",
                text_x, text_y,
                color=(150, 205, 255), font_size=44, life=2.0,
            )

        # Stage 50 — floating status text for miss/dodge/parry/crit.
        if not seq.pending_is_hit:
            # Miss/dodge — the attack didn't connect.
            self._damage_numbers.spawn_text(
                "Уклон!", text_x, text_y,
                color=(100, 200, 255), font_size=52, life=2.5,
            )
        elif getattr(seq, 'pending_is_parry', 0) == 1:
            # Parried — damage reduced by 50%.
            self._damage_numbers.spawn_text(
                "Парри!", text_x, text_y,
                color=(255, 200, 100), font_size=52, life=2.5,
            )

        if seq.pending_is_hit and seq.pending_damage > 0 and defender_fighter.is_alive:
            self._trigger_hit_reaction(defender_role)

        if seq.pending_is_hit and seq.pending_damage > 0:
            if seq.pending_is_ranged == 1:
                # Ranged skills (e.g. Fireball): the projectile lands ON the
                # defender, so spawn impact particles/text right at the defender
                # instead of the melee midpoint.
                impact_x = float(defender_x)
            else:
                impact_x = (seq.strike_x + defender_x) / 2.0
            impact_y = float(SPRITE_BASE_Y + PARTICLE_IMPACT_Y_OFFSET)
            is_crit = bool(seq.pending_is_crit)
            self._particles.spawn_hit(impact_x, impact_y, is_crit=is_crit)

            dn_y = float(SPRITE_BASE_Y + DAMAGE_NUMBER_IMPACT_Y_OFFSET)
            self._damage_numbers.spawn(
                damage=seq.pending_damage,
                x=impact_x,
                y=dn_y,
                is_crit=is_crit,
            )

            # Stage 132 — "Крит!" text in red, bold (spawn_text already uses bold font).
            if is_crit:
                self._damage_numbers.spawn_text(
                    "КРИТ!", text_x, text_y - 40,
                    color=(255, 50, 50), font_size=56, life=2.0,
                )

        if seq.pending_skill_name and seq.pending_skill_name != "Базовая атака":
            attacker_f = self._player_fighter if seq.is_player else self._enemy_fighter
            defender_f = self._enemy_fighter if seq.is_player else self._player_fighter
            # Аудит 2026-09 (вариант C) — статусы на ТРУПЕ не вешаем: если
            # смертельный удар убил защитника, оверлеи (лёд/яд/туча) на
            # «павшем» смотреть странно (щит атакующему — можно, он жив).
            defender_alive = (defender_f is not None and defender_f.is_alive)
            if seq.pending_is_frozen == 1 and defender_alive:
                defender_f.status.apply("freeze", CRYSTAL_BLADE_FREEZE_DURATION)
                ice_effect = self._enemy_ice if seq.is_player else self._player_ice
                ice_effect.activate(self.asset_manager)
            if seq.pending_poison_applied == 1 and defender_alive:
                skill = get_skill_by_name(seq.pending_skill_name)
                if skill and "poison" in skill.on_hit_effects:
                    params = skill.on_hit_effects["poison"]
                    duration = params.get("duration", 4)
                    effect_params = {k: v for k, v in params.items() if k not in ("chance", "duration")}
                    defender_f.status.apply("poison", duration, effect_params)
            if seq.pending_shield_applied == 1 and attacker_f is not None:
                skill = get_skill_by_name(seq.pending_skill_name)
                if skill and "shield" in skill.on_hit_effects:
                    params = skill.on_hit_effects["shield"]
                    duration = params.get("duration", 4)
                    effect_params = {k: v for k, v in params.items() if k not in ("chance", "duration")}
                    attacker_f.status.apply("shield", duration, effect_params)
            if seq.pending_cloud_applied == 1 and defender_alive:
                duration = seq.pending_cloud_duration or 3
                defender_f.status.apply("thunder_cloud", duration, {"caster_role_id": attacker_f.role_id if attacker_f else 0})

    def _trigger_hit_reaction(self, defender_role: int) -> None:
        """Trigger hit reaction on the defender."""
        if defender_role == 0:
            self._player_hit_timer = HIT_REACTION_DURATION
            if self._player_animator is not None:
                self._player_animator.set_action("hit", self.asset_manager)
        else:
            self._enemy_hit_timer = HIT_REACTION_DURATION
            self._enemy_shake_timer = HIT_REACTION_DURATION
            if self._enemy_animator is not None:
                self._enemy_animator.set_action("hit", self.asset_manager)

    def _update_hp_mp_display(self, dt: float) -> None:
        """Lerp displayed HP/MP toward actual values.

        Stage 70 — lerp speed now uses HP_LERP_SPEED (9.0, was 5.0) to ensure
        the HP bar catches up before the next event fires. With individual
        event delays (min 0.5s for END_ATTACK), the old 5.0 was too slow and
        the bar would lag behind the actual hp by several events.

        Stage 193 — здесь же обновляются ghost-значения (медленный «догоняющий»
        сегмент полосок, BAR_GHOST_LERP_SPEED < HP_LERP_SPEED).
        """
        from pockie_rpg.config import BAR_GHOST_LERP_SPEED, HP_LERP_SPEED
        lerp_k = min(1.0, dt * HP_LERP_SPEED)
        if self._player_fighter is not None:
            target = float(self._player_fighter.hp)
            self._player_hp_display += (target - self._player_hp_display) * lerp_k
            target_mp = float(self._player_fighter.mp)
            self._player_mp_display += (target_mp - self._player_mp_display) * lerp_k
        if self._enemy_fighter is not None:
            target = float(self._enemy_fighter.hp)
            self._enemy_hp_display += (target - self._enemy_hp_display) * lerp_k
            target_mp = float(self._enemy_fighter.mp)
            self._enemy_mp_display += (target_mp - self._enemy_mp_display) * lerp_k

        # Stage 193 — ghost: медленно догоняет заливку; при лечении мгновенно
        # подтягивается к заливке (белый сегмент показывает только ПОТЕРЮ).
        ghost_k = min(1.0, dt * BAR_GHOST_LERP_SPEED)
        if not hasattr(self, "_bar_ghosts"):
            self._bar_ghosts: dict[str, float] = {}
        ghosts = (
            ("p_hp", self._player_hp_display, self._player_fighter.hp if self._player_fighter is not None else None),
            ("p_mp", self._player_mp_display, self._player_fighter.mp if self._player_fighter is not None else None),
            ("e_hp", self._enemy_hp_display, self._enemy_fighter.hp if self._enemy_fighter is not None else None),
            ("e_mp", self._enemy_mp_display, self._enemy_fighter.mp if self._enemy_fighter is not None else None),
        )
        for key, disp, actual in ghosts:
            if actual is None:
                continue
            ghost = self._bar_ghosts.get(key, float(disp))
            if ghost < disp:
                ghost = float(disp)
            ghost += (float(actual) - ghost) * ghost_k
            if ghost < disp:
                ghost = float(disp)
            self._bar_ghosts[key] = ghost

    # Stage 193 — ghost-значения для рендера (доступ из BattleRendererMixin).
    @property
    def _player_hp_ghost(self) -> float:
        return self._bar_ghosts.get("p_hp", self._player_hp_display)

    @property
    def _player_mp_ghost(self) -> float:
        return self._bar_ghosts.get("p_mp", self._player_mp_display)

    @property
    def _enemy_hp_ghost(self) -> float:
        return self._bar_ghosts.get("e_hp", self._enemy_hp_display)

    @property
    def _enemy_mp_ghost(self) -> float:
        return self._bar_ghosts.get("e_mp", self._enemy_mp_display)

    def _start_endgame(self) -> None:
        """Trigger win/lose overlay based on combat_replay.winner.

        Stage 92 — Tower battles skip the standard endgame window entirely.
        Instead of showing "Победа/Поражение" text + rewards window, the
        flow goes directly to _finish_tower_battle → _exit_battle → Tower
        result modal on the MAP screen.
        """
        if self._combat_replay is None:
            return
        # Stage 192 — если seq ещё не финализирована через HOLD→PARKED (смерть
        # не от seq: DoT, DIE-путь и т.п.), помечаем PARKED БЕЗ сдвига
        # current_x к базе — спрайт остаётся там, где его застала смерть.
        # (HOLD-ветка сама переводит в PARKED перед вызовом этого метода.)
        if self._active_attack_seq is not None and self._active_attack_seq.phase not in ("DONE", "PARKED"):
            self._active_attack_seq.phase = "PARKED"
            self._active_attack_seq.active = False
        winner = self._combat_replay.winner
        if winner == 0:
            self._endgame_text = "Победа"
        elif winner == 1:
            self._endgame_text = "Поражение"
        else:
            self._endgame_text = "Поражение"

        # Stage 92 — Tower: skip standard endgame, go straight to tower result.
        if self._battle_mode == BattleMode.TOWER:
            self._finish_tower_battle()
            self._combat_replay = None
            self._endgame_active = False
            self._exit_battle()
            return

        # Stage 133 — slot machine gauntlet: chain into the next round or
        # finish with a result modal. Handled entirely by
        # _finish_gauntlet_round (never shows the standard endgame window).
        if self._battle_mode == BattleMode.SLOT_GAUNTLET:
            self._finish_gauntlet_round()
            return

        self._endgame_active = True
        self._endgame_phase = "text"
        self._endgame_text_timer = 0.0
        self._endgame_xp_gained = 0
        self._endgame_xp_bonus = 0  # Stage 184
        self._endgame_gold_gained = 0
        self._endgame_leveled_up = False
        self._endgame_old_level = self.player.level
        self._endgame_new_level = self.player.level
        self._combat_replay = None
        # Stage 112/118/119 — reset ALL drop tracking fields to prevent stale display.
        self._endgame_gems_dropped = None
        # Stage 119 — unified single equipment_drop field (max 1 per battle).
        self._endgame_equipment_drop = None

    def _apply_endgame_rewards(self) -> None:
        """Apply rewards to the player at the text->rewards phase transition.

        Stage 71 — World Boss: if this was a boss fight, calculate rank based
        on damage dealt, apply boss HP reduction, and give rank-based rewards.
        Stage 89 — Tower: dispatch to _finish_tower_battle (which sets the
        _tower_result modal instead of the normal endgame rewards window).
        """
        old_level = self.player.level
        is_victory = (self._endgame_text == "Победа")

        # Stage 89 — Tower battle: dispatch to the Tower reward handler.
        # The Tower result is shown via _render_tower_result (not the normal
        # endgame rewards window), so we skip the rest of this method.
        if self._battle_mode == BattleMode.TOWER:
            self._finish_tower_battle()
            # Skip the normal endgame rewards window — the Tower result modal
            # will be shown instead when the player exits battle.
            self._endgame_xp_gained = 0
            self._endgame_xp_bonus = 0  # Stage 184
            self._endgame_gold_gained = 0
            self._endgame_leveled_up = False
            self._endgame_old_level = old_level
            self._endgame_new_level = self.player.level
            return

        # Stage 71/95 — World Boss fight.
        # Stage 95 — FIX: _enter_world_boss_fight() already applied damage +
        # respawn + rewards. This block was causing DOUBLE damage (reducing
        # the NEW boss HP after respawn) and double gold reward.
        # Now we skip the rewards block entirely — all WB logic is in
        # _enter_world_boss_fight() which runs the instant fight + applies
        # rewards + respawns if killed, all BEFORE endgame text shows.
        if self._world_boss_active and self.target_mob_id == "world_boss":
            # The rewards were already applied in _enter_world_boss_fight().
            # Just set the display values (they may already be set, but this
            # ensures consistency if _apply_endgame_rewards is called again).
            self._endgame_xp_gained = 0
            self._endgame_gold_gained = getattr(self, "_endgame_gold_gained", 0)
            self._endgame_leveled_up = False
            self._endgame_old_level = old_level
            self._endgame_new_level = old_level
            return

        enemy = ENEMY_MOBS.get(self.target_mob_id)
        if enemy is None:
            self._endgame_xp_gained = 0
            self._endgame_gold_gained = 0
            self._endgame_leveled_up = False
            self._endgame_old_level = old_level
            self._endgame_new_level = old_level
            return

        if is_victory:
            # Stage 113 — call server-side process_battle_rewards (moved from UI).
            loc_id = int(self._map_location) if hasattr(self, "_map_location") else 1
            rewards = self.player.process_battle_rewards(
                is_victory=True,
                enemy_mob_id=enemy.mob_id,
                location_id=loc_id,
                enemy_xp=enemy.xp_reward,
                enemy_gold=enemy.gold_reward,
            )

            # Copy results to endgame display fields.
            self._endgame_xp_gained = rewards["xp"]
            # Stage 184 — бонус от xp-бафов (окно награды: «Опыт: 50 (+350)»).
            self._endgame_xp_bonus = rewards.get("xp_bonus", 0)
            self._endgame_gold_gained = rewards["gold"]
            self._endgame_leveled_up = rewards["leveled_up"]
            self._endgame_gems_dropped = rewards["gems"] if rewards["gems"] else None
            eq_drop = rewards.get("equipment_drop")
            self._endgame_equipment_drop = eq_drop

            self._track_daily_quest("kill_mobs")
            self.save_mgr.mark_dirty()
        else:
            self._endgame_xp_gained = 0
            self._endgame_xp_bonus = 0
            self._endgame_gold_gained = 0
            self._endgame_leveled_up = False
            self._endgame_equipment_drop = None

        player_role = ROLES.get(self.player.role_id)
        if player_role is not None:
            # Stage 134 — full-heal from the RECALC stats snapshot (gear + level
            # + title included); was player_role.max_hp (base role, no gear).
            stats = self.player.stats
            if stats is not None:
                self.player.current_hp = stats.max_hp
                self.player.current_mp = stats.max_mp

        self._endgame_old_level = old_level
        self._endgame_new_level = self.player.level

    def _update_endgame(self, dt: float) -> None:
        """Advance the phased endgame state machine."""
        if self._endgame_phase == "text":
            self._endgame_text_timer += dt
            if self._endgame_text_timer >= ENDGAME_TEXT_DURATION:
                self._apply_endgame_rewards()
                self._endgame_phase = "rewards"

    def _endgame_ok_clicked(self) -> None:
        """Handler for the rewards window OK button click."""
        if self._endgame_phase != "rewards":
            return
        self._endgame_phase = "done"
        self._endgame_active = False
        # Stage 88 — Fix 2.5: use debounced autosave instead of direct save.
        self.save_mgr.mark_dirty()
        # Stage 89 — if this was a Tower battle, show the Tower result modal
        # (which was already populated by _finish_tower_battle). The result
        # modal is shown on the MAP screen after _exit_battle.
        self._exit_battle()
        # After _exit_battle, state is MAP. If Tower, the _tower_result dict
        # is already set — _render_tower_result will show it on the MAP.
        # (No need to reopen the Tower modal here — _close_tower_result does
        # that when the player clicks OK on the result modal.)
