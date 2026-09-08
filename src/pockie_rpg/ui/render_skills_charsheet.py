"""SkillsCharSheetRendererMixin — skills modal + char sheet (player + slot 2).

Stage 96 — extracted from `render_map.py` (MapRendererMixin) as a focused
mixin so the parent module shrinks. The class has no `__init__`; it inherits
`self` (screen, fonts, player, _char_sheet_* state, asset_manager, etc.)
from PygameUI.

Stage 178 — ЕДИНОЕ окно характеристик: игрок рендерится ТОЙ ЖЕ компактной
схемой, что и враг (Stage 177): ОЗ/МП → Атака/Скорость → 8 рейтингов в
2 колонки (Проб/Защит, А.Блок/Блок, Хит/Уворот, Крит/Стойк.). Первичные
статы (Сила/Ловкость/Выносливость) и «Крит. урон» из окна убраны у ОБОИХ.
Высота окна едина: CHAR_SHEET_H = 380 (константа CHAR_SHEET_H_ENEMY удалена).

Stage 179 — первичные статы (Сила/Ловкость/Выносливость) в окне ИГРОКА
показываются ТОЛЬКО вне боя (GameState.MAP): 2 строки после ОЗ/МП в
компактном формате «Сила:158  Ловкость:4500». В бою (BATTLE/TEST_BATTLE)
окно игрока = окно врага (единая компактная схема). Высота окна едина:
CHAR_SHEET_H = 420 (+40px под 2 строки первичных статов).

Stage 178 — ТУЛТИПЫ ФОРМУЛ: при наведении на строку РЕЙТИНГА (Проб/Защит/
А.Блок/Блок/Хит/Уворот/Крит/Стойк.) показывается плавающий тултип с
семантикой стата и формулой пересчёта рейтинга → процент (значения
подставляются фактические). Семантика по запросу пользователя:
  * Пробивание — ПРОБИВАНИЕ ЗАЩИТЫ (игнор части снижения урона от защиты);
  * А.Блок — СНИЖЕНИЕ БЛОКА ВРАГА (уменьшает шанс блока противника).
"""
from __future__ import annotations

from typing import Any

import pygame

from pockie_rpg.config import (
    CHAR_SHEET_ACCENT,
    CHAR_SHEET_BG,
    CHAR_SHEET_EDGE_MARGIN,
    CHAR_SHEET_H,
    CHAR_SHEET_W,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SKILLS_GRID_H,
    SKILLS_GRID_W,
    SKILLS_MODAL_BG,
    SKILLS_MODAL_BORDER,
    SKILLS_MODAL_H,
    SKILLS_MODAL_RADIUS,
    SKILLS_MODAL_TITLE_COLOR,
    SKILLS_MODAL_W,
    SKILLS_SLOT_ACTIVE_BG,
    SKILLS_SLOT_INACTIVE_BG,
    SKILLS_SLOT_INACTIVE_BORDER,
    SKILLS_SLOT_LABEL_COLOR,
    SKILLS_TOOLTIP_AREA_H,
    SKILLS_TOOLTIP_DESC_COLOR,
    SKILLS_TOOLTIP_PLACEHOLDER_COLOR,
    SKILLS_TOOLTIP_TITLE_COLOR,
    TEXT_DIM,
    TEXT_WHITE,
)
from pockie_rpg.game.state import ENEMY_MOBS, ROLES
from pockie_rpg.ui.animator import ClickRect


# ---------------------------------------------------------------------------
# Stage 178 — тултипы формул рейтингов.
# key → (полное название, семантика, fn(значение) → строки формулы).
# Формулы — точные реализации из pockie_rpg/combat/formulas.py:
#   * пары Защита/Пробивание — гипербола K=1354 (DEFENSE_BREAK_CONSTANT);
#   * Блок/А.Блок/Крит-шанс/Стойкость-шанс/Хит/Уворот — ШАГ_А = 0.0625%;
#   * Крит-урон/Стойкость-урон — ШАГ_Б = 0.125%; база крит-урона 150%;
#   * попадание: 100 − (Уворот − Хит) × 0.0625, кламп [5, 100];
#   * блок снижает урон до 60% (BLOCK_DAMAGE_MULTIPLIER).
# ---------------------------------------------------------------------------
def _fmt_pct(v: float) -> str:
    return f"{v:.2f}"


STAT_TOOLTIPS: dict[str, dict[str, Any]] = {
    "pierce": {
        "title": "Пробивание",
        "desc": "Пробивание ЗАЩИТЫ: игнорирует часть снижения урона от защиты врага.",
        "formula": lambda v: (
            f"Проб / (Проб + 1354) × 100 = +{_fmt_pct(v / (v + 1354) * 100)}% урона сквозь защиту"
        ),
    },
    "defense": {
        "title": "Защита",
        "desc": "Снижает получаемый урон от атак врага.",
        "formula": lambda v: (
            f"Защ / (Защ + 1354) × 100 = −{_fmt_pct(v / (v + 1354) * 100)}% урона"
        ),
    },
    "antiblock": {
        "title": "А.Блок (Антиблок)",
        "desc": "СНИЖЕНИЕ БЛОКА ВРАГА: уменьшает шанс блока противника.",
        "formula": lambda v: (
            f"Шанс блока врага − {v} × 0.0625% = −{_fmt_pct(v * 0.0625)}% к его блоку"
        ),
    },
    "block": {
        "title": "Блок",
        "desc": "Шанс заблокировать удар врага. Блок снижает урон до 60% (−40%).",
        "formula": lambda v: (
            f"{v} × 0.0625% − А.Блок врага × 0.0625% = шанс {_fmt_pct(v * 0.0625)}%"
        ),
    },
    "hit": {
        "title": "Меткость (Хит)",
        "desc": "Шанс попасть по врагу против его Уворота.",
        "formula": lambda v: (
            f"100 − (Уворот врага − Хит) × 0.0625%; база: {v} × 0.0625 = {_fmt_pct(v * 0.0625)}%"
        ),
    },
    "dodge": {
        "title": "Уворот",
        "desc": "Шанс уклониться: снижает точность атакующего врага.",
        "formula": lambda v: (
            f"Уворот × 0.0625% = {_fmt_pct(v * 0.0625)}% (вычитается из меткости врага)"
        ),
    },
    "crit": {
        "title": "Крит",
        "desc": "Шанс критического удара; база урона крита — 150%.",
        "formula": lambda v: (
            f"шанс: {v} × 0.0625% − Стойк. врага × 0.0625% = {_fmt_pct(v * 0.0625)}%; "
            f"урон: 150% + {v} × 0.125% = +{_fmt_pct(v * 0.125)}%"
        ),
    },
    "tough": {
        "title": "Стойкость",
        "desc": "Снижает шанс крита по вам и урон критов.",
        "formula": lambda v: (
            f"{v} × 0.0625% = −{_fmt_pct(v * 0.0625)}% к шансу крита врага; "
            f"× 0.125% = −{_fmt_pct(v * 0.125)}% к урону его крита"
        ),
    },
}

# Цвет значения рейтингов (общий для игрока и врага — Stage 177).
_RATING_VALUE_COLOR = (200, 200, 210)
_HP_COLOR = (80, 220, 100)
_MP_COLOR = (100, 180, 255)
_ATK_COLOR = (255, 200, 80)

# Тултип формул — геометрия/палитра.
_STAT_TT_W = 264
_STAT_TT_PAD = 10
_STAT_TT_BG = (16, 16, 20, 235)
_STAT_TT_BORDER = (82, 82, 91)
_STAT_TT_TITLE = (234, 179, 8)      # gold — акцент окна
_STAT_TT_DESC = (220, 220, 225)
_STAT_TT_FORMULA = (150, 220, 150)  # зелёный акцент палитры
_STAT_TT_HOVER_BG = (255, 255, 255, 14)

# Строка тултипа: (kind, label, value_str, color, key, numeric_value)
StatLine = tuple[str, tuple[tuple[str, str, tuple[int, int, int], str | None, int], ...]]


class SkillsCharSheetRendererMixin:
    """Renders the MAP skills modal and the sliding char sheet (player + slot 2)."""

    def _render_skills_modal(self) -> None:
        """Render the MAP skills modal window."""
        # Stage 36 — no background dimming (user request).

        win_x = (SCREEN_WIDTH - SKILLS_MODAL_W) // 2
        win_y = (SCREEN_HEIGHT - SKILLS_MODAL_H) // 2
        win_rect = pygame.Rect(win_x, win_y, SKILLS_MODAL_W, SKILLS_MODAL_H)
        # Stage 29 — save modal rect for click-outside-to-close hit-testing.
        self._skills_modal_rect = win_rect
        pygame.draw.rect(self.screen, SKILLS_MODAL_BG, win_rect, border_radius=SKILLS_MODAL_RADIUS)
        pygame.draw.rect(self.screen, SKILLS_MODAL_BORDER, win_rect, 2, border_radius=SKILLS_MODAL_RADIUS)
        pygame.draw.rect(
            self.screen,
            SKILLS_MODAL_BORDER,
            pygame.Rect(win_x, win_y, SKILLS_MODAL_W, 3),
            border_radius=2,
        )

        title_surf = self.font_skills_modal_title.render(
            "Навыки игрока", True, SKILLS_MODAL_TITLE_COLOR
        )
        title_x = win_x + (SKILLS_MODAL_W - title_surf.get_width()) // 2
        title_y = win_y + 16
        self.screen.blit(title_surf, (title_x, title_y))

        tooltip_x = win_x + 16
        tooltip_y = title_y + title_surf.get_height() + 8
        tooltip_w = SKILLS_MODAL_W - 32
        tooltip_h = SKILLS_TOOLTIP_AREA_H
        pygame.draw.line(
            self.screen,
            (60, 60, 68),
            (tooltip_x, tooltip_y + tooltip_h),
            (tooltip_x + tooltip_w, tooltip_y + tooltip_h),
            1,
        )

        grid_x = win_x + (SKILLS_MODAL_W - SKILLS_GRID_W) // 2
        grid_y = tooltip_y + tooltip_h + 12
        _, slots = self._render_skills_grid(grid_x, grid_y)

        hovered_skill_id: int | None = None
        for slot_rect, skill_id in slots:
            if slot_rect.collidepoint(self._mouse_pos):
                hovered_skill_id = skill_id
                break
        for slot_rect, skill_id in slots:
            if slot_rect.collidepoint(self._mouse_pos):
                pygame.draw.rect(
                    self.screen,
                    SKILLS_TOOLTIP_TITLE_COLOR,
                    slot_rect,
                    2,
                    border_radius=4,
                )
                break

        self._render_skill_tooltip(
            hovered_skill_id, tooltip_x, tooltip_y, tooltip_w, tooltip_h
        )

        legend_y = grid_y + SKILLS_GRID_H + 16
        legend_x = win_x + 16
        legend_w = SKILLS_MODAL_W - 32
        sample_size = 14
        pygame.draw.rect(
            self.screen,
            SKILLS_SLOT_ACTIVE_BG,
            pygame.Rect(legend_x, legend_y, sample_size, sample_size),
            border_radius=3,
        )
        pygame.draw.rect(
            self.screen,
            (255, 255, 255),
            pygame.Rect(legend_x, legend_y, sample_size, sample_size),
            1,
            border_radius=3,
        )
        active_label = self.font_skills_modal_close.render(
            " — активен", True, SKILLS_TOOLTIP_DESC_COLOR
        )
        self.screen.blit(active_label, (legend_x + sample_size + 4, legend_y - 1))
        sample2_x = legend_x + sample_size + 4 + active_label.get_width() + 16
        pygame.draw.rect(
            self.screen,
            SKILLS_SLOT_INACTIVE_BG,
            pygame.Rect(sample2_x, legend_y, sample_size, sample_size),
            border_radius=3,
        )
        pygame.draw.rect(
            self.screen,
            SKILLS_SLOT_INACTIVE_BORDER,
            pygame.Rect(sample2_x, legend_y, sample_size, sample_size),
            1,
            border_radius=3,
        )
        inactive_label = self.font_skills_modal_close.render(
            " — выключен", True, SKILLS_TOOLTIP_DESC_COLOR
        )
        self.screen.blit(inactive_label, (sample2_x + sample_size + 4, legend_y - 1))
        help_y = legend_y + sample_size + 6
        help_surf = self.font_skills_modal_close.render(
            "Кликните по навыку, чтобы включить/выключить его",
            True,
            SKILLS_TOOLTIP_PLACEHOLDER_COLOR,
        )
        help_x = legend_x + (legend_w - help_surf.get_width()) // 2
        self.screen.blit(help_surf, (help_x, help_y))

        # Stage 29 — close button removed; click outside the modal closes it.
        click_rects: list[ClickRect] = []
        for slot_rect, skill_id in slots:
            if skill_id is None:
                continue
            def _on_click(_sid: int = skill_id) -> None:
                self._toggle_player_skill(_sid)
            click_rects.append(
                ClickRect(
                    tag=f"toggle_skill_{skill_id}",
                    rect=slot_rect,
                    on_click=_on_click,
                )
            )
        self._click_rects = click_rects
        # Stage 30 — small red "X" close button in the top-right corner.
        self._render_close_x_button(win_x, win_y, SKILLS_MODAL_W, self._close_skills_modal)

    def _render_char_sheet(self, close_cb=None) -> None:
        """Render the character sheet modal sliding in from the screen edge.

        Stage 169 — close_cb задаёт обработчик красного «X» (по умолчанию
        слот 1, self._close_char_sheet); рендер слота 2 (враг) передаёт
        self._close_char_sheet2 ЯВНО — per-frame monkey-patch атрибута удалён.

        Stage 178 — ЕДИНОЕ окно: и игрок, и враг рендерятся одной компактной
        схемой (см. `_render_sheet_lines`); высота едина (CHAR_SHEET_H = 420).
        """

        t = self._char_sheet_anim_t
        eased = 1.0 - (1.0 - t) ** 3

        if self._char_sheet_origin == "left":
            x_off = -CHAR_SHEET_W
            x_in = CHAR_SHEET_EDGE_MARGIN
            win_x = int(x_off + (x_in - x_off) * eased)
        else:
            x_off = SCREEN_WIDTH
            x_in = SCREEN_WIDTH - CHAR_SHEET_W - CHAR_SHEET_EDGE_MARGIN
            win_x = int(x_off + (x_in - x_off) * eased)

        # Stage 59 — keep char sheet between top panel (64px) and bottom bar (56px).
        from pockie_rpg.config import BOTTOM_BAR_HEIGHT, MAP_PANEL_HEIGHT
        available_top = MAP_PANEL_HEIGHT + 4  # 68px
        available_bottom = SCREEN_HEIGHT - BOTTOM_BAR_HEIGHT - 4  # 660px
        available_h = available_bottom - available_top  # 592px
        # Stage 178 — единая высота окна у игрока и врага (было 592 / 380).
        win_y = available_top + (available_h - CHAR_SHEET_H) // 2  # centered
        win_w = CHAR_SHEET_W
        win_h = CHAR_SHEET_H

        # Stage 36 — no background dimming (user request).

        win_rect = pygame.Rect(win_x, win_y, win_w, win_h)
        # Stage 29 — save modal rect for click-outside-to-close hit-testing.
        self._char_sheet_rect = win_rect
        pygame.draw.rect(self.screen, CHAR_SHEET_BG, win_rect, border_radius=12)
        # Stage 55 — remove full border, keep only top yellow strip.
        pygame.draw.rect(
            self.screen,
            CHAR_SHEET_ACCENT,
            pygame.Rect(win_x, win_y, win_w, 4),
            border_radius=2,
        )

        if t < 0.5 or self._char_sheet_closing:
            return

        if self._char_sheet_target == "player":
            role = ROLES.get(self.player.role_id)
            fighter = self._player_fighter
            level = self.player.level
        else:
            enemy = ENEMY_MOBS.get(self.target_mob_id)
            if enemy is None:
                return
            role = ROLES.get(enemy.role_id)
            fighter = self._enemy_fighter
            level = enemy.level

        if role is None:
            return

        # Stage 177 — АВАТАРЫ УДАЛЕНЫ из окна характеристик (у врага и игрока —
        # запрос пользователя). Шапка: имя слева + «Ур.N» справа на одной
        # строке (по схеме), под ней разделитель.
        header_y = win_y + 12
        level_text = f"Ур.{level}"
        level_surf = self.font_charsheet_level.render(level_text, True, CHAR_SHEET_ACCENT)
        name_text = role.name
        # Stage 177 — шрифт 20px вместо 28px: длинные имена («Черный самурай»)
        # влезают в 279px окна рядом с «Ур.N» без обрезки.
        title_surf = self.font_charsheet_name.render(name_text, True, TEXT_WHITE)
        max_name_w = win_w - 32 - level_surf.get_width() - 12
        while title_surf.get_width() > max_name_w and len(name_text) > 2:
            name_text = name_text[:-1]
            title_surf = self.font_charsheet_name.render(name_text + "…", True, TEXT_WHITE)
        self.screen.blit(title_surf, (win_x + 16, header_y))
        level_y = header_y + (title_surf.get_height() - level_surf.get_height()) // 2 + 2
        self.screen.blit(
            level_surf,
            (win_x + win_w - 16 - level_surf.get_width(), level_y),
        )
        header_sep_y = header_y + title_surf.get_height() + 8
        pygame.draw.line(
            self.screen, (80, 80, 85),
            (win_x + 16, header_sep_y), (win_x + win_w - 16, header_sep_y), 1,
        )

        if self._char_sheet_target == "player":
            hp_val = self.player.current_hp
            mp_val = self.player.current_mp
            max_hp_val = self.player.stats.max_hp
            max_mp_val = self.player.stats.max_mp
        elif fighter is not None:
            hp_val = fighter.hp
            mp_val = fighter.mp
            max_hp_val = fighter.max_hp
            max_mp_val = fighter.max_mp
        else:
            hp_val = role.max_hp
            mp_val = role.max_mp
            max_hp_val = role.max_hp
            max_mp_val = role.max_mp

        # Stage 178 — ЕДИНЫЙ блок статов: строим строки для игрока и врага
        # в одном формате, рисует их один рендерер, тултипы формул — общие.
        if self._char_sheet_target == "player":
            lines = self._build_player_sheet_lines(hp_val, mp_val, max_hp_val, max_mp_val)
        else:
            lines = self._build_enemy_sheet_lines(role, hp_val, mp_val, max_hp_val, max_mp_val)

        hovered = self._render_sheet_lines(win_x, win_y, win_w, header_sep_y, lines)

        # Stage 36 — skills section fixed in footer of the window (always visible).
        skills_label_surf = self.font_skills_label.render("Навыки", True, SKILLS_SLOT_LABEL_COLOR)
        skills_label_x = win_x + (win_w - skills_label_surf.get_width()) // 2
        # Fixed at bottom of window, above the X button area.
        skills_label_y = win_y + win_h - SKILLS_GRID_H - 36
        self.screen.blit(skills_label_surf, (skills_label_x, skills_label_y))

        grid_x = win_x + (win_w - SKILLS_GRID_W) // 2
        grid_y = skills_label_y + skills_label_surf.get_height() + 6
        slots: list[tuple[pygame.Rect, int | None]] = []
        _, slots = self._render_skills_grid(grid_x, grid_y)

        hovered_skill_id_cs: int | None = None
        for slot_rect, skill_id in slots:
            if slot_rect.collidepoint(self._mouse_pos):
                hovered_skill_id_cs = skill_id
                pygame.draw.rect(
                    self.screen,
                    SKILLS_TOOLTIP_TITLE_COLOR,
                    slot_rect,
                    2,
                    border_radius=4,
                )
                break
        if hovered_skill_id_cs is not None:
            grid_end_y = grid_y + SKILLS_GRID_H
            tooltip_h_cs = SKILLS_TOOLTIP_AREA_H
            close_btn_top_y = win_y + win_h - 40 - 16
            if grid_end_y + tooltip_h_cs <= close_btn_top_y - 4:
                tt_bg = pygame.Surface((win_w - 32, tooltip_h_cs), pygame.SRCALPHA)
                tt_bg.fill((0, 0, 0, 140))
                self.screen.blit(tt_bg, (win_x + 16, grid_end_y + 4))
                self._render_skill_tooltip(
                    hovered_skill_id_cs,
                    win_x + 16,
                    grid_end_y + 4,
                    win_w - 32,
                    tooltip_h_cs,
                )

        # Stage 29 — close button removed; click outside the modal closes it.
        # Char sheet no longer registers any click rects (skills grid uses
        # its own hover logic; toggling is handled via the skills modal).
        # Stage 30 — small red "X" close button in the top-right corner.
        # Stage 169 — close_cb — явный колбэк (слот 2 передаёт свой),
        # подмена self._close_char_sheet на время рендера удалена.
        self._render_close_x_button(
            win_x, win_y, win_w, close_cb or self._close_char_sheet,
        )

        # Stage 178 — тултип формулы поверх всего (после всех секций окна).
        if hovered is not None:
            key, numeric, row_rect = hovered
            self._render_stat_formula_tooltip(key, numeric, row_rect)

    # ------------------------------------------------------------------
    # Stage 178 — строки статов (единый формат) + тултипы формул.
    # ------------------------------------------------------------------
    def _build_player_sheet_lines(
        self,
        hp_val: int,
        mp_val: int,
        max_hp_val: int,
        max_mp_val: int,
    ) -> list[StatLine]:
        """Строки статов ИГРОКА.

        Stage 179 — первичные статы (Сила/Ловк./Выносл., значения total_* из
        recalc_stats — костюм + шмотки + камни) показываются ТОЛЬКО вне боя
        (GameState.MAP). В бою (BATTLE/TEST_BATTLE) окно остаётся единым
        компактным форматом врага — без первичных статов.

        Формат: ОЗ/МП → [вне боя: первичные статы] → Атака/Скорость →
        8 рейтингов в 2 колонки голыми числами (Проб/Защит, А.Блок/Блок,
        Хит/Уворот, Крит/Стойк.).
        """
        # Stage 24 — force a fresh recalc every frame so the char sheet
        # always reflects the currently equipped gear.
        # Аудит 2026-09 — replaced: full recalc 60×/сек был самой дорогой
        # точкой UI. use_cache=True отдаёт кэш recalc_stats; все мутирующие
        # операции (equip/enchant/gem/баф) пересчитывают форсированно, а при
        # активных бафах кэш отключён на стороне state (бафы тикают по
        # реальному времени). Актуальность окна сохранена.
        stats = self.player.recalc_stats(use_cache=True)

        speed = stats.speed
        speed_str = f"{speed:.2f}" if isinstance(speed, float) else str(speed)

        lines: list[StatLine] = [
            ("line", (
                ("ОЗ :", f"{hp_val} / {max_hp_val}", _HP_COLOR, None, 0),
            )),
            ("line", (
                ("МП :", f"{mp_val} / {max_mp_val}", _MP_COLOR, None, 0),
            )),
        ]

        # Stage 179 — первичные статы ТОЛЬКО вне боя (GameState.MAP). В бою
        # окно игрока выглядит как окно врага (единая компактная схема).
        from pockie_rpg.config import GameState
        if self.state == GameState.MAP:
            lines.append(("sep",))
            # Stage 179 — компактный формат «Сила:158  Ловкость:4500» —
            # без пробела после двоеточия, пары в 2 колонки.
            lines.append(("line", (
                (f"Сила:{stats.total_strength}", "", _RATING_VALUE_COLOR, None, 0),
                (f"Ловкость:{stats.total_agility}", "", _RATING_VALUE_COLOR, None, 0),
            )))
            lines.append(("line", (
                (f"Выносливость:{stats.total_stamina}", "", _RATING_VALUE_COLOR, None, 0),
            )))

        lines.extend([
            ("sep",),
            ("line", (
                ("Атака :", f"{stats.min_atk} - {stats.max_atk}", _ATK_COLOR, None, 0),
            )),
            ("line", (
                ("Скорость :", speed_str, _HP_COLOR, None, 0),
            )),
            ("sep",),
            ("line", (
                ("Проб :", str(stats.pierce_rating_ui), _RATING_VALUE_COLOR,
                 "pierce", stats.pierce_rating_ui),
                ("Защит :", str(stats.defense), _RATING_VALUE_COLOR,
                 "defense", stats.defense),
            )),
            ("line", (
                ("А.Блок :", str(stats.antiblock_rating_ui), _RATING_VALUE_COLOR,
                 "antiblock", stats.antiblock_rating_ui),
                ("Блок :", str(stats.block_rating_ui), _RATING_VALUE_COLOR,
                 "block", stats.block_rating_ui),
            )),
            ("line", (
                ("Хит :", str(stats.hit_rating_ui), _RATING_VALUE_COLOR,
                 "hit", stats.hit_rating_ui),
                ("Уворот :", str(stats.dodge_rating_ui), _RATING_VALUE_COLOR,
                 "dodge", stats.dodge_rating_ui),
            )),
            ("line", (
                ("Крит :", str(stats.crit_rating), _RATING_VALUE_COLOR,
                 "crit", stats.crit_rating),
                ("Стойк. :", str(stats.tough_rating), _RATING_VALUE_COLOR,
                 "tough", stats.tough_rating),
            )),
            ("sep",),
        ])
        return lines
    def _build_enemy_sheet_lines(
        self,
        role,
        hp_val: int,
        mp_val: int,
        max_hp_val: int,
        max_mp_val: int,
    ) -> list[StatLine]:
        """Строки статов ВРАГА (Stage 177 схема; с Stage 178 — общий формат).

        Значения считаются из первичных статов роли через DEFAULT_BMV_PRICE
        (как в Stage 104: у мобов нет костюма/броней; Проб = 0, А.Блок = 0).
        """
        from pockie_rpg.combat.formulas import (
            DEFAULT_BMV_PRICE_AGI,
            DEFAULT_BMV_PRICE_STA,
            DEFAULT_BMV_PRICE_STR,
            calc_block_rating,
            calc_crit_rating,
            calc_dodge_rating,
            calc_hit_rating,
            calc_speed,
            calc_tough_rating,
        )

        speed = calc_speed(role.agility, DEFAULT_BMV_PRICE_AGI, 0)
        # У мобов Проб = 0 и А.Блок = 0 (нет снаряжения — Stage 177).
        pierce = 0
        antiblock = 0
        crit = calc_crit_rating(role.strength, 0)
        hit = calc_hit_rating(role.strength, DEFAULT_BMV_PRICE_STR, 0)
        dodge = calc_dodge_rating(role.agility, DEFAULT_BMV_PRICE_AGI, 0)
        tough = calc_tough_rating(
            role.strength, role.stamina,
            DEFAULT_BMV_PRICE_STR, DEFAULT_BMV_PRICE_STA, 0,
        )
        block = calc_block_rating(role.strength, DEFAULT_BMV_PRICE_STR, 0)
        defense = role.defense

        return [
            ("line", (
                ("ОЗ :", f"{hp_val} / {max_hp_val}", _HP_COLOR, None, 0),
            )),
            ("line", (
                ("МП :", f"{mp_val} / {max_mp_val}", _MP_COLOR, None, 0),
            )),
            ("sep",),
            ("line", (
                ("Атака :", f"{role.min_atk} - {role.max_atk}", _ATK_COLOR, None, 0),
            )),
            ("line", (
                ("Скорость :", f"{speed:.2f}", _HP_COLOR, None, 0),
            )),
            ("sep",),
            ("line", (
                ("Проб :", str(pierce), _RATING_VALUE_COLOR, "pierce", pierce),
                ("Защит :", str(defense), _RATING_VALUE_COLOR, "defense", defense),
            )),
            ("line", (
                ("А.Блок :", str(antiblock), _RATING_VALUE_COLOR,
                 "antiblock", antiblock),
                ("Блок :", str(block), _RATING_VALUE_COLOR, "block", block),
            )),
            ("line", (
                ("Хит :", str(hit), _RATING_VALUE_COLOR, "hit", hit),
                ("Уворот :", str(dodge), _RATING_VALUE_COLOR, "dodge", dodge),
            )),
            ("line", (
                ("Крит :", str(crit), _RATING_VALUE_COLOR, "crit", crit),
                ("Стойк. :", str(tough), _RATING_VALUE_COLOR, "tough", tough),
            )),
            ("sep",),
        ]

    def _render_sheet_lines(
        self,
        win_x: int,
        win_y: int,
        win_w: int,
        start_y: int,
        lines: list[StatLine],
    ) -> tuple[str, int, pygame.Rect] | None:
        """Рисует единый блок статов; возвращает hover-тултип (key, value, rect).

        Схема (Stage 177/178): label слева, value справа; в двухколоночных
        строках вторая пара начинается от середины окна. При наведении на
        пару с key (рейтинг) строка подсвечивается и запоминается для
        тултипа формулы.
        """
        su = self._su
        left_x = su(win_x + 16)
        right_edge = su(win_x + win_w - 16)
        col2_x = su(win_x + 16) + (right_edge - left_x) // 2 + su(8)
        y = su(start_y + 10)
        row_h = su(20)
        gap_after_sep = su(8)

        f_label = self.font_charsheet_label
        f_value = self.font_charsheet_value
        mouse = self._mouse_pos
        hovered: tuple[str, int, pygame.Rect] | None = None

        def _pair_rect(label: str, value: str, lx: int, rx: int, ly: int) -> pygame.Rect:
            # Позиция строки: от начала лейбла до правого края значения.
            lbl_w = f_label.size(label)[0]
            val_w = f_value.size(value)[0]
            val_x = rx - val_w
            x0 = min(lx, val_x)
            x1 = max(lx + lbl_w, rx)
            return pygame.Rect(x0, ly - su(2), x1 - x0, row_h)

        def _draw_pair(
            label: str,
            value: str,
            color,
            key: str | None,
            numeric: int,
            lx: int,
            rx: int,
            ly: int,
        ) -> None:
            nonlocal hovered
            lbl = f_label.render(label, True, TEXT_DIM)
            val = f_value.render(value, True, color)
            self.screen.blit(lbl, (lx, ly))
            self.screen.blit(val, (rx - val.get_width(), ly))
            if key is not None:
                rect = _pair_rect(label, value, lx, rx, ly)
                if rect.collidepoint(mouse):
                    if hovered is None:
                        hovered = (key, numeric, rect)

        for line in lines:
            if line[0] == "sep":
                pygame.draw.line(
                    self.screen, (80, 80, 85), (left_x, y), (right_edge, y), 1,
                )
                y += gap_after_sep
                continue
            entries = line[1]
            if len(entries) == 1:
                label, value, color, key, numeric = entries[0]
                _draw_pair(label, value, color, key, numeric, left_x, right_edge, y)
            else:
                (l1, v1, c1, k1, n1), (l2, v2, c2, k2, n2) = entries
                _draw_pair(
                    l1, v1, c1, k1, n1, left_x, col2_x - su(14), y,
                )
                _draw_pair(l2, v2, c2, k2, n2, col2_x, right_edge, y)
            y += row_h

        # Hover-подсветка строки поверх текста (лёгкая заливка).
        if hovered is not None:
            _key, _num, rect = hovered
            hl = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
            hl.fill(_STAT_TT_HOVER_BG)
            self.screen.blit(hl, rect.topleft)

        return hovered

    def _render_stat_formula_tooltip(
        self,
        key: str,
        numeric: int,
        row_rect: pygame.Rect,
    ) -> None:
        """Stage 178 — плавающий тултип формулы над строкой рейтинга.

        Панель у курсора (с флипом у правого/нижнего края): название стата,
        семантика и формула пересчёта рейтинга → процент с фактическим
        значением. Рисуется ПОСЛЕДНИМ — поверх всего окна.
        """
        info = STAT_TOOLTIPS.get(key)
        if info is None:
            return

        f_label = self.font_charsheet_label
        f_value = self.font_charsheet_value

        title_s = f_value.render(info["title"], True, _STAT_TT_TITLE)
        inner_w = _STAT_TT_W - _STAT_TT_PAD * 2

        desc_lines = self._wrap_text(info["desc"], f_label, inner_w)
        formula_lines = self._wrap_text(info["formula"](numeric), f_label, inner_w)

        line_h = f_label.get_height() + 2
        h = (
            _STAT_TT_PAD + title_s.get_height() + 6
            + len(desc_lines) * line_h + 4
            + 1 + 6  # разделитель
            + len(formula_lines) * line_h
            + _STAT_TT_PAD
        )

        # Позиция: правее/ниже курсора; флип у краёв экрана.
        mx, my = self._mouse_pos
        tx = mx + 18
        if tx + _STAT_TT_W > SCREEN_WIDTH - 8:
            tx = mx - _STAT_TT_W - 18
        ty = min(my + 16, SCREEN_HEIGHT - h - 8)
        tx = max(8, tx)
        ty = max(8, ty)

        panel = pygame.Surface((_STAT_TT_W, h), pygame.SRCALPHA)
        panel.fill(_STAT_TT_BG)
        pygame.draw.rect(
            panel,
            (*_STAT_TT_BORDER, 255),
            pygame.Rect(0, 0, _STAT_TT_W, h),
            1,
            border_radius=6,
        )
        self.screen.blit(panel, (tx, ty))

        cur_y = ty + _STAT_TT_PAD
        self.screen.blit(title_s, (tx + _STAT_TT_PAD, cur_y))
        cur_y += title_s.get_height() + 6
        for text in desc_lines:
            self.screen.blit(
                f_label.render(text, True, _STAT_TT_DESC), (tx + _STAT_TT_PAD, cur_y),
            )
            cur_y += line_h
        cur_y += 2
        pygame.draw.line(
            self.screen, (70, 70, 78),
            (tx + _STAT_TT_PAD, cur_y),
            (tx + _STAT_TT_W - _STAT_TT_PAD, cur_y), 1,
        )
        cur_y += 6
        for text in formula_lines:
            self.screen.blit(
                f_label.render(text, True, _STAT_TT_FORMULA), (tx + _STAT_TT_PAD, cur_y),
            )
            cur_y += line_h

    @staticmethod
    def _wrap_text(text: str, font: pygame.font.Font, max_w: int) -> list[str]:
        """Перенос текста по ширине (пословно)."""
        words = text.split()
        lines: list[str] = []
        cur = ""
        for word in words:
            probe = f"{cur} {word}".strip()
            if font.size(probe)[0] <= max_w or not cur:
                cur = probe
            else:
                lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
        return lines

    def _render_char_sheet2(self) -> None:
        """Stage 63 — render the second char sheet (enemy in battle).

        Swaps the char sheet state variables to slot 2, calls _render_char_sheet
        with a custom close callback, then swaps back.
        """
        # Swap state to slot 2.
        orig_open = self._char_sheet_open
        orig_target = self._char_sheet_target
        orig_origin = self._char_sheet_origin
        orig_anim = self._char_sheet_anim_t
        orig_closing = self._char_sheet_closing

        self._char_sheet_open = self._char_sheet2_open
        self._char_sheet_target = self._char_sheet2_target
        self._char_sheet_origin = self._char_sheet2_origin
        self._char_sheet_anim_t = self._char_sheet2_anim_t
        self._char_sheet_closing = self._char_sheet2_closing

        # Stage 169 — колбэк «X» слота 2 передаётся ЯВНО параметром
        # close_cb (раньше self._close_char_sheet подменялся на время
        # рендера каждый кадр — хрупкий per-frame monkey-patch).

        # Render.
        self._render_char_sheet(close_cb=self._close_char_sheet2)

        # Stage 98 — save the rect for click-outside-to-close hit-testing.
        self._char_sheet2_rect = self._char_sheet_rect

        # Swap back.
        self._char_sheet2_open = self._char_sheet_open
        self._char_sheet2_target = self._char_sheet_target
        self._char_sheet2_origin = self._char_sheet_origin
        self._char_sheet2_anim_t = self._char_sheet_anim_t
        self._char_sheet2_closing = self._char_sheet_closing

        self._char_sheet_open = orig_open
        self._char_sheet_target = orig_target
        self._char_sheet_origin = orig_origin
        self._char_sheet_anim_t = orig_anim
        self._char_sheet_closing = orig_closing
