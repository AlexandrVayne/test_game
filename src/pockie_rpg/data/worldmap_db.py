"""Layer A — world map data «Sakura of mainland» (Stage 135).

Загружает assets/worldmap/config.json ОДИН раз при импорте модуля.
Только stdlib + lazy-импорт pockie_rpg.config (layering rule).
Единственный источник правды по уровням зон — WORLD_ZONES[zone_id].unlock_level.
"""
from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorldZone:
    """Зона мировой карты (35 шт.: 8 деревень + 27 локаций)."""

    zone_id: int
    name: str
    x: int
    y: int
    w: int
    h: int
    is_village: bool
    level_range: str
    unlock_level: int


@dataclass(frozen=True, slots=True)
class RouteMarker:
    """Фиолетовый маркер маршрута; подсвечивается при hover своей зоны."""

    x: int
    y: int
    r: int
    zone_id: int | None


def _load_worldmap() -> tuple[
    dict[int, WorldZone],
    tuple[RouteMarker, ...],
    tuple[int, int],
    tuple[int, int],
]:
    from pockie_rpg.config import ASSETS_DIR

    path = ASSETS_DIR / "worldmap" / "config.json"
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)

    zones: dict[int, WorldZone] = {}
    for z in raw["zones"]:
        zone = WorldZone(
            zone_id=int(z["id"]),
            name=str(z["name"]),
            x=int(z["x"]),
            y=int(z["y"]),
            w=int(z["w"]),
            h=int(z["h"]),
            is_village=bool(z["village"]),
            level_range=str(z.get("level", "?")),
            unlock_level=int(z.get("unlockLevel", 1)),
        )
        zones[zone.zone_id] = zone

    markers = tuple(
        RouteMarker(
            x=int(m["x"]),
            y=int(m["y"]),
            r=int(m["r"]),
            zone_id=int(m["zoneId"]) if m.get("zoneId") is not None else None,
        )
        for m in raw["routeMarkers"]
    )

    map_cfg = raw.get("map", {})
    size = (int(map_cfg.get("width", 768)), int(map_cfg.get("height", 426)))
    overlay_cfg = map_cfg.get("overlay", {})
    offset = (int(overlay_cfg.get("x", 31)), int(overlay_cfg.get("y", 48)))
    return zones, markers, size, offset


(
    WORLD_ZONES,
    ROUTE_MARKERS,
    WORLD_MAP_SIZE,
    OVERLAY_OFFSET,
) = _load_worldmap()

# Строгая привязка «зона → её маркер» (README §9): подсвечивается ТОЛЬКО
# маркер hovered-зоны. Первая привязка zoneId выигрывает (как в референсе).
ZONE_MARKER_INDEX: dict[int, int] = {}
for _i, _marker in enumerate(ROUTE_MARKERS):
    if _marker.zone_id is not None and _marker.zone_id not in ZONE_MARKER_INDEX:
        ZONE_MARKER_INDEX[_marker.zone_id] = _i


def _location_min_unlock() -> dict[int, int]:
    """Мин. уровень игрока для MapLocation.LOC1-4 — из WORLD_ZONES (источник правды)."""
    from pockie_rpg.config import ZONE_LOCATION_MAP

    out: dict[int, int] = {}
    for zone_id, loc in ZONE_LOCATION_MAP.items():
        zone = WORLD_ZONES.get(zone_id)
        if zone is None:
            continue
        current = out.get(loc)
        if current is None or zone.unlock_level < current:
            out[loc] = zone.unlock_level
    return out


LOCATION_MIN_UNLOCK: dict[int, int] = _location_min_unlock()
