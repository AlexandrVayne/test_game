"""WorldMapRendererMixin — Stage 135, модалка мировой карты «Sakura of mainland».

Порт интерактивной карты (README §5-§17 из pockie_worldmap_clean.zip) на Pygame.
ПРАВИЛО 9: это boolean-флаг _worldmap_modal_open внутри GameState.MAP, НЕ новый
GameState. Все координаты зон/маркеров — в логической системе 768×426; на экран
выводятся с масштабом WORLDMAP_SCALE=1.0 — ОРИГИНАЛЬНЫЙ размер ассета
(панель 768×426 по центру 1280×720; Stage 136 снизил 1.4→1.0, Stage 161
подтвердил: карта НЕ увеличена).

Слои (README §5): фон → платформы (up/over; неактивные — обесцвеченный up) →
overlay.png со сдвигом OVERLAY_OFFSET (как вшитые дома, так и маркеры — БЕЗ
обесцвечивания: bbox-прямоугольники перекрываются и портят активные зоны) →
маркеры → 🔒-бейджи.
Хиттест (README §10): pygame.mask.from_surface(b{id}_hit.png, 127), при
пересечении нескольких зон побеждает МЕНЬШАЯ по площади.
Маркеры (README §8-§9): ВСЕГДА фиолетовые; при hover подсвечивается ТОЛЬКО
маркер, привязанный к зоне по zoneId (ZONE_MARKER_INDEX); остальные маркеры
не меняются (константная альфа WORLDMAP_MARKER_GLOW_ALPHA).
"""
from __future__ import annotations

import math

import pygame

from pockie_rpg.config import (
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    WORLDMAP_BTN_H,
    WORLDMAP_BTN_W,
    WORLDMAP_DESAT_FLOOR,
    WORLDMAP_DESAT_MUL,
    WORLDMAP_HILIGHT_CORE,
    WORLDMAP_HILIGHT_EDGE,
    WORLDMAP_HILIGHT_MID,
    WORLDMAP_HILIGHT_PHASE,
    WORLDMAP_HILIGHT_PULSE_MS,
    WORLDMAP_HILIGHT_WHITE,
    WORLDMAP_LOCATION_ZONE,
    WORLDMAP_LOCK_BG,
    WORLDMAP_LOCK_BODY,
    WORLDMAP_LOCK_BORDER,
    WORLDMAP_LOCKED_TOAST_SEC,
    WORLDMAP_MARKER_COLOR,
    WORLDMAP_MARKER_GLOW_ALPHA,
    WORLDMAP_PANEL_H,
    WORLDMAP_PANEL_W,
    WORLDMAP_PANEL_X,
    WORLDMAP_PANEL_Y,
    WORLDMAP_PLAYER_COLOR,
    WORLDMAP_PLAYER_CORE_COLOR,
    WORLDMAP_PLAYER_GLOW_ALPHA,
    WORLDMAP_PLAYER_PULSE_MS,
    WORLDMAP_PLAYER_PULSE_PHASE,
    WORLDMAP_PULSE_MS,
    WORLDMAP_PULSE_PHASE,
    WORLDMAP_SCALE,
    WORLDMAP_TIP_BG,
    WORLDMAP_TIP_BORDER,
    WORLDMAP_TIP_SUB_LOCATION,
    WORLDMAP_TIP_SUB_LOCKED,
    WORLDMAP_TIP_SUB_VILLAGE,
    WORLDMAP_TIP_TEXT,
    WORLDMAP_TIP_VILLAGE_BORDER,
    WORLDMAP_TOOLTIP_OFFSET_X,
    ZONE_LOCATION_MAP,
)
from pockie_rpg.data.worldmap_db import (
    OVERLAY_OFFSET,
    ROUTE_MARKERS,
    WORLD_MAP_SIZE,
    WORLD_ZONES,
    ZONE_MARKER_INDEX,
)
from pockie_rpg.ui.animator import ClickRect

_F_WM_NAME = pygame.font.SysFont("dejavusans,arial", 13, bold=True)
_F_WM_SUB = pygame.font.SysFont("dejavusans,arial", 11)
_F_WM_TOAST = pygame.font.SysFont("dejavusans,arial", 12, bold=True)

_WM_ASSETS: dict | None = None


def _desaturate(surface: pygame.Surface) -> pygame.Surface:
    """README §6: gray = 0.30R + 0.59G + 0.11B; V = gray*MUL + FLOOR (stdlib-only)."""
    raw = bytearray(pygame.image.tobytes(surface, "RGBA"))
    mul = WORLDMAP_DESAT_MUL
    floor = WORLDMAP_DESAT_FLOOR
    for i in range(0, len(raw), 4):
        if raw[i + 3] == 0:
            continue
        gray = 0.30 * raw[i] + 0.59 * raw[i + 1] + 0.11 * raw[i + 2]
        v = int(gray * mul) + floor
        raw[i] = v
        raw[i + 1] = v
        raw[i + 2] = v
    return pygame.image.frombytes(bytes(raw), surface.get_size(), "RGBA").convert_alpha()


def _load_worldmap_assets() -> dict | None:
    """Разовая загрузка ассетов + масок (после pygame.display.set_mode)."""
    global _WM_ASSETS
    if _WM_ASSETS is not None:
        return _WM_ASSETS or None
    try:
        from pockie_rpg.config import ASSETS_DIR

        base = ASSETS_DIR / "worldmap"
        bg = pygame.image.load(str(base / "background.jpg")).convert()
        overlay = pygame.image.load(str(base / "overlay.png")).convert_alpha()
        map_w, map_h = WORLD_MAP_SIZE
        panel_w = int(map_w * WORLDMAP_SCALE)
        panel_h = int(map_h * WORLDMAP_SCALE)

        ups: dict[int, pygame.Surface] = {}
        overs: dict[int, pygame.Surface] = {}
        ups_desat: dict[int, pygame.Surface] = {}
        masks: dict[int, pygame.mask.Mask] = {}
        for zone_id, zone in WORLD_ZONES.items():
            up = pygame.image.load(
                str(base / "buttons" / f"b{zone_id}_up.png")
            ).convert_alpha()
            over = pygame.image.load(
                str(base / "buttons" / f"b{zone_id}_over.png")
            ).convert_alpha()
            hit = pygame.image.load(
                str(base / "buttons" / f"b{zone_id}_hit.png")
            ).convert_alpha()
            ups[zone_id] = up
            overs[zone_id] = over
            ups_desat[zone_id] = _desaturate(up)
            masks[zone_id] = pygame.mask.from_surface(hit, 127)

        ups_scaled = {
            zid: pygame.transform.smoothscale(
                s,
                (
                    round(WORLD_ZONES[zid].w * WORLDMAP_SCALE),
                    round(WORLD_ZONES[zid].h * WORLDMAP_SCALE),
                ),
            )
            for zid, s in ups.items()
        }
        overs_scaled = {
            zid: pygame.transform.smoothscale(s, ups_scaled[zid].get_size())
            for zid, s in overs.items()
        }
        ups_desat_scaled = {
            zid: pygame.transform.smoothscale(s, ups_scaled[zid].get_size())
            for zid, s in ups_desat.items()
        }

        _WM_ASSETS = {
            "bg": pygame.transform.smoothscale(bg, (panel_w, panel_h)),
            "overlay": overlay,
            "ups_scaled": ups_scaled,
            "overs_scaled": overs_scaled,
            "ups_desat_scaled": ups_desat_scaled,
            "masks": masks,
        }
        return _WM_ASSETS
    except Exception as exc:
        print(f"[WorldMap] ассеты карты недоступны: {exc}")
        _WM_ASSETS = {}
        return None


def _draw_glow(
    screen: pygame.Surface,
    cx: int,
    cy: int,
    radius: int,
    color: tuple[int, int, int],
    max_alpha: int,
) -> None:
    """Радиальное свечение концентрическими кругами (маленькая SRCALPHA-поверхность)."""
    if radius <= 0:
        return
    surf = pygame.Surface((radius * 2 + 2, radius * 2 + 2), pygame.SRCALPHA)
    center = (radius + 1, radius + 1)
    steps = 7
    for s in range(steps, 0, -1):
        k = s / steps
        alpha = int(max_alpha * (1.0 - k))
        if alpha <= 0:
            continue
        pygame.draw.circle(surf, (*color, alpha), center, max(1, int(radius * k)))
    pygame.draw.circle(surf, (*color, max_alpha), center, max(2, radius // 6))
    screen.blit(surf, (cx - radius - 1, cy - radius - 1))


def _draw_hilight(
    screen: pygame.Surface,
    cx: int,
    cy: int,
    core_r: int,
    glow_r: int,
) -> None:
    """Золотая подсветка hovered-маркера (README §8): внешний пульс + ядро."""
    if glow_r > 0:
        surf = pygame.Surface((glow_r * 2 + 2, glow_r * 2 + 2), pygame.SRCALPHA)
        center = (glow_r + 1, glow_r + 1)
        steps = 8
        for s in range(steps, 0, -1):
            k = s / steps
            alpha = int(255 * (1.0 - k) ** 1.2)
            if alpha <= 0:
                continue
            color = (
                WORLDMAP_HILIGHT_WHITE
                if k < 0.35
                else WORLDMAP_HILIGHT_EDGE
            )
            pygame.draw.circle(surf, (*color, alpha), center, max(1, int(glow_r * k)))
        screen.blit(surf, (cx - glow_r - 1, cy - glow_r - 1))
    if core_r > 0:
        surf = pygame.Surface((core_r * 2 + 2, core_r * 2 + 2), pygame.SRCALPHA)
        center = (core_r + 1, core_r + 1)
        steps = 8
        for s in range(steps, 0, -1):
            k = s / steps
            if k > 0.62:
                continue
            t = k / 0.62
            color = (
                int(WORLDMAP_HILIGHT_CORE[0] + (WORLDMAP_HILIGHT_MID[0] - WORLDMAP_HILIGHT_CORE[0]) * t),
                int(WORLDMAP_HILIGHT_CORE[1] + (WORLDMAP_HILIGHT_MID[1] - WORLDMAP_HILIGHT_CORE[1]) * t),
                int(WORLDMAP_HILIGHT_CORE[2] + (WORLDMAP_HILIGHT_MID[2] - WORLDMAP_HILIGHT_CORE[2]) * t),
            )
            alpha = int(255 * (1.0 - t) + 26)
            pygame.draw.circle(surf, (*color, min(255, alpha)), center, max(1, int(core_r * k)))
        pygame.draw.circle(surf, (*WORLDMAP_HILIGHT_CORE, 255), center, max(2, core_r // 3))
        screen.blit(surf, (cx - core_r - 1, cy - core_r - 1))


def _draw_dashed_rect(
    screen: pygame.Surface,
    rect: pygame.Rect,
    color: tuple[int, int, int],
    dash: int = 6,
    gap: int = 4,
    width: int = 2,
) -> None:
    """Пунктирная рамка выбранной зоны (README §6: setLineDash([6,4]))."""
    x0, y0 = rect.topleft
    x1, y1 = rect.right, rect.bottom

    def _line(a: tuple[int, int], b: tuple[int, int]) -> None:
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = max(1, int(math.hypot(dx, dy)))
        step = dash + gap
        pos = 0
        while pos < length:
            t0 = pos / length
            t1 = min(length, pos + dash) / length
            pygame.draw.line(
                screen,
                color,
                (int(a[0] + dx * t0), int(a[1] + dy * t0)),
                (int(a[0] + dx * t1), int(a[1] + dy * t1)),
                width,
            )
            pos += step

    _line((x0, y0), (x1, y0))
    _line((x0, y1), (x1, y1))
    _line((x0, y0), (x0, y1))
    _line((x1, y0), (x1, y1))


class WorldMapRendererMixin:
    """Модалка мировой карты (ПРАВИЛО 9: флаг _worldmap_modal_open)."""

    def _open_worldmap_modal(self) -> None:
        self._worldmap_modal_open = True
        self._worldmap_hovered_zone = None
        self._worldmap_selected_zone = None
        self._worldmap_locked_timer = 0.0
        self._worldmap_locked_name = ""
        # Stage 152 — общий механизм fade (ScalableRendererMixin).
        self._modal_fade_begin("worldmap")

    def _close_worldmap_modal(self) -> None:
        self._worldmap_modal_open = False
        self._worldmap_hovered_zone = None
        self._modal_fade_end("worldmap")

    def _update_worldmap_fade(self, dt: float) -> None:
        """Stage 136/152 — плавное появление модалки (общий fade, MODAL_FADE_SEC)."""
        if not self._worldmap_modal_open:
            return
        self._modal_fade_tick("worldmap", dt)

    def _worldmap_player_zone_id(self) -> int | None:
        """Stage 136 — zone_id текущего положения игрока (по self._map_location)."""
        return WORLDMAP_LOCATION_ZONE.get(self._map_location.value)

    def _worldmap_panel_rect(self) -> pygame.Rect:
        return pygame.Rect(WORLDMAP_PANEL_X, WORLDMAP_PANEL_Y, WORLDMAP_PANEL_W, WORLDMAP_PANEL_H)

    def _worldmap_zone_at(self, mx: float, my: float) -> object | None:
        """README §10: пиксель-перфект хиттест; меньшая зона побеждает."""
        assets = _load_worldmap_assets()
        if not assets:
            return None
        masks: dict[int, pygame.mask.Mask] = assets["masks"]
        best = None
        for zone in WORLD_ZONES.values():
            half_w = zone.w / 2
            half_h = zone.h / 2
            if mx < zone.x - half_w or mx > zone.x + half_w or my < zone.y - half_h or my > zone.y + half_h:
                continue
            mask = masks.get(zone.zone_id)
            if mask is not None:
                mw, mh = mask.get_size()
                lx = int(round(mx - (zone.x - mw / 2)))
                ly = int(round(my - (zone.y - mh / 2)))
                if lx < 0 or ly < 0 or lx >= mw or ly >= mh:
                    continue
                if mask.get_at((lx, ly)) == 0:
                    continue
            if best is None or zone.w * zone.h < best.w * best.h:
                best = zone
        return best

    def _update_worldmap_hover(self, pos: tuple[int, int]) -> None:
        """mousemove по модалке: координаты карты = (экран − панель) / SCALE."""
        panel = self._worldmap_panel_rect()
        if not panel.collidepoint(pos):
            self._worldmap_hovered_zone = None
            return
        mx = (pos[0] - panel.x) / WORLDMAP_SCALE
        my = (pos[1] - panel.y) / WORLDMAP_SCALE
        zone = self._worldmap_zone_at(mx, my)
        self._worldmap_hovered_zone = zone.zone_id if zone is not None else None

    def _handle_worldmap_click(self, pos: tuple[int, int]) -> None:
        """Клик: вне панели — закрыть; активная зона — переход; неактивная — плашка."""
        panel = self._worldmap_panel_rect()
        if not panel.collidepoint(pos):
            self._close_worldmap_modal()
            return
        mx = (pos[0] - panel.x) / WORLDMAP_SCALE
        my = (pos[1] - panel.y) / WORLDMAP_SCALE
        zone = self._worldmap_zone_at(mx, my)
        if zone is None:
            return
        if zone.unlock_level > self.player.level:
            self._worldmap_locked_timer = WORLDMAP_LOCKED_TOAST_SEC
            self._worldmap_locked_name = zone.name
            return
        self._worldmap_selected_zone = zone.zone_id
        from pockie_rpg.config import MapLocation

        if zone.is_village:
            self._close_worldmap_modal()
            self._go_to_location(MapLocation.CITY)
            return
        target = ZONE_LOCATION_MAP.get(zone.zone_id)
        self._close_worldmap_modal()
        if target is not None:
            self._go_to_location(target)

    def _render_worldmap_modal(self) -> None:
        assets = _load_worldmap_assets()
        # Stage 136/152 — fade-in через общий механизм (_render_with_fade
        # держит переиспользуемый буфер размера цели).
        self._render_with_fade(
            "worldmap", lambda: self._render_worldmap_modal_to(self.screen, assets)
        )

    def _render_worldmap_modal_to(self, screen: pygame.Surface, assets: dict) -> None:
        # Stage 168 (аудит 5.2) — шейд карты мира из кэша (была аллокация/кадр
        # при каждом открытом окне; размер фиксированный 1280×720).
        shade = self._static_surface(
            "worldmap_shade", (SCREEN_WIDTH, SCREEN_HEIGHT),
            lambda s: s.fill((0, 0, 0, 165)),
        )
        screen.blit(shade, (0, 0))

        panel = self._worldmap_panel_rect()
        if not assets:
            pygame.draw.rect(screen, WORLDMAP_TIP_BG, panel, border_radius=8)
            msg = _F_WM_NAME.render("Карта недоступна: ассеты assets/worldmap не найдены", True, (248, 113, 113))
            screen.blit(msg, msg.get_rect(center=panel.center))
            return

        pygame.draw.rect(screen, (9, 9, 11), panel)
        player_level = self.player.level
        hovered_id = self._worldmap_hovered_zone
        selected_id = self._worldmap_selected_zone
        inactive_ids = tuple(
            zone.zone_id for zone in WORLD_ZONES.values() if zone.unlock_level > player_level
        )
        inactive_set = set(inactive_ids)

        # Слой 1: фон.
        screen.blit(assets["bg"], panel.topleft)

        # Слой 2: платформы (неактивные — обесцвеченные, БЕЗ hover-подсветки).
        for zone in WORLD_ZONES.values():
            pos = (
                panel.x + int((zone.x - zone.w / 2) * WORLDMAP_SCALE),
                panel.y + int((zone.y - zone.h / 2) * WORLDMAP_SCALE),
            )
            if zone.zone_id in inactive_set:
                screen.blit(assets["ups_desat_scaled"][zone.zone_id], pos)
                continue
            is_hilight = hovered_id == zone.zone_id
            is_selected = selected_id == zone.zone_id
            if is_hilight or is_selected:
                screen.blit(assets["overs_scaled"][zone.zone_id], pos)
            else:
                screen.blit(assets["ups_scaled"][zone.zone_id], pos)
            if is_selected:
                rect = assets["ups_scaled"][zone.zone_id].get_rect().inflate(4, 4)
                rect.topleft = (pos[0] - 2, pos[1] - 2)
                _draw_dashed_rect(screen, rect, (251, 191, 36))

        # Слой 3: оверлей зданий и маркеров (PNG меньше карты на OVERLAY_OFFSET;
        # blit со сдвигом, без растяжения — иначе дублирование домов и артефакты).
        ox, oy = OVERLAY_OFFSET
        if WORLDMAP_SCALE == 1.0:
            overlay_surf = assets["overlay"]
        else:
            overlay_surf = pygame.transform.smoothscale(
                assets["overlay"],
                (
                    int(assets["overlay"].get_width() * WORLDMAP_SCALE),
                    int(assets["overlay"].get_height() * WORLDMAP_SCALE),
                ),
            )
        screen.blit(overlay_surf, (
            panel.x + int(ox * WORLDMAP_SCALE),
            panel.y + int(oy * WORLDMAP_SCALE),
        ))

        # Слой 4: маркеры — ВСЕГДА фиолетовые; hover → ТОЛЬКО свой маркер.
        hilight_marker = None
        if hovered_id is not None and hovered_id not in inactive_set:
            hilight_marker = ZONE_MARKER_INDEX.get(hovered_id)
        ticks = pygame.time.get_ticks()
        for i, marker in enumerate(ROUTE_MARKERS):
            cx = panel.x + int(marker.x * WORLDMAP_SCALE)
            cy = panel.y + int(marker.y * WORLDMAP_SCALE)
            if i == hilight_marker:
                pulse = 0.5 + 0.5 * math.sin(ticks / WORLDMAP_HILIGHT_PULSE_MS + i * WORLDMAP_HILIGHT_PHASE)
                glow_r = int((marker.r + 7 + pulse * 9) * WORLDMAP_SCALE)
                core_r = int(marker.r * 1.25 * WORLDMAP_SCALE)
                _draw_hilight(screen, cx, cy, core_r, glow_r)
            else:
                pulse = 0.5 + 0.5 * math.sin(ticks / WORLDMAP_PULSE_MS + i * WORLDMAP_PULSE_PHASE)
                glow_r = max(3, int((marker.r + 3 + pulse * 5) * WORLDMAP_SCALE))
                _draw_glow(screen, cx, cy, glow_r, WORLDMAP_MARKER_COLOR, WORLDMAP_MARKER_GLOW_ALPHA)

        # Слой 5: 🔒-бейджи неактивных зон.
        for zone_id in inactive_ids:
            zone = WORLD_ZONES[zone_id]
            bx = panel.x + int(zone.x * WORLDMAP_SCALE)
            by = panel.y + int((zone.y + zone.h / 2 - 11) * WORLDMAP_SCALE)
            pygame.draw.circle(screen, WORLDMAP_LOCK_BG, (bx, by), 9)
            pygame.draw.circle(screen, WORLDMAP_LOCK_BORDER, (bx, by), 9, 1)
            pygame.draw.circle(screen, WORLDMAP_LOCK_BODY, (bx, by - 3), 2, 1)
            pygame.draw.rect(screen, WORLDMAP_LOCK_BODY, (bx - 3, by - 2, 6, 5), border_radius=1)

        # Слой 6: метка игрока — пульсирующий emerald-контур на текущей зоне.
        player_zone_id = self._worldmap_player_zone_id()
        player_zone = WORLD_ZONES.get(player_zone_id) if player_zone_id is not None else None
        if player_zone is not None:
            px = panel.x + int(player_zone.x * WORLDMAP_SCALE)
            py = panel.y + int(player_zone.y * WORLDMAP_SCALE)
            pulse = 0.5 + 0.5 * math.sin(
                ticks / WORLDMAP_PLAYER_PULSE_MS + WORLDMAP_PLAYER_PULSE_PHASE
            )
            base_r = max(6, int(min(player_zone.w, player_zone.h) * 0.22 * WORLDMAP_SCALE))
            glow_r = int((base_r + 4 + pulse * 8) * 1.0)
            _draw_glow(screen, px, py, glow_r, WORLDMAP_PLAYER_COLOR, WORLDMAP_PLAYER_GLOW_ALPHA)
            ring_r = max(4, int((base_r + 2 - pulse * 2) * 1.0))
            pygame.draw.circle(screen, WORLDMAP_PLAYER_COLOR, (px, py), ring_r, 2)
            pygame.draw.circle(screen, WORLDMAP_PLAYER_CORE_COLOR, (px, py), max(2, ring_r // 3))

        # Тултип у курсора (README §12).
        if hovered_id is not None:
            zone = WORLD_ZONES.get(hovered_id)
            if zone is not None:
                self._render_worldmap_tooltip(zone, self._mouse_pos)

        # Красная плашка «Зона закрыта» (клик по неактивной зоне).
        if self._worldmap_locked_timer > 0:
            self._render_worldmap_locked_toast(panel)
        # Stage 161 — подсказка внизу («Клик по зоне — переход…») и её тёмная
        # подложка УДАЛЕНЫ по запросу пользователя (панель карты чистая).

    def _render_worldmap_tooltip(self, zone, mouse_pos: tuple[int, int]) -> None:
        locked = zone.unlock_level > self.player.level
        if locked:
            sub_color = WORLDMAP_TIP_SUB_LOCKED
            sub = f"Локация · Ур. {zone.level_range} · откроется на {zone.unlock_level} ур."
            border = WORLDMAP_TIP_BORDER
        elif zone.is_village:
            sub_color = WORLDMAP_TIP_SUB_VILLAGE
            sub = f"Деревня · Ур. {zone.level_range}"
            border = WORLDMAP_TIP_VILLAGE_BORDER
        else:
            sub_color = WORLDMAP_TIP_SUB_LOCATION
            sub = f"Локация · Ур. {zone.level_range}"
            border = WORLDMAP_TIP_BORDER

        name_surf = _F_WM_NAME.render(zone.name, True, WORLDMAP_TIP_TEXT)
        sub_surf = _F_WM_SUB.render(sub, True, sub_color)
        icon_r = 4
        pad_x = 10
        width = max(name_surf.get_width(), sub_surf.get_width() + icon_r * 2 + 4) + pad_x * 2
        height = name_surf.get_height() + sub_surf.get_height() + 12

        x = mouse_pos[0] + WORLDMAP_TOOLTIP_OFFSET_X
        if x + width > SCREEN_WIDTH - 6:
            x = mouse_pos[0] - width - 14
        y = mouse_pos[1] - height // 2
        y = max(6, min(y, SCREEN_HEIGHT - height - 6))

        plate = pygame.Surface((width, height), pygame.SRCALPHA)
        plate.fill((*WORLDMAP_TIP_BG, 235))
        pygame.draw.rect(plate, (*border, 220), plate.get_rect(), 1, border_radius=8)
        self.screen.blit(plate, (x, y))
        self.screen.blit(name_surf, (x + pad_x, y + 5))
        dot_x = x + pad_x + icon_r
        dot_y = y + name_surf.get_height() + 9
        pygame.draw.circle(self.screen, sub_color, (dot_x, dot_y), icon_r)
        self.screen.blit(sub_surf, (x + pad_x + icon_r * 2 + 4, dot_y - sub_surf.get_height() // 2))

    def _render_worldmap_locked_toast(self, panel: pygame.Rect) -> None:
        text = f"Зона закрыта: {self._worldmap_locked_name}"
        surf = _F_WM_TOAST.render(text, True, (254, 226, 226))
        width = surf.get_width() + 28
        height = 30
        x = panel.centerx - width // 2
        y = panel.y + 12
        plate = pygame.Surface((width, height), pygame.SRCALPHA)
        plate.fill((127, 29, 29, 235))
        pygame.draw.rect(plate, (248, 113, 113, 255), plate.get_rect(), 1, border_radius=8)
        pygame.draw.circle(plate, (252, 165, 165), (14, height // 2), 5)
        pygame.draw.rect(plate, (127, 29, 29), (12, height // 2 - 1, 4, 4), border_radius=1)
        self.screen.blit(plate, (x, y))
        self.screen.blit(surf, surf.get_rect(midleft=(x + 24, y + height // 2)))

    def _render_worldmap_button(self, btn_x: int, btn_y: int) -> None:
        """Кнопка «Карта мира» в top-панели (Stage 135 — замена дропдауна).

        Стиль соседних top-панельных кнопок: zinc-фон, hover-осветление,
        золотая рамка при hover. Регистрирует ClickRect tag="open_worldmap".
        Stage 159 — Hi-DPI: рендер и хиттест через _su/_su_rect/_su_font.
        Раньше rect строился в ДИЗАЙН-координатах сырым pygame.Rect: на
        нативном 2К кнопка рисовалась вчетверо меньше ожидаемого места
        (у центра экрана), а не рядом с миникартой.
        """
        btn_rect = self._su_rect(btn_x, btn_y, WORLDMAP_BTN_W, WORLDMAP_BTN_H)
        hover = btn_rect.collidepoint(self._mouse_pos)
        if hover:
            bg_col = (50, 50, 55)
            border_col = (120, 120, 130)
            text_col = (255, 255, 255)
        else:
            bg_col = (30, 30, 35)
            border_col = (60, 60, 65)
            text_col = (200, 200, 205)
        pygame.draw.rect(self.screen, bg_col, btn_rect, border_radius=self._su(6))
        pygame.draw.rect(self.screen, border_col, btn_rect,
                         self._su(2) if hover else self._su(1), border_radius=self._su(6))
        label = self._su_font(13, bold=True).render("Карта мира", True, text_col)
        self.screen.blit(label, label.get_rect(center=btn_rect.center))
        self._click_rects.append(
            ClickRect(tag="open_worldmap", rect=btn_rect, on_click=self._open_worldmap_modal)
        )
