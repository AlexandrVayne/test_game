# PROJECT_PROMPT — Pockie RPG (Ninja Wars 2)

> **Точка входа в проект (Stage 178).** Контекст — 3 файла: RULES (как работать)
> → PROJECT_PROMPT (этот файл, как устроено) → MEMORY (что случилось, план).
> Это самостоятельный 2D-RPG на Python + Pygame, декомпилированный/вдохновлённый Pockie Ninja.
> Версия: **v176.0** (Stage 178 — 4 правки фидбека: семантика рейтингов —
> «Пробивание» = пробивание ЗАЩИТЫ, «А.Блок» = снижение БЛОКА ВРАГА; ЕДИНОЕ
> окно характеристик — игрок рендерится той же компактной схемой, что враг
> (ОЗ/МП → Атака/Скорость → 8 рейтингов 2 колонки голыми числами → Навыки),
> первичка/«Крит. урон» убраны у ОБОИХ, высота едина `CHAR_SHEET_H=380`
> (CHAR_SHEET_H_ENEMY удалена); ТУЛТИПЫ ФОРМУЛ — hover на строку рейтинга
> показывает панель (название → семантика → формула с фактическим значением;
> `STAT_TOOLTIPS` сверены с combat/formulas.py); scripts/extract_swf.py —
> обёртка FFDec `-export sprite` с автопроверкой качества кадров (6 чеков,
> детект выцветания) и обновлением MANIFEST — новые SWF добавляются одной
> командой, FFDec постоянно в `~/tools/ffdec`).
> Stage 177: тултипы предметов — строка
> «Продажа: N зол.» удалена (инвентарь + магазин), префикс редкости «[GRAY]…»
> удалён из шапки (инвентарь + лут) — остался только тип, цвет читается по
> рамке/иконке; чёрный самурай (role 10004) — ПОЛНАЯ ре-экстракция анимаций
> из новых SWF пользователя через FFDec 22.0.2 `-export sprite` (кадры в
> едином холсте экшена — старый сырой экспорт битмапов давал выцветшие
> полупрозрачные кадры): idle 7 / attack 13 / run 4 / death_fall 10 / hit 8,
> id действий = суффиксам SWF (999/52/55/57/64); окно характеристик в бою —
> АВАТАРЫ удалены у игрока и врага, у врага компактная схема (имя+«Ур.N» →
> ОЗ/МП → Атака/Скорость → 8 рейтингов 2 колонки голыми числами).
> Stage 174: Старейшина — кликабельный
> текст в центре города без аватара на карте (аватар в диалоге); ЕДИНОЕ окно
> NPC — 480px, динамическая высота 250..430, жёсткие секции ШАПКА|ЗАДАНИЕ|
> НАГРАДЫ, кнопки 28px, тот же стиль у стража Лас Ночеса (`_npc_window_*`);
> трекер — иконка «Т» в нижнем баре (плавающая кнопка удалена, бейдж активных)
> + ФИКС перехвата кликов стражем ЛН: `ClickRect.priority` + двухпроходный
> `_handle_click`; город — текстовые плашки 136×38 с подложкой, иконки 64px
> только при hover (fade 0.22с), хаотичные позиции `CITY_CARD_POSITIONS`.
> Stage 173: жаба — ре-экстракция
> кадров из шейпов SWF (голова в прыжке не обрезана, 121×168, sprite_h 154);
> трекер заданий прижат к правому нижнему углу (BOTTOM_MARGIN=66, тосты над
> панелью, Старейшина x→920); стрелка-подсветка цели после «Перейти» (5 с,
> над NPC или рядом мобов, гаснет по таймеру/локации); q4 «Победите самураев» —
> kill_mobs (goal_count=3, префикс samurai_*), хук в process_battle_rewards,
> счётчик «(2/3)» в трекере, сейв story_quests_kill_progress; Stage 172:
> сюжетные NPC и квесты (жаба на Локации 1, Старейшина в CITY, цепочка из
> 3 квестов, индикаторы «!»/«?», диалог, трекер). Stage 171: rolling saves ×3
> слота `player_save_slot_<n>.json` (архивация primary, цепочка загрузки,
> `load_from_slot` + F9); `validate_save` → `LAST_LOAD_REPORT` в F10;
> компакция generated_weapons/outfit_instances в to_dict-копиях
> (`synth_slots_provider`); троттлинг автосейва 5 с; Stage 170:
> посев global random из рендера арены убран, ESC-гантлет финализируется,
> 8 магических чисел → константы, звание tower_conqueror; Stage 169: 7
> копипаст-генераторов предметов заменены единым spec-driven `generate_item()`
> + `_GENERATOR_SPECS` (дифф-фаззинг 1050 кейсов), удалён мёртвый код;
> Stage 168: боевая математика в `combat/formulas.py` (config.py 2891→2263,
> ре-экспорты, дифф-фаззинг ~60k), кэши `_su_text`/`_static_surface` —
> MAP ×3.6; МУЛЬТИПЛЕЕР ИСКЛЮЧЕН; см. MEMORY.md).

---

## 0. TL;DR — что это за проект

Pockie RPG — single-player 2D пошаговая RPG-аркада в стиле Pockie Ninja/Ninja Wars.
Игрок управляет персонажем Ичиго (роль 1), ходит по карте локаций (CITY + 4 combat-локации + Лас Ночес — хаб Башни),
сражается с самураями/цветами в автобою, собирает шмот (7 слотов, 5 редкостей), точит её в Кузнице, вставляет камни (gems),
проходит 100-этажную Башню (Лас Ночес), бьёт Мирового Босса, выполняет дейлики, открывает 13 званий.

**Движок:** чистый Python 3.13 + Pygame. **Без веб-фреймворков, без БД** (только JSON save-файл).
**Архитектура:** 4 слоя (`config → data → combat → game → ui`) + миксины для UI.
**Размер:** 50 .py файлов, ~29,900 строк. Главный контроллер `ui/pygame_ui.py` (~3810 строк) наследует 17 миксинов.

---

## 1. Технологический стек

| Компонент | Технология | Назначение |
|---|---|---|
| Язык | Python 3.13+ | единственный язык (типы через `from __future__ import annotations` + dataclass slots) |
| Графика | Pygame (SDL2) | рендеринг, события, звук |
| Аудио | Pygame mixer | **отключён** (`SOUND_ENABLED = False`) — для dev |
| Сохранения | JSON (атомарная запись через `tempfile` + `os.replace`) | `data/player_save.json` + `.bak` + слоты ×3 (Stage 171) |
| Шрифт урона | `Ninja Naruto.ttf` (в `assets/fonts/`) | кастомный шрифт для цифр урона |
| Ассеты | PNG-спрайты (`assets/extracted/...`) | раскадровка SWF → N.png (1.png, 2.png, ...) |

**Сторонних веб-зависимостей нет.** Проект запускается одной командой:
```bash
python -m pockie_rpg.main
```
(или через entry_point `pockie-rpg` из `pyproject.toml`)

---

## 2. Архитектура — 4 слоя + config

```
        ┌──────────────────────────────────────┐
        │  ui/        (PygameUI + 14 mixins)    │  ← Layer D (UI, pygame)
        ├──────────────────────────────────────┤
        │  game/      (PlayerState, SaveManager)│  ← Layer C (game state, mutable)
        ├──────────────────────────────────────┤
        │  combat/    (Fighter, Fight, damage,   │  ← Layer B (combat, mutable)
        │              status_manager, events,   │
        │              skill_registry)           │
        ├──────────────────────────────────────┤
        │  data/      (Role, EnemyDef, item_db,  │  ← Layer A (data, frozen, stdlib only)
        │              tower_db, titles_db, ...) │
        ├──────────────────────────────────────┤
        │  config.py  (константы + данные;        │  ← Foundation (см. ниже:
        │             боевая математика → combat) │     ре-экспорты формул)
        └──────────────────────────────────────┘
```

### Layering rule (КРИТИЧНО)
- `config.py` — самый нижний слой. **Импортирует ТОЛЬКО stdlib И
  `combat.formulas`** (Stage 168: боевая математика живёт в formulas.py,
  config ре-экспортирует её имена В КОНЦЕ файла — обратная совместимость;
  formulas.py сам не импортирует ничего из pockie_rpg → цикла нет).
- `data/` — импортирует stdlib + `pockie_rpg.config` (lazy, внутри функций — иначе circular).
- `combat/` — импортирует `data/` + `config/` (боевые формулы — напрямую из
  `combat.formulas`).
- `game/` — импортирует `data/` + `config/` (не `combat/` — наоборот: `combat/fighter.py` импортирует `game.state` через `from_player_state`).
- `ui/` — импортирует всё.

**Циклических import'ов нет.** Если появляется circular — используй lazy import внутри функции (см. `damage.py:get_hit`).

---

## 3. Структура файлов (с LOC)

```
src/pockie_rpg/
├── config.py                    (2135)  UI/окна/данные-константы + TowerDB +
│                                       прогрессия/экономика (Stage 170: LEVEL_XP_CURVE,
│                                       ATK_TIME_*, GEM_*, TEST_START_*); боевая математика
│                                       ПЕРЕЕХАЛА в combat/formulas.py — в конце
│                                       файла блок ре-экспортов (Stage 168)
├── main.py                        (40)  entry point: pygame.init + PygameUI().run()
│
├── data/                                  Layer A — frozen dataclasses + datasets
│   ├── models.py                 (248)  Role, EnemyDef, Suit, CharacterStats
│   ├── roles_db.py               (173)  5 ролей (Ichigo + 4 самурая + Flower) + STARTER_SUITS + ENEMY_MOBS
│   ├── enemy_db.py               (206)  13 врагов (samurai_1..12, flower_1)
│   ├── item_db.py                (933)  EQUIPMENT_DB (42), OUTFITS_DB (4), GEMS_DB (5), generate_item() + _GENERATOR_SPECS (Stage 169 — 1 генератор вместо 7 копипаст-функций)
│   ├── tower_db.py               (369)  100 этажей + 10 боссов + TowerReward/Floor/Boss
│   ├── titles_db.py              (209)  13 званий (novice..legend, tower_conqueror — Stage 170)
│   ├── daily_quests.py            (76)  4 дейлика
│   ├── quests_db.py              (163)  Stage 172/173 — STORY_QUESTS (4 квеста: talk_to/use_item/kill_mobs), STORY_QUEST_CHAIN, chain_prerequisites_met
│   ├── npcs_db.py                 (91)  Stage 172-174 — NPCS: жаба (Локация 1, idle 121×168, sprite_h 154) + Старейшина (CITY, текстовая метка map_text/label_x/label_y = 640,560, giver квестов); аватары/реплики
│   └── worldmap_db.py            (130)  Stage 135 — WORLD_ZONES (35), ROUTE_MARKERS (26), ZONE_MARKER_INDEX, LOCATION_MIN_UNLOCK (из assets/worldmap/config.json)
│
├── combat/                                Layer B — mutable combat runtime
│   ├── formulas.py               (655)  Stage 168 (аудит 5.1) — БОЕВАЯ
│   │                                    МАТЕМАТИКА: рейтинги calc_*_rating,
│   │                                    hit chance, ШАГИ rating→%, пайплайн
│   │                                    урона apply_*_stage, BMV-хелперы,
│   │                                    growth-дефолты; только stdlib —
│   │                                    разрывает цикл combat→config
│   ├── events.py                 (191)  EventType(IntEnum), FightValue, FightSave
│   ├── fighter.py                (451)  Fighter @dataclass(slots) + from_role/from_player_state
│   ├── status_manager.py         (454)  StatusManager (freeze/poison/shield/cloud/extra_turn/burn)
│   ├── skill_registry.py         (284)  SKILL_REGISTRY (6 навыков) + SkillDef
│   ├── damage.py                 (426)  compute_attack, execute_skill, try_skill, apply_skill_effects
│   └── fight.py                  (469)  FightSystem.fight() — SPEED-LAW turn loop
│
├── game/                                   Layer C — persistent player state
│   ├── state.py                 (2404)  PlayerState (player progression, recalc_stats, rewards, сюжетные квесты Stage 172)
│   └── save_load.py              (~695)  SaveManager (debounce+троттлинг) + atomic JSON + rolling slots ×3 + validate_save
│
└── ui/                                     Layer D — Pygame rendering + input
    ├── pygame_ui.py             (3744)  PygameUI — главный контроллер, event loop, FSM, 16 mixins; Stage 170: _finalize_gauntlet_on_exit/_settle_gauntlet_rewards (ESC-гантлет)
    ├── animator.py               (255)  IdleAnimator + AttackSequence (фазы анимации) + ClickRect
    ├── assets.py                 (668)  AssetManager (LRU-кеш спрайтов, фреймов, иконок, фонтов)
    ├── effects.py                (430)  IceBlockEffect, EffectOverlay, CastEffect, ProjectileEffect
    ├── particles.py              (338)  ParticleSystem + DamageNumberSystem
    ├── tooltip.py                 (~130)  Stage 202: единая «панель у курсора» — TooltipLine/PanelStyle/render_tooltip_panel (cursor|anchor, перенос, флип у краёв); используют тултипы статусов (render_battle) и лута (render_quick_battle)
    ├── combat_replay.py         (1068)  CombatReplayMixin — реплей боя, тайминги, применение урона
    ├── render_battle.py         (1210)  BattleRendererMixin — экран боя (HUD, бойцы, оверлеи, endgame); Stage 202: _render_hud → 5 методов (оркестратор + _render_hud_player/_render_hud_enemy, возвращают якоря полосок + _render_hud_status_icons/_render_gauntlet_queue), тултип статуса через ui/tooltip.py
    ├── render_worldmap.py       (~560)  WorldMapRendererMixin — Stage 135: мировая карта (5 слоёв, хиттест, тултип)
    ├── scaling.py               (~285)  ScalableRendererMixin — Stage 152/153: _su/_su_font/_su_rect/_su_icon_size/_su_scaled/_su_image/_su_overlay + fade модалок; Stage 168 (аудит 5.2): _su_text (LRU-кэш отрисованного текста, кап 2048, НЕ мутировать) + _static_surface (draw-once кэш SRCALPHA-поверхностей)
    ├── render_map.py            (~910)  MapRendererMixin — MAP НАТИВНО (Hi-DPI, Stage 153) + bottom bar + enemy cards (клик по ВСЕЙ карточке открывает бой — Stage 167)
    ├── render_inventory.py     (~1795)  InventoryRendererMixin — инвентарь НАТИВНО (Hi-DPI, Stage 151), drag&drop; сетка 12×8, окно 491, кнопки 118, 10 вкладок (Stage 167; ITEMS_PER_PAGE=128 не урезать — визуальный гейт _can_visually_fit); заглушки (Stage 163); якоря-списки (Stage 164); тултип БЕЗ «Продажа»/«[RARITY]» (Stage 177)
    ├── render_synth.py           (~775)  Synth+WardrobeRendererMixin — синтез костюмов (400×248, 4 слота в ряд с ячейками 2 кол. × 3 ряда — Stage 167; слоты хранят item_id — физический перенос, возврат ПКМ/кликом; результат +N+1 остаётся в слоте результата, «(костюм +N)»/шанс под ним; тултипы слотов — Stage 166) + гардероб (480×484; 25 слотов = 5 страниц × 5 с пагинацией снизу, глобальный индекс страница×5+i — Stage 167); без затемнения (Stage 162)
    ├── render_forge.py          (922)  ForgeRendererMixin — Кузница НАТИВНО (Hi-DPI, Stage 152): заточка/камни/синтез
    ├── render_shop.py            (337)  ShopRendererMixin — магазин (тултип БЕЗ «Продажа» — Stage 177)
    ├── render_tower.py           (344)  TowerRendererMixin — Башня (100 этажей, shop, result)
    ├── render_world_boss.py      (224)  WorldBossRendererMixin — Мировой Босс на карте
    ├── render_las_noches.py      (350)  LasNochesRendererMixin — хаб Башни + диалоги NPC (Stage 174 — единый стиль окон `_npc_window_*`, динамическая высота)
    ├── render_quests.py          (907)  QuestRendererMixin — Stage 172-174: NPC на карте (спрайт/текст-метка/индикатор «!»/«?», анимация жабы, стрелка цели), ЕДИНОЕ окно NPC (динамическая высота, секции ШАПКА|ЗАДАНИЕ|НАГРАДЫ, кнопки 28px, хелперы `_npc_window_*`), трекер (2 вкладки, иконка в нижнем баре, «Перейти» по состоянию)
    ├── render_skills_charsheet.py(~660)  SkillsCharSheetRendererMixin — скиллы + char sheet (dual); Stage 178: ЕДИНОЕ окно у игрока и врага — компактная схема ОЗ/МП→Атака/Скорость→8 рейтингов 2 колонки, тултипы формул на hover рейтинга (`STAT_TOOLTIPS`, `_render_sheet_lines`), высота 380 у обоих
    ├── render_quick_battle.py    (~630)  QuickBattleRendererMixin — x1/x10/Анимация (карточки 112×138 приглушены, «плей» треугольником вместо битого глифа ⚔ — Stage 167) + loot grid
    ├── render_slot_machine.py    (~200)  SlotMachineRendererMixin — слот-машина v2 (окно 420×260, без текстов; до прокрутки — аватарки врагов _slot_idle_faces, Stage 167)
    ├── render_test_panel.py      (503)  TestPanelRendererMixin — F9 dev-панель
    ├── render_misc_modals.py     (364)  MiscModalsRendererMixin — звания, арена, дейлики
    └── test_battle.py            (481)  TestBattleMixin — F9 TEST_BATTLE state
```

---

## 4. Главное окно и FSM

### 4.1 Экран (1280×720, 60 FPS)
```
SCREEN_WIDTH=1280, SCREEN_HEIGHT=720, FPS=60
PLAYER_SPRITE_X=320 (25%), ENEMY_SPRITE_X=960 (75%)
SPRITE_BASE_Y=600 (линия земли)
BODY_SPRITE_W=130, BODY_SPRITE_H=135
HUD_HEIGHT=82 (верхняя панель)
```
**HUD боя (Stage 192-195):** HP_BAR_W=420 / MP_BAR_W=380 (MP уже, кончики
совпадают), полоски+имена сдвинуты к VS (HUD_BAR_CENTER_SHIFT=70).
ЗЕРКАЛЬНОЕ списание: у Ичиго остаток прижат к ПРАВОМУ (центро-обращённому)
краю (mirrored=True), у врага — к ЛЕВОМУ (mirrored=False); направление
градиента — отдельный флаг gradient_mirrored (кончик тёплый всегда у центра).
Градиенты: HP красный→жёлтый, MP синий→голубой (BAR_GRADIENTS-пары в
config); белый догоняющий сегмент (BAR_GHOST_LERP_SPEED=2.5). Иконки
статусов — от кончика полоски к аватару (Ичиго: под правым краем, рост
влево; враг: под левым, рост вправо), тень 2px, мини-счётчик ходов
(duration>1), тултип при наведении (STATUS_TOOLTIPS в config).

### 4.2 FSM `GameState(IntEnum)` — всего 3 состояния
```python
class GameState(IntEnum):
    MAP         = 1   # карта/хаб/локации + все модалки
    BATTLE      = 2   # бой (countdown → replay → endgame)
    TEST_BATTLE  = 3   # F9 dev-режим
```

**ВСЕ экраны (SHOP, FORGE, INVENTORY, TOWER, WORLD_BOSS, LAS_NOCHES, SKILLS, CHARSHEET, TITLES, DAILY_QUEST, TEST_PANEL, SLOT_MACHINE, WORLDMAP)** — это **модальные boolean-флаги внутри `GameState.MAP`**:
`_shop_modal_open`, `_forge_modal_open`, `_inventory_modal_open`, `_tower_modal_open`, `_skills_modal_open`, `_char_sheet_open`, `_char_sheet2_open`, `_titles_modal_open`, `_daily_quest_modal_open`, `_test_panel_open`, `_arena_active`, `_las_noches_dialog`, `_quick_battle_modal_open`, `_slot_machine_modal_open`, `_endgame_active`, `_worldmap_modal_open` (Stage 135), `_synth_modal_open` + `_wardrobe_modal_open` (Stage 138), `_quest_dialog_npc` (Stage 172 — диалог сюжетного NPC, хранит npc_id или None).

### 4.3 Под-флаги
- `_battle_mode: BattleMode` (Stage 134 — IntEnum в config: NORMAL / TOWER / WORLD_BOSS / SLOT_GAUNTLET,
  был строкой) — определяет flow endgame (Tower скипает стандартный endgame → `_finish_tower_battle`).
- `_map_location ∈ MapLocation {CITY=0, LOC1=1, LOC2=2, LOC3=3, LOC4=4, LAS_NOCHES=5}` — текущая локация карты.

### 4.4 Переходы
```
MAP ──_enter_battle()──────────▶ BATTLE  (countdown → replay → endgame → OK → MAP)
MAP ──_enter_tower_battle(floor)▶ BATTLE  (mode="tower"; endgame → _finish_tower_battle → LAS_NOCHES + tower_result)
MAP ──_enter_world_boss_fight()▶ MAP (mode="world_boss"; _endgame_active=True, instant)
MAP ──_enter_test_battle()─────▶ TEST_BATTLE  (F9 из карточки моба)
BATTLE/TEST_BATTLE ──_exit_*()──▶ MAP (или LAS_NOCHES если Tower)
```

### 4.5 ESC cascade (приоритет закрытия модалок, Stage 133 — полный; Stage 135 — +worldmap)
```
TestPanel → WorldMap → Quest NPC dialog (Stage 172) → Las Noches dialog →
Tower result → Slot result → Daily Quest → Tower Shop → Tower modal →
Slot machine → Quick Battle modal → Quick Battle result → Titles → Shop →
Forge → Inventory → Char sheet 2 → Char sheet 1 → Skills modal →
_exit_battle → _exit_test_battle → quit
```
При добавлении новой модалки — **вставь её в эту цепочку** в `pygame_ui._handle_keydown`.

---

## 5. Поток боя (от старта до endgame)

### 5.1 Старт
1. `_enter_battle()` / `_enter_tower_battle(floor)` строит `Fighter.from_player_state(player, role)` + `Fighter.from_role(role, level, hp_mul, atk_mul)`.
2. Создаёт `IdleAnimator` для обоих бойцов (загружает `idle` спрайты).
3. Сбрасывает все battle-поля (HP/MP display, particles, overlays, countdown, endgame).
4. `self.state = GameState.BATTLE`, `_countdown_active = True`.
5. `_update_countdown(dt)` проигрывает `COUNTDOWN_PHASES` (~3.8s).
6. По завершении → `_start_combat_replay()`.

### 5.2 Replay start
```python
fight = FightSystem(player_fighter, enemy_fighter)
self._combat_replay = fight.fight()   # → FightSave (event log)
```
`FightSave.values` — список `FightValue`-событий (EventType.BEGIN_ATTACK, ATTACK, CANT_MOVE, FREEZE_EXPIRED, DIE, END_ATTACK, CLOUD_STRIKE, POISON_DAMAGE, SHIELD_APPLIED, EXTRA_TURN_ATTACK).

### 5.3 Per-frame update (`_update_battle(dt)`)
1. Анимировать idle-фреймы обоих бойцов.
2. Если `_active_attack_seq` активен → `_update_attack_sequence(dt)` + **early return** (анимация должна закончиться перед следующим событием). Stage 189 — на этом пути работает `_update_battle_watchdog(dt)`: таймер реплея в это время ЗАМОРОЖЕН, задержки EVENT_DELAY_* отсчитываются ПОСЛЕ анимации.
3. Иначе: апдейтить hit-таймеры, HP/MP lerp, particles, damage numbers, все effect overlays, cast effect, projectile.
4. `_update_combat_replay(dt)` — если `_replay_timer >= event_delay` → `_process_combat_event(fv)` + `_replay_event_idx += 1`.
5. Stage 189 — страж зависания: если бой жив, endgame не начался, а прогресса (смена event_idx/фазы seq) нет дольше `BATTLE_WATCHDOG_TIMEOUT=45с` игровых секунд → рапорт `[WATCHDOG] …` в `_combat_debug_lines` (F10/F12, кэп 6). Ничего не чинит — только сигнализирует.

### 5.4 Event processing (`_process_combat_event(fv)`)
| EventType | Действие |
|---|---|
| `BEGIN_ATTACK` | run turn-start DoTs (poison/burn/cloud), peek следующего ATTACK для damage/crit/skill, `_start_attack_sequence`, log |
| `ATTACK` | apply MP cost, apply damage если нет активной seq, freeze shatter, apply statuses (freeze/poison/shield/cloud/extra_turn) |
| `CANT_MOVE` | `can_move=0`, `frozen_duration`; activate/deactivate ice overlay по `is_frozen` |
| `FREEZE_EXPIRED` | deactivate ice overlay, `status.remove("freeze")` |
| `DIE` | death animation на animator, deactivate все оверлеи этого бойца, cancel attack seq |
| `END_ATTACK` | `on_turn_end()` (MP НЕ синхронизируется — регена нет с Stage 133) |
| `CLOUD_STRIKE` / `POISON_DAMAGE` | apply DoT damage + spawn damage number + log |
| `SHIELD_APPLIED` / `EXTRA_TURN_ATTACK` | log + status remove |

### 5.5 AttackSequence фазы (animator.py)
```
DONE → RUN_FORWARD → PAUSE (Stage 97) → ATTACK → RUN_BACK → DONE
                                              └─→ HOLD → DONE (смертельный удар)
```
- **RUN_FORWARD** (`ATTACK_SEQ_RUN_FORWARD_DURATION`): спрайт бежит `base_x → reach_x`, action=`run`.
- **PAUSE** (`ATTACK_SEQ_PAUSE_DURATION`): спрайт стоит на `reach_x` (драматическая пауза).
- **ATTACK** (`ATTACK_SEQ_ATTACK_DURATION`): спрайт на `strike_x`, action=`attack`. На `progress >= 0.5` (midpoint) → `_apply_attack_damage(seq)` — **здесь спавнятся частицы, damage number, применяется урон/статусы**. Урон принимается через `Fighter.take_log_damage` (Stage 188 — pending_damage уже после щита движка).
- **RUN_BACK** (`ATTACK_SEQ_RUN_BACK_DURATION`): спрайт бежит обратно `strike_x → base_x`, flip toggled. Stage 188 — обработчик был УТРАЧЕН (бой замирал после 1-й атаки), восстановлен.
- **HOLD** («стойка победителя», Stage 188): после СМЕРТЕЛЬНОГО удара seq замирает на `strike_x` на `ATTACK_SEQ_HOLD_ENDGAME_DELAY=0.9с`, затем сама вызывает `_start_endgame()`.
- **DONE**: return to idle. КАЖДАЯ фаза обязана иметь ветку в `_update_attack_sequence` — бесхвостая фаза = тупик реплея (early return по `is_done()`), ловит `scripts/diag_replay_flow.py`.

**Ranged skills** (`is_ranged==1`): `reach_x = strike_x = base_x`, фаза стартует сразу с `ATTACK`. Урон применяется после того, как `_projectile_effect.active` станет False (снаряд долетел).

**Синхронизация зеркала с движком (Stage 188/190):** `FightSystem.fight()` исполняется целиком ДО реплея; реплей играет `FightSave` и держит зеркало бойцов синхронным: DoT-тик в BEGIN_ATTACK — «сухой» (`on_turn_start(..., apply_damage=False)`, урон несёт POISON_DAMAGE/CLOUD_STRIKE-событие лога); урон из лога — через `take_log_damage` (fv.damage уже после щита движка; вызывается и при damage=0 — полное поглощение щитом); статусы скилла применяет владелец ATTACK-события — seq (`_seq_applied_event_idx == _replay_event_idx`, проставляется в `_start_attack_sequence`) ИЛИ фолбэк-обработчик события (self-buff'ы без seq, например Купол). Полное поглощение щитом даёт в логе «щит поглотил удар …» + плашку «Щит поглотил N!» над защитником.

### 5.6 Endgame (`_start_endgame` → `_update_endgame`)
- `_endgame_phase = "text"`: пульсирующий большой текст "Победа"/"Поражение" (~2s).
- → `_apply_endgame_rewards()`: вызывает `player.process_battle_rewards(...)` → dict с xp/gold/leveled_up/gems/equipment_drop.
- → `_endgame_phase = "rewards"`: окно с XP/золотом/level-up + **Loot Grid** (5-кол, 48px слоты с rarity-фоном + иконка + count badge + tooltip).
- Player click OK → `_endgame_phase = "done"`, `_endgame_active = False`, `save_mgr.mark_dirty()`, `_exit_battle()`.

**Tower mode** скипает стандартный endgame → `_finish_tower_battle` → `_exit_battle` → `_tower_result` modal.
**World Boss** — instant flow (без анимации), `_enter_world_boss_fight` сразу ставит `_endgame_active=True`.

---

## 6. Combat-движок — ВСЕ формулы

### 6.1 Базовая атака (`damage.compute_attack`)
```python
base_dmg = rand_int(attacker.min_atk, attacker.max_atk)  # inclusive
hit_chance = combat_hit_chance(attacker.hit_rating, target.dodge_rating)  # %
if rand_int(1, 100) > hit_chance:  # Stage 88: 1..100, не 0..100
    return miss
dmg, is_crit = apply_crit_stage(base_dmg, attacker.crit_rating, target.tough_rating)
dmg = apply_defense_stage(dmg, target.defense)        # Stage 133 — ЗАЩИТА (hyperbolic)
dmg, is_block = apply_block_stage(dmg, target.block_rating, attacker.pierce_rating)
dmg = apply_pierce_stage(dmg, attacker.pierce_rating)
dmg, freeze_consumed = _apply_freeze_amplification(target, dmg)  # если freeze с multiplier
target.take_damage(dmg)
```

### 6.2 Hit chance (linear, capped)
```python
# config.combat_hit_chance(attacker_hit_rating, defender_dodge_rating)
hit_pct = attacker_hit_rating * 0.0625      # ШАГ_А
dodge_pct = defender_dodge_rating * 0.0625
final = 100 - (dodge_pct - hit_pct)
return max(5, min(100, int(final)))           # caps [5, 100]
```
- `BASE_HIT_CHANCE=100`, `HIT_FLOOR_PCT=5`, `HIT_CAP_PCT=100`.
- **Важно:** `attacker.hit_chance` и `target.dodge_chance` — это RATINGS (int, uncapped), НЕ проценты. `800` = `50%`.

### 6.3 Crit stage (Stage 104 — linear difference)
```python
crit_chance = attacker.crit_rating * 0.0625 - defender.tough_rating * 0.0625
if crit_chance <= 0 or roll(1..100) > crit_chance:
    return base_damage, is_crit=False
crit_dmg_pct = attacker.crit_rating * 0.125 - defender.tough_rating * 0.125  # ШАГ_Б
total_crit_pct = 150 + crit_dmg_pct   # CRIT_BASE_DAMAGE_PCT=150
return int(base_damage * total_crit_pct / 100), is_crit=True
```

### 6.3.1 Defense stage (Stage 137 — ОРИГИНАЛ: Защита vs Пробивание защиты)
```python
# config.apply_defense_stage(dmg, defender_defense, attacker_defense_break)
# DEFENSE_BREAK_CONSTANT = 1354 — один K на ОБА стата (зеркальная пара)
mitigation_def = def / (def + 1354)        # верифицировано: 1604 → 54.23%
defbreak_pct   = break / (break + 1354)    # верифицировано: 2072 → 60.48%
mitigation = mitigation_def - defbreak_pct # ВЫЧИТАНИЕ процентов (вики §5)
if mitigation <= 0: return dmg             # break > def → урон без усиления
return int(dmg * (1 - mitigation))
```
- Порядок пайплайна Stage 137: **Crit → ЗАЩИТА(def−break) → Block(block−antiblock)** — 3 стадии.
- Пара гасится в ноль при def = break (ровно ×1.0). Применяется к ОБОИМ (мобы и игрок).
- КАПОВ НЕТ: рейтинги 5000/10000+ валидны (overcap разрешён всюду).

### 6.4 Block stage (Stage 137 — Блок vs Антиблок, оба /16)
```python
# config.apply_block_stage(dmg, defender_block, attacker_antiblock, roll)
block_chance = block_rating * 0.0625 - antiblock_rating * 0.0625  # оба /16
if block_chance <= 0 or roll > block_chance:
    return dmg, False
return int(dmg * 0.60), True   # BLOCK_DAMAGE_MULTIPLIER=0.60 (-40%)
```
- `antiblock_rating` — НОВЫЙ стат Stage 137 (flat с гира; ключи `antiblock_rating`/`antiblock_pct`).
- Антиблок > блока → блок полностью снят (отрицательный шанс = 0%).

### 6.5 Pierce stage (Stage 137 — УДАЛЁН из пайплайна)
- Старый «pierce-множитель урона» `×(1+pierce%/100)` — НЕ оригинал; удалён из пайплайна.
- `pierce_rating` теперь = **Пробивание защиты**: гипербола pierce/(pierce+1354), вычитается из mitigation ВНУТРИ apply_defense_stage (см. 6.3.1). `apply_pierce_stage`/`PIERCE_STEP=0.072` — legacy, не вызываются.

### 6.6 Шаги конвертации rating → % (Stage 104/137)
| Константа | Значение | Назначение |
|---|---|---|
| `RATING_PCT_STEP` / `CRIT_CHANCE_STEP` | 0.0625 (1/16) | hit/dodge/crit-chance/tough-reduction/block/АНТИБЛОК (вики: +1% за 16 очков) |
| `CRIT_DAMAGE_STEP` | 0.125 (1/8) | crit-damage-bonus / tough-damage-reduction |
| `DEFENSE_BREAK_CONSTANT` | 1354 | гипербола пары Защита/Пробивание защиты (оба стата) |
| `PIERCE_STEP` | 0.072 | LEGACY (не вызывается с Stage 137) |
| `CRIT_BASE_DAMAGE_PCT` | 150 | базовый крит = 150% урона |
| `BLOCK_DAMAGE_MULTIPLIER` | 0.60 | блок = 60% урона |
| `EVENT_DELAY_ATTACK` | 0.2 | Stage 189 — бит ПОСЛЕ seq до бухгалтерии (раньше 1.5; таймер заморожен во время seq) |
| `BATTLE_WATCHDOG_TIMEOUT` | 45.0 | Stage 189 — порог стража зависания реплея (игровые секунды без прогресса) |

### 6.7 Primary stat → rating (в `recalc_stats`)
```python
# Linear floor-division, NO CAP
Dodge_Rating = floor(AGI / bmv_price_agi) + flat_gear_dodge
Hit_Rating   = max(0, floor(STR / bmv_price_str) + flat_gear_hit - STR_THRESHOLD_FOR_HIT)  # =150
Tough_Rating = floor(STR/bmv_price_str) + floor(STA/bmv_price_sta) + flat_gear_tough
Crit_Rating  = flat_gear_crit + flat_gem_crit   # STR НЕ участвует!
Block_Rating = floor(STR / bmv_price_str) + flat_gear_block
Pierce_Rating = max(0, flat_gear_pierce)       # только gear (no stats)
Antiblock_Rating = flat_gear_antiblock         # Stage 137 — только gear
Speed = 1.0 + (AGI/bmv_price_agi + gear_speed) / 100.0  # linear, no cap (cap=10.0 в fight.py AP_CAP)
```

### 6.8 BMV-Цена / BMV-Прирост (Stage 103)
- **BMV-Цена** (`bmv_price` в outfit) — сколько стат-единиц даёт 1 rating. **Меньше = эффективнее.**
  - suit_ichigo: STR=30, AGI=10, STA=20 → Ichigo AGI-зависимый (AGI даёт много dodge).
- **BMV-Прирост** (`growth` в outfit) — прирост за уровень: `{current, max}`. UI: "Ловкость 41 (+1.35) | Макс (+1.65)".
- `DEFAULT_BMV_PRICE_STR/AGI/STA = 20` — для мобов/без outfit.
- `DEFAULT_GROWTH_STR/AGI/STA = 0.3/0.4/0.25` — fallback.

### 6.9 Базовые формулы (CharacterStats docstring)
```python
min_atk = 10 + STR*5 + gear_min + gem_min_atk
max_atk = (min_atk_no_gear * 1.5) + gear_max + 0   # NOTE: НЕТ gem_max (по design)
max_hp  = 100 + STA*20 + gear_hp + gem_max_hp
defense = 5 + STA*2 + gear_def + gem_def
max_mp  = base_max_mp + gear_mp
parry_chance = min(50, 0 + AGI*0.4 + gear_parry)   # legacy, capped 50
crit_chance_legacy = min(75, 5 + STR*0.3 + gear_crit)   # UI display only
crit_mul = min(2.50, 1.50 + STR * 0.01)   # Stage 52 crit multiplier (отдельная система!)
```

### 6.10 Speed-law turn loop (Stage 120/121, `fight.py`)
```
1. OUTER TICK: fighter0.AP += fighter0.speed; fighter1.AP += fighter1.speed
2. AP_CAP = 10.0 (hardcoded в fight() — флаг для centralization)
3. INNER LOOP: пока хотя бы один боец AP >= 1.0:
   a. attacker = fighter с наибольшим AP (tie-break — большая base speed)
    b. DoT tick (on_turn_start) — poison/burn/cloud тикают ДАЖЕ ЕСЛИ frozen
    c. if !can_act (freeze/stun/paralyze) → CANT_MOVE, on_turn_end,
       AP -= 1.0 (Stage 191 — пропуск СПИСЫВАЕТ очко действия: контроль
       стоит темпа; при равных скоростях между пропусками влезает ход
       соперника — удар по замороженному разбивает глыбу ×2),
       _global_freeze_decrement(), continue
    d. _try_skills() → если скилл сработал, emit FightValue + follow-ups
       else compute_attack()
    e. if defender died → DIE, break
    f. attacker.on_turn_end()
    g. AP -= 1.0
    h. if extra_turn → AP += 1.0 (net zero → ещё один ход в этом tick)
    i. (Stage 133 — MP regen УДАЛЕН: никто не регенит MP в бою)
    j. _global_freeze_decrement()  # оба бойца: freeze duration -= 1
       (just_applied защищает ход наложения)
4. Safety: if ticks_this_bout == 0 → bout += 1 (anti-infinite-loop)
5. После MAX_BOUT=60 → draw
```

### 6.11 Status effects (`status_manager.py`)
| Статус | Применение | Эффект | Tick |
|---|---|---|---|
| `freeze` | Crystal Blade (skill 12006) | can_act=False, damage_taken×2.0 (amplification) | `_global_freeze_decrement` оба бойца |
| `poison` | Poison Dart (skill 18003) | DoT = `int(max_hp * 0.05)` (5% max HP) за ход, 4 хода | on_turn_start (даже если frozen) |
| `burn` | (нет навыка) | DoT = `int(params["dmg_per_turn"])` | on_turn_start |
| `thunder_cloud` | Thunderstorm (skill 14001) | DoT = `int(rand(caster.min_atk, caster.max_atk) * 0.6)`, 50% миграция к оппоненту | on_turn_start, decremented отдельно |
| `shield` | Crystal Shield (skill 14002) | поглощает урон: `absorbed = min(dmg, amount); dmg -= absorbed; amount -= absorbed`. **Стэкается** (existing + new). | on_turn_end (NO_END_DECREMENT_STATUSES исключает freeze/shield/cloud/extra_turn) |
| `extra_turn` | Lightning Step (skill 15005) | после хода → AP += 1.0 (net zero → доп. ход) | consume_extra_turn |
| `stun` / `paralyze` | (нет навыка) | can_act=False | как freeze |

**`just_applied` flag (Stage 126):** при первом `decrement_freeze_durations()` флаг сбрасывается в False, длительность НЕ декрементируется. Это фиксит "freeze срабатывает на тот же ход, что применён".

**Контроль и темп (Stage 191):** пропущенный (замороженный/станнутый) ход списывает AP наравне с обычным. При равных скоростях цикл глыбы: наложение → пропуск жертвы (глыба 2→1) → ход атакующего (**удар по замороженному = шаттер: урон ×2, «Глыба разрушена!»**) → если не разбил — глыба спадает по таймеру (1→0 в конце его хода) → жертва ходит. При скорости жертвы ×2 оба пропуска идут подряд.

### 6.12 Навыки (`skill_registry.SKILL_REGISTRY` — 6 штук)
| skill_id | Имя | MP | trigger | dmg_mult | on_hit | is_ranged | is_self_buff |
|---:|---|---:|---:|---:|---|---|---|
| 12006 | Кристальный клинок (Crystal Blade) | 35 | 0.15 | 0.0 | freeze{chance:1.0, duration:2, dmg_mult:2.0} | False | False |
| 15005 | Шаг молнии (Lightning Step) | 40 | 0.10 | 1.0 | extra_turn{chance:1.0, duration:1} | False | False |
| 10001 | Огненный шар (Fireball) | 35 | 0.15 | 1.6 | {} (pure damage) | True | False |
| 14001 | Грозовая туча (Thunderstorm) | 55 | 0.10 | 0.6 | thunder_cloud{chance:1.0, dur:2-4, cloud_mult:0.6} | False | False |
| 18003 | Яд (Poison Dart) | 25 | 0.15 | 1.0 | poison{chance:0.70, duration:4, dmg_pct_max_hp:0.05} | False | False |
| 14002 | Купол (Crystal Shield) | 40 | 0.10 | 0.0 | shield{chance:1.0, amount:300, duration:4} | False | True |

Все 6 навыков привязаны к роли Ichigo (`role_id=1`). `ROLES[1].skills = (12006, 15005, 10001, 14001, 18003, 14002)`.

---

## 7. Прогрессия игрока

### 7.1 Уровни
- `MAX_LEVEL = 80`.
- XP-кривая: `max_xp = level * 100` (linear, в `PlayerState.gain_xp`).
- Level-up: `level += 1`, накопить `growth_*` в float-аккумуляторах, `strength = int(_str_accum)` (сохраняет дробный прирост), `max_mp += 10` (LEVEL_UP_MP), bonus HP `+50/level` (LEVEL_UP_HP).
- Level-up growth берётся из outfit.growth (BMV-Прирост).

### 7.2 Экипировка — 7 слотов
| slot_key | RU название | Главные статы | Примеры ID |
|---|---|---|---|
| `weapon` | Оружие | min_atk, max_atk | weapon_wooden (L1), weapon_blunt2..6 (L5/10/15/20/25) |
| `head` | Голова | defense, max_hp | headband_ninja, head_helm2..6 |
| `body` | Броня | defense, max_hp | vest_ninja, body_cloth2..6 |
| `hands` | Перчатки | defense, hit_rating | gloves_leather, gloves_mitten2..6 |
| `belt` | Пояс | defense, tough_rating | belt_fabric, belt_jade2..6 |
| `boots` | Обувь | defense, speed | boots_shinobi, boots_shoes2..6 |
| `accessory` | Аксессуар | crit_rating, pierce_rating | amulet_clan, ring_jade2..6 |
| `outfit` | Костюм | (base_stats + bmv_price + growth) | suit_ichigo, suit_samurai_tank, suit_ninja_evasion, suit_ogre_brute |

### 7.3 Редкости (5 уровней)
| Rarity | # доп. статов | RGB | Drop rate | Sell × |
|---|---:|---|---:|---:|
| Grey | 0 | (150,150,150) | 60% | ×1 |
| Blue | 1 | (60,120,220) | 25% | ×2 |
| Purple | 2 | (167,139,250) | 10% | ×4 |
| Gold | 3 | (234,179,8) | 4% | ×8 |
| Red | 4 | (220,60,60) | 1% | ×16 |

### 7.4 Тир-прогрессия
- `WEAPON_LEVELS = (1, 5, 10, 15, 20, 25)` — канонические уровни предметов.
- Суффикс ID `*2..6` ↔ уровни `5, 10, 15, 20, 25`. Нет T7+.
- `scale_gear_stat(base, item_level) = base * (1 + (item_level - 1) * 0.15)` — +15%/уровень.

### 7.5 Forge (Кузница, Stage 47/115)
- `MAX_ENCHANT = 20`.
- `get_enchant_cost(current_level) = 100 * (current_level + 1) ** 1.15`. Примеры: 0→1=100, 5→6=843, 19→20=3257.
- `get_enchanted_stat(base, enchant_level) = int(base * (1 + enchant_level * 0.05))` — +5% за уровень (Stage 115: было +50%).
- 3 таба: Enchant (точить gear), Gems (вставить/вынуть/апгрейд), Synthesis (склеить 2 гема).

### 7.6 Gems (Stage 51)
- `MAX_GEM_LEVEL = 10`, `MAX_GEM_SLOTS_PER_ITEM = 3`.
- 5 типов: red (STR), blue (defense, **triangular** growth), green (AGI), yellow (STA), orange (crit_rating).
- `get_gem_stat_bonus(type, level)`:
  - red/green/yellow/orange: `3 + level * 2` (linear).
  - blue: `50 * level * (level + 1) // 2` (triangular: L1=50, L2=150, L3=300...).
- Upgrade: `cost = 50 * level ** 1.3`, `chance = max(10, 100 - (level-1)*10)`.
- Synthesis: 2 гема одного уровня → 1 гем level+1, **40% failure** (60% success), оба гема consumируются.

### 7.7 Loot / Drops (Stage 119)
```python
# Mob drop table (MOB_DROP_TABLES[location_id] — только Loc1 определена!)
equipment_chance = 30   # % за победу
type_weights = {weapon:4, armor:3, boots:2, ring:1, gloves:1, belt:1, head:1}
rarity_chances = {Grey:60, Blue:25, Purple:13, Gold:2}   # нет Red в drops
levels = [1, 5]
# Max 1 equip за бой (Stage 119 fix). Gem drop — отдельный 10% roll.
```

### 7.8 Tower (Башня, Stage 89/90 — Лас Ночес)
- `TOWER_MAX_FLOOR = 100`. Boss-этажи: 10, 20, ..., 100 (10 боссов).
- **Нет лимита попыток** (Stage 90 убрал; legacy поля `tower_attempts=3` и `tower_next_attempt_ts` мёртвые).
- Floor HP/atk: `hp_mul = 1 + (bracket_pos-1) * 0.08`, `atk_mul = 1 + (bracket_pos-1) * 0.05` (bracket = позиция в десятке).
- Boss HP/atk: `hp_mul = 1 + (floor//10) * 0.5` (+50% за 10 этажей), `atk_mul = 1 + (floor//10) * 0.3`.
- Rewards (normal floor): `gold = 20 + floor*3`, `shards = 10 + floor//3`, `xp = 30 + floor*5`.
- Boss-100 (`tower_conqueror` title) — **title_id не существует в titles_db** (forward-reference / unimplemented).
- Hub: CITY → Tower card → LAS_NOCHES → guardian NPC → welcome dialog → shop_offer → Tower modal.

### 7.9 World Boss (Stage 71/72)
- `WORLD_BOSS_MAX_HP = 50000`, 3 попытки в день.
- `WORLD_BOSS_BASE_DODGE = 0` → игрок всегда попадает.
- Ranks: F(0) / B(500) / A(1500) / S(3000) / SS(5000) / SSS(10000) — по суммарному урону.
- Rewards: F=50 / B=200 / A=500 / S=1000 / SS=2500 / SSS=5000 золота.

### 7.10 Titles (Stage 70) — 12 званий
novice(t1) → apprentice(2) → warrior(3) → hunter(4) → defender(5) → berserker(6) → assassin(7) → monk(8) → ronin(9) → shadow_master(10) → warlord(11) → legend(12).
Активное звание (одно) даёт flat-бонусы к статам (`stats` dict). Бонусы суммируются в `get_gear_bonuses()`.

### 7.11 Daily Quests (Stage 95) — 4 штуки
kill_mobs(30 → 500g/300xp), tower_floors(5 → 800g/500xp/50shards), world_boss(3 → 1200g/800xp/100shards), arena_fights(10 → 2000g/1200xp/200shards). Сброс ежедневно.


### 7.12 Слот-машина «3 лица → бой» (Stage 133 + v2 в Stage 134, Локация 1)
- Карточка на карте Локации 1 — 120×72 в ЛЕВОМ ВЕРХНЕМ углу зоны (`SLOT_CARD_X/Y=16/100`, под top-панелью,
  левее ряда карточек мобов); локации 2/3/4 — вне скоупа. Модалка `_slot_machine_modal_open` (RULE 10).
- Константы в config: `SLOT_MACHINE_POOL` (mob_1, mob_2, mob_3, flower_1), `SLOT_MACHINE_FACES=3`,
  `SLOT_MACHINE_COOLDOWN_SEC=60` — все с маркером «TODO balance».
- **Спин-анимация (Stage 134):** барабан i стопится в момент `SPIN_SEC + i*STOP_STAGGER` (1.2с + 0.4с × i,
  итог ~2.0с); до стопа перелистывает случайные лица каждые `SPIN_TICK=0.08`, в последние
  `SPIN_SLOWDOWN_SEC=0.3` тик удваивается (доводка). Кулдаун стартует в момент НАЖАТИЯ (`slot_next_roll_ts`);
  `_slot_rolled=True` ставится по завершении анимации → кнопка «В бой!». Во время спина кнопка заблокирована.
- **История (Stage 134) — УДАЛЕНА (Stage 163):** `player.slot_history` и константы
  `SLOT_MACHINE_HISTORY_MAX/SHOWN` удалены (поле/сейв/загрузка/запись); ключ
  `slot_history` в старых сейвах игнорируется. В модалке секции «История» нет.
- **Бонус за 3/3 (Stage 134):** `SLOT_MACHINE_PERFECT_GOLD_MULT=1.5` — золото ×1.5 (ceil, в пользу игрока);
  в результат-модалке пометка «Бонус ×1.5 за 3/3!».
- «В бой!» → 3 ПОСЛЕДОВАТЕЛЬНЫХ 1v1-боя через штатный FightSystem (`_battle_mode=BattleMode.SLOT_GAUNTLET`).
  HP/MP игрока переносятся между раундами (`fighter.hp/mp` перезаписываются из `_gauntlet_hp/_gauntlet_mp`),
  БЕЗ регена и БЕЗ восстановления. Движок строго 1v1 — мульти-боя нет.
- **Очередь врагов в HUD (Stage 134):** при `_gauntlet_active` под дебаффами врага рендерится очередь
  (лица 44px, right-aligned к `SCREEN_WIDTH-16`): прошедшие раунды — затемнённые + серый бордер,
  активный — скрыт (он и так главный аватар), будущие — обычные с подписью «далее».
- Умер в раунде N → гантлет завершён, награда за побеждённых до N.
- Награда: `gold_reward` + `xp_reward` за каждого побеждённого + `record_defeat`. НЕ вызывает
  `process_battle_rewards` (никаких дропов шмота/гемов — не размывать баланс Локации 1).
- **Синк HP/MP (Stage 134):** при финале гантлета `player.current_hp/mp` = остатку бойца (кламп 1/0);
  фулл-хил `_exit_battle` для SLOT_GAUNTLET ПРОПУСКАЕТСЯ. Для обычных боёв фулл-хил (`_apply_endgame_rewards`)
  теперь использует `player.stats.max_hp/max_mp` (был базовый `ROLES[].max_hp` без шмота/уровня).
- Конец → `_slot_result` модалка на MAP (лица ✓/✗, золото, опыт, level-up) + `_exit_battle`.

---

## 7.13 Мировая карта «Sakura of mainland» (Stage 135-136, v136.0)

- **Данные (Layer A):** `data/worldmap_db.py` — грузит `assets/worldmap/config.json` один раз: `WORLD_ZONES` (35 frozen `WorldZone`), `ROUTE_MARKERS` (26 frozen `RouteMarker`), `WORLD_MAP_SIZE=(768,426)`, `OVERLAY_OFFSET=(31,48)`, `ZONE_MARKER_INDEX` (строгая привязка zoneId → индекс маркера), `LOCATION_MIN_UNLOCK` (производная: LOC1≥6, LOC2≥16, LOC3≥26, LOC4≥36). Константы рендера — `WORLDMAP_*` + `ZONE_LOCATION_MAP` + `WORLDMAP_LOCATION_ZONE` в config.py.
- **Маппинг зон → локации** (config.ZONE_LOCATION_MAP, 27 не-деревень; деревни → CITY=0): unlock 1-11 → LOC1, 16-21 → LOC2, 26-31 → LOC3, 36-50 → LOC4 (полная таблица — комментарий в config.py).
- **UI (Layer D):** `ui/render_worldmap.py` — `WorldMapRendererMixin`, флаг `_worldmap_modal_open` (ПРАВИЛО 9). Панель: оригинальный размер 768×426 × `WORLDMAP_SCALE=1.0` (Stage 136; было 1.4; Stage 161 — подтверждено) по центру; подсказка внизу панели удалена (Stage 161); хиттест: `map_x=(mx-panel_x)/SCALE`; маски `pygame.mask.from_surface(b{id}_hit.png, 127)`, меньшая зона побеждает.
- **6 слоёв (Stage 136):** фон → платформы (up/over; неактивные — обесцвеченный up: gray=0.30R+0.59G+0.11B, V=gray*0.5+8, кэш по zone_id) → overlay.png (blit СО СДВИГОМ `panel+OVERLAY_OFFSET(31,48)`, БЕЗ растяжения при SCALE=1.0; НЕ обесцвечивается — bbox-перекрытия портили активные зоны) → маркеры → 🔒-бейджи (примитивы, НЕ эмодзи) → метка игрока (emerald-пульс 52,211,153 + светлое ядро, радиус ~0.22×min(w,h) зоны, WORLDMAP_LOCATION_ZONE: CITY→12, LOC1→7, LOC2→102, LOC3→52, LOC4→127; LAS_NOCHES на карте нет → метки нет).
- **Вшитые маркеры:** в overlay.png зашиты 26 фиолетовых кружков (координаты маркера минус OVERLAY_OFFSET в системе оверлея) — дублируются процедурными свечениями поверх.
- **Fade-in (Stage 136):** `_worldmap_fade_alpha` 0→1 за `WORLDMAP_FADE_SEC=0.15`; при alpha<1 рендер идёт в промежуточный SRCALPHA-буфер с set_alpha; обновление в run-цикле рядом с `_update_endgame`.
- **Маркеры:** ВСЕГДА фиолетовые (217,70,239), пульс 0.5+0.5*sin(t/320+i*0.7); при hover подсвечивается ТОЛЬКО маркер hovered-зоны по ZONE_MARKER_INDEX (золотое ядро, пульс t/140); остальные НЕ меняются (альфа 115 ≈ 0.45, константа).
- **Активность:** `zone.unlock_level <= player.level`. Неактивная: серая платформа, 🔒, без hover-подсветки, тултип «откроется на N ур.», клик → красная плашка «Зона закрыта» 1.5с (карта НЕ закрывается).
- **Тултип у курсора:** справа +18px, флип влево у правого края, clamp по вертикали; деревни — золотая рамка.
- **Клик по активной зоне:** деревня → закрыть + `_go_to_location(CITY)`; локация → закрыть + `_go_to_location(ZONE_LOCATION_MAP[zone_id])`; Las Noches на карте НЕТ (вход через карточку в CITY). Клик вне панели закрывает карту; нижние клики блокируются ранним return в `_handle_click`.
- **`_go_to_location` (Stage 135):** CITY разрешён (сброс las_noches_dialog) + страховочный гейт `player.level < LOCATION_MIN_UNLOCK[loc]` → не переключать.
- **Кнопка «Карта мира»** (110×36, левее миникарты, tag `open_worldmap`) заменила дропдаун «Локации ▾» (Stage 46 удалён: render_map.py, `_toggle_loc_dropdown`, `_select_loc_from_dropdown`, `_loc_dropdown_open`). Миникарта-круг НЕ тронут (CITY↔последняя локация).
- **Ленивая загрузка:** ассеты/маски/скейлы строятся при первом открытии (`_load_worldmap_assets`); обесцвечивание stdlib-only (pygame.image.tobytes), без numpy.

### 7.14 Сюжетные квесты и NPC (Stage 172-174, v174.0)

- **Данные:** `data/quests_db.py` — `STORY_QUESTS` (4 квеста) + `STORY_QUEST_CHAIN` + `chain_prerequisites_met()`. Цель — `goal_type`: `talk_to` | `use_item` | `kill_mobs` (Stage 173: `goal_target` — ПРЕФИКС enemy_id, `goal_count`). `data/npcs_db.py` — `NPCS` (жаба Локация 1 — спрайт; Старейшина CITY — **текстовая метка** `map_text` в `label_x/label_y` = (640,560), аватар ТОЛЬКО в диалоге — Stage 174), позиции `ground_x/ground_y`, `sprite_h`, реплики `flavor`/`hover_text`. Константы UI — `NPC_*`, `QUEST_ARROW_*`, `QUEST_TRACKER_*`, `QUEST_DIALOG_*`, `CITY_CARD_*` в config.py.
- **Цепочка (всё от Старейшины):** q1 «Материк Сакура окутан тьмой» (talk_to; Оружие для новичка + 5000 золота + 5 опыта + 10 купонов) → q2 «Первые шаги» (use_item: надеть weapon_novice; 5 опыта + 10 купонов) → q3 «Доложите о своём прогрессе» (talk_to; 15 опыта + 10 купонов) → **q4 «Победите самураев» (Stage 173, kill_mobs: 3 любых samurai_*; 20 опыта + 10 купонов)**. «Камни» = золото.
- **Состояние (PlayerState):** `story_quests_active` / `story_quests_goal_done` / `story_quests_completed` / `story_quests_kill_progress` (Stage 173, {quest_id: n}, только активные kill_mobs — компакция to_dict/from_dict/turn_in, кэп по goal_count). Доступность НЕ хранится — выводится из chain + completed. talk_to сдаётся тем же кликом по giver'у; use_item — хук `equip_gear_item → notify_story_quest_item_used`; kill_mobs — хук ПОБЕДЫ в `process_battle_rewards` (единая точка x1/x10 боя; mob_id → enemy_id через ENEMY_MOBS → `notify_story_quest_kill`). API: `story_quest_available / accept_story_quest / story_quest_goal_done / story_quest_kill_progress (→ (сделано, надо)) / turn_in_story_quest (→ сводка наград; полный инвентарь → item_failed) / story_quest_npc_indicators («!», «?»)`. reset_progression сбрасывает цепочку.
- **UI:** NPC+трекер — нативно в `_render_map` (`_render_map_npcs`, `_render_quest_tracker`, `_render_quest_mobs_arrow`; теги `map_npc:<id>`, `quest_tracker_*`, `quest_go_to_*` — в skip-списке `_handle_click`, инертны под модалками; **Stage 174 — все rect'ы трекера/диалогов `priority=True`** — двухпроходный `_handle_click` бьёт порядок регистрации, страж ЛН не перехватывает клики панели + он в skip-листе). Индикаторы: «!» amber = можно взять, «?» emerald = готов к сдаче. **Диалог NPC (Stage 174 — единое окно):** legacy-модалка через `_render_modal_scaled(self._render_npc_dialog)`; контекст offer/turn_in/reminder/flavor; ширина 480, высота ДИНАМИЧЕСКАЯ (измерение строк → `QUEST_DIALOG_MIN_H=250..MAX_H=430`); жёсткие секции ШАПКА (аватар 64)|ЗАДАНИЕ|НАГРАДЫ через `_npc_window_divider`; кнопки h=28 (`QUEST_DIALOG_BTN_H`); хелперы `_npc_window_frame/_divider/_button` — общие со стражем Лас Ночеса (`render_las_noches`). Строка цели в трекере/диалоге — `_quest_goal_display_text` (kill_mobs добавляет «(2/3)»). Трекер: 264px, прижат к правому нижнему углу (`QUEST_TRACKER_BOTTOM_MARGIN=66`), 2 вкладки, тосты НАД панелью; **сворачивание — иконка «Т» в нижнем UI-баре** (правый край, бейдж = число активных; плавающая кнопка 44×44 удалена Stage 174). **«Перейти» ведёт по состоянию** (`_quest_target_location`): невзятый/готовый квест → к giver'у, активный с невыполненной целью → `quest.location`; закрытая локация → тост. **Стрелка-подсветка (Stage 173):** после успешного «Перейти» 5 c качается золотая стрелка над целью (`_quest_arrow_quest/_quest_arrow_timer`, тик в run(); цель пересчитывается каждый кадр `_quest_arrow_target`: NPC — поверх бейджа, kill_mobs — над рядом карточек мобов).
- **Город (Stage 174):** карточки Арена/Магазин/Башня = текстовые плашки 136×38 (`CITY_CARD_POSITIONS` — слегка хаотичные центры) с тёмной подложкой; иконки 64px НЕ видны постоянно — плавно проявляются НАД плашкой только при hover (fade `CITY_CARD_HOVER_SEC=0.22` через `_card_hover_anim`; альфа через `.copy().set_alpha` — кэш `_su_image` мутить нельзя; Башня — программная иконка в SRCALPHA); клик по плашке открывает окно (Башня по дизайну ведёт на LAS_NOCHES).
- **Ассеты:** `assets/npcs/toad_avatar.png`, `assets/npcs/elder_avatar.png` (портреты 137×182 из upload); `assets/extracted/npc_toad_idle/1..17.png` — idle-анимация жабы 121×168 (Stage 173: экспорт ШЕЙПОВ `JPEXS -format shape:png -select 3,…,35 -export shape` + выравнивание оффсетов по сырым кадрам; кроп y=62 кадрового экспорта СРЕЗАЛ голову в прыжке — не использовать; sprite_h=154).
- **Предмет-награда:** `weapon_novice` (EQUIPMENT_DB; «Оружие для новичка», ур. 1, sell_price=0 — продажа запрещена, иначе q2 невыполним).
- ⚠ **Локация 1 открывается с 6 ур.** (`LOCATION_MIN_UNLOCK`), а q4 выдаётся ~на 3-м: «Перейти» честно отвечает «Локация закрыта», счётчик копится с любого samurai_*. Баланс не трогать.

---

## 8. UI/Рендеринг

### 8.1 Render order (battle, `_render_battle`)
1. Background (Tower → `get_tower_battle_bg(floor)`; normal → `LOCATIONS_DB[loc]["bg"]`).
2. HUD (`_render_hud`) — аватары + имена + HP/MP бары + central VS + debuff иконки.
3. Side banners (`_render_side_banners`) — "Осмотреть" слева/справа (открывают char sheet).
4. Fighters (`_render_fighter` × 2).
5. Particles (`_particles.render`).
6. Damage numbers (`_damage_numbers.render`).
7. Cast effect (`_cast_effect.render`) — one-shot анимации (Fireball).
8. Projectile effect (`_projectile_effect.render`).
9. Click rects (left + right banner).
10. Combat log (`_render_combat_log`) — bottom bar.
11. Speed buttons (x1/x2/x3/x4) — если char sheet закрыт.

### 8.2 `_render_fighter` (Stage v132.1 binding)
```python
sprite = animator.get_sprite(asset_manager)
if attack_seq active: actual_x = attack_seq.current_x
else: actual_x = x   # PLAYER_SPRITE_X или ENEMY_SPRITE_X
actual_x += shake_offset

# Shadow + ring (centered on actual_x)
# Sprite blit at (actual_x - w/2, SPRITE_BASE_Y - h)

# Effect overlays (BOUND to actual_x):
if ice_effect.active:
    ice_cx = actual_x + ICE_BLOCK_X_OFFSET       # =5
    ice_cy = SPRITE_BASE_Y - ICE_BLOCK_RENDER_H//2 + ICE_BLOCK_Y_OFFSET  # =25
    ice_effect.render(screen, ice_cx, ice_cy, asset_manager)

if shield_effect.active:
    shield_cx = actual_x + SHIELD_DOME_X_OFFSET   # =-8
    shield_cy = SPRITE_BASE_Y - SHIELD_DOME_RENDER_H//2 + SHIELD_DOME_Y_OFFSET  # =25
    shield_effect.render(screen, shield_cx, shield_cy, asset_manager)

# Cloud: above head (cloud_x=actual_x, cloud_y=blit_y-40)
# Poison: centered on sprite body
```
**Stage v132.1 fix:** ice block + shield dome теперь привязаны к `actual_x + X_OFFSET` (раньше — фиксированная позиция). Y = `SPRITE_BASE_Y - RENDER_H//2 + Y_OFFSET` → "стоит на земле", не прыгает по кадрам. Размеры 280×210 (раньше 340×270 / 334×270).

### 8.3 Effect overlay классы (`effects.py`)
| Класс | Тип | Поведение |
|---|---|---|
| `IceBlockEffect` | looping | пока `freeze` активен, 8 FPS, centered на (cx, cy) |
| `EffectOverlay` | looping | shield/cloud/poison — generic, параметризуется folder+fps+w+h |
| `CastEffect` | one-shot | играет N кадров → auto-deactivate (не используется сейчас, кроме Fireball через ProjectileEffect) |
| `ProjectileEffect` | one-shot | 3 фазы: Phase 1 (`frame < CAST_HOLD_FRAMES=3`) — anchor на caster; Phase 2 — linear travel caster→target; Phase 3 — anchor на target (explosion) |

**Активация:**
- `EffectOverlay`/`IceBlockEffect`: `activate(asset_manager)` (idempotent), `deactivate()`.
- `CastEffect`/`ProjectileEffect`: `start(folder, x, y, asset_manager, fps, w, h, flip)`.

### 8.4 Animation — IdleAnimator + AttackSequence
- `IdleAnimator.set_action(action_name, asset_manager)` мапит action → folder через role-specific dicts:
  - Player (Ichigo): `ICHIGO_ACTION_BY_NAME` → `ICHIGO_ACTIONS[action_id]["folder"]`.
  - Enemy 10001 (Samurai): `SAMURAI_ACTION_BY_NAME`.
  - Enemy 10002 (Blue Swordsman): `BLUE_SWORDSMAN_ACTION_BY_NAME`.
  - Enemy 10004 (Black Samurai): `BLACK_SAMURAI_ACTION_BY_NAME`.
  - Enemy 10102 (Flower): `FLOWER_ACTION_BY_NAME`.
- Action FPS: `ACTION_FPS = {idle:8, idle_bored:6, idle_breath_long:6, attack:14, run:10, hit:10, death:6}`.
- Death action: freeze на последнем кадре (`_frozen = True`).

### 8.5 Facing detection (`assets.py`)
- `INTRINSIC_FACING` dict (config.py) — hardcoded facing для каждого motion folder.
- Fallback: alpha-mass heuristic (upper 60% спрайта, left_mass vs right_mass).
- Player всегда flip'ится чтобы смотреть вправо, enemy — влево.

### 8.6 Drag-and-drop (Stage 64-67, inventory)
- LMB-down записывает позицию + слот.
- Если motion > `_DRAG_THRESHOLD = 5px` → drag (swap на release).
- Иначе click → context menu (`_context_menu_item_id`).
- Cross-page drags preserved.
- RMB → equip/unequip.
- **Drag-призрак (Stage 160/164)**: общий хелпер `_render_drag_ghost`
  (`ui/scaling.py`): верхний левый угол призрака = КОНЧИК КУРСОРА
  (`self._mouse_pos`, без оффсета +28 Stage 147), общая прозрачность
  `DRAG_GHOST_ALPHA = 160` через `Surface.set_alpha` поверх SRCALPHA-буфера
  (подсветка зоны/цели дропа видна сквозь предмет). Размер призрака =
  `item_span` предмета. Рамка рисуется ПОСЛЕ иконки (rarity-подложка иконки
  непрозрачна и перекрыла бы её). Тот же хелпер — у drag-иконки «в руке»
  при переносе между слотами синтеза. **Stage 164 — призрак рисуется
  ПОСЛЕДНИМ в кадре** (`pygame_ui._render_drag_ghost_topmost`: legacy — в
  буфер до композита, native — на монитор после `_render_native_overlays`);
  НЕ рисовать призрака внутри рендера модалки — он прячется за окнами.
- **Синтез — предмет живёт в слоте (Stage 164)**: дроп костюма из инвентаря
  освобождает ячейку (`src_slots[src_idx] = None`), слот синтеза хранит
  item_id; ПКМ/LMB-клик/закрытие окна возвращают предмет (`inv_add`);
  `synth_preview/execute` принимают item_id (одинаковые id в слотах =
  разные физические копии). **Stage 166 — УСПЕХ кладёт результат +N+1 в СЛОТ
  РЕЗУЛЬТАТА** (`_synth_result_item`, НЕ inv_add — место в инвентаре не
  нужно, полный инвентарь не блокирует синтез); забрать — ЛКМ/ПКМ по слоту
  результата (`_synth_collect_result`); гейт уровня игрока в synth_preview
  удалён — носить по требованию проверяет equip_gear_item.
- **Якорная память инвентаря (Stage 148/164)**: `dict[item_id → список
  позиций]`, хелперы `_inv_anchor_*` (единственные точки изменения);
  drag обновляет позицию только перетащенной копии (по текущей клетке
  layout'а); дубликаты (одинаковый item_id) не пересортировываются.

### 8.7 Как уменьшать окна без потери качества (анализ Stage 160)

Резкость элемента определяется отношением размера растра к размеру источника.
Отсюда — правила сжатия окон:

1. **Сначала убрать «воздух», не трогая контент** (нулевой риск): паддинги
   16→10px, зазоры блоков 8→6, шапка окна 40→32, высота плашек-кнопок.
   Дают −10…15% ширины/высоты окна без изменения шрифтов и иконок.
2. **Текст ужимать можно (до предела читаемости)** — шрифты векторные и
   рендерятся под фактический размер (`_su_font` в нативной фазе — сразу в
   физических пикселях): уменьшение кегля НЕ мылит. Минимумы: 12px — подписи,
   10px — второстепенные (ниже — теряется читаемость, не резкость).
3. **Иконки ужимать нельзя ниже нативного размера источника**: исходники 24×24
   (мелкие items) и 82×82 (аватары). Правила Stage 142/149 обязательны: без
   даунскейла при влезании 1:1, кап апскейла ×1.3. На 2К ячейка 27 дизайн =
   54 физ — 24px-арт растягивается ×2.25 (уже за капом); запас даёт только
   HD-пак иконок (оффлайн-апскейл 24→96, xBRZ/ESRGAN — идея в реестре).
4. **Немигрированные модалки НЕ уменьшать**: на 2К они идут апскейлом ×2 —
   уменьшение окна уменьшит и растр → двойной ресемпл. Сначала миграция экрана
   в нативный путь, потом ужимать вёрстку (текст останется резким на любом
   размере).
5. **Компактные режимы вместо уменьшения**: вкладки/сворачиваемые секции
   (образец — удаление gem-секции Stage 142), тултип вместо постоянно видимой
   статистики, скролл внутри окна вместо растяжения.
6. Ориентир по инвентарю (624×541): −11% (≈560×500) достижимо пунктами 1+5
   без потери качества; −25% — только с уменьшением ячеек 27→24 (на 2К это
   48 физ — иконка 24×24 остаётся 1:1 при наличии HD-пака) или без него.
7. **Пример применения (Stage 162)**: синтез/гардероб сужены по прямому анализу
   контента: синтезу достаточно 4×72 + 3×24 = 360px (окно 480 = контент + поля),
   гардеробу 24+64+16+240+16+80+24 = 464px (окно 480); высота — по позиции
   последнего элемента + нижний запас (360/470 вместо 440/500). Размеры слотов
   НЕ тронуты — «воздух» по краям просто уходит.

### 8.8 Particles + Damage numbers (`particles.py`)
- `ParticleSystem.spawn_hit(x, y, is_crit)`:
  - 8-15 частиц, 50% (`PARTICLE_BLOOD_FRACTION`) — blood цвета для crit.
  - Случайный угол + скорость + жизнь + size, gravity applied.
- `DamageNumber` — 2 фазы (Stage 97):
  - FLASH (0.8s): стоит на месте, пульсирует scale 1.0→1.3→1.0.
  - FLOAT: плывёт вверх с vy, alpha fade linear.
- Crit → "Крит!" floating text выше damage number.
- Miss → "Уклон!", Parry → "Парри!".

---

## 9. Сохранения (`game/save_load.py`)

### 9.1 Формат
- Путь: `<repo_root>/data/player_save.json` (НЕ в `src/pockie_rpg/data/`!).
- Backup: `player_save.json.bak`.
- **Stage 171 — rolling slots:** `data/player_save_slot_<n>.json` ×3
  (`ROLLING_SAVE_SLOTS`); `archive_rolling_save()` копирует primary в
  следующий слот (свободный → старейший по mtime, цикл 1→2→3) после
  успешной загрузки на старте сессии; битый primary НЕ архивируется.
- Цепочка загрузки: primary → .bak → слоты (новые раньше старых);
  `load_from_slot(n)` — прямая загрузка (F9 dev-кнопки: 2 клика,
  только на карте, flush → load → set_player → провайдер → mark_dirty).
- `SAVE_VERSION = 2` (migration hook — no-op пока).
- Атомарная запись: `tempfile.mkstemp` → `fsync` → backup old → `os.replace`.

### 9.2 SaveManager (Stage 88, debounced; Stage 171 — троттлинг)
- `SaveManager(player)` оборачивает PlayerState.
- `mark_dirty()` — помечает изменённым, сбрасывает debounce таймер на `0.5s`.
- `update(dt)` — per-frame: decrements таймер; после истечения debounce
  дисковая запись троттлится `AUTOSAVE_MIN_INTERVAL_SECONDS = 5.0`.
- `flush()` — force save если dirty (переходы экранов/QUIT) — БЕЗ троттлинга;
  `_last_write` обновляется даже при сбое (нет шторма повторов).

### 9.3 validate_save + компакция (Stage 171)
- `validate_save(data) -> list[str]` — перечень полей, которые from_dict
  отбросит/заменит (типы зеркалят from_dict: bool-ok для int;
  int|float|null для accum/кулдаунов; легаси-ключи НЕ сообщаются);
  вызывается в `_try_load_from_path` (→ `(player, issues)`), пишется в
  logger.warning + `LAST_LOAD_REPORT` → F10-оверлей.
- `to_dict` фильтрует КОПИИ `generated_weapons`/`outfit_instances` по ссылкам
  (инвентарь все страницы, equipped_gear, equipped_outfit, гардероб,
  слоты синтеза через `PlayerState.synth_slots_provider` — callable от UI,
  НЕ сериализуется, биндится в `__init__` и после загрузки слота);
  живой PlayerState НЕ мутируется.

### 9.4 Migration (PlayerState.from_dict)
- Обрабатывает: absent `active_skills` → migrate к full role set; per-slot enchants → per-item-id; legacy flat inventory → paged; absent `gear_enchants`/`tower_*` → defaults.
- Сложный, но well-commented.

---

## 10. Известные баги и готчи (КРИТИЧЕСКИ ВАЖНО)

### 10.1 Bug'и
1. ~~`state.py:1376-1377` — `type_field` undefined~~ — ИСПРАВЛЕН (Stage 133, блок удалён).
2. ~~`state.py:987 vs 990` — `gold = 0` мёртвое~~ — ИСПРАВЛЕН (Stage 133).
3. ~~`state.py:933-975` — хрупкая пересборка CharacterStats~~ — ИСПРАВЛЕН (Stage 133, перенесено в recalc_stats).
4. **`events.py` `is_parry`** — объявлен, но не пишется движком; читается UI (полу-фича «Парри!») — НЕ удалять. `inc_hp` УДАЛЁН (Stage 133).
5. ~~`EventType.FREEZE_SHATTER`~~ — УДАЛЁН (Stage 133, никогда не эмитился).
6. ~~`save_load.TEMP_FILE_PATH` мёртвый~~ — ЗАПИСЬ ОШИБОЧНА: используется в `delete_save()` (исправлено в Stage 133).
7. **`fighter.py` legacy fields** (`parry_mul, parry_chance, crit_mul, crit_attach, crit_chance=5, tough, neglect_def, pierce=0`) — для backward-compat, **не используются в Stage 104 pipeline**.
8. **`status_manager` `"freeze"` vs `"frozen"`** — оба в `SKIP_STATUSES`. Skill registry использует `"freeze"`; `"frozen"` — legacy.
9. ~~`DAMAGE_NUMBER_POISON_COLOR` отсутствовал в config → NameError на первом тике яда~~ — ИСПРАВЛЕН (Stage 134: константа добавлена, ленивый импорт заменён на верхний).
10. ~~Фулл-хил после обычного боя ставил `player_role.max_hp` (без шмота/уровня)~~ — ИСПРАВЛЕН (Stage 134: `player.stats.max_hp/max_mp`).
11. ~~Фулл-хил `_exit_battle` затирал HP/MP после гантлета~~ — ИСПРАВЛЕН (Stage 134: для SLOT_GAUNTLET фулл-хил пропускается, синк из `_finish_gauntlet_round`).

### 10.2 Дублирующиеся формулы (риск вызова не той)
1. **Crit chance — 2 системы:**
   - Legacy `calc_crit_chance(strength, gear)` → `min(75, 5 + STR*0.3 + gear)` (UI display only).
   - Stage 104 `rating_to_crit_chance(rating)` → `rating * 0.0625` (combat, uncapped).
2. **Crit multiplier — 2 системы:**
   - Stage 52 `calc_crit_multiplier(strength)` → `min(2.50, 1.50 + STR*0.01)`.
   - Stage 104 `rating_to_crit_damage(rating)` → `rating * 0.125` (used in `apply_crit_stage`).
3. **Hyperbolic CRIT_K=3200** — упомянут в docstring, но НЕ используется в `apply_crit_stage` (linear). Dangling. **`DEFENSE_CONSTANT=1354` С Stage 133 ИСПОЛЬЗУЕТСЯ** в `apply_defense_stage` (4-стадийный пайплайн).

### 10.3 Магические числа НЕ в config (флаг для centralization)
- `fight.py:201` — `AP_CAP = 10.0` (внутри `fight()`).
- `fight.py:187` — `+= 0.01` deadlock-breaker.
- ~~`fight.py:386` — MP regen 2%~~ — УДАЛЁН (Stage 133, MP не регенится).
- `fighter.py:409` — `duration = 2` (default freeze duration, должно быть `CRYSTAL_BLADE_FREEZE_DURATION`).
- `state.py:53,990` — `gold = 100000` (test gold).
- `state.py:606` — `max(400, int(1500 / max(0.1, speed)))` (atk_time).
- `state.py:639` — `* 1.5` (max_atk multiplier).
- `state.py:922` — `self.level * 100` (XP curve).
- `state.py:1203` — `> 60` (gem synthesis 60% success).
- `state.py:1320` — `< 0.10` (10% gem drop).
- `status_manager.py:435` — `10` (cloud_dmg_fallback).

### 10.4 Неочевидные решения
- `MOB_DROP_TABLES` определяет **только Location 1** — Locations 2/3/4 **MISSING** (fallback на no drops).
- `RING_TEMPLATE_MAP[5] = "ring_jade2"` — placeholder icon (пользователь не загрузил `icon_equip_ring2.s110.gif`).
- `INTRINSIC_FACING` — hardcoded facing для каждого motion folder, потому что VLM и alpha-mass heuristics ненадёжны для Ichigo.
- `effect_folder` (UI concern) хранится в `SkillDef` (engine data) — mild layering violation.
- `crit_rating` НЕ зависит от STR (только gear+gems) — design choice, не bug.
- `total_flat_max = base_max_no_gear + gear_max + 0` — `+ 0` intentional (NO gem_max contribution). Закомментировано.
- `FightValue` mutable с `slots=True` — добавление нового field требует обновления dataclass.
- ~~`player_mp`/`enemy_mp` sync hack~~ — ПОЛЯ УДАЛЕНЫ (Stage 134; после Stage 133 никем не писались/не читались).
- Burn использует `EventType.POISON_DAMAGE` + `is_poison=1` (re-use, нет отдельного BURN_DAMAGE).
- `combat_hit_chance` использует `attacker.hit_rating` (NEW) но `Fighter` также имеет legacy `hit_chance` (RATING) — легко перепутать.

### 10.5 Defensive reads (могут прятать баги)
- `getattr(attacker, 'crit_rating', 0)` в `apply_damage_pipeline` (для старых Fighters).
- `getattr(stats, 'block_rating_ui', 0)` в `from_player_state` (для старых saves).
- `getattr(self, 'gear_enchants', ...)` в `state.py` (для очень старых saves).

---

## 11. История версий

**Единый источник истории — `MEMORY.md` §«История Stage'ей»** (полный таймлайн
от Stage 4 до текущей версии, от новых к старым; подробности свежих stage'ей —
в начале того файла). Здесь история НЕ дублируется (Stage 160 — консолидация
документации 7→3 файла: удалены AI_START_HERE/HANDOFF/IDEAS/HI_DPI2K как
дублирующие; правила Hi-DPI переехали в RULES.md, идеи — в MEMORY.md).

---

## 12. Как запустить и разрабатывать

### 12.1 Запуск
```bash
cd <repo_root>
python -m pockie_rpg.main
# или
pockie-rpg   # через entry_point
```

### 12.2 Проверка синтаксиса (после правок)
```bash
python -m py_compile config.py ui/render_battle.py ui/effects.py ui/combat_replay.py
```

### 12.3 Тестовые режимы
- **F9** — Test Panel (dev-панель: spawn test weapon, override skill chances).
- **F9 из карточки моба** — TEST_BATTLE state (immortal enemy, infinite MP, manual skill triggers).
- **F10** — Stage 152: отладочный оверлей Hi-DPI (время кадра/FPS, ui_scale/render_scale/
  modal_scale, размеры монитора и буфера, native path on/off + registry, ClickRect'ы
  всего/native, state/локация/BattleMode, открытые модалки, размеры кэшей).
- **F11** — fullscreen ↔ окно 1280×720 (в оконном режиме нативный Hi-DPI выключен).
- **F12** — toggle combat debug log (пишет `data/combat_debug.txt`).

### 12.3.1 Hi-DPI (нативный рендер на 2К+) — Stage 150-159
Чек-лист миграции и критичные готчи нативного пути — в **`RULES.md`** (секция
«Hi-DPI — правила работы»); статус миграции и план — в `MEMORY.md`.
- `config.UI_SCALE = 2.0`, `SCREEN_WIDTH_UI/HEIGHT_UI` (2560×1440), `su()`,
  `NATIVE_MODAL_REGISTRY = {"inventory", "forge", "map", "synth", "wardrobe",
  "titles", "shop", "battle"}` (Stage 151-157, 201), `MODAL_SCALE_2K = 1.0`,
  `MODAL_FADE_SEC = 0.15`.
- Нативный путь активен при ЦЕЛОЧИСЛЕННОМ масштабе монитора (`compute_ui_scale`:
  2560×1440 → 2.0, 3840×2160 → 3.0); дробные (2048×1152 = 1.6 от Windows 125%
  без DPI-aware) → legacy 1.0. DPI-awareness — `_make_windows_dpi_aware()` в main.py.
- **Порядок кадра (Stage 153)**: `_begin_native_base_frame()` → рендер базового
  экрана НАТИВНО (screen = монитор, `_mouse_pos` ×2, `_render_scale` = UI_SCALE) →
  `_end_native_base_screen()` (ClickRect'ы помечаются `native=True`; screen →
  прозрачный `_legacy_layer` 1280×720) → немигрированные модалки в слой →
  `_present_fullscreen(flip=False)` (при нативном базовом экране накладывает
  ТОЛЬКО слой, буфер не растягивается) → `_render_native_overlays()` → оверлей
  F10 → `flip()`.
- **Бой (Stage 201) — нативный, но по СВОЕЙ схеме (окно 60%)**: scale =
  UI_SCALE × BATTLE_WINDOW_SCALE (2К: 1.2); контент рисуется в offscreen-
  поверхность ОКНА (монитор ×BATTLE_WINDOW_SCALE) и блитится 1:1; ClickRect'ы
  боя — ДИЗАЙН-координаты (мышь ремапится `_map_battle_mouse`, маркировка
  native=True сломала бы клики); чар-листы — `_legacy_layer`, накладываемый
  в прямоугольник окна; фон — снапшот сцены через кэш `_battle_bg_monitor`.
  Арена/тест-бой (F9) — legacy-путь. Детали и готчи — MEMORY (Stage 201).
- **Fade-in окна боя (Stage 202)**: `_battle_window_fade` 0→1 за
  `MODAL_FADE_SEC` (сброс в `_enter_battle`); в `_present_fullscreen`
  альфу получают окно (нативный surf / legacy smoothscale), legacy-слой,
  затемнение и рамка (SRCALPHA-кэш); фон-снапшот НЕ фейдится. set_alpha
  на кэшированных поверхностях — сброс в 255 после blit.
- Мигрированный рендер пишется в ДИЗАЙН-координатах и проходит через
  `self._su()` / `_su_rect()` / `_su_font()` / `_su_icon_size()` / `_su_scaled()` /
  `_su_image()` / `_su_overlay()` (`ui/scaling.ScalableRendererMixin`) + общие
  перетаскиваемые окна (`_render_window_titlebar`, Stage 157) и drag-призрак
  (`_render_drag_ghost`, Stage 160).
- `ClickRect.native` + `_click_rect_hit()` — hit-тест в своём пространстве;
  `_inv_native_pos()` — конвертация позиций событий для экранов с нативным layout.
- Смоук: `PYTHONPATH=src python scripts/hidpi_smoke.py [--modal inventory|forge|map]`.
- Ещё legacy: char sheet/навыки, башня/дейлики/слот-машина/quick battle,
  мировая карта (свой `WORLDMAP_SCALE` + маски), арена, тест-бой (F9).
- Смоук нативного боя: `python scripts/verify_battle_native.py` (18 чеков).

### 12.4 Ассеты
- Спрайты: `assets/extracted/<role>/<action>/N.png` (1.png, 2.png, ...).
- Backgrounds: `assets/backgrounds/<name>.jpg`.
- Avatars: `assets/avatars/userface_NNNNN.png`.
- Skill icons: `assets/skills/icons/icon_skill<id>.png`.
- Gem icons: `assets/gems/<gem_icon_filename>`.
- Fonts: `assets/fonts/Ninja Naruto.ttf`.

### 12.5 SWF → PNG extraction
Если пользователь даёт `.swf` файл — извлечь кадры в PNG **без чёрного/белого фона** (прозрачный alpha). Использовать `ffdec` (JPEXS Free Flash Decompiler). Сохранять в `assets/extracted/<role>/<action>/N.png` с цифровой нумерацией.

**Stage 178 — ОДНА КОМАНДА (стандартный путь):**
`python scripts/extract_swf.py upload/motion_10004_52.s117.swf`
— обёртка над FFDec `-export sprite` + автопроверка качества (6 чеков:
frame_count / uniform_size / alpha / density / brightness / distinct;
выцветшие кадры детектятся по средней яркости) + установка кадров с
заменой + обновление MANIFEST.json. Имя `motion_<персонаж>_<экшен>.swf`
разбирается автоматически (10004→black_samurai; 999→idle, 52→attack,
55→run, 57→death_fall, 64→hit); нестандартное имя — флаги
`--char/--action/--action-id`. Полезные флаги: `--dry-run` (только отчёт),
`--force` (установить вопреки FAIL), `--keep-old`, `--no-download`,
`--ffdec <путь>`. FFDec ищется в `./tools/ffdec` → `~/tools/ffdec` →
`/tmp/ffdec` (или $FFDEC_JAR), иначе скачивается с GitHub. Exit-коды:
0 ок / 1 ошибка аргументов / 2 качество не пройдено (старые кадры не
тронуты). Диагностика конвейера: `python scripts/diag_stage178.py`.

**Stage 177 — ПРАВИЛЬНЫЙ метод (важно!):** сырой экспорт битмапов
(`-export image`) даёт ВЫЦВЕТШИЕ/полупрозрачные кадры (DefineBitsJPEG3 без
учёта шейпа). Правильно: `java -jar ffdec.jar -export sprite <outdir> <swf>`
— FFDec рендерит кадры DefineSprite в ЕДИНОМ холсте экшена (выравнивание +
корректная альфа). Кадров может быть БОЛЬШЕ, чем битмапов (шейпы переиспользуют
битмапы: attack чёрного самурая = 13 кадров из 7 битмапов) — бери количество
кадров СПРАЙТА. Проверка качества: средняя яркость непрозрачных пикселей
(битые кадры ~0.6+, правильные тёмные спрайты ~0.3).

---

## 13. Ключевые принципы работы (для нового чата)

1. **config.py — единый источник констант.** Все магические числа → в config. Если число только в одном месте — всё равно в config с комментарием.
2. **Layering rule.** `config → data → combat → game → ui`. Без circular imports (используй lazy import внутри функций).
3. **Frozen dataclasses** (`frozen=True, slots=True`) для всех Layer A данных. Items — исключение (dicts, для merge с save state).
4. **Skill registry — data-driven.** Новый навык = новая запись в `SKILL_REGISTRY`. Движок подхватывает автоматически.
5. **Damage pipeline — 3 стадии.** Crit → Block → Pierce. Линейные формулы, без hyperbolic.
6. **SPEED LAW.** AP накапливается, боец с наибольшим AP ходит. Пропущенный ход тоже тратит AP. Extra turn → AP refund.
7. **Stage 104 IRON RULE.** `*_rating` (flat) и `*_pct` (multiplier) — разные поля. Legacy % ключи (`dodge_mul`, `hit_chance`, `crit_chance`, `parry_chance`, `pierce`) — трактуются как MULTIPLIERS, не flat.
8. **Save atomicity.** Все мутации игрока → `save_mgr.mark_dirty()`. Прямой `save_player_state()` только в legacy-путях.
9. **Модалки — boolean flags inside MAP.** Не добавляй новые `GameState`. Добавь `_X_modal_open: bool` + click handler + render dispatch + ESC cascade entry.
10. **Visual overlay binding.** Оверлеи (ice/shield/cloud/poison) привязаны к `actual_x + X_OFFSET`, не к фиксированной позиции. Y = `SPRITE_BASE_Y - RENDER_H//2 + Y_OFFSET` (ground-anchor).
11. **py_compile после правок.** Перед коммитом/архивом — `python -m py_compile <changed_files>`.
12. **No comments в коде.** Пиши чистый код без комментариев (кроме stage-маркеров и неочевидных workaround'ов).

---

## 14. Ссылки на детальный анализ

- `MEMORY.md` — лор, история stage'ей, готчи (короткий формат).
- `RULES.md` — строгие правила для чата (как себя вести, что обновлять).
- Подробный анализ по модулям — в `/home/z/my-project/tool-results/` (результаты подагентов ANALYSIS-COMBAT/CONFIG/DATA/UI).

**Конец PROJECT_PROMPT.md.**
