"""Save/load player progression via JSON (Stage 9 — Fix 4).

Stage 88 — Fix 2.4 (atomic save): the save is now written to a temporary
file first, then ``os.replace()`` swaps it into place atomically. This
guarantees the save file is never left half-written even if the process
is killed or Windows crashes mid-write. A ``.bak`` backup of the previous
good save is kept for recovery.

Stage 88 — Fix 2.5 (autosave): the save module now exposes a lightweight
``mark_dirty(player)`` hook + a ``SaveManager`` class that the UI can use
to debounce saves (flush after 0.5s of inactivity, on QUIT, on screen
transitions). The legacy ``save_player_state(player)`` remains for direct
synchronous saves.

Stage 171 — B1 (rolling saves): после успешной загрузки primary на старте
сессии копия player_save.json архивируется в ``player_save_slot_<n>.json``
(n циклически 1→2→3). ``load_player_state`` при порче primary и .bak
спускается по слотам (новые раньше старых). ``load_from_slot(n)`` —
прямая загрузка слота (F9 dev-кнопки).

Stage 171 — B2 (validate_save): отчёт о целостности (перечень отброшенных
по типу полей) пишется в logger.warning и в ``LAST_LOAD_REPORT`` для F10.

Stage 171 — B4 (троттлинг): debounced-автосейв пишет на диск не чаще
``AUTOSAVE_MIN_INTERVAL_SECONDS``; flush() на переходах/QUIT — всегда.

Per Stage 9 spec:
  * Save file location: ``{PROJECT_ROOT}/data/player_save.json``.
  * ``save_player_state(player)`` serializes the PlayerState to JSON.
  * ``load_player_state()`` deserializes it back (or returns None if no save).
  * ``has_save()`` checks if a save file exists.
  * ``delete_save()`` removes the save file (for reset).

Per rule 11 (Core Decoupling): this module imports ONLY from ``game.state``
(PlayerState) and ``config`` (PROJECT_ROOT). It does NOT import ``ui``,
``combat``, or any pygame modules — it's a pure-stdlib JSON serializer
usable from any layer.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING

from pockie_rpg.config import PROJECT_ROOT
from pockie_rpg.game.state import PlayerState

if TYPE_CHECKING:
    pass


# Save file paths.
SAVE_DIR: Path = PROJECT_ROOT / "data"
SAVE_FILE_PATH: Path = SAVE_DIR / "player_save.json"
BACKUP_FILE_PATH: Path = SAVE_DIR / "player_save.json.bak"
TEMP_FILE_PATH: Path = SAVE_DIR / "player_save.json.tmp"

# Stage 171 — B1: rolling saves (межсессионные слоты-страховки).
ROLLING_SAVE_SLOTS: int = 3
SLOT_FILE_PREFIX: str = "player_save_slot"
# Stage 171 — B4: минимальный интервал дисковой записи debounced-автосейва.
AUTOSAVE_MIN_INTERVAL_SECONDS: float = 5.0

# Stage 171 — B2: отчёт последней загрузки (dict path/source/issues или None).
LAST_LOAD_REPORT: dict | None = None

# Stage 88 — Fix 2.4: save schema version for forward migrations.
# Bump when the save schema changes in a backward-incompatible way.
# from_dict must handle older versions (migration logic).
SAVE_VERSION: int = 2

# Logger (uses module name — silent by default unless configured).
logger = logging.getLogger(__name__)


def _ensure_save_dir() -> None:
    """Create the save directory if it doesn't exist (idempotent)."""
    SAVE_DIR.mkdir(parents=True, exist_ok=True)


def save_player_state(player: PlayerState) -> None:
    """Serialize the PlayerState to the save file (JSON, indent=2).

    Stage 88 — Fix 2.4 (atomic save): writes to a temp file first, calls
    ``flush()`` + ``os.fsync()`` to force the bytes to disk, then
    ``os.replace()`` swaps the temp file into the final path atomically.
    This guarantees the save file is never left in a half-written state
    even if the process is killed or Windows crashes mid-write. The
    previous good save is preserved as a ``.bak`` backup before the swap.

    Args:
        player: the PlayerState to serialize.

    Raises:
        OSError: if the save file cannot be written (disk full, permission
            denied, etc.). The caller should handle this gracefully.
    """
    _ensure_save_dir()
    data = player.to_dict()
    # Stage 88 — inject save schema version for future migrations.
    data["save_version"] = SAVE_VERSION

    # Stage 88 — Fix 2.4: atomic write via temp file + fsync + os.replace.
    # 1. Write to a temp file in the SAME directory as the save (so os.replace
    #    is atomic — it's a rename on the same filesystem).
    # 2. flush() + os.fsync() to force bytes to disk.
    # 3. If a previous good save exists, back it up to .bak (overwrite).
    # 4. os.replace() swaps the temp file into the final path atomically.
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=str(SAVE_DIR),
        prefix="player_save_",
        suffix=".tmp",
    )
    tmp_file = Path(tmp_path)
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        # Backup the previous good save (if any) before replacing.
        if SAVE_FILE_PATH.exists():
            try:
                # os.replace is atomic on the same filesystem — overwrites .bak.
                os.replace(SAVE_FILE_PATH, BACKUP_FILE_PATH)
            except OSError as exc:
                # Backup failure is non-fatal — log + continue.
                logger.warning("Failed to back up save file: %s", exc)
        # Atomic swap: temp → final path.
        os.replace(tmp_file, SAVE_FILE_PATH)
    except Exception:
        # Clean up the temp file on any error (don't leave stale .tmp files).
        try:
            tmp_file.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    logger.debug("Player state saved atomically to %s", SAVE_FILE_PATH)


def rolling_slot_path(n: int) -> Path:
    """Stage 171 — B1: путь слота N (1..ROLLING_SAVE_SLOTS)."""
    return SAVE_DIR / f"{SLOT_FILE_PREFIX}_{n}.json"


def _rolling_slot_paths() -> list[Path]:
    paths = [rolling_slot_path(n) for n in range(1, ROLLING_SAVE_SLOTS + 1)]
    return paths


def _next_rolling_slot() -> tuple[int, Path]:
    """Stage 171 — B1: следующий слот цикла 1→2→3.

    Сначала свободные (по возрастанию N), затем самый старый по mtime
    (при равенстве — меньший N). Одна архивация за сессию даёт ровно
    циклическую ротацию.
    """
    paths = _rolling_slot_paths()
    for n, path in enumerate(paths, start=1):
        if not path.exists():
            return n, path
    oldest_n, oldest_mtime = 1, paths[0].stat().st_mtime
    for n, path in enumerate(paths[1:], start=2):
        mtime = path.stat().st_mtime
        if mtime < oldest_mtime:
            oldest_n, oldest_mtime = n, mtime
    return oldest_n, paths[oldest_n - 1]


def archive_rolling_save() -> int | None:
    """Stage 171 — B1: копия player_save.json в следующий слот (1→2→3).

    Вызывается после успешной загрузки primary на старте сессии. Битый
    primary (не парсится как JSON) НЕ архивируется — слоты хранят только
    читаемые снимки. Запись атомарная (tmp + os.replace); сбой —
    не-фатальный warning.

    Returns:
        Номер слота, куда записан снимок, или None (нет primary/сбой).
    """
    if not SAVE_FILE_PATH.exists():
        return None
    try:
        raw = SAVE_FILE_PATH.read_bytes()
        json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.warning("Rolling save skipped — primary unreadable: %s", exc)
        return None
    _ensure_save_dir()
    n, slot_path = _next_rolling_slot()
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=str(SAVE_DIR), prefix="slot_", suffix=".tmp",
    )
    tmp_file = Path(tmp_path)
    try:
        with os.fdopen(tmp_fd, "wb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_file, slot_path)
    except OSError as exc:
        try:
            tmp_file.unlink(missing_ok=True)
        except OSError:
            pass
        logger.warning("Rolling save to %s failed: %s", slot_path, exc)
        return None
    logger.debug("Rolling save archived to slot %d (%s)", n, slot_path)
    return n


def load_from_slot(n: int) -> PlayerState | None:
    """Stage 171 — B1: прямая загрузка PlayerState из слота N (F9 dev-кнопки).

    Успешная загрузка обновляет LAST_LOAD_REPORT (source = «слот N»).
    """
    path = rolling_slot_path(n)
    if not path.exists():
        logger.warning("Save slot %d not found: %s", n, path)
        return None
    player, issues = _try_load_from_path(path, is_backup=False)
    if player is None:
        return None
    _set_load_report(path, f"слот {n}", issues)
    return player


def _set_load_report(path: Path, source: str, issues: list[str]) -> None:
    global LAST_LOAD_REPORT
    LAST_LOAD_REPORT = {
        "path": str(path),
        "source": source,
        "issues": list(issues),
    }


def load_player_state() -> PlayerState | None:
    """Load the PlayerState from the save file, or return None if absent/corrupt.

    Stage 88 — Fix 2.4: if the primary save file is corrupted (invalid JSON
    or missing required fields), the loader attempts to recover from the
    ``.bak`` backup file before giving up. This provides resilience against
    partial writes that slipped through the old non-atomic save.

    Stage 171 — B1: цепочка источников расширена — primary → .bak →
    rolling-слоты (новые раньше старых, по mtime). После успешной загрузки
    primary текущий player_save.json архивируется в следующий слот.

    Returns:
        A reconstructed PlayerState, or None if no save or every source
        (primary + backup + все слоты) нечитаем.
    """
    if SAVE_FILE_PATH.exists():
        player, issues = _try_load_from_path(SAVE_FILE_PATH, is_backup=False)
        if player is not None:
            _set_load_report(SAVE_FILE_PATH, "primary", issues)
            archive_rolling_save()
            return player
    if BACKUP_FILE_PATH.exists():
        logger.warning(
            "Primary save at %s is corrupt/absent — attempting backup at %s",
            SAVE_FILE_PATH, BACKUP_FILE_PATH,
        )
        player, issues = _try_load_from_path(BACKUP_FILE_PATH, is_backup=True)
        if player is not None:
            _set_load_report(BACKUP_FILE_PATH, "backup", issues)
            return player
    existing_slots = [
        (n, path) for n, path in enumerate(_rolling_slot_paths(), start=1)
        if path.exists()
    ]
    existing_slots.sort(key=lambda np: np[1].stat().st_mtime, reverse=True)
    for n, path in existing_slots:
        player, issues = _try_load_from_path(path, is_backup=False)
        if player is not None:
            logger.warning("Recovered progress from rolling slot %d: %s", n, path)
            _set_load_report(path, f"слот {n}", issues)
            return player
    return None


def _try_load_from_path(
    path: Path, *, is_backup: bool,
) -> tuple[PlayerState | None, list[str]]:
    """Attempt to load + reconstruct a PlayerState from a specific JSON file.

    Defensive (per rule 10): returns (None, issues) on any parse or
    reconstruction error — the caller falls back to the next source
    (backup or default).

    Stage 171 — B2: перед реконструкцией запускается validate_save();
    найденные проблемы логируются и возвращаются второй частью кортежа.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        label = "backup" if is_backup else "save"
        logger.warning("%s file at %s is corrupted: %s", label.title(), path, exc)
        return None, []
    except Exception as exc:  # noqa: BLE001 — defensive: any other error.
        label = "backup" if is_backup else "save"
        logger.warning("Unexpected error loading %s: %s", label, exc)
        return None, []

    if not isinstance(data, dict):
        logger.warning("Save file at %s is not a dict: %r", path, type(data))
        return None, []

    # Stage 88 — Fix 2.4: save_version migration hook.
    # Currently version 2 (the first versioned save). Older saves lack the
    # field → treated as version 1 (no migration needed — from_dict handles
    # missing fields defensively). Future migrations would go here.
    _version = data.get("save_version", 1)
    # No migrations defined yet for v1 → v2 (v2 only adds save_version field).

    # Stage 171 — B2: отчёт о целостности (поля, которые from_dict отбросит).
    issues = validate_save(data)
    if issues:
        logger.warning(
            "Save integrity report for %s — %d проблема(и): %s",
            path, len(issues), "; ".join(issues),
        )

    try:
        return PlayerState.from_dict(data), issues
    except Exception as exc:  # noqa: BLE001 — defensive.
        logger.warning("Failed to reconstruct PlayerState from %s: %s", path, exc)
        return None, issues


def has_save() -> bool:
    """Return True if a save file exists at SAVE_FILE_PATH (or backup)."""
    return SAVE_FILE_PATH.exists() or BACKUP_FILE_PATH.exists()


def delete_save() -> None:
    """Remove the save file + backup (used for reset).

    Per Stage 9 spec: idempotent — if the files don't exist, this is a no-op.
    """
    for path in (SAVE_FILE_PATH, BACKUP_FILE_PATH, TEMP_FILE_PATH):
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Failed to delete %s: %s", path, exc)
    logger.debug("Save files deleted")


# ---------------------------------------------------------------------------
# Stage 171 — B2: validate_save — отчёт о целостности сейва
# ---------------------------------------------------------------------------

_INT_FIELDS: tuple[str, ...] = (
    "level", "current_xp", "max_xp", "gold", "coupons",
    "strength", "agility", "stamina", "max_mp",
    "_gem_id_counter", "gen_w_counter", "_outfit_inst_counter",
    "world_boss_attempts", "save_version",
)
_NUM_FIELDS: tuple[str, ...] = (
    "_str_accum", "_agi_accum", "_sta_accum",
    "slot_next_roll_ts", "world_boss_next_attempt_ts",
)
_STR_FIELDS: tuple[str, ...] = ("name", "suit_id", "daily_quest_date")
_STRNONE_FIELDS: tuple[str, ...] = ("active_title", "equipped_outfit")
_STR_LIST_FIELDS: tuple[str, ...] = ("defeated_mobs", "daily_quest_claimed")
_EQUIP_SLOTS: tuple[str, ...] = (
    "weapon", "head", "body", "hands", "belt", "boots",
    "accessory", "accessory2", "outfit",
)
_GEM_SLOTS: tuple[str, ...] = _EQUIP_SLOTS[:-1]


def _type_name(value: object) -> str:
    if value is None:
        return "null"
    return type(value).__name__


def validate_save(data: dict) -> list[str]:
    """Stage 171 — B2: перечень полей сейва, которые from_dict отбросит/заменит.

    Проверяются ТОЛЬКО присутствующие ключи: отсутствие поля — легальная
    ситуация (старые сейвы → дефолты). Удаляемые ключи старых сейвов
    (auto_sell_grey, slot_history, tower_attempts, tower_next_attempt_ts)
    игнорируются намеренно — не сообщаются. Сравнение типов зеркалит
    фактические проверки from_dict (bool допустим для int и т.п.).

    Returns:
        list[str] — человекочитаемые проблемы; пустой список = сейв чист.
    """
    issues: list[str] = []
    if not isinstance(data, dict):
        return ["корневой объект не dict"]

    for key in _INT_FIELDS:
        if key in data and not isinstance(data[key], int):
            issues.append(
                f"{key}: ожидался int, получен {_type_name(data[key])}"
            )
    for key in _NUM_FIELDS:
        if key in data:
            value = data[key]
            if value is not None and (
                not isinstance(value, (int, float)) or isinstance(value, bool)
            ):
                issues.append(
                    f"{key}: ожидался int|float|null, получен {_type_name(value)}"
                )
    for key in _STR_FIELDS:
        if key in data and not isinstance(data[key], str):
            issues.append(
                f"{key}: ожидался str, получен {_type_name(data[key])}"
            )
    for key in _STRNONE_FIELDS:
        if key in data and not (data[key] is None or isinstance(data[key], str)):
            issues.append(
                f"{key}: ожидался str|null, получен {_type_name(data[key])}"
            )

    raw_mobs = data.get("defeated_mobs")
    for key in _STR_LIST_FIELDS:
        raw = data.get(key)
        if key in data and not isinstance(raw, list):
            issues.append(f"{key}: ожидался список, получен {_type_name(raw)}")
    if isinstance(raw_mobs, list):
        bad = [m for m in raw_mobs if not isinstance(m, str)]
        if bad:
            issues.append(
                f"defeated_mobs: {len(bad)} не-str элементов отброшено"
            )
    # Stage 172 — сюжетные квесты: не-str и неизвестные цепочке id отбрасываются.
    from pockie_rpg.data.quests_db import STORY_QUEST_CHAIN
    for key in ("story_quests_active", "story_quests_goal_done",
                "story_quests_completed"):
        raw_quests = data.get(key)
        if not isinstance(raw_quests, list):
            continue
        bad_type = [q for q in raw_quests if not isinstance(q, str)]
        bad_unknown = [
            q for q in raw_quests
            if isinstance(q, str) and q not in STORY_QUEST_CHAIN
        ]
        if bad_type:
            issues.append(f"{key}: {len(bad_type)} не-str элементов отброшено")
        if bad_unknown:
            issues.append(
                f"{key}: {len(bad_unknown)} неизвестных квестов отброшено"
            )
    # Stage 173 — счётчики kill_mobs: dict {quest_id: int}.
    raw_kills = data.get("story_quests_kill_progress")
    if raw_kills is not None and not isinstance(raw_kills, dict):
        issues.append(
            f"story_quests_kill_progress: ожидался dict, получен "
            f"{type(raw_kills).__name__} — отброшено"
        )
    elif isinstance(raw_kills, dict):
        bad_keys = [k for k in raw_kills
                    if not isinstance(k, str) or k not in STORY_QUEST_CHAIN]
        bad_vals = [
            v for v in raw_kills.values()
            if not isinstance(v, int) or isinstance(v, bool) or v < 0
        ]
        if bad_keys:
            issues.append(
                f"story_quests_kill_progress: {len(bad_keys)} неизвестных "
                f"квестов отброшено"
            )
        if bad_vals:
            issues.append(
                f"story_quests_kill_progress: {len(bad_vals)} "
                f"не-целых/отрицательных значений отброшено"
            )
    if "active_skills" in data and isinstance(data.get("active_skills"), list):
        bad = [s for s in data["active_skills"]
               if not isinstance(s, int) or isinstance(s, bool)]
        if bad:
            issues.append(f"active_skills: {len(bad)} не-int элементов отброшено")
    if "tower_first_clear_claimed" in data and isinstance(
        data.get("tower_first_clear_claimed"), list,
    ):
        from pockie_rpg.config import TOWER_MAX_FLOOR
        bad = [f for f in data["tower_first_clear_claimed"]
               if not isinstance(f, (int, float)) or not 1 <= int(f) <= TOWER_MAX_FLOOR]
        if bad:
            issues.append(
                f"tower_first_clear_claimed: {len(bad)} вне 1..{TOWER_MAX_FLOOR}"
            )

    raw_gear = data.get("equipped_gear")
    if "equipped_gear" in data and not isinstance(raw_gear, dict):
        issues.append(f"equipped_gear: ожидался dict, получен {_type_name(raw_gear)}")
    elif isinstance(raw_gear, dict):
        for slot, val in raw_gear.items():
            if slot not in _EQUIP_SLOTS:
                issues.append(f"equipped_gear[{slot!r}]: неизвестный слот отброшен")
            elif not (val is None or isinstance(val, str)):
                issues.append(
                    f"equipped_gear[{slot}]: ожидался str|null, получен {_type_name(val)}"
                )

    raw_inv = data.get("inventory")
    if "inventory" in data and not (
        isinstance(raw_inv, dict) or isinstance(raw_inv, list)
    ):
        issues.append(f"inventory: ожидался dict|list, получен {_type_name(raw_inv)}")
    elif isinstance(raw_inv, dict):
        from pockie_rpg.config import INVENTORY_PAGE_KEYS
        for page_key, slots in raw_inv.items():
            try:
                page = int(page_key)
            except (TypeError, ValueError):
                issues.append(
                    f"inventory[{page_key!r}]: нечисловая страница отброшена"
                )
                continue
            if page not in INVENTORY_PAGE_KEYS:
                issues.append(f"inventory[{page}]: страница вне 1..10 отброшена")
                continue
            if not isinstance(slots, list):
                issues.append(
                    f"inventory[{page}]: ожидался список, получен {_type_name(slots)}"
                )
                continue
            bad = [
                i for i in slots
                # Stage 183 — валидны: None, str (шмот) и dict-стак
                # {"item_id": str, "count": int>0}.
                if not (
                    i is None
                    or isinstance(i, str)
                    or (isinstance(i, dict)
                        and isinstance(i.get("item_id"), str)
                        and isinstance(i.get("count"), (int, float))
                        and int(i.get("count", 0)) > 0)
                )
            ]
            if bad:
                issues.append(
                    f"inventory[{page}]: {len(bad)} не-str слотов отброшено"
                )

    raw_ench = data.get("gear_enchants")
    if "gear_enchants" in data and not isinstance(raw_ench, dict):
        issues.append(f"gear_enchants: ожидался dict, получен {_type_name(raw_ench)}")
    elif isinstance(raw_ench, dict):
        bad = [k for k, v in raw_ench.items()
               if not isinstance(v, (int, float)) or isinstance(v, bool) or int(v) <= 0]
        if bad:
            issues.append(f"gear_enchants: {len(bad)} нечисловых/нулевых значений")

    raw_gems = data.get("gem_inventory")
    if "gem_inventory" in data and not isinstance(raw_gems, list):
        issues.append(f"gem_inventory: ожидался список, получен {_type_name(raw_gems)}")
    elif isinstance(raw_gems, list):
        bad = [g for g in raw_gems
               if not (isinstance(g, dict) and "id" in g and "type" in g and "level" in g)]
        if bad:
            issues.append(f"gem_inventory: {len(bad)} записей без id/type/level")

    raw_gslots = data.get("gear_gem_slots")
    if "gear_gem_slots" in data and not isinstance(raw_gslots, dict):
        issues.append(f"gear_gem_slots: ожидался dict, получен {_type_name(raw_gslots)}")
    elif isinstance(raw_gslots, dict):
        for slot, slots_list in raw_gslots.items():
            if slot not in _GEM_SLOTS:
                issues.append(f"gear_gem_slots[{slot!r}]: неизвестный слот отброшен")
            elif not isinstance(slots_list, list):
                issues.append(
                    f"gear_gem_slots[{slot}]: ожидался список, получен {_type_name(slots_list)}"
                )

    for key in ("daily_quest_progress", "tower_materials"):
        raw = data.get(key)
        if key in data and not isinstance(raw, dict):
            issues.append(f"{key}: ожидался dict, получен {_type_name(raw)}")
        elif isinstance(raw, dict):
            bad = [k for k, v in raw.items()
                   if not isinstance(v, (int, float)) or isinstance(v, bool)]
            if bad:
                issues.append(f"{key}: {len(bad)} нечисловых значений отброшено")

    raw_boss = data.get("world_boss_hp")
    if "world_boss_hp" in data and not (raw_boss is None or isinstance(raw_boss, dict)):
        issues.append(f"world_boss_hp: ожидался dict|null, получен {_type_name(raw_boss)}")
    elif isinstance(raw_boss, dict):
        required = ("level", "max_hp", "current_hp", "location",
                    "min_atk", "max_atk", "killed_count")
        missing = [k for k in required
                   if not isinstance(raw_boss.get(k), (int, float))
                   or isinstance(raw_boss.get(k), bool)]
        if missing:
            issues.append(f"world_boss_hp: нет/битые ключи {', '.join(missing)}")

    raw_gen = data.get("generated_weapons")
    if "generated_weapons" in data and not isinstance(raw_gen, dict):
        issues.append(f"generated_weapons: ожидался dict, получен {_type_name(raw_gen)}")
    elif isinstance(raw_gen, dict):
        bad = [k for k, v in raw_gen.items()
               if not (isinstance(v, dict) and v.get("generated") is True)]
        if bad:
            issues.append(
                f"generated_weapons: {len(bad)} записей без generated=True отброшено"
            )

    raw_inst = data.get("outfit_instances")
    if "outfit_instances" in data and not isinstance(raw_inst, dict):
        issues.append(f"outfit_instances: ожидался dict, получен {_type_name(raw_inst)}")
    elif isinstance(raw_inst, dict):
        bad = [k for k, v in raw_inst.items()
               if not (isinstance(k, str) and isinstance(v, dict)
                       and isinstance(v.get("outfit_id"), str))]
        if bad:
            issues.append(
                f"outfit_instances: {len(bad)} записей без outfit_id отброшено"
            )

    raw_ward = data.get("wardrobe")
    if "wardrobe" in data and not isinstance(raw_ward, list):
        issues.append(f"wardrobe: ожидался список, получен {_type_name(raw_ward)}")
    elif isinstance(raw_ward, list):
        bad = [i for i in raw_ward if not (i is None or isinstance(i, str))]
        if bad:
            issues.append(f"wardrobe: {len(bad)} не-str слотов отброшено")

    raw_winpos = data.get("window_positions")
    if "window_positions" in data and not isinstance(raw_winpos, dict):
        issues.append(f"window_positions: ожидался dict, получен {_type_name(raw_winpos)}")
    elif isinstance(raw_winpos, dict):
        bad = [k for k, v in raw_winpos.items()
               if not (isinstance(v, list) and len(v) == 2
                       and all(isinstance(c, (int, float)) for c in v))]
        if bad:
            issues.append(f"window_positions: {len(bad)} записей без пары [x, y]")

    return issues


# ---------------------------------------------------------------------------
# Stage 88 — Fix 2.5: debounced autosave via SaveManager
# ---------------------------------------------------------------------------

# Debounce window: after mark_dirty() is called, wait this many seconds of
# inactivity before flushing the save to disk. Prevents excessive disk I/O
# when the player rapidly toggles skills or drags inventory items.
AUTOSAVE_DEBOUNCE_SECONDS: float = 0.5


class SaveManager:
    """Lightweight debounce-based autosave manager.

    Usage pattern (in PygameUI):
        self.save_mgr = SaveManager(self.player)
        # After ANY mutation to player state:
        self.save_mgr.mark_dirty()
        # In the main loop (every frame):
        self.save_mgr.update(dt)
        # On QUIT or screen transition:
        self.save_mgr.flush()

    The manager tracks a ``_dirty`` flag + a ``_debounce_timer``. When
    ``mark_dirty()`` is called, the flag is set and the timer resets to
    ``AUTOSAVE_DEBOUNCE_SECONDS``. Each ``update(dt)`` call decrements the
    timer; when it reaches 0 AND dirty is True, the save is flushed
    synchronously and the flag is cleared. ``flush()`` forces an immediate
    save if dirty (used on QUIT / screen transitions).

    Stage 171 — B4 (троттлинг): debounced-запись (путь update) выполняется
    не чаще ``AUTOSAVE_MIN_INTERVAL_SECONDS`` — спорадические fsync-хичи
    10-50 мс реже 1 раза в 5 с. ``flush()`` (переходы экранов, QUIT) пишет
    ВСЕГДА, минуя троттлинг. Асинхронная запись в worker-поток отклонена
    (риск гонок/зависаний на QUIT не окупается в одно-процессной игре).
    """

    def __init__(self, player: PlayerState) -> None:
        self._player: PlayerState = player
        self._dirty: bool = False
        self._debounce_timer: float = 0.0
        # Stage 171 — B4: monotonic-метка последней дисковой записи.
        self._last_write: float = 0.0

    def set_player(self, player: PlayerState) -> None:
        """Swap the player reference (used after load_player_state on startup)."""
        self._player = player
        self._dirty = False
        self._debounce_timer = 0.0

    def mark_dirty(self) -> None:
        """Mark the player state as modified — schedules a debounced save."""
        self._dirty = True
        self._debounce_timer = AUTOSAVE_DEBOUNCE_SECONDS

    def update(self, dt: float) -> None:
        """Per-frame update — decrements the debounce timer + flushes if expired.

        Stage 171 — B4: когда debounce истёк, запись дополнительно
        троттлится ``AUTOSAVE_MIN_INTERVAL_SECONDS`` от последней дисковой
        записи; до истечения троттлинга таймер откладывается на остаток.

        Args:
            dt: frame delta in seconds (from clock.tick(60) / 1000.0).
        """
        if not self._dirty:
            return
        self._debounce_timer -= dt
        if self._debounce_timer > 0.0:
            return
        wait = AUTOSAVE_MIN_INTERVAL_SECONDS - (time.monotonic() - self._last_write)
        if wait > 0.0:
            self._debounce_timer = wait
            return
        self.flush()

    def flush(self) -> None:
        """Force an immediate save if the state is dirty (used on QUIT / transition).

        Stage 171 — B4: НЕ троттлится (переходы экранов/QUIT — обязательная
        запись); метка _last_write обновляется даже при сбое (защита от
        шторма повторов каждый кадр при постоянной ошибке диска).
        Аудит 2026-09 — при сбое записи (OSError/Exception) dirty-флаг
        БОЛЬШЕ НЕ сбрасывается: раньше потеря диска молча «съедала» ожидающий
        сейв (повтор не планировался до следующего mark_dirty → потеря
        прогресса на QUIT). Повтор планируется на ближайший update()/
        flush(); от шторма защищает _last_write-троттлинг в update().
        """
        if not self._dirty:
            return
        try:
            save_player_state(self._player)
        except OSError as exc:
            logger.warning("Autosave failed (will retry): %s", exc)
            self._last_write = time.monotonic()
            return
        except Exception as exc:  # noqa: BLE001 — defensive.
            logger.warning("Autosave unexpected error (will retry): %s", exc)
            self._last_write = time.monotonic()
            return
        self._dirty = False
        self._debounce_timer = 0.0
        self._last_write = time.monotonic()

    @property
    def is_dirty(self) -> bool:
        """True if there are unsaved changes pending."""
        return self._dirty
