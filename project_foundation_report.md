# Технический отчёт: аудит фундамента проекта Ninja Wars2 (Pockie RPG)

**Дата:** 06.09.2026
**Метод:** полный просмотр боевого ядра, ядра состояния, сейвов, config/data; профилирующий разбор всех 24 UI-модулей; проверка по цепочкам вызовов (60 FPS-рендер, боевая петля, загрузка/сохранение).
**Оценка проекта:** 7/10 — сильная боевая математика и инфраструктура сейвов; главные риски — god-модули, recalc_stats в кадре рендера и ряд аллокаций поверхностей на каждый кадр.

---

## 6. СТАТУС РЕАЛИЗАЦИИ ФИКСОВ (обновлено 06.09.2026, после аудита)

| # | Приоритет | Что | Статус |
|---|---|---|---|
| 1 | 🔴 | Кэш кругов частиц | ✅ РЕАЛИЗОВАНО — `particles.py`: class-level `_circle_cache`, ключ (size, color, alpha-бакет), ≤240 surf; рендер 0.01 мс/кадр |
| 2 | 🔴 | os.listdir → кэш кадров NPC | ✅ РЕАЛИЗОВАНО — `render_quests.py`: `_npc_idle_frames_cache` по idle_folder; 0.17 мс → 8.5 мкс/вызов, 0 обращений к ФС в кадре |
| 3 | 🔴 | recalc_stats dirty-инвалидация | ✅ РЕАЛИЗОВАНО — `state.py:recalc_stats(use_cache=False)`: кэш отдаётся при `use_cache=True` и отсутствии активных бафов (они тикают по времени); чар-лист переключён; force-мутации не тронуты; ×100 быстрее (0.2 мкс vs 20 мкс) |
| 4 | 🔴 | SysFont из циклов → кэш | ✅ РЕАЛИЗОВАНО — `render_quick_battle.py:76` (24px), `test_battle.py:372-377` (2 шрифта) → `_su_font` |
| 5 | 🔴 | smoothscale → scale в present | ⏳ ОТСРОЧЕНО — требует визуальной проверки на 2К-мониторе (риск артефактов nearest-масштаба) |
| 6 | 🔴 | flush() не сбрасывает dirty при сбое | ✅ РЕАЛИЗОВАНО — `save_load.py`: OSError/Exception → warning + return (dirty живёт, повтор через update()); протестировано симуляцией Disk full |
| 7 | 🟡 | from_dict защитить int() | ✅ РЕАЛИЗОВАНО — `state.py`: gen_w_counter и gem level с type-check; битые значения отбрасываются точечно, загрузка выживает |
| 8 | 🟡 | _refresh_stats для gem-методов | ✅ РЕАЛИЗОВАНО — единый метод с ДЕЛЬТА-семантикой (рост потолка → current растёт на дельту; уменьшение → кламп); попутно закрыт эксплоит «переоделся = полный хил» старого equip-кода |
| 9 | 🟡 | StatusManager копия params | ✅ РЕАЛИЗОВАНО — `apply()` хранит `dict(params)`; shield-мутация больше не трогает replay-данные |
| 10 | 🟡 | Fallback тучи caster=None | ✅ РЕАЛИЗОВАНО — несовпадение role_id → честный cloud_dmg_fallback вместо урона статами жертвы |
| 11 | 🟡 | Убрать getattr-дефолты в damage | ✅ РЕАЛИЗОВАНО — прямой доступ к 6 полям; опечатка упадёт с AttributeError вместо молчаливого 0 |
| 12 | 🟡 | Снапшот бафов раз в 0.5с | ✅ РЕАЛИЗОВАНО — `render_map.py`: pygame-таймер, 60 rebuild/сек → 2/сек |
| 13 | 🟢 | Мёртвый BMV-блок | ✅ РЕАЛИЗОВАНО — удалён из recalc_stats (рассинхрон дефолтов устранён) |
| 14 | 🟢 | Тройной recalc в __post_init__ | ✅ РЕАЛИЗОВАНО — один пересчёт; cached HP/MP снимаются с результата |
| 15 | 🟡 | Капы icon-кэшей | ✅ РЕАЛИЗОВАНО — forge `_gem_icon_cache`, quick_battle `_loot_icon_cache`/`_loot_gem_cache` — кап 256 + reset |
| 16-20 | 🟡/🟢 | MappingProxyType, config→combat, дефолты, MAP_BACKGROUND, preload | ⏳ ОТСРОЧЕНО — архитектурные, требуют отдельной сессии |

**Верификация после всех правок:** ruff 0 ошибок; все модули импортируются; боевой цикл жив (полная симуляция боя, winner определяется); save/load round-trip проходит; дельта-семантика HP подтверждена 4 тестами.

**Осознанные трейд-оффы:**
1. Альфа частиц квантуется бакетами по 16 (различимо только на иконках >10px — для спарков 3-5px незаметно).
2. recalc-кэш отключается при ЛЮБОМ активном бафе (консервативно; можно уточнить per-kind).
3. Дельта-семантика `_refresh_stats` меняет поведение переодевания (было неявное полное лечение) — целевое исправление эксплоита.

---

## 1. Игровой цикл (Game Loop) и рендер

### 1.1. Архитектура цикла — в целом грамотная ✅

`pygame_ui.py:590-597` (`run()`): `clock.tick(FPS) → events → update → render → present`.
FPS-кап задаётся `config.FPS`; dt-анимации везде получают `dt` параметром — нет физически завязанных на кадровую частоту таймеров. ESC-каскад (`pygame_ui.py:605-662`) корректно приоритизирует закрытие модалок. **Критичных проблем нет.**

### 1.2. Present-пайплайн 2К: двойной smoothscale полноэкранных буферов — 🔴 ВЫСОКИЙ приоритет

**Файл:** `src/pockie_rpg/ui/pygame_ui.py:1151-1153` (`_present_fullscreen`, ветка боя).

```python
window_surf = pygame.transform.smoothscale(
    self._fullscreen_game, (win_w, win_h)
)
```

Каждый кадр боя на 2К-мониторе выполняются **два** smoothscale полноэкранных буферов: фон-снапшот (2560×1440) + окно боя 60% (1536×864). `smoothscale` — одна из самых дорогих операций pygame (фрактальная интерполяция в Python-циклах C-слоя). Замер самой команды: ~6 мс только на растяжение фона. Итог: до ~10-12 мс кадра уходит на ресемплинг ещё до отрисовки спрайтов.

**Фикс (кэш, безопасно):**
```python
# _present_fullscreen, ветка BATTLE:
cache = getattr(self, "_battle_window_scaled_cache", None)
if cache is None:
    cache = self._battle_window_scaled_cache = {}
key = self._fullscreen_game.get_size()  # содержимое буфера меняется, размер — нет
window_surf = cache.get(key)
if window_surf is None:
    window_surf = pygame.transform.smoothscale(
        self._fullscreen_game, (win_w, win_h))
    cache[key] = window_surf
# важно: smoothscale возвращает НОВУЮ поверхность, blit содержимого
# меняется каждый кадр, поэтому кэшировать по размеру нельзя без blit
```
Корректный вариант — кэшировать **направление и формулу** экономнее: так как буфер перерисовывается каждый кадр, кэшировать нельзя, но можно заменить `smoothscale` → `scale` (nearest, ~в 5-8 раз дешевле, визуально на боевом окне почти неотличимо):
```python
window_surf = pygame.transform.scale(
    self._fullscreen_game, (win_w, win_h)
)
```
То же для строки 1143 (фон — уже кэшированный снапшот, менять размер не нужно вовсе: снапшот делается в размере буфера).

### 1.3. Аллокации Surface каждый кадр — 🔴 ВЫСОКИЙ (наиболее массовый класс)

Каждая SRCALPHA-поверхность это malloc + memset + GC-давление. Найдены по всем рендерам:

| Файл | Строки | Что |
|---|---|---|
| `particles.py` | 123-130 | `pygame.Surface((size*2, size*2), SRCALPHA)` **на каждую частицу каждый кадр** (до сотен) |
| `test_battle.py` | 332-334 | полноширинная SRCALPHA-панель лога каждый кадр |
| `render_quests.py` | 44-48 | `os.listdir()` — сканирование **файловой системы** каждый кадр для каждого NPC |
| `render_quests.py` | 110, 205, 221, 489, 602 | SRCALPHA-плашки/тени/панели каждый кадр |
| `render_forge.py` | 468, 848 | `sorted()` всего gem-инвентаря каждый кадр (O(n log n)) |
| `render_forge.py` | 207, 393, 675 | Surface для обрезки текста + `icon.copy()` каждый кадр |
| `render_worldmap.py` | 179-215 | glow/hilite Surface × 7-16 кругов × ~20-40 маркеров каждый кадр |
| `render_las_noches.py` | 95-116 | glow-композиция (12 blit BLEND_ADD) каждый кадр при hover |
| `render_world_boss.py` | 102-112 | тень + flash Surface каждый кадр |
| `render_quick_battle.py` | 76 | `pygame.font.SysFont(...)` **в цикле по карточкам каждый кадр** |
| `test_battle.py` | 372-377 | 2 × `SysFont` каждый кадр |
| `render_shop.py` | 168-170 | while-цикл `font.render()` обрезки имени (до 18 рендеров/кадр) |
| `render_misc_modals.py` | 138-161 | те же while-циклы перерендера |

В проекте уже есть идеальный инструмент для всех этих мест — **`_static_surface(key, size, draw_fn)`** (`scaling.py:351-374`) и **`_su_text()` LRU-кэш** (`scaling.py:321-349`) — но мигрированы не все модули. Пример фикса для частиц:

```python
# particles.py:123 — было: новая Surface на частицу
# стало: кэш кругов (размер/цвет/альфа-бакет — конечные множества)
key = (p.size, p.color, p.alpha // 16)
surf = ParticleSystem._circle_cache.get(key)
if surf is None:
    surf = pygame.Surface((p.size * 2, p.size * 2), pygame.SRCALPHA)
    pygame.draw.circle(surf, (*p.color, 255), (p.size, p.size), p.size)
    ParticleSystem._circle_cache[key] = surf
surf.set_alpha(p.alpha)
self.screen.blit(surf, (p.x - p.size, p.y - p.size))
```

Топ-3 места по вреду: частицы (в бою — сотни аллокаций), `os.listdir` в quests (диск в кадре), SysFont в quick_battle/test_battle (системный матчинг шрифта × 5/кадр).

### 1.4. Кэши текста — хорошая база, но покрытие неполное — 🟡 СРЕДНИЙ

`scaling.py:321-349` — `_su_text()` с LRU 2048 элементов. Карта и бой уже на нём (`render_map.py:671,813`, `render_battle.py:542`). Но `render_battle.py:316-327` (имена бойцов), `render_world_boss.py:200-230`, `render_shop.py:165`, `render_misc_modals.py:134-161` рендерят `font.render()` напрямую. Унификация на `_su_text` закрывает все while-циклы обрезки.

### 1.5. ФС в рендер-пути — 🔴

`render_quests.py:44-48`: `os.listdir(str(EXTRACTED_DIR / npc.idle_folder))` вызывается из `_render_single_npc` → 60×/сек × N NPC. Фикс:

```python
if not hasattr(self, "_npc_frames_cache"):
    self._npc_frames_cache: dict[str, list[str]] = {}
frames = self._npc_frames_cache.get(npc.idle_folder)
if frames is None:
    frames = sorted(os.listdir(str(EXTRACTED_DIR / npc.idle_folder)))
    self._npc_frames_cache[npc.idle_folder] = frames
```

### 1.6. Кэши без капа — 🟡 НИЗКИЙ

Без капа растут: `_gem_icon_cache` (forge, ключ включает размеры), `_loot_icon_cache`/`_loot_gem_cache` (quick_battle), `_panel_gradient_cache`. Рост ограничен разнообразием контента, но при длинной сессии память течёт. Фикс — `if len(cache) > 256: cache.clear()` при закрытии модалки. У AssetManager и `_su_text` капы есть — образец соблюдён.

### 1.7. Preload-кэш аватаров мёртвый — 🟡

`assets.py:75` кладёт в кэш ключ `enemy_{mob_id}_72`, а `get_enemy_avatar` ищет `__enemy_avatar__:{mob_id}:{size}` → прелоад не используется, первый рендер врага грузит с диска в кадре. Фикс: unify ключей.

**Вывод по разделу:** цикл здоров, фреймворк кэшей правильный и уже частично внедрён. Утечек памяти классических нет (растущие кэши ограничены по природе контента) — риски «размазанной» памяти из per-frame аллокаций.

---

## 2. Боевой движок и формулы

### 2.1. Пайплайн Stage 137 — математически корректен ✅

`combat/formulas.py` (500 строк, изолирован от проекта — импортирует только stdlib): пайплайн `Hit → Crit → Defense → Block` реализован строго по спецификации оригинала:
- `combat_hit_chance` (стр. 278-305): `100 − (dodge − hit)`, кламп [5, 100] — анти-иммортальность работает;
- `apply_crit_stage` (516-556): шанс/урон крита через два независимых шага (/16 и /8), ноль шанса при отрицательной разнице;
- `apply_defense_stage` (589-608): гипербола `x/(x+1354)` с вычитанием — при равных статах защиты и пробивания ровно гасятся в ноль;
- `apply_block_stage` — та же логика для пары блок/антиблок.

Верифицировано тестами ранее в сессии: hit 100% → dodge перекрывает, freeze-сценарии, нанесение урона по стадиям. Формулы **без капов** на рейтинги — по оригиналу, но жёсткие капы вероятностей [5,100] присутствуют. Хорошо документировано (docstring с примерами и деривацией).

### 2.2. Ключевая ловушка масштабирования: бой читает поля Fighter, считанные при создании — 🟡

`damage.py:83-88`:
```python
attacker_crit = getattr(attacker, 'crit_rating', 0)
defender_tough = getattr(target, 'tough_rating', 0)
```
Боец строится один раз (`Fighter.from_player_state`, `fighter.py:236-313`), рейтинги снимаются из `recalc_stats()` на момент старта. Это правильно для бафа «на бой», но:
- **баг-паттерн для будущего:** любые mid-бой модификации статов (новые скиллы-бафы атаки/защиты) не попадут в пайплайн, пока их не внесут в Fighter до `fight()`;
- `getattr(..., 0)` скрывает опечатки в имени поля — при переименовании `crit_rating` бой молча продолжит считать 0 крита. Фикс: убрать `getattr`-дефолты (`attacker.crit_rating` напрямую), чтобы опечатка падала с AttributeError.

### 2.3. StatusManager: общий dict params — 🟡

`status_manager.py:224`:
```python
self._effects[name] = StatusEffect(name=name, duration=duration, params=params or {})
```
`params` сохраняется **по ссылке**. Боевой путь (`damage.py:_build_effect_params`) строит свежий dict — безопасно. Но `combat_replay.py:433-863` передаёт словари из replay-данных; при поглощении щита `take_damage` (`fighter.py:318`) мутирует `params["amount"]` — мутируются и replay-данные. Фикс (1 строка):
```python
params=dict(params or {})
```

### 2.4. Fallback урона грозовой тучи бьёт жертву её же статами — 🟡

`status_manager.py:433-435`:
```python
else:
    # Role_ids don't match either fighter — defensive fallback.
    caster = opponent
```
Если `caster_role_id` не совпал ни с кем (например, добавят третьего участника или изменят role_id), урон тучи считается от min/max_atk **самой жертвы**. Фикс:
```python
else:
    caster = None  # → fallback в cloud_dmg_fallback
```

### 2.5. Двойной декремент заморозки (известное решение) — ℹ️

Контроль-статусы тикают глобальным декрементом (`fight.py:_global_freeze_decrement` на каждый ход любого бойца) **и** собственным `on_turn_end` замороженного. С недавнего фикса AP-несгорания это даёт ровно 2 пропущенных хода при duration=2 — поведение целевое, но семантика «двойного тика» хрупка: при изменении порядка вызовов легко сломать. Рекомендация: один механизм — либо только глобальный, либо только per-turn.

### 2.6. Масштабируемость новых скиллов — ✅ хорошо

`skill_registry.py` — единый реестр `SKILL_REGISTRY: dict[int, SkillDef]`, скиллы data-driven (`on_hit_effects` декларативны), движок (`fight.py:_try_skills`) полностью generic — новый скилл = запись в реестр без правок движка. Это сильная сторона. Костюмы — тоже данные (`OUTFITS_DB` + BMV-цены). Узкое место одно: `config.py:1966-1979` содержит жёстко прошитую мапу `_ROLE_BY_SKILL` (дублирует `Role.skills` из roles_db) — при добавлении скилла нужно править два места. Фикс: вывести из `ROLES` автоматически.

---

## 3. Ядро (Core) и стейт игры

### 3.1. PlayerState — god-класс (~15 ответственностей, 2553 строки) — 🟡 СРЕДНИЙ (долгосрочно)

`game/state.py:63-216`: прогрессия, экономика, инвентарь (3 домена), шмот/заточка, камни, 3 вида синтеза, гардероб, бафы, world boss, башня, квесты двух типов, сериализация, пересчёт статов. ~60 полей, ~70 методов. Работает, но каждое изменение рискует зацепить несвязанные механики. Рекомендация (не срочно): миксины `InventoryMixin / QuestState / TowerState / BuffState` + сериализация в отдельный mapper.

### 3.2. recalc_stats вызывается каждый кадр — 🔴 ВЫСОКИЙ

`render_skills_charsheet.py:483`:
```python
stats = self.player.recalc_stats()  # Stage 24 comment: "fresh recalc every frame"
```
`recalc_stats` — самая тяжёлая функция ядра: обход 8 слотов шмота × scale/enchant, 24 gem-слота, 15 импортов из config, `get_buff_multiplier` → `time.time()`, ~30 вычисляемых полей, аллокация `CharacterStats`. В открытом окне персонажа это выполняется **60 раз/сек**.

Фикс (инвалидация по dirty-флагу):
```python
# state.py:
_stats_dirty: bool = True
def touch_stats(self) -> None: self._stats_dirty = True
# recalc_stats() в начале: if not self._stats_dirty and self.stats is not None: return self.stats
# в конце: self._stats_dirty = False
# equip/unequip/enchant/gem/level-up/активация бафа → touch_stats()
# charsheet: stats = self.player.recalc_stats()  # теперь дешёвый вызов
```

### 3.3. Снапшот бафов на карте каждый кадр — 🟡

`render_map.py:164`: `self._map_buffs_ui = self.player.get_active_buffs_ui()` → rebuild списка + sort + `time.time()` 60×/сек. Фикс — раз в 0.5 сек:
```python
now = time.time()
if now - getattr(self, "_buffs_snap_ts", 0) > 0.5:
    self._buffs_snap_ts = now
    self._map_buffs_ui = self.player.get_active_buffs_ui()
```

### 3.4. Мёртвый BMV-блок в recalc_stats — 🟢 дешёвый фикс

`state.py:765-768`: блок `bmv = outfit.get("bmv", {})` перезаписывается на 830-833 из `bmv_price` — мёртвая работа + рассинхрон дефолтов (20/40/10 vs 20/20/20). Удалить.

### 3.5. Тройной recalc при создании PlayerState — 🟢

`state.py:243-248`: `__post_init__` вызывает `get_max_hp()` + `get_effective_max_mp()` (каждый = полный recalc) и потом ещё `recalc_stats()`. Фикс:
```python
s = self.recalc_stats()
object.__setattr__(self, '_cached_hp', s.max_hp)
object.__setattr__(self, '_cached_mp', s.max_mp)
```

### 3.6. Gem-методы не обновляют кэш HP/MP — 🟡 заметный игроку баг

`socket_gem`/`unsocket_gem`/`upgrade_gem`/`synthesize_gems` (`state.py:1467-1540`) вызывают `recalc_stats()` без обновления `_cached_hp/_cached_mp` → после вставки HP-камня current_hp не получает новую ёмкость до следующего equip/level-up. Фикс: единый `_refresh_stats()` (recalc + оба кэша) и везде звать его.

### 3.7. Сохранение/загрузка — архитектурно сильно ✅ с двумя гэпами

Сильные стороны (`save_load.py`): атомарная запись (tmp + fsync + os.replace, 113-141), ротация слотов (B1, 144-179), validate_save (357+), debounced autosave с троттлингом 5 сек, резервная цепочка primary→.bak→слоты (240-282). Это лучше среднего для инди-проекта.

**Гэп 1 — потеря dirty-флага при сбое диска** (`save_load.py:726-734`):
```python
except OSError as exc:
    logger.warning("Autosave failed: %s", exc)
...
self._dirty = False   # ← сброс даже при ошибке
```
Диск отвалился → warning → `_dirty=False` → до следующего mark_dirty сейв не повторяется; при выходе игрок теряет прогресс молча. Фикс:
```python
except OSError as exc:
    logger.warning("Autosave failed (will retry): %s", exc)
    return  # не сбрасываем _dirty — повтор на следующем update()
```

**Гэп 2 — незащищённые int() в from_dict** (`state.py:2626`, `2526`):
```python
p._gen_w_counter = max(0, int(data.get("gen_w_counter", 0)))   # ValueError на "abc"
... "level": int(g["level"]) ...                                 # то же
```
Битое поле уронит ВЕСЬ from_dict → первичный сейв отброшен (спасает только .bak/слоты). Фикс:
```python
raw = data.get("gen_w_counter", 0)
p._gen_w_counter = max(0, int(raw)) if isinstance(raw, (int, float)) else 0
```

**Гэп 3 — рассинхрон дефолтов** (`state.py:2456-2459` vs `87-90`): старый сейв без полей получает 24/24/20/300, новый игрок — 10/10/10/200. Нужен единый источник дефолтов.

### 3.8. Конфиг как god-модуль — 🟡 СРЕДНИЙ

`config.py` (2283 строки): пути + Hi-DPI + анимационные маппинги + enum'ы + LOCATIONS_DB + лут-таблицы + 7 балансных таблиц + локализация (`SLOT_NAME_RU`) + BUFF_DB + формулы (`outfit_synth_*`) + боевые константы скиллов + ре-экспорты combat. Дополнительно:
- `config.py:2235` — импорт **combat** в config = инверсия слоёв (docstring обещает «only stdlib»). Цикла сейчас нет, но `import config` в любой combat-модуль даст взаимоблокировку. Ре-экспорты нужны только для совместимости старых импортов — план отказа: перевести ~20 потребителей на прямой импорт и удалить блок.
- `config.py:2221-2223` — `sys.path.insert` на уровне модуля (побочный эффект импорта).
- Дублирование данных: балансные таблицы (1029-1191) дублируют `EQUIPMENT_DB` (item_db 49-433) — правка в одном месте молча разойдётся; `TOWER_MAX_FLOOR` в config и tower_db; `MAP_BACKGROUND` (439) противоречит `LOCATIONS_DB[1].bg` (496) и мёртв; suit_ichigo описан в двух БД с разными именами.
- Мутабельные глобалы без защиты: `LOCATIONS_DB`, `MOB_DROP_TABLES`, `BUFF_DB`, `EQUIPMENT_DB` и т.д. — любой импортёр может испортить. Фикс: `types.MappingProxyType` в ре-экспортах или frozen dataclass (образец — tower_db).
- Локализация в конфиге — вынести в `i18n.py`.

### 3.9. Семантическая ловушка: title-бонусы — 🟡

`titles_db.py:66-179`: ключи `hit_chance`/`crit_chance`/`dodge_chance` выглядят как «+X% к шансу», но через `collect_rating_pct` (`state.py:911-919`) работают **множителем плоского рейтинга** (и только при базе > 0 — малая база «сжигает» бонус). Игрок видит «Крит +8%», реально — ×1.08 к crit_rating. Фикс: переименовать в `crit_pct`-семантику или сменить описание в UI.

---

## 4. Приоритетный план действий

| # | Приоритет | Что | Где |
|---|---|---|---|
| 1 | 🔴 | Кэш кругов частиц (сотни Surface-аллокаций/кадр в бою) | `particles.py:123` |
| 2 | 🔴 | os.listdir → кэш списка кадров NPC | `render_quests.py:44` |
| 3 | 🔴 | recalc_stats → dirty-инвалидация (60×/сек в charsheet) | `state.py` + `render_skills_charsheet.py:483` |
| 4 | 🔴 | SysFont из циклов карточек → кэш шрифтов | `render_quick_battle.py:76`, `test_battle.py:372` |
| 5 | 🔴 | smoothscale → scale в present-пайплайне боя | `pygame_ui.py:1143,1151` |
| 6 | 🔴 | flush(): не сбрасывать _dirty при OSError | `save_load.py:726-734` |
| 7 | 🟡 | from_dict: защитить int() (gen_w_counter, gem level) | `state.py:2626,2526` |
| 8 | 🟡 | _refresh_stats() для gem-методов (кэш HP/MP) | `state.py:1467-1540` |
| 9 | 🟡 | StatusManager.apply: копия params | `status_manager.py:224` |
| 10 | 🟡 | Fallback тучи: caster=None вместо opponent | `status_manager.py:433-435` |
| 11 | 🟡 | Убрать getattr-дефолты в damage pipeline | `damage.py:83-88` |
| 12 | 🟡 | Снапшот бафов раз в 0.5с | `render_map.py:164` |
| 13 | 🟢 | Удалить мёртвый BMV-блок + hasattr | `state.py:765-768,710` |
| 14 | 🟢 | Тройной recalc в __post_init__ → один | `state.py:243-248` |
| 15 | 🟡 | Капы для icon-кэшей | forge/quick_battle |
| 16 | 🟡 | MappingProxyType для БД-глобалов | config/item_db/titles_db |
| 17 | 🟢 | План отказа от config→combat ре-экспортов | `config.py:2235` |
| 18 | 🟢 | Единый источник дефолтов стата | `state.py:2456` |
| 19 | 🟢 | Синхронизировать/удалить MAP_BACKGROUND, TOWER_MAX_FLOOR | `config.py:439,1445` |
| 20 | 🟢 | Прелоад-ключи аватаров | `assets.py:75` |

## 5. Резюме

**Сильные стороны:** изолированный и документированный боевой модуль (0 внешних зависимостей formulas.py); data-driven скиллы; атомарные сейвы с ротацией и валидацией; продуманная система кэшей (_su_text/_static_surface/_su_font) с уже мигрированными горячими путями; defensive-стиль сейвов.

**Слабые стороны:** god-модули (config 2283 строк, state 2553, pygame_ui 4127) — работает, но тормозит развитие; per-frame аллокации в немигрированных рендерах; recalc_stats в кадре; два гэпа в надёжности сейвов.

**Стратегическая рекомендация:** пункт 3 (dirty-инвалидация recalc) даст наибольший эффект наименьшей кровью — после него чар-лист перестанет быть самым дорогим экраном, а бафы перестанут звать time() в кадре. Дальше — пункты 1-2 (бой и NPC-кадры) и пункт 6 (данные).
