"""MapRendererMixin — MAP screen rendering.

Stage 153 — Hi-DPI: MAP мигрирован на нативный рендер. Весь код пишется в
ДИЗАЙН-координатах (1280×720), а каждый Rect/draw/blit проходит через
`self._su()` / `self._su_rect()`; шрифты — через `self._su_font()` (обёртки
`_f_*` ниже), фоны/иконки — через `self._su_scaled()` / `self._su_image()`
(`ui/scaling.py`). Legacy-фаза: `_render_scale=1.0` → поведение как до Stage 153.
Native-фаза (2К): базовый экран рисуется прямо на монитор в физических
пикселях, немигрированные модалки уходят в legacy-слой (см.
`pygame_ui._begin_native_base_frame` / `_end_native_base_screen`).
"""
from __future__ import annotations

import os

import pygame

# Stage 153 — размеры шрифтов MAP в ДИЗАЙН-пространстве (соответствуют прежним
# модульным _F_MAP_* и self.font_*; масштабируются через self._su_font()).
_FS_MAP_NAME = (12, True)
_FS_MAP_LEVEL = (10, False)
_FS_MAP_SOON = (11, True)
_FS_MAP_BTN_SM = (10, True)
_FS_MAP_BTN_MD = (12, True)
_FS_MAP_GOLD = (16, True)
# Stage 204 — _FS_MAP_LABEL удалён (единственный потребитель — удалённый
# _f_map_label).
_FS_SMALL = (13, False)
_FS_BODY = (16, False)
_FS_BANNER = (14, True)
_FS_BUTTON = (18, True)
_FS_SUBTITLE = (18, False)
_FS_SKILLS_BTN_LETTER = (24, True)


def _fmt_hp(n: int) -> str:
    """Stage 80 — format HP as K (50000 → 50K, 100000 → 100K). Module-level."""
    if n >= 1000:
        return f"{n // 1000}K"
    return str(n)


def _lerp_color(
    a: tuple[int, int, int], b: tuple[int, int, int], t: float,
) -> tuple[int, int, int]:
    """Stage 159 — линейная интерполяция цвета для плавного hover карточек."""
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))  # type: ignore[return-value]

from pockie_rpg.config import (
    BUTTON_BG,
    BUTTON_BG_HOVER,
    BUTTON_BORDER,
    BUTTON_BORDER_HOVER,
    BUTTON_TEXT,
    BUTTON_TEXT_HOVER,
    HP_BG_COLOR,
    HP_FILL_COLOR,
    MAP_AVATAR_SIZE,
    MAP_CARD_ACCENT,
    MAP_CARD_AVATAR_SLOT,
    MAP_CARD_BG,
    MAP_CARD_BORDER,
    MAP_CARD_GAP,
    MAP_CARD_H,
    MAP_CARD_HOVER_BG,
    MAP_CARD_HOVER_BORDER,
    MAP_CARD_HOVER_GLOW_ALPHA,
    MAP_CARD_HOVER_GLOW_PAD,
    MAP_CARD_HOVER_SEC,
    MAP_CARD_STUB_BG,
    MAP_CARD_STUB_TEXT,
    MAP_CARD_W,
    MAP_EXP_BAR_BG,
    MAP_EXP_BAR_H,
    MAP_EXP_BAR_W,
    MAP_GOLD_ICON_COLOR,
    MAP_GOLD_TEXT_COLOR,
    MAP_HP_BAR_H,
    MAP_HP_BAR_W,
    MAP_LEVEL_TEXT_COLOR,
    MAP_MP_BAR_H,
    MAP_MP_BAR_W,
    MAP_PANEL_BG,
    MAP_PANEL_BORDER,
    MAP_PANEL_HEIGHT,
    MP_BG_COLOR,
    MP_FILL_COLOR,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SLOT_CARD_H,
    SLOT_CARD_REEL_H,
    SLOT_CARD_REEL_W,
    SLOT_CARD_W,
    SLOT_CARD_X,
    SLOT_CARD_Y,
    TEST_ENTRY_BTN_BG,
    TEST_ENTRY_BTN_BG_HOVER,
    TEST_ENTRY_BTN_FG,
    TEST_ENTRY_BTN_H,
    TEST_ENTRY_BTN_W,
    TEXT_WHITE,
    TEXT_YELLOW,
    UI_THEME,
)
from pockie_rpg.data.models import EnemyDef
from pockie_rpg.data.quests_db import STORY_QUESTS
from pockie_rpg.game.state import ENEMY_MOBS, ROLES, resolve_player_suit
from pockie_rpg.ui.animator import ClickRect
from pockie_rpg.ui.tooltip import PanelStyle, TooltipLine, render_tooltip_panel


class MapRendererMixin:
    """Renders the MAP state, skills modal, and char sheet modal."""

    # Stage 153 — обёртки шрифтов MAP под текущий масштаб рендера.
    # Stage 204 — сироты _f_map_level/_f_map_soon/_f_map_btn_sm/_f_map_btn_md/
    # _f_map_gold/_f_map_label/_f_map_banner/_f_map_letter удалены (0 вызовов
    # после миграции на _su_text/_su_font напрямую).
    def _f_map_name(self) -> pygame.font.Font:
        return self._su_font(*_FS_MAP_NAME)

    def _f_map_small(self) -> pygame.font.Font:
        return self._su_font(*_FS_SMALL)

    def _f_map_body(self) -> pygame.font.Font:
        return self._su_font(*_FS_BODY)

    def _f_map_button(self) -> pygame.font.Font:
        return self._su_font(*_FS_BUTTON)

    def _f_map_subtitle(self) -> pygame.font.Font:
        return self._su_font(*_FS_SUBTITLE)

    def _render_map(self) -> None:
        """Render MAP state: top panel + bg + mob cards + skills button + minimap."""
        from pockie_rpg.config import LAS_NOCHES_BG, LOCATIONS_DB, MINIMAP_CITY_BG, MapLocation

        # Stage 181 — активные бафы игрока: снимок ДЛЯ ИКОНОК + сдвига
        # карточки слот-машины. Аудит 2026-09 — снапшот раз в 0.5 сек
        # (get_active_buffs_ui: rebuild списка + sort + time.time() — раньше
        # 60×/сек). _render_map зовётся ТОЛЬКО в GameState.MAP — в бою
        # иконок нет по определению.
        now_t = pygame.time.get_ticks() / 1000.0
        if now_t - getattr(self, "_buffs_snap_ts", -1.0) >= 0.5:
            self._buffs_snap_ts = now_t
            self._map_buffs_ui = self.player.get_active_buffs_ui()
        self._map_buff_hover: tuple[dict | None, pygame.Rect | None] = (None, None)

        # Stage 45 — pick background by current location.
        if self._map_location == MapLocation.CITY:
            bg_filename = MINIMAP_CITY_BG
        elif self._map_location == MapLocation.LAS_NOCHES:
            bg_filename = LAS_NOCHES_BG
        else:
            loc_info = LOCATIONS_DB.get(int(self._map_location))
            bg_filename = loc_info["bg"] if loc_info else MINIMAP_CITY_BG
        # Stage 153 — фон масштабируется под пространство рендера (на 2К —
        # 2560×1440 напрямую из исходника, кэш в _su_surface_cache).
        bg = self._su_scaled(
            f"__map_bg__:{bg_filename}",
            self.asset_manager.get_background(bg_filename),
            SCREEN_WIDTH, SCREEN_HEIGHT,
        )
        self.screen.blit(bg, (0, 0))

        self.screen.blit(self._su_overlay(60), (0, 0))

        self._click_rects = []

        # Stage 159 — плавный hover карточек мобов: дельта времени кадра
        # для анимации (/_render_map вызывается раз в кадр).
        now_ms = pygame.time.get_ticks()
        last_ms = getattr(self, "_hover_anim_last_ms", now_ms)
        self._hover_anim_last_ms = now_ms
        self._hover_anim_dt = min(0.1, max(0.0, (now_ms - last_ms) / 1000.0))
        if not hasattr(self, "_card_hover_anim"):
            self._card_hover_anim: dict[str, float] = {}

        self._render_map_panel()

        # Stage 91 — Las Noches scene: guardian NPC + dialogs.
        # Stage 93 — back button removed (user navigates via minimap).
        # Stage 159 — диалог стража рендерится в run() в legacy-фазе
        # (раньше рисовался здесь, в нативной фазе, дизайн-координатами —
        # на 2К окно диалога сжималось в верхне-левый квадрант монитора).
        if self._map_location == MapLocation.LAS_NOCHES:
            self._render_las_noches_scene()

        # Stage 45 — render mob cards only in combat locations (not CITY/LAS_NOCHES).
        if self._map_location not in (MapLocation.CITY, MapLocation.LAS_NOCHES):
            loc_info = LOCATIONS_DB.get(int(self._map_location), {})
            mob_ids = loc_info.get("mobs", ["mob_1", "mob_2", "mob_3"])
            row_w = len(mob_ids) * MAP_CARD_W + (len(mob_ids) - 1) * MAP_CARD_GAP
            row_x_start = (SCREEN_WIDTH - row_w) // 2
            card_y = 60 + MAP_PANEL_HEIGHT

            for i, mob_id in enumerate(mob_ids):
                enemy = ENEMY_MOBS.get(mob_id)
                if enemy is None:
                    continue
                card_x = row_x_start + i * (MAP_CARD_W + MAP_CARD_GAP)
                self._render_map_enemy_card(card_x, card_y, enemy)

            # Stage 173 — стрелка-подсветка над рядом мобов (kill_mobs-цель
            # сюжетного квеста после «Перейти»).
            self._render_quest_mobs_arrow()

            # Stage 134 — slot machine card moved to the TOP-LEFT of the map zone
            # (below top panel, left of the centered mob card row), 120×72.
            # Stage 133 — slot machine icon (Location 1 only; Locations 2/3/4
            # are out of scope). Card-less design: 3 mini-reels + red label.
            if int(self._map_location) == 1:
                slot_w = SLOT_CARD_W
                slot_h = SLOT_CARD_H
                slot_x = SLOT_CARD_X
                # Stage 182 — ряд слотов бафов под аватаркой РЕЗЕРВИРУЕТСЯ
                # ВСЕГДА (даже без активных бафов) — карточка не прыгает.
                slot_y = SLOT_CARD_Y + 28
                slot_rect = self._su_rect(slot_x, slot_y, slot_w, slot_h)
                slot_hover = slot_rect.collidepoint(self._mouse_pos)

                if slot_hover:
                    glow_surf = pygame.Surface(
                        (self._su(slot_w + 20), self._su(slot_h + 20)), pygame.SRCALPHA
                    )
                    for r in range(10, 0, -1):
                        alpha = int(30 * (1 - r / 10))
                        pygame.draw.rect(glow_surf, (234, 179, 8, alpha),
                                         (self._su(10 - r), self._su(10 - r),
                                          self._su(slot_w + r * 2), self._su(slot_h + r * 2)),
                                         border_radius=14)
                    self.screen.blit(glow_surf, (self._su(slot_x - 10), self._su(slot_y - 10)))

                pygame.draw.rect(self.screen, (24, 24, 28), slot_rect, border_radius=8)
                pygame.draw.rect(self.screen,
                                 (234, 179, 8) if slot_hover else (63, 63, 70),
                                 slot_rect, self._su(2), border_radius=8)
                reel_size = SLOT_CARD_REEL_W
                reel_gap = 10
                reels_w = 3 * reel_size + 2 * reel_gap
                reel_x0 = slot_x + (slot_w - reels_w) // 2
                reel_y = slot_y + 12
                for j in range(3):
                    reel_rect = self._su_rect(reel_x0 + j * (reel_size + reel_gap), reel_y,
                                              reel_size, SLOT_CARD_REEL_H)
                    pygame.draw.rect(self.screen, (39, 39, 44), reel_rect, border_radius=4)
                    pygame.draw.rect(self.screen, (113, 113, 122), reel_rect, self._su(1), border_radius=4)
                    q_surf = self._f_map_small().render("?", True, (234, 179, 8))
                    self.screen.blit(q_surf, q_surf.get_rect(center=reel_rect.center))
                lbl = self._f_map_button().render("Слот-машина", True, (200, 80, 60))
                self.screen.blit(lbl, lbl.get_rect(
                    center=(slot_rect.centerx, self._su(slot_y + slot_h - 16))))
                self._click_rects.append(ClickRect(
                    tag="open_slot_machine", rect=slot_rect,
                    on_click=self._open_slot_machine_modal,
                ))
        elif self._map_location == MapLocation.CITY:
            # CITY — show 3 cards: Arena + Shop + Tower (boss is on locations 1-4 now).
            # Stage 92 — city cards ONLY in CITY, NOT in Las Noches.
            city_title = self._f_map_subtitle().render("Город", True, (234, 179, 8))
            self.screen.blit(city_title, (
                (self._su(SCREEN_WIDTH) - city_title.get_width()) // 2,
                self._su(80 + MAP_PANEL_HEIGHT),
            ))

            # Stage 174 — карточки города = ТЕКСТОВЫЕ ПЛАШКИ (иконок постоянно
            # НЕ видно): иконка плавно проявляется ТОЛЬКО при hover над плашкой
            # (fade через _card_hover_anim + копия кэшированной поверхности,
            # т.к. set_alpha на кэше _su_image запрещён). Клик по плашке
            # открывает окно. Позиции — слегка хаотичные (CITY_CARD_POSITIONS).
            from pockie_rpg.config import (
                CITY_CARD_HOVER_SEC,
                CITY_CARD_ICON_GAP,
                CITY_CARD_ICON_SIZE,
                CITY_CARD_LABEL_BG,
                CITY_CARD_LABEL_BORDER,
                CITY_CARD_LABEL_BORDER_HOVER,
                CITY_CARD_LABEL_H,
                CITY_CARD_LABEL_TEXT,
                CITY_CARD_LABEL_W,
                CITY_CARD_POSITIONS,
            )
            _cards_root = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                "assets", "icons", "ui")

            cards = [
                ("enter_arena", "arena_icon.png", "Арена", self._enter_arena),
                ("open_shop", "shop_icon.png", "Магазин", self._open_shop),
                ("open_tower", None, "Башня", self._open_tower),
            ]
            anim = getattr(self, "_card_hover_anim", None)
            if anim is None:
                anim = self._card_hover_anim = {}
            dt = getattr(self, "_hover_anim_dt", 0.0)
            step = dt / max(0.001, CITY_CARD_HOVER_SEC)

            for tag, icon_file, label, on_click in cards:
                center_x, center_y = CITY_CARD_POSITIONS[tag]
                plate = self._su_rect(center_x - CITY_CARD_LABEL_W // 2,
                                      center_y - CITY_CARD_LABEL_H // 2,
                                      CITY_CARD_LABEL_W, CITY_CARD_LABEL_H)
                hover = plate.collidepoint(self._mouse_pos)

                # Плавный fade иконки (0..1) — тот же механизм, что у мобов.
                t = anim.get(f"city_{tag}", 0.0)
                target = 1.0 if hover else 0.0
                if target > t:
                    t = min(target, t + step)
                elif target < t:
                    t = max(target, t - step)
                anim[f"city_{tag}"] = t

                # Подложка-плашка под текст (читаемость на фоне города).
                # Stage 197 — drop-shadow через единый хелпер (глубина).
                self._drop_shadow(
                    plate.x, plate.y, plate.w, plate.h,
                    offset=self._su(2), alpha=110, border_radius=8,
                    cache_key="city_card_shadow",
                )
                plate_bg = pygame.Surface(plate.size, pygame.SRCALPHA)
                plate_bg.fill(CITY_CARD_LABEL_BG)
                self.screen.blit(plate_bg, plate.topleft)
                pygame.draw.rect(self.screen,
                                 CITY_CARD_LABEL_BORDER_HOVER if hover else CITY_CARD_LABEL_BORDER,
                                 plate, self._su(2) if hover else self._su(1), border_radius=8)
                lbl = self._su_text(label, 16, CITY_CARD_LABEL_TEXT, bold=True)
                self.screen.blit(lbl, lbl.get_rect(center=plate.center))

                # Иконка — ТОЛЬКО при hover, плавно, НАД плашкой.
                if t > 0.001:
                    icon_cx = center_x
                    icon_bottom = center_y - CITY_CARD_LABEL_H // 2 - CITY_CARD_ICON_GAP
                    alpha = int(255 * t)
                    lift = int((1.0 - t) * 6)
                    if icon_file:
                        icon_path = os.path.join(_cards_root, icon_file)
                        icon_img = self._su_image(icon_path, CITY_CARD_ICON_SIZE, CITY_CARD_ICON_SIZE)
                        if icon_img is not None:
                            icon_surf = icon_img.copy()
                            icon_surf.set_alpha(alpha)
                            self.screen.blit(icon_surf, icon_surf.get_rect(
                                center=(self._su(icon_cx),
                                        self._su(icon_bottom - CITY_CARD_ICON_SIZE // 2 + lift))))
                    else:
                        # Башня без PNG — программная иконка (4 яруса) в SRCALPHA,
                        # альфа через copy().set_alpha (кэш _static_surface не мутируем).
                        tw_px = self._su(CITY_CARD_ICON_SIZE)
                        tower_surf = pygame.Surface((tw_px, tw_px), pygame.SRCALPHA)
                        for j, w in enumerate([44, 36, 28, 20]):
                            row_y = self._su(CITY_CARD_ICON_SIZE - 12 - j * 13)
                            bw = self._su(w)
                            bh = self._su(11)
                            pygame.draw.rect(tower_surf, (167, 139, 250, 255),
                                             (tw_px // 2 - bw // 2, row_y, bw, bh), border_radius=2)
                            pygame.draw.rect(tower_surf, (220, 220, 240, 255),
                                             (tw_px // 2 - bw // 2, row_y, bw, bh),
                                             self._su(1), border_radius=2)
                        tower_surf.set_alpha(alpha)
                        self.screen.blit(tower_surf, tower_surf.get_rect(
                            center=(self._su(icon_cx),
                                    self._su(icon_bottom - CITY_CARD_ICON_SIZE // 2 + lift))))

                self._click_rects.append(ClickRect(tag=tag, rect=plate, on_click=on_click))

        # Stage 72 — spawn boss on first view.
        if self.player.world_boss_hp is None:
            self._spawn_world_boss()

        # Stage 78 — REMOVED safety check that was resetting _endgame_active
        # during MAP render. This was BREAKING the boss results window: the
        # endgame was set in _enter_world_boss_fight(), then _render_map()
        # immediately reset it → window never appeared.
        # The stuck-endgame issue is now handled by _exit_battle() which
        # properly clears _endgame_active when the player clicks OK.

        # Stage 72/74/76 — render World Boss on combat locations (1-4) where boss is.
        boss = self.player.world_boss_hp
        if boss is not None:
            loc_match = int(self._map_location) == boss.get("location", 0)
            is_city = self._map_location == MapLocation.CITY
            hp_ok = boss["current_hp"] > 0
            endgame = self._endgame_active
            if (not is_city and loc_match and hp_ok and not endgame):
                self._render_world_boss_on_map(boss)
            elif (not is_city and loc_match and hp_ok and endgame):
                self._render_world_boss_sprite_only(boss)

        # Stage 172 — сюжетные NPC (жаба на Локации 1, Старейшина в городе)
        # + окно навигации по заданиям (HUD в правом верхнем углу).
        self._render_map_npcs()
        self._render_quest_tracker()

        # Stage 33 — minimap is now rendered inside _render_map_panel (integrated).
        # No duplicate rendering here.

        # Stage 34 — bottom UI bar is rendered by _render_bottom_bar (called
        # separately in the render loop, AFTER modals, so it stays on top).
        # Test/Reset buttons are also in _render_bottom_bar.

    def _render_bottom_bar(self) -> None:
        """Stage 34/94 — render the bottom UI bar (hotbar style).

        Stage 94 — redesigned to match original game: dark glassmorphism bar
        with icon slots (bag, skills, forge, titles, settings, exit) on the
        right + debug buttons (TEST/RESET/+1УР) on the left. Icons loaded
        via AssetManager / direct load with cache.
        """
        from pockie_rpg.config import (
            BOTTOM_BAR_BORDER,
            BOTTOM_BAR_HEIGHT,
            BOTTOM_BAR_ICON_GAP,
            BOTTOM_BAR_ICON_SIZE,
        )
        bar_y = SCREEN_HEIGHT - BOTTOM_BAR_HEIGHT
        # Stage 94 — semi-transparent dark glassmorphism background.
        # Stage 168 (аудит 5.2) — поверхность + заливка ОДИН РАЗ (кэш
        # _static_surface), раньше — новая SRCALPHA-поверхность каждый кадр.
        bar_bg = self._static_surface(
            "bottom_bar_bg",
            (self._su(SCREEN_WIDTH), self._su(BOTTOM_BAR_HEIGHT)),
            lambda s: s.fill((24, 24, 27, 220)),  # zinc-900 with alpha
        )
        self.screen.blit(bar_bg, (0, self._su(bar_y)))
        pygame.draw.line(self.screen, BOTTOM_BAR_BORDER,
                         (0, self._su(bar_y)), (self._su(SCREEN_WIDTH), self._su(bar_y)),
                         self._su(2))

        icon_sz = BOTTOM_BAR_ICON_SIZE
        icon_gap = BOTTOM_BAR_ICON_GAP
        # Stage 94 — 6 icon slots on the right: bag, titles, skills, forge, settings, exit.
        # (was 3: skills, forge, inventory)
        icon_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                                "assets", "icons", "ui", "bottom_bar")
        # Define icon slots (right to left).
        icon_slots = [
            # Stage 174 — трекер заданий: сворачивание/разворачивание переехало
            # из плавающей кнопки 44×44 в нижний бар (правый край). Бейдж —
            # число активных сюжетных квестов (см. bag-бейдж ниже).
            ("quests", "open_quests_tracker", self._quest_toggle_tracker, (234, 179, 8)),  # amber
            ("bag", "open_inventory", self._open_inventory_modal, (52, 211, 153)),       # emerald
            ("titles", "open_titles", self._open_titles_modal, (167, 139, 250)),          # violet
            ("skills", "open_skills_modal", self._open_skills_modal, (96, 165, 250)),     # blue
            ("forge", "open_forge_modal", self._open_forge_modal, (234, 179, 8)),         # gold
            ("settings", "open_settings", self._open_settings_modal, (148, 163, 184)),   # zinc-400
            # Stage 99 — removed exit button per user request.
        ]
        # Position: right-aligned, starting from right edge.
        inv_icon_x = SCREEN_WIDTH - icon_sz - 24
        icon_y = bar_y + (BOTTOM_BAR_HEIGHT - icon_sz) // 2
        for i, (icon_name, tag, handler, accent_color) in enumerate(icon_slots):
            slot_x = inv_icon_x - i * (icon_sz + icon_gap)
            slot_rect = self._su_rect(slot_x, icon_y, icon_sz, icon_sz)
            hover = slot_rect.collidepoint(self._mouse_pos)
            # Slot background — dark glass with subtle border.
            slot_bg = (39, 39, 42) if not hover else (55, 55, 60)
            pygame.draw.rect(self.screen, slot_bg, slot_rect, border_radius=6)
            border_col = accent_color if hover else (63, 63, 70)
            pygame.draw.rect(self.screen, border_col, slot_rect,
                             self._su(2) if hover else self._su(1), border_radius=6)
            # Stage 153 — иконка через кэш (_su_image): image.load один раз.
            icon_path = os.path.join(icon_dir, f"{icon_name}.png")
            icon_surf = self._su_image(icon_path, icon_sz - 8, icon_sz - 8)
            if icon_surf is not None:
                self.screen.blit(icon_surf, icon_surf.get_rect(center=slot_rect.center).topleft)
            else:
                # Fallback to letter.
                letter_map = {"bag": "И", "titles": "З", "skills": "Н", "forge": "К", "settings": "⚙", "quests": "Т", "exit": "✕"}
                letter_surf = self._su_text(
                    letter_map.get(icon_name, "?"),
                    _FS_SKILLS_BTN_LETTER[0], (255, 255, 255), bold=True,
                )
                self.screen.blit(letter_surf, letter_surf.get_rect(center=slot_rect.center))
            self._click_rects.append(ClickRect(tag=tag, rect=slot_rect, on_click=handler))
            # Inventory count badge for bag icon.
            if icon_name == "bag" and hasattr(self, "player") and self.player is not None:
                inv_count = self.player.inv_count()
                badge_surf = self._su_text(
                    str(inv_count), _FS_SMALL[0], (255, 255, 255),
                )
                bw = badge_surf.get_width() + self._su(8)
                bh = self._su(14)
                bx = slot_rect.right - bw + self._su(2)
                by = slot_rect.top - self._su(2)
                badge_rect = pygame.Rect(bx, by, bw, bh)
                fill_ratio = inv_count / 192 if 192 > 0 else 0
                if fill_ratio >= 0.90:
                    badge_bg = (220, 38, 38)
                elif fill_ratio >= 0.60:
                    badge_bg = (234, 179, 8)
                else:
                    badge_bg = (22, 163, 74)
                pygame.draw.rect(self.screen, badge_bg, badge_rect, border_radius=7)
                pygame.draw.rect(self.screen, (255, 255, 255), badge_rect, self._su(1), border_radius=7)
                self.screen.blit(badge_surf, badge_surf.get_rect(center=badge_rect.center))
            # Stage 174 — бейдж числа активных сюжетных квестов на иконке заданий.
            if icon_name == "quests" and hasattr(self, "player") and self.player is not None:
                q_count = len([q for q in self.player.story_quests_active if q in STORY_QUESTS])
                if q_count > 0:
                    q_surf = self._su_text(str(q_count), _FS_SMALL[0], (255, 255, 255), bold=True)
                    qw = q_surf.get_width() + self._su(8)
                    qh = self._su(14)
                    q_rect = pygame.Rect(slot_rect.right - qw + self._su(2),
                                         slot_rect.top - self._su(2), qw, qh)
                    pygame.draw.rect(self.screen, (234, 179, 8), q_rect, border_radius=7)
                    pygame.draw.rect(self.screen, (255, 255, 255), q_rect, self._su(1), border_radius=7)
                    self.screen.blit(q_surf, q_surf.get_rect(center=q_rect.center))

        # Test + Reset + Levelup buttons (left side of bar — debug tools).
        test_btn_x = 32
        test_btn_y = bar_y + (BOTTOM_BAR_HEIGHT - TEST_ENTRY_BTN_H) // 2
        test_btn_rect = self._su_rect(test_btn_x, test_btn_y, TEST_ENTRY_BTN_W, TEST_ENTRY_BTN_H)
        test_hover = test_btn_rect.collidepoint(self._mouse_pos)
        test_bg_col = TEST_ENTRY_BTN_BG_HOVER if test_hover else TEST_ENTRY_BTN_BG
        pygame.draw.rect(self.screen, test_bg_col, test_btn_rect, border_radius=8)
        pygame.draw.rect(self.screen, (255, 255, 255), test_btn_rect, self._su(2), border_radius=8)
        test_text = self._su_text(
            "ТЕСТ", _FS_MAP_BTN_MD[0], TEST_ENTRY_BTN_FG, bold=True,
        )
        test_text_rect = test_text.get_rect(center=test_btn_rect.center)
        self.screen.blit(test_text, test_text_rect.topleft)
        self._click_rects.append(ClickRect(tag="enter_test_battle", rect=test_btn_rect, on_click=self._enter_test_battle))

        reset_btn_x = test_btn_x + TEST_ENTRY_BTN_W + 12
        reset_btn_rect = self._su_rect(reset_btn_x, test_btn_y, TEST_ENTRY_BTN_W, TEST_ENTRY_BTN_H)
        reset_hover = reset_btn_rect.collidepoint(self._mouse_pos)
        reset_bg_col = (127, 29, 29) if reset_hover else (100, 20, 20)
        pygame.draw.rect(self.screen, reset_bg_col, reset_btn_rect, border_radius=8)
        pygame.draw.rect(self.screen, (255, 255, 255), reset_btn_rect, self._su(2), border_radius=8)
        reset_text = self._su_text(
            "СБРОС", _FS_MAP_BTN_MD[0], (255, 255, 255), bold=True,
        )
        reset_text_rect = reset_text.get_rect(center=reset_btn_rect.center)
        self.screen.blit(reset_text, reset_text_rect.topleft)
        self._click_rects.append(ClickRect(tag="reset_progression", rect=reset_btn_rect, on_click=self._reset_player_progression))

        # Stage 51 — "+1 УР" debug level-up button (for testing all player levels).
        levelup_btn_x = reset_btn_x + TEST_ENTRY_BTN_W + 12
        levelup_btn_rect = self._su_rect(levelup_btn_x, test_btn_y, TEST_ENTRY_BTN_W, TEST_ENTRY_BTN_H)
        levelup_hover = levelup_btn_rect.collidepoint(self._mouse_pos)
        levelup_bg_col = (22, 101, 52) if levelup_hover else (16, 72, 38)
        pygame.draw.rect(self.screen, levelup_bg_col, levelup_btn_rect, border_radius=8)
        pygame.draw.rect(self.screen, (255, 255, 255), levelup_btn_rect, self._su(2), border_radius=8)
        levelup_text = self._su_text(
            "+1 УР", _FS_MAP_BTN_MD[0], (255, 255, 255), bold=True,
        )
        levelup_text_rect = levelup_text.get_rect(center=levelup_btn_rect.center)
        self.screen.blit(levelup_text, levelup_text_rect.topleft)
        self._click_rects.append(ClickRect(tag="debug_level_up", rect=levelup_btn_rect, on_click=self._debug_level_up))

    def _render_map_enemy_card(self, card_x: int, card_y: int, enemy: EnemyDef) -> None:
        """Render a single enemy card on the MAP screen.

        Stage 87 — hover state on the whole card: lighter bg + gold border +
        outer shadow giving visual lift feedback (matches shop-item hover).

        Stage 153 — координаты в ДИЗАЙН-пространстве, отрисовка через _su.
        """
        card_rect = self._su_rect(card_x, card_y, MAP_CARD_W, MAP_CARD_H)
        is_locked = (not enemy.is_stub) and (enemy.level > self.player.level)
        card_hover = card_rect.collidepoint(self._mouse_pos) and not enemy.is_stub

        # Stage 159 — ПЛАВНЫЙ hover: анимированный фактор 0..1 за
        # MAP_CARD_HOVER_SEC (раньше свечение/рамка включались мгновенно).
        anim = getattr(self, "_card_hover_anim", None)
        if anim is None:
            anim = self._card_hover_anim = {}
        t = anim.get(enemy.mob_id, 0.0)
        target = 1.0 if card_hover else 0.0
        dt = getattr(self, "_hover_anim_dt", 0.0)
        step = dt / max(0.001, MAP_CARD_HOVER_SEC)
        if target > t:
            t = min(target, t + step)
        elif target < t:
            t = max(target, t - step)
        anim[enemy.mob_id] = t
        hovered = t > 0.001

        # Stage 155/159 — HOVER: мягкое золотое свечение НАРУЖУ (SRCALPHA-слои
        # с затуханием), альфа умножается на анимированный фактор — свечение
        # плавно разгорается и плавно гаснет. Рамка карточки при hover НЕ
        # меняет толщину (контур не «прыгает»).
        if hovered:
            glow_pad = MAP_CARD_HOVER_GLOW_PAD
            gw = self._su(MAP_CARD_W + glow_pad * 2)
            gh = self._su(MAP_CARD_H + glow_pad * 2)
            glow = pygame.Surface((gw, gh), pygame.SRCALPHA)
            steps = max(1, self._su(glow_pad))
            for k in range(steps, 0, -1):
                # Наружные слои прозрачнее — плавное затухание к краю.
                a = int(MAP_CARD_HOVER_GLOW_ALPHA
                        * (1.0 - (k - 1) / steps) ** 2 * t)
                if a <= 0:
                    continue
                inset = steps - k
                pygame.draw.rect(
                    glow,
                    (*MAP_CARD_HOVER_BORDER, a),
                    pygame.Rect(inset, inset, gw - inset * 2, gh - inset * 2),
                    self._su(1),
                    border_radius=self._su(8) + (steps - inset),
                )
            self.screen.blit(glow, (self._su(card_x - glow_pad), self._su(card_y - glow_pad)))

        # Stage 197 — drop-shadow под карточкой (единый хелпер; до тела
        # карточки — свет сверху-слева, тень видна снизу/справа).
        # Stage 198 — при hover тень «поднимается» (offset растёт с
        # анимированным фактором t) — карточка визуально приподнимается.
        # ВНИМАНИЕ: offset/alpha анимированы → в cache_key входят значения.
        shadow_offset = self._su(3 + 2 * t)
        shadow_alpha = 120 + int(30 * t)
        self._drop_shadow(
            self._su(card_x), self._su(card_y),
            self._su(MAP_CARD_W), self._su(MAP_CARD_H),
            offset=shadow_offset, alpha=shadow_alpha, halo_alpha=50,
            border_radius=8,
            cache_key=f"map_card_shadow_{shadow_offset}_{shadow_alpha}",
        )
        # Card background — lighter on hover (интерполяция по t).
        if enemy.is_stub:
            bg_color = MAP_CARD_STUB_BG
            border_color = (63, 63, 70)
        elif is_locked:
            bg_color = MAP_CARD_BG
            border_color = (63, 63, 70)
        else:
            bg_color = _lerp_color(MAP_CARD_BG, MAP_CARD_HOVER_BG, t)
            border_color = _lerp_color(MAP_CARD_BORDER, MAP_CARD_HOVER_BORDER, t)
        pygame.draw.rect(self.screen, bg_color, card_rect, border_radius=8)
        pygame.draw.rect(self.screen, border_color, card_rect, self._su(2), border_radius=8)
        accent_color = MAP_CARD_ACCENT if (not enemy.is_stub and not is_locked) else (113, 113, 122)
        pygame.draw.rect(
            self.screen,
            accent_color,
            self._su_rect(card_x, card_y, MAP_CARD_W, 3),
            border_radius=2,
        )

        # Stage 154 — ПЕРЕВЁРСТКА: карточка 110×110, сетка с честными зазорами.
        # Раньше (Stage 140) карточку уменьшили до 84×77, не пересчитав вёрстку:
        # уровень (54..66) уходил ПОД кнопку (53..73), имя вплотную к аватарке
        # и уровню (зазор 0), длинные имена вылезали за рамку.
        # Новая сетка (дизайн-px от верха карточки):
        #   аккцент-полоса 3 | аватарка 6..47 (слот 41) | имя 51..65 | уровень 66..78
        #   | кнопка 84..104 | низ 6
        # Аватарка: слот 41 дизайн = 82 физических на 2К = размер исходников
        # userface_n1000*.png → блит 1:1, БЕЗ ресемплинга (Stage 154).
        avatar_slot = MAP_CARD_AVATAR_SLOT
        avatar = self.asset_manager.get_enemy_avatar(enemy.mob_id, self._su(avatar_slot))
        slot_x = card_x + (MAP_CARD_W - avatar_slot) // 2
        slot_y = card_y + 6
        slot_rect = self._su_rect(slot_x, slot_y, avatar_slot, avatar_slot)
        # Stage 155 — рамка-квадрат вокруг аватарки УБРАНА (еле заметный контур
        # (63,63,70) конфликтовал с рамкой самой карточки и «дробил» вёрстку).
        # Остаётся только тёмная подложка слота — портрет на ней читается сам.
        pygame.draw.rect(self.screen, (16, 16, 19), slot_rect, border_radius=4)
        # Портрет центрируется в слоте (может быть меньше слота — не растягиваем).
        self.screen.blit(avatar, avatar.get_rect(center=slot_rect.center).topleft)

        # Имя: обрезка с «…», если не влезает в карточку (Stage 154 — раньше
        # «Черный самурай» (99px) вылезал за рамку 84px в обе стороны).
        # Stage 168 (аудит 5.2) — цикл обрезки меряет font.size() (без
        # растеризации), рендерится ТОЛЬКО итоговая строка — и она кэшируется
        # (_su_text): раньше до 10+ render() на карточку каждый кадр.
        name_font = self._f_map_name()
        name_color = TEXT_WHITE if not enemy.is_stub else MAP_CARD_STUB_TEXT
        max_name_w = self._su(MAP_CARD_W - 8)
        name_text = enemy.name
        if name_font.size(name_text)[0] > max_name_w:
            while len(name_text) > 1 and name_font.size(name_text + "…")[0] > max_name_w:
                name_text = name_text[:-1]
            name_text = name_text + "…"
        name_surf = self._su_text(name_text, _FS_MAP_NAME[0], name_color, bold=True)
        name_rect = name_surf.get_rect(center=(
            self._su(card_x + MAP_CARD_W // 2), self._su(slot_y + avatar_slot + 11)))
        self.screen.blit(name_surf, name_rect.topleft)

        level_color = TEXT_YELLOW if not enemy.is_stub else MAP_CARD_STUB_TEXT
        level_text = f"Ур. {enemy.level}"
        level_surf = self._su_text(
            level_text, _FS_MAP_LEVEL[0], level_color,
        )
        level_rect = level_surf.get_rect(center=(
            self._su(card_x + MAP_CARD_W // 2), self._su(slot_y + avatar_slot + 27)))
        self.screen.blit(level_surf, level_rect.topleft)

        if enemy.is_stub:
            soon_surf = self._su_text(
                "Скоро", _FS_MAP_SOON[0], MAP_CARD_STUB_TEXT, bold=True,
            )
            soon_rect = soon_surf.get_rect(
                center=(self._su(card_x + MAP_CARD_W // 2), self._su(card_y + MAP_CARD_H - 16))
            )
            self.screen.blit(soon_surf, soon_rect.topleft)
        else:
            is_locked = enemy.level > self.player.level
            btn_w = 84
            btn_h = 20
            btn_x = card_x + (MAP_CARD_W - btn_w) // 2
            btn_y = card_y + MAP_CARD_H - btn_h - 6
            btn_rect = self._su_rect(btn_x, btn_y, btn_w, btn_h)
            hover = btn_rect.collidepoint(self._mouse_pos) and not is_locked

            if is_locked:
                # Stage 154 — «Нужен ур. N» (75px) не влезало в кнопку: короткое
                # «Закрыто» + требуемый уровень уже виден строкой выше.
                button_bg = (50, 50, 55)
                button_border = (100, 100, 105)
                btn_text = self._su_text(
                    "Закрыто", _FS_MAP_BTN_SM[0], (150, 150, 155), bold=True,
                )
            else:
                # Stage 154 — «В бой» вместо «Уровень N» (65px не влезало).
                # Stage 155 — приглушённая палитра: тёмно-кирпичный фон + мягкая
                # красная рамка (red-600 слишком кричал), ярче только при hover.
                button_bg = BUTTON_BG_HOVER if hover else BUTTON_BG
                button_border = BUTTON_BORDER_HOVER if hover else BUTTON_BORDER
                btn_text = self._su_text(
                    "В бой", _FS_MAP_BTN_MD[0],
                    BUTTON_TEXT_HOVER if hover else BUTTON_TEXT, bold=True,
                )

            pygame.draw.rect(self.screen, button_bg, btn_rect, border_radius=6)
            pygame.draw.rect(self.screen, button_border, btn_rect, self._su(1), border_radius=6)
            text_rect = btn_text.get_rect(center=btn_rect.center)
            self.screen.blit(btn_text, text_rect)

            if not is_locked:
                def _open_quick_battle(_mob_id: str = enemy.mob_id) -> None:
                    self.target_mob_id = _mob_id
                    self._open_quick_battle_modal()
                self._click_rects.append(
                    ClickRect(tag="open_quick_battle", rect=btn_rect, on_click=_open_quick_battle)
                )
                # Stage 167 — клик по САМОЙ карточке тоже открывает окно
                # выбора боя (раньше — только кнопка «В бой»). Регистрируется
                # ПОСЛЕ кнопки: диспетчер берёт первый hit → кнопка приоритетна.
                # Тот же tag «open_quick_battle» — при открытой модалке клик
                # по карточке глотается (как и по кнопке).
                card_click_rect = self._su_rect(card_x, card_y, MAP_CARD_W, MAP_CARD_H)
                self._click_rects.append(
                    ClickRect(tag="open_quick_battle", rect=card_click_rect, on_click=_open_quick_battle)
                )

    def _blit_hud_plate(self, rect: pygame.Rect) -> None:
        """Stage 166 — тёмная полупрозрачная ПОДЛОЖКА под аватаром/полосками.

        Запрос пользователя: «под аватарку и полоски хп нужна небольшая
        подложка, чтобы не сливалось с локациями (не слишком яркую)».
        Тёмный цинк (9,9,11) с альфой 156 + тонкая рамка (63,63,70) —
        сквозь неё читается локация, но HUD выделен. Поверхность кэшируется
        по размеру (заполнение+рамка один раз, дальше только blit).
        Вынесено в метод для детерминированных diag-проверок (можно
        подменить на no-op и сравнить кадры с подложкой/без).
        """
        cache = getattr(self, "_hud_plate_cache", None)
        if cache is None:
            cache = self._hud_plate_cache = {}
        surf = cache.get(rect.size)
        if surf is None:
            surf = pygame.Surface(rect.size, pygame.SRCALPHA)
            surf.fill((9, 9, 11, 156))
            pygame.draw.rect(surf, (63, 63, 70), surf.get_rect(), 1, border_radius=8)
            cache[rect.size] = surf
        self.screen.blit(surf, rect.topleft)

    def _render_map_panel(self) -> None:
        """Render the MAP top UI panel (gold + coupons) and the HUD block
        (avatar + HP/MP/EXP) BELOW the panel.

        Stage 153 — Hi-DPI: дизайн-координаты + _su/_su_font/_su_image.
        Stage 165 — схема пользователя: панель содержит ТОЛЬКО ресурсы
        (золото и купоны в самом левом краю; минимапа справа), а аватар
        и полоски перенесены ПОД панель (y=56..96, кнопка слот-машины
        на локации при y=100 не перекрывается). Полоски — «пирамида»:
        HP 200 > MP 170 > EXP 140 (значения прежние, только визуал).
        """
        panel_rect = self._su_rect(0, 0, SCREEN_WIDTH, MAP_PANEL_HEIGHT)
        pygame.draw.rect(self.screen, MAP_PANEL_BG, panel_rect)
        pygame.draw.line(
            self.screen,
            MAP_PANEL_BORDER,
            (0, self._su(MAP_PANEL_HEIGHT)),
            (self._su(SCREEN_WIDTH), self._su(MAP_PANEL_HEIGHT)),
            self._su(2),
        )

        suit = resolve_player_suit(self.player)
        player_role = ROLES.get(self.player.role_id)
        if suit is None or player_role is None:
            return

        # Stage 165 — РЕСУРСЫ: золото и КУПОНЫ в самом ЛЕВОМ краю панели
        # (иконки 26px — золото уменьшено с 32, купон — «билет» с «К»).
        res_y = (MAP_PANEL_HEIGHT - 26) // 2
        gold_icon_x = 8
        gold_sz = self._su(26)
        # Stage 168 (аудит 5.2) — иконка рисуется ОДИН РАЗ (кэш по размеру):
        # раньше Surface + 2 circle + render("G") каждый кадр.
        gold_c = gold_sz // 2

        def _draw_gold_icon(s: pygame.Surface) -> None:
            pygame.draw.circle(s, MAP_GOLD_ICON_COLOR, (gold_c, gold_c), self._su(11))
            pygame.draw.circle(s, (161, 98, 7), (gold_c, gold_c), self._su(11), self._su(2))
            g = self._su_text("G", _FS_MAP_GOLD[0], (255, 255, 255), bold=True)
            s.blit(g, g.get_rect(center=(gold_c, gold_c)).topleft)

        gold_icon_surf = self._static_surface(
            "map_gold_icon", (gold_sz, gold_sz), _draw_gold_icon,
        )
        self.screen.blit(gold_icon_surf, (self._su(gold_icon_x), self._su(res_y)))

        gold_text_x = gold_icon_x + 30
        gold_text = f"{self.player.gold}"
        gold_text_surf = self._su_text(
            gold_text, _FS_BODY[0], MAP_GOLD_TEXT_COLOR,
        )
        self.screen.blit(
            gold_text_surf,
            (self._su(gold_text_x),
             self._su(res_y) + (gold_sz - gold_text_surf.get_height()) // 2),
        )

        # КУПОНЫ (Stage 165) — после золота: «билет»-иконка (скруглённый
        # прямоугольник с насечками и буквой «К», изумрудный).
        coupon_icon_x = gold_text_x + gold_text_surf.get_width() + 16
        cp_sz = self._su(26)

        def _draw_coupon_icon(s: pygame.Surface) -> None:
            cp_r = pygame.Rect(1, 4, s.get_width() - 2, s.get_height() - 8)
            pygame.draw.rect(s, (52, 211, 153), cp_r, border_radius=4)
            pygame.draw.rect(s, (5, 150, 105), cp_r, self._su(2), border_radius=4)
            pygame.draw.circle(s, MAP_PANEL_BG, (1, s.get_height() // 2), self._su(3))
            pygame.draw.circle(s, MAP_PANEL_BG, (s.get_width() - 1, s.get_height() // 2), self._su(3))
            k = self._su_text("К", _FS_MAP_GOLD[0], (255, 255, 255), bold=True)
            s.blit(k, k.get_rect(center=(s.get_width() // 2, cp_r.centery)).topleft)

        coupon_icon_surf = self._static_surface(
            "map_coupon_icon", (cp_sz, cp_sz), _draw_coupon_icon,
        )
        self.screen.blit(coupon_icon_surf, (self._su(coupon_icon_x), self._su(res_y)))

        coupon_text = f"{self.player.coupons}"
        coupon_text_surf = self._su_text(
            coupon_text, _FS_BODY[0], (110, 231, 183),
        )
        self.screen.blit(
            coupon_text_surf,
            (self._su(coupon_icon_x + 30),
             self._su(res_y) + (cp_sz - coupon_text_surf.get_height()) // 2),
        )

        # Stage 38 — gold flash effect on sell.
        flash_timer = getattr(self, "_gold_flash_timer", 0.0)
        if flash_timer > 0:
            self._gold_flash_timer = max(0.0, flash_timer - 0.016)  # ~60fps decay
            flash_alpha = int(255 * flash_timer)
            flash_text = f"+{self._gold_flash_amount}"
            flash_surf = self._f_map_body().render(flash_text, True, (80, 220, 100))
            flash_surf.set_alpha(flash_alpha)
            flash_y = self._su(res_y - int((1.0 - flash_timer) * 30))
            self.screen.blit(flash_surf, (self._su(gold_text_x), flash_y))

        # Stage 165 — АВАТАР и ПОЛОСКИ HP/MP/EXP перенесены ПОД панель
        # (запрос пользователя). Панель теперь только ресурсы + минимапа.
        # Блок занимает y=56..96 — кнопка слот-машины на локации
        # (SLOT_CARD_Y=100) и карточки мобов (y=112) НЕ перекрываются.
        avatar_x = 8
        avatar_y = MAP_PANEL_HEIGHT + 4
        hp_x = avatar_x + MAP_AVATAR_SIZE + 8

        # Stage 166 — ПОДЛОЖКА под аватаром и полосками (запрос: «сделать
        # небольшую подложку, чтобы не сливалось с локациями»). Тёмный
        # полупрозрачный цинк (9,9,11,156) с тонкой рамкой — тот же стиль,
        # что у панелей игры, но НЕ яркий: сквозь него читается локация.
        # Блок 54..98 — слот-машина (y=100) по-прежнему не задета.
        level_label = f"Ур. {self.player.level}"
        level_surf = self._su_text(
            level_label, _FS_BANNER[0], MAP_LEVEL_TEXT_COLOR, bold=True,
        )
        _s_plate = getattr(self, "_render_scale", 1.0)
        level_w_design = int(round(level_surf.get_width() / _s_plate))
        plate_x = 4
        plate_y = MAP_PANEL_HEIGHT + 2
        plate_h = 44
        plate_w = (hp_x + MAP_HP_BAR_W + 10 + level_w_design + 10) - plate_x
        plate_rect = self._su_rect(plate_x, plate_y, plate_w, plate_h)
        self._blit_hud_plate(plate_rect)

        # Stage 153 — аватар запрашивается в НАТИВНОМ размере (кэш AssetManager).
        player_avatar = self.asset_manager.get_avatar(
            suit.avatar_filename, self._su(MAP_AVATAR_SIZE)
        )
        avatar_rect = self._su_rect(
            avatar_x - 2, avatar_y - 2, MAP_AVATAR_SIZE + 4, MAP_AVATAR_SIZE + 4
        )
        pygame.draw.rect(
            self.screen, MAP_PANEL_BORDER, avatar_rect, self._su(2), border_radius=4,
        )
        self.screen.blit(player_avatar, (self._su(avatar_x), self._su(avatar_y)))

        hover_avatar = avatar_rect.collidepoint(self._mouse_pos)
        if hover_avatar:
            pygame.draw.rect(self.screen, (234, 179, 8), avatar_rect, self._su(2), border_radius=4)
        self._click_rects.append(ClickRect(
            tag="open_player_sheet_from_map",
            rect=avatar_rect,
            on_click=lambda: self._open_char_sheet("player", "left"),
        ))

        # Полоски-«пирамида» (Stage 165): HP самая длинная (200), MP немного
        # короче (170), EXP ещё короче (140). Значения прежние — только визуал.
        # (hp_x вычислен выше — нужен подложке Stage 166.)
        hp_y = avatar_y + 2
        hp_w = MAP_HP_BAR_W
        hp_h = MAP_HP_BAR_H

        player_hp = min(self.player.current_hp, self.player.stats.max_hp)
        player_max_hp = self.player.stats.max_hp
        self._render_bar(
            hp_x, hp_y, hp_w, hp_h,
            value=player_hp,
            maximum=player_max_hp,
            fill_color=HP_FILL_COLOR,
            bg_color=HP_BG_COLOR,
            label=f"HP {player_hp}/{player_max_hp}",
            pulse_when_low=True,
            simple=True,
        )

        mp_y = hp_y + hp_h + 2
        player_mp = min(self.player.current_mp, self.player.stats.max_mp)
        player_max_mp = self.player.stats.max_mp
        self._render_bar(
            hp_x, mp_y, MAP_MP_BAR_W, MAP_MP_BAR_H,
            value=player_mp,
            maximum=player_max_mp,
            fill_color=MP_FILL_COLOR,
            bg_color=MP_BG_COLOR,
            label=f"MP {player_mp}/{player_max_mp}",
            simple=True,
        )

        xp_y = mp_y + MAP_MP_BAR_H + 2
        xp_for_bar = min(self.player.xp, self.player.xp_to_next)
        self._render_bar(
            hp_x, xp_y, MAP_EXP_BAR_W, MAP_EXP_BAR_H,
            value=xp_for_bar,
            maximum=self.player.xp_to_next,
            fill_color=MAP_LEVEL_TEXT_COLOR,
            bg_color=MAP_EXP_BAR_BG,
            label=f"EXP {self.player.xp}/{self.player.xp_to_next}",
            simple=True,
        )

        # «Ур. N» — справа от самой длинной (HP) полосы.
        # Stage 166 — level_surf отрендерен ВЫШЕ (подложка подгоняется под
        # ширину надписи); здесь только позиционирование и blit.
        _s = _s_plate
        level_x = hp_x + MAP_HP_BAR_W + 10
        level_h = int(round(level_surf.get_height() / _s))
        level_y = hp_y + (hp_h - level_h) // 2
        self.screen.blit(level_surf, (self._su(level_x), self._su(level_y)))

        # Stage 181/182 — слоты АКТИВНЫХ БАФОВ под аватаркой (только вне боя:
        # _render_map выполняется исключительно в GameState.MAP). Ряд 30×30
        # РЕЗЕРВИРУЕТСЯ ВСЕГДА: без бафов рисуются пустые тёмные слоты (4 шт.),
        # при активации заполняются слева направо. Карточка слот-машины стоит
        # на фиксированном y и не прыгает.
        self._render_buff_icons_row(plate_x, plate_y + plate_h + 2)

        # Stage 33/94 — minimap integrated into the top panel (right side).
        # Stage 94 — redesigned: circular minimap with decorative frame +
        # location name above it (matching original game style).
        from pockie_rpg.config import MINIMAP_UI_RECT, MapLocation
        mm_x, mm_y, mm_w, mm_h = MINIMAP_UI_RECT
        minimap_rect = self._su_rect(mm_x, mm_y, mm_w, mm_h)
        mm_hover = minimap_rect.collidepoint(self._mouse_pos)

        # Stage 94 — draw circular minimap.
        mm_cx = self._su(mm_x + mm_w // 2)
        mm_cy = self._su(mm_y + mm_h // 2)
        mm_r = self._su(min(mm_w, mm_h) // 2 - 2)
        # Outer decorative ring (gold).
        pygame.draw.circle(self.screen, (234, 179, 8) if mm_hover else (180, 83, 9),
                           (mm_cx, mm_cy), mm_r + self._su(3), self._su(2))
        # Inner dark fill.
        pygame.draw.circle(self.screen, (20, 20, 28), (mm_cx, mm_cy), mm_r)
        # Location indicator — small colored dot in center.
        loc_colors = {
            MapLocation.CITY: (52, 211, 153),      # emerald
            MapLocation.LAS_NOCHES: (167, 139, 250),  # violet
            MapLocation.LOC1: (96, 165, 250),       # blue
            MapLocation.LOC2: (96, 165, 250),
            MapLocation.LOC3: (96, 165, 250),
            MapLocation.LOC4: (96, 165, 250),
        }
        dot_color = loc_colors.get(self._map_location, (148, 163, 184))
        pygame.draw.circle(self.screen, dot_color, (mm_cx, mm_cy), self._su(4))
        # Inner ring border.
        pygame.draw.circle(self.screen, (63, 63, 70), (mm_cx, mm_cy), mm_r, self._su(1))

        # Location name above the minimap (small, centered).
        loc_names = {
            MapLocation.CITY: "Город",
            MapLocation.LAS_NOCHES: "Лас Ночес",
            MapLocation.LOC1: "Локация 1",
            MapLocation.LOC2: "Локация 2",
            MapLocation.LOC3: "Локация 3",
            MapLocation.LOC4: "Локация 4",
        }
        loc_name = loc_names.get(self._map_location, "—")
        # Draw the name to the LEFT of the minimap (since it's in the top-right corner).
        name_surf = self._su_text(
            loc_name, _FS_SMALL[0], (220, 220, 240),
        )
        name_x = self._su(mm_x - 8) - name_surf.get_width()
        name_y = self._su(mm_y) + (self._su(mm_h) - name_surf.get_height()) // 2
        self.screen.blit(name_surf, (name_x, name_y))

        # Toggle label inside the minimap circle (small).
        if self._map_location != MapLocation.CITY:
            mm_label = "↩"
        else:
            mm_label = "→"
        # Stage 91 — in Las Noches, the minimap returns to City.
        if self._map_location == MapLocation.LAS_NOCHES:
            mm_label = "↩"
        label_surf = self._su_text(
            mm_label, _FS_MAP_BTN_MD[0], (255, 255, 255), bold=True,
        )
        self.screen.blit(label_surf, label_surf.get_rect(center=(mm_cx, mm_cy + self._su(10))))
        self._click_rects.append(
            ClickRect(tag="toggle_minimap", rect=minimap_rect, on_click=self._toggle_map_location)
        )

        # Stage 95 — Daily Quest icon below the minimap.
        dq_icon_sz = 36
        dq_x = mm_x + mm_w - dq_icon_sz
        dq_y = mm_y + mm_h + 4
        dq_rect = self._su_rect(dq_x, dq_y, dq_icon_sz, dq_icon_sz)
        dq_hover = dq_rect.collidepoint(self._mouse_pos)
        # Slot background.
        dq_bg = (55, 55, 60) if dq_hover else (39, 39, 42)
        pygame.draw.rect(self.screen, dq_bg, dq_rect, border_radius=6)
        dq_border = (234, 179, 8) if dq_hover else (63, 63, 70)
        pygame.draw.rect(self.screen, dq_border, dq_rect,
                         self._su(2) if dq_hover else self._su(1), border_radius=6)
        # Stage 153 — иконка свитка через кэш (_su_image).
        dq_icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                                    "assets", "icons", "ui", "bottom_bar", "scroll.png")
        dq_icon_surf = self._su_image(dq_icon_path, dq_icon_sz - 8, dq_icon_sz - 8)
        if dq_icon_surf is not None:
            self.screen.blit(dq_icon_surf, dq_icon_surf.get_rect(center=dq_rect.center))
        else:
            dq_letter = self._su_text(
                "Q", _FS_SMALL[0], (255, 255, 255),
            )
            self.screen.blit(dq_letter, dq_letter.get_rect(center=dq_rect.center))
        self._click_rects.append(ClickRect(tag="open_daily_quests", rect=dq_rect, on_click=self._open_daily_quest_modal))
        # Label below icon.
        dq_label = self._su_text(
            "Дневные квесты", _FS_SMALL[0], (180, 180, 200),
        )
        dq_label_x = dq_rect.centerx - dq_label.get_width() // 2
        dq_label_y = dq_rect.bottom + self._su(1)
        # Only show if it fits below minimap (Stage 161 — не хардкод 64).
        if dq_label_y + dq_label.get_height() <= self._su(MAP_PANEL_HEIGHT):
            self.screen.blit(dq_label, (dq_label_x, dq_label_y))

        # Stage 135 — «Карта мира» button (left of minimap; replaces the
        # Stage 46 location dropdown). Handler in WorldMapRendererMixin.
        wm_btn_w = 110
        wm_btn_h = 36
        wm_btn_x = mm_x - wm_btn_w - 8
        wm_btn_y = (MAP_PANEL_HEIGHT - wm_btn_h) // 2
        self._render_worldmap_button(wm_btn_x, wm_btn_y)

    def _render_buff_icons_row(self, x: int, y: int) -> None:
        """Stage 181/182 — ряд слотов бафов под аватаркой + hover-тултип.

        Ряд РЕЗЕРВИРУЕТСЯ ВСЕГДА (MIN_BUFF_SLOTS пустых тёмных слотов), при
        активации иконки заполняют его слева направо, при переполнении ряд
        растёт. Снимок self._map_buffs_ui берётся в _render_map (один раз за
        кадр). icon_filename=None → процент-текст на тёмном квадрате.
        Тултип — через _render_buff_tooltip (панель подгоняется под текст).
        """
        buffs = getattr(self, "_map_buffs_ui", [])
        su = self._su
        icon_sz = 26
        gap = 4
        # Stage 182 — минимум 4 слота: резерв места, чтобы нижний ряд
        # (слот-машина) не прыгал при первой активации.
        min_slots = 4
        slot_count = max(min_slots, len(buffs))
        hovered_buff: dict | None = None
        hover_rect: pygame.Rect | None = None
        for i in range(slot_count):
            bx = x + i * (icon_sz + gap)
            rect = self._su_rect(bx, y, icon_sz, icon_sz)
            b = buffs[i] if i < len(buffs) else None
            hover = rect.collidepoint(self._mouse_pos)
            # Слот: тёмная плашка + рамка (hover — золотая; пустой слот тусклее).
            pygame.draw.rect(self.screen, (24, 24, 28), rect, border_radius=5)
            if b is not None:
                border = (234, 179, 8) if hover else (63, 63, 70)
            else:
                border = (39, 39, 44)
            pygame.draw.rect(self.screen, border, rect, su(1), border_radius=5)
            if b is None:
                continue
            # Иконка бафа: файл из BUFF_DB или процент-текст (фолбэк).
            icon_fn = b.get("icon_filename")
            surf = None
            if icon_fn:
                from pockie_rpg.config import ASSETS_DIR
                icon_path = os.path.join(ASSETS_DIR, "icons", "items", icon_fn)
                surf = self._su_image(icon_path, icon_sz - 6, icon_sz - 6)
            if surf is not None:
                self.screen.blit(surf, surf.get_rect(center=rect.center))
            else:
                pct = ""
                name = b.get("name", "")
                for ch in name:
                    if ch.isdigit() or ch in "+%":
                        pct += ch
                letter = self._su_text(pct or "B", _FS_SMALL[0], (234, 179, 8))
                self.screen.blit(letter, letter.get_rect(center=rect.center))
            if hover:
                hovered_buff = b
                hover_rect = rect
        self._map_buff_hover = (hovered_buff, hover_rect)
        if hovered_buff is not None and hover_rect is not None:
            self._render_buff_tooltip(hovered_buff, hover_rect)

    def _render_buff_tooltip(self, buff: dict, anchor_rect: pygame.Rect) -> None:
        """Stage 181/182 — тултип иконки бафа (формат ТЗ пользователя):

            название
            ─────────────
            Скорость опыта 50%
            ─────────────
            Время 3:15:20 осталось

        Stage 203 — через единый хелпер ui/tooltip.py (render_tooltip_panel):
        rule-разделители, min_w 170, anchor prefer_below (под иконкой,
        флип вверх у низа экрана) — вид и позиция как в ручной реализации,
        убраны дублированные построение панели/перенос/флип/кламп.
        """
        remaining = max(0, int(buff.get("remaining_sec", 0)))
        h, rem, s = remaining // 3600, (remaining % 3600) // 60, remaining % 60
        time_str = f"Время {h}:{rem:02d}:{s:02d} осталось"

        lines = [
            TooltipLine(buff.get("name", ""), UI_THEME["white"], size=12, bold=True),
            TooltipLine("", UI_THEME["tooltip_sep"], space_before=4, rule=True),
            TooltipLine(buff.get("desc", ""), UI_THEME["zinc_300"], size=11,
                        space_before=5),
            TooltipLine("", UI_THEME["tooltip_sep"], space_before=5, rule=True),
            TooltipLine(time_str, UI_THEME["green_soft"], size=11, bold=True,
                        space_before=5),
        ]
        style = PanelStyle(
            bg=(16, 16, 20, 238),
            border=UI_THEME["gold"],
            border_w=1,
            radius=6,
            pad_x=8,
            pad_y=8,
            min_w=170,
        )
        render_tooltip_panel(
            self, lines, anchor=anchor_rect, style=style,
            wrap_width=200, prefer_below=True,
        )

    def _render_close_x_button(self, win_x: int, win_y: int, win_w: int, on_click) -> None:
        """Stage 30 — render an 'X' close button at the top-right of a modal.

        Stage 159 — КВАДРАТНЫЙ Х (без отступа, как у общих окон в ui/scaling.py;
        раньше — красный кружок с отступом 10px).
        Stage 161 — Х ВЫНЕСЕН ЗА окно: приклеен к правому краю СНАРУЖИ
        (x = win_x + win_w), единообразно с общими окнами (scaling.py).
        Registers a click rect so the user can click it to close the modal.

        Stage 151 — аргументы в ДИЗАЙН-координатах; отрисовка через self._su()
        (identity в legacy-фазе, ×UI_SCALE в native-фазе Hi-DPI).
        Stage 203 — визуал через общий _draw_close_x_square (scaling.py);
        хиттест остаётся ПОКАДРОВЫМ ClickRect: персистентный реестр
        _window_close_buttons гейтится open_attr, которого у MAP-модалок
        нет — устаревшая запись глотала бы клики после закрытия модалки.
        """
        from pockie_rpg.ui.scaling import CLOSE_X_SIZE
        su = self._su
        size = su(CLOSE_X_SIZE)
        btn_rect = pygame.Rect(su(win_x) + su(win_w), su(win_y), size, size)
        hover = btn_rect.collidepoint(self._mouse_pos)
        self._draw_close_x_square(btn_rect, hover)
        self._click_rects.append(ClickRect(tag="close_x_btn", rect=btn_rect, on_click=on_click))

    def _save_player(self) -> None:
        """Stage 88 — Fix 2.5: mark player state as dirty for debounced autosave.

        All mutation handlers (equip, enchant, gem socket, synthesis, sell,
        buy, title change, skill toggle, boss fight, battle rewards) call
        this method. Previously it saved synchronously to disk on EVERY
        mutation — now it just flags the state as dirty. The SaveManager in
        pygame_ui debounces the actual disk write (0.5s after the last
        mutation) and flushes on QUIT / screen transitions. This prevents
        excessive disk I/O when the player rapidly toggles skills or drags
        inventory items, and ensures the save is never lost mid-mutation.
        """
        # save_mgr is set up in PygameUI.__init__ (in pygame_ui.py).
        # This mixin is mixed into PygameUI, so self.save_mgr is always present.
        if hasattr(self, "save_mgr"):
            self.save_mgr.mark_dirty()

