"""Game state: player progression and curated content (Layer C).

Per §4.3: imports ONLY stdlib — no `pockie_rpg.*` imports at top level.
This keeps the layer pure data carrier (decoupled from combat / ui).

Stage 4: expanded Role with full character sheet stats (strength, agility,
stamina, defense, crit, dodge, parry, hit, etc.) for the character sheet window.
Stage 96: Role/Suit/ENEMY_MOBS data extracted to data/roles_db.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from pockie_rpg.config import (
    ATK_TIME_BASE_MS,
    ATK_TIME_MIN_MS,
    ATK_TIME_SPEED_FLOOR,
    GEM_DROP_CHANCE,
    GEM_SYNTH_SUCCESS_PCT,
    LEVEL_XP_CURVE,
    MAX_LEVEL,
    TEST_START_COUPONS,
    TEST_START_GOLD,
)
from pockie_rpg.data.models import CharacterStats

# Stage 96 — re-export from roles_db for backward compat.
# ENEMY_MOBS/STARTER_SUITS не используются в state.py, НО re-export'ятся
# для 7 ui-модулей (workaround против ruff F401 — НЕ удалять).
from pockie_rpg.data.roles_db import (  # noqa: F401
    ENEMY_MOBS,
    ROLE_ICHIGO,
    ROLES,
    STARTER_SUITS,
)

# ---------------------------------------------------------------------------
# PLAYER STATE (mutable — progression persists between battles)
# ---------------------------------------------------------------------------


def _empty_inventory() -> dict:
    """Stage 64 — build a fresh empty paged inventory (3 pages × 64 slots).

    Returns a dict keyed by page number (1, 2, 3) where each value is a list
    of exactly ITEMS_PER_PAGE None entries (empty slots). Used as the
    default_factory for PlayerState.inventory and on reset_progression().
    """
    from pockie_rpg.config import INVENTORY_PAGE_KEYS, ITEMS_PER_PAGE
    return {p: [None] * ITEMS_PER_PAGE for p in INVENTORY_PAGE_KEYS}


def _empty_wardrobe() -> list:
    """Stage 167 — пустой гардероб: WARDROBE_SLOTS слотов (5 страниц × 5).

    Ленивый импорт config — как в _empty_inventory (слой game не тянет
    config на уровень модуля).
    """
    from pockie_rpg.config import WARDROBE_SLOTS
    return [None] * WARDROBE_SLOTS


@dataclass
class PlayerState:
    """Mutable player progression state.

    Level Up system: max_xp = level * 100. On level up: strength/agility/stamina
    each +2, max_mp +10. All derived stats auto-recalculated from primary stats.
    """

    name: str = "Игрок"
    suit_id: str = "i290001"
    role_id: int = 1
    level: int = 1
    current_xp: int = 0
    max_xp: int = 100
    # Stage 113 — тестовое золото для баланс-тестов (запрошено пользователем;
    # Stage 170 — значение вынесено в config.TEST_START_GOLD).
    gold: int = TEST_START_GOLD
    # Stage 165 — КУПОНЫ: второй ресурс рядом с золотом (пользовательский
    # запрос). Для теста выдаётся 10 500: и новым игрокам (дефолт поля;
    # Stage 170 — config.TEST_START_COUPONS), и старым сейвам (from_dict —
    # дефолт при отсутствии ключа).
    coupons: int = TEST_START_COUPONS
    defeated_mobs: list[str] = field(default_factory=list)
    # Stage 39 — base stats are 10/10/10/200 (outfit adds the rest).
    strength: int = 10
    agility: int = 10
    stamina: int = 10
    max_mp: int = 200
    active_skills: list[int] = field(default_factory=list)
    # Stage 39 — active outfit (costume). Determines base_stats + growth_bonus.
    equipped_outfit: str = "suit_ichigo"
    # Stage 31 — SINGLE equipment standard (7 gear + 1 outfit = 8 slots).
    equipped_gear: dict = field(default_factory=lambda: {
        "weapon": None, "head": None, "body": None, "hands": None,
        "belt": None, "boots": None, "accessory": None, "accessory2": None,
        "outfit": "suit_ichigo",
    })
    # Stage 64 — INVENTORY PAGINATION.
    # Inventory is split into 3 fixed pages (1, 2, 3), each holding exactly
    # ITEMS_PER_PAGE = 64 slots. A slot is either None (empty) or an item_id
    # string. Methods inv_find / inv_add / inv_remove / inv_count operate
    # across all pages transparently so callers don't need to know the layout.
    inventory: dict = field(default_factory=lambda: _empty_inventory())
    # Stage 47/116 — FORGE: per-ITEM-ID enchant level (0-20).
    # Stage 116 — changed from per-slot to per-item-id so enchant follows
    # the item, not the slot. When you unequip an item, it keeps its enchant.
    # Keyed by item_id (e.g., "weapon_wooden" or "gen_w_001").
    gear_enchants: dict = field(default_factory=lambda: {})
    # Stage 51 — GEM SYSTEM.
    # gem_inventory: list of gem instances. Each entry is a dict
    #   {"id": "gem_<n>", "type": "gem_red", "level": 1}.
    # The "id" is a unique instance identifier (so two rubins are distinct).
    gem_inventory: list = field(default_factory=list)
    # gear_gem_slots: per-slot list of gem instance IDs (or None).
    # A slot can have up to MAX_GEM_SLOTS_PER_ITEM (3) gems socketed.
    gear_gem_slots: dict = field(default_factory=lambda: {
        "weapon": [None, None, None], "head": [None, None, None],
        "body": [None, None, None], "hands": [None, None, None],
        "belt": [None, None, None], "boots": [None, None, None],
        "accessory": [None, None, None], "accessory2": [None, None, None],
    })
    # Counter for generating unique gem instance IDs.
    _gem_id_counter: int = 0
    # Stage 70 — TITLES SYSTEM. Active title id (or None). The active title's
    # stat bonuses are added to the player's CharacterStats via recalc_stats().
    active_title: str | None = None
    # Stage 71/72/77 — WORLD BOSS. Attempts remaining (max 3).
    # Each attempt = 1 fight. At 0, player must wait for timer.
    world_boss_attempts: int = 3
    # Stage 77 — timestamp when next attempt will be added (epoch seconds).
    # None = timer not active (attempts already at max).
    world_boss_next_attempt_ts: float | None = None
    # Stage 72 — boss state dict. None = boss not spawned.
    world_boss_hp: dict | None = None
    # Stage 89 — TOWER MODE. Per TOWER_MODE_IMPLEMENTATION.md §6.
    # tower_current_floor: the floor the player is about to enter (1-100).
    # tower_highest_floor: highest floor cleared (0 = none cleared yet).
    # Stage 90 — attempt limit REMOVED. Tower is endless (play until death).
    # Stage 134 — legacy fields tower_attempts / tower_next_attempt_ts DELETED
    # (from_dict ignores the keys in old saves — no restore code needed).
    # tower_shards: Tower currency (spent in Tower Shop).
    # tower_materials: dict of material_id → count (5 core types).
    # tower_first_clear_claimed: list of floor numbers whose first-clear
    #   reward has been claimed (prevents double-claiming).
    tower_current_floor: int = 1
    tower_highest_floor: int = 0
    tower_shards: int = 0
    # Stage 94 — accumulated XP from Tower battles (claimed via "Получить" button).
    tower_pending_xp: int = 0
    # Stage 95 — Daily Quests. Progress dict {quest_id: count}.
    # claimed: list of quest_ids claimed today.
    # quest_date: ISO date string (YYYY-MM-DD) for daily reset check.
    daily_quest_progress: dict = field(default_factory=dict)
    daily_quest_claimed: list = field(default_factory=list)
    daily_quest_date: str = ""
    tower_materials: dict = field(default_factory=dict)
    tower_first_clear_claimed: list = field(default_factory=list)
    # Stage 108 — generated (procedural) weapons storage.
    # Keyed by unique instance ID (e.g., "gen_w_001"). Value is the item dict
    # produced by generate_item(). Inventory slots and equipped_gear can hold
    # these instance IDs — get_item_definition() resolves them.
    generated_weapons: dict = field(default_factory=dict)
    _gen_w_counter: int = 0
    # Stage 138 — SYNTH: заточенные костюмы-инстансы (по образцу generated_weapons).
    # Ключ: "outfit_inst_<n>". Значение: {"outfit_id": модель, "plus": int}.
    # Инвентарь/equipped_gear["outfit"] могут держать эти инстанс-ID —
    # get_item_definition() резолвит их. Базовые (не заточенные) костюмы
    # остаются обычными item_id ("suit_ichigo") — их в БД и так может быть
    # несколько копий в разных слотах.
    outfit_instances: dict = field(default_factory=dict)
    _outfit_inst_counter: int = 0
    # Stage 138 — плюс заточки по item_id (для базовых моделей, если когда-нибудь
    # понадобится плюс у базовой копии; инстансы хранят плюс в себе).
    outfit_plus: dict = field(default_factory=dict)
    # Stage 138/167 — WARDROBE: 25 слотов-хранилищ (5 страниц × 5; None | item_id/inst_id).
    wardrobe: list = field(default_factory=_empty_wardrobe)
    # Stage 133 — fractional BMV-growth accumulators (gain_xp). Persisted in
    # to_dict/from_dict so fractional growth survives save/load; None = not
    # started (lazy-init from current int stats on first level-up).
    _str_accum: float | None = None
    _agi_accum: float | None = None
    _sta_accum: float | None = None
    # Stage 133 — slot machine: earliest epoch second the player may roll again.
    slot_next_roll_ts: float | None = None
    # Stage 157 — UI: позиции перетаскиваемых окон {key: (x, y)} в ДИЗАЙН-
    # координатах (1280×720). Ключи: "synth", "wardrobe", "inventory",
    # "forge", "titles", "shop". UI (ScalableRendererMixin) синхронизирует
    # свой runtime-словарь с этим полем (persist между сессиями).
    window_positions: dict = field(default_factory=dict)
    # Stage 160 — разовый грант 6 костюмов Ичиго существующим сейвам (тест
    # синтеза). False у старых сейвов → from_dict выдаёт костюмы один раз
    # и ставит флаг; новые сейвы получают костюмы через starter_items().
    synth_test_grant_v160: bool = False
    # Stage 172 — сюжетные квесты (цепочка — data/quests_db.py). «Доступные»
    # НЕ хранятся: выводятся из chain-порядка и completed. goal_done — для
    # целей use_item (факт надетия предмета); talk_to-цели завершаются
    # самой сдачей (клик по giver'у).
    story_quests_active: list[str] = field(default_factory=list)
    story_quests_goal_done: list[str] = field(default_factory=list)
    story_quests_completed: list[str] = field(default_factory=list)
    # Stage 173 — счётчик kill_mobs-целей {quest_id: сколько побеждено}.
    # Хранится только для АКТИВНЫХ kill_mobs-квестов (компакция в to_dict/
    # from_dict/turn_in), значения 0..goal_count.
    story_quests_kill_progress: dict[str, int] = field(default_factory=dict)
    # Stage 171 — B3: UI-провайдер слотов синтеза (callable → 4 item_id|None:
    # главный, кат.1, кат.2, результат). НЕ сериализуется. to_dict читает
    # его В МОМЕНТ сохранения — предметы в слотах физически вне инвентаря
    # (Stage 164/166), статически собрать ссылки на их инстансы нельзя.
    synth_slots_provider: object = field(default=None, repr=False, compare=False)
    # Stage 23 — cached snapshot of the dynamic stat recalculation.
    # Refreshed by recalc_stats() (called in __post_init__, equip_gear_item,
    # gain_xp, reset_progression, from_dict). UI reads total_* / max_hp /
    # min_atk etc. from this field instead of recomputing every frame.
    stats: CharacterStats | None = None

    # Backward compat aliases
    @property
    def xp(self) -> int:
        return self.current_xp

    @property
    def xp_to_next(self) -> int:
        return self.max_xp

    @property
    def current_hp(self) -> int:
        return self._cached_hp

    @current_hp.setter
    def current_hp(self, value: int) -> None:
        self._cached_hp = value

    @property
    def current_mp(self) -> int:
        return self._cached_mp

    @current_mp.setter
    def current_mp(self, value: int) -> None:
        self._cached_mp = value

    def __post_init__(self) -> None:
        # Аудит 2026-09 — было ТРИ полных recalc_stats (get_max_hp и
        # get_effective_max_mp сами зовут recalc_stats + явный третий вызов).
        # Теперь один пересчёт, кэши HP/MP снимаются с его результата.
        s = self.recalc_stats()
        object.__setattr__(self, '_cached_hp', s.max_hp)
        object.__setattr__(self, '_cached_mp', s.max_mp)

    # ------------------------------------------------------------------
    # Stage 64 — INVENTORY PAGINATION helpers
    # ------------------------------------------------------------------
    # The inventory is a dict {1: [...], 2: [...], 3: [...]} where each
    # page holds ITEMS_PER_PAGE = 48 slots (None = empty, str = item_id).
    # These helpers let callers treat the inventory as a flat collection
    # without caring about which page an item lives on.

    def _ensure_inventory_pages(self) -> None:
        """Make sure all 3 pages exist and each has exactly ITEMS_PER_PAGE slots.

        Defensive: repairs corrupt state (missing pages, wrong-length lists)
        in-place so subsequent reads/writes are safe.

        Stage 64 — IMPORTANT: this method mutates the existing list objects
        in place whenever possible (rather than replacing them with new
        lists). This preserves list-identity so external code holding a
        reference to `self.inventory[1]` (e.g. the UI's `page_slots` var)
        keeps seeing mutations applied by other code paths.
        """
        from pockie_rpg.config import INVENTORY_PAGE_KEYS, ITEMS_PER_PAGE
        if not isinstance(self.inventory, dict):
            self.inventory = {p: [None] * ITEMS_PER_PAGE for p in INVENTORY_PAGE_KEYS}
            return
        for p in INVENTORY_PAGE_KEYS:
            slots = self.inventory.get(p)
            if not isinstance(slots, list):
                # Page missing or wrong type — create a fresh list.
                self.inventory[p] = [None] * ITEMS_PER_PAGE
                continue
            # Pad / truncate in-place to exactly ITEMS_PER_PAGE.
            if len(slots) < ITEMS_PER_PAGE:
                slots.extend([None] * (ITEMS_PER_PAGE - len(slots)))
            elif len(slots) > ITEMS_PER_PAGE:
                del slots[ITEMS_PER_PAGE:]
            # Coerce any non-str / non-None / non-valid-stack entries to None
            # — in-place.
            # Stage 183 — dict-стаки {"item_id": str, "count": int>0} валидны.
            for i, s in enumerate(slots):
                if s is None or isinstance(s, str):
                    continue
                if (isinstance(s, dict)
                        and isinstance(s.get("item_id"), str)
                        and isinstance(s.get("count"), (int, float))
                        and int(s.get("count", 0)) > 0):
                    continue
                slots[i] = None

    def inv_find(self, item_id: str) -> tuple[int, int] | None:
        """Return (page, slot_idx) of the first slot holding item_id, or None.

        Stage 183 — стак-слоты (dict) тоже находятся: совпадение по item_id.
        """
        if not isinstance(self.inventory, dict):
            return None
        from pockie_rpg.config import INVENTORY_PAGE_KEYS
        for page in INVENTORY_PAGE_KEYS:
            slots = self.inventory.get(page)
            if not isinstance(slots, list):
                continue
            for i, iid in enumerate(slots):
                if isinstance(iid, dict):
                    if iid.get("item_id") == item_id:
                        return (page, i)
                elif iid == item_id:
                    return (page, i)
        return None

    @staticmethod
    def slot_item_id(slot) -> str | None:
        """Stage 183 — распаковка слота: str → сам, dict-стак → item_id.

        Единая точка чтения слота для UI (рендер/drag/меню), чтобы
        dict-стаки не «протекали» туда, где ожидается строка item_id.
        """
        if isinstance(slot, str):
            return slot
        if isinstance(slot, dict):
            sid = slot.get("item_id")
            return sid if isinstance(sid, str) else None
        return None

    @staticmethod
    def slot_count(slot) -> int:
        """Stage 183 — количество предметов в слоте (стак dict → count, иначе 1)."""
        if isinstance(slot, dict):
            return max(1, int(slot.get("count", 1)))
        return 1 if slot is not None else 0

    def inv_split(self, page: int, slot_idx: int, take: int) -> bool:
        """Stage 185 — разделить стак: `take` копий в новую ячейку.

        Работает ТОЛЬКО со стаками (dict). Исходный стак уменьшается на take,
        `take` кладётся в первый пустой слот (та же страница). take >= count →
        делить нечего (False). Место/списывание атомарны: сначала ищем пустой
        слот, потом уменьшаем.
        """
        self._ensure_inventory_pages()
        from pockie_rpg.config import INVENTORY_PAGE_KEYS

        if page not in self.inventory or not (0 <= slot_idx < len(self.inventory[page])):
            return False
        slots = self.inventory[page]
        entry = slots[slot_idx]
        if not isinstance(entry, dict):
            return False  # не стак — делить нечего
        count = int(entry.get("count", 1))
        if take < 1 or take >= count:
            return False

        # Ищем пустой слот на этой странице (или на любой следующей).
        for pg in [page] + [p for p in INVENTORY_PAGE_KEYS if p != page]:
            target_slots = self.inventory[pg]
            for i, s in enumerate(target_slots):
                if s is not None:
                    continue
                # Атомарно: уменьшаем источник, кладём take.
                rest = count - take
                if rest <= 0:
                    slots[slot_idx] = None
                else:
                    entry["count"] = rest
                target_slots[i] = {"item_id": entry["item_id"], "count": take}
                return True
        return False  # нет пустой ячейки

    def _can_visually_fit(self, page: int, new_item_id: str) -> bool:
        """Stage 68/145 — check if new_item_id can be VISUALLY placed on the page.

        Stage 145 — МИНИ-СЕТКА 16×8: спаны предметов item_span() (оружие 2×3,
        броня 2×2, мелочь 1×1). Симулирует размещение ВСЕХ предметов страницы
        + нового; False = новый предмет был бы невидим (нет визуального места).
        """
        from pockie_rpg.config import INV_COLS, INV_MAX_ROWS, item_span
        from pockie_rpg.data.item_db import get_equipment

        slots = self.inv_page_slots(page)
        # Stage 183 — стак-слоты (dict) распаковываются в item_id: их спан 1×1.
        existing_items = [
            self.slot_item_id(iid) for iid in slots
            if self.slot_item_id(iid) is not None
        ]

        def _span(iid: str) -> tuple[int, int]:
            # Stage 111 — use get_item_definition for generated weapons support.
            g = self.get_item_definition(iid) if hasattr(self, "get_item_definition") else get_equipment(iid)
            return item_span(g) if g else (1, 1)

        occupied: set[tuple[int, int]] = set()
        new_item_placed = False
        all_items = existing_items + [new_item_id]
        for idx, iid in enumerate(all_items):
            span_w, span_h = _span(iid)
            placed = False
            for row in range(INV_MAX_ROWS - span_h + 1):
                for col in range(INV_COLS - span_w + 1):
                    if all((col + dx, row + dy) not in occupied
                           for dx in range(span_w) for dy in range(span_h)):
                        for dx in range(span_w):
                            for dy in range(span_h):
                                occupied.add((col + dx, row + dy))
                        placed = True
                        if idx == len(all_items) - 1:
                            new_item_placed = True
                        break
                if placed:
                    break
        return new_item_placed

    def inv_add(self, item_id: str) -> bool:
        """Add an item to the first page where it can be VISUALLY placed.

        Stage 183 — СТАКАНИЕ расходников: если item_id стакуемый (баф) и в
        инвентаре уже есть его стак (dict-слот) с count < ITEM_STACK_MAX —
        инкрементируется счётчик, новая ячейка НЕ занимаетcя. Новый предмет
        стакуемого типа кладётся как {"item_id": id, "count": 1}.
        Нестакуемые (шмот) — как раньше, строка item_id в слоте.

        Stage 68 — iterates pages 1 → 2 → 3. For each page, checks both:
        (a) there is an empty DATA slot, AND
        (b) the item can be VISUALLY placed (considering weapon span=2).

        Returns True on success, False if all 3 pages are visually full.
        """
        self._ensure_inventory_pages()
        from pockie_rpg.config import INVENTORY_PAGE_KEYS, ITEM_STACK_MAX
        from pockie_rpg.data.item_db import is_stackable_item

        # Стак: дозапись в существующую ячейку (без поиска пустого слота).
        if is_stackable_item(item_id):
            for page in INVENTORY_PAGE_KEYS:
                for entry in self.inventory[page]:
                    if isinstance(entry, dict) and entry.get("item_id") == item_id \
                            and int(entry.get("count", 1)) < ITEM_STACK_MAX:
                        entry["count"] = int(entry.get("count", 1)) + 1
                        return True

        for page in INVENTORY_PAGE_KEYS:
            slots = self.inventory[page]
            # Must have an empty data slot.
            has_empty = any(iid is None for iid in slots)
            if not has_empty:
                continue
            # Must be able to visually place the item (Stage 68 fix).
            if not self._can_visually_fit(page, item_id):
                continue
            # Both conditions met — place in the first empty data slot.
            for i, iid in enumerate(slots):
                if iid is None:
                    if is_stackable_item(item_id):
                        slots[i] = {"item_id": item_id, "count": 1}
                    else:
                        slots[i] = item_id
                    return True
        return False

    def inv_has_space(self, item_id: str) -> bool:
        """Stage 133 — non-mutating capacity check mirroring inv_add().

        True if inv_add(item_id) would succeed (some page has both an empty
        data slot and visual room for the item). Used by the shop so gold is
        not charged when the paged inventory is full.
        Stage 183 — стакуемый предмет: место есть, если есть неполный стак.
        """
        self._ensure_inventory_pages()
        from pockie_rpg.config import INVENTORY_PAGE_KEYS, ITEM_STACK_MAX
        from pockie_rpg.data.item_db import is_stackable_item

        if is_stackable_item(item_id):
            for page in INVENTORY_PAGE_KEYS:
                for entry in self.inventory[page]:
                    if isinstance(entry, dict) and entry.get("item_id") == item_id \
                            and int(entry.get("count", 1)) < ITEM_STACK_MAX:
                        return True

        for page in INVENTORY_PAGE_KEYS:
            slots = self.inventory[page]
            if not any(iid is None for iid in slots):
                continue
            if not self._can_visually_fit(page, item_id):
                continue
            return True
        return False

    def inv_remove(self, item_id: str) -> bool:
        """Remove one occurrence of item_id (any page). Returns True if removed.

        Stage 183 — стакуемые предметы (бафы): декремент счётчика стака;
        пустой стак (count → 0) освобождает ячейку.
        """
        if not isinstance(self.inventory, dict):
            return False
        from pockie_rpg.config import INVENTORY_PAGE_KEYS
        from pockie_rpg.data.item_db import is_stackable_item

        if is_stackable_item(item_id):
            for page in INVENTORY_PAGE_KEYS:
                slots = self.inventory.get(page)
                if not isinstance(slots, list):
                    continue
                for i, entry in enumerate(slots):
                    if isinstance(entry, dict) and entry.get("item_id") == item_id:
                        count = int(entry.get("count", 1)) - 1
                        if count <= 0:
                            slots[i] = None
                        else:
                            entry["count"] = count
                        return True
            return False

        for page in INVENTORY_PAGE_KEYS:
            slots = self.inventory.get(page)
            if not isinstance(slots, list):
                continue
            for i, iid in enumerate(slots):
                if iid == item_id:
                    slots[i] = None
                    return True
        return False

    def inv_count_item(self, item_id: str) -> int:
        """Сколько копий конкретного item_id лежит во всех страницах.

        Stage 183 — стак-слоты считаются по count, обычные — по 1.
        """
        if not isinstance(self.inventory, dict):
            return 0
        from pockie_rpg.config import INVENTORY_PAGE_KEYS
        n = 0
        for page in INVENTORY_PAGE_KEYS:
            slots = self.inventory.get(page)
            if not isinstance(slots, list):
                continue
            for iid in slots:
                if isinstance(iid, dict):
                    if iid.get("item_id") == item_id:
                        n += int(iid.get("count", 1))
                elif iid == item_id:
                    n += 1
        return n

    def inv_count(self) -> int:
        """Total non-empty slots across all 3 pages."""
        if not isinstance(self.inventory, dict):
            return 0
        from pockie_rpg.config import INVENTORY_PAGE_KEYS
        total = 0
        for page in INVENTORY_PAGE_KEYS:
            slots = self.inventory.get(page)
            if not isinstance(slots, list):
                continue
            total += sum(1 for iid in slots if iid is not None)
        return total

    def inv_page_slots(self, page: int) -> list:
        """Return the slot list for the given page (or 48 Nones if missing).

        Always returns a list of exactly ITEMS_PER_PAGE entries. The returned
        list is a live reference — mutating it mutates the inventory.
        """
        self._ensure_inventory_pages()
        from pockie_rpg.config import INVENTORY_PAGE_KEYS
        if page not in INVENTORY_PAGE_KEYS:
            page = 1
        return self.inventory[page]

    # ------------------------------------------------------------------
    # Stage 180 — PLAYER BUFFS (расходники-бафы на реальное время)
    # ------------------------------------------------------------------

    # active_buffs: list of {"buff_id": str, "expires_ts": float}.
    # Активные бафы. duration считается в РЕАЛЬНОМ времени (epoch seconds) —
    # тикают вне боя, в бою, при закрытой игре (после загрузки истёкшие
    # чистятся лениво при первом запросе). Один buff_id — одна запись:
    # повторная активация ПРОДЛЕВАЕТ (max(old, now) + duration).
    active_buffs: list = field(default_factory=list)

    def _prune_expired_buffs(self) -> None:
        """Удалить истёкшие бафы (ленивая очистка при каждом чтении)."""
        import time as _time
        now = _time.time()
        self.active_buffs = [b for b in self.active_buffs if b.get("expires_ts", 0) > now]

    def activate_buff(self, buff_id: str) -> tuple[bool, str]:
        """Активировать баф-предмет из инвентаря.

        Правила (Stage 181):
          * buff_id должен быть в BUFF_DB и присутствовать в инвентаре;
          * тот же buff_id уже активен → ОБНОВЛЕНИЕ времени: expires =
            now + duration (НЕ прибавляется к остатку);
          * бафы одного kind СТАКАЮТСЯ аддитивно — можно повесить все 4 вида
            опыта сразу (сумма значений, см. get_buff_multiplier).

        Returns:
            (success, message) — message для UI-лога (уже на русском).
        """
        import time as _time

        from pockie_rpg.config import get_buff

        buff = get_buff(buff_id)
        if buff is None:
            return False, "Неизвестный баф"
        if self.inv_count_item(buff_id) <= 0:
            return False, "Бафа нет в инвентаре"

        now = _time.time()
        dur = float(buff["duration_sec"])
        for entry in self.active_buffs:
            if entry.get("buff_id") == buff_id:
                # Stage 181 — повторная активация ОБНОВЛЯЕТ время (не +dur).
                entry["expires_ts"] = now + dur
                break
        else:
            self.active_buffs.append({"buff_id": buff_id, "expires_ts": now + dur})

        if not self.inv_remove(buff_id):
            # Инвентарь изменился между проверкой и удалением (defensive).
            self.active_buffs = [
                b for b in self.active_buffs
                if not (b.get("buff_id") == buff_id and b.get("expires_ts", 0) > now)
            ]
            return False, "Не удалось списать баф из инвентаря"
        return True, f"{buff['name']} активирован"

    def get_buff_multiplier(self, kind: str) -> float:
        """Суммарный множитель активных бафов данного kind (1.0 = нет бафа).

        Stage 181 — бафы одного kind СТАКАЮТСЯ аддитивно: 50+100+150+200% =
        +500% → множитель ×6.0. "atk" так же (+10% и +25% = +35% → ×1.35).
        Истёкшие бафы чистятся лениво перед подсчётом.
        """
        from pockie_rpg.config import get_buff

        self._prune_expired_buffs()
        total = 0
        for entry in self.active_buffs:
            buff = get_buff(entry.get("buff_id", ""))
            if buff is None or buff.get("kind") != kind:
                continue
            total += int(buff.get("value", 0))
        return 1.0 + total / 100.0

    def get_active_buffs_ui(self) -> list[dict]:
        """Список активных бафов для UI (иконки + таймеры).

        Returns: [{"buff_id", "name", "icon_filename", "remaining_sec",
                   "duration_sec"}] — отсортировано по убыванию остатка.
        """
        import time as _time

        from pockie_rpg.config import get_buff

        self._prune_expired_buffs()
        now = _time.time()
        out: list[dict] = []
        for entry in self.active_buffs:
            buff = get_buff(entry.get("buff_id", ""))
            if buff is None:
                continue
            remaining = max(0.0, entry.get("expires_ts", 0.0) - now)
            out.append({
                "buff_id": entry["buff_id"],
                "name": buff["name"],
                "icon_filename": buff.get("icon_filename"),
                "remaining_sec": remaining,
                "duration_sec": float(buff["duration_sec"]),
            })
        out.sort(key=lambda d: -d["remaining_sec"])
        return out

    # ------------------------------------------------------------------
    # Stage 22-23 — Direct dynamic stat recalculation + cached snapshot
    # ------------------------------------------------------------------

    def get_gear_bonuses(self) -> dict[str, int]:
        """Sum scaled stat bonuses from gear items (excludes outfit slot).

        Stage 47 — applies enchant bonus per slot: each equipped item's stats
        are multiplied by (1 + enchant_level * ENCHANT_STAT_MULTIPLIER).

        Stage 70 — TITLES SYSTEM: the active title's stat bonuses are added
        to the gear bonuses dict (so they flow through recalc_stats like gear).

        The outfit slot is handled separately in recalc_stats() via
        OUTFITS_DB base_stats. Only the 7 gear slots contribute here.
        """
        from pockie_rpg.data.item_db import get_enchanted_stat, scale_gear_stat
        bonuses: dict[str, int] = {}
        for slot, item_id in self.equipped_gear.items():
            if slot == "outfit":
                continue  # outfit handled separately
            if item_id is None:
                continue
            # Stage 108 — resolve via get_item_definition (supports both
            # static EQUIPMENT_DB items and procedural generated_weapons).
            item = self.get_item_definition(item_id)
            if item is None:
                continue
            # Stage 116 — enchant level per ITEM-ID (not per-slot).
            enchant_lvl = self.gear_enchants.get(item_id, 0) if hasattr(self, "gear_enchants") else 0
            for stat, base_val in item.get("stats", {}).items():
                scaled = scale_gear_stat(base_val, item.get("item_level", 1))
                enchanted = get_enchanted_stat(scaled, enchant_lvl)
                bonuses[stat] = bonuses.get(stat, 0) + enchanted
        # Stage 70 — add active title bonuses.
        if getattr(self, "active_title", None) is not None:
            from pockie_rpg.data.titles_db import get_title_stats
            title_stats = get_title_stats(self.active_title)
            for stat, val in title_stats.items():
                bonuses[stat] = bonuses.get(stat, 0) + val
        return bonuses

    def recalc_stats(self, *, use_cache: bool = False) -> CharacterStats:
        """Direct dynamic stat recalculation + cache (Stage 40 — BMV system).

        Аудит 2026-09 — параметр ``use_cache``: чар-лист звал recalc_stats()
        60×/сек «на всякий случай» (пересчёт = обход 8 слотов шмота ×
        enchant/scale + 24 gem-слота + ~30 полей + аллокация CharacterStats).
        Теперь UI может запросить кэш; возврат кэша безопасен только при
        НЕактивных бафах (бафы истекают по РЕАЛЬНОМУ времени и меняют
        множители между кадрами).

        ВАЖНО: все мутирующие стат методы (equip/unequip/enchant/gem/level/
        баф-активация) по-прежнему зовут recalc_stats() БЕЗ use_cache —
        форс-пересчёт, семантика не изменилась.

        Stage 40 — BMV (Basic Modifier Value) from outfit determines stat
        efficiency. Higher BMV = each point of that attribute is MORE effective.

        Flow:
            1. base (10/10/10) + outfit base_stats → current attributes
            2. gear bonuses → final attributes
            3. BMV formulas → derived secondary stats

        Stage 103 formulas (outfit bmv_price for player, default 20 for mobs):
            min_atk = int((10 + STR*5 + gear_min + gem_min) * (1 + atk_mul_pct/100))
            max_atk = int((base_min*1.5 + gear_max) * (1 + atk_mul_pct/100))
            max_hp  = 100 + STA*20 + gear_hp + gem_hp + (level-1)*LEVEL_UP_HP
            defense = 5 + STA*2 + gear_def + gem_def
            speed   = 1.0 + (AGI/bmv_agi + gear_speed)/100
            atk_time = max(ATK_TIME_MIN_MS, ATK_TIME_BASE_MS / speed)
            ratings (hit/dodge/tough/crit/block/pierce/antiblock) — Step 1-3
            ниже: Base_Flat → % multiplier → Final_Rating (см. formulas.py).
        """
        # Аудит 2026-09 — кэш: валиден, если есть снимок и нет активных бафов
        # (бафы меняют множители xp/atk по времени — кэш был бы протухшим).
        if use_cache and self.stats is not None and not self.active_buffs:
            return self.stats
        from pockie_rpg.data.item_db import get_outfit

        # 1. Get outfit base_stats. Stage 138 — заточенный инстанс резолвится
        # к своей базовой модели (бонусы base_stats * (1 + 0.03*plus)).
        outfit_model = self.equipped_outfit
        if outfit_model.startswith("outfit_inst_"):
            inst = self.outfit_instances.get(outfit_model)
            outfit_model = inst["outfit_id"] if inst else None
        outfit = get_outfit(outfit_model) if outfit_model else None
        if outfit is not None:
            outfit_base = outfit.get("base_stats", {})
            # Stage 138 — заточка костюма: base_stats * (1 + 0.10*plus) (Stage 165).
            # Плюс берём у ИНСТАНСА (outfit_instances), либо outfit_plus для базы.
            from pockie_rpg.config import outfit_synth_stat_multiplier
            equipped_plus = self._outfit_plus_of(self.equipped_outfit, self)
            synth_mult = outfit_synth_stat_multiplier(equipped_plus)
            # Stage 165 — округление половина вверх: 10*1.1 = 11, 15*1.1 = 17,
            # 8*1.1 = 9 (int() обрезал до 10/16/8 — синтез не менял статы).
            current_str = self.strength + int(outfit_base.get("strength", 0) * synth_mult + 0.5)
            current_agi = self.agility + int(outfit_base.get("agility", 0) * synth_mult + 0.5)
            current_sta = self.stamina + int(outfit_base.get("stamina", 0) * synth_mult + 0.5)
            # Аудит 2026-09 — мёртвый блок "bmv = outfit.get('bmv', {})" удалён:
            # bmv_str/agi/sta безусловно перезаписываются ниже из bmv_price
            # (или дефолтами), а старые дефолты 20/40/10 рассинхронизированы
            # с DEFAULT_BMV_PRICE_* (20/20/20).
        else:
            current_str = self.strength
            current_agi = self.agility
            current_sta = self.stamina

        # 2. Collect gear bonuses (from 7 gear slots — outfit excluded).
        bonuses = self.get_gear_bonuses()
        gear_hp = bonuses.get("max_hp", 0)
        gear_mp = bonuses.get("max_mp", 0)
        gear_def = bonuses.get("defense", 0)
        gear_min = bonuses.get("min_atk", 0)
        gear_max = bonuses.get("max_atk", 0)
        gear_speed = bonuses.get("speed", 0)
        gear_atk_mul = bonuses.get("atk_mul", 0)       # +% attack multiplier
        # Stage 52 — crit/tough RATINGS from gear (flat, no cap).
        gear_crit_rating = bonuses.get("crit_rating", 0)
        gear_tough_rating = bonuses.get("tough_rating", 0)

        # Stage 51 — GEM BONUSES (flat, from socketed gems).
        gem_min_atk = self.get_total_gem_bonus("min_atk")
        gem_max_hp = self.get_total_gem_bonus("max_hp")
        gem_def = self.get_total_gem_bonus("defense")
        # Stage 52 — gem crit/tough ratings.
        gem_crit_rating = self.get_total_gem_bonus("crit_rating")
        gem_tough_rating = self.get_total_gem_bonus("tough_rating")
        # Stage 53 — gems now give STR/AGI/STA directly (added to primary stats).
        gem_str = self.get_total_gem_bonus("strength")
        gem_agi = self.get_total_gem_bonus("agility")
        gem_sta = self.get_total_gem_bonus("stamina")
        # Add gem STR/AGI/STA to current stats (before deriving secondary stats).
        current_str += gem_str
        current_agi += gem_agi
        current_sta += gem_sta

        # 3. Stage 103 — POCKIE NINJA ORIGINAL COMBAT MATH (per task spec).
        # All secondary stats derive from primary stats via the equipped
        # outfit's BMV-Цена (cost). Lower bmv_price = each stat more effective.
        from pockie_rpg.config import (
            DEFAULT_BMV_PRICE_AGI,
            DEFAULT_BMV_PRICE_STA,
            DEFAULT_BMV_PRICE_STR,
            DEFAULT_GROWTH_AGI,
            DEFAULT_GROWTH_AGI_MAX,
            DEFAULT_GROWTH_STA,
            DEFAULT_GROWTH_STA_MAX,
            DEFAULT_GROWTH_STR,
            DEFAULT_GROWTH_STR_MAX,
            STA_TO_DEF,
            STA_TO_HP,
            STR_TO_ATK,
            calc_atk_mul_pct,
            calc_crit_rating,
            calc_dodge_rating,
            calc_hit_rating,
            calc_speed,
            calc_tough_rating,
        )

        # Stage 103 — get BMV-Цена (cost) + BMV-Прирост (growth) from outfit.
        if outfit is not None:
            bmv_price = outfit.get("bmv_price", outfit.get("bmv", {}))
            bmv_str = bmv_price.get("strength", DEFAULT_BMV_PRICE_STR)
            bmv_agi = bmv_price.get("agility", DEFAULT_BMV_PRICE_AGI)
            bmv_sta = bmv_price.get("stamina", DEFAULT_BMV_PRICE_STA)
            # Stage 103 — growth (current/max per stat) for UI display.
            growth_dict = outfit.get("growth", {})
            growth_str = growth_dict.get("strength", {}).get("current", DEFAULT_GROWTH_STR)
            growth_agi = growth_dict.get("agility", {}).get("current", DEFAULT_GROWTH_AGI)
            growth_sta = growth_dict.get("stamina", {}).get("current", DEFAULT_GROWTH_STA)
            growth_str_max = growth_dict.get("strength", {}).get("max", DEFAULT_GROWTH_STR_MAX)
            growth_agi_max = growth_dict.get("agility", {}).get("max", DEFAULT_GROWTH_AGI_MAX)
            growth_sta_max = growth_dict.get("stamina", {}).get("max", DEFAULT_GROWTH_STA_MAX)
        else:
            bmv_str = DEFAULT_BMV_PRICE_STR
            bmv_agi = DEFAULT_BMV_PRICE_AGI
            bmv_sta = DEFAULT_BMV_PRICE_STA
            growth_str = DEFAULT_GROWTH_STR
            growth_agi = DEFAULT_GROWTH_AGI
            growth_sta = DEFAULT_GROWTH_STA
            growth_str_max = DEFAULT_GROWTH_STR_MAX
            growth_agi_max = DEFAULT_GROWTH_AGI_MAX
            growth_sta_max = DEFAULT_GROWTH_STA_MAX

        # Stage 103 — legacy BMV-driven multipliers (kept for backward compat
        # with old UI code; Stage 103 uses linear base formulas directly).
        # Stage 180 — баф на атаку добавляется к общему множителю
        # (atk_mul_pct = Скрытый_Процент_Силы + gear_atk_mul + баф).
        atk_mul_pct = calc_atk_mul_pct(current_str, bmv_str) + gear_atk_mul \
            + int((self.get_buff_multiplier("atk") - 1.0) * 100)
        # Stage 169 (аудит 4.4): max_hp_mul_pct/def_mul_pct удалены — считались,
        # но ни разу не читались (поля CharacterStats мертвы).

        # Stage 106 — IRON RULE: ANY '%' on gear is ALWAYS a MULTIPLIER
        # for the flat rating base. NO item may add pure % to final chance.
        #
        # Bug fix (Stage 105 → 106): legacy % keys (dodge_mul, hit_chance,
        # parry_chance, pierce, crit_chance) were previously converted to
        # flat rating via GEAR_PCT_TO_RATING (16), which effectively gave
        # direct +X% to final chance. E.g., dodge_mul: 5 → +80 flat rating
        # → +5% final chance (BUG). Now they are ALL multipliers (Step 2).
        #
        # Only PURE flat rating keys (*_rating) remain in Step 1 (Base_Flat).
        #   - dodge_rating, hit_rating, tough_rating, crit_rating,
        #     block_rating, pierce_rating  (pure flat bonuses from gear/gems)
        from pockie_rpg.config import (
            apply_pct_bonus,
            calc_block_rating,
            calc_pierce_rating,
            collect_rating_pct,
        )

        # Step 1 — Base_Flat = stats + gear_flat + gem_flat (pure flat only).
        # NO % conversion here — all % keys (legacy and new) go to Step 2.
        # Hit_Rating: floor(STR / bmv_price_str) + flat_gear_hit_rating - STR_THRESHOLD (min 0).
        #   NOTE: hit_chance (legacy % key) is NO LONGER here — it's a multiplier now.
        gear_hit_flat = bonuses.get("hit_rating", 0)
        hit_base_flat = calc_hit_rating(current_str, bmv_str, gear_hit_flat)
        # Dodge_Rating: floor(AGI / bmv_price_agi) + flat_gear_dodge_rating.
        #   NOTE: dodge_mul (legacy % key) is NO LONGER here — it's a multiplier now.
        gear_dodge_flat = bonuses.get("dodge_rating", 0)
        dodge_base_flat = calc_dodge_rating(current_agi, bmv_agi, gear_dodge_flat)
        # Tough_Rating: floor(STR/bmv_str) + floor(STA/bmv_sta) + flat_gear_tough + gem_tough.
        tough_base_flat = calc_tough_rating(
            current_str, current_sta, bmv_str, bmv_sta,
            gear_tough_rating + gem_tough_rating,
        )
        # Crit_Rating: flat_gear_crit_rating + gem_crit (no STR contribution).
        #   NOTE: crit_chance (legacy % key) is NO LONGER here — it's a multiplier now.
        crit_base_flat = calc_crit_rating(current_str, gear_crit_rating + gem_crit_rating)
        # Block_Rating: floor(STR / bmv_price_str) + flat_gear_block_rating (NO threshold).
        #   NOTE: parry_chance (legacy % key) is NO LONGER here — it's a multiplier now.
        gear_block_flat = bonuses.get("block_rating", 0)
        block_base_flat = calc_block_rating(current_str, bmv_str, gear_block_flat)
        # Pierce_Rating: flat_gear_pierce_rating only (no STR contribution).
        #   NOTE: pierce (legacy % key) is NO LONGER here — it's a multiplier now.
        gear_pierce_flat = bonuses.get("pierce_rating", 0)
        pierce_base_flat = calc_pierce_rating(gear_pierce_flat)
        # Stage 137 — Антиблок: flat_gear only (снимает чужой блок, /16%).
        gear_antiblock_flat = bonuses.get("antiblock_rating", 0)
        antiblock_base_flat = max(0, gear_antiblock_flat)

        # Step 2 — collect ALL percentage modifiers (new *_pct + legacy % keys).
        # collect_rating_pct() sums both *_pct and legacy aliases (dodge_mul,
        # hit_chance, parry_chance, pierce, crit_chance) into Pct_Sum.
        hit_pct_sum    = collect_rating_pct(bonuses, "hit")
        dodge_pct_sum  = collect_rating_pct(bonuses, "dodge")
        tough_pct_sum  = collect_rating_pct(bonuses, "tough")
        crit_pct_sum   = collect_rating_pct(bonuses, "crit")
        block_pct_sum  = collect_rating_pct(bonuses, "block")
        pierce_pct_sum = collect_rating_pct(bonuses, "pierce")
        antiblock_pct_sum = collect_rating_pct(bonuses, "antiblock")

        # Step 3 — apply percentage multiplier (floor truncation).
        # Final_Rating = floor(Base_Flat * (1 + Pct_Sum / 100))
        hit_rating    = apply_pct_bonus(hit_base_flat, hit_pct_sum)
        dodge_rating  = apply_pct_bonus(dodge_base_flat, dodge_pct_sum)
        tough_rating  = apply_pct_bonus(tough_base_flat, tough_pct_sum)
        crit_rating   = apply_pct_bonus(crit_base_flat, crit_pct_sum)
        block_rating = apply_pct_bonus(block_base_flat, block_pct_sum)
        pierce_rating = apply_pct_bonus(pierce_base_flat, pierce_pct_sum)
        # Stage 137 — Антиблок: НЕТ КАПА (оригинал: рейтинги могут быть 5000+).
        antiblock_rating = apply_pct_bonus(antiblock_base_flat, antiblock_pct_sum)

        # Stage 103 — speed via BMV-Цена (linear, no cap).
        speed = calc_speed(current_agi, bmv_agi, gear_speed + 0)
        # atk_time kept for backward compat (derived from speed): faster speed = lower atk_time
        # Stage 170 — константы вместо магических чисел (значения прежние).
        atk_time = max(
            ATK_TIME_MIN_MS,
            int(ATK_TIME_BASE_MS / max(ATK_TIME_SPEED_FLOOR, speed)),
        )

        # Stage 107 — ATTACK (multiplicative scheme, per task spec).
        # Strict Rule: min and max are computed INDEPENDENTLY, then BOTH are
        # multiplied by the same percentage multiplier (atk_mul_pct).
        #
        # Step 1 — Total_Flat_Min/Max (independent flat bases):
        #   Базовый_Мин_Урон_Без_Вещей = 10 + STR * STR_TO_ATK  (= 10 + STR*5)
        #   Базовый_Макс_Урон_Без_Вещей = (10 + STR * STR_TO_ATK) * 1.5
        #   Total_Flat_Min = Базовый_Мин + gear_min + gem_min
        #   Total_Flat_Max = Базовый_Макс + gear_max + gem_max
        #
        # Step 2 — atk_mul_pct (percentage multiplier):
        #   Скрытый_Процент_Силы = floor(STR / bmv_price_str)  ← integer floor
        #   gear_atk_mul = sum of +X% attack multipliers from gear
        #   atk_mul_pct = Скрытый_Процент_Силы + gear_atk_mul
        #
        # Step 3 — Final multiplication + floor (int truncation):
        #   min_atk = int( Total_Flat_Min * (1 + atk_mul_pct/100) )
        #   max_atk = int( Total_Flat_Max * (1 + atk_mul_pct/100) )
        #
        # Example (per task spec):
        #   STR=20, bmv_price_str=30, gear +3 min / +6 max / +5% atk_mul
        #   Базовый_Мин = 10 + 20*5 = 110
        #   Базовый_Макс = 110 * 1.5 = 165
        #   Total_Flat_Min = 110 + 3 + 0 = 113
        #   Total_Flat_Max = 165 + 6 + 0 = 171
        #   Скрытый_Процент_Силы = floor(20/30) = 0
        #   atk_mul_pct = 0 + 5 = 5
        #   min_atk = int(113 * 1.05) = int(118.65) = 118
        #   max_atk = int(171 * 1.05) = int(179.55) = 179
        #   RESULT: 118-179 ✓
        base_min_no_gear = 10 + current_str * STR_TO_ATK              # 10 + STR*5
        base_max_no_gear = base_min_no_gear * 1.5                     # min * 1.5
        total_flat_min = base_min_no_gear + gear_min + gem_min_atk    # independent
        total_flat_max = base_max_no_gear + gear_max + 0              # independent (no gem_max)
        # atk_mul_pct = floor(STR / bmv_str) + gear_atk_mul (already computed above)
        # Stage 107 — apply percentage multiplier (multiplicative, floor truncation)
        min_atk = int(total_flat_min * (1 + atk_mul_pct / 100))
        max_atk = int(total_flat_max * (1 + atk_mul_pct / 100))

        base_hp = int(100 + current_sta * STA_TO_HP + gear_hp + gem_max_hp)
        # Stage 133 — level HP bonus applied HERE (single source of truth).
        # Previously added only by the manual CharacterStats rebuild in
        # gain_xp, so every from_dict/recalc call silently dropped it.
        from pockie_rpg.config import LEVEL_UP_HP
        max_hp = base_hp + (self.level - 1) * LEVEL_UP_HP

        base_def = int(5 + current_sta * STA_TO_DEF + gear_def + gem_def)
        defense = base_def

        self.stats = CharacterStats(
            total_strength=current_str,
            total_agility=current_agi,
            total_stamina=current_sta,
            max_hp=max_hp,
            max_mp=self.max_mp + gear_mp,
            defense=defense,
            min_atk=min_atk,
            max_atk=max_atk,
            atk_time=atk_time,
            hit_rating_ui=int(hit_rating),
            dodge_rating_ui=int(dodge_rating),
            speed=speed,
            crit_rating=crit_rating,
            tough_rating=tough_rating,
            # Stage 104 — BLOCK & PIERCE RATINGS.
            block_rating_ui=block_rating,
            pierce_rating_ui=pierce_rating,
            # Stage 137 — АНТИБЛОК rating (flat, /16%, no cap).
            antiblock_rating_ui=antiblock_rating,
            # Stage 103 — BMV-Цена (cost) fields.
            bmv_price_str=bmv_str,
            bmv_price_agi=bmv_agi,
            bmv_price_sta=bmv_sta,
            # Stage 103 — BMV-Прирост (growth) fields for UI display.
            growth_str=growth_str,
            growth_agi=growth_agi,
            growth_sta=growth_sta,
            growth_str_max=growth_str_max,
            growth_agi_max=growth_agi_max,
            growth_sta_max=growth_sta_max,
        )
        return self.stats

    def get_effective_max_mp(self) -> int:
        """Base max_mp + amulet's max_mp bonus (if equipped)."""
        return self.recalc_stats().max_mp

    def get_max_hp(self) -> int:
        """max_hp via Stage 22 formula: total_stamina * 15 + 300."""
        return self.recalc_stats().max_hp

    def get_item_definition(self, item_id: str) -> dict | None:
        """Stage 108/113 — Resolve an item_id to its definition dict.

        Checks both EQUIPMENT_DB (static items) and self.generated_weapons
        (procedural weapons). Returns the item dict, or None if not found.

        Stage 113 — if a static item has no 'rarity' field, automatically
        assigns 'Grey' so ALL items display rarity-colored backgrounds and
        tooltip prefixes consistently.

        Args:
            item_id: static item id (e.g., "weapon_wooden") OR generated
                     weapon instance id (e.g., "gen_w_001").

        Returns:
            The item definition dict, or None.
        """
        from pockie_rpg.data.item_db import get_equipment, get_outfit
        # Check generated weapons first (instance IDs start with "gen_w_").
        if item_id.startswith("gen_w_"):
            return self.generated_weapons.get(item_id)
        # Stage 138 — заточенные костюмы-инстансы ("outfit_inst_<n>").
        if item_id.startswith("outfit_inst_"):
            inst = self.outfit_instances.get(item_id)
            if inst is None:
                return None
            model = get_outfit(inst["outfit_id"])
            if model is None:
                return None
            from pockie_rpg.config import outfit_synth_required_level
            item = dict(model)
            item["slot"] = "outfit"
            item["rarity"] = "Outfit"
            item["item_level"] = 1
            item["plus"] = int(inst.get("plus", 0))
            item["level_requirement"] = outfit_synth_required_level(item["plus"])
            item["is_outfit_instance"] = True
            return item
        # Fall back to static EQUIPMENT_DB.
        item = get_equipment(item_id)
        # Stage 180 — бафы-расходники: BUFF_DB → псевдо-предмет
        # (имя/иконка/описание для инвентаря и тултипов).
        if item is None:
            from pockie_rpg.data.item_db import get_buff_item
            item = get_buff_item(item_id)
        # Stage 113 — ensure ALL items have a rarity field.
        # Static items from EQUIPMENT_DB don't have 'rarity' — default to "Grey".
        if item is not None and not item.get("rarity"):
            item = dict(item)  # shallow copy to avoid mutating EQUIPMENT_DB
            item["rarity"] = "Grey"
        return item

    def equip_gear_item(
        self,
        item_id: str,
        source_slot: tuple[int, int] | None = None,
    ) -> bool:
        """Equip an item from inventory into its `equipped_gear` slot.

        Looks up the item in EQUIPMENT_DB (or generated_weapons for procedural
        weapons), places it in the slot named by the item's `slot` field,
        returns the previously-equipped item (if any) back to the inventory,
        then force-refreshes the cached CharacterStats snapshot.

        Stage 31 — level requirement: if the item's item_level is higher
        than the player's level, the item CANNOT be equipped (returns False).

        Stage 108 — level_requirement field: procedural weapons have an
        explicit `level_requirement` field. If present, it takes precedence
        over `item_level` for the equip gate. Player level must be >=
        level_requirement to equip.

        Stage 66 — **slot-preserving swap**: when ``source_slot`` is provided
        (as ``(page, slot_idx)``), the old equipped item is placed directly
        into THAT exact slot — not into the first empty slot via inv_add().

        Args:
            item_id: the equipment id to equip (static or generated).
            source_slot: optional ``(page, slot_idx)`` of the inventory slot
                the item was taken from.

        Returns True on success, False if the item is unknown, not in the
        inventory, or above the player's level.
        """
        item = self.get_item_definition(item_id)
        if item is None:
            return False

        # --- Resolve the source slot ---
        if source_slot is not None:
            page, idx = source_slot
            slots = self.inv_page_slots(page)
            if not (0 <= idx < len(slots)) or slots[idx] != item_id:
                source_slot = self.inv_find(item_id)
        else:
            source_slot = self.inv_find(item_id)

        if source_slot is None:
            return False  # item not in inventory at all.

        # Stage 108 — level gate (prefer level_requirement if present).
        level_req = item.get("level_requirement", item.get("item_level", 1))
        if level_req > self.level:
            return False

        slot = item["slot"]
        # Stage 146 — СТРОГОЕ распределение аксессуаров по type:
        # ring -> только accessory (КОЛЬЦО); amulet -> только accessory2
        # (АМУЛ). Никаких кросс-дропов.
        if slot == "accessory":
            if item.get("type") == "amulet":
                slot = "accessory2"
            else:
                slot = "accessory"
        old = self.equipped_gear.get(slot)
        self.equipped_gear[slot] = item_id
        # Stage 133 — keep the two outfit sources of truth in sync at runtime
        # (same rule as from_dict: gear slot "outfit" wins).
        if slot == "outfit":
            self.equipped_outfit = item_id

        # --- Place the old item back ---
        page, idx = source_slot
        slots = self.inv_page_slots(page)
        slots[idx] = old  # None if the gear slot was empty, else old item_id.

        # Stage 23 — force-refresh the cached snapshot immediately
        # (аудит 2026-09: единая точка _refresh_stats).
        self._refresh_stats()
        # Stage 172 — сюжетные квесты: цель use_item («надень предмет»).
        self.notify_story_quest_item_used(item_id)
        return True

    def give_test_item(self, item_level: int, rarity_color: str, item_type: str = "weapon") -> str | None:
        """Stage 112 — Unified debug method: generate and spawn any item in inventory.

        Generates a procedural item (weapon or armor) via generate_item() and
        places it directly in the player's inventory.

        Args:
            item_level: int from WEAPON_LEVELS (1, 5, 10, 15, 20, 25).
            rarity_color: str from RARITY_COLORS ("Grey", "Blue", "Purple", "Gold", "Red").
            item_type: "weapon" or "armor".

        Returns:
            The generated item's instance ID (e.g., "gen_w_001") on success,
            or None if generation failed or inventory is full.
        """
        from pockie_rpg.data.item_db import generate_item
        try:
            item = generate_item(item_level, rarity_color, item_type)
        except ValueError:
            return None

        # Generate unique instance ID.
        self._gen_w_counter += 1
        instance_id = f"gen_w_{self._gen_w_counter:03d}"
        self.generated_weapons[instance_id] = item

        # Place in inventory (inv_add handles multi-page + visual capacity).
        if not self.inv_add(instance_id):
            # Inventory full — rollback.
            del self.generated_weapons[instance_id]
            self._gen_w_counter -= 1
            return None
        return instance_id

    def buffed_xp(self, amount: int) -> int:
        """Stage 184 — XP с учётом xp-бафов (без зачисления).

        Единая формула с gain_xp: int(amount * get_buff_multiplier("xp")).
        Нужна UI (окно награды), чтобы показать бонус отдельной строкой.
        """
        return int(amount * self.get_buff_multiplier("xp"))

    def gain_xp(self, amount: int) -> bool:
        """Add XP. Returns True if leveled up.

        Stage 180 — XP-баф применяется ЗДЕСЬ (единая точка для боёв, башни,
        гаунтлета, квестов): amount умножается на get_buff_multiplier("xp").

        Stage 103 — BMV-Прирост (level-up growth) per original Pockie Ninja:
            On every level-up: stat += outfit.growth[stat].current.
            Different costumes grow stats differently (build diversity).

            Example (suit_ichigo): STR += 0.6, AGI += 1.35, STA += 0.5 per level.
                     (suit_ninja_evasion): STR += 0.3, AGI += 2.0, STA += 0.5.
                     (suit_ogre_brute):    STR += 0.8, AGI += 0.3, STA += 1.7.

            UI shows: "Ловкость 41 (+1.35) | Макс (+1.65)" where +1.35 is current
            growth and +1.65 is the maximum possible (for upgradeable outfits).

            HP: +50 per level (linear base growth, same for all costumes).
            MP: +10 per level.
        """
        from pockie_rpg.config import (
            DEFAULT_GROWTH_AGI,
            DEFAULT_GROWTH_STA,
            DEFAULT_GROWTH_STR,
            LEVEL_UP_MP,
        )
        from pockie_rpg.data.item_db import get_outfit

        # Stage 180 — XP-баф (единая точка входа любого опыта).
        amount = self.buffed_xp(amount)

        # Stage 103 — get BMV-Прирост (growth) from equipped outfit.
        outfit = get_outfit(self.equipped_outfit)
        if outfit is not None:
            growth_dict = outfit.get("growth", {})
            growth_str = growth_dict.get("strength", {}).get("current", DEFAULT_GROWTH_STR)
            growth_agi = growth_dict.get("agility", {}).get("current", DEFAULT_GROWTH_AGI)
            growth_sta = growth_dict.get("stamina", {}).get("current", DEFAULT_GROWTH_STA)
        else:
            growth_str = DEFAULT_GROWTH_STR
            growth_agi = DEFAULT_GROWTH_AGI
            growth_sta = DEFAULT_GROWTH_STA

        if self.level >= MAX_LEVEL:
            self.current_xp = min(self.current_xp + amount, self.max_xp)
            return False

        self.current_xp += amount
        leveled = False

        while self.current_xp >= self.max_xp:
            self.current_xp -= self.max_xp
            self.level += 1
            # Stage 103/133 — apply BMV-Прирост from costume. Per-field
            # lazy-init (not all-or-nothing): a partially restored/None
            # accumulator must never crash the += below.
            if self._str_accum is None:
                self._str_accum = float(self.strength)
            if self._agi_accum is None:
                self._agi_accum = float(self.agility)
            if self._sta_accum is None:
                self._sta_accum = float(self.stamina)
            self._str_accum += growth_str   # Stage 103 — costume BMV-Прирост
            self._agi_accum += growth_agi   # (e.g., suit_ichigo: +0.6/+1.35/+0.5)
            self._sta_accum += growth_sta
            self.strength = int(self._str_accum)
            self.agility = int(self._agi_accum)
            self.stamina = int(self._sta_accum)
            self.max_mp += LEVEL_UP_MP                         # +10
            self.max_xp = self.level * LEVEL_XP_CURVE
            leveled = True
            if self.level >= MAX_LEVEL:
                self.level = MAX_LEVEL
                self.current_xp = min(self.current_xp, self.max_xp)
                break
        # Stage 133 — level HP bonus moved INTO recalc_stats (single source),
        # so loading an old save no longer slices max_hp (bug: (level-1)*50
        # was only re-applied by the manual CharacterStats rebuild below).
        if leveled:
            self.recalc_stats()
            self._cached_hp = self.stats.max_hp
            self._cached_mp = self.stats.max_mp
        return leveled

    def gain_gold(self, amount: int) -> None:
        self.gold = max(0, self.gold + max(0, amount))

    def reset_progression(self) -> None:
        self.level = 1
        self.current_xp = 0
        self.max_xp = LEVEL_XP_CURVE
        self.defeated_mobs.clear()
        # Stage 113/165 — тестовая экономика (Stage 170 — константы config).
        self.gold = TEST_START_GOLD
        self.coupons = TEST_START_COUPONS
        # Stage 39 — base 10/10/10/200 (outfit adds the rest).
        self.strength = 10
        self.agility = 10
        self.stamina = 10
        # Stage 133 — restart growth accumulators from the reset base
        # (stale pre-reset values would keep accumulating into new levels).
        self._str_accum = 10.0
        self._agi_accum = 10.0
        self._sta_accum = 10.0
        self.max_mp = 200
        self.equipped_outfit = "suit_ichigo"
        self.active_skills = list(ROLE_ICHIGO.skills)
        self.equipped_gear = {
            "weapon": None, "head": None, "body": None, "hands": None,
            "belt": None, "boots": None, "accessory": None,
            "outfit": "suit_ichigo",
        }
        from pockie_rpg.data.item_db import starter_items
        # Stage 64 — reset to fresh paged inventory and add starter items.
        self.inventory = _empty_inventory()
        for it in starter_items():
            self.inv_add(it)
        # Stage 47 — reset all enchants to 0.
        self.gear_enchants = {}  # Stage 116 — per-item-id, not per-slot
        # Stage 51 — reset gem inventory + gem slots.
        self.gem_inventory = []
        self._gem_id_counter = 0
        self.gear_gem_slots = {
            "weapon": [None, None, None], "head": [None, None, None],
            "body": [None, None, None], "hands": [None, None, None],
            "belt": [None, None, None], "boots": [None, None, None],
            "accessory": [None, None, None],
        }
        # Stage 89 — reset Tower mode state.
        # Stage 90 — attempt limit removed; Stage 134 — legacy attempt fields deleted.
        from pockie_rpg.config import TOWER_DEFAULT_START_FLOOR
        self.tower_current_floor = TOWER_DEFAULT_START_FLOOR
        self.tower_highest_floor = 0
        self.tower_shards = 0
        self.tower_pending_xp = 0
        # Stage 182 — сброс сессии снимает ВСЕ активные бафы.
        self.active_buffs = []
        # Stage 95 — reset daily quests.
        self.daily_quest_progress = {}
        self.daily_quest_claimed = []
        self.daily_quest_date = ""
        self.tower_materials = {}
        self.tower_first_clear_claimed = []
        # Stage 134 — reset slot machine cooldown.
        # Stage 163 — история прокруток удалена (сбрасывать больше нечего).
        self.slot_next_roll_ts = None
        # Stage 172 — reset story quest chain (новый забег с первого квеста).
        self.story_quests_active = []
        self.story_quests_goal_done = []
        self.story_quests_completed = []
        # Stage 173 — счётчики kill_mobs-целей тоже под ноль.
        self.story_quests_kill_progress = {}
        self.recalc_stats()  # refresh self.stats + cached HP/MP
        self._cached_hp = self.stats.max_hp
        self._cached_mp = self.stats.max_mp

    def upgrade_gear(self, slot: str) -> bool:
        """Stage 47/115/116 — FORGE: upgrade the enchant level of the item in `slot`.

        Stage 116 — enchant is now per-ITEM-ID (not per-slot). When you
        unequip an item, it keeps its enchant level. Equipping a new item
        in the same slot starts at enchant 0.

        Checks: slot has an equipped item, enchant < MAX_ENCHANT, player has
        enough gold. Deducts gold, increments enchant, refreshes stats.

        Returns True on success, False otherwise.
        """
        from pockie_rpg.config import MAX_ENCHANT
        from pockie_rpg.data.item_db import get_enchant_cost
        item_id = self.equipped_gear.get(slot)
        if item_id is None:
            return False
        item = self.get_item_definition(item_id)
        if item is None:
            return False
        # Stage 116 — enchant keyed by item_id, not slot.
        current = self.gear_enchants.get(item_id, 0)
        if current >= MAX_ENCHANT:
            return False
        cost = get_enchant_cost(current)
        if self.gold < cost:
            return False
        self.gold -= cost
        self.gear_enchants[item_id] = current + 1
        self.recalc_stats()
        self._cached_hp = min(self._cached_hp or self.stats.max_hp, self.stats.max_hp)
        self._cached_mp = min(self._cached_mp or self.stats.max_mp, self.stats.max_mp)
        return True

    def get_enchant_level(self, item_id_or_slot: str) -> int:
        """Stage 116 — return the enchant level for an item_id.

        Stage 116 — changed from per-slot to per-item-id.
        Accepts either an item_id directly, or tries to resolve it
        from equipped_gear if it looks like a slot name.
        """
        # If it's a slot name, resolve to the equipped item_id.
        if item_id_or_slot in ("weapon", "head", "body", "hands", "belt", "boots", "accessory"):
            item_id = self.equipped_gear.get(item_id_or_slot)
            if item_id is None:
                return 0
        else:
            item_id = item_id_or_slot
        return self.gear_enchants.get(item_id, 0)

    # ------------------------------------------------------------------
    # Stage 51 — GEM SYSTEM helpers
    # ------------------------------------------------------------------

    def add_gem(self, gem_type: str, level: int = 1) -> str:
        """Create a new gem instance and add it to the gem inventory.

        Returns the unique instance id (e.g., "gem_42").
        """
        self._gem_id_counter += 1
        gem_id = f"gem_{self._gem_id_counter}"
        self.gem_inventory.append({"id": gem_id, "type": gem_type, "level": level})
        return gem_id

    def get_gem_instance(self, gem_id: str) -> dict | None:
        """Look up a gem instance by its unique id. Returns None if not found."""
        for g in self.gem_inventory:
            if g.get("id") == gem_id:
                return g
        return None

    def remove_gem_instance(self, gem_id: str) -> dict | None:
        """Remove + return a gem instance from inventory (and unequip if socketed)."""
        for i, g in enumerate(self.gem_inventory):
            if g.get("id") == gem_id:
                # Unsocket from any gear slot if present.
                for slot, slots_list in self.gear_gem_slots.items():
                    for j in range(len(slots_list)):
                        if slots_list[j] == gem_id:
                            slots_list[j] = None
                return self.gem_inventory.pop(i)
        return None

    def _refresh_stats(self) -> None:
        """Аудит 2026-09 — ЕДИНАЯ точка «recalc + кэш HP/MP».

        Раньше gem-методы звали только recalc_stats() БЕЗ обновления
        _cached_hp/_cached_mp → после вставки HP-камня current_hp не видел
        новую ёмкость до следующего equip/level-up. equip_gear_item дублиро-
        вал те же 3 строки.

        Семантика (delta): рост max_hp/max_mp зачисляет ДЕЛЬТУ в current
        (вставил камень +180 HP → current +180); уменьшение потолка клампит
        current. Это же закрывает эксплуат «переоделся = полный хил» старого
        equip-кода. Полное лечение остаётся только на level-up (gain_xp).
        """
        old_max_hp = self.stats.max_hp if self.stats is not None else None
        old_max_mp = self.stats.max_mp if self.stats is not None else None
        self.recalc_stats()
        if self.stats is None:
            return
        new_max_hp = self.stats.max_hp
        new_max_mp = self.stats.max_mp
        if old_max_hp is not None and new_max_hp >= old_max_hp:
            self._cached_hp = min(self._cached_hp + (new_max_hp - old_max_hp), new_max_hp)
        else:
            self._cached_hp = min(self._cached_hp, new_max_hp)
        if old_max_mp is not None and new_max_mp >= old_max_mp:
            self._cached_mp = min(self._cached_mp + (new_max_mp - old_max_mp), new_max_mp)
        else:
            self._cached_mp = min(self._cached_mp, new_max_mp)

    def socket_gem(self, slot: str, slot_index: int, gem_id: str) -> bool:
        """Place a gem into gear_gem_slots[slot][slot_index].

        Returns True on success, False if slot invalid, index out of range,
        or gem not in inventory.
        """
        from pockie_rpg.config import MAX_GEM_SLOTS_PER_ITEM
        if slot not in self.gear_gem_slots:
            return False
        if slot_index < 0 or slot_index >= MAX_GEM_SLOTS_PER_ITEM:
            return False
        if self.get_gem_instance(gem_id) is None:
            return False
        # If gem is already socketed somewhere, remove it first.
        for s, slots_list in self.gear_gem_slots.items():
            for j in range(len(slots_list)):
                if slots_list[j] == gem_id:
                    slots_list[j] = None
        self.gear_gem_slots[slot][slot_index] = gem_id
        self._refresh_stats()
        return True

    def unsocket_gem(self, slot: str, slot_index: int) -> bool:
        """Remove a gem from gear_gem_slots[slot][slot_index] back to inventory."""
        if slot not in self.gear_gem_slots:
            return False
        if slot_index < 0 or slot_index >= len(self.gear_gem_slots[slot]):
            return False
        if self.gear_gem_slots[slot][slot_index] is None:
            return False
        self.gear_gem_slots[slot][slot_index] = None
        self._refresh_stats()
        return True

    def upgrade_gem(self, gem_id: str) -> bool:
        """Stage 51 — upgrade a gem's level by 1 (max MAX_GEM_LEVEL).

        Checks gold cost + success chance. On failure, gold is still consumed
        but level doesn't increase. Returns True if the gem leveled up, False
        if it failed OR was already at max level OR insufficient gold.
        """
        import random as _random

        from pockie_rpg.config import MAX_GEM_LEVEL
        from pockie_rpg.data.item_db import get_gem_upgrade_chance, get_gem_upgrade_cost
        gem = self.get_gem_instance(gem_id)
        if gem is None:
            return False
        if gem["level"] >= MAX_GEM_LEVEL:
            return False
        cost = get_gem_upgrade_cost(gem["level"])
        if self.gold < cost:
            return False
        self.gold -= cost
        chance = get_gem_upgrade_chance(gem["level"])
        roll = _random.randint(1, 100)
        if roll <= chance:
            gem["level"] += 1
            self._refresh_stats()
            return True
        return False  # upgrade failed (gold consumed, no level up)

    def synthesize_gems(self, gem_a_id: str, gem_b_id: str) -> str | None:
        """Stage 51 — Synthesis: combine 2 gems of SAME type + level into 1 gem of level+1.

        Both source gems are consumed. Returns the new gem instance id on
        success, or None if: gems not found, types differ, levels differ, or
        result would exceed MAX_GEM_LEVEL.
        """
        import random as _random

        from pockie_rpg.config import MAX_GEM_LEVEL
        from pockie_rpg.data.item_db import get_synthesis_result_level
        ga = self.get_gem_instance(gem_a_id)
        gb = self.get_gem_instance(gem_b_id)
        if ga is None or gb is None:
            return None
        if ga["type"] != gb["type"]:
            return None
        result_level = get_synthesis_result_level(ga["level"], gb["level"])
        if result_level is None or result_level > MAX_GEM_LEVEL:
            return None
        # 60% success chance (flat) — Stage 170: GEM_SYNTH_SUCCESS_PCT в config.
        if _random.randint(1, 100) > GEM_SYNTH_SUCCESS_PCT:
            # Failure: both gems consumed, no result.
            self.remove_gem_instance(gem_a_id)
            self.remove_gem_instance(gem_b_id)
            return None
        new_type = ga["type"]
        self.remove_gem_instance(gem_a_id)
        self.remove_gem_instance(gem_b_id)
        new_id = self.add_gem(new_type, result_level)
        self._refresh_stats()
        return new_id

    def get_total_gem_bonus(self, stat_key: str) -> int:
        """Sum the stat bonus from all socketed gems matching stat_key."""
        from pockie_rpg.data.item_db import get_gem, get_gem_stat_bonus
        total = 0
        for slot, slots_list in self.gear_gem_slots.items():
            for gem_id in slots_list:
                if gem_id is None:
                    continue
                gem = self.get_gem_instance(gem_id)
                if gem is None:
                    continue
                gem_def = get_gem(gem["type"])
                if gem_def is None:
                    continue
                if gem_def["stat_key"] == stat_key:
                    total += get_gem_stat_bonus(gem["type"], gem["level"])
        return total

    def add_item(self, item_id: str) -> None:
        """Add an item to inventory (loot/purchase).

        Stage 64 — routes to the paged inventory helper, which finds the
        first empty slot across pages 1 → 2 → 3.
        """
        self.inv_add(item_id)

    def record_defeat(self, mob_id: str) -> None:
        if mob_id not in self.defeated_mobs:
            self.defeated_mobs.append(mob_id)

    # ------------------------------------------------------------------
    # Stage 138 — SYNTH (заточка костюмов) + WARDROBE (гардероб)
    # ------------------------------------------------------------------

    @staticmethod
    def _outfit_model_of(item_id: str, state: "PlayerState") -> str | None:
        """Базовая модель костюма для item_id (инстанс → outfit_id, база → сама)."""
        from pockie_rpg.data.item_db import get_outfit
        if item_id.startswith("outfit_inst_"):
            inst = state.outfit_instances.get(item_id)
            return inst["outfit_id"] if inst else None
        if get_outfit(item_id) is not None:
            return item_id
        return None

    @staticmethod
    def _outfit_plus_of(item_id: str, state: "PlayerState") -> int:
        """Ступень заточки item_id (0 для базового костюма)."""
        if item_id.startswith("outfit_inst_"):
            inst = state.outfit_instances.get(item_id)
            return int(inst.get("plus", 0)) if inst else 0
        return 0

    def _loc_item(self, loc: tuple[int, int] | None) -> str | None:
        """Stage 138 — item_id в локации (page, slot_idx) инвентаря, или None."""
        if not isinstance(loc, tuple) or len(loc) != 2:
            return None
        page, idx = loc
        slots = self.inventory.get(page) if isinstance(self.inventory, dict) else None
        if not isinstance(slots, list) or not (0 <= idx < len(slots)):
            return None
        return slots[idx]

    # --- Stage 184 — СИНТЕЗ БАФОВ ОПЫТА (50→100→150→200) ---
    # Рецепты — в config.BUFF_SYNTH_RECIPES (данные — Layer A).

    def buff_synth_preview(self, main_id, cat1_id, cat2_id) -> dict:
        """Валидация рецепта синтеза бафов опыта (без выполнения).

        Рецепт: 3 ОДИНАКОВЫХ бафа опыта одного вида (3×50% → 100%,
        3×100% → 150%, 3×150% → 200%). Шансы: 75/50/25%.
        Слоты хранят item_id (бафы физически вне инвентаря, как костюмы).
        Возвращает {ok, error, result_id, chance}.
        """
        bad = {"ok": False, "error": "Заполните все 3 слота",
               "result_id": None, "chance": 0}
        if main_id is None or cat1_id is None or cat2_id is None:
            return dict(bad)
        from pockie_rpg.config import get_buff

        main_buff = get_buff(main_id)
        if main_buff is None or main_buff.get("kind") != "xp":
            bad["error"] = "Главный слот: баф опыта"
            return bad
        if not (get_buff(cat1_id) and get_buff(cat2_id)) \
                or get_buff(cat1_id).get("kind") != "xp" \
                or get_buff(cat2_id).get("kind") != "xp":
            bad["error"] = "Катализаторы: бафы опыта"
            return bad
        if not (main_id == cat1_id == cat2_id):
            bad["error"] = "Нужны 3 ОДИНАКОВЫХ бафа"
            return bad
        from pockie_rpg.config import BUFF_SYNTH_RECIPES
        recipe = BUFF_SYNTH_RECIPES.get(main_id)
        if recipe is None:
            bad["error"] = "Максимальный баф +200% не синтезируется"
            return bad
        result_id, chance = recipe
        return {"ok": True, "error": "", "result_id": result_id,
                "chance": chance}

    def buff_synth_execute(self, main_id, cat1_id, cat2_id) -> dict:
        """Выполнить синтез бафов: 3 одинаковых → 1 следующий вид.

        Списывает 1 копию КАЖДОГО слота (слоты хранят item_id — предмет
        физически вне инвентаря, поэтому просто НЕ возвращается обратно;
        activate_buff-логика не участвует). Провал: все 3 бафа сгорают
        (цена попытки, как у костюмов). Успех: баф результата остаётся
        в слоте результата (UI), забирается кликом.
        """
        import random

        preview = self.buff_synth_preview(main_id, cat1_id, cat2_id)
        if not preview["ok"]:
            return {"success": False, "result_id": None,
                    "chance": 0, "error": preview["error"]}
        chance = preview["chance"]
        if random.randint(1, 100) > chance:
            # Провал: бафы сгорели (слоты очищает UI).
            return {"success": False, "result_id": None,
                    "chance": chance, "error": ""}
        return {"success": True, "result_id": preview["result_id"],
                "chance": chance, "error": ""}

    def synth_preview(self, main_id, cat1_id, cat2_id) -> dict:
        """Stage 138/164/166 — валидация рецепта + расчёт, БЕЗ выполнения.

        Stage 164 — слоты синтеза хранят САМИ ПРЕДМЕТЫ (костюм физически
        уходит из инвентаря в слот при drag), поэтому API принимает item_id,
        а не локации (page, idx). Дубликат невозможен по построению: один
        экземпляр существует либо в инвентаре, либо в слоте синтеза
        (прежний баг: loc-ссылка копировалась во все 3 слота и рецепт
        «Нужны 3 РАЗНЫХ ячейки» блокировал кнопку «Создать»).
        Рецепт: главный (любой +N модели M) + 2 катализатора (+0 модели M).
        Stage 166 — гейт уровня игрока УДАЛЕН (запрос пользователя:
        «синтезировать можно любые уровни костюмов»): синтезируется любой
        главный +N, НО НОСИТЬ результат можно строго по требованию
        (equip_gear_item проверяет level_requirement инстанса).
        Возвращает {ok, error, main_id, model_name, main_plus, result_plus,
        chance, required_level}.
        """
        from pockie_rpg.config import (
            OUTFIT_SYNTH_MAX_PLUS,
            outfit_synth_chance,
            outfit_synth_required_level,
        )
        from pockie_rpg.data.item_db import get_outfit

        bad = {"ok": False, "error": "Заполните все 3 слота", "main_id": None,
               "main_plus": 0, "model_name": "", "result_plus": 0, "chance": 0,
               "required_level": 0}
        if main_id is None or cat1_id is None or cat2_id is None:
            return dict(bad)
        # Примечание Stage 164: одинаковые item_id в разных слотах — это
        # РАЗНЫЕ физические копии (базовые костюмы делят item_id; инстансы
        # уникальны). Один экземпляр не может быть в двух слотах: он физически
        # уходит из инвентаря при дропе.
        model = self._outfit_model_of(main_id, self)
        if model is None:
            bad["error"] = "Главный слот: нужен костюм"
            return bad
        bad["model_name"] = get_outfit(model)["name"]
        if (self._outfit_model_of(cat1_id, self) != model
                or self._outfit_model_of(cat2_id, self) != model):
            bad["error"] = "Катализаторы: та же модель, что главный"
            return bad
        if self._outfit_plus_of(cat1_id, self) != 0 or self._outfit_plus_of(cat2_id, self) != 0:
            bad["error"] = "Катализаторы должны быть +0"
            return bad
        main_plus = self._outfit_plus_of(main_id, self)
        if main_plus >= OUTFIT_SYNTH_MAX_PLUS:
            bad["error"] = f"Максимальная заточка +{OUTFIT_SYNTH_MAX_PLUS}"
            bad["main_plus"] = main_plus
            bad["result_plus"] = main_plus
            bad["required_level"] = outfit_synth_required_level(main_plus)
            bad["main_id"] = main_id
            return bad
        result_plus = main_plus + 1
        # Stage 166 — гейт уровня удалён: синтезировать можно ЛЮБЫЕ уровни
        # костюмов. required_level остаётся в ответе (тултип/носибельность
        # проверяет equip_gear_item по level_requirement инстанса).
        req_lvl = outfit_synth_required_level(result_plus)
        return {
            "ok": True,
            "error": "",
            "main_id": main_id,
            "main_plus": main_plus,
            "model_name": get_outfit(model)["name"],
            "result_plus": result_plus,
            "chance": outfit_synth_chance(main_plus),
            "required_level": req_lvl,
        }

    def synth_execute(self, main_id, cat1_id, cat2_id) -> dict:
        """Stage 138/164/166 — выполнить синтез по item_id слотов.

        Предметы УЖЕ физически вне инвентаря (в слотах синтеза UI).
        Провал: сгорают 2 катализатора (инстансы удаляются), главный
        ОСТАЁТСЯ в слоте — можно пробовать снова.
        Stage 166 (запрос пользователя): УСПЕХ — созданный инстанс +N+1
        ОСТАЁТСЯ В СЛОТЕ РЕЗУЛЬТАТА (UI показывает его там и игрок
        забирает кликом); в инвентарь он НЕ добавляется, поэтому место в
        инвентаре больше не требуется и гейт inv_has_space удалён.
        Старый главный инстанс при успехе удаляется (переплавился).
        """
        import random

        preview = self.synth_preview(main_id, cat1_id, cat2_id)
        if not preview["ok"]:
            return {"success": False, "result_id": None, "chance": 0,
                    "error": preview["error"]}
        # Сжигаем катализаторы (цена попытки — в любом случае).
        for iid in (cat1_id, cat2_id):
            if iid.startswith("outfit_inst_"):
                self.outfit_instances.pop(iid, None)
        chance = preview["chance"]
        if random.randint(1, 100) > chance:
            return {"success": False, "result_id": None, "chance": chance, "error": ""}
        # Успех: инстанс +N+1 остаётся В СЛОТЕ РЕЗУЛЬТАТА (Stage 166 —
        # НЕ inv_add: место в инвентаре не требуется, игрок заберёт кликом).
        model = self._outfit_model_of(preview["main_id"], self)
        self._outfit_inst_counter += 1
        inst_id = f"outfit_inst_{self._outfit_inst_counter}"
        self.outfit_instances[inst_id] = {
            "outfit_id": model,
            "plus": preview["result_plus"],
        }
        # Чистим старый инстанс, если главный был инстансом.
        old_main = preview["main_id"]
        if old_main.startswith("outfit_inst_"):
            self.outfit_instances.pop(old_main, None)
        return {"success": True, "result_id": inst_id, "chance": chance, "error": ""}

    # --- Stage 138 — WARDROBE (гардероб) ---

    def wardrobe_store(self, item_id: str, slot: int | None = None) -> bool:
        """Положить костюм из инвентаря в гардероб (свободный или заданный слот)."""
        from pockie_rpg.config import WARDROBE_SLOTS
        if self._outfit_model_of(item_id, self) is None:
            return False
        if not self.inv_remove(item_id):
            return False
        if slot is None:
            for i in range(WARDROBE_SLOTS):
                if self.wardrobe[i] is None:
                    self.wardrobe[i] = item_id
                    return True
        elif 0 <= slot < WARDROBE_SLOTS and self.wardrobe[slot] is None:
            self.wardrobe[slot] = item_id
            return True
        # Слот занят/не найден — вернуть предмет в инвентарь.
        self.inv_add(item_id)
        return False

    def wardrobe_take(self, slot: int) -> str | None:
        """Вынуть костюм из слота гардероба в инвентарь. None = пусто/нет места."""
        if not (0 <= slot < len(self.wardrobe)):
            return None
        item_id = self.wardrobe[slot]
        if item_id is None:
            return None
        if not self.inv_has_space(item_id):
            return None
        self.wardrobe[slot] = None
        self.inv_add(item_id)
        return item_id

    # ------------------------------------------------------------------
    # Stage 113 — SERVER-SIDE BATTLE REWARDS (moved from UI animation layer)
    # ------------------------------------------------------------------

    def process_battle_rewards(
        self,
        is_victory: bool,
        enemy_mob_id: str,
        location_id: int,
        enemy_xp: int = 0,
        enemy_gold: int = 0,
    ) -> dict:
        """Stage 113/118/119 — Server-side battle reward processing.

        This method is called BEFORE the UI shows any animation or reward window.
        It handles ALL reward logic: XP, gold, gems, and equipment drops.

        Stage 119 — REFACTORED drop system:
            * MAX 1 equipment per battle (was: up to 3 — weapon + armor + boots).
            * First rolls `equipment_chance` for ANY drop.
            * If yes, picks ONE type using `type_weights`.
            * Then rolls ONE rarity from `rarity_chances`.
            * Gem drops are still rolled separately (10% chance, unaffected).

        Both animated battle (x1) and quick battle (x10) call this method.
        For x10, it is called 10 times independently — each call rolls its own
        drop chances.

        Args:
            is_victory: True if the player won the battle.
            enemy_mob_id: The mob_id of the defeated enemy (for record_defeat).
            location_id: int — current map location (1-4 for combat zones).
            enemy_xp: XP reward from the enemy.
            enemy_gold: Gold reward from the enemy.

        Returns:
            A dict with reward details for UI display:
                {
                    "xp": int,
                    "gold": int,
                    "leveled_up": bool,
                    "old_level": int,
                    "new_level": int,
                    "gems": [{"type": str, "level": 1}, ...],
                    "equipment_drop": {"type": str, "name": str, "rarity": str,
                                       "item_id": str} | None,
                }
        """
        import random as _rdrop

        from pockie_rpg.config import MOB_DROP_TABLES

        old_level = self.level
        result = {
            "xp": 0,
            "gold": 0,
            "leveled_up": False,
            "old_level": old_level,
            "new_level": old_level,
            "gems": [],
            "equipment_drop": None,
        }

        if not is_victory:
            return result

        # --- XP + Gold ---
        # Stage 184 — бонус от xp-бафов считается ОТДЕЛЬНО для UI: окно
        # награды показывает «Опыт: 50 (+350)». В gain_xp уходит БАЗА —
        # множитель применяется внутри.
        result["xp"] = enemy_xp
        result["xp_bonus"] = self.buffed_xp(enemy_xp) - enemy_xp
        result["gold"] = enemy_gold
        leveled_up = self.gain_xp(enemy_xp)
        self.gain_gold(enemy_gold)
        self.record_defeat(enemy_mob_id)
        # Stage 173 — сюжетные kill_mobs-квесты: победа над врагом двигает
        # счётчик (mob_id → enemy_id, напр. mob_1 → samurai_1).
        if self.story_quests_active:
            from pockie_rpg.data.roles_db import ENEMY_MOBS
            _tmpl = ENEMY_MOBS.get(enemy_mob_id)
            _enemy_id = _tmpl.enemy_id if _tmpl is not None else enemy_mob_id
            self.notify_story_quest_kill(_enemy_id)
        result["leveled_up"] = bool(leveled_up)
        result["new_level"] = self.level

        # --- Gem drop: 10% chance per victory (Stage 170: GEM_DROP_CHANCE в config) ---
        if _rdrop.random() < GEM_DROP_CHANCE:
            gem_types = ["gem_red", "gem_blue", "gem_green", "gem_yellow", "gem_orange"]
            dropped_type = _rdrop.choice(gem_types)
            self.add_gem(dropped_type, 1)
            result["gems"].append({"type": dropped_type, "level": 1})

        # --- Equipment drop: Stage 119 — MAX 1 per battle ---
        # Single roll for ANY equipment drop, then weighted type pick,
        # then rarity roll. Replaces the old per-type independent rolls.
        drop_table = MOB_DROP_TABLES.get(location_id)
        if drop_table is not None:
            equip_chance = drop_table.get("equipment_chance", 0)
            if _rdrop.randint(1, 100) <= equip_chance:
                # Pick type using weighted random.
                type_weights = drop_table.get("type_weights", {"weapon": 1})
                types = list(type_weights.keys())
                weights = [type_weights[t] for t in types]
                chosen_type = _rdrop.choices(types, weights=weights, k=1)[0]

                # Pick rarity using rarity_chances.
                rarity_chances = drop_table.get("rarity_chances", {"Grey": 100})
                rarities = list(rarity_chances.keys())
                r_weights = [rarity_chances[r] for r in rarities]
                chosen_rarity = _rdrop.choices(rarities, weights=r_weights, k=1)[0]

                # Pick level from the levels list.
                levels = drop_table.get("levels", [1, 5])
                chosen_level = _rdrop.choice(levels)

                # Generate and add to inventory.
                gen_id = self.give_test_item(chosen_level, chosen_rarity, chosen_type)
                if gen_id is not None:
                    item = self.get_item_definition(gen_id)
                    if item:
                        # Stage 119 — unified equipment_drop field.
                        result["equipment_drop"] = {
                            "type": chosen_type,
                            "name": item["name"],
                            "rarity": chosen_rarity,
                            "item_id": gen_id,
                        }
                        # Stage 143 — авто-прод серых УДАЛЁН по требованию
                        # (замена: кнопка «Продать» с выбором качества в UI).

        return result

    # ------------------------------------------------------------------
    # Stage 89 — TOWER MODE helpers (per TOWER_MODE_IMPLEMENTATION.md §6)
    # ------------------------------------------------------------------

    def can_enter_tower(self, floor: int) -> bool:
        """Return True if ``floor`` is unlocked and enterable.

        Stage 90 — attempt limit REMOVED. Tower is now endless: the player can
        retry floors unlimited times until death. A floor is enterable when:
          - 1 <= floor <= TOWER_MAX_FLOOR
          - floor <= tower_highest_floor + 1 (next floor after highest cleared)
        """
        from pockie_rpg.config import TOWER_MAX_FLOOR
        if not (1 <= floor <= TOWER_MAX_FLOOR):
            return False
        if floor > self.tower_highest_floor + 1:
            return False
        return True

    def start_tower_attempt(self, floor: int) -> bool:
        """Mark ``floor`` as the current Tower floor.

        Stage 90 — attempt limit REMOVED. No longer consumes an attempt or
        starts a regen timer. Returns True if the floor is enterable, False
        otherwise.
        """
        if not self.can_enter_tower(floor):
            return False
        self.tower_current_floor = floor
        return True

    def complete_tower_floor(self, floor: int) -> bool:
        """Mark ``floor`` as cleared and update ``tower_highest_floor``.

        Returns True if the floor was newly cleared (first time), False if
        it was already cleared (repeat clear). Does NOT award rewards —
        the caller uses ``claim_tower_first_clear`` to determine which
        reward to apply.
        """
        from pockie_rpg.config import TOWER_MAX_FLOOR
        if not (1 <= floor <= TOWER_MAX_FLOOR):
            return False
        is_first_clear = floor not in self.tower_first_clear_claimed
        if is_first_clear:
            self.tower_first_clear_claimed.append(floor)
        if floor > self.tower_highest_floor:
            self.tower_highest_floor = floor
        # Advance tower_current_floor to the next unlocked floor.
        if self.tower_current_floor == floor and floor < TOWER_MAX_FLOOR:
            self.tower_current_floor = floor + 1
        return is_first_clear

    def claim_tower_first_clear(self, floor: int) -> bool:
        """Return True if ``floor``'s first-clear reward is still unclaimed.

        Note: this is a QUERY, not a mutation. The caller should call
        ``complete_tower_floor`` first (which marks the claim), then check
        the return value to decide first-clear vs repeat reward.
        """
        return floor not in self.tower_first_clear_claimed

    def add_tower_shards(self, amount: int) -> None:
        """Add ``amount`` Tower shards (clamped to non-negative)."""
        if amount <= 0:
            return
        self.tower_shards += amount

    def spend_tower_shards(self, amount: int) -> bool:
        """Spend ``amount`` Tower shards. Returns True if affordable + spent."""
        if amount <= 0 or self.tower_shards < amount:
            return False
        self.tower_shards -= amount
        return True

    def add_tower_material(self, material_id: str, amount: int) -> None:
        """Add ``amount`` of ``material_id`` to ``tower_materials``."""
        if amount <= 0 or not material_id:
            return
        self.tower_materials[material_id] = self.tower_materials.get(material_id, 0) + amount

    # ------------------------------------------------------------------
    # Stage 95 — Daily Quests
    # ------------------------------------------------------------------

    def check_daily_quest_reset(self) -> None:
        """Check if daily quests need to be reset (new day).

        Compares ``daily_quest_date`` to today's date. If different, resets
        progress + claimed lists.
        """
        import datetime as _dt
        today = _dt.date.today().isoformat()  # YYYY-MM-DD
        if self.daily_quest_date != today:
            self.daily_quest_progress = {}
            self.daily_quest_claimed = []
            self.daily_quest_date = today

    def add_daily_quest_progress(self, quest_id: str, amount: int = 1) -> None:
        """Increment progress for a daily quest.

        Does NOT auto-claim — the player must click "Получить" in the UI.
        """
        if amount <= 0:
            return
        self.check_daily_quest_reset()
        self.daily_quest_progress[quest_id] = self.daily_quest_progress.get(quest_id, 0) + amount

    def is_daily_quest_complete(self, quest_id: str) -> bool:
        """Return True if the quest target is met (but not yet claimed)."""
        from pockie_rpg.data.daily_quests import get_daily_quest
        quest = get_daily_quest(quest_id)
        if quest is None:
            return False
        self.check_daily_quest_reset()
        progress = self.daily_quest_progress.get(quest_id, 0)
        return progress >= quest.target and quest_id not in self.daily_quest_claimed

    def claim_daily_quest(self, quest_id: str) -> bool:
        """Claim the reward for a completed daily quest.

        Returns True if claimed successfully, False if not complete or
        already claimed. Applies gold + XP + shards to the player.
        """
        from pockie_rpg.data.daily_quests import get_daily_quest
        quest = get_daily_quest(quest_id)
        if quest is None:
            return False
        self.check_daily_quest_reset()
        if quest_id in self.daily_quest_claimed:
            return False
        progress = self.daily_quest_progress.get(quest_id, 0)
        if progress < quest.target:
            return False
        # Apply rewards.
        self.gain_gold(quest.reward_gold)
        self.gain_xp(quest.reward_xp)
        if quest.reward_shards > 0:
            self.add_tower_shards(quest.reward_shards)
        # Mark as claimed.
        self.daily_quest_claimed.append(quest_id)
        return True

    # ------------------------------------------------------------------
    # Stage 172 — сюжетные квесты (цепочка от Старейшины деревни)
    # ------------------------------------------------------------------

    def story_quest_available(self, quest_id: str) -> bool:
        """True — квест можно взять: есть в цепочке, ещё не взят/сдан,
        все предыдущие квесты цепочки сданы."""
        from pockie_rpg.data.quests_db import (
            chain_prerequisites_met,
            get_story_quest,
        )
        quest = get_story_quest(quest_id)
        if quest is None:
            return False
        if quest_id in self.story_quests_active or quest_id in self.story_quests_completed:
            return False
        return chain_prerequisites_met(quest_id, self.story_quests_completed)

    def first_available_story_quest(self) -> str | None:
        """Первый доступный к цепочке квест (для индикатора «!»), или None."""
        from pockie_rpg.data.quests_db import STORY_QUEST_CHAIN
        for quest_id in STORY_QUEST_CHAIN:
            if self.story_quest_available(quest_id):
                return quest_id
        return None

    def story_quest_goal_done(self, quest_id: str) -> bool:
        """Цель активного квеста выполнена СЕЙЧАС (для индикатора «?»):
        talk_to — всегда True (сдача = сам разговор); use_item — факт
        надетия целевого предмета (story_quests_goal_done); kill_mobs —
        счётчик побед дошёл до goal_count (Stage 173)."""
        from pockie_rpg.data.quests_db import get_story_quest
        quest = get_story_quest(quest_id)
        if quest is None or quest_id not in self.story_quests_active:
            return False
        if quest.goal_type == "talk_to":
            return True
        if quest.goal_type == "kill_mobs":
            return self.story_quests_kill_progress.get(quest_id, 0) >= quest.goal_count
        return quest_id in self.story_quests_goal_done

    def story_quest_kill_progress(self, quest_id: str) -> tuple[int, int]:
        """Stage 173 — (сделано, нужно) для счётчика «(2/3)» в трекере;
        для не-kill_mobs квестов — (0, 0)."""
        from pockie_rpg.data.quests_db import get_story_quest
        quest = get_story_quest(quest_id)
        if quest is None or quest.goal_type != "kill_mobs":
            return (0, 0)
        return (self.story_quests_kill_progress.get(quest_id, 0), quest.goal_count)

    def notify_story_quest_kill(self, enemy_id: str | None) -> None:
        """Stage 173 — хук победы над врагом (process_battle_rewards):
        увеличивает счётчик активных kill_mobs-квестов, чей goal_target
        совпадает с enemy_id (точное совпадение или префикс, напр. "samurai"
        ловит samurai_1/samurai_2/…). Значение кэпится goal_count — сейв
        не раздувается, цель не «перевыполняется».

        Возвращает список квестов, чья цель ВЫПОЛНЕНА этим убийством
        (для тоста в UI; обычно 0 или 1 квест).
        """
        from pockie_rpg.data.quests_db import STORY_QUESTS
        if not enemy_id:
            return []
        done_now: list[str] = []
        for quest_id in self.story_quests_active:
            quest = STORY_QUESTS.get(quest_id)
            if quest is None or quest.goal_type != "kill_mobs":
                continue
            target = quest.goal_target
            if not (enemy_id == target or enemy_id.startswith(target)):
                continue
            cur = self.story_quests_kill_progress.get(quest_id, 0)
            if cur < quest.goal_count:
                self.story_quests_kill_progress[quest_id] = cur + 1
                if cur + 1 >= quest.goal_count:
                    done_now.append(quest_id)
        return done_now

    def accept_story_quest(self, quest_id: str) -> bool:
        """Взять квест (только доступный). True — успех."""
        if not self.story_quest_available(quest_id):
            return False
        self.story_quests_active.append(quest_id)
        return True

    def notify_story_quest_item_used(self, item_id: str) -> None:
        """Хук equip_gear_item: фиксирует выполнение use_item-цели активного
        квеста (обратимо не является — факты надетия накапливаются)."""
        from pockie_rpg.data.quests_db import STORY_QUESTS
        for quest_id in self.story_quests_active:
            quest = STORY_QUESTS.get(quest_id)
            if quest is None or quest.goal_type != "use_item":
                continue
            if quest.goal_target == item_id and quest_id not in self.story_quests_goal_done:
                self.story_quests_goal_done.append(quest_id)

    def turn_in_story_quest(self, quest_id: str) -> dict | None:
        """Сдать квест и выдать награды. Возвращает сводку наград
        {xp, gold, coupons, item, leveled_up} или None (не готов/нет места).

        Предмет-награда при полном инвентаре НЕ выдаётся, квест НЕ завершается
        (сводка {"item_failed": ...}) — игрок освобождает место и сдаёт снова.
        """
        from pockie_rpg.data.quests_db import get_story_quest
        quest = get_story_quest(quest_id)
        if quest is None or quest_id not in self.story_quests_active:
            return None
        if not self.story_quest_goal_done(quest_id):
            return None
        item_failed = False
        if quest.reward_item is not None:
            if not self.inv_add(quest.reward_item):
                item_failed = True
        if not item_failed:
            leveled_up = self.gain_xp(quest.reward_xp)
            self.gain_gold(quest.reward_gold)
            if quest.reward_coupons > 0:
                self.coupons += quest.reward_coupons
            self.story_quests_active.remove(quest_id)
            if quest_id in self.story_quests_goal_done:
                self.story_quests_goal_done.remove(quest_id)
            # Stage 173 — счётчик kill_mobs больше не нужен (компакция).
            self.story_quests_kill_progress.pop(quest_id, None)
            self.story_quests_completed.append(quest_id)
        return {
            "xp": 0 if item_failed else quest.reward_xp,
            "gold": 0 if item_failed else quest.reward_gold,
            "coupons": 0 if item_failed else quest.reward_coupons,
            "item": None if item_failed else quest.reward_item,
            "leveled_up": False if item_failed else leveled_up,
            "item_failed": item_failed,
        }

    def story_quest_npc_indicators(self, npc_id: str) -> tuple[bool, bool]:
        """(есть_доступный_квест «!», есть_готовый_к_сдаче «?»)."""
        from pockie_rpg.data.quests_db import STORY_QUESTS
        has_available = any(
            q.giver_npc == npc_id and self.story_quest_available(qid)
            for qid, q in STORY_QUESTS.items()
        )
        has_ready = any(
            q.giver_npc == npc_id
            and qid in self.story_quests_active
            and self.story_quest_goal_done(qid)
            for qid, q in STORY_QUESTS.items()
        )
        return has_available, has_ready

    def active_story_quests_at(self, npc_id: str) -> list[str]:
        """Активные квесты данного giver'а (для диалога: сдача/напоминание)."""
        from pockie_rpg.data.quests_db import STORY_QUESTS
        return [
            qid for qid in self.story_quests_active
            if STORY_QUESTS.get(qid) is not None
            and STORY_QUESTS[qid].giver_npc == npc_id
        ]

    # ------------------------------------------------------------------
    # Stage 9 — Serialization for save/load (JSON)
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize this PlayerState to a JSON-encodable dict.

        Per Stage 9 spec (Fix 4): used by `game.save_load.save_player_state`
        to persist progression between sessions. Encodes all fields needed
        to reconstruct the player state on load.

        Stage 14 — also serializes `active_skills` (the subset of skills the
        player has enabled via the skills modal). On load, if missing or
        empty, defaults to all Role.skills enabled (backward compat with
        pre-Stage-14 saves).

        Returns:
            dict with keys: name, suit_id, role_id, level, xp, xp_to_next,
            gold, defeated_mobs, current_hp, current_mp, active_skills.
        """
        # Stage 171 — B3: компакция процедурных словарей в КОПИИ для сейва.
        # Живой PlayerState НЕ мутируется — фильтруются только to_dict-выходы,
        # монотонный рост сейва от старых процедурных предметов прекращается.
        # Ссылки: инвентарь (все страницы, включая слоты 96-127 старых сейвов),
        # equipped_gear, equipped_outfit, гардероб, слоты синтеза (UI-провайдер).
        ref_ids: set[str] = set()
        for _slots in self.inventory.values():
            for i in _slots:
                # Stage 183 — слоты могут быть dict-стаками {"item_id", "count"}.
                if isinstance(i, str):
                    ref_ids.add(i)
                elif isinstance(i, dict) and isinstance(i.get("item_id"), str):
                    ref_ids.add(i["item_id"])
        for _gear in self.equipped_gear.values():
            if isinstance(_gear, str):
                ref_ids.add(_gear)
        if isinstance(self.equipped_outfit, str):
            ref_ids.add(self.equipped_outfit)
        ref_ids.update(i for i in self.wardrobe if isinstance(i, str))
        _prov = getattr(self, "synth_slots_provider", None)
        if callable(_prov):
            try:
                _synth_ids = _prov()
            except Exception:  # noqa: BLE001 — defensive: UI-провайдер.
                _synth_ids = ()
            if _synth_ids:
                ref_ids.update(i for i in _synth_ids if isinstance(i, str))
        # Stage 173 — ленивый импорт БД квестов (компакция kill_mobs-счётчиков).
        from pockie_rpg.data.quests_db import STORY_QUESTS as _SQ
        return {
            "name": self.name,
            "suit_id": self.suit_id,
            "role_id": self.role_id,
            "level": self.level,
            "current_xp": self.current_xp,
            "max_xp": self.max_xp,
            "gold": self.gold,
            # Stage 165 — купоны (второй ресурс).
            "coupons": self.coupons,
            "defeated_mobs": list(self.defeated_mobs),
            "current_hp": self.current_hp,
            "current_mp": self.current_mp,
            "strength": self.strength,
            "agility": self.agility,
            "stamina": self.stamina,
            "max_mp": self.max_mp,
            "active_skills": list(self.active_skills),
            "equipped_outfit": self.equipped_outfit,
            "equipped_gear": dict(self.equipped_gear),
            # Stage 64 — serialize paged inventory as {page_key: [slots...]}.
            # JSON object keys must be strings, so we cast page numbers.
            # Stage 183 — стак-слоты (dict {"item_id", "count"}) сериализуются
            # как есть — JSON-safe. Пустые стаки не пишутся.
            "inventory": {
                str(p): [
                    (s if not (isinstance(s, dict) and int(s.get("count", 0)) <= 0) else None)
                    for s in slots
                ]
                for p, slots in self.inventory.items()
            },
            "gear_enchants": dict(self.gear_enchants),
            "gem_inventory": list(self.gem_inventory),
            "gear_gem_slots": {k: list(v) for k, v in self.gear_gem_slots.items()},
            "_gem_id_counter": self._gem_id_counter,
            # Stage 70 — active title id (or None).
            "active_title": self.active_title,
            # Stage 71/77 — World Boss state.
            "world_boss_attempts": self.world_boss_attempts,
            "world_boss_next_attempt_ts": self.world_boss_next_attempt_ts,
            "world_boss_hp": dict(self.world_boss_hp) if self.world_boss_hp else None,
            # Stage 89 — Tower mode state.
            "tower_current_floor": self.tower_current_floor,
            "tower_highest_floor": self.tower_highest_floor,
            "tower_shards": self.tower_shards,
            "tower_pending_xp": self.tower_pending_xp,
            "daily_quest_progress": dict(self.daily_quest_progress),
            "daily_quest_claimed": list(self.daily_quest_claimed),
            "daily_quest_date": self.daily_quest_date,
            "tower_materials": dict(self.tower_materials),
            "tower_first_clear_claimed": list(self.tower_first_clear_claimed),
            # Stage 108 — procedural weapons storage.
            # Stage 171 — B3: в сейв идут только ИНСТАНСЫ, на которые есть
            # ссылки (проданные/потеранные — выпадают из копии для сейва).
            "generated_weapons": {
                k: dict(v) for k, v in self.generated_weapons.items()
                if k in ref_ids
            },
            "gen_w_counter": self._gen_w_counter,
            # Stage 133 — fractional growth accumulators (preserve fractional
            # BMV-Прирост across save/load).
            "_str_accum": self._str_accum,
            "_agi_accum": self._agi_accum,
            "_sta_accum": self._sta_accum,
            # Stage 133 — slot machine cooldown.
            "slot_next_roll_ts": self.slot_next_roll_ts,
            # Stage 138 — SYNTH: заточенные костюмы-инстансы + счётчик.
            # Stage 171 — B3: компакция по ссылкам (как generated_weapons).
            "outfit_instances": {
                k: dict(v) for k, v in self.outfit_instances.items()
                if k in ref_ids
            },
            "_outfit_inst_counter": self._outfit_inst_counter,
            # Stage 138 — WARDROBE: 5 слотов-хранилищ (None | item_id).
            "wardrobe": list(self.wardrobe),
            # Stage 180 — активные бафы (реальное время; истёкшие не пишутся).
            "active_buffs": list(self.active_buffs),
            # Stage 157 — UI: позиции перетаскиваемых окон {key: [x, y]}.
            "window_positions": {
                k: [int(v[0]), int(v[1])]
                for k, v in self.window_positions.items()
                if isinstance(v, (tuple, list)) and len(v) == 2
            },
            # Stage 160 — флаг разового гранта тест-костюмов.
            "synth_test_grant_v160": self.synth_test_grant_v160,
            # Stage 172 — сюжетные квесты (активные / выполненные цели / сданные).
            "story_quests_active": list(self.story_quests_active),
            "story_quests_goal_done": list(self.story_quests_goal_done),
            "story_quests_completed": list(self.story_quests_completed),
            # Stage 173 — счётчики kill_mobs (компакция: только известные
            # цепочке kill_mobs-квесты, значения 0..goal_count).
            "story_quests_kill_progress": {
                qid: int(v) for qid, v in self.story_quests_kill_progress.items()
                if isinstance(qid, str) and isinstance(v, int) and v > 0
                and qid in self.story_quests_active
                and (_q := _SQ.get(qid)) is not None
                and _q.goal_type == "kill_mobs"
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PlayerState":
        """Reconstruct a PlayerState from a deserialized dict.

        Per Stage 9 spec (Fix 4): used by `game.save_load.load_player_state`
        to restore progression from the save file.

        Defensive: if any field is missing or has the wrong type, the
        corresponding default value is used (per PlayerState defaults).
        This guards against corrupted or partially-written save files.

        Args:
            data: dict with the same keys produced by `to_dict()`.

        Returns:
            A new PlayerState with the loaded values (or defaults for
            missing/invalid fields).
        """
        # Helper: fetch with type check + fallback.
        def _get(key: str, expected_type: type, default):
            v = data.get(key, default)
            if isinstance(v, expected_type):
                return v
            # bool is a subclass of int — accept bool for int fields too.
            if expected_type is int and isinstance(v, bool):
                return int(v)
            return default

        # defeated_mobs is a list[str] — validate element types.
        raw_mobs = data.get("defeated_mobs", [])
        if not isinstance(raw_mobs, list):
            raw_mobs = []
        defeated_mobs: list[str] = [m for m in raw_mobs if isinstance(m, str)]

        # Stage 88 — Fix 2.6: distinguish "active_skills key absent" (old save
        # without the field → migrate to full role set) from "active_skills is
        # an empty list" (user explicitly disabled all skills → keep empty).
        # Previously, both cases produced [] and Fighter.from_player_state
        # treated [] as falsy, falling back to role.skills — making it
        # impossible to play with skills intentionally disabled.
        if "active_skills" in data:
            raw_skills = data["active_skills"]
            if not isinstance(raw_skills, list):
                raw_skills = []
            active_skills: list[int] = [
                int(s) for s in raw_skills if isinstance(s, int) and not isinstance(s, bool)
            ]
        else:
            # Old save without active_skills — migrate to full role set.
            _migrate_role_id = _get("role_id", int, 1)
            _migrate_role = ROLES.get(_migrate_role_id)
            active_skills = list(_migrate_role.skills) if _migrate_role else []

        p = cls(
            name=_get("name", str, "Игрок"),
            suit_id=_get("suit_id", str, "i290001"),
            role_id=_get("role_id", int, 1),
            level=_get("level", int, 1),
            current_xp=_get("current_xp", int, _get("xp", int, 0)),
            max_xp=_get("max_xp", int, _get("xp_to_next", int, 100)),
            gold=_get("gold", int, 0),
            # Stage 165 — купоны: старые сейвы без ключа получают тестовые
            # 10 500 (Stage 170 — константа config; значение НЕ менялось).
            coupons=_get("coupons", int, TEST_START_COUPONS),
            defeated_mobs=defeated_mobs,
            strength=_get("strength", int, 24),
            agility=_get("agility", int, 24),
            stamina=_get("stamina", int, 20),
            max_mp=_get("max_mp", int, 300),
            active_skills=active_skills,
        )
        raw_gear = data.get("equipped_gear", {})
        if isinstance(raw_gear, dict):
            for slot in ["weapon", "head", "body", "hands", "belt", "boots",
                         "accessory", "accessory2", "outfit"]:
                val = raw_gear.get(slot)
                p.equipped_gear[slot] = val if isinstance(val, str) or val is None else None
        raw_inv = data.get("inventory", [])
        # Stage 64 — load paged inventory.
        # Accept the new paged dict format {1: [...], 2: [...], 3: [...]}.
        # For backward-compat with pre-Stage-64 saves (legacy flat list of
        # item_ids), migrate each item into the first empty slot of the
        # paged structure.
        p.inventory = _empty_inventory()
        if isinstance(raw_inv, dict):
            for page_key, slots in raw_inv.items():
                try:
                    page = int(page_key)
                except (TypeError, ValueError):
                    continue
                if page not in p.inventory:
                    continue
                if not isinstance(slots, list):
                    continue
                for i, iid in enumerate(slots):
                    if i >= len(p.inventory[page]):
                        break
                    if isinstance(iid, str):
                        p.inventory[page][i] = iid
                    elif isinstance(iid, dict):
                        # Stage 183 — стак-слот {"item_id": str, "count": int}.
                        s_item = iid.get("item_id")
                        s_count = iid.get("count", 1)
                        if isinstance(s_item, str) and isinstance(s_count, (int, float)) \
                                and int(s_count) > 0:
                            p.inventory[page][i] = {
                                "item_id": s_item, "count": int(s_count),
                            }
        elif isinstance(raw_inv, list):
            # Legacy flat list — migrate to paged structure.
            for iid in raw_inv:
                if isinstance(iid, str):
                    p.inv_add(iid)
        # Defensive: ensure all pages are well-formed (correct length, types).
        p._ensure_inventory_pages()
        # Stage 116 — load gear_enchants (per-item-id, migrated from per-slot).
        raw_enchants = data.get("gear_enchants", {})
        if isinstance(raw_enchants, dict):
            for key, val in raw_enchants.items():
                if isinstance(val, (int, float)) and int(val) > 0:
                    # Stage 116 — if key is a slot name (old format), migrate
                    # to the currently-equipped item_id in that slot.
                    if key in ("weapon", "head", "body", "hands", "belt", "boots", "accessory", "accessory2"):
                        item_id = p.equipped_gear.get(key)
                        if item_id:
                            p.gear_enchants[item_id] = int(val)
                    else:
                        # Already per-item-id (new format).
                        p.gear_enchants[key] = int(val)
        # Stage 51 — load gem_inventory, gear_gem_slots, _gem_id_counter.
        # Аудит 2026-09 — type-check УГЛУБЛЁН: раньше int(g["level"]) на
        # строке/"abc" ронял ВЕСЬ from_dict (первичный сейв отбрасывался).
        raw_gems = data.get("gem_inventory", [])
        if isinstance(raw_gems, list):
            p.gem_inventory = []
            for g in raw_gems:
                if not (isinstance(g, dict) and "id" in g and "type" in g and "level" in g):
                    continue
                lvl = g["level"]
                if not isinstance(lvl, (int, float)):
                    continue
                p.gem_inventory.append({
                    "id": g["id"] if isinstance(g["id"], str) else "",
                    "type": g["type"] if isinstance(g["type"], str) else "",
                    "level": int(lvl),
                })
        raw_gem_slots = data.get("gear_gem_slots", {})
        if isinstance(raw_gem_slots, dict):
            for slot in ["weapon", "head", "body", "hands", "belt", "boots", "accessory", "accessory2"]:
                slots_list = raw_gem_slots.get(slot, [None, None, None])
                if isinstance(slots_list, list):
                    p.gear_gem_slots[slot] = [
                        (s if isinstance(s, str) else None) for s in slots_list[:3]
                    ]
                # Pad to 3 entries if shorter.
                while len(p.gear_gem_slots[slot]) < 3:
                    p.gear_gem_slots[slot].append(None)
        raw_counter = data.get("_gem_id_counter", 0)
        if isinstance(raw_counter, (int, float)):
            p._gem_id_counter = int(raw_counter)
        # Stage 70 — load active_title (or None).
        raw_title = data.get("active_title")
        p.active_title = raw_title if isinstance(raw_title, str) else None
        # Stage 143 — auto_sell_grey УДАЛЁН (ключ в старых сейвах игнорируется).
        # Stage 71/77 — load World Boss state.
        raw_attempts = data.get("world_boss_attempts", 3)
        p.world_boss_attempts = int(raw_attempts) if isinstance(raw_attempts, (int, float)) else 3
        raw_ts = data.get("world_boss_next_attempt_ts")
        p.world_boss_next_attempt_ts = float(raw_ts) if isinstance(raw_ts, (int, float)) else None
        raw_boss_hp = data.get("world_boss_hp")
        if isinstance(raw_boss_hp, dict):
            p.world_boss_hp = {
                "level": int(raw_boss_hp.get("level", 1)),
                "max_hp": int(raw_boss_hp.get("max_hp", 50000)),
                "current_hp": int(raw_boss_hp.get("current_hp", 50000)),
                "location": int(raw_boss_hp.get("location", 1)),
                "min_atk": int(raw_boss_hp.get("min_atk", 1000)),
                "max_atk": int(raw_boss_hp.get("max_atk", 1500)),
                "killed_count": int(raw_boss_hp.get("killed_count", 0)),
            }
        else:
            p.world_boss_hp = None
        # Stage 89 — Tower mode state (defensive: old saves default to fresh state).
        from pockie_rpg.config import TOWER_DEFAULT_START_FLOOR, TOWER_MAX_FLOOR
        raw_t_curr = data.get("tower_current_floor", TOWER_DEFAULT_START_FLOOR)
        p.tower_current_floor = (
            int(raw_t_curr) if isinstance(raw_t_curr, (int, float)) and 1 <= int(raw_t_curr) <= TOWER_MAX_FLOOR
            else TOWER_DEFAULT_START_FLOOR
        )
        raw_t_high = data.get("tower_highest_floor", 0)
        p.tower_highest_floor = (
            int(raw_t_high) if isinstance(raw_t_high, (int, float)) and 0 <= int(raw_t_high) <= TOWER_MAX_FLOOR
            else 0
        )
        # Fix invariant: current can't be more than highest+1.
        if p.tower_current_floor > p.tower_highest_floor + 1:
            p.tower_current_floor = min(TOWER_MAX_FLOOR, p.tower_highest_floor + 1)
        # Stage 134 — tower_attempts/tower_next_attempt_ts keys in old saves are
        # intentionally ignored (fields deleted; nothing to restore).
        raw_t_shards = data.get("tower_shards", 0)
        p.tower_shards = max(0, int(raw_t_shards)) if isinstance(raw_t_shards, (int, float)) else 0
        # Stage 94 — tower_pending_xp (accumulated XP, claimed via "Получить").
        raw_t_xp = data.get("tower_pending_xp", 0)
        p.tower_pending_xp = max(0, int(raw_t_xp)) if isinstance(raw_t_xp, (int, float)) else 0
        # Stage 95 — daily quest progress.
        raw_dqp = data.get("daily_quest_progress", {})
        if isinstance(raw_dqp, dict):
            p.daily_quest_progress = {
                str(k): max(0, int(v)) for k, v in raw_dqp.items()
                if isinstance(v, (int, float))
            }
        else:
            p.daily_quest_progress = {}
        raw_dqc = data.get("daily_quest_claimed", [])
        if isinstance(raw_dqc, list):
            p.daily_quest_claimed = [str(q) for q in raw_dqc if isinstance(q, str)]
        else:
            p.daily_quest_claimed = []
        raw_dqd = data.get("daily_quest_date", "")
        p.daily_quest_date = str(raw_dqd) if isinstance(raw_dqd, str) else ""
        raw_t_mats = data.get("tower_materials", {})
        if isinstance(raw_t_mats, dict):
            p.tower_materials = {
                str(k): max(0, int(v)) for k, v in raw_t_mats.items()
                if isinstance(v, (int, float))
            }
        else:
            p.tower_materials = {}
        raw_t_claimed = data.get("tower_first_clear_claimed", [])
        if isinstance(raw_t_claimed, list):
            p.tower_first_clear_claimed = [
                int(f) for f in raw_t_claimed
                if isinstance(f, (int, float)) and 1 <= int(f) <= TOWER_MAX_FLOOR
            ]
        else:
            p.tower_first_clear_claimed = []
        # Stage 108 — restore procedural weapons storage.
        raw_gen_weapons = data.get("generated_weapons", {})
        if isinstance(raw_gen_weapons, dict):
            p.generated_weapons = {
                str(k): v for k, v in raw_gen_weapons.items()
                if isinstance(v, dict) and v.get("generated") is True
            }
        else:
            p.generated_weapons = {}
        raw_gwc = data.get("gen_w_counter", 0)
        # Аудит 2026-09 — int("abc") раньше ронял ВЕСЬ from_dict.
        p._gen_w_counter = max(0, int(raw_gwc)) if isinstance(raw_gwc, (int, float)) else 0
        # Stage 133 — restore fractional growth accumulators. Keys absent
        # (old save) → lazy-init from the loaded int stats (same as the
        # gain_xp lazy-init) so fractional growth continues seamlessly.
        accum_sources = (
            ("_str_accum", p.strength),
            ("_agi_accum", p.agility),
            ("_sta_accum", p.stamina),
        )
        for key, int_stat in accum_sources:
            raw = data.get(key)
            if isinstance(raw, (int, float)) and not isinstance(raw, bool):
                setattr(p, key, float(raw))
            else:
                setattr(p, key, float(int_stat))
        # Stage 133 — slot machine cooldown.
        # Stage 163 — slot_history из старых сейвов просто игнорируется.
        raw_slot_ts = data.get("slot_next_roll_ts")
        p.slot_next_roll_ts = float(raw_slot_ts) if isinstance(raw_slot_ts, (int, float)) and not isinstance(raw_slot_ts, bool) else None
        # Stage 138 — SYNTH: заточенные костюмы-инстансы (tolerant к старым сейвам).
        raw_inst = data.get("outfit_instances", {})
        if isinstance(raw_inst, dict):
            for k, v in raw_inst.items():
                if isinstance(k, str) and isinstance(v, dict) and isinstance(v.get("outfit_id"), str):
                    p.outfit_instances[k] = {
                        "outfit_id": v["outfit_id"],
                        "plus": int(v.get("plus", 0)) if isinstance(v.get("plus", 0), (int, float)) and not isinstance(v.get("plus", 0), bool) else 0,
                    }
        p._outfit_inst_counter = _get("_outfit_inst_counter", int, 0)
        # Stage 138 — WARDROBE: 5 слотов (tolerant; None/str).
        raw_wardrobe = data.get("wardrobe", [])
        if isinstance(raw_wardrobe, list):
            from pockie_rpg.config import WARDROBE_SLOTS
            p.wardrobe = [None] * WARDROBE_SLOTS
            for i in range(min(WARDROBE_SLOTS, len(raw_wardrobe))):
                if isinstance(raw_wardrobe[i], str):
                    p.wardrobe[i] = raw_wardrobe[i]
        # Stage 180 — активные бафы: валидация + отбрасывание истёкших.
        p.active_buffs = []
        raw_buffs = data.get("active_buffs", [])
        if isinstance(raw_buffs, list):
            import time as _time_load

            from pockie_rpg.config import get_buff as _get_buff
            _now = _time_load.time()
            for b in raw_buffs:
                if not isinstance(b, dict):
                    continue
                if _get_buff(str(b.get("buff_id", ""))) is None:
                    continue  # неизвестный buff_id — отбрасываем
                try:
                    exp = float(b.get("expires_ts", 0))
                except (TypeError, ValueError):
                    continue
                if exp <= _now:
                    continue  # истёкший — отбрасываем
                p.active_buffs.append({"buff_id": str(b["buff_id"]), "expires_ts": exp})
        # Stage 157 — UI: позиции перетаскиваемых окон (дизайн-координаты).
        raw_winpos = data.get("window_positions", {})
        if isinstance(raw_winpos, dict):
            for key, val in raw_winpos.items():
                if (isinstance(key, str) and isinstance(val, list)
                        and len(val) == 2
                        and all(isinstance(c, (int, float)) for c in val)):
                    p.window_positions[key] = (int(val[0]), int(val[1]))
        # Stage 133 — restore equipped_outfit (to_dict wrote it, from_dict
        # never read it → every load reverted to suit_ichigo).
        from pockie_rpg.data.item_db import get_outfit
        raw_outfit = data.get("equipped_outfit")
        # Stage 138 — заточенный инстанс тоже валиден как equipped_outfit.
        if isinstance(raw_outfit, str) and (get_outfit(raw_outfit) is not None
                                            or raw_outfit.startswith("outfit_inst_")):
            p.equipped_outfit = raw_outfit
        # Stage 133 — TWO SOURCES OF TRUTH for the outfit (fixed rule):
        # equipped_gear["outfit"] is restored separately by the gear loop
        # above. If that slot holds a VALID outfit it WINS and
        # equipped_outfit is synced to it; otherwise the restored
        # equipped_outfit field stands.
        gear_outfit = p.equipped_gear.get("outfit")
        if isinstance(gear_outfit, str) and (get_outfit(gear_outfit) is not None
                                             or gear_outfit.startswith("outfit_inst_")):
            p.equipped_outfit = gear_outfit
        # Stage 172 — сюжетные квесты: только известные цепочке id (мусор
        # и неизвестные квесты из будущих/битых сейвов отбрасываются).
        from pockie_rpg.data.quests_db import STORY_QUEST_CHAIN
        for key, target in (
            ("story_quests_active", p.story_quests_active),
            ("story_quests_goal_done", p.story_quests_goal_done),
            ("story_quests_completed", p.story_quests_completed),
        ):
            raw_quests = data.get(key, [])
            if isinstance(raw_quests, list):
                target.extend(
                    q for q in raw_quests
                    if isinstance(q, str) and q in STORY_QUEST_CHAIN
                )
        # Инварианты цепочки: сданный квест не может быть активным; цель
        # без активного квеста не имеет смысла; порядок — порядок цепочки.
        p.story_quests_active = [
            q for q in STORY_QUEST_CHAIN
            if q in p.story_quests_active and q not in p.story_quests_completed
        ]
        p.story_quests_goal_done = [
            q for q in p.story_quests_goal_done if q in p.story_quests_active
        ]
        p.story_quests_completed = [
            q for q in STORY_QUEST_CHAIN if q in p.story_quests_completed
        ]
        # Stage 173 — счётчики kill_mobs: только активные kill_mobs-квесты
        # цепочки, целые > 0, кэп по goal_count (мусор/сироты отбрасываются —
        # доступность квеста по-прежнему выводится из цепочки, консистентность
        # сейва не зависит от счётчика).
        from pockie_rpg.data.quests_db import STORY_QUESTS as _SQ_LD
        raw_kills = data.get("story_quests_kill_progress", {})
        kills: dict[str, int] = {}
        if isinstance(raw_kills, dict):
            for _kq, _kv in raw_kills.items():
                _kdef = _SQ_LD.get(_kq) if isinstance(_kq, str) else None
                if (_kdef is not None and _kdef.goal_type == "kill_mobs"
                        and _kq in p.story_quests_active
                        and isinstance(_kv, int) and not isinstance(_kv, bool)
                        and _kv > 0):
                    kills[_kq] = min(_kv, _kdef.goal_count)
        p.story_quests_kill_progress = kills
        # Stage 160 — разовый грант 6 костюмов Ичиго старым сейвам (тест
        # синтеза): флага нет в сейве → выдаём и запоминаем. Новые сейвы
        # получают костюмы через starter_items(), у них флаг ставится сразу.
        if data.get("synth_test_grant_v160", False):
            p.synth_test_grant_v160 = True
        else:
            for _ in range(6):
                p.inv_add("suit_ichigo")
            p.synth_test_grant_v160 = True
        # Stage 23 — refresh the cached CharacterStats snapshot now that
        # equipped_gear + base stats are both fully restored. This makes
        # player.stats valid immediately after load.
        p.recalc_stats()
        saved_hp = _get("current_hp", int, 0)
        saved_mp = _get("current_mp", int, 0)
        if saved_hp > 0:
            p.current_hp = min(saved_hp, p.stats.max_hp)
        else:
            p.current_hp = p.stats.max_hp
        if saved_mp > 0:
            p.current_mp = min(saved_mp, p.stats.max_mp)
        else:
            p.current_mp = p.stats.max_mp
        return p


def create_default_player() -> PlayerState:
    """Create a fresh player with Ichigo outfit + starter items."""
    from pockie_rpg.data.item_db import starter_items
    p = PlayerState(
        name="Игрок",
        suit_id="i290001",
        role_id=1,
        level=1,
        current_xp=0,
        max_xp=LEVEL_XP_CURVE,
        gold=0,
        # Stage 170 — тестовые купоны явно (раньше приходили из дефолта поля).
        coupons=TEST_START_COUPONS,
        # Stage 39 — base 10/10/10/200 (outfit adds 14/24/10).
        strength=10,
        agility=10,
        stamina=10,
        max_mp=200,
        equipped_outfit="suit_ichigo",
        active_skills=list(ROLE_ICHIGO.skills),
        # Stage 64 — inventory defaults to an empty paged dict via the
        # field's default_factory; starter items are added below.
    )
    # Stage 64 — place starter items into the paged inventory (page 1 first).
    for it in starter_items():
        p.inv_add(it)
    # Stage 160 — стартовые костюмы уже выданы выше; флаг блокирует
    # повторный грант при первом же from_dict (идемпотентность).
    p.synth_test_grant_v160 = True
    return p
