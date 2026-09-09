"""BattleRendererMixin — battle state rendering (HUD, fighters, log, overlays).

Stage 201 — миграция на нативный Hi-DPI: весь рендер боя идёт через
_su()/_su_font()/_static_surface (масштаб = _render_scale: 1.0 legacy,
UI_SCALE×BATTLE_WINDOW_SCALE в нативной фазе боя). Логика/ховеры/клики
остаются в ДИЗАЙН-координатах (мышь боя ремапится _map_battle_mouse);
модульные шрифты _FONT_* удалены (фиксированный размер = кроха на 2К).
"""
from __future__ import annotations

import math
import os
import random

import pygame

# Stage 86 — render_battle импортируется ЛАЗИВО из main.py ДО pygame.init()
# в PygameUI.__init__(). Модульные шрифты _FONT_* удалены (Stage 201), но
# ДРУГИЕ ui-модули (render_worldmap) всё ещё создают SysFont на уровне
# модуля — pygame.font.init() здесь страхует весь порядок импортов.
# Вызов идемпотентен (повторный pygame.init() — no-op).
pygame.font.init()

from pockie_rpg.config import (
    ASSETS_DIR,
    AVATAR_SIZE,
    BANNER_BG,
    BANNER_H,
    BANNER_TEXT_COLOR,
    BANNER_TOP_INSET,
    BANNER_W,
    BAR_GAP,
    BAR_GHOST_COLOR,
    BAR_NAME_GAP,
    BAR_SHINE_BAND_ALPHA,
    BAR_SHINE_BAND_W,
    BAR_SHINE_PERIOD,
    BATTLE_SPEEDS,
    COMBAT_LOG_EXPANDED_H,
    COMBAT_LOG_LINE_HEIGHT,
    COMBAT_LOG_MAX_LINES,
    COUNTDOWN_COLOR,
    COUNTDOWN_SHADOW_COLOR,
    COUNTDOWN_TEXT_SCALE_PER_PHASE,
    DEBUFF_ICON_GAP,
    DEBUFF_ICON_SIZE,
    ENDGAME_GOLD_COLOR,
    ENDGAME_LEVELUP_COLOR,
    ENDGAME_LOSE_COLOR,
    ENDGAME_OK_BTN_BG,
    ENDGAME_OK_BTN_BG_HOVER,
    ENDGAME_OK_BTN_FG,
    ENDGAME_OK_BTN_H,
    ENDGAME_OK_BTN_W,
    ENDGAME_WIN_COLOR,
    ENDGAME_WINDOW_BG,
    ENDGAME_WINDOW_BORDER,
    ENDGAME_WINDOW_H,
    ENDGAME_WINDOW_RADIUS,
    ENDGAME_WINDOW_W,
    ENEMY_BAR_RIGHT_MARGIN,
    ENEMY_HIT_SHAKE_AMPLITUDE,
    ENEMY_SPRITE_X,
    HP_BAR_H,
    HP_BAR_W,
    HP_BG_COLOR,
    HP_FILL_COLOR,
    HP_GRADIENT_COLOR_FROM,
    HP_GRADIENT_COLOR_TO,
    HP_PULSE_FREQ_HZ,
    HP_PULSE_MAX,
    HP_PULSE_MIN,
    HP_PULSE_RATIO,
    HUD_BAR_CENTER_SHIFT,
    HUD_BG_COLOR,
    HUD_BORDER_COLOR,
    HUD_DIVIDER_COLOR,
    HUD_HEIGHT,
    HUD_THEME,
    ICE_BLOCK_RENDER_H,
    ICE_BLOCK_X_OFFSET,
    ICE_BLOCK_Y_OFFSET,
    LOG_BAR_H,
    LOG_BG_ALPHA,
    LOG_BG_COLOR,
    MAP_PANEL_BORDER,
    MP_BAR_H,
    MP_BAR_W,
    MP_BG_COLOR,
    MP_FILL_COLOR,
    MP_GRADIENT_COLOR_FROM,
    MP_GRADIENT_COLOR_TO,
    PLAYER_SPRITE_X,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SHADOW_H,
    SHADOW_W,
    SHIELD_DOME_RENDER_H,
    SHIELD_DOME_X_OFFSET,
    SHIELD_DOME_Y_OFFSET,
    SKILLS_GRID_H,
    SKILLS_SLOT_ACTIVE_BG,
    SKILLS_SLOT_INACTIVE_BG,
    SKILLS_SLOT_INACTIVE_BORDER,
    SKILLS_SLOT_INACTIVE_ICON_ALPHA,
    SLOT_QUEUE_FACE_SIZE,
    SLOT_QUEUE_GAP,
    SPEED_BTN_ACTIVE_BG,
    SPEED_BTN_ACTIVE_FG,
    SPEED_BTN_GAP,
    SPEED_BTN_H,
    SPEED_BTN_HOVER_BG,
    SPEED_BTN_INACTIVE_BG,
    SPEED_BTN_INACTIVE_FG,
    SPEED_BTN_TAGS,
    SPEED_BTN_W,
    SPRITE_BASE_Y,
    TEXT_DIM,
    TEXT_WHITE,
    VS_GOLD_COLOR,
    VS_GOLD_DARK,
    BattleMode,
)
from pockie_rpg.data.item_db import DEFAULT_GEAR_ICONS, DEFAULT_TYPE_TO_SLOT
from pockie_rpg.game.state import ENEMY_MOBS, ROLES, resolve_player_suit
from pockie_rpg.ui.animator import ClickRect
from pockie_rpg.ui.tooltip import PanelStyle, TooltipLine, render_tooltip_panel


def _wrap_text(text: str, max_chars_per_line: int) -> list[str]:
    """Wrap text into multiple lines of at most max_chars_per_line chars."""
    if max_chars_per_line <= 0:
        return [text] if text else [""]
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = ""
    for word in words:
        if not current:
            current = word
            continue
        if len(current) + 1 + len(word) <= max_chars_per_line:
            current = f"{current} {word}"
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _draw_bar_gradient(
    surf: pygame.Surface,
    mirrored: bool,
    color_from: tuple[int, int, int],
    color_to: tuple[int, int, int],
) -> None:
    """Stage 193/194 — рисует горизонтальный градиент полоски (HP/MP).

    Однократно в _static_surface-кэш: вертикальные линии по колонкам,
    интерполяция color_from → color_to. mirrored разворачивает направление
    (враг: кончик color_to у центра экрана, основание у края).
    """
    w, h = surf.get_size()
    for col in range(w):
        t = (w - 1 - col) / max(1, w - 1) if mirrored else col / max(1, w - 1)
        color = tuple(
            int(color_from[i] + (color_to[i] - color_from[i]) * t)
            for i in range(3)
        )
        pygame.draw.line(surf, color, (col, 0), (col, h))


def _outlined_text(surf: pygame.Surface) -> pygame.Surface:
    """Stage 197 — текст с 1px чёрным аутлайном (имена бойцов над полосками).

    Чёрная копия текста блитится на 4 соседних позиции (верх/низ/лево/
    право от центра), поверх — оригинальный цвет. Поле +1px с каждой
    стороны; альфа полностью копируется из исходного текста.
    """
    w, h = surf.get_size()
    panel = pygame.Surface((w + 2, h + 2), pygame.SRCALPHA)
    black = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    black.blit(surf, (0, 0))
    black.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MULT)
    for dx, dy in ((0, 1), (2, 1), (1, 0), (1, 2)):
        panel.blit(black, (dx, dy))
    panel.blit(surf, (1, 1))
    return panel


def _draw_shine_band(surf: pygame.Surface) -> None:
    """Stage 198 — бэнд shine-sweep: белая полоса с треугольной альфой
    (0 → пик → 0) по горизонтали, на всю высоту полоски."""
    w, h = surf.get_size()
    for col in range(w):
        a = int(BAR_SHINE_BAND_ALPHA * (1.0 - abs(col - w / 2) / max(1, w / 2)))
        pygame.draw.line(surf, (255, 255, 255, a), (col, 0), (col, h))


class BattleRendererMixin:
    """Renders the BATTLE state: HUD, sprites, log, speed buttons, endgame."""

    def _render_battle(self) -> None:
        """Render BATTLE state: bg + HUD + banners + sprites + log + speed btns.

        Stage 201 — нативный Hi-DPI: фон масштабируется _su_scaled (кэш),
        вся отрисовка — через _su(); ClickRect'ы баннеров остаются в
        ДИЗАЙН-координатах (мышь боя ремапится _map_battle_mouse в дизайн
        окна — см. _click_rect_hit).
        """
        from pockie_rpg.config import BATTLE_BACKGROUND, LOCATIONS_DB

        # Stage 92 — Tower battles use floor-specific backgrounds from Las Noches.
        if self._battle_mode == BattleMode.TOWER and self._tower_active_floor is not None:
            from pockie_rpg.config import get_tower_battle_bg
            bg_name = get_tower_battle_bg(self._tower_active_floor)
        else:
            # Stage 46 — battle background = current location's bg.
            loc_info = LOCATIONS_DB.get(int(self._map_location))
            bg_name = loc_info["bg"] if loc_info else BATTLE_BACKGROUND
        bg = self.asset_manager.get_background(bg_name)
        bg = self._su_scaled(f"battle_bg_{bg_name}", bg, SCREEN_WIDTH, SCREEN_HEIGHT)
        self.screen.blit(bg, (0, 0))

        self._render_hud()
        self._render_side_banners()

        player_seq = (
            self._active_attack_seq
            if (self._active_attack_seq is not None and self._active_attack_seq.is_player)
            else None
        )
        enemy_seq = (
            self._active_attack_seq
            if (self._active_attack_seq is not None and not self._active_attack_seq.is_player)
            else None
        )
        enemy_shake = 0
        if self._enemy_shake_timer > 0.0:
            enemy_shake = random.randint(
                -ENEMY_HIT_SHAKE_AMPLITUDE, ENEMY_HIT_SHAKE_AMPLITUDE
            )
        self._render_fighter(
            self._player_animator,
            PLAYER_SPRITE_X,
            is_player=True,
            attack_seq=player_seq,
            shake_offset=0,
        )
        self._render_fighter(
            self._enemy_animator,
            ENEMY_SPRITE_X,
            is_player=False,
            attack_seq=enemy_seq,
            shake_offset=enemy_shake,
        )

        self._particles.render(self.screen, getattr(self, "_render_scale", 1.0))
        self._damage_numbers.render(self.screen, getattr(self, "_render_scale", 1.0))
        self._cast_effect.render(
            self.screen, self.asset_manager, getattr(self, "_render_scale", 1.0)
        )
        self._projectile_effect.render(
            self.screen, self.asset_manager, getattr(self, "_render_scale", 1.0)
        )

        # Stage 62 — always register banner click rects, even when char sheet is open.
        # This allows opening the second char sheet (enemy) while the first (player) is open.
        banner_top = HUD_HEIGHT + BANNER_TOP_INSET
        banner_h = BANNER_H
        left_banner = pygame.Rect(0, banner_top, BANNER_W, banner_h)
        right_banner = pygame.Rect(
            SCREEN_WIDTH - BANNER_W, banner_top, BANNER_W, banner_h
        )
        self._click_rects = [
            ClickRect(
                tag="open_player_sheet",
                rect=left_banner,
                on_click=lambda: self._open_char_sheet("player", "left"),
            ),
            ClickRect(
                tag="open_enemy_sheet",
                rect=right_banner,
                on_click=lambda: self._open_char_sheet("enemy", "right"),
            ),
        ]

        self._render_combat_log()

        if not self._char_sheet_open:
            self._render_speed_buttons()

    def _render_hud(self) -> None:
        """Render top HUD: avatars + names + HP/MP bars + central VS emblem.

        Stage 98 — removed black HUD background (transparent, shows battle bg).
        Stage 202 — оркестрация: симметричные половины _render_hud_player /
        _render_hud_enemy, эмблема VS, ряды иконок статусов (+тултип) и
        очередь гантелей — по якорям полосок, возвращаемым половинами.
        """
        # Stage 98 — no background fill (transparent HUD, shows battle bg).
        # Stage 99 — removed bottom border line (per user request).

        suit = resolve_player_suit(self.player)
        enemy = ENEMY_MOBS.get(self.target_mob_id)
        if suit is None or enemy is None:
            return
        player_role = ROLES.get(self.player.role_id)
        enemy_role = ROLES.get(enemy.role_id)
        if player_role is None or enemy_role is None:
            return

        p_bars = self._render_hud_player(player_role)
        e_bars = self._render_hud_enemy(enemy, enemy_role)
        self._render_vs_emblem(SCREEN_WIDTH // 2, HUD_HEIGHT // 2)
        icon_rects = self._render_hud_status_icons(p_bars, e_bars)
        self._render_status_tooltip(icon_rects)
        self._render_gauntlet_queue(e_bars[1])

    def _render_hud_player(self, player_role) -> tuple[int, int]:
        """Stage 202 — левая половина HUD: аватар + плашка имени + HP/MP.

        Возвращает (hp_x, mp_y) — дизайн-якоря ряда иконок статусов.
        """
        suit = resolve_player_suit(self.player)
        avatar_sz = self._su(AVATAR_SIZE)
        avatar_x = 16
        avatar_y = (HUD_HEIGHT - AVATAR_SIZE) // 2
        player_avatar = self.asset_manager.get_avatar(
            suit.avatar_filename, avatar_sz
        )
        # Stage 99 — decorative avatar frame (border.svg style).
        frame_surf = self._get_avatar_frame()
        frame_pad = (frame_surf.get_width() - avatar_sz) // 2
        self.screen.blit(
            frame_surf,
            (self._su(avatar_x) - frame_pad, self._su(avatar_y) - frame_pad),
        )
        self.screen.blit(player_avatar, (self._su(avatar_x), self._su(avatar_y)))

        name_x = avatar_x + AVATAR_SIZE + 12 + HUD_BAR_CENTER_SHIFT
        name_y = avatar_y - 2
        # Stage 200 — цвета имён/уровня из HUD_THEME (единая точка).
        p_name_color = HUD_THEME["name_text_color"]
        p_lvl_color = HUD_THEME["level_text_color"]
        # Stage 206 — имя игрока от КОСТЮМА (надел Абарая — табличка «Ренджи
        # Абараи»; у Ичиго имя совпадает с role.name — вид не меняется).
        display_name = suit.name or player_role.name
        name_surf = self._su_font(16).render(display_name, True, p_name_color)
        # Stage 197 — 1px чёрный аутлайн вместо тени (текст над полосками).
        name_surf = _outlined_text(name_surf)
        lvl_surf = self._su_font(13).render(
            f"Ур. {self.player.level}", True, p_lvl_color
        )
        # Stage 198 — аутлайн и на тексте уровня.
        lvl_surf = _outlined_text(lvl_surf)
        # Stage 199/200 — тёмная ПОДЛОЖКА под имя+уровень: текст
        # ВЕРТИКАЛЬНО ЦЕНТРИРОВАН (имя и уровень на общей средней линии),
        # fade-in с боем (HUD_PLATE_FADE_SEC из HUD_THEME).
        # Stage 201 — размеры плашки нативные (текст уже ×scale).
        plate_h = self._su(24)
        plate_w = (
            name_surf.get_width() + self._su(10)
            + lvl_surf.get_width() + self._su(6)
        ) + self._su(3)
        plate_alpha = int(HUD_THEME["name_plate_alpha"]
                          * getattr(self, "_hud_plate_fade", 1.0))
        plate_border_alpha = int(HUD_THEME["name_plate_border_alpha"]
                                 * getattr(self, "_hud_plate_fade", 1.0))
        name_plate = self._static_surface(
            f"name_plate_{plate_w}_{plate_h}_{plate_alpha}_{plate_border_alpha}",
            (plate_w, plate_h),
            lambda s: (
                pygame.draw.rect(s, (*HUD_THEME["name_plate_bg"], plate_alpha),
                                 s.get_rect(), border_radius=self._su(6)),
                pygame.draw.rect(s, (*HUD_THEME["name_plate_border"],
                                     plate_border_alpha),
                                 s.get_rect(), 1, border_radius=self._su(6)),
            ),
        )
        self.screen.blit(
            name_plate,
            (self._su(name_x - 3), self._su(name_y - 4)),
        )
        # Вертикальное центрирование: имя — по центру плашки, уровень —
        # тоже по центру (общая средняя линия, а не «привязка к верху»).
        plate_cy = self._su(name_y - 4) + plate_h // 2
        self.screen.blit(name_surf, (self._su(name_x), plate_cy - name_surf.get_height() // 2))
        self.screen.blit(
            lvl_surf,
            (self._su(name_x) + name_surf.get_width() + self._su(10),
             plate_cy - lvl_surf.get_height() // 2)
        )

        hp_x = name_x
        hp_y = name_y + 24
        player_hp = int(self._player_hp_display)
        player_max_hp = player_role.max_hp
        if self._player_fighter is not None:
            player_max_hp = self._player_fighter.max_hp
        # Stage 192 — числа с полосок убраны (запрос пользователя): состояние
        # читается по длине заливки + пульсации при низком HP.
        # Stage 193 — градиент красный→жёлтый + белый догоняющий сегмент.
        # Stage 195 — ЗАЕРКАЛЬНОЕ списание: у Ичиго остаток прижат к ПРАВОМУ
        # (центро-обращённому) краю, пустота растёт слева направо
        # (mirrored=True). Градиент — инверсно (жёлтый кончик у центра).
        self._render_bar(
            hp_x, hp_y, HP_BAR_W, HP_BAR_H,
            value=player_hp,
            maximum=player_max_hp,
            fill_color=HP_FILL_COLOR,
            bg_color=HP_BG_COLOR,
            mirrored=True,
            gradient_mirrored=False,
            pulse_when_low=True,
            ghost_value=self._player_hp_ghost,
            gradient=True,
        )
        mp_y = hp_y + HP_BAR_H + BAR_GAP
        player_mp = int(self._player_mp_display)
        player_max_mp = player_role.max_mp
        if self._player_fighter is not None:
            player_max_mp = self._player_fighter.max_mp
        # Stage 195 — MP уже HP, кончики (правые края) совпадают.
        player_mp_x = hp_x + (HP_BAR_W - MP_BAR_W)
        self._render_bar(
            player_mp_x, mp_y, MP_BAR_W, MP_BAR_H,
            value=player_mp,
            maximum=player_max_mp,
            fill_color=MP_FILL_COLOR,
            bg_color=MP_BG_COLOR,
            mirrored=True,
            gradient_mirrored=False,
            ghost_value=self._player_mp_ghost,
            gradient=True,
            gradient_from=MP_GRADIENT_COLOR_FROM,
            gradient_to=MP_GRADIENT_COLOR_TO,
        )

        return (hp_x, mp_y)

    def _render_hud_enemy(self, enemy, enemy_role) -> tuple[int, int]:
        """Stage 202 — правая половина HUD (зеркально): аватар + плашка
        имя/уровень + HP/MP. Возвращает (hp_x, mp_y) — дизайн-якоря ряда
        иконок статусов.
        """
        avatar_sz = self._su(AVATAR_SIZE)
        enemy_avatar = self.asset_manager.get_enemy_avatar(self.target_mob_id, avatar_sz)
        enemy_avatar_x = SCREEN_WIDTH - AVATAR_SIZE - 16
        enemy_avatar_y = (HUD_HEIGHT - AVATAR_SIZE) // 2
        # Stage 99 — decorative avatar frame for enemy.
        frame_surf = self._get_avatar_frame()
        frame_pad = (frame_surf.get_width() - avatar_sz) // 2
        self.screen.blit(
            frame_surf,
            (self._su(enemy_avatar_x) - frame_pad, self._su(enemy_avatar_y) - frame_pad),
        )
        # Stage 154 — портрет может быть МЕНЬШЕ слота (без апскейла) → центруем.
        self.screen.blit(
            enemy_avatar,
            enemy_avatar.get_rect(
                center=(self._su(enemy_avatar_x) + avatar_sz // 2,
                        self._su(enemy_avatar_y) + avatar_sz // 2)
            ).topleft,
        )

        # Stage 134 — mirrored player layout: bar X is FIXED (does NOT depend on
        # enemy name width). Name/level float inside the space between the VS
        # emblem and the bar right edge; shrink to font_small then truncate «…».
        enemy_hp_x = (
            SCREEN_WIDTH - ENEMY_BAR_RIGHT_MARGIN - AVATAR_SIZE
            - BAR_NAME_GAP - HP_BAR_W
            - HUD_BAR_CENTER_SHIFT
        )
        enemy_bar_right = enemy_hp_x + HP_BAR_W
        enemy_name_y = enemy_avatar_y - 2
        e_name_color = HUD_THEME["name_text_color"]
        e_lvl_color = HUD_THEME["level_text_color"]
        enemy_lvl_surf = self._su_font(13).render(
            f"Ур. {enemy.level}", True, e_lvl_color
        )
        name_text = enemy.name
        enemy_name_font = self._su_font(16)
        enemy_name_surf = enemy_name_font.render(name_text, True, e_name_color)
        vs_right_edge = SCREEN_WIDTH // 2 + 34
        avail_name_w = enemy_bar_right - vs_right_edge
        if enemy_name_surf.get_width() + self._su(10) + enemy_lvl_surf.get_width() > self._su(avail_name_w):
            enemy_name_font = self._su_font(13)
            enemy_name_surf = enemy_name_font.render(name_text, True, e_name_color)
        while (
            enemy_name_surf.get_width() + self._su(10) + enemy_lvl_surf.get_width()
            > self._su(avail_name_w)
            and len(name_text) > 1
        ):
            name_text = name_text[:-1]
            enemy_name_surf = enemy_name_font.render(name_text + "…", True, e_name_color)
        # Stage 199/200 — подложка врага: текст вертикально центрирован,
        # fade-in как у игрока. Stage 202 — фикс: геометрия плашки считается
        # от ШИРИН С АУТЛАЙНОМ (имя прижато к правому краю полоски, уровень
        # левее); раньше ширина уровня бралась без аутлайна + магический «+1»
        # в blit — чёрный аутлайн мог вылезать за левый край подложки.
        enemy_name_surf = _outlined_text(enemy_name_surf)
        enemy_lvl_outlined = _outlined_text(enemy_lvl_surf)
        e_name_x = self._su(enemy_bar_right) - enemy_name_surf.get_width()
        e_lvl_x = e_name_x - self._su(10) - enemy_lvl_outlined.get_width()
        e_plate_left = e_lvl_x - self._su(4)
        e_plate_right = self._su(enemy_bar_right) + self._su(5)
        e_plate_w = e_plate_right - e_plate_left
        plate_h = self._su(24)
        plate_alpha = int(HUD_THEME["name_plate_alpha"] * getattr(self, "_hud_plate_fade", 1.0))
        plate_border_alpha = int(HUD_THEME["name_plate_border_alpha"]
                                 * getattr(self, "_hud_plate_fade", 1.0))
        enemy_plate = self._static_surface(
            f"name_plate_e_{e_plate_w}_{plate_h}_{plate_alpha}_{plate_border_alpha}",
            (e_plate_w, plate_h),
            lambda s: (
                pygame.draw.rect(s, (*HUD_THEME["name_plate_bg"], plate_alpha),
                                 s.get_rect(), border_radius=self._su(6)),
                pygame.draw.rect(s, (*HUD_THEME["name_plate_border"],
                                     plate_border_alpha),
                                 s.get_rect(), 1, border_radius=self._su(6)),
            ),
        )
        self.screen.blit(enemy_plate, (e_plate_left, self._su(enemy_name_y - 4)))
        e_plate_cy = self._su(enemy_name_y - 4) + plate_h // 2
        self.screen.blit(
            enemy_name_surf,
            (e_name_x, e_plate_cy - enemy_name_surf.get_height() // 2)
        )
        self.screen.blit(
            enemy_lvl_outlined,
            (e_lvl_x, e_plate_cy - enemy_lvl_outlined.get_height() // 2),
        )

        enemy_hp_y = enemy_name_y + 24
        enemy_hp = int(self._enemy_hp_display)
        enemy_max_hp = enemy_role.max_hp
        if self._enemy_fighter is not None:
            enemy_max_hp = self._enemy_fighter.max_hp
        # Stage 195 — ЗАЕРКАЛЬНОЕ списание: у врага остаток прижат к ЛЕВОМУ
        # (центро-обращённому) краю, пустота растёт справа налево к центру
        # (mirrored=False). Градиент инверсно (жёлтый кончик у центра).
        self._render_bar(
            enemy_hp_x, enemy_hp_y, HP_BAR_W, HP_BAR_H,
            value=enemy_hp,
            maximum=enemy_max_hp,
            fill_color=HP_FILL_COLOR,
            bg_color=HP_BG_COLOR,
            mirrored=False,
            gradient_mirrored=True,
            pulse_when_low=True,
            ghost_value=self._enemy_hp_ghost,
            gradient=True,
        )
        enemy_mp_y = enemy_hp_y + HP_BAR_H + BAR_GAP
        enemy_mp = int(self._enemy_mp_display)
        enemy_max_mp = enemy_role.max_mp
        if self._enemy_fighter is not None:
            enemy_max_mp = self._enemy_fighter.max_mp
        # Stage 195 — MP уже HP, кончики (левые края) совпадают.
        self._render_bar(
            enemy_hp_x, enemy_mp_y, MP_BAR_W, MP_BAR_H,
            value=enemy_mp,
            maximum=enemy_max_mp,
            fill_color=MP_FILL_COLOR,
            bg_color=MP_BG_COLOR,
            mirrored=False,
            gradient_mirrored=True,
            ghost_value=self._enemy_mp_ghost,
            gradient=True,
            gradient_from=MP_GRADIENT_COLOR_FROM,
            gradient_to=MP_GRADIENT_COLOR_TO,
        )

        return (enemy_hp_x, enemy_mp_y)

    def _render_hud_status_icons(
        self,
        p_bars: tuple[int, int],
        e_bars: tuple[int, int],
    ) -> list[tuple[pygame.Rect, str, int]]:
        """Stage 202 — ряды иконок статусов зеркально от кончиков полосок.

        Stage 192/195 — С ТЕНЬЮ (2px drop-shadow) и МИНИ-СЧЁТЧИКОМ ходов в
        углу; Stage 201 — rect'ы для ховера/тултипа — ДИЗАЙН (мышь боя в
        дизайн-пространстве окна), отрисовка — нативная (_blit_status_icon).
        Возвращает rect'ы для _render_status_tooltip (ClickRect'ы не
        регистрируются — тултип пассивный).
        """
        hp_x, mp_y = p_bars
        enemy_hp_x, enemy_mp_y = e_bars
        icon_rects: list[tuple[pygame.Rect, str, int]] = []
        if self._player_fighter is not None:
            active = self._player_fighter.status.get_active()
            if active:
                icon_size = DEBUFF_ICON_SIZE
                icon_gap = DEBUFF_ICON_GAP
                icon_y = mp_y + MP_BAR_H + 4  # below MP bar
                for i, status_name in enumerate(active):
                    icon = self.asset_manager.get_debuff_icon(
                        status_name, self._su(icon_size)
                    )
                    # кончик игрока = правый край полоски; рост влево
                    ix = hp_x + HP_BAR_W - (i + 1) * icon_size - i * icon_gap
                    duration = self._player_fighter.status.get_duration(status_name)
                    self._blit_status_icon(icon, ix, icon_y, duration, status_name)
                    icon_rects.append(
                        (pygame.Rect(ix, icon_y, icon_size, icon_size),
                         status_name, duration)
                    )
        # Enemy: кончик = левый край полоски; рост вправо (к аватару).
        if self._enemy_fighter is not None:
            active = self._enemy_fighter.status.get_active()
            if active:
                icon_size = DEBUFF_ICON_SIZE
                icon_gap = DEBUFF_ICON_GAP
                icon_y = enemy_mp_y + MP_BAR_H + 4
                for i, status_name in enumerate(active):
                    icon = self.asset_manager.get_debuff_icon(
                        status_name, self._su(icon_size)
                    )
                    ix = enemy_hp_x + i * (icon_size + icon_gap)
                    duration = self._enemy_fighter.status.get_duration(status_name)
                    self._blit_status_icon(icon, ix, icon_y, duration, status_name)
                    icon_rects.append(
                        (pygame.Rect(ix, icon_y, icon_size, icon_size),
                         status_name, duration)
                    )

        return icon_rects

    def _render_gauntlet_queue(self, enemy_mp_y: int) -> None:
        """Stage 134 — очередь гантлея: будущие/прошедшие враги справа.

        Stage 202 — вынесена из _render_hud; якорь — низ вражеской колонки
        (mp_y врага). Только в режиме гантелея, ниже ряда дебаффов врага.
        """
        if self._gauntlet_active and self._gauntlet_enemies:
            face_size = SLOT_QUEUE_FACE_SIZE
            face_gap = SLOT_QUEUE_GAP
            entries: list[tuple[str, bool]] = []
            for idx, mob_id in enumerate(self._gauntlet_enemies):
                if idx == self._gauntlet_round:
                    continue
                entries.append((mob_id, idx < self._gauntlet_round))
            if entries:
                total_w = len(entries) * face_size + (len(entries) - 1) * face_gap
                queue_x = SCREEN_WIDTH - 16 - total_w
                queue_y = enemy_mp_y + MP_BAR_H + 4 + DEBUFF_ICON_SIZE + 8
                first_future_drawn = False
                label_surf = self._su_font(13).render("далее", True, TEXT_DIM)
                for i, (mob_id, is_past) in enumerate(entries):
                    fx = queue_x + i * (face_size + face_gap)
                    avatar = self.asset_manager.get_enemy_avatar(
                        mob_id, self._su(face_size)
                    )
                    # Stage 154 — портрет центруется в слоте (может быть меньше).
                    a_pos = avatar.get_rect(
                        center=(self._su(fx) + self._su(face_size) // 2,
                                self._su(queue_y) + self._su(face_size) // 2)
                    ).topleft
                    slot_rect = self._su_rect(fx, queue_y, face_size, face_size)
                    if is_past:
                        dark = avatar.copy()
                        dark.fill((90, 90, 90), special_flags=pygame.BLEND_RGB_MULT)
                        self.screen.blit(dark, a_pos)
                        pygame.draw.rect(
                            self.screen, (113, 113, 122),
                            slot_rect, self._su(2), border_radius=self._su(6),
                        )
                    else:
                        if not first_future_drawn:
                            self.screen.blit(
                                label_surf,
                                (self._su(fx) + self._su(face_size) // 2 - label_surf.get_width() // 2,
                                 self._su(queue_y) - label_surf.get_height() - self._su(2)),
                            )
                            first_future_drawn = True
                        self.screen.blit(avatar, a_pos)
                        pygame.draw.rect(
                            self.screen, HUD_BORDER_COLOR,
                            slot_rect, 1, border_radius=self._su(6),
                        )

    def _render_bar(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        value: int,
        maximum: int,
        fill_color: tuple[int, int, int],
        bg_color: tuple[int, int, int],
        label: str = "",
        mirrored: bool = False,
        pulse_when_low: bool = False,
        ghost_value: float | None = None,
        gradient: bool = False,
        gradient_from: tuple[int, int, int] | None = None,
        gradient_to: tuple[int, int, int] | None = None,
        gradient_mirrored: bool | None = None,
        simple: bool = False,
    ) -> None:
        """Render a horizontal bar (HP/MP) with optional label.

        Stage 87 — when ``pulse_when_low`` is True (HP bar) and value ratio
        drops below ``HP_PULSE_RATIO`` (25%), fill color brightness oscillates
        at ``HP_PULSE_FREQ_HZ`` (1 Hz) — pulse without surface allocation.

        Stage 193/194 — ``gradient=True``: заливка — горизонтальный градиент
        (цвета из gradient_from/gradient_to; по умолчанию HP-пара), кэш
        _static_surface. ``ghost_value``: белый «догоняющий» сегмент между
        заливкой и прошлым значением (классика файтингов).

        Stage 195 — ``mirrored`` = ТОЛЬКО якорь заливки/ghost (True: остаток
        прижат к правому краю, пустота растёт слева). Направление градиента
        — отдельный флаг ``gradient_mirrored`` (None = как mirrored): жёлтый/
        голубой кончик всегда у центра экрана, основание — у края.

        Stage 196 — drop-shadow 2px под полоской (глубина): тёмная скруглённая
        плашка смещена на +2,+2, рисуется ДО тела полоски (кэш по размеру).

        Stage 201 — x/y/w/h приходят в ДИЗАЙН-координатах и масштабируются
        через _su() внутри (вся внутренняя математика — в пикселях рендера).

        Stage 203 — ``simple=True``: упрощённый MAP-режим (бывш.
        _render_map_bar): без тени/ghost/блика/shine-градиента, рамка
        MAP_PANEL_BORDER su(1), радиус 3, лейбл 10px bold — вид MAP-полосок
        сохранён 1:1.
        """
        rx, ry = self._su(x), self._su(y)
        rw, rh = self._su(w), self._su(h)
        rect = pygame.Rect(rx, ry, rw, rh)
        br = 3 if simple else self._su(4)
        if not simple:
            # Stage 196/197 — drop-shadow через общий хелпер (_drop_shadow):
            # основная плашка +2,+2 (альфа 110) + мягкий ореол +3,+3 (альфа 45).
            # Stage 197 — блик: 1px светлая линия вдоль верха полоски
            # («стекло» в паре с тенью; под рамкой, над заливкой).
            self._drop_shadow(rx, ry, rw, rh, offset=self._su(2), alpha=110,
                              halo_alpha=45, halo_spread=self._su(1),
                              border_radius=self._su(4),
                              cache_key=f"bar_shadow_{rw}x{rh}")
        pygame.draw.rect(self.screen, bg_color, rect, border_radius=br)
        fill_w = 0
        if maximum > 0:
            fill_w = max(0, int(rw * value / maximum))
            if fill_w > 0:
                fill_rect = pygame.Rect(rx, ry, fill_w, rh)
                if mirrored:
                    fill_rect = pygame.Rect(rx + (rw - fill_w), ry, fill_w, rh)
                # Stage 87 — pulse when HP is low.
                ratio = value / maximum
                if gradient:
                    g_from = gradient_from if gradient_from is not None else HP_GRADIENT_COLOR_FROM
                    g_to = gradient_to if gradient_to is not None else HP_GRADIENT_COLOR_TO
                    # Stage 195 — направление градиента НЕ привязано к якорю
                    # заливки: кончик (color_to) всегда у центра экрана.
                    eff_gm = gradient_mirrored if gradient_mirrored is not None else mirrored
                    key = f"bar_grad_{g_from}_{g_to}_{'r2l' if eff_gm else 'l2r'}_{rw}x{rh}"
                    grad = self._static_surface(
                        key, (rw, rh),
                        lambda s: _draw_bar_gradient(s, eff_gm, g_from, g_to),
                    )
                    surf = grad
                    if pulse_when_low and ratio < HP_PULSE_RATIO:
                        phase = (math.sin(self._hp_pulse_timer * 2.0 * math.pi * HP_PULSE_FREQ_HZ) + 1.0) * 0.5
                        pulse_factor = HP_PULSE_MIN + (HP_PULSE_MAX - HP_PULSE_MIN) * phase
                        tint = int(255 * pulse_factor)
                        surf = grad.copy()
                        surf.fill((tint, tint, tint), special_flags=pygame.BLEND_RGB_MULT)
                    # Окно кропа — сторона ОСНОВАНИЯ (color_from): у Ичиго
                    # слева, у врага справа (зеркально) — красный всегда у
                    # границы урона, тёплый кончик у центра.
                    area = (
                        pygame.Rect(rw - fill_w, 0, fill_w, rh)
                        if eff_gm
                        else pygame.Rect(0, 0, fill_w, rh)
                    )
                    self.screen.blit(surf, fill_rect.topleft, area=area)
                elif pulse_when_low and ratio < HP_PULSE_RATIO:
                    phase = (math.sin(self._hp_pulse_timer * 2.0 * math.pi * HP_PULSE_FREQ_HZ) + 1.0) * 0.5
                    pulse_factor = HP_PULSE_MIN + (HP_PULSE_MAX - HP_PULSE_MIN) * phase
                    tinted = tuple(min(255, int(c * pulse_factor)) for c in fill_color)
                    pygame.draw.rect(self.screen, tinted, fill_rect, border_radius=br)
                else:
                    pygame.draw.rect(self.screen, fill_color, fill_rect, border_radius=br)
        # Stage 193 — белый «догоняющий» сегмент (fill — текущая, ghost —
        # прошлое значение; зазор = недавно потерянное HP).
        if ghost_value is not None and maximum > 0:
            ghost_w = max(fill_w, min(rw, int(rw * max(0.0, ghost_value) / maximum)))
            if ghost_w > fill_w:
                gx = rx + (rw - ghost_w) if mirrored else rx + fill_w
                pygame.draw.rect(
                    self.screen, BAR_GHOST_COLOR,
                    pygame.Rect(gx, ry, ghost_w - fill_w, rh), border_radius=self._su(4),
                )
        # Stage 196/197 — стеклянный блик: 1px светлая линия вдоль верха
        # полоски (с отступом под скруглённые углы radius 4).
        if not simple:
            gloss_w = max(1, rw - self._su(6))
            gloss = self._static_surface(
                f"bar_gloss_{gloss_w}", (gloss_w, 1),
                lambda s: s.fill((255, 255, 255, 60)),
            )
            self.screen.blit(gloss, (rx + self._su(3), ry + self._su(1)))
        # Stage 198 — SHINE SWEEP: раз в BAR_SHINE_PERIOD сек мягкая белая
        # полоса пробегает слева направо по заливке (у зеркального врага —
        # справа налево, зеркально). Бэнд кэшируется, клип по телу полоски.
        if gradient and fill_w > 0:
            shine_timer = getattr(self, "_bar_shine_timer", 0.0)
            t_shine = (shine_timer % BAR_SHINE_PERIOD) / BAR_SHINE_PERIOD
            band_w = self._su(BAR_SHINE_BAND_W)
            band = self._static_surface(
                f"bar_shine_band_{band_w}x{rh}",
                (band_w, rh),
                _draw_shine_band,
            )
            # центр полосы идёт от левого края заливки к её кончику
            # (у врага — зеркально: от кончика к основанию).
            # Stage 198 — sweep ЗЕРКАЛЕН списанию: Ичиго (остаток прижат
            # справа) — бэнд слева направо; враг — справа налево к центру.
            if mirrored:
                cx = rx - band_w / 2 + t_shine * (rw + band_w)
            else:
                cx = rx + rw + band_w / 2 - t_shine * (rw + band_w)
            # клип по телу заливки (внутри скруглений: x+2 .. x+w-2)
            left = max(int(cx - band_w / 2), rx + self._su(2))
            right = min(int(cx + band_w / 2), rx + rw - self._su(2))
            if right > left:
                src_x = left - int(cx - band_w / 2)
                self.screen.blit(
                    band, (left, ry),
                    area=pygame.Rect(src_x, 0, right - left, rh),
                )
        if simple:
            pygame.draw.rect(self.screen, MAP_PANEL_BORDER, rect, self._su(1),
                             border_radius=3)
        else:
            pygame.draw.rect(self.screen, HUD_BORDER_COLOR, rect, 1,
                             border_radius=self._su(4))

        if label:
            if simple:
                label_surf = self._su_text(label, 10, TEXT_WHITE, bold=True)
            else:
                label_surf = self._su_font(13).render(label, True, TEXT_WHITE)
            label_rect = label_surf.get_rect(center=rect.center)
            self.screen.blit(label_surf, label_rect.topleft)

    def _blit_status_icon(
        self,
        icon: pygame.Surface,
        x: int,
        y: int,
        duration: int,
        status_name: str,
    ) -> None:
        """Stage 195/197 — иконка статуса с 2px-тенью и мини-счётчиком ходов.

        Тень — силуэт иконки (альфа 150) через общий хелпер `_drop_shadow`,
        смещённый на +2,+2, под иконкой; счётчик — тёмная плашка с цифрой
        оставшихся ходов в правом нижнем углу (показывается при duration > 1
        — одиночный эффект не подписываем, чтобы не шуметь).

        Stage 201 — x/y приходят в ДИЗАЙН-координатах, отрисовка — через _su
        (иконка уже нативного размера — get_debuff_icon(_su(icon_size))).
        """
        self._drop_shadow(
            self._su(x), self._su(y), icon.get_width(), icon.get_height(),
            offset=self._su(2), alpha=150, border_radius=self._su(4),
            cache_key=f"status_icon_shadow_{status_name}_{icon.get_width()}",
        )
        self.screen.blit(icon, (self._su(x), self._su(y)))
        # Счётчик ходов.
        if duration > 1:
            bw, bh = self._su(18), self._su(14)
            badge = self._static_surface(
                f"status_badge_{duration}_{bw}x{bh}",
                (bw, bh),
                lambda s: (
                    pygame.draw.rect(s, (24, 24, 28), s.get_rect(), border_radius=self._su(4)),
                    pygame.draw.rect(s, (82, 82, 91), s.get_rect(), 1, border_radius=self._su(4)),
                ),
            )
            bx = self._su(x) + icon.get_width() - badge.get_width() - self._su(1)
            by = self._su(y) + icon.get_height() - badge.get_height() - self._su(1)
            self.screen.blit(badge, (bx, by))
            num_surf = self._su_text(str(duration), 11, (250, 204, 21), bold=True)
            num_rect = num_surf.get_rect(
                center=(bx + badge.get_width() // 2, by + badge.get_height() // 2)
            )
            self.screen.blit(num_surf, num_rect)

    def _render_status_tooltip(
        self,
        icon_rects: list[tuple[pygame.Rect, str, int]],
    ) -> None:
        """Stage 195 — тултип иконки статуса при наведении.

        Stage 202 — панель через единый хелпер ui/tooltip.py («панель у
        курсора»: имя → описание с переносом → строка ходов; флип у краёв
        экрана). Только для статусов из STATUS_TOOLTIPS.
        """
        from pockie_rpg.config import STATUS_TOOLTIPS

        hit = None
        for rect, status_name, duration in icon_rects:
            if rect.collidepoint(self._mouse_pos):
                hit = (rect, status_name, duration)
                break
        if hit is None:
            return
        _rect, status_name, duration = hit
        info = STATUS_TOOLTIPS.get(status_name)
        if info is None:
            return
        name, desc = info

        lines = [
            TooltipLine(name, (250, 204, 21), size=14, bold=True),
            TooltipLine(desc, (212, 212, 216), size=12, space_before=4),
            TooltipLine(f"Осталось ходов: {duration}", (161, 161, 170),
                        size=12, space_before=4),
        ]
        render_tooltip_panel(
            self, lines, cursor=self._mouse_pos, wrap_width=260,
            style=PanelStyle(),
        )

    def _get_avatar_frame(self) -> pygame.Surface:
        """Stage 99 — return cached decorative avatar frame (border.svg style).

        Stage 201 — возвращается версия под ТЕКУЩИЙ масштаб рендера
        (_su_scaled, кэш по размеру) — legacy 1:1, нативная фаза ×scale.
        """
        if not hasattr(self, "_avatar_frame_raw_cache"):
            import os
            frame_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                "assets", "icons", "ui", "avatar_frame.png"
            )
            try:
                self._avatar_frame_raw_cache = pygame.image.load(frame_path).convert_alpha()
            except Exception:
                # Fallback: simple gold rect border.
                fp = 4
                fw = AVATAR_SIZE + fp * 2
                surf = pygame.Surface((fw, fw), pygame.SRCALPHA)
                pygame.draw.rect(surf, (234, 179, 8), (0, 0, fw, fw), 2, border_radius=6)
                self._avatar_frame_raw_cache = surf
        raw = self._avatar_frame_raw_cache
        return self._su_scaled(
            "avatar_frame", raw, raw.get_width(), raw.get_height()
        )

    def _render_vs_emblem(self, cx: int, cy: int) -> None:
        """Render the gold diamond VS emblem in the center of the HUD.

        Stage 201 — cx/cy — дизайн-координаты, отрисовка — ×_su.
        """
        size = self._su(28)
        ncx, ncy = self._su(cx), self._su(cy)
        points = [
            (ncx, ncy - size),
            (ncx + size, ncy),
            (ncx, ncy + size),
            (ncx - size, ncy),
        ]
        pygame.draw.polygon(self.screen, HUD_BG_COLOR, points)
        pygame.draw.polygon(self.screen, VS_GOLD_DARK, points, self._su(2))
        vs_surf = self._su_font(22, bold=True).render("VS", True, VS_GOLD_COLOR)
        vs_rect = vs_surf.get_rect(center=(ncx, ncy))
        self.screen.blit(vs_surf, vs_rect)

    def _render_side_banners(self) -> None:
        """Render vertical 'Осмотреть' banners on left + right edges.

        Stage 201 — rect'ы баннеров ДИЗАЙН (ховер + ClickRect), отрисовка —
        ×_su; буквы через _su_text (уже масштабо-осведомлён).
        """
        text = "Осмотреть"
        banner_h = BANNER_H

        left_rect = pygame.Rect(0, HUD_HEIGHT + BANNER_TOP_INSET, BANNER_W, banner_h)
        left_draw = self._su_rect(0, HUD_HEIGHT + BANNER_TOP_INSET, BANNER_W, banner_h)
        pygame.draw.rect(self.screen, BANNER_BG, left_draw)
        if left_rect.collidepoint(self._mouse_pos) and not self._char_sheet_open:
            # Stage 168 (аудит 5.2) — hover-подложка из кэша (была аллокация/кадр).
            hover_surf = self._static_surface(
                f"banner_hover_{left_draw.w}x{left_draw.h}",
                (left_draw.w, left_draw.h),
                lambda s: s.fill((234, 179, 8, 40)),
            )
            self.screen.blit(hover_surf, left_draw.topleft)
        chars = list(text)
        char_h = self._su_font(14, bold=True).get_height()
        total_h = char_h * len(chars)
        start_y = left_draw.centery - total_h // 2
        for i, ch in enumerate(chars):
            ch_surf = self._su_text(ch, 14, BANNER_TEXT_COLOR, bold=True)
            ch_rect = ch_surf.get_rect(center=(left_draw.centerx, start_y + i * char_h))
            self.screen.blit(ch_surf, ch_rect)

        right_rect = pygame.Rect(
            SCREEN_WIDTH - BANNER_W,
            HUD_HEIGHT + BANNER_TOP_INSET,
            BANNER_W,
            banner_h,
        )
        right_draw = self._su_rect(
            SCREEN_WIDTH - BANNER_W,
            HUD_HEIGHT + BANNER_TOP_INSET,
            BANNER_W,
            banner_h,
        )
        pygame.draw.rect(self.screen, BANNER_BG, right_draw)
        if right_rect.collidepoint(self._mouse_pos) and not self._char_sheet_open:
            hover_surf = self._static_surface(
                f"banner_hover_{right_draw.w}x{right_draw.h}",
                (right_draw.w, right_draw.h),
                lambda s: s.fill((234, 179, 8, 40)),
            )
            self.screen.blit(hover_surf, right_draw.topleft)
        start_y = right_draw.centery - total_h // 2
        for i, ch in enumerate(chars):
            ch_surf = self._su_text(ch, 14, BANNER_TEXT_COLOR, bold=True)
            ch_rect = ch_surf.get_rect(center=(right_draw.centerx, start_y + i * char_h))
            self.screen.blit(ch_surf, ch_rect)

    def _render_fighter(
        self,
        animator,
        x: int,
        is_player: bool,
        attack_seq=None,
        shake_offset: int = 0,
    ) -> None:
        """Render a fighter sprite + shadow + debuff icons + effect overlays.

        Stage 201 — анимация (attack_seq.current_x, shake) остаётся в
        ДИЗАЙН-координатах; спрайт берётся нативного размера
        (get_motion_sprite с ×_su размерами — кэш asset_manager по размеру),
        тень/кольцо/позиции — ×_su. Эффектам передаётся нативный центр +
        scale для размеров спрайтов.
        """
        if animator is None:
            return

        scale = getattr(self, "_render_scale", 1.0)
        if scale == 1.0:
            sprite = animator.get_sprite(self.asset_manager)
        else:
            from pockie_rpg.config import BODY_SPRITE_H, BODY_SPRITE_W
            sprite = self.asset_manager.get_motion_sprite(
                animator.folder,
                animator.frame_index,
                self._su(BODY_SPRITE_W),
                self._su(BODY_SPRITE_H),
                flip=animator.flip,
            )
        breathing = 0

        # Stage 192 — holds_position(): PARKED (победитель у поверженного
        # врага во время endgame) тоже читает current_x — спрайт не
        # телепортируется на базовую позицию.
        if attack_seq is not None and attack_seq.holds_position():
            actual_x = attack_seq.current_x
        else:
            actual_x = x

        actual_x += shake_offset

        sprite_w, sprite_h = sprite.get_size()
        blit_x = self._su(actual_x) - sprite_w // 2
        blit_y = self._su(SPRITE_BASE_Y) - sprite_h + breathing

        # Stage 168 (аудит 5.2) — тень бойца рисуется ОДИН РАЗ (кэш),
        # раньше — SRCALPHA-поверхность + ellipse дважды за кадр на бойца.
        sh_w, sh_h = self._su(SHADOW_W), self._su(SHADOW_H)
        shadow_surf = self._static_surface(
            f"fighter_shadow_{sh_w}x{sh_h}", (sh_w, sh_h),
            lambda s: pygame.draw.ellipse(s, (0, 0, 0, 90), s.get_rect()),
        )
        shadow_x = self._su(actual_x) - sh_w // 2
        shadow_y = self._su(SPRITE_BASE_Y) - sh_h + self._su(2)
        self.screen.blit(shadow_surf, (shadow_x, shadow_y))

        ring_w = sh_w + self._su(24)
        ring_h = sh_h + self._su(8)
        ring_surf = self._static_surface(
            f"fighter_ring_{ring_w}x{ring_h}", (ring_w, ring_h),
            lambda s: pygame.draw.ellipse(s, (234, 179, 8, 50), s.get_rect(), self._su(2)),
        )
        ring_x = self._su(actual_x) - ring_w // 2
        ring_y = self._su(SPRITE_BASE_Y) - ring_h + self._su(2)
        self.screen.blit(ring_surf, (ring_x, ring_y))

        self.screen.blit(sprite, (blit_x, blit_y))

        # Stage 98 — debuff icons moved to _render_hud (below HP bars).
        # Old code rendered them above the sprite via DEBUFF_ICON_Y_OFFSET.

        if is_player:
            ice_effect = self._player_ice
        else:
            ice_effect = self._enemy_ice
        if ice_effect.active:
            # Stage v132.1 — bind the ice block to the fighter's actual_x so it
            # follows the enemy during run/hit-shake, and anchor its Y to the
            # ground line (centerY = SPRITE_BASE_Y - RENDER_H//2 + Y_OFFSET) so
            # the block "stands on the ground" and never jumps between frames.
            ice_cx = self._su(actual_x + ICE_BLOCK_X_OFFSET)
            ice_cy = self._su(
                SPRITE_BASE_Y - ICE_BLOCK_RENDER_H // 2 + ICE_BLOCK_Y_OFFSET
            )
            ice_effect.render(self.screen, ice_cx, ice_cy, self.asset_manager, scale)

        if is_player:
            shield_effect = self._player_shield
        else:
            shield_effect = self._enemy_shield
        if shield_effect.active:
            # Stage v132.1 — bind the shield dome to the fighter's actual_x so it
            # moves together with the caster during run/hit-shake, and anchor its
            # Y to the ground line (centerY = SPRITE_BASE_Y - RENDER_H//2 + Y_OFFSET)
            # so the dome "stands on the ground" and never jumps between frames.
            shield_cx = self._su(actual_x + SHIELD_DOME_X_OFFSET)
            shield_cy = self._su(
                SPRITE_BASE_Y - SHIELD_DOME_RENDER_H // 2 + SHIELD_DOME_Y_OFFSET
            )
            shield_effect.render(self.screen, shield_cx, shield_cy, self.asset_manager, scale)

        if is_player:
            cloud_effect = self._player_cloud
        else:
            cloud_effect = self._enemy_cloud
        if cloud_effect.active:
            cloud_x = actual_x
            cloud_y = self._su(SPRITE_BASE_Y) - sprite_h - self._su(40)
            cloud_effect.render(
                self.screen, self._su(cloud_x), cloud_y, self.asset_manager, scale
            )

        if is_player:
            poison_effect = self._player_poison
        else:
            poison_effect = self._enemy_poison
        if poison_effect.active:
            sprite_center_y = self._su(SPRITE_BASE_Y) - sprite_h // 2
            poison_effect.render(
                self.screen, self._su(actual_x), sprite_center_y, self.asset_manager, scale
            )

    def _render_combat_log(self) -> None:
        """Render the bottom combat log bar (collapsed or expanded).

        Stage 201 — отрисовка ×_su; ClickRect треугольника — ДИЗАЙН-рект.
        """
        h = int(self._combat_log_height_display)
        log_rect = pygame.Rect(0, SCREEN_HEIGHT - h, SCREEN_WIDTH, h)
        # Stage 168 (аудит 5.2) — фон лога из кэша по высоте (аллокация была
        # каждый кадр; высоты анимации раскрытия — ограниченное множество).
        log_surf = self._static_surface(
            f"battle_log_bg_{self._su(SCREEN_WIDTH)}x{self._su(h)}",
            (self._su(SCREEN_WIDTH), self._su(h)),
            lambda s: s.fill((LOG_BG_COLOR[0], LOG_BG_COLOR[1], LOG_BG_COLOR[2], LOG_BG_ALPHA)),
        )
        self.screen.blit(log_surf, (0, self._su(log_rect.top)))
        pygame.draw.line(
            self.screen,
            HUD_DIVIDER_COLOR,
            (0, self._su(log_rect.top)),
            (self._su(SCREEN_WIDTH), self._su(log_rect.top)),
            1,
        )

        tri_cx = SCREEN_WIDTH // 2
        tri_cy = log_rect.top - 8
        expansion = (self._combat_log_height_display - LOG_BAR_H) / max(
            1, COMBAT_LOG_EXPANDED_H - LOG_BAR_H
        )
        expansion = max(0.0, min(1.0, expansion))
        self._render_combat_log_triangle(
            self._su(tri_cx), self._su(tri_cy), expansion
        )

        if not self._char_sheet_open:
            tri_click_rect = pygame.Rect(tri_cx - 12, tri_cy - 12, 24, 24)
            self._click_rects.insert(
                0,
                ClickRect(
                    tag="toggle_combat_log",
                    rect=tri_click_rect,
                    on_click=self._toggle_combat_log,
                )
            )

        if not self._combat_log_lines:
            return

        if self._combat_log_height_display >= COMBAT_LOG_EXPANDED_H - 1:
            lines_to_show = self._combat_log_lines[-COMBAT_LOG_MAX_LINES:]
            n = len(lines_to_show)
            for i, line in enumerate(lines_to_show):
                line_y = log_rect.top + 10 + (i * COMBAT_LOG_LINE_HEIGHT)
                if line_y + COMBAT_LOG_LINE_HEIGHT > log_rect.bottom - 2:
                    break
                if n > 1:
                    alpha = int(80 + (255 - 80) * (i / (n - 1)))
                else:
                    alpha = 255
                text_surf = self._su_font(13).render(line, True, TEXT_WHITE)
                text_surf.set_alpha(alpha)
                text_rect = text_surf.get_rect(
                    center=(self._su(SCREEN_WIDTH // 2),
                            self._su(line_y + COMBAT_LOG_LINE_HEIGHT // 2))
                )
                self.screen.blit(text_surf, text_rect)
        else:
            recent_line = self._combat_log_lines[-1]
            text_surf = self._su_font(13).render(recent_line, True, TEXT_WHITE)
            text_rect = text_surf.get_rect(
                center=(self._su(SCREEN_WIDTH // 2), self._su(log_rect.centery))
            )
            self.screen.blit(text_surf, text_rect)

        if self._combat_log_height_display < LOG_BAR_H + 20:
            esc_surf = self._su_font(13).render("ESC — назад на карту", True, TEXT_DIM)
            self.screen.blit(
                esc_surf,
                (
                    self._su(SCREEN_WIDTH) - esc_surf.get_width() - self._su(16),
                    self._su(log_rect.centery) - esc_surf.get_height() // 2,
                ),
            )

    def _render_combat_log_triangle(
        self, cx: int, cy: int, expansion: float
    ) -> None:
        """Render the green triangle, rotated based on expansion.

        Stage 201 — cx/cy приходят в нативных координатах (масштабирует
        вызывающий), радиус — дизайн 6 → ×_su внутри.
        """
        r = self._su(6)
        base_angles = (-math.pi / 2, math.pi / 4, 3 * math.pi / 4)
        angle_offset = expansion * math.pi
        points = []
        for ba in base_angles:
            a = ba + angle_offset
            x = cx + r * math.cos(a)
            y = cy + r * math.sin(a)
            points.append((x, y))
        pygame.draw.polygon(self.screen, (34, 197, 94), points)
        pygame.draw.polygon(self.screen, (22, 101, 52), points, 1)

    def _render_speed_buttons(self) -> None:
        """Render the 4 speed buttons (x1/x2/x3/x4) at bottom-center.

        Stage 201 — rect'ы кнопок ДИЗАЙН (ховер + ClickRect), отрисовка ×_su.
        """
        n_buttons = len(BATTLE_SPEEDS)
        row_w = n_buttons * SPEED_BTN_W + (n_buttons - 1) * SPEED_BTN_GAP
        row_x = (SCREEN_WIDTH - row_w) // 2
        base_y = SCREEN_HEIGHT - LOG_BAR_H - SPEED_BTN_H - 16
        row_y = int(base_y + self._speed_buttons_y_offset)

        for i, speed in enumerate(BATTLE_SPEEDS):
            btn_x = row_x + i * (SPEED_BTN_W + SPEED_BTN_GAP)
            btn_rect = pygame.Rect(btn_x, row_y, SPEED_BTN_W, SPEED_BTN_H)
            draw_rect = self._su_rect(btn_x, row_y, SPEED_BTN_W, SPEED_BTN_H)
            is_active = (speed == self._battle_speed)
            is_hover = btn_rect.collidepoint(self._mouse_pos)

            if is_active:
                bg_color = SPEED_BTN_ACTIVE_BG
                fg_color = SPEED_BTN_ACTIVE_FG
            elif is_hover:
                bg_color = SPEED_BTN_HOVER_BG
                fg_color = SPEED_BTN_INACTIVE_FG
            else:
                bg_color = SPEED_BTN_INACTIVE_BG
                fg_color = SPEED_BTN_INACTIVE_FG

            pygame.draw.rect(self.screen, bg_color, draw_rect, border_radius=self._su(6))
            border_color = SPEED_BTN_ACTIVE_BG if is_active else (63, 63, 70)
            pygame.draw.rect(self.screen, border_color, draw_rect, 1, border_radius=self._su(6))

            label = f"x{int(speed)}"
            label_surf = self._su_font(14, bold=True).render(label, True, fg_color)
            label_rect = label_surf.get_rect(center=draw_rect.center)
            self.screen.blit(label_surf, label_rect)

            tag = SPEED_BTN_TAGS[i]
            self._click_rects.insert(
                0,
                ClickRect(
                    tag=tag,
                    rect=btn_rect,
                    on_click=lambda s=speed: self._set_battle_speed(s),
                )
            )

    def _render_countdown(self) -> None:
        """Render the countdown text in big bold gold at center of screen.

        Stage 201 — шрифт/позиции ×_su (пульс-скейл — на нативной поверхности).
        """
        from pockie_rpg.config import COUNTDOWN_PHASES
        if self._countdown_phase_idx >= len(COUNTDOWN_PHASES):
            return

        phase_text, _ = COUNTDOWN_PHASES[self._countdown_phase_idx]
        scale = COUNTDOWN_TEXT_SCALE_PER_PHASE[
            min(self._countdown_phase_idx, len(COUNTDOWN_TEXT_SCALE_PER_PHASE) - 1)
        ]

        text_surf = self._su_font(96, bold=True).render(
            phase_text, True, COUNTDOWN_COLOR
        )
        if scale != 1.0:
            new_w = max(1, int(text_surf.get_width() * scale))
            new_h = max(1, int(text_surf.get_height() * scale))
            text_surf = pygame.transform.smoothscale(text_surf, (new_w, new_h))

        shadow_surf = self._su_font(96, bold=True).render(
            phase_text, True, COUNTDOWN_SHADOW_COLOR
        )
        if scale != 1.0:
            new_w = max(1, int(shadow_surf.get_width() * scale))
            new_h = max(1, int(shadow_surf.get_height() * scale))
            shadow_surf = pygame.transform.smoothscale(shadow_surf, (new_w, new_h))

        cx = self._su(SCREEN_WIDTH) // 2
        cy = self._su(SCREEN_HEIGHT) // 2
        shadow_rect = shadow_surf.get_rect(center=(cx + self._su(4), cy + self._su(4)))
        self.screen.blit(shadow_surf, shadow_rect.topleft)
        text_rect = text_surf.get_rect(center=(cx, cy))
        self.screen.blit(text_surf, text_rect.topleft)

    def _render_endgame(self) -> None:
        """Render the endgame overlay (phased — text then rewards).

        Stage 201 — мигрировано на _su/_su_font (работает в обеих фазах:
        legacy ×1.0 = прежний вид; нативный бой ×1.2 — чёткий текст).
        Используется и в MAP (мгновенные бои боссов) — там scale=1.0.
        """
        if not self._endgame_text:
            return

        cx = SCREEN_WIDTH // 2
        cy = SCREEN_HEIGHT // 2

        if self._endgame_phase == "text":
            is_win = self._endgame_text == "Победа"
            color = ENDGAME_WIN_COLOR if is_win else ENDGAME_LOSE_COLOR
            shadow_color = (0, 0, 0)

            text_surf = self._su_font(60, bold=True).render(
                self._endgame_text, True, color
            )
            shadow_surf = self._su_font(60, bold=True).render(
                self._endgame_text, True, shadow_color
            )

            pulse = 1.0 + 0.1 * math.sin(self._endgame_text_timer * math.pi * 2.0)
            new_w = max(1, int(text_surf.get_width() * pulse))
            new_h = max(1, int(text_surf.get_height() * pulse))
            text_scaled = pygame.transform.smoothscale(text_surf, (new_w, new_h))
            shadow_scaled = pygame.transform.smoothscale(shadow_surf, (new_w, new_h))

            shadow_rect = shadow_scaled.get_rect(
                center=(self._su(cx) + self._su(4), self._su(cy) + self._su(4))
            )
            self.screen.blit(shadow_scaled, shadow_rect.topleft)
            text_rect = text_scaled.get_rect(center=(self._su(cx), self._su(cy)))
            self.screen.blit(text_scaled, text_rect.topleft)
            return

        if self._endgame_phase == "rewards":
            win_x = (SCREEN_WIDTH - ENDGAME_WINDOW_W) // 2
            win_y = (SCREEN_HEIGHT - ENDGAME_WINDOW_H) // 2
            win_rect = self._su_rect(
                win_x, win_y, ENDGAME_WINDOW_W, ENDGAME_WINDOW_H
            )

            dim_surf = self._su_overlay(120)
            self.screen.blit(dim_surf, (0, 0))

            pygame.draw.rect(
                self.screen, ENDGAME_WINDOW_BG, win_rect,
                border_radius=self._su(ENDGAME_WINDOW_RADIUS),
            )
            pygame.draw.rect(
                self.screen, ENDGAME_WINDOW_BORDER, win_rect, self._su(2),
                border_radius=self._su(ENDGAME_WINDOW_RADIUS),
            )

            # Stage 79 — skip "Награды" title when boss_error (no attempts).
            # Stage 201 — вертикальный layout в ДИЗАЙН-координатах (row_y),
            # масштабирование — при отрисовке (self._su(row_y)); шрифты —
            # _su_font (нативные поверхности).
            boss_err = getattr(self, "_world_boss_error", False)
            title_h = 0
            if not boss_err:
                title_surf = self._su_font(28, bold=True).render(
                    "Награды", True, ENDGAME_WINDOW_BORDER
                )
                title_x = self._su(win_x) + (win_rect.w - title_surf.get_width()) // 2
                self.screen.blit(title_surf, (title_x, self._su(win_y + 24)))
                title_h = int(round(
                    title_surf.get_height() / max(0.01, getattr(self, "_render_scale", 1.0))
                ))
            title_h = title_h if title_h else 0

            is_victory = (self._endgame_text == "Победа")
            row_y = win_y + 24 + title_h + 32
            row_gap = 32

            def _cx(surf: pygame.Surface) -> int:
                return self._su(win_x) + (win_rect.w - surf.get_width()) // 2

            font_content = self._su_font(18, bold=True)
            font_levelup = self._su_font(16, bold=True)
            font_dim = self._su_font(18)

            if is_victory:
                # Stage 184 — бонус от xp-бафов показывается в скобках
                # зелёным: «Опыт: +50 (+250)» (если бафы активны).
                xp_base_text = f"Опыт: +{self._endgame_xp_gained}"
                xp_bonus = getattr(self, "_endgame_xp_bonus", 0)
                if xp_bonus > 0:
                    xp_base_text += f" (+{xp_bonus})"
                    # Пересчёт: база белым + бонус зелёным, единый центр.
                    base_only = f"Опыт: +{self._endgame_xp_gained} "
                    base_surf = font_content.render(base_only, True, TEXT_WHITE)
                    bonus_surf = font_content.render(
                        f"(+{xp_bonus})", True, (80, 220, 100),
                    )
                    bx = self._su(win_x) + (win_rect.w
                            - base_surf.get_width() - bonus_surf.get_width()) // 2
                    self.screen.blit(base_surf, (bx, self._su(row_y)))
                    self.screen.blit(bonus_surf,
                                     (bx + base_surf.get_width(), self._su(row_y)))
                else:
                    xp_surf = font_content.render(xp_base_text, True, TEXT_WHITE)
                    self.screen.blit(xp_surf, (_cx(xp_surf), self._su(row_y)))
                row_y += row_gap

                gold_surf = font_content.render(
                    f"Золото: +{self._endgame_gold_gained}", True, ENDGAME_GOLD_COLOR
                )
                self.screen.blit(gold_surf, (_cx(gold_surf), self._su(row_y)))
                row_y += row_gap

                if self._endgame_leveled_up:
                    lvl_text = (
                        f"Уровень повышен! {self._endgame_old_level} "
                        f"→ {self._endgame_new_level}"
                    )
                    lvl_surf = font_levelup.render(lvl_text, True, ENDGAME_LEVELUP_COLOR)
                    self.screen.blit(lvl_surf, (_cx(lvl_surf), self._su(row_y)))
                    row_y += row_gap

                # Stage 117 — Loot Grid for animated battle (same as x10).
                # Collect drops into loot_items list for unified grid display.
                # Stage 118 — uses shared _build_loot_tooltip_lines + _render_loot_slot
                # from QuickBattleRendererMixin so the tooltip shows base + extra stats.
                # Stage 119 — uses unified _endgame_equipment_drop (max 1 per battle).
                loot_items: list[dict] = []

                # Gems.
                gems = getattr(self, "_endgame_gems_dropped", None) or []
                from collections import Counter
                gem_counts = Counter()
                for gem in gems:
                    gem_counts[(gem["type"], gem["level"])] += 1
                for (g_type, g_level), count in gem_counts.items():
                    from pockie_rpg.config import GEM_ICON_DIR
                    from pockie_rpg.data.item_db import get_gem, get_gem_icon_filename
                    icon_file = get_gem_icon_filename(g_type, g_level)
                    icon_path = str(GEM_ICON_DIR / icon_file)
                    # Stage 203 — _su_image(fit) вместо удалённого
                    # _load_gem_icon_surface (42 = 48 − 6, прежний внутренний
                    # отступ иконки в слоте).
                    icon_surf = self._su_image(icon_path, 42, 42, fit=True)
                    gem_def = get_gem(g_type)
                    gem_name = gem_def.get("name", g_type) if gem_def else g_type
                    loot_items.append({"icon_surf": icon_surf, "rarity": "Grey", "count": count,
                                       "tooltip": f"{gem_name} L{g_level}", "type": "gem"})

                # Stage 119 — unified single equipment_drop (max 1 per battle).
                # Falls back to legacy per-type fields for old saves.
                eq_drop = getattr(self, "_endgame_equipment_drop", None)
                if eq_drop:
                    eq_type = eq_drop.get("type", "weapon")
                    eq_name = eq_drop.get("name", "")
                    eq_rarity = eq_drop.get("rarity", "")
                    item_id = eq_drop.get("item_id")
                    # Resolve icon + matched_item from generated_weapons.
                    # Stage 204 — словари вынесены в item_db (единый источник).
                    icon_filename = DEFAULT_GEAR_ICONS.get(eq_type, "weapon_wooden.png")
                    matched_item: dict | None = None
                    if item_id is not None:
                        matched_item = self.player.generated_weapons.get(item_id)
                        if matched_item is not None:
                            icon_filename = matched_item.get("icon_filename", icon_filename)
                    icon_path = os.path.join(str(ASSETS_DIR), "icons", "items", icon_filename)
                    icon_surf = self._su_image(icon_path, 42, 42, fit=True)
                    tooltip_lines = None
                    if matched_item is not None:
                        tooltip_lines = self._build_loot_tooltip_lines(
                            item_name=eq_name, rarity=eq_rarity,
                            item_stats=matched_item.get("stats", {}),
                            item_slot=matched_item.get("slot", DEFAULT_TYPE_TO_SLOT.get(eq_type, "weapon")),
                            item_level=matched_item.get("item_level", 1),
                            level_requirement=matched_item.get("level_requirement"),
                        )
                    # Stage 119 — mark auto-sold items in tooltip.
                    if eq_drop.get("auto_sold") and tooltip_lines:
                        tooltip_lines = list(tooltip_lines) + [
                            ("─" * 24, (113, 113, 122)),
                            ("[АВТО-ПРОДАНО]", (220, 38, 38)),
                        ]
                    loot_items.append({
                        "icon_surf": icon_surf, "rarity": eq_rarity, "count": 1,
                        "tooltip": eq_name, "tooltip_lines": tooltip_lines,
                        "type": eq_type, "auto_sold": eq_drop.get("auto_sold", False),
                    })

                # Render loot grid if any items.
                if loot_items:
                    loot_label = self._su_font(14, bold=True).render(
                        "Полученный лут:", True, ENDGAME_GOLD_COLOR
                    )
                    self.screen.blit(
                        loot_label, (_cx(loot_label), self._su(row_y))
                    )
                    row_y += 24

                    slot_sz = 48
                    slot_gap = 6
                    max_cols = 5
                    grid_x_start = win_x + (ENDGAME_WINDOW_W - max_cols * slot_sz - (max_cols - 1) * slot_gap) // 2
                    for idx, loot in enumerate(loot_items):
                        col = idx % max_cols
                        row = idx // max_cols
                        sx = grid_x_start + col * (slot_sz + slot_gap)
                        sy = row_y + row * (slot_sz + slot_gap)
                        # Stage 118 — delegate to shared _render_loot_slot (handles
                        # rarity bg, icon, count badge, hover + rich tooltip).
                        # Stage 201 — координаты ДИЗАЙН (масштабирует внутри).
                        # Stage 203 — hasattr-гард и fallback удалены (мёртвый
                        # код: QuickBattleRendererMixin всегда в PygameUI).
                        self._render_loot_slot(
                            sx, sy, slot_sz, loot.get("icon_surf"),
                            loot.get("rarity", ""), loot.get("count", 1),
                            loot.get("type", "item"),
                            loot.get("tooltip", ""),
                            loot.get("tooltip_lines"),
                        )

                    grid_rows = (len(loot_items) + max_cols - 1) // max_cols
                    row_y += grid_rows * (slot_sz + slot_gap) + 8
            else:
                defeat_surf = font_content.render(
                    "Вы потерпели поражение", True, ENDGAME_LOSE_COLOR
                )
                self.screen.blit(defeat_surf, (_cx(defeat_surf), self._su(row_y)))
                row_y += row_gap

                xp_surf = font_dim.render("Опыт: 0", True, TEXT_DIM)
                self.screen.blit(xp_surf, (_cx(xp_surf), self._su(row_y)))
                row_y += row_gap

                gold_surf = font_dim.render("Золото: 0", True, TEXT_DIM)
                self.screen.blit(gold_surf, (_cx(gold_surf), self._su(row_y)))
                row_y += row_gap

            # Stage 71/72/77/79 — World Boss rank display.
            if getattr(self, "_world_boss_active", False) and self._world_boss_active:
                rank = getattr(self, "_world_boss_rank", "")
                damage = getattr(self, "_world_boss_damage_dealt", 0)
                boss_killed = getattr(self, "_world_boss_killed", False)
                boss_error = getattr(self, "_world_boss_error", False)
                item_drop = getattr(self, "_world_boss_item_drop", None)
                if boss_error:
                    # Stage 79 — no "Награды" title, no XP/gold. Just the error.
                    error_surf = self._su_font(20, bold=True).render(
                        "Попытки закончились!", True, (220, 38, 38)
                    )
                    self.screen.blit(error_surf, (_cx(error_surf), self._su(row_y)))
                    row_y += row_gap
                    sub_surf = font_content.render(
                        "Ждите восстановления (30 мин за попытку)", True, TEXT_DIM
                    )
                    self.screen.blit(sub_surf, (_cx(sub_surf), self._su(row_y)))
                    row_y += row_gap
                elif rank:
                    # Big rank letter.
                    rank_colors = {
                        "F": (150, 150, 150), "B": (100, 200, 255), "A": (80, 220, 100),
                        "S": (234, 179, 8), "SS": (255, 140, 0), "SSS": (255, 50, 50),
                    }
                    rank_color = rank_colors.get(rank, (234, 179, 8))
                    rank_surf = self._su_font(48, bold=True).render(
                        rank, True, rank_color
                    )
                    self.screen.blit(rank_surf, (_cx(rank_surf), self._su(row_y)))
                    row_y += 50
                    # Damage text.
                    dmg_surf = self._su_font(16, bold=True).render(
                        f"Нанесено урона: {damage}", True, TEXT_WHITE
                    )
                    self.screen.blit(dmg_surf, (_cx(dmg_surf), self._su(row_y)))
                    row_y += row_gap
                    # Gold reward.
                    gold_surf = font_content.render(
                        f"Золото: +{self._endgame_gold_gained}", True, ENDGAME_GOLD_COLOR
                    )
                    self.screen.blit(gold_surf, (_cx(gold_surf), self._su(row_y)))
                    row_y += row_gap
                    # Stage 77 — item drop (SSS 30%).
                    if item_drop:
                        drop_surf = self._su_font(16, bold=True).render(
                            f"Получен предмет: {item_drop}!", True, (255, 200, 50)
                        )
                        self.screen.blit(drop_surf, (_cx(drop_surf), self._su(row_y)))
                        row_y += row_gap
                    # Stage 72 — boss killed message.
                    if boss_killed:
                        kill_surf = self._su_font(18, bold=True).render(
                            "Босс повержен! Новый уровень!", True, (80, 220, 100)
                        )
                        self.screen.blit(kill_surf, (_cx(kill_surf), self._su(row_y)))
                        row_y += row_gap

            ok_btn_w = ENDGAME_OK_BTN_W
            ok_btn_h = ENDGAME_OK_BTN_H
            ok_btn_x = win_x + (ENDGAME_WINDOW_W - ok_btn_w) // 2
            ok_btn_y = win_y + ENDGAME_WINDOW_H - ok_btn_h - 24
            ok_btn_rect = pygame.Rect(ok_btn_x, ok_btn_y, ok_btn_w, ok_btn_h)
            hover = ok_btn_rect.collidepoint(self._mouse_pos)
            ok_bg = ENDGAME_OK_BTN_BG_HOVER if hover else ENDGAME_OK_BTN_BG
            ok_draw = self._su_rect(ok_btn_x, ok_btn_y, ok_btn_w, ok_btn_h)
            pygame.draw.rect(self.screen, ok_bg, ok_draw, border_radius=self._su(8))
            pygame.draw.rect(self.screen, (255, 255, 255), ok_draw, self._su(2), border_radius=self._su(8))

            ok_text = self._su_font(18, bold=True).render("ОК", True, ENDGAME_OK_BTN_FG)
            ok_text_rect = ok_text.get_rect(center=ok_draw.center)
            self.screen.blit(ok_text, ok_text_rect.topleft)

            self._click_rects = [
                ClickRect(
                    tag="endgame_ok",
                    rect=ok_btn_rect,
                    on_click=self._endgame_ok_clicked,
                )
            ]
            return

        return

    def _render_skills_grid(
        self, x: int, y: int
    ) -> tuple[int, list[tuple[pygame.Rect, int | None]]]:
        """Render the 10-slot skills grid (5 cols x 2 rows) at (x, y).

        Iterates the player's actual skill deck and fills slots 0..N with
        each skill's icon. Empty slots are rendered as locked.
        """
        from pockie_rpg.config import (
            SKILLS_GRID_COLS,
            SKILLS_GRID_ROWS,
            SKILLS_SLOT_EMPTY_BG,
            SKILLS_SLOT_EMPTY_BORDER,
            SKILLS_SLOT_GAP,
            SKILLS_SLOT_SIZE,
        )
        from pockie_rpg.game.state import ROLES

        is_enemy_grid = (
            self._char_sheet_target == "enemy" and self._enemy_fighter is not None
        )
        if is_enemy_grid:
            enemy_role = ROLES.get(self._enemy_fighter.role_id)
            skill_deck = list(enemy_role.skills) if enemy_role else []
        elif self.player is not None:
            player_role = ROLES.get(self.player.role_id)
            skill_deck = list(player_role.skills) if player_role else []
        else:
            skill_deck = []

        if is_enemy_grid or self.player is None:
            active_skill_ids: set[int] = set(skill_deck)
        else:
            active_skill_ids = set(self.player.active_skills)

        slots: list[tuple[pygame.Rect, int | None]] = []
        for row in range(SKILLS_GRID_ROWS):
            for col in range(SKILLS_GRID_COLS):
                slot_idx = row * SKILLS_GRID_COLS + col
                slot_x = x + col * (SKILLS_SLOT_SIZE + SKILLS_SLOT_GAP)
                slot_y = y + row * (SKILLS_SLOT_SIZE + SKILLS_SLOT_GAP)
                slot_rect = pygame.Rect(slot_x, slot_y, SKILLS_SLOT_SIZE, SKILLS_SLOT_SIZE)
                if slot_idx < len(skill_deck):
                    skill_id = skill_deck[slot_idx]
                    is_active = skill_id in active_skill_ids
                    if is_active:
                        pygame.draw.rect(
                            self.screen, SKILLS_SLOT_ACTIVE_BG, slot_rect, border_radius=4
                        )
                        pygame.draw.rect(
                            self.screen, (255, 255, 255), slot_rect, 1, border_radius=4
                        )
                    else:
                        pygame.draw.rect(
                            self.screen, SKILLS_SLOT_INACTIVE_BG, slot_rect, border_radius=4
                        )
                        pygame.draw.rect(
                            self.screen,
                            SKILLS_SLOT_INACTIVE_BORDER,
                            slot_rect,
                            1,
                            border_radius=4,
                        )
                    icon = self.asset_manager.get_skill_icon(skill_id, 36)
                    if not is_active:
                        icon = icon.copy()
                        icon.set_alpha(SKILLS_SLOT_INACTIVE_ICON_ALPHA)
                    icon_x = slot_x + (SKILLS_SLOT_SIZE - 36) // 2
                    icon_y = slot_y + (SKILLS_SLOT_SIZE - 36) // 2
                    self.screen.blit(icon, (icon_x, icon_y))
                    slots.append((slot_rect, skill_id))
                else:
                    pygame.draw.rect(self.screen, SKILLS_SLOT_EMPTY_BG, slot_rect, border_radius=4)
                    pygame.draw.rect(self.screen, SKILLS_SLOT_EMPTY_BORDER, slot_rect, 1, border_radius=4)
                    slots.append((slot_rect, None))
        self._last_skills_grid_slots = slots
        return (y + SKILLS_GRID_H, slots)

    def _render_skill_tooltip(
        self,
        skill_id: int | None,
        x: int,
        y: int,
        w: int,
        h: int,
    ) -> None:
        """Render a tooltip area for a skill (placeholder if skill_id is None)."""
        from pockie_rpg.config import (
            SKILL_CONFIG,
            SKILLS_TOOLTIP_DESC_COLOR,
            SKILLS_TOOLTIP_MAX_LINE_WIDTH,
            SKILLS_TOOLTIP_PLACEHOLDER_COLOR,
            SKILLS_TOOLTIP_STATS_COLOR,
            SKILLS_TOOLTIP_TITLE_COLOR,
        )

        pad = 8
        if skill_id is None or skill_id not in SKILL_CONFIG:
            placeholder = "Наведите курсор на навык для подсказки"
            ph_surf = self.font_skills_tooltip_desc.render(
                placeholder, True, SKILLS_TOOLTIP_PLACEHOLDER_COLOR
            )
            ph_x = x + (w - ph_surf.get_width()) // 2
            ph_y = y + (h - ph_surf.get_height()) // 2
            self.screen.blit(ph_surf, (ph_x, ph_y))
            return

        skill = SKILL_CONFIG[skill_id]
        title_surf = self.font_skills_tooltip_title.render(
            skill["name"], True, SKILLS_TOOLTIP_TITLE_COLOR
        )
        self.screen.blit(title_surf, (x + pad, y + 4))

        desc = skill.get("description", "")
        desc_lines = _wrap_text(desc, SKILLS_TOOLTIP_MAX_LINE_WIDTH)
        line_y = y + 4 + title_surf.get_height() + 2
        for line in desc_lines:
            line_surf = self.font_skills_tooltip_desc.render(
                line, True, SKILLS_TOOLTIP_DESC_COLOR
            )
            self.screen.blit(line_surf, (x + pad, line_y))
            line_y += line_surf.get_height() + 1

        stats_text = (
            f"MP: {skill['mp_cost']} · "
            f"Шанс: {int(skill['trigger_chance'] * 100)}% · "
            f"Заморозка: {int(skill['freeze_chance'] * 100)}% · "
            f"Длительность: {skill['freeze_duration']} хода"
        )
        stats_surf = self.font_skills_tooltip_stats.render(
            stats_text, True, SKILLS_TOOLTIP_STATS_COLOR
        )
        self.screen.blit(stats_surf, (x + pad, line_y + 2))
