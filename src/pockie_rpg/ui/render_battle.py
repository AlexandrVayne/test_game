"""BattleRendererMixin — battle state rendering (HUD, fighters, log, overlays)."""
from __future__ import annotations

import math
import random

import pygame

# Stage 86 — Variant B fix for "font not initialized" crash.
# render_battle.py is imported lazily by main.py BEFORE PygameUI.__init__()
# runs pygame.init(). The module-level _FONT_* calls below need pygame.font
# to be initialized first, otherwise they raise pygame.error.
# pygame.font.init() is idempotent — calling it again later inside
# PygameUI.__init__() (via pygame.init()) is a no-op, so this is safe.
pygame.font.init()

# Stage 85 — cached fonts (avoid creating SysFont every frame in _render_endgame).
# Stage 118 — added _FONT_14 + _FONT_14B for loot grid label + count badges + tooltips
# (previously referenced but never defined, causing NameError on animated-battle endgame).
_FONT_18B = pygame.font.SysFont("dejavusans,arial", 18, bold=True)
_FONT_16B = pygame.font.SysFont("dejavusans,arial", 16, bold=True)
_FONT_14B = pygame.font.SysFont("dejavusans,arial", 14, bold=True)
_FONT_14 = pygame.font.SysFont("dejavusans,arial", 14)
_FONT_18 = pygame.font.SysFont("dejavusans,arial", 18)
_FONT_20B = pygame.font.SysFont("dejavusans,arial", 20, bold=True)
_FONT_48B = pygame.font.SysFont("dejavusans,arial", 48, bold=True)

from pockie_rpg.config import (
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
from pockie_rpg.game.state import ENEMY_MOBS, ROLES, STARTER_SUITS
from pockie_rpg.ui.animator import ClickRect


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
        """Render BATTLE state: bg + HUD + banners + sprites + log + speed btns."""
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

        self._particles.render(self.screen)
        self._damage_numbers.render(self.screen)
        self._cast_effect.render(self.screen, self.asset_manager)
        self._projectile_effect.render(self.screen, self.asset_manager)

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
        """
        # Stage 98 — no background fill (transparent HUD, shows battle bg).
        # Stage 99 — removed bottom border line (per user request).

        suit = STARTER_SUITS.get(self.player.suit_id)
        enemy = ENEMY_MOBS.get(self.target_mob_id)
        if suit is None or enemy is None:
            return
        player_role = ROLES.get(self.player.role_id)
        enemy_role = ROLES.get(enemy.role_id)
        if player_role is None or enemy_role is None:
            return

        avatar_x = 16
        avatar_y = (HUD_HEIGHT - AVATAR_SIZE) // 2
        player_avatar = self.asset_manager.get_avatar(
            suit.avatar_filename, AVATAR_SIZE
        )
        # Stage 99 — decorative avatar frame (border.svg style).
        frame_surf = self._get_avatar_frame()
        frame_pad = (frame_surf.get_width() - AVATAR_SIZE) // 2
        self.screen.blit(frame_surf, (avatar_x - frame_pad, avatar_y - frame_pad))
        self.screen.blit(player_avatar, (avatar_x, avatar_y))

        name_x = avatar_x + AVATAR_SIZE + 12 + HUD_BAR_CENTER_SHIFT
        name_y = avatar_y - 2
        # Stage 200 — цвета имён/уровня из HUD_THEME (единая точка).
        p_name_color = HUD_THEME["name_text_color"]
        p_lvl_color = HUD_THEME["level_text_color"]
        name_surf = self.font_body.render(player_role.name, True, p_name_color)
        # Stage 197 — 1px чёрный аутлайн вместо тени (текст над полосками).
        name_surf = _outlined_text(name_surf)
        lvl_surf = self.font_small.render(
            f"Ур. {self.player.level}", True, p_lvl_color
        )
        # Stage 198 — аутлайн и на тексте уровня.
        lvl_surf = _outlined_text(lvl_surf)
        # Stage 199/200 — тёмная ПОДЛОЖКА под имя+уровень: текст
        # ВЕРТИКАЛЬНО ЦЕНТРИРОВАН (имя и уровень на общей средней линии),
        # fade-in с боем (HUD_PLATE_FADE_SEC из HUD_THEME).
        plate_h = 24
        plate_w = (name_surf.get_width() + 10 + lvl_surf.get_width() + 6) + 3
        plate_alpha = int(HUD_THEME["name_plate_alpha"]
                          * getattr(self, "_hud_plate_fade", 1.0))
        plate_border_alpha = int(HUD_THEME["name_plate_border_alpha"]
                                 * getattr(self, "_hud_plate_fade", 1.0))
        name_plate = self._static_surface(
            f"name_plate_{plate_w}_{plate_alpha}_{plate_border_alpha}",
            (plate_w, plate_h),
            lambda s: (
                pygame.draw.rect(s, (*HUD_THEME["name_plate_bg"], plate_alpha),
                                 s.get_rect(), border_radius=6),
                pygame.draw.rect(s, (*HUD_THEME["name_plate_border"],
                                     plate_border_alpha),
                                 s.get_rect(), 1, border_radius=6),
            ),
        )
        self.screen.blit(name_plate, (name_x - 3, name_y - 4))
        # Вертикальное центрирование: имя — по центру плашки, уровень —
        # тоже по центру (общая средняя линия, а не «привязка к верху»).
        plate_cy = name_y - 4 + plate_h // 2
        self.screen.blit(name_surf, (name_x, plate_cy - name_surf.get_height() // 2))
        self.screen.blit(
            lvl_surf,
            (name_x + name_surf.get_width() + 10,
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

        enemy_avatar = self.asset_manager.get_enemy_avatar(self.target_mob_id, AVATAR_SIZE)
        enemy_avatar_x = SCREEN_WIDTH - AVATAR_SIZE - 16
        enemy_avatar_y = (HUD_HEIGHT - AVATAR_SIZE) // 2
        # Stage 99 — decorative avatar frame for enemy.
        self.screen.blit(frame_surf, (enemy_avatar_x - frame_pad, enemy_avatar_y - frame_pad))
        # Stage 154 — портрет может быть МЕНЬШЕ слота (без апскейла) → центруем.
        self.screen.blit(enemy_avatar, enemy_avatar.get_rect(
            center=(enemy_avatar_x + AVATAR_SIZE // 2,
                    enemy_avatar_y + AVATAR_SIZE // 2)).topleft)

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
        enemy_name_font = self.font_body
        e_name_color = HUD_THEME["name_text_color"]
        e_lvl_color = HUD_THEME["level_text_color"]
        enemy_lvl_surf = self.font_small.render(
            f"Ур. {enemy.level}", True, e_lvl_color
        )
        name_text = enemy.name
        enemy_name_surf = enemy_name_font.render(name_text, True, e_name_color)
        vs_right_edge = SCREEN_WIDTH // 2 + 34
        avail_name_w = enemy_bar_right - vs_right_edge
        if enemy_name_surf.get_width() + 10 + enemy_lvl_surf.get_width() > avail_name_w:
            enemy_name_font = self.font_small
            enemy_name_surf = enemy_name_font.render(name_text, True, e_name_color)
        while (
            enemy_name_surf.get_width() + 10 + enemy_lvl_surf.get_width() > avail_name_w
            and len(name_text) > 1
        ):
            name_text = name_text[:-1]
            enemy_name_surf = enemy_name_font.render(name_text + "…", True, e_name_color)
        # Stage 199/200 — подложка врага: текст вертикально центрирован,
        # fade-in как у игрока. ГОТЧА: имени уже добавлен аутлайн (+2px
        # справа) — правый край имени = bar_right - name_w + 2.
        enemy_name_surf = _outlined_text(enemy_name_surf)
        enemy_lvl_outlined = _outlined_text(enemy_lvl_surf)
        e_plate_right = enemy_bar_right - enemy_name_surf.get_width() + 2 + 5
        e_plate_left = (enemy_bar_right - enemy_name_surf.get_width() - 10
                        - enemy_lvl_surf.get_width() - 4)
        e_plate_w = e_plate_right - e_plate_left
        plate_h = 24
        plate_alpha = int(HUD_THEME["name_plate_alpha"] * getattr(self, "_hud_plate_fade", 1.0))
        plate_border_alpha = int(HUD_THEME["name_plate_border_alpha"]
                                 * getattr(self, "_hud_plate_fade", 1.0))
        enemy_plate = self._static_surface(
            f"name_plate_e_{e_plate_w}_{plate_alpha}_{plate_border_alpha}",
            (e_plate_w, plate_h),
            lambda s: (
                pygame.draw.rect(s, (*HUD_THEME["name_plate_bg"], plate_alpha),
                                 s.get_rect(), border_radius=6),
                pygame.draw.rect(s, (*HUD_THEME["name_plate_border"],
                                     plate_border_alpha),
                                 s.get_rect(), 1, border_radius=6),
            ),
        )
        self.screen.blit(enemy_plate, (e_plate_left, enemy_name_y - 4))
        e_plate_cy = enemy_name_y - 4 + plate_h // 2
        self.screen.blit(
            enemy_name_surf,
            (enemy_bar_right - enemy_name_surf.get_width(),
             e_plate_cy - enemy_name_surf.get_height() // 2)
        )
        self.screen.blit(
            enemy_lvl_outlined,
            (
                enemy_bar_right - enemy_name_surf.get_width() - 10 - enemy_lvl_surf.get_width() + 1,
                e_plate_cy - enemy_lvl_outlined.get_height() // 2,
            ),
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

        self._render_vs_emblem(SCREEN_WIDTH // 2, HUD_HEIGHT // 2)

        # Stage 192/195 — иконки статусов ЗЕРКАЛЬНО от кончиков полосок,
        # С ТЕНЬЮ (2px drop-shadow) и МИНИ-СЧЁТЧИКОМ ходов в углу.
        icon_rects: list[tuple[pygame.Rect, str, int]] = []
        if self._player_fighter is not None:
            active = self._player_fighter.status.get_active()
            if active:
                icon_size = DEBUFF_ICON_SIZE
                icon_gap = DEBUFF_ICON_GAP
                icon_y = mp_y + MP_BAR_H + 4  # below MP bar
                for i, status_name in enumerate(active):
                    icon = self.asset_manager.get_debuff_icon(status_name, icon_size)
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
                    icon = self.asset_manager.get_debuff_icon(status_name, icon_size)
                    ix = enemy_hp_x + i * (icon_size + icon_gap)
                    duration = self._enemy_fighter.status.get_duration(status_name)
                    self._blit_status_icon(icon, ix, icon_y, duration, status_name)
                    icon_rects.append(
                        (pygame.Rect(ix, icon_y, icon_size, icon_size),
                         status_name, duration)
                    )

        # Stage 195 — тултип иконки статуса при наведении (имя + описание).
        self._render_status_tooltip(icon_rects)

        # Stage 134 — slot-gauntlet enemy queue: below the enemy debuff row,
        # right-aligned to the HUD edge. Only rendered during the gauntlet.
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
                label_surf = self.font_small.render("далее", True, TEXT_DIM)
                for i, (mob_id, is_past) in enumerate(entries):
                    fx = queue_x + i * (face_size + face_gap)
                    avatar = self.asset_manager.get_enemy_avatar(mob_id, face_size)
                    # Stage 154 — портрет центруется в слоте (может быть меньше).
                    a_pos = avatar.get_rect(
                        center=(fx + face_size // 2, queue_y + face_size // 2)).topleft
                    if is_past:
                        dark = avatar.copy()
                        dark.fill((90, 90, 90), special_flags=pygame.BLEND_RGB_MULT)
                        self.screen.blit(dark, a_pos)
                        pygame.draw.rect(
                            self.screen, (113, 113, 122),
                            pygame.Rect(fx, queue_y, face_size, face_size), 2, border_radius=6,
                        )
                    else:
                        if not first_future_drawn:
                            self.screen.blit(
                                label_surf,
                                (fx + face_size // 2 - label_surf.get_width() // 2, queue_y - label_surf.get_height() - 2),
                            )
                            first_future_drawn = True
                        self.screen.blit(avatar, a_pos)
                        pygame.draw.rect(
                            self.screen, HUD_BORDER_COLOR,
                            pygame.Rect(fx, queue_y, face_size, face_size), 1, border_radius=6,
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
        """
        rect = pygame.Rect(x, y, w, h)
        # Stage 196/197 — drop-shadow через общий хелпер (_drop_shadow):
        # основная плашка +2,+2 (альфа 110) + мягкий ореол +3,+3 (альфа 45).
        # Stage 197 — блик: 1px светлая линия вдоль верха полоски
        # («стекло» в паре с тенью; под рамкой, над заливкой).
        self._drop_shadow(x, y, w, h, offset=2, alpha=110, halo_alpha=45,
                          halo_spread=1, border_radius=4,
                          cache_key=f"bar_shadow_{w}x{h}")
        pygame.draw.rect(self.screen, bg_color, rect, border_radius=4)
        fill_w = 0
        if maximum > 0:
            fill_w = max(0, int(w * value / maximum))
            if fill_w > 0:
                fill_rect = pygame.Rect(x, y, fill_w, h)
                if mirrored:
                    fill_rect = pygame.Rect(x + (w - fill_w), y, fill_w, h)
                # Stage 87 — pulse when HP is low.
                ratio = value / maximum
                if gradient:
                    g_from = gradient_from if gradient_from is not None else HP_GRADIENT_COLOR_FROM
                    g_to = gradient_to if gradient_to is not None else HP_GRADIENT_COLOR_TO
                    # Stage 195 — направление градиента НЕ привязано к якорю
                    # заливки: кончик (color_to) всегда у центра экрана.
                    eff_gm = gradient_mirrored if gradient_mirrored is not None else mirrored
                    key = f"bar_grad_{g_from}_{g_to}_{'r2l' if eff_gm else 'l2r'}_{w}x{h}"
                    grad = self._static_surface(
                        key, (w, h),
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
                        pygame.Rect(w - fill_w, 0, fill_w, h)
                        if eff_gm
                        else pygame.Rect(0, 0, fill_w, h)
                    )
                    self.screen.blit(surf, fill_rect.topleft, area=area)
                elif pulse_when_low and ratio < HP_PULSE_RATIO:
                    phase = (math.sin(self._hp_pulse_timer * 2.0 * math.pi * HP_PULSE_FREQ_HZ) + 1.0) * 0.5
                    pulse_factor = HP_PULSE_MIN + (HP_PULSE_MAX - HP_PULSE_MIN) * phase
                    tinted = tuple(min(255, int(c * pulse_factor)) for c in fill_color)
                    pygame.draw.rect(self.screen, tinted, fill_rect, border_radius=4)
                else:
                    pygame.draw.rect(self.screen, fill_color, fill_rect, border_radius=4)
        # Stage 193 — белый «догоняющий» сегмент (fill — текущая, ghost —
        # прошлое значение; зазор = недавно потерянное HP).
        if ghost_value is not None and maximum > 0:
            ghost_w = max(fill_w, min(w, int(w * max(0.0, ghost_value) / maximum)))
            if ghost_w > fill_w:
                gx = x + (w - ghost_w) if mirrored else x + fill_w
                pygame.draw.rect(
                    self.screen, BAR_GHOST_COLOR,
                    pygame.Rect(gx, y, ghost_w - fill_w, h), border_radius=4,
                )
        # Stage 196/197 — стеклянный блик: 1px светлая линия вдоль верха
        # полоски (с отступом под скруглённые углы radius 4).
        gloss_w = max(1, w - 6)
        gloss = self._static_surface(
            f"bar_gloss_{gloss_w}", (gloss_w, 1),
            lambda s: s.fill((255, 255, 255, 60)),
        )
        self.screen.blit(gloss, (x + 3, y + 1))
        # Stage 198 — SHINE SWEEP: раз в BAR_SHINE_PERIOD сек мягкая белая
        # полоса пробегает слева направо по заливке (у зеркального врага —
        # справа налево, зеркально). Бэнд кэшируется, клип по телу полоски.
        if gradient and fill_w > 0:
            shine_timer = getattr(self, "_bar_shine_timer", 0.0)
            t_shine = (shine_timer % BAR_SHINE_PERIOD) / BAR_SHINE_PERIOD
            band_w = BAR_SHINE_BAND_W
            band = self._static_surface(
                f"bar_shine_band_{band_w}x{h}",
                (band_w, h),
                _draw_shine_band,
            )
            # центр полосы идёт от левого края заливки к её кончику
            # (у врага — зеркально: от кончика к основанию).
            # Stage 198 — sweep ЗЕРКАЛЕН списанию: Ичиго (остаток прижат
            # справа) — бэнд слева направо; враг — справа налево к центру.
            if mirrored:
                cx = x - band_w / 2 + t_shine * (w + band_w)
            else:
                cx = x + w + band_w / 2 - t_shine * (w + band_w)
            # клип по телу заливки (внутри скруглений: x+2 .. x+w-2)
            left = max(int(cx - band_w / 2), x + 2)
            right = min(int(cx + band_w / 2), x + w - 2)
            if right > left:
                src_x = left - int(cx - band_w / 2)
                self.screen.blit(
                    band, (left, y),
                    area=pygame.Rect(src_x, 0, right - left, h),
                )
        pygame.draw.rect(self.screen, HUD_BORDER_COLOR, rect, 1, border_radius=4)

        if label:
            label_surf = self.font_small.render(label, True, TEXT_WHITE)
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
        """
        self._drop_shadow(
            x, y, icon.get_width(), icon.get_height(),
            offset=2, alpha=150, border_radius=4,
            cache_key=f"status_icon_shadow_{status_name}_{icon.get_width()}",
        )
        self.screen.blit(icon, (x, y))
        # Счётчик ходов.
        if duration > 1:
            badge = self._static_surface(
                f"status_badge_{duration}",
                (18, 14),
                lambda s: (
                    pygame.draw.rect(s, (24, 24, 28), s.get_rect(), border_radius=4),
                    pygame.draw.rect(s, (82, 82, 91), s.get_rect(), 1, border_radius=4),
                ),
            )
            bx = x + icon.get_width() - badge.get_width() - 1
            by = y + icon.get_height() - badge.get_height() - 1
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

        Панель у курсора: ИМЯ (золото) → описание с переносом → строка
        «осталось N ход.». Флип у краёв экрана. Только для статусов из
        STATUS_TOOLTIPS.
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

        font_name = self._su_font(14, bold=True)
        font_body = self._su_font(12)
        name_surf = font_name.render(name, True, (250, 204, 21))
        # перенос описания по ширине
        wrap_w = 260
        desc_lines: list[str] = []
        cur = ""
        for word in desc.split():
            trial = f"{cur} {word}" if cur else word
            if font_body.size(trial)[0] <= wrap_w:
                cur = trial
            else:
                if cur:
                    desc_lines.append(cur)
                cur = word
        if cur:
            desc_lines.append(cur)
        dur_text = f"Осталось ходов: {duration}"
        dur_surf = font_body.render(dur_text, True, (161, 161, 170))

        pad = 8
        w = max(
            name_surf.get_width(),
            max(font_body.size(line)[0] for line in desc_lines) if desc_lines else 0,
            dur_surf.get_width(),
        ) + pad * 2
        h = (
            name_surf.get_height()
            + (len(desc_lines)) * (font_body.get_height() + 1)
            + dur_surf.get_height()
            + pad * 2 + 6
        )
        mx, my = self._mouse_pos
        tx = mx + 16
        ty = my + 16
        if tx + w > SCREEN_WIDTH - 8:
            tx = mx - 16 - w
        if ty + h > SCREEN_HEIGHT - 8:
            ty = my - 16 - h
        tx = max(8, tx)
        ty = max(8, ty)

        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(panel, (15, 15, 18, 235), panel.get_rect(), border_radius=8)
        pygame.draw.rect(panel, (82, 82, 91, 255), panel.get_rect(), 1, border_radius=8)
        panel.blit(name_surf, (pad, pad))
        yy = pad + name_surf.get_height() + 4
        for line in desc_lines:
            ls = font_body.render(line, True, (212, 212, 216))
            panel.blit(ls, (pad, yy))
            yy += font_body.get_height() + 1
        panel.blit(dur_surf, (pad, yy + 2))
        self.screen.blit(panel, (tx, ty))

    def _get_avatar_frame(self) -> pygame.Surface:
        """Stage 99 — return cached decorative avatar frame (border.svg style)."""
        if not hasattr(self, "_avatar_frame_cache"):
            import os
            frame_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                "assets", "icons", "ui", "avatar_frame.png"
            )
            try:
                self._avatar_frame_cache = pygame.image.load(frame_path).convert_alpha()
            except Exception:
                # Fallback: simple gold rect border.
                from pockie_rpg.config import AVATAR_SIZE
                fp = 4
                fw = AVATAR_SIZE + fp * 2
                surf = pygame.Surface((fw, fw), pygame.SRCALPHA)
                pygame.draw.rect(surf, (234, 179, 8), (0, 0, fw, fw), 2, border_radius=6)
                self._avatar_frame_cache = surf
        return self._avatar_frame_cache

    def _render_vs_emblem(self, cx: int, cy: int) -> None:
        """Render the gold diamond VS emblem in the center of the HUD."""
        size = 28
        points = [
            (cx, cy - size),
            (cx + size, cy),
            (cx, cy + size),
            (cx - size, cy),
        ]
        pygame.draw.polygon(self.screen, HUD_BG_COLOR, points)
        pygame.draw.polygon(self.screen, VS_GOLD_DARK, points, 2)
        vs_surf = self.font_vs.render("VS", True, VS_GOLD_COLOR)
        vs_rect = vs_surf.get_rect(center=(cx, cy))
        self.screen.blit(vs_surf, vs_rect)

    def _render_side_banners(self) -> None:
        """Render vertical 'Осмотреть' banners on left + right edges."""
        text = "Осмотреть"
        banner_h = BANNER_H

        left_rect = pygame.Rect(0, HUD_HEIGHT + BANNER_TOP_INSET, BANNER_W, banner_h)
        pygame.draw.rect(self.screen, BANNER_BG, left_rect)
        if left_rect.collidepoint(self._mouse_pos) and not self._char_sheet_open:
            # Stage 168 (аудит 5.2) — hover-подложка из кэша (была аллокация/кадр).
            hover_surf = self._static_surface(
                "banner_hover",
                (BANNER_W, left_rect.h),
                lambda s: s.fill((234, 179, 8, 40)),
            )
            self.screen.blit(hover_surf, left_rect.topleft)
        chars = list(text)
        char_h = self.font_banner.get_height()
        total_h = char_h * len(chars)
        start_y = left_rect.centery - total_h // 2
        for i, ch in enumerate(chars):
            ch_surf = self._su_text(ch, 14, BANNER_TEXT_COLOR, bold=True)
            ch_rect = ch_surf.get_rect(center=(left_rect.centerx, start_y + i * char_h))
            self.screen.blit(ch_surf, ch_rect)

        right_rect = pygame.Rect(
            SCREEN_WIDTH - BANNER_W,
            HUD_HEIGHT + BANNER_TOP_INSET,
            BANNER_W,
            banner_h,
        )
        pygame.draw.rect(self.screen, BANNER_BG, right_rect)
        if right_rect.collidepoint(self._mouse_pos) and not self._char_sheet_open:
            hover_surf = self._static_surface(
                "banner_hover",
                (BANNER_W, right_rect.h),
                lambda s: s.fill((234, 179, 8, 40)),
            )
            self.screen.blit(hover_surf, right_rect.topleft)
        start_y = right_rect.centery - total_h // 2
        for i, ch in enumerate(chars):
            ch_surf = self._su_text(ch, 14, BANNER_TEXT_COLOR, bold=True)
            ch_rect = ch_surf.get_rect(center=(right_rect.centerx, start_y + i * char_h))
            self.screen.blit(ch_surf, ch_rect)

    def _render_fighter(
        self,
        animator,
        x: int,
        is_player: bool,
        attack_seq=None,
        shake_offset: int = 0,
    ) -> None:
        """Render a fighter sprite + shadow + debuff icons + effect overlays."""
        if animator is None:
            return

        sprite = animator.get_sprite(self.asset_manager)
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
        blit_x = actual_x - sprite_w // 2
        blit_y = SPRITE_BASE_Y - sprite_h + breathing

        # Stage 168 (аудит 5.2) — тень бойца рисуется ОДИН РАЗ (кэш),
        # раньше — SRCALPHA-поверхность + ellipse дважды за кадр на бойца.
        shadow_surf = self._static_surface(
            "fighter_shadow", (SHADOW_W, SHADOW_H),
            lambda s: pygame.draw.ellipse(s, (0, 0, 0, 90), s.get_rect()),
        )
        shadow_x = actual_x - SHADOW_W // 2
        shadow_y = SPRITE_BASE_Y - SHADOW_H + 2
        self.screen.blit(shadow_surf, (shadow_x, shadow_y))

        ring_w = SHADOW_W + 24
        ring_h = SHADOW_H + 8
        ring_surf = self._static_surface(
            "fighter_ring", (ring_w, ring_h),
            lambda s: pygame.draw.ellipse(s, (234, 179, 8, 50), s.get_rect(), 2),
        )
        ring_x = actual_x - ring_w // 2
        ring_y = SPRITE_BASE_Y - ring_h + 2
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
            ice_cx = actual_x + ICE_BLOCK_X_OFFSET
            ice_cy = SPRITE_BASE_Y - ICE_BLOCK_RENDER_H // 2 + ICE_BLOCK_Y_OFFSET
            ice_effect.render(self.screen, ice_cx, ice_cy, self.asset_manager)

        if is_player:
            shield_effect = self._player_shield
        else:
            shield_effect = self._enemy_shield
        if shield_effect.active:
            # Stage v132.1 — bind the shield dome to the fighter's actual_x so it
            # moves together with the caster during run/hit-shake, and anchor its
            # Y to the ground line (centerY = SPRITE_BASE_Y - RENDER_H//2 + Y_OFFSET)
            # so the dome "stands on the ground" and never jumps between frames.
            shield_cx = actual_x + SHIELD_DOME_X_OFFSET
            shield_cy = SPRITE_BASE_Y - SHIELD_DOME_RENDER_H // 2 + SHIELD_DOME_Y_OFFSET
            shield_effect.render(self.screen, shield_cx, shield_cy, self.asset_manager)

        if is_player:
            cloud_effect = self._player_cloud
        else:
            cloud_effect = self._enemy_cloud
        if cloud_effect.active:
            cloud_x = actual_x
            cloud_y = blit_y - 40
            cloud_effect.render(self.screen, cloud_x, cloud_y, self.asset_manager)

        if is_player:
            poison_effect = self._player_poison
        else:
            poison_effect = self._enemy_poison
        if poison_effect.active:
            sprite_center_y = SPRITE_BASE_Y - sprite_h // 2
            poison_effect.render(self.screen, actual_x, sprite_center_y, self.asset_manager)

    def _render_combat_log(self) -> None:
        """Render the bottom combat log bar (collapsed or expanded)."""
        h = int(self._combat_log_height_display)
        log_rect = pygame.Rect(0, SCREEN_HEIGHT - h, SCREEN_WIDTH, h)
        # Stage 168 (аудит 5.2) — фон лога из кэша по высоте (аллокация была
        # каждый кадр; высоты анимации раскрытия — ограниченное множество).
        log_surf = self._static_surface(
            "battle_log_bg",
            (SCREEN_WIDTH, h),
            lambda s: s.fill((LOG_BG_COLOR[0], LOG_BG_COLOR[1], LOG_BG_COLOR[2], LOG_BG_ALPHA)),
        )
        self.screen.blit(log_surf, log_rect.topleft)
        pygame.draw.line(
            self.screen,
            HUD_DIVIDER_COLOR,
            (0, log_rect.top),
            (SCREEN_WIDTH, log_rect.top),
            1,
        )

        tri_cx = SCREEN_WIDTH // 2
        tri_cy = log_rect.top - 8
        expansion = (self._combat_log_height_display - LOG_BAR_H) / max(
            1, COMBAT_LOG_EXPANDED_H - LOG_BAR_H
        )
        expansion = max(0.0, min(1.0, expansion))
        self._render_combat_log_triangle(tri_cx, tri_cy, expansion)

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
                text_surf = self.font_small.render(line, True, TEXT_WHITE)
                text_surf.set_alpha(alpha)
                text_rect = text_surf.get_rect(center=(SCREEN_WIDTH // 2, line_y + COMBAT_LOG_LINE_HEIGHT // 2))
                self.screen.blit(text_surf, text_rect)
        else:
            recent_line = self._combat_log_lines[-1]
            text_surf = self.font_small.render(recent_line, True, TEXT_WHITE)
            text_rect = text_surf.get_rect(center=(SCREEN_WIDTH // 2, log_rect.centery))
            self.screen.blit(text_surf, text_rect)

        if self._combat_log_height_display < LOG_BAR_H + 20:
            esc_surf = self.font_small.render("ESC — назад на карту", True, TEXT_DIM)
            self.screen.blit(
                esc_surf,
                (
                    SCREEN_WIDTH - esc_surf.get_width() - 16,
                    log_rect.centery - esc_surf.get_height() // 2,
                ),
            )

    def _render_combat_log_triangle(
        self, cx: int, cy: int, expansion: float
    ) -> None:
        """Render the green triangle, rotated based on expansion."""
        r = 6
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
        """Render the 4 speed buttons (x1/x2/x3/x4) at bottom-center."""
        n_buttons = len(BATTLE_SPEEDS)
        row_w = n_buttons * SPEED_BTN_W + (n_buttons - 1) * SPEED_BTN_GAP
        row_x = (SCREEN_WIDTH - row_w) // 2
        base_y = SCREEN_HEIGHT - LOG_BAR_H - SPEED_BTN_H - 16
        row_y = int(base_y + self._speed_buttons_y_offset)

        for i, speed in enumerate(BATTLE_SPEEDS):
            btn_x = row_x + i * (SPEED_BTN_W + SPEED_BTN_GAP)
            btn_rect = pygame.Rect(btn_x, row_y, SPEED_BTN_W, SPEED_BTN_H)
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

            pygame.draw.rect(self.screen, bg_color, btn_rect, border_radius=6)
            border_color = SPEED_BTN_ACTIVE_BG if is_active else (63, 63, 70)
            pygame.draw.rect(self.screen, border_color, btn_rect, 1, border_radius=6)

            label = f"x{int(speed)}"
            label_surf = self.font_speed_btn.render(label, True, fg_color)
            label_rect = label_surf.get_rect(center=btn_rect.center)
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
        """Render the countdown text in big bold gold at center of screen."""
        from pockie_rpg.config import COUNTDOWN_PHASES
        if self._countdown_phase_idx >= len(COUNTDOWN_PHASES):
            return

        phase_text, _ = COUNTDOWN_PHASES[self._countdown_phase_idx]
        scale = COUNTDOWN_TEXT_SCALE_PER_PHASE[
            min(self._countdown_phase_idx, len(COUNTDOWN_TEXT_SCALE_PER_PHASE) - 1)
        ]

        text_surf = self.font_countdown.render(phase_text, True, COUNTDOWN_COLOR)
        if scale != 1.0:
            new_w = max(1, int(text_surf.get_width() * scale))
            new_h = max(1, int(text_surf.get_height() * scale))
            text_surf = pygame.transform.smoothscale(text_surf, (new_w, new_h))

        shadow_surf = self.font_countdown.render(phase_text, True, COUNTDOWN_SHADOW_COLOR)
        if scale != 1.0:
            new_w = max(1, int(shadow_surf.get_width() * scale))
            new_h = max(1, int(shadow_surf.get_height() * scale))
            shadow_surf = pygame.transform.smoothscale(shadow_surf, (new_w, new_h))

        cx = SCREEN_WIDTH // 2
        cy = SCREEN_HEIGHT // 2
        shadow_rect = shadow_surf.get_rect(center=(cx + 4, cy + 4))
        self.screen.blit(shadow_surf, shadow_rect.topleft)
        text_rect = text_surf.get_rect(center=(cx, cy))
        self.screen.blit(text_surf, text_rect.topleft)

    def _render_endgame(self) -> None:
        """Render the endgame overlay (phased — text then rewards)."""
        if not self._endgame_text:
            return

        cx = SCREEN_WIDTH // 2
        cy = SCREEN_HEIGHT // 2

        if self._endgame_phase == "text":
            is_win = self._endgame_text == "Победа"
            color = ENDGAME_WIN_COLOR if is_win else ENDGAME_LOSE_COLOR
            shadow_color = (0, 0, 0)

            text_surf = self.font_endgame.render(self._endgame_text, True, color)
            shadow_surf = self.font_endgame.render(self._endgame_text, True, shadow_color)

            pulse = 1.0 + 0.1 * math.sin(self._endgame_text_timer * math.pi * 2.0)
            new_w = max(1, int(text_surf.get_width() * pulse))
            new_h = max(1, int(text_surf.get_height() * pulse))
            text_scaled = pygame.transform.smoothscale(text_surf, (new_w, new_h))
            shadow_scaled = pygame.transform.smoothscale(shadow_surf, (new_w, new_h))

            shadow_rect = shadow_scaled.get_rect(center=(cx + 4, cy + 4))
            self.screen.blit(shadow_scaled, shadow_rect.topleft)
            text_rect = text_scaled.get_rect(center=(cx, cy))
            self.screen.blit(text_scaled, text_rect.topleft)
            return

        if self._endgame_phase == "rewards":
            win_x = (SCREEN_WIDTH - ENDGAME_WINDOW_W) // 2
            win_y = (SCREEN_HEIGHT - ENDGAME_WINDOW_H) // 2
            win_rect = pygame.Rect(win_x, win_y, ENDGAME_WINDOW_W, ENDGAME_WINDOW_H)

            dim_surf = self.asset_manager.get_overlay(120)
            self.screen.blit(dim_surf, (0, 0))

            pygame.draw.rect(
                self.screen, ENDGAME_WINDOW_BG, win_rect,
                border_radius=ENDGAME_WINDOW_RADIUS,
            )
            pygame.draw.rect(
                self.screen, ENDGAME_WINDOW_BORDER, win_rect, 2,
                border_radius=ENDGAME_WINDOW_RADIUS,
            )

            # Stage 79 — skip "Награды" title when boss_error (no attempts).
            boss_err = getattr(self, "_world_boss_error", False)
            title_h = 0
            if not boss_err:
                title_surf = self.font_charsheet_title.render("Награды", True, ENDGAME_WINDOW_BORDER)
                title_x = win_x + (ENDGAME_WINDOW_W - title_surf.get_width()) // 2
                title_y = win_y + 24
                self.screen.blit(title_surf, (title_x, title_y))
                title_h = title_surf.get_height()
            else:
                title_y = win_y + 24

            is_victory = (self._endgame_text == "Победа")
            row_y = title_y + title_h + 32
            row_gap = 32

            font_content = _FONT_18B
            font_levelup = _FONT_16B
            font_dim = _FONT_18

            if is_victory:
                # Stage 184 — бонус от xp-бафов показывается в скобках
                # зелёным: «Опыт: +50 (+250)» (если бафы активны).
                xp_base_text = f"Опыт: +{self._endgame_xp_gained}"
                xp_bonus = getattr(self, "_endgame_xp_bonus", 0)
                if xp_bonus > 0:
                    xp_base_text += f" (+{xp_bonus})"
                xp_surf = font_content.render(xp_base_text, True, TEXT_WHITE)
                total_w = xp_surf.get_width()
                if xp_bonus > 0:
                    # Пересчёт: база белым + бонус зелёным, единый центр.
                    base_only = f"Опыт: +{self._endgame_xp_gained} "
                    base_surf = font_content.render(base_only, True, TEXT_WHITE)
                    bonus_surf = font_content.render(
                        f"(+{xp_bonus})", True, (80, 220, 100),
                    )
                    total_w = base_surf.get_width() + bonus_surf.get_width()
                    bx = win_x + (ENDGAME_WINDOW_W - total_w) // 2
                    self.screen.blit(base_surf, (bx, row_y))
                    self.screen.blit(bonus_surf,
                                     (bx + base_surf.get_width(), row_y))
                else:
                    xp_x = win_x + (ENDGAME_WINDOW_W - total_w) // 2
                    self.screen.blit(xp_surf, (xp_x, row_y))
                row_y += row_gap

                gold_text = f"Золото: +{self._endgame_gold_gained}"
                gold_surf = font_content.render(gold_text, True, ENDGAME_GOLD_COLOR)
                gold_x = win_x + (ENDGAME_WINDOW_W - gold_surf.get_width()) // 2
                self.screen.blit(gold_surf, (gold_x, row_y))
                row_y += row_gap

                if self._endgame_leveled_up:
                    lvl_text = (
                        f"Уровень повышен! {self._endgame_old_level} "
                        f"→ {self._endgame_new_level}"
                    )
                    lvl_surf = font_levelup.render(lvl_text, True, ENDGAME_LEVELUP_COLOR)
                    lvl_x = win_x + (ENDGAME_WINDOW_W - lvl_surf.get_width()) // 2
                    self.screen.blit(lvl_surf, (lvl_x, row_y))
                    row_y += row_gap

                # Stage 117 — Loot Grid for animated battle (same as x10).
                # Collect drops into loot_items list for unified grid display.
                # Stage 118 — uses shared _build_loot_tooltip_lines + _render_loot_slot
                # from QuickBattleRendererMixin so the tooltip shows base + extra stats.
                # Stage 119 — uses unified _endgame_equipment_drop (max 1 per battle).
                from pockie_rpg.config import RARITY_RGB, RARITY_SLOT_BG
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
                    if hasattr(self, "_load_gem_icon_surface"):
                        icon_surf = self._load_gem_icon_surface(icon_path, 48)
                    else:
                        icon_surf = None
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
                    default_icons = {
                        "weapon": "weapon_wooden.png",
                        "armor":  "vest_ninja.png",
                        "boots":  "boots_shinobi.png",
                        "ring":   "ring1.png",
                        "gloves": "gloves_leather.png",
                        "belt":   "belt_fabric.png",
                        "head":   "headband_ninja.png",
                    }
                    default_slots = {
                        "weapon": "weapon", "armor": "body",
                        "boots":  "boots",  "ring":  "accessory",
                        "gloves": "hands",  "belt":  "belt",
                        "head":   "head",
                    }
                    icon_filename = default_icons.get(eq_type, "weapon_wooden.png")
                    matched_item: dict | None = None
                    if item_id is not None:
                        matched_item = self.player.generated_weapons.get(item_id)
                        if matched_item is not None:
                            icon_filename = matched_item.get("icon_filename", icon_filename)
                    if hasattr(self, "_load_item_icon_surface"):
                        icon_surf = self._load_item_icon_surface(icon_filename, 48)
                    else:
                        icon_surf = None
                    tooltip_lines = None
                    if matched_item is not None and hasattr(self, "_build_loot_tooltip_lines"):
                        tooltip_lines = self._build_loot_tooltip_lines(
                            item_name=eq_name, rarity=eq_rarity,
                            item_stats=matched_item.get("stats", {}),
                            item_slot=matched_item.get("slot", default_slots.get(eq_type, "weapon")),
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
                    loot_label = _FONT_14B.render("Полученный лут:", True, ENDGAME_GOLD_COLOR)
                    self.screen.blit(loot_label, (win_x + (ENDGAME_WINDOW_W - loot_label.get_width()) // 2, row_y))
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
                        if hasattr(self, "_render_loot_slot"):
                            self._render_loot_slot(
                                sx, sy, slot_sz, loot.get("icon_surf"),
                                loot.get("rarity", ""), loot.get("count", 1),
                                loot.get("type", "item"),
                                loot.get("tooltip", ""),
                                loot.get("tooltip_lines"),
                            )
                        else:
                            # Fallback inline rendering (legacy path).
                            slot_rect = pygame.Rect(sx, sy, slot_sz, slot_sz)
                            bg_color = RARITY_SLOT_BG.get(loot["rarity"], (39, 39, 42))
                            pygame.draw.rect(self.screen, bg_color, slot_rect, border_radius=6)
                            border_color = RARITY_RGB.get(loot["rarity"], (82, 82, 91))
                            is_hover = slot_rect.collidepoint(self._mouse_pos)
                            pygame.draw.rect(self.screen, border_color, slot_rect, 3 if is_hover else 2, border_radius=6)
                            if loot.get("icon_surf"):
                                iw, ih = loot["icon_surf"].get_size()
                                self.screen.blit(loot["icon_surf"], (sx + (slot_sz - iw) // 2, sy + (slot_sz - ih) // 2))
                            if loot["count"] > 1:
                                badge = _FONT_14.render(f"x{loot['count']}", True, (255, 255, 255))
                                bw = badge.get_width() + 4
                                bh = badge.get_height() + 2
                                pygame.draw.rect(self.screen, (0, 0, 0), pygame.Rect(sx + slot_sz - bw - 2, sy + slot_sz - bh - 2, bw, bh), border_radius=3)
                                self.screen.blit(badge, (sx + slot_sz - bw, sy + slot_sz - bh - 1))
                            if is_hover and loot.get("tooltip"):
                                tip_surf = _FONT_14.render(loot["tooltip"], True, (255, 255, 255))
                                tw = tip_surf.get_width() + 8
                                th = tip_surf.get_height() + 4
                                tx = sx + slot_sz // 2 - tw // 2
                                ty = sy - th - 4
                                if ty < 0:
                                    ty = sy + slot_sz + 4
                                tip_rect = pygame.Rect(tx, ty, tw, th)
                                pygame.draw.rect(self.screen, (15, 15, 18), tip_rect, border_radius=4)
                                pygame.draw.rect(self.screen, border_color, tip_rect, 1, border_radius=4)
                                self.screen.blit(tip_surf, (tx + 4, ty + 2))

                    grid_rows = (len(loot_items) + max_cols - 1) // max_cols
                    row_y += grid_rows * (slot_sz + slot_gap) + 8
            else:
                defeat_text = "Вы потерпели поражение"
                defeat_surf = font_content.render(defeat_text, True, ENDGAME_LOSE_COLOR)
                defeat_x = win_x + (ENDGAME_WINDOW_W - defeat_surf.get_width()) // 2
                self.screen.blit(defeat_surf, (defeat_x, row_y))
                row_y += row_gap

                xp_text = "Опыт: 0"
                xp_surf = font_dim.render(xp_text, True, TEXT_DIM)
                xp_x = win_x + (ENDGAME_WINDOW_W - xp_surf.get_width()) // 2
                self.screen.blit(xp_surf, (xp_x, row_y))
                row_y += row_gap

                gold_text = "Золото: 0"
                gold_surf = font_dim.render(gold_text, True, TEXT_DIM)
                gold_x = win_x + (ENDGAME_WINDOW_W - gold_surf.get_width()) // 2
                self.screen.blit(gold_surf, (gold_x, row_y))
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
                    error_font = _FONT_20B
                    error_text = "Попытки закончились!"
                    error_surf = error_font.render(error_text, True, (220, 38, 38))
                    error_x = win_x + (ENDGAME_WINDOW_W - error_surf.get_width()) // 2
                    self.screen.blit(error_surf, (error_x, row_y))
                    row_y += row_gap
                    sub_text = "Ждите восстановления (30 мин за попытку)"
                    sub_surf = font_content.render(sub_text, True, TEXT_DIM)
                    sub_x = win_x + (ENDGAME_WINDOW_W - sub_surf.get_width()) // 2
                    self.screen.blit(sub_surf, (sub_x, row_y))
                    row_y += row_gap
                elif rank:
                    # Big rank letter.
                    rank_colors = {
                        "F": (150, 150, 150), "B": (100, 200, 255), "A": (80, 220, 100),
                        "S": (234, 179, 8), "SS": (255, 140, 0), "SSS": (255, 50, 50),
                    }
                    rank_color = rank_colors.get(rank, (234, 179, 8))
                    rank_font = _FONT_48B
                    rank_surf = rank_font.render(rank, True, rank_color)
                    rank_x = win_x + (ENDGAME_WINDOW_W - rank_surf.get_width()) // 2
                    self.screen.blit(rank_surf, (rank_x, row_y))
                    row_y += 50
                    # Damage text.
                    dmg_font = _FONT_16B
                    dmg_text = f"Нанесено урона: {damage}"
                    dmg_surf = dmg_font.render(dmg_text, True, TEXT_WHITE)
                    dmg_x = win_x + (ENDGAME_WINDOW_W - dmg_surf.get_width()) // 2
                    self.screen.blit(dmg_surf, (dmg_x, row_y))
                    row_y += row_gap
                    # Gold reward.
                    gold_text = f"Золото: +{self._endgame_gold_gained}"
                    gold_surf = font_content.render(gold_text, True, ENDGAME_GOLD_COLOR)
                    gold_x = win_x + (ENDGAME_WINDOW_W - gold_surf.get_width()) // 2
                    self.screen.blit(gold_surf, (gold_x, row_y))
                    row_y += row_gap
                    # Stage 77 — item drop (SSS 30%).
                    if item_drop:
                        drop_font = _FONT_16B
                        drop_text = f"Получен предмет: {item_drop}!"
                        drop_surf = drop_font.render(drop_text, True, (255, 200, 50))
                        drop_x = win_x + (ENDGAME_WINDOW_W - drop_surf.get_width()) // 2
                        self.screen.blit(drop_surf, (drop_x, row_y))
                        row_y += row_gap
                    # Stage 72 — boss killed message.
                    if boss_killed:
                        kill_font = _FONT_18B
                        kill_text = "Босс повержен! Новый уровень!"
                        kill_surf = kill_font.render(kill_text, True, (80, 220, 100))
                        kill_x = win_x + (ENDGAME_WINDOW_W - kill_surf.get_width()) // 2
                        self.screen.blit(kill_surf, (kill_x, row_y))
                        row_y += row_gap

            ok_btn_w = ENDGAME_OK_BTN_W
            ok_btn_h = ENDGAME_OK_BTN_H
            ok_btn_x = win_x + (ENDGAME_WINDOW_W - ok_btn_w) // 2
            ok_btn_y = win_y + ENDGAME_WINDOW_H - ok_btn_h - 24
            ok_btn_rect = pygame.Rect(ok_btn_x, ok_btn_y, ok_btn_w, ok_btn_h)
            hover = ok_btn_rect.collidepoint(self._mouse_pos)
            ok_bg = ENDGAME_OK_BTN_BG_HOVER if hover else ENDGAME_OK_BTN_BG
            pygame.draw.rect(self.screen, ok_bg, ok_btn_rect, border_radius=8)
            pygame.draw.rect(self.screen, (255, 255, 255), ok_btn_rect, 2, border_radius=8)

            ok_text = self.font_button.render("ОК", True, ENDGAME_OK_BTN_FG)
            ok_text_rect = ok_text.get_rect(center=ok_btn_rect.center)
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
