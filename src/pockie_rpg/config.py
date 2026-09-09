"""Configuration: paths, constants, and enums for Pockie RPG.

This module is the foundation of the layer stack (rule 11):
    ui → game → combat → data → config

It contains ONLY stdlib imports — no pygame, no project modules.
All other layers import from here.
"""
from __future__ import annotations

import sys
from enum import IntEnum
from pathlib import Path

# ---------------------------------------------------------------------------
# VERSION
# ---------------------------------------------------------------------------

# Stage 210 — версия сборки: показывается в F9-фейсинг-оверлее, чтобы на
# экране было видно, какая сборка запущена (репорты со старых архивов).
GAME_VERSION: str = "v207.0"

# ---------------------------------------------------------------------------
# PROJECT PATHS
# ---------------------------------------------------------------------------

# /home/z/pockie_rpg/src/pockie_rpg/config.py → /home/z/pockie_rpg
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
ASSETS_DIR: Path = PROJECT_ROOT / "assets"
BACKGROUNDS_DIR: Path = ASSETS_DIR / "backgrounds"
EXTRACTED_DIR: Path = ASSETS_DIR / "extracted"
AVATAR_DIR: Path = ASSETS_DIR / "icons" / "avatar"
SKILL_ICON_DIR: Path = ASSETS_DIR / "icons" / "skill"
GEM_ICON_DIR: Path = ASSETS_DIR / "icons" / "gems"
FONTS_DIR: Path = PROJECT_ROOT / "fonts"

# ---------------------------------------------------------------------------
# WINDOW / RENDER
# ---------------------------------------------------------------------------

SCREEN_WIDTH: int = 1280
SCREEN_HEIGHT: int = 720
FPS: int = 60
WINDOW_TITLE: str = "Pockie RPG"
# Stage 139 — FULLSCREEN: окно на весь монитор, логический экран ОСТАЁТСЯ
# 1280×720 (pygame FULLSCREEN|SCALED растягивает сам — весь UI не меняется).
# Stage 139.2 — РЕЖИМ ПО УМОЛЧАНИЮ: окно на весь рабочий стол БЕЗ растяжения
# UI. Экранная поверхность = реальный размер монитора (напр. 2560×1440);
# игра рендерится 1:1 (1280×720) в центре, вокруг — блюр-фон. Мышь
# ремапится: координаты окна → UI-координаты (offset центра).
# Stage 139.3 — СТРОГО по требованию пользователя: ВСЯ игра растягивается
# на весь монитор (smoothscale 1280×720 → 2560×1440, ~6мс); элементы,
# которые не впишутся, будем переделывать отдельно. Боевое окно — 60%
# от размера ЭКРАНА (монитора), вокруг блюр.
FRAMELESS_ENABLED: bool = True
# Stage 139.3 — масштаб боевого окна (доля размера монитора).
BATTLE_WINDOW_SCALE: float = 0.60
# Stage 166 — затемнение фона ВОКРУГ боевого окна (запрос пользователя:
# «во время боя сделай затемнение заднего фона, как у карты мира»).
# 165 = ровно тот же чёрный SRCALPHA-слой (0,0,0,165), что рисует
# _render_worldmap_modal_to за окном карты. Блюр НЕ возвращаем — только
# затемнение поверх резкого снапшота локации.
BATTLE_BG_DIM_ALPHA: int = 165
# Аудит 2026-09 — «живой» фон боя: стоп-кадр карты вокруг боевого окна
# обновляется каждые N секунд (NPC/бейджи карты продолжают двигаться,
# фон перестаёт выглядеть фотографией). 0.25 = 4 обновления/сек.
BATTLE_BG_REFRESH_SEC: float = 0.25
# Stage 140 — масштаб модалок/char sheet (1.0 = обычный, 0.5 = вдвое меньше).
# Модалки рендерятся в под-буфер и блитятся уменьшенными — на 2К-растяжении
# (×2) итоговый визуальный размер равен дизайну 720p.
# Stage 141 — per-модалка: инвентарь 1.0 (ячейки 57 → иконки 51×51 1:1),
# остальные 0.5.
# Stage 158 — 0.5 → 1.0 ГЛОБАЛЬНО: shrink-упаковка (draw 720p → shrink 360p →
# upscale монитором) давала двойной ресемплинг = «мыло» на ЛЮБОМ не-нативном
# запуске (оконный режим F11, не-2К монитор, Windows 125% DPI без
# DPI-awareness). При 1.0 модалка рисуется в дизайн-размер 1280×720 и
# растягивается монитором ОДИН раз — как инвентарь (MODAL_SCALE_INVENTORY).
# Целочисленный `su()`/хиттест не затронуты: масштаб применяется к буферу.
MODAL_SCALE: float = 1.0
MODAL_SCALE_INVENTORY: float = 1.0  # Stage 141 — крупная сетка, иконки 51×51 1:1
# Stage 152 — на НАТИВНОМ 2К немигрированные модалки рисуются в дизайн-размере:
# было draw 960 → shrink 480 → upscale 960 (двойной ресемпл = мыло), стало
# draw 960 → upscale 1920 (один проход) — крупнее И чётче. В оконном режиме и
# на не-2К мониторе остаётся MODAL_SCALE (поведение не меняется).
MODAL_SCALE_2K: float = 1.0
# Stage 152 — единая длительность fade-in модалок (обобщение Stage 136 карты).
MODAL_FADE_SEC: float = 0.15
# Stage 152 — вертикальная виньетка top-панели инвентаря (спрайт + слоты):
# было плоское (31,31,34) — теперь лёгкий градиент сверху вниз (глубина без
# новых ассетов). Градиент строится один раз в полосу 1×N и кэшируется.
INV_TOP_PANEL_GRAD_TOP: tuple[int, int, int] = (40, 40, 45)
INV_TOP_PANEL_GRAD_BOTTOM: tuple[int, int, int] = (23, 23, 26)
INV_TOP_PANEL_GRAD_STEPS: int = 32

# --- Stage 150 — Hi-DPI: нативный рендер 2560×1440 (поэкранная миграция) ---
# Дизайн-пространство остаётся 1280×720 (все константы рендеров не меняются),
# но мигрированные экраны рисуются НАТИВНО ×UI_SCALE — без финального блюра.
# Stage 158 — нативный путь активен при ЦЕЛОЧИСЛЕННОМ масштабе монитора
# (2560×1440 → ×2, 3840×2160 → ×3): дробные (2048×1152 = 1.6 при Windows
# 125% без DPI-awareness) держат legacy-путь + MODAL_SCALE=1.0 (один
# растяг — см. выше), т.к. _su()/хиттест требуют целочисленного множителя.
UI_SCALE: float = 2.0


def compute_ui_scale(mon_w: int, mon_h: int) -> float:
    """Stage 158 — целочисленный нативный масштаб монитора (или 1.0).

    (2560,1440) → 2.0, (3840,2160) → 3.0, (2048,1152) → 1.0 (дробный 1.6 —
    нативный путь НЕ включаем), (1280,720) → 1.0 (identity).
    """
    for s in (4.0, 3.0, 2.0):
        if (mon_w, mon_h) == (int(SCREEN_WIDTH * s), int(SCREEN_HEIGHT * s)):
            return s
    return 1.0


def su(v: float) -> int:
    """Дизайн-координата (1280×720) → нативная (×UI_SCALE, округление)."""
    return int(round(v * UI_SCALE))


# Имена мигрированных экранов/модалок. Stage 151 — "inventory"; Stage 152 —
# "forge"; Stage 153 — "map" (БАЗОВЫЙ экран: рисуется прямо на монитор, а
# немигрированные модалки уходят в legacy-слой); Stage 156 — "synth",
# "wardrobe" (единый размер + перетаскивание за шапку) и "titles";
# Stage 157 — "shop". Чек-лист миграции — RULES.md (§Hi-DPI).
# Stage 201 — "battle": нативный Hi-DPI боя (контент окна 60% рисуется
# ×(UI_SCALE×BATTLE_WINDOW_SCALE) в offscreen-поверхность окна; ClickRect'ы
# боя остаются ДИЗАЙН-координатами — мышь ремапится _map_battle_mouse).
NATIVE_MODAL_REGISTRY: set[str] = {
    "inventory", "forge", "map", "synth", "wardrobe", "titles", "shop",
    "battle",
}
# Клавиша переключения fullscreen (pygame key code, F11) — Stage 204: константа
# FULLSCREEN_TOGGLE_KEY удалена (0 импортов; F11-хоткей живёт в pygame_ui).
# Stage 165 — фон боя/модалок БОЛЬШЕ НЕ БЛУРИТСЯ и не затемняется (запрос
# пользователя: «чтобы ничего не менялось и только окно появлялось как Карта
# мира/магазин»). Боевой фон = резкий снапшот сцены входа (_battle_bg_snapshot);
# модалки MAP рисуются поверх живой сцены без подложек. Бывшие константы
# FULLSCREEN_BLUR_DOWN_W/H и BLUR_BACKDROP_* удалены.
# Рамка игрового окна (золотая, 2px).
GAME_WINDOW_BORDER: tuple[int, int, int] = (234, 179, 8)
GAME_WINDOW_BORDER_W: int = 2

# ---------------------------------------------------------------------------
# SPRITE LAYOUT (battle arena)
# ---------------------------------------------------------------------------

# Side-view combat sprite target size.
# Stage 4: reduced by 10% from 100×150 to 90×135 per user request.
BODY_SPRITE_W: int = 130
BODY_SPRITE_H: int = 135

# Sprite anchor positions on the 1280×720 arena.
# Player on the left, enemy on the right (per reference layout).
PLAYER_SPRITE_X: int = 320       # ~25% of 1280
ENEMY_SPRITE_X: int = 960        # ~75% of 1280
# Stage 9 (per user request): sprites lowered by 200px (540 → 740).
# This moves the floor line down so fighters stand closer to the bottom of
# the screen, leaving more room for damage numbers + particles + UI overlays.
# Math: sprite height 135px, base 740 → top at 740-135=605, which is below
# HUD bottom (86px) and above SCREEN_HEIGHT (720), so sprites still fit.
SPRITE_BASE_Y: int = 600         # feet ground line (Stage 9.1: was 740 in Stage 9, 540 before)

# Shadow ellipse under each fighter (per §8.5).
SHADOW_W: int = 80
SHADOW_H: int = 20

# ---------------------------------------------------------------------------
# HUD (top bar)
# ---------------------------------------------------------------------------

HUD_HEIGHT: int = 82          # ~12% of 720
HUD_BG_COLOR: tuple[int, int, int] = (18, 18, 22)       # near-black zinc
HUD_BORDER_COLOR: tuple[int, int, int] = (60, 60, 68)   # zinc-700
HUD_DIVIDER_COLOR: tuple[int, int, int] = (82, 82, 91)  # zinc-600

AVATAR_SIZE: int = 64

# HP / MP bar geometry
HP_BAR_W: int = 420
# Stage 195 — MP-полоска чуть уже HP-полоски (запрос пользователя);
# кончики (центро-обращённые края) HP и MP совпадают по вертикали.
MP_BAR_W: int = 380
HP_BAR_H: int = 18
MP_BAR_H: int = 9                # Stage 4: reduced by 10% (was 10)
BAR_GAP: int = 4
# Stage 134 — mirrored enemy HUD: fixed bar X (invariant: does NOT depend on name width).
ENEMY_BAR_RIGHT_MARGIN: int = 16
BAR_NAME_GAP: int = 12
# Stage 192 — сдвиг HP/MP-полосок (и имён над ними) к центру к эмблеме VS
# (запрос пользователя). Полоски сближаются с ромбом VS: при 70px внутренние
# края полосок в 30px от кончиков ромба (VS_SIZE=28).
HUD_BAR_CENTER_SHIFT: int = 70

# Bar colors (per reference: crimson red HP, royal blue MP, gold accents)
HP_FILL_COLOR: tuple[int, int, int] = (220, 38, 38)        # red-600
HP_BG_COLOR: tuple[int, int, int] = (40, 12, 12)           # dark red bg
MP_FILL_COLOR: tuple[int, int, int] = (37, 99, 235)        # blue-600
MP_BG_COLOR: tuple[int, int, int] = (8, 12, 40)            # dark blue bg
# Stage 193 — градиент HP-полоски (от красного к жёлтому) + белый догоняющий
# сегмент (классика файтингов: недавно потерянное HP гаснет медленнее заливки).
HP_GRADIENT_COLOR_FROM: tuple[int, int, int] = (220, 38, 38)   # красный у основания
HP_GRADIENT_COLOR_TO: tuple[int, int, int] = (250, 204, 21)    # жёлтый на кончике
# Stage 194 — градиент MP-полоски (синий у основания → голубой на кончике;
# тот же механизм _static_surface-кэша, что у HP).
MP_GRADIENT_COLOR_FROM: tuple[int, int, int] = (37, 99, 235)   # синий-600 (основание)
MP_GRADIENT_COLOR_TO: tuple[int, int, int] = (56, 189, 248)    # sky-400 (кончик)
BAR_GHOST_COLOR: tuple[int, int, int] = (244, 244, 245)        # zinc-100
BAR_GHOST_LERP_SPEED: float = 2.5    # скорость догоняющего сегмента (< HP_LERP_SPEED=9)
# Stage 198 — shine-sweep: мягкая белая полоса пробегает по заливке HP/MP
# раз в BAR_SHINE_PERIOD секунд (у зеркального врага — в обратную сторону).
BAR_SHINE_PERIOD: float = 3.0        # секунд между пробегами
BAR_SHINE_BAND_W: int = 46           # ширина бэнда (px)
BAR_SHINE_BAND_ALPHA: int = 55       # пик альфы бэнда

# === Stage 200 — HUD_THEME: цвета HUD-текста/подложек в одном словаре =======
# Единая точка правды для оформления «текстовых зон» боя: подложки имён,
# рамки, цвета текста, fade. Stage 204 — константы-дубликаты (TEXT_NAME и т.п.)
# удалены (0 импортов вне HUD_THEME).
HUD_THEME: dict[str, tuple[int, ...] | float] = {
    # Подложка имени+уровня над полосками (Stage 199)
    "name_plate_bg": (10, 10, 12),        # тёмная плашка (рисуется с alpha)
    "name_plate_alpha": 135,              # видимость плашки (0-255)
    "name_plate_border": (82, 82, 91),    # zinc-500 — лёгкая рамка
    "name_plate_border_alpha": 70,
    "name_plate_fade_sec": 0.4,           # плавное появление с боем
    # Текст поверх подложки
    "name_text_color": (255, 255, 255),   # имя — чисто-белый (ярче zinc-100)
    "level_text_color": (253, 224, 71),   # уровень — yellow-300 (ярче 204)
}
# === Stage 203 — UI_THEME: семантические цвета UI ===========================
# Единая точка правки для часто используемых сырых RGB-троек (~940 по аудиту).
# Миграция постепенная: новые/правимый код использует словарь, старый —
# переписывается при касании. Ключи по палитре zinc/yellow/emerald.
UI_THEME: dict[str, tuple[int, int, int]] = {
    # Gold/Yellow — акценты, рамки, золото/опыт
    "gold": (234, 179, 8),           # yellow-500
    "gold_dark": (161, 98, 7),       # yellow-700
    "yellow_400": (250, 204, 21),
    "yellow_300": (253, 224, 71),
    # Zinc — фоны/рамки/текст
    "zinc_900": (24, 24, 27),
    "zinc_850": (28, 28, 32),
    "zinc_800": (39, 39, 42),
    "zinc_700": (63, 63, 70),
    "zinc_600": (82, 82, 91),
    "zinc_500": (113, 113, 122),
    "zinc_400": (161, 161, 170),
    "zinc_300": (212, 212, 216),
    "zinc_200": (228, 228, 231),
    "zinc_100": (244, 244, 245),
    # Красный — HP/ошибки/X-кнопки
    "red_600": (220, 38, 38),
    "red_500": (239, 68, 68),
    "close_x_bg": (120, 28, 28),     # X-кнопка закрытия (scaling.py)
    "close_x_bg_hover": (200, 40, 40),
    # Зелёный — успех/время/статы
    "emerald_500": (16, 185, 129),
    "emerald_400": (52, 211, 153),
    "green_500": (34, 197, 94),
    "green_soft": (150, 220, 150),   # «осталось ходов/время» в тултипах
    # Синий — MP/вторичные статы
    "blue_600": (37, 99, 235),
    "blue_400": (100, 180, 255),
    # Базовые
    "white": (255, 255, 255),
    "black": (0, 0, 0),
    # Разделители тултипов (линии «─────»)
    "tooltip_sep": (70, 70, 78),
}
# Stage 195 — тултипы иконок статусов в бою: имя + описание (наведение).
STATUS_TOOLTIPS: dict[str, tuple[str, str]] = {
    "freeze": (
        "Заморозка",
        "Боец пропускает ход в ледяной глыбе. Получаемый урон удвоен; "
        "удар по замороженному разбивает глыбу.",
    ),
    "poison": (
        "Яд",
        "В начале каждого хода боец теряет 5% своего максимального HP.",
    ),
    "burn": (
        "Ожог",
        "В начале каждого хода боец теряет фиксированное количество HP.",
    ),
    "thunder_cloud": (
        "Грозовая туча",
        "Удар молнии (60% атаки призвавшего) в начале хода; после тика "
        "с шансом 50% перелетает на противника.",
    ),
    "shield": (
        "Купол",
        "Щит поглощает входящий урон, пока не исчерпает прочность.",
    ),
    "extra_turn": (
        "Шаг молнии",
        "Даёт дополнительный ход сразу после текущего.",
    ),
    "stun": ("Оглушение", "Боец пропускает ход."),
    "paralyze": ("Паралич", "Боец пропускает ход."),
}
VS_GOLD_COLOR: tuple[int, int, int] = (234, 179, 8)        # yellow-500
VS_GOLD_DARK: tuple[int, int, int] = (161, 98, 7)          # yellow-700

# Text colors
TEXT_WHITE: tuple[int, int, int] = (244, 244, 245)        # zinc-100
TEXT_YELLOW: tuple[int, int, int] = (250, 204, 21)        # yellow-400
TEXT_DIM: tuple[int, int, int] = (161, 161, 170)           # zinc-400

# ---------------------------------------------------------------------------
# MAP (Location 1)
# ---------------------------------------------------------------------------

# Enemy card at top-center of MAP screen.
# Stage 9 (per user request): enemy card ×3 smaller (was 360×180, now 120×60).
# The MAP screen now shows 3 enemy cards in a horizontal row (mob_1 real
# enemy + mob_2/mob_3 stubs) instead of a single centered card.
# Stage 154 — карточка переверстана: Stage 140 уменьшил её на 30% (84×77), НЕ
# пересчитав внутреннюю сетку — уровень уходил под кнопку, имена вылезали за
# рамку. Новый размер 110×110 + сетка с зазорами (см. _render_map_enemy_card).
MAP_CARD_W: int = 110  # Stage 154 (было 84 в Stage 140, 120 в Stage 9)
MAP_CARD_H: int = 110  # Stage 154 (было 77)
MAP_CARD_GAP: int = 14
# Stage 154 — слот аватарки моба в ДИЗАЙН-пикселях. 41 дизайн = 82 физических
# на 2К (UI_SCALE=2) — ровно размер исходных портретов userface_n1000*.png
# (82×82), поэтому на 2К они блитятся 1:1 БЕЗ ресемплинга. Мелкие портреты
# (n10002 51×51, n10074 50×50) НЕ апскейлятся — рисуются как есть по центру.
MAP_CARD_AVATAR_SLOT: int = 41
# Stage 9 — stub enemy "Скоро" label color (greyed-out, not clickable).
MAP_CARD_STUB_BG: tuple[int, int, int] = (39, 39, 42)         # zinc-800
MAP_CARD_STUB_TEXT: tuple[int, int, int] = (113, 113, 122)   # zinc-500
MAP_CARD_BG: tuple[int, int, int] = (24, 24, 27)          # zinc-900
MAP_CARD_BORDER: tuple[int, int, int] = (82, 82, 91)     # zinc-600
MAP_CARD_ACCENT: tuple[int, int, int] = (234, 179, 8)    # gold accent

# "В бой" button
# Stage 155 — приглушённая палитра: red-600 (220,38,38) слишком кричал на тёмной
# карточке. Теперь тёмно-кирпичный фон + мягкая красная рамка, ярче только при
# hover (сама кнопка стала акцентом СВОЕЙ карточки, а не всего экрана).
BUTTON_BG: tuple[int, int, int] = (108, 32, 32)           # dark brick
BUTTON_BG_HOVER: tuple[int, int, int] = (168, 46, 46)    # brighter on hover
BUTTON_BORDER: tuple[int, int, int] = (146, 52, 52)      # soft red edge
BUTTON_BORDER_HOVER: tuple[int, int, int] = (226, 96, 96)
BUTTON_TEXT: tuple[int, int, int] = (250, 232, 232)      # warm off-white
BUTTON_TEXT_HOVER: tuple[int, int, int] = (255, 255, 255)

# Combat log (bottom)
LOG_BAR_H: int = 36
LOG_BG_COLOR: tuple[int, int, int] = (0, 0, 0)
LOG_BG_ALPHA: int = 160

# Side banners ("Осмотреть персонажа" — decorative for now)
BANNER_W: int = 24  # Stage 100 — was 36, narrowed for shorter "Осмотреть" text.
BANNER_BG: tuple[int, int, int] = (10, 10, 12)
BANNER_TEXT_COLOR: tuple[int, int, int] = (250, 204, 21)  # yellow-400
# Vertical inset below the HUD so the shortened banner is vertically centered
# in the battle field (top & bottom gaps are equal).
BANNER_TOP_INSET: int = 150
BANNER_H: int = 234  # was full field height (SCREEN_HEIGHT - HUD_HEIGHT = 634), shortened by 200

# ---------------------------------------------------------------------------
# ANIMATION
# ---------------------------------------------------------------------------

IDLE_FPS: int = 8                 # 8 frames per second (per §8.3)
# Stage 204 — BREATHING_AMP/BREATHING_PERIOD удалены (0 использований:
# программное дыхание снято — движение в кадрах SWF, IdleAnimator.get_breathing_offset удалён).

# Per-action frame rates (Stage 4 — extracted from user-provided SWFs).
# Attack faster, death slower, run cycles quickly.
ACTION_FPS: dict[str, int] = {
    "idle": 8,
    "idle_bored": 6,
    "idle_breath_long": 6,
    "attack": 14,
    "run": 10,
    "hit": 10,
    "death": 6,
}

# ---------------------------------------------------------------------------
# ICHIGO ANIMATION MAPPING (Stage 5 — HUMAN-READABLE folder names)
# ---------------------------------------------------------------------------
# ANIMATION NAMING RULE (per user request — Stage 5, mandatory for all future anims):
#
#   Pattern:  <character>_<action>[_<variant>]
#   Examples: ichigo_idle, ichigo_attack, ichigo_run, ichigo_hit, ichigo_death,
#             samurai_idle, samurai_attack (future), naruto_idle (future)
#
#   Why: Original SWF filenames (motion_0_1_52_role.s118.swf) are opaque.
#        Renamed folders make the asset purpose obvious at a glance:
#          ls assets/extracted/  →  ichigo_attack/  ichigo_idle/  samurai_idle/  ...
#
#   Old → New mapping (Stage 5 rename):
#     motion_0_1_1_role    → ichigo_idle
#     motion_0_1_52_role   → ichigo_attack
#     motion_0_1_55_role   → ichigo_run
#     motion_0_1_57_role   → ichigo_death
#     motion_0_1_59_role   → ichigo_idle_bored
#     motion_0_1_60_role   → ichigo_idle_breath_long
#     motion_0_1_64_role   → ichigo_hit
#     motion_10001_1        → samurai_idle
#
# Stage 4 notes preserved:
#   - action=7 (idle_variant) DELETED per user request (лишняя).
#   - action=60 confirmed by user as 3rd idle variant (стоит скучает, достаёт меч зангетсу).

ICHIGO_ACTIONS: dict[int, dict[str, str]] = {
    1:  {"folder": "ichigo/idle",             "name": "idle"},
    52: {"folder": "ichigo/attack",           "name": "attack"},
    55: {"folder": "ichigo/run",              "name": "run"},
    57: {"folder": "ichigo/death",            "name": "death"},
    59: {"folder": "ichigo/idle_bored",       "name": "idle_bored"},
    60: {"folder": "ichigo/idle_breath_long", "name": "idle_breath_long"},
    64: {"folder": "ichigo/hit",              "name": "hit"},
}

# Reverse lookup: semantic name → action_id (for UI code that asks by name).
ICHIGO_ACTION_BY_NAME: dict[str, int] = {
    info["name"]: action_id for action_id, info in ICHIGO_ACTIONS.items()
}

# ---------------------------------------------------------------------------
# SAMURAI (ENEMY) ANIMATION MAPPING (Stage 6 — user-provided SWFs)
# ---------------------------------------------------------------------------
# All enemy (samurai) animations. Stored under `assets/extracted/samurai_<action>/`.
# Per Stage 5 naming rule: <character>_<action>[_<variant>].
#
# Stage 6: 5 new enemy SWFs extracted + VLM-verified.
# Source SWF → folder mapping:
#   motion_10001_4.s117.swf    → samurai_hit         (4 frames — hit reaction)
#   motion_10001_52.s117.swf   → samurai_attack      (12 frames — sword slash)
#   motion_10001_55.s117.swf   → samurai_run          (4 frames — run cycle)
#   motion_10001_57.s117.swf   → samurai_death_fall  (10 frames — knockdown + fall)
#   motion_10001_100.s117.swf  → samurai_death_floor (2 frames — lying on floor)
#
# Note: samurai_death_fall (action=57) and samurai_death_floor (action=100) are
# two phases of death: first the fall animation, then the lying pose.
# Per user: action=57 = "получил урон и упал", action=100 = "лежит на полу".

SAMURAI_ACTIONS: dict[int, dict[str, str]] = {
    1:   {"folder": "samurai/idle",        "name": "idle"},
    4:   {"folder": "samurai/hit",         "name": "hit"},
    52:  {"folder": "samurai/attack",      "name": "attack"},
    55:  {"folder": "samurai/run",         "name": "run"},
    57:  {"folder": "samurai/death_fall",  "name": "death_fall"},
    100: {"folder": "samurai/death_floor", "name": "death_floor"},
}

SAMURAI_ACTION_BY_NAME: dict[str, int] = {
    info["name"]: action_id for action_id, info in SAMURAI_ACTIONS.items()
}

# Blue Swordsman (role_id=10002) — "Синий мечник".
BLUE_SWORDSMAN_ACTIONS: dict[int, dict[str, str]] = {
    1:   {"folder": "blue_swordsman/idle",       "name": "idle"},
    5:   {"folder": "blue_swordsman/attack",     "name": "attack"},
    55:  {"folder": "blue_swordsman/run",        "name": "run"},
    57:  {"folder": "blue_swordsman/death_fall", "name": "death_fall"},
    64:  {"folder": "blue_swordsman/hit",        "name": "hit"},
}

BLUE_SWORDSMAN_ACTION_BY_NAME: dict[str, int] = {
    info["name"]: action_id for action_id, info in BLUE_SWORDSMAN_ACTIONS.items()
}

# Black Samurai (role_id=10004) — "Черный самурай". Separate folder.
# Stage 177 — ПОЛНАЯ РЕ-ЭКСТРАКЦИЯ (запрос пользователя: «у черного самурая
# сломалась анимация — стала полупрозрачная, исходники дам заного»):
#   motion_10004_999.s117.swf → idle        (7 кадров)
#   motion_10004_52.s117.swf  → attack      (13 кадров; раньше action=5, 8 кадров)
#   motion_10004_55.s117.swf  → run         (4 кадра)
#   motion_10004_57.s117.swf  → death_fall  (10 кадров)
#   motion_10004_64.s117.swf  → hit         (8 кадров; раньше 4)
# Экстрактор: JPEXS FFDec 22.0.2, `-export sprite` (рендер кадров DefineSprite
# в ЕДИНОМ холсте каждого экшена — старый экспорт сырых DefineBitsJPEG3 давал
# выцветшие/полупрозрачные кадры). ID действий = суффиксы имён SWF.
BLACK_SAMURAI_ACTIONS: dict[int, dict[str, str]] = {
    999: {"folder": "black_samurai/idle",       "name": "idle"},
    52:  {"folder": "black_samurai/attack",     "name": "attack"},
    55:  {"folder": "black_samurai/run",        "name": "run"},
    57:  {"folder": "black_samurai/death_fall", "name": "death_fall"},
    64:  {"folder": "black_samurai/hit",        "name": "hit"},
}

BLACK_SAMURAI_ACTION_BY_NAME: dict[str, int] = {
    info["name"]: action_id for action_id, info in BLACK_SAMURAI_ACTIONS.items()
}

FLOWER_ACTIONS: dict[int, dict[str, str]] = {
    1:   {"folder": "flower/idle",    "name": "idle"},
    52:  {"folder": "flower/attack",  "name": "attack"},
    64:  {"folder": "flower/hit",     "name": "hit"},
    57:  {"folder": "flower/death",   "name": "death_fall"},
    75:  {"folder": "flower/run",     "name": "run"},
}

FLOWER_ACTION_BY_NAME: dict[str, int] = {
    info["name"]: action_id for action_id, info in FLOWER_ACTIONS.items()
}

ENEMY_ACTION_NAME_MAP: dict[str, str] = {
    "idle": "idle",
    "attack": "attack",
    "run": "run",
    "hit": "hit",
    "death": "death_fall",
}

# ---------------------------------------------------------------------------
# CLOTH14 — КОСТЮМ ИГРОКА (Stage 205 — user-provided SWFs)
# ---------------------------------------------------------------------------
# Первый альтернативный скин игрока: анимации переключаются надетым костюмом
# (OUTFITS_DB["suit_cloth14"]["motion_skin"] = "cloth14" → PLAYER_MOTION_SKINS).
#
# Source SWFs (motion_0_14_<id>_role.s118.swf) → action id = суффикс имени:
#   motion_0_14_998_role.s118.swf  → cloth14/idle    (8 кадров)
#   motion_0_14_52_role.s118.swf   → cloth14/attack  (11 кадров)
#   motion_0_14_55_role.s118.swf   → cloth14/run     (4 кадра)
#   motion_0_14_63_role.s118.swf   → cloth14/hit     (7 кадров)
#   motion_0_14_100_role.s118.swf  → cloth14/death   (2 кадра)
#
# Экстракция: JPEXS FFDec 22.0.2 `-export sprite` (кадры в единых баундах
# экшена, прозрачный фон, hold-дубли таймлайна SWF сохранены — конвенция
# ichigo/black_samurai). Отличие от ichigo: кадры ПРЕДВАРИТЕЛЬНО ОТЗЕРКАЛЕНЫ
# (исходник смотрит ВЛЕВО, костюм игрока должен смотреть ВПРАВО) — поэтому
# INTRINSIC_FACING = RIGHT, runtime-флип не нужен (needs_flip_for_player=False).

CLOTH14_ACTIONS: dict[int, dict[str, str]] = {
    998: {"folder": "cloth14/idle",   "name": "idle"},
    52:  {"folder": "cloth14/attack", "name": "attack"},
    55:  {"folder": "cloth14/run",    "name": "run"},
    63:  {"folder": "cloth14/hit",    "name": "hit"},
    100: {"folder": "cloth14/death",  "name": "death"},
}

CLOTH14_ACTION_BY_NAME: dict[str, int] = {
    info["name"]: action_id for action_id, info in CLOTH14_ACTIONS.items()
}

# Stage 205 — сеты анимаций игрока (action name → motion folder).
# Ключ = motion_skin из OUTFITS_DB; отсутствие ключа в надетом костюме
# (или skin_actions=None у аниматора) = классический Ичиго.
PLAYER_MOTION_SKINS: dict[str, dict[str, str]] = {
    "ichigo":  {info["name"]: info["folder"] for info in ICHIGO_ACTIONS.values()},
    "cloth14": {info["name"]: info["folder"] for info in CLOTH14_ACTIONS.values()},
}

# ---------------------------------------------------------------------------
# MOTION FOLDER MAPPING (per §10.9)
# ---------------------------------------------------------------------------

# Enemy mobs → idle motion folder.
# Stage 46 — all 12 mobs mapped by role_id:
#   role 10001 (samurai)   → samurai_idle
#   role 10002 (samurai_2) → samurai2_idle
#   role 10004 (samurai_3) → samurai2_idle
MOB_TO_MOTION: dict[str, str] = {
    "mob_1": "samurai/idle",
    "mob_2": "blue_swordsman/idle",
    "mob_3": "black_samurai/idle",
    # Location 2
    "mob_4": "samurai/idle",
    "mob_5": "blue_swordsman/idle",
    "mob_6": "black_samurai/idle",
    # Location 3
    "mob_7": "samurai/idle",
    "mob_8": "blue_swordsman/idle",
    "mob_9": "black_samurai/idle",
    # Location 4
    "mob_10": "samurai/idle",
    "mob_11": "blue_swordsman/idle",
    "mob_12": "black_samurai/idle",
    # Flower mob
    "flower_1": "flower/idle",
}

# Backgrounds: BATTLE state (Stage 204 — MAP_BACKGROUND удалён: фон локации
# рендерится через ассеты карты, константа не читалась).
BATTLE_BACKGROUND: str = "fightbg_2302.jpg"   # Location 2

# ---------------------------------------------------------------------------
# ENUMS
# ---------------------------------------------------------------------------


class GameState(IntEnum):
    """Finite State Machine states for the UI.

    Stage 15 (NEW): TEST_BATTLE = 3 — a debug/test mode where the player can
    manually trigger any skill by clicking buttons at the screen center.
    No countdown, no autobattle, no endgame, no speed buttons. The enemy is
    immortal (HP refills to max if it would drop to 0) and the player has
    infinite MP (refilled to max every frame). Used to visually verify each
    skill's animation + status effects without having to wait for the
    trigger_chance roll in a real battle.
    """

    MAP = 1          # Location 1: world map with enemy card
    BATTLE = 2       # Location 2: combat arena with 2 fighters
    TEST_BATTLE = 3  # Stage 15 — test mode for skill debugging


class MapLocation(IntEnum):
    """Stage 45 — multiple locations with level-gated access.

    CITY is the safe hub. LOC1-4 are combat zones with increasing difficulty.
    """

    CITY = 0    # safe city (hub)
    LOC1 = 1    # Location 1: L1/L5/L10 mobs (samurai)
    LOC2 = 2    # Location 2: L10/L15/L20 mobs (stub)
    LOC3 = 3    # Location 3: L20/L25/L30 mobs (stub)
    LOC4 = 4    # Location 4: L30/L35/L40 mobs (stub)
    LAS_NOCHES = 5  # Stage 91 — Las Noches (Tower hub with guardian NPC)


class BattleMode(IntEnum):
    """Stage 134 — endgame-flow selector (was string field _battle_mode).

    NORMAL: standard endgame rewards window. TOWER: _finish_tower_battle.
    WORLD_BOSS: instant flow from _enter_world_boss_fight. SLOT_GAUNTLET:
    slot-machine 3-round chain (_finish_gauntlet_round).
    """

    NORMAL = 1
    TOWER = 2
    WORLD_BOSS = 3
    SLOT_GAUNTLET = 4


# Stage 45 — location definitions.
LOCATIONS_DB: dict[int, dict] = {
    1: {
        "name": "Локация 1",
        "bg": "fightbg_2302.jpg",
        "mobs": ["mob_1", "mob_2", "mob_3"],  # L1, L5, L10
    },
    2: {
        "name": "Локация 2",
        "bg": "fightbg_2502.jpg",
        "mobs": ["flower_1", "mob_4", "mob_6"],  # L10 flower, L10 samurai, L20 samurai3
    },
    3: {
        "name": "Локация 3",
        "bg": "fightbg_2501.jpg",
        "mobs": ["mob_7", "mob_8", "mob_9"],  # L20, L25, L30
    },
    4: {
        "name": "Локация 4",
        "bg": "fightbg_2503.jpg",
        "mobs": ["mob_10", "mob_11", "mob_12"],  # L30, L35, L40
    },
}


# Stage 133 — slot machine «3 лица → бой» (Локация 1 only).
# TODO balance: pool size, faces count and cooldown are placeholders.
SLOT_MACHINE_POOL: tuple[str, ...] = ("mob_1", "mob_2", "mob_3", "flower_1")
SLOT_MACHINE_FACES: int = 3
SLOT_MACHINE_COOLDOWN_SEC: int = 60
# Stage 134 — slot machine v2.
# TODO balance: spin timing + perfect-series bonus are placeholders.
SLOT_MACHINE_SPIN_SEC: float = 1.2
SLOT_MACHINE_SPIN_STOP_STAGGER: float = 0.4
SLOT_MACHINE_SPIN_TICK: float = 0.08
SLOT_MACHINE_SPIN_SLOWDOWN_SEC: float = 0.3
SLOT_MACHINE_PERFECT_GOLD_MULT: float = 1.5
# Stage 134 — map card geometry (top-left of location zone, below HUD).
SLOT_CARD_W: int = 120
SLOT_CARD_H: int = 72
SLOT_CARD_X: int = 16
SLOT_CARD_Y: int = 100
SLOT_CARD_REEL_W: int = 28
SLOT_CARD_REEL_H: int = 32
SLOT_QUEUE_FACE_SIZE: int = 44
SLOT_QUEUE_GAP: int = 6


# ---------------------------------------------------------------------------
# Stage 135 — World map modal «Sakura of mainland» (35 зон, 26 маркеров).
# Ассеты: assets/worldmap/ (background.jpg 768×426, overlay.png, buttons/).
# Данные: data/worldmap_db.py (WORLD_ZONES / ROUTE_MARKERS из config.json).
# ---------------------------------------------------------------------------

# Панель карты: оригинальный размер ассетов 768×426 (SCALE=1.0), по центру 1280×720.
WORLDMAP_SCALE: float = 1.0
WORLDMAP_PANEL_W: int = int(768 * WORLDMAP_SCALE)   # 768
WORLDMAP_PANEL_H: int = int(426 * WORLDMAP_SCALE)   # 426
WORLDMAP_PANEL_X: int = (SCREEN_WIDTH - WORLDMAP_PANEL_W) // 2   # 256
WORLDMAP_PANEL_Y: int = (SCREEN_HEIGHT - WORLDMAP_PANEL_H) // 2  # 147
# Кнопка «Карта мира» в top-панели карты (на месте дропдауна «Локации ▾»).
WORLDMAP_BTN_W: int = 110
WORLDMAP_BTN_H: int = 36
# Красная плашка «Зона закрыта» после клика по неактивной зоне (сек).
WORLDMAP_LOCKED_TOAST_SEC: float = 1.5
# Тултип: смещение вправо от курсора (флип влево у правого края).
WORLDMAP_TOOLTIP_OFFSET_X: int = 18

# Маркеры ВСЕГДА фиолетовые (fuchsia-500), цвет НЕ зависит от уровня игрока.
WORLDMAP_MARKER_COLOR: tuple[int, int, int] = (217, 70, 239)
# Альфа свечения обычных маркеров — КОНСТАНТА (0.45×255); при hover НЕ меняется.
WORLDMAP_MARKER_GLOW_ALPHA: int = 115
# Подсветка hovered-зоны: золотое ядро (README §8).
WORLDMAP_HILIGHT_WHITE: tuple[int, int, int] = (255, 252, 235)
WORLDMAP_HILIGHT_CORE: tuple[int, int, int] = (255, 254, 245)
WORLDMAP_HILIGHT_MID: tuple[int, int, int] = (254, 240, 138)
WORLDMAP_HILIGHT_EDGE: tuple[int, int, int] = (253, 224, 71)
# Пульс: обычный t/320 + фаза i*0.7; подсветка t/140 + фаза i*1.3 (мс).
WORLDMAP_PULSE_MS: int = 320
WORLDMAP_PULSE_PHASE: float = 0.7
WORLDMAP_HILIGHT_PULSE_MS: int = 140
WORLDMAP_HILIGHT_PHASE: float = 1.3

# 🔒-бейдж неактивной зоны (README §5 слой 5).
WORLDMAP_LOCK_BG: tuple[int, int, int] = (24, 24, 27)
WORLDMAP_LOCK_BORDER: tuple[int, int, int] = (161, 161, 170)
WORLDMAP_LOCK_BODY: tuple[int, int, int] = (212, 212, 216)
# Тултип (README §12): тёмная плашка; у деревень золотая рамка.
WORLDMAP_TIP_BG: tuple[int, int, int] = (9, 9, 11)
WORLDMAP_TIP_BORDER: tuple[int, int, int] = (82, 82, 91)
WORLDMAP_TIP_VILLAGE_BORDER: tuple[int, int, int] = (251, 191, 36)
WORLDMAP_TIP_TEXT: tuple[int, int, int] = (250, 250, 250)
WORLDMAP_TIP_SUB_VILLAGE: tuple[int, int, int] = (252, 211, 77)
WORLDMAP_TIP_SUB_LOCATION: tuple[int, int, int] = (110, 231, 183)
WORLDMAP_TIP_SUB_LOCKED: tuple[int, int, int] = (161, 161, 170)

# Обесцвечивание неактивных зон (README §6): V = gray * MUL + FLOOR.
WORLDMAP_DESAT_MUL: float = 0.5
WORLDMAP_DESAT_FLOOR: int = 8

# Stage 136 — метка игрока на текущей зоне (emerald-пульс, слой 6).
WORLDMAP_PLAYER_COLOR: tuple[int, int, int] = (52, 211, 153)   # emerald-400
WORLDMAP_PLAYER_CORE_COLOR: tuple[int, int, int] = (209, 250, 229)
WORLDMAP_PLAYER_PULSE_MS: int = 380
WORLDMAP_PLAYER_PULSE_PHASE: float = 0.0
WORLDMAP_PLAYER_GLOW_ALPHA: int = 140

# Stage 136 — реверс ZONE_LOCATION_MAP: MapLocation.value → референсная зона
# (для метки игрока: CITY → Деревня Огня 12; LOC1-4 → первая зона тира).
WORLDMAP_LOCATION_ZONE: dict[int, int] = {
    0: 12,    # CITY → стартовая деревня
    1: 7,     # LOC1
    2: 102,   # LOC2
    3: 52,    # LOC3
    4: 127,   # LOC4
}

# Stage 135 — маппинг 27 не-деревень на MapLocation.LOC1-4 по unlock_level
# (деревни → 0 = CITY-хаб; на карте их 8, все unlock_level=1).
# Таблица соответствия (zone_id: unlock_level → LOC):
#   unlock 1-11   → LOC1:  7:6, 92:6, 147:6, 17:11, 22:11, 97:11
#   unlock 16-21  → LOC2:  102:16, 152:16, 157:16, 47:21, 57:21, 142:21
#   unlock 26-31  → LOC3:  52:26, 117:26, 122:26, 132:31, 137:31, 162:31
#   unlock 36-50  → LOC4:  127:36, 167:36, 177:36, 37:41, 67:41, 77:41, 32:46, 42:46, 82:46
#   деревни → CITY(0): 12, 27, 62, 72, 87, 107, 112, 172 (unlock 1)
# Единственный источник правды по уровню — data/worldmap_db.WORLD_ZONES.
ZONE_LOCATION_MAP: dict[int, int] = {
    7: 1, 92: 1, 147: 1,        # 6–11
    17: 1, 22: 1, 97: 1,        # 11–16
    102: 2, 152: 2, 157: 2,     # 16–21
    47: 2, 57: 2, 142: 2,       # 21–26
    52: 3, 117: 3, 122: 3,      # 26–31
    132: 3, 137: 3, 162: 3,     # 31–36
    127: 4, 167: 4, 177: 4,     # 36–41
    37: 4, 67: 4, 77: 4,        # 41–46
    32: 4, 42: 4, 82: 4,        # 46–50
}


# Stage 46 — minimap rect slightly reduced (was 140 → 120) to make room
# for the location dropdown selector to its left.
MINIMAP_UI_RECT = (1146, 3, 110, 46)  # x, y, w, h — Stage 161: под панель 52px
MINIMAP_CITY_BG = "city_bg.jpg"  # filename under assets/backgrounds/
# Stage 91/92 — Las Noches (Tower hub) background.
# Stage 92 — moved to las_noches/images/Enter.jpg per user request.
LAS_NOCHES_BG = "las_noches/images/Enter.jpg"  # path under assets/backgrounds/
LAS_NOCHES_GUARDIAN_FOLDER = "las_noches_guardian/idle"
LAS_NOCHES_GUARDIAN_FILENAME = "las_noches.png"  # Stage 92 — user-provided sprite
LAS_NOCHES_GUARDIAN_SCALE: float = 0.65  # Stage 93 — user-requested scale.
# Stage 92 — Tower battle backgrounds by floor range.
# Files under assets/backgrounds/las_noches/images/.
TOWER_BATTLE_BG_BY_FLOOR_RANGE: tuple[tuple[int, int, str], ...] = (
    (1, 30, "las_noches/images/1-30.jpg"),
    (31, 60, "las_noches/images/30-60.jpg"),
    (61, 80, "las_noches/images/60-80.jpg"),
    (81, 100, "las_noches/images/80-100.jpg"),
)


# ---------------------------------------------------------------------------
# Stage 172 — сюжетные NPC на карте + окно навигации по заданиям.
# Данные: data/npcs_db.py (NPCS) + data/quests_db.py (STORY_QUESTS).
# Ассеты: assets/npcs/ (аватарки), assets/extracted/npc_toad_idle/ (кадры жабы).
# ---------------------------------------------------------------------------
NPC_AVATAR_DIR_NAME: str = "npcs"
# Цвета индикаторов над головой NPC («!» — квест можно взять, «?» — готов к сдаче).
NPC_EXCLAMATION_COLOR: tuple[int, int, int] = (250, 204, 21)   # amber-400
NPC_READY_COLOR: tuple[int, int, int] = (52, 211, 153)         # emerald-400
NPC_INDICATOR_SIZE: int = 22          # размер бейджа (дизайн-пиксели)
NPC_INDICATOR_BOB_AMP: float = 4.0    # амплитуда покачивания (px)
NPC_INDICATOR_BOB_SPEED: float = 2.6  # циклы покачивания в секунду
NPC_INDICATOR_LIFT: int = 14          # подъём над головой спрайта (px)
NPC_NAME_PLATE_TEXT: tuple[int, int, int] = (240, 240, 244)
NPC_NAME_PLATE_BG: tuple[int, int, int, int] = (9, 9, 11, 190)
NPC_HOVER_BUBBLE_BG: tuple[int, int, int] = (30, 30, 35)
NPC_HOVER_BUBBLE_BORDER: tuple[int, int, int] = (52, 211, 153)
# Stage 173 — стрелка-подсветка над целью после «Перейти» (NpcDef над головой
# или над рядом карточек мобов для kill_mobs-квестов).
QUEST_ARROW_SEC: float = 5.0            # сколько секунд горит стрелка
QUEST_ARROW_COLOR: tuple[int, int, int] = (250, 204, 21)   # amber-400
QUEST_ARROW_OUTLINE: tuple[int, int, int] = (20, 20, 24)
QUEST_ARROW_W: int = 22                 # ширина стрелки (дизайн-пиксели)
QUEST_ARROW_H: int = 18                 # высота стрелки
QUEST_ARROW_BOB_AMP: float = 6.0        # амплитуда покачивания вниз-вверх (px)
QUEST_ARROW_BOB_SPEED: float = 2.2      # циклы покачивания в секунду
# Трекер заданий (HUD, прижат к правому нижнему углу над нижним баром — Stage 173).
QUEST_TRACKER_W: int = 264
QUEST_TRACKER_X: int = SCREEN_WIDTH - QUEST_TRACKER_W - 16   # 1000
# Stage 173 — трекер прижат к ПРАВОМУ НИЖНЕМУ углу: низ панели на
# BOTTOM_BAR_HEIGHT(56)+10=66 дизайн-пикселей выше низа экрана
# (верх панели вычисляется от высоты контента: см. QuestRendererMixin).
QUEST_TRACKER_BOTTOM_MARGIN: int = 66
QUEST_TRACKER_ROW_H: int = 52
QUEST_TRACKER_MAX_ROWS: int = 4
QUEST_TRACKER_TAB_H: int = 30
QUEST_TRACKER_HEADER_H: int = 30
# Stage 174 — плавающая кнопка 44×44 удалена: сворачивание — иконка
# «scroll.png» в нижнем UI-баре (слоты иконок см. _render_bottom_bar).
QUEST_TRACKER_BG: tuple[int, int, int, int] = (24, 24, 27, 226)
QUEST_TRACKER_BORDER: tuple[int, int, int] = (63, 63, 70)
QUEST_TRACKER_ACCENT: tuple[int, int, int] = (234, 179, 8)
QUEST_TRACKER_TAB_ACTIVE_BG: tuple[int, int, int] = (63, 63, 70)
QUEST_TRACKER_TAB_IDLE_BG: tuple[int, int, int] = (39, 39, 42)
QUEST_TRACKER_MAX_NAME_CHARS: int = 24
# Диалог NPC (Stage 174 — единое окно для ВСЕХ реплик NPC: offer/turn_in/
# reminder/flavor, тот же стиль у диалогов стража Лас Ночеса). Высота
# ДИНАМИЧЕСКАЯ — окно сжимается, если текста мало (MIN_H..MAX_H).
QUEST_DIALOG_W: int = 480
QUEST_DIALOG_PORTRAIT_SIZE: int = 64
QUEST_DIALOG_HEADER_H: int = 80         # шапка: аватарка + имя + роль
QUEST_DIALOG_MIN_H: int = 250
QUEST_DIALOG_MAX_H: int = 430
QUEST_DIALOG_BTN_H: int = 28            # маленькие кнопки (было 40)
QUEST_DIALOG_ACCENT: tuple[int, int, int] = (234, 179, 8)
QUEST_DIALOG_FLAVOR_ACCENT: tuple[int, int, int] = (52, 211, 153)
QUEST_DIALOG_FEEDBACK_SEC: float = 3.5   # длительность тоста о награде

# --- Stage 174 — карточки города (Арена/Магазин/Башня) как текстовые плашки.
# Иконки НЕ видны постоянно: плавно проявляются ТОЛЬКО при hover по плашке.
# Клик по плашке открывает окно (арена/магазин/башня).
CITY_CARD_ICON_SIZE: int = 64
CITY_CARD_LABEL_W: int = 136
CITY_CARD_LABEL_H: int = 38
CITY_CARD_HOVER_SEC: float = 0.22       # время плавного появления иконки
CITY_CARD_ICON_GAP: int = 10            # зазор между иконкой и плашкой
# Центры плашек (дизайн-координаты 1280×720) — слегка хаотичное распределение
# в центральной зоне. Проверено на пересечения: «Город» (y≈132..152),
# метка Старейшины (центр 640,560), трекер (x≥1000), нижний бар (y≥664),
# зоны hover-иконок (верх плашки − ICON_SIZE − GAP) друг с другом.
CITY_CARD_POSITIONS: dict[str, tuple[int, int]] = {
    "enter_arena": (440, 270),   # Арена
    "open_shop": (780, 235),     # Магазин
    "open_tower": (625, 405),    # Башня
}
CITY_CARD_LABEL_TEXT: tuple[int, int, int] = (255, 228, 222)
CITY_CARD_LABEL_BG: tuple[int, int, int, int] = (9, 9, 11, 208)
CITY_CARD_LABEL_BORDER: tuple[int, int, int] = (200, 80, 60)
CITY_CARD_LABEL_BORDER_HOVER: tuple[int, int, int] = (248, 113, 82)


def get_tower_battle_bg(floor: int) -> str:
    """Stage 92 — return the battle background path for the given Tower floor.

    Picks the background by floor range (1-30, 31-60, 61-80, 81-100).
    Falls back to the first range if floor is out of bounds.
    """
    for lo, hi, path in TOWER_BATTLE_BG_BY_FLOOR_RANGE:
        if lo <= floor <= hi:
            return path
    return TOWER_BATTLE_BG_BY_FLOOR_RANGE[0][2]


class SpriteFacing(IntEnum):
    """Intrinsic sprite facing direction (before flip correction)."""

    LEFT = 1
    RIGHT = 2


# Hardcoded facing map (Stage 6 — USER-VERIFIED + alpha-mass + VLM cross-checked).
#
# IMPORTANT LESSON (Stage 4): Both VLM and alpha-mass heuristic are unreliable
# for Ichigo because his Zangetsu sword is large and shifts alpha-mass to RIGHT
# even though the character visually faces LEFT (user-confirmed).
#
# SOLUTION: User is the single source of truth for sprite facing.
# - All Ichigo animations are marked LEFT (→ flip=True for player to face RIGHT).
# - All enemy (samurai) action animations are marked LEFT (→ flip=False, already faces LEFT).
# - Death animations (death_fall, death_floor) are horizontal poses — facing is
#   ambiguous, but marked LEFT for consistency (no flip needed).
#
# Stage 6: 5 new enemy animations added (samurai_attack/run/hit/death_fall/death_floor).
# All action animations VLM-verified as LEFT-facing. Death animations are horizontal
# (alpha-mass shows RIGHT due to body orientation, but visually neutral).
#
# This is the SINGLE SOURCE OF TRUTH for intrinsic sprite facing.
INTRINSIC_FACING: dict[str, SpriteFacing] = {
    # Ichigo (all LEFT-facing).
    "ichigo/idle":             SpriteFacing.LEFT,
    "ichigo/attack":           SpriteFacing.LEFT,
    "ichigo/run":              SpriteFacing.LEFT,
    "ichigo/death":            SpriteFacing.LEFT,
    "ichigo/idle_bored":       SpriteFacing.LEFT,
    "ichigo/idle_breath_long": SpriteFacing.LEFT,
    "ichigo/hit":              SpriteFacing.LEFT,
    # Samurai (all LEFT-facing).
    "samurai/idle":            SpriteFacing.LEFT,
    "samurai/attack":          SpriteFacing.LEFT,
    "samurai/run":             SpriteFacing.LEFT,
    "samurai/hit":             SpriteFacing.LEFT,
    "samurai/death_fall":      SpriteFacing.LEFT,
    "samurai/death_floor":     SpriteFacing.LEFT,
    # Blue Swordsman (all LEFT-facing).
    "blue_swordsman/idle":       SpriteFacing.LEFT,
    "blue_swordsman/attack":     SpriteFacing.LEFT,
    "blue_swordsman/run":        SpriteFacing.LEFT,
    "blue_swordsman/hit":        SpriteFacing.LEFT,
    "blue_swordsman/death_fall": SpriteFacing.LEFT,
    # Black Samurai (all LEFT-facing).
    "black_samurai/idle":       SpriteFacing.LEFT,
    "black_samurai/attack":     SpriteFacing.LEFT,
    "black_samurai/run":        SpriteFacing.LEFT,
    "black_samurai/hit":        SpriteFacing.LEFT,
    "black_samurai/death_fall": SpriteFacing.LEFT,
    # Flower (all LEFT-facing).
    "flower/idle":             SpriteFacing.LEFT,
    "flower/attack":           SpriteFacing.LEFT,
    "flower/hit":              SpriteFacing.LEFT,
    "flower/run":              SpriteFacing.LEFT,
    "flower/death":            SpriteFacing.LEFT,
    # Cloth14 costume (Stage 205 — pre-flipped frames, face RIGHT natively;
    # пользователь: «анимация повёрнута налево, а нужно направо — это игрок»).
    "cloth14/idle":            SpriteFacing.RIGHT,
    "cloth14/attack":          SpriteFacing.RIGHT,
    "cloth14/run":             SpriteFacing.RIGHT,
    "cloth14/hit":             SpriteFacing.RIGHT,
    "cloth14/death":           SpriteFacing.RIGHT,
    # Las Noches Guardian (Stage 91 — static NPC, faces RIGHT toward player).
    "las_noches_guardian/idle": SpriteFacing.RIGHT,
}

# ---------------------------------------------------------------------------
# HARD RULES (Stage 4 — per user request)
# ---------------------------------------------------------------------------
# ALL enemies in BATTLE state MUST face LEFT (toward the player on left side).
# Player is ALWAYS positioned on the left side of the arena and faces RIGHT.
# These rules are enforced in AssetManager.needs_flip_for_enemy / needs_flip_for_player.
# A mob's intrinsic facing determines whether a flip is needed:
#   intrinsic RIGHT → flip=True  (after flip: faces LEFT ✓)
#   intrinsic LEFT  → flip=False (already faces LEFT ✓)
# Stage 204 — константы ENEMY_MUST_FACE_LEFT/PLAYER_MUST_FACE_RIGHT удалены
# (0 чтений: правило зашито в needs_flip_for_enemy/player).


# ---------------------------------------------------------------------------
# SOUND (disabled per user — §13.2 Q9 answered "muted for dev")
# ---------------------------------------------------------------------------

SOUND_ENABLED: bool = False
# Stage 204 — BGM_VOLUME/SFX_VOLUME удалены (звук не реализован, 0 чтений).

# ---------------------------------------------------------------------------
# BATTLE INTRO COUNTDOWN (Stage 4 — per user request)
# ---------------------------------------------------------------------------
# When entering BATTLE state, show 3-2-1-FIGHT countdown in big text at center.

COUNTDOWN_PHASES: list[tuple[str, float]] = [
    ("3", 1.0),       # 1 second showing "3"
    ("2", 1.0),       # 1 second showing "2"
    ("1", 1.0),       # 1 second showing "1"
    ("FIGHT!", 0.8),  # 0.8 second showing "FIGHT!"
]
# Stage 204 — COUNTDOWN_TOTAL удалён (0 чтений: фазы итерируются напрямую).

# Countdown text rendering
COUNTDOWN_FONT_SIZE: int = 96           # big bold text
COUNTDOWN_COLOR: tuple[int, int, int] = (234, 179, 8)   # gold yellow-500
COUNTDOWN_SHADOW_COLOR: tuple[int, int, int] = (0, 0, 0)
COUNTDOWN_TEXT_SCALE_PER_PHASE: list[float] = [1.0, 1.05, 1.1, 1.3]  # progressive zoom

# ---------------------------------------------------------------------------
# COMBAT TIMING (Stage 4 — turn-based autobattle)
# ---------------------------------------------------------------------------
# Per §5.4 FightSystem: AtkTime is turn frequency in ms (base 1000).
# Lower AtkTime = more turns = attacks more often.

# Stage 7: base speed +10% per user request — TURN_EVENT_DELAY reduced from
# 1.2 to 1.08 seconds (1.2 * 0.9). Speed buttons (x2/x3/x4) further divide by
# the speed multiplier at runtime (see PygameUI._update_combat_replay).
TURN_EVENT_DELAY: float = 1.08         # seconds — pause between events (Stage 7: was 1.2)
# Stage 70 — INDIVIDUAL EVENT DELAYS. More cinematic pacing: each event type
# has its own delay. _update_combat_replay picks the delay based on event type.
# This replaces the flat 1.08s for all events (which felt too uniform).
#
# Stage 189 — синхронизация ритма. Визуал удара теперь несёт AttackSequence
# (урон/статусы в midpoint seq, Stage 188), а ранний return в _update_battle
# ЗАМОРАЖИВАЕТ таймер реплея на всё время seq — задержка события считается
# ПОСЛЕ анимации. Старые 1.5с превращались в мёртвую паузу после возврата
# бойца (итог ~4.7с на ход, из них 1.5с ничего не происходит). Теперь
# EVENT_DELAY_ATTACK — короткий бит «после анимации до бухгалтерии»
# (стоимость MP, shatter глыбы, фолбэк-статусы): событие и анимация живут
# в одном такте, ход ~3.4с. NOTE: если вернёшь визуал удара на событие
# (без seq) — верни и длинную задержку.
EVENT_DELAY_BEGIN_ATTACK: float = 0.7   # turn start — quick (status ticks + setup)
EVENT_DELAY_END_ATTACK: float = 0.5      # turn end — quick (cleanup + MP regen)
EVENT_DELAY_ATTACK: float = 0.2          # main attack — bookkeeping beat AFTER seq (Stage 189; was 1.5)
# Stage 189 — страж зависания реплея: если бой жив, endgame ещё не начался,
# а события реплея не обрабатывались дольше BATTLE_WATCHDOG_TIMEOUT игровых
# секунд — пишем диагностику в _combat_debug_lines (видна в F10; при
# включённом _combat_debug пишется в data/combat_debug.txt). Порог взят с
# большим запасом: максимальная легальная пауза между событиями —
# EVENT_DELAY_DIE (2.0с), seq длится ~2.1с; законные бои (MAX_BOUT×такт)
# не достигают порога, т.к. события продолжают обрабатываться.
BATTLE_WATCHDOG_TIMEOUT: float = 45.0    # seconds of battle-time without event progress
BATTLE_WATCHDOG_REPORT_MAX: int = 6      # max distinct watchdog reports per battle
EVENT_DELAY_DIE: float = 2.0             # death — slowest (dramatic pause)
EVENT_DELAY_CANT_MOVE: float = 0.8      # frozen/skip — quick (just shows ice block)
EVENT_DELAY_EXTRA_TURN: float = 0.6     # extra turn — quick (Lightning Step)
EVENT_DELAY_DOT: float = 0.8             # poison/cloud tick — quick (small effect)
EVENT_DELAY_SHIELD: float = 0.6         # shield applied — quick (buff flash)
HIT_REACTION_DURATION: float = 0.4    # seconds — hit flash (per §8.4 Q28)
# Stage 204 — LUNGE_DURATION/LUNGE_DISTANCE/DEATH_FREEZE_DURATION удалены
# (0 чтений: тайминги атаки/смерти живут в AttackSequence).

# Stage 70 — HP/MP LERP SPEED tied to TURN_EVENT_DELAY.
# The lerp factor `dt * HP_LERP_SPEED` must be high enough that the displayed
# HP bar catches up to the actual fighter.hp BEFORE the next event fires.
# With individual delays (min 0.5s for END_ATTACK), we need lerp to reach
# ~99% within 0.5s. lerp_factor = 1 - (1-k)^n where n=frames. At 60 FPS,
# 0.5s = 30 frames. For 99%: k ≈ 0.15. So HP_LERP_SPEED = 9.0 (was 5.0).
# This ensures the HP bar visually catches up before the next event.
HP_LERP_SPEED: float = 9.0           # was 5.0 (Stage 69) — now syncs with min event delay

# Max battle turns (per §5.2 MAX_BOUT)
MAX_BOUT: int = 60

# Combat log max lines displayed
COMBAT_LOG_MAX_LINES: int = 8
COMBAT_LOG_LINE_HEIGHT: int = 18

# ---------------------------------------------------------------------------
# COMBAT DAMAGE CONSTANTS (Stage 4 — per §5.3 INFERRED, port of Damage.java)
# ---------------------------------------------------------------------------
# These constants are imported by combat.damage.py. They mirror the
# decompiled `com.d2.serv.game.FightModule.Damage` formulas.
#
# All values are INFERRED design choices (decompiled constants not available
# in source); chosen to give a sensible damage range between Ichigo and
# samurai in Stage 4 testing.

# ---------------------------------------------------------------------------
# Stage 168 (аудит 5.1) — БОЕВАЯ МАТЕМАТИКА ПЕРЕЕХАЛА в combat/formulas.py.
# Сюда входили: заголовок Stage 103 (рейтинги/hit chance), шаги rating→%
# (RATING_PCT_STEP, CRIT_CHANCE_STEP, CRIT_DAMAGE_STEP, RATING_PCT_DIVISOR),
# DEFENSE_BREAK_CONSTANT, константы пайплайна урона (CRIT_BASE_*,
# BLOCK_DAMAGE_MULTIPLIER), RATING_STAT_KEYS, капы hit
# (BASE_HIT_CHANCE/HIT_FLOOR_PCT/HIT_CAP_PCT), STR_THRESHOLD_FOR_HIT,
# DEFAULT_BMV_PRICE_*, SPEED_BASE_FLOAT и конверсии первичных статов
# (STR_TO_ATK, STA_TO_HP/DEF). Функции: apply_pct_bonus, collect_rating_pct.
# Легаси-константы CRIT/PARRY (AGI_TO_PARRY, BASE_CRIT/PARRY, PARRY_CAP,
# CRIT_CAP, PARRY_DAMAGE_REDUCTION, PIERCE_MAX, STR_TO_CRIT, STA_TO_TOUGH)
# удалены — реальной боевой математики не касались. Ре-экспорты — в конце файла.
# ---------------------------------------------------------------------------


# === Stage 108 — WEAPON GENERATION SYSTEM (per task spec) ==================
#
# Procedural weapon generation with rarity tiers (Grey/Blue/Purple/Gold/Red).
# Each weapon has:
#   - Fixed main stat (min_atk, max_atk) from WEAPON_BALANCE_TABLE by level.
#   - Random secondary stats rolled from SECONDARY_STAT_POOL.
#   - Number of secondary stats determined by rarity color.
#   - level_requirement field (player must be >= level to equip).
#
# Rarity → secondary stat count:
#   Grey   = 0 stats (only main stat, no random affixes)
#   Blue   = 1 random stat
#   Purple = 2 random stats
#   Gold   = 3 random stats
#   Red    = 4 random stats
#
# No duplicates: the same secondary stat cannot appear twice on one weapon.

# Valid weapon levels (from task spec table).
WEAPON_LEVELS: tuple[int, ...] = (1, 5, 10, 15, 20, 25)

# Stage 110 — mapping from weapon_level → item_id template in EQUIPMENT_DB.
# generate_item() uses this to look up the base template (name + icon_filename)
# for each level, so generated weapons keep their original name and sprite.
WEAPON_TEMPLATE_MAP: dict[int, str] = {
    1:  "weapon_wooden",    # "Деревянный меч", weapon_wooden.png
    5:  "weapon_blunt2",    # "Булава новичка", weapon_blunt2.gif
    10: "weapon_blunt3",    # "Стальная булава", weapon_blunt3.gif
    15: "weapon_blunt4",    # "Боевой молот", weapon_blunt4.gif
    20: "weapon_blunt5",    # "Молот разрушения", weapon_blunt5.gif
    25: "weapon_blunt6",    # "Легендарный молот", weapon_blunt6.gif
}

# Stage 169 (аудит 4.4) — мёртвый код удалён (0 вызовов в src/ и scripts/).



# Pastel background colors for inventory slots (RGBA, applied with alpha).
# Soft, muted, eye-friendly — not saturated.
RARITY_SLOT_BG: dict[str, tuple[int, int, int]] = {
    "Grey":   (39, 39, 42),       # default dark slot (no tint)
    "Blue":   (44, 82, 130),       # #2C5282 pastel blue
    "Purple": (85, 60, 154),       # #553C9A muted lavender
    "Gold":   (116, 66, 16),       # #744210 soft amber
    "Red":    (116, 42, 42),       # #742A2A matte burgundy
}

# Stage 209 — качество КОСТЮМОВ (гардероб/инвентарь): 4 тира, как у
# предметов. Качество живёт в OUTFITS_DB/EQUIPMENT_DB["quality"]; отсутствие
# поля = Grey. База на 15+ будущих костюмов: добавить запись с "quality" —
# фон слота/рамка/имя подхватятся автоматически (render_inventory,
# render_synth-гардероб, тултип костюма).
COSTUME_QUALITY_ORDER: tuple[str, ...] = ("Grey", "Blue", "Purple", "Orange")
COSTUME_QUALITY_RU: dict[str, str] = {
    "Grey":   "Серый",
    "Blue":   "Синий",
    "Purple": "Фиолетовый",
    "Orange": "Оранжевый",
}
# Фон ячейки/слота за иконкой костюма.
COSTUME_QUALITY_BG: dict[str, tuple[int, int, int]] = {
    "Grey":   (39, 39, 42),        # как RARITY_SLOT_BG["Grey"] — тёмный слот
    "Blue":   (44, 82, 130),       # как предметы
    "Purple": (85, 60, 154),       # как предметы
    "Orange": (124, 66, 16),       # тёплый янтарно-оранжевый
}
# Рамка слота/имя костюма (насыщенный цвет тира).
COSTUME_QUALITY_RGB: dict[str, tuple[int, int, int]] = {
    "Grey":   (150, 150, 150),
    "Blue":   (60, 120, 220),
    "Purple": (167, 139, 250),
    "Orange": (234, 146, 8),       # оранжевый (у предметов Gold — желтее)
}

# Stage 112/118/119 — MOB DROP TABLES per location.
# Stage 119 — REFACTORED to "max 1 equipment per battle" model:
#   * Each battle rolls ONCE for "any equipment drop?" using `equipment_chance`.
#   * If drop succeeds, ONE type is picked using weighted `type_weights`
#     (the weights don't need to sum to 100 — they're normalized internally).
#   * Then ONE rarity is rolled using `rarity_chances` (shared across all types).
#   * The level is picked randomly from `levels`.
# This replaces the old per-type independent rolls (which could yield up to
# 3 items per battle — weapon + armor + boots).
# Gem drops are still rolled separately (10% chance, unaffected by this table).
MOB_DROP_TABLES: dict[int, dict] = {
    1: {  # Location 1 — starting area
        # Single roll: 30% chance any equipment drops per victory.
        "equipment_chance": 30,
        # Type weights (normalized internally). Sum doesn't have to be 100.
        # Stage 123 — added gloves (weight 1, same as ring — both "accessory-like").
        # Stage 127 — added belt (weight 1, same as ring/gloves).
        # Stage 128 — added head (weight 1, completes the 7-slot system).
        "type_weights": {
            "weapon": 4,
            "armor":  3,
            "boots":  2,
            "ring":   1,
            "gloves": 1,
            "belt":   1,
            "head":   1,
        },
        # Shared rarity chances for ALL types on this location.
        "rarity_chances": {
            "Grey":   60,   # 60% — common
            "Blue":   25,   # 25% — uncommon
            "Purple": 13,   # 13% — rare
            "Gold":   2,    # 2%  — epic
            # Red NOT in Loc1 (no legendary drops on starting area).
        },
        # Levels available for drops on this location.
        "levels": [1, 5],
    },
}

# Rarity colors and their secondary stat count.
RARITY_COLORS: dict[str, int] = {
    "Grey":   0,
    "Blue":   1,
    "Purple": 2,
    "Gold":   3,
    "Red":    4,
}

# Display color (RGB) for each rarity tier (for UI rendering).
RARITY_RGB: dict[str, tuple[int, int, int]] = {
    "Grey":   (150, 150, 150),   # gray
    "Blue":   (60, 120, 220),    # blue
    "Purple": (167, 139, 250),   # violet
    "Gold":   (234, 179, 8),     # gold
    "Red":    (220, 60, 60),     # red
}

# Weapon balance table (per task spec §3):
#   level → (min_atk, max_atk, flat_min, flat_max, pct_min, pct_max)
# Where:
#   min_atk/max_atk — fixed main stat (added to gear_min/gear_max).
#   flat_min/flat_max — range for rolling flat secondary stats (rating points).
#   pct_min/pct_max — range for rolling percentage secondary stats (%).
WEAPON_BALANCE_TABLE: dict[int, dict[str, int]] = {
    1:  {"min_atk": 3,  "max_atk": 6,  "flat_min": 1,  "flat_max": 2,  "pct_min": 1, "pct_max": 2},
    5:  {"min_atk": 7,  "max_atk": 13, "flat_min": 2,  "flat_max": 4,  "pct_min": 1, "pct_max": 3},
    10: {"min_atk": 12, "max_atk": 22, "flat_min": 4,  "flat_max": 7,  "pct_min": 2, "pct_max": 4},
    15: {"min_atk": 18, "max_atk": 32, "flat_min": 6,  "flat_max": 10, "pct_min": 2, "pct_max": 5},
    20: {"min_atk": 26, "max_atk": 45, "flat_min": 9,  "flat_max": 14, "pct_min": 3, "pct_max": 6},
    25: {"min_atk": 35, "max_atk": 60, "flat_min": 12, "flat_max": 18, "pct_min": 3, "pct_max": 7},
}

# Stage 112 — ARMOR BALANCE TABLE (per task spec §3).
#   level → (defense, max_hp, flat_min, flat_max, pct_min, pct_max)
ARMOR_BALANCE_TABLE: dict[int, dict[str, int]] = {
    1:  {"defense": 5,  "max_hp": 15,  "flat_min": 1,  "flat_max": 2,  "pct_min": 1, "pct_max": 2},
    5:  {"defense": 12, "max_hp": 35,  "flat_min": 2,  "flat_max": 4,  "pct_min": 1, "pct_max": 3},
    10: {"defense": 22, "max_hp": 65,  "flat_min": 4,  "flat_max": 7,  "pct_min": 2, "pct_max": 4},
    15: {"defense": 35, "max_hp": 105, "flat_min": 6,  "flat_max": 10, "pct_min": 2, "pct_max": 5},
    20: {"defense": 52, "max_hp": 155, "flat_min": 9,  "flat_max": 14, "pct_min": 3, "pct_max": 6},
    25: {"defense": 75, "max_hp": 220, "flat_min": 12, "flat_max": 18, "pct_min": 3, "pct_max": 7},
}

# Stage 112 — ARMOR TEMPLATE MAP: level → item_id in EQUIPMENT_DB.
ARMOR_TEMPLATE_MAP: dict[int, str] = {
    1:  "vest_ninja",      # "Жилет ниндзя", vest_ninja.png  (L1 starter)
    5:  "body_cloth2",     # "Кожаная броня", body_cloth2.gif
    10: "body_cloth3",     # "Кольчуга", body_cloth3.gif
    15: "body_cloth4",     # "Латы стража", body_cloth4.gif
    20: "body_cloth5",     # "Доспех войны", body_cloth5.gif
    25: "body_cloth6",     # "Легендарный доспех", body_cloth6.gif
}

# Stage 118 — BOOTS BALANCE TABLE.
# Mirrors ARMOR_BALANCE_TABLE structure but uses (defense, speed) as main stats.
# Speed scales more aggressively than defense (boots are the speed slot).
# Secondary stat ranges are shared with WEAPON/ARMOR tables (same flat_min/pct_max).
BOOTS_BALANCE_TABLE: dict[int, dict[str, int]] = {
    1:  {"defense": 1,  "speed": 5,   "flat_min": 1,  "flat_max": 2,  "pct_min": 1, "pct_max": 2},
    5:  {"defense": 3,  "speed": 12,  "flat_min": 2,  "flat_max": 4,  "pct_min": 1, "pct_max": 3},
    10: {"defense": 6,  "speed": 22,  "flat_min": 4,  "flat_max": 7,  "pct_min": 2, "pct_max": 4},
    15: {"defense": 10, "speed": 35,  "flat_min": 6,  "flat_max": 10, "pct_min": 2, "pct_max": 5},
    20: {"defense": 15, "speed": 52,  "flat_min": 9,  "flat_max": 14, "pct_min": 3, "pct_max": 6},
    25: {"defense": 22, "speed": 75,  "flat_min": 12, "flat_max": 18, "pct_min": 3, "pct_max": 7},
}

# Stage 118 — BOOTS TEMPLATE MAP: level → item_id in EQUIPMENT_DB.
# L1 keeps the existing "boots_shinobi" starter (preserves backward-compat
# for existing save files that may have it equipped). L5/L10/L15/L20/L25
# use the new boots_shoes2..6 templates that pair with the user-provided
# icon_equip_shoes2..6.gif sprites.
BOOTS_TEMPLATE_MAP: dict[int, str] = {
    1:  "boots_shinobi",   # "Сандалии ниндзя", boots_shinobi.png  (L1 starter, kept for save-compat)
    5:  "boots_shoes2",    # "Туфли ловкости", boots_shoes2.gif
    10: "boots_shoes3",    # "Сапоги странника", boots_shoes3.gif
    15: "boots_shoes4",    # "Поножи стража", boots_shoes4.gif
    20: "boots_shoes5",    # "Сапоги войны", boots_shoes5.gif
    25: "boots_shoes6",    # "Легендарные поножи", boots_shoes6.gif
}

# Stage 119 — RING BALANCE TABLE.
# Mirrors ARMOR/BOOTS table structure but uses (crit_rating, pierce_rating) as main stats.
# crit_rating scales faster than pierce_rating (rings are the crit/pierce slot).
# Main stats идентичны слоту "accessory" в SLOT_MAIN_STATS (Stage 169: ссылка
# на мёртвую ITEM_BALANCE_TABLE убрана вместе с таблицей).
RING_BALANCE_TABLE: dict[int, dict[str, int]] = {
    1:  {"crit_rating": 2,  "pierce_rating": 1,  "flat_min": 1,  "flat_max": 2,  "pct_min": 1, "pct_max": 2},
    5:  {"crit_rating": 5,  "pierce_rating": 2,  "flat_min": 2,  "flat_max": 4,  "pct_min": 1, "pct_max": 3},
    10: {"crit_rating": 10, "pierce_rating": 4,  "flat_min": 4,  "flat_max": 7,  "pct_min": 2, "pct_max": 4},
    15: {"crit_rating": 17, "pierce_rating": 6,  "flat_min": 6,  "flat_max": 10, "pct_min": 2, "pct_max": 5},
    20: {"crit_rating": 26, "pierce_rating": 9,  "flat_min": 9,  "flat_max": 14, "pct_min": 3, "pct_max": 6},
    25: {"crit_rating": 38, "pierce_rating": 13, "flat_min": 12, "flat_max": 18, "pct_min": 3, "pct_max": 7},
}

# Stage 119 — RING TEMPLATE MAP: level → item_id in EQUIPMENT_DB.
# L1 keeps the existing "amulet_clan" starter (preserves backward-compat for
# existing save files). L5-L25 use the new ring_jade2..6 templates.
# NOTE: ring_jade2 uses ring1.png as a placeholder icon because the user did
# not upload icon_equip_ring2.s110.gif. Replace with the real ring2 sprite
# when available.
RING_TEMPLATE_MAP: dict[int, str] = {
    1:  "amulet_clan",    # "Амулет клана", amulet_clan.png  (L1 starter, kept for save-compat)
    5:  "ring_jade2",     # "Кольцо нефрита", ring_jade2.png (placeholder for missing ring2.s110.gif)
    10: "ring_jade3",     # "Кольцо клана", ring_jade3.gif
    15: "ring_jade4",     # "Кольцо стража", ring_jade4.gif
    20: "ring_jade5",     # "Кольцо войны", ring_jade5.gif
    25: "ring_jade6",     # "Легендарное кольцо", ring_jade6.gif
}

# Stage 123 — GLOVES BALANCE TABLE.
# Mirrors BOOTS/RING table structure but uses (defense, hit_rating) as main stats.
# hit_rating scales same as defense (hands slot is the defense+hit slot).
GLOVES_BALANCE_TABLE: dict[int, dict[str, int]] = {
    1:  {"defense": 2,  "hit_rating": 2,  "flat_min": 1,  "flat_max": 2,  "pct_min": 1, "pct_max": 2},
    5:  {"defense": 5,  "hit_rating": 5,  "flat_min": 2,  "flat_max": 4,  "pct_min": 1, "pct_max": 3},
    10: {"defense": 10, "hit_rating": 10, "flat_min": 4,  "flat_max": 7,  "pct_min": 2, "pct_max": 4},
    15: {"defense": 17, "hit_rating": 17, "flat_min": 6,  "flat_max": 10, "pct_min": 2, "pct_max": 5},
    20: {"defense": 26, "hit_rating": 26, "flat_min": 9,  "flat_max": 14, "pct_min": 3, "pct_max": 6},
    25: {"defense": 38, "hit_rating": 38, "flat_min": 12, "flat_max": 18, "pct_min": 3, "pct_max": 7},
}

# Stage 123 — GLOVES TEMPLATE MAP: level → item_id in EQUIPMENT_DB.
# L1 keeps the existing "gloves_leather" starter (preserves backward-compat
# for existing save files). L5-L25 use the new gloves_mitten2..6 templates.
GLOVES_TEMPLATE_MAP: dict[int, str] = {
    1:  "gloves_leather",  # "Кожаные перчатки", gloves_leather.png (L1 starter, kept for save-compat)
    5:  "gloves_mitten2",  # "Перчатки ловкости", gloves_mitten2.gif
    10: "gloves_mitten3",  # "Перчатки клана", gloves_mitten3.gif
    15: "gloves_mitten4",  # "Перчатки стража", gloves_mitten4.gif
    20: "gloves_mitten5",  # "Перчатки войны", gloves_mitten5.gif
    25: "gloves_mitten6",  # "Легендарные перчатки", gloves_mitten6.gif
}

# Stage 127 — BELT BALANCE TABLE.
# Mirrors GLOVES table structure but uses (defense, tough_rating) as main stats.
BELT_BALANCE_TABLE: dict[int, dict[str, int]] = {
    1:  {"defense": 2,  "tough_rating": 2,  "flat_min": 1,  "flat_max": 2,  "pct_min": 1, "pct_max": 2},
    5:  {"defense": 5,  "tough_rating": 5,  "flat_min": 2,  "flat_max": 4,  "pct_min": 1, "pct_max": 3},
    10: {"defense": 10, "tough_rating": 10, "flat_min": 4,  "flat_max": 7,  "pct_min": 2, "pct_max": 4},
    15: {"defense": 17, "tough_rating": 17, "flat_min": 6,  "flat_max": 10, "pct_min": 2, "pct_max": 5},
    20: {"defense": 26, "tough_rating": 26, "flat_min": 9,  "flat_max": 14, "pct_min": 3, "pct_max": 6},
    25: {"defense": 38, "tough_rating": 38, "flat_min": 12, "flat_max": 18, "pct_min": 3, "pct_max": 7},
}

# Stage 127 — BELT TEMPLATE MAP: level → item_id in EQUIPMENT_DB.
BELT_TEMPLATE_MAP: dict[int, str] = {
    1:  "belt_fabric",   # "Тканевый пояс", belt_fabric.png (L1 starter, kept for save-compat)
    5:  "belt_jade2",    # "Пояс ловкости", belt_jade2.gif
    10: "belt_jade3",    # "Пояс клана", belt_jade3.gif
    15: "belt_jade4",    # "Пояс стража", belt_jade4.gif
    20: "belt_jade5",    # "Пояс войны", belt_jade5.gif
    25: "belt_jade6",    # "Легендарный пояс", belt_jade6.gif
}

# Stage 128 — HEAD BALANCE TABLE.
# Same stats as ARMOR (defense + max_hp) but slightly lower defense, higher HP.
# This completes the 7-slot equipment system: weapon/head/body/hands/belt/boots/accessory.
HEAD_BALANCE_TABLE: dict[int, dict[str, int]] = {
    1:  {"defense": 3,  "max_hp": 15,  "flat_min": 1,  "flat_max": 2,  "pct_min": 1, "pct_max": 2},
    5:  {"defense": 7,  "max_hp": 35,  "flat_min": 2,  "flat_max": 4,  "pct_min": 1, "pct_max": 3},
    10: {"defense": 13, "max_hp": 65,  "flat_min": 4,  "flat_max": 7,  "pct_min": 2, "pct_max": 4},
    15: {"defense": 21, "max_hp": 105, "flat_min": 6,  "flat_max": 10, "pct_min": 2, "pct_max": 5},
    20: {"defense": 32, "max_hp": 155, "flat_min": 9,  "flat_max": 14, "pct_min": 3, "pct_max": 6},
    25: {"defense": 45, "max_hp": 220, "flat_min": 12, "flat_max": 18, "pct_min": 3, "pct_max": 7},
}

# Stage 128 — HEAD TEMPLATE MAP: level → item_id in EQUIPMENT_DB.
HEAD_TEMPLATE_MAP: dict[int, str] = {
    1:  "headband_ninja",  # "Повязка шиноби", headband_ninja.png (L1 starter, kept for save-compat)
    5:  "head_helm2",      # "Шлем ловкости", head_helm2.gif
    10: "head_helm3",      # "Шлем клана", head_helm3.gif
    15: "head_helm4",      # "Шлем стража", head_helm4.gif
    20: "head_helm5",      # "Шлем войны", head_helm5.gif
    25: "head_helm6",      # "Легендарный шлем", head_helm6.gif
}

# Stage 115 — SLOT MAIN STATS: defines which stats are "main" per slot.
# Used by tooltip + forge to separate main stats from secondary stats.
SLOT_MAIN_STATS: dict[str, tuple[str, ...]] = {
    "weapon": ("min_atk", "max_atk"),
    "head": ("defense", "max_hp"),
    "body": ("defense", "max_hp"),
    "hands": ("defense", "hit_rating"),
    "belt": ("defense", "tough_rating"),
    "boots": ("defense", "speed"),
    "accessory": ("crit_rating", "pierce_rating"),
}

# Stage 169 (аудит 4.4) — мёртвый код удалён (0 вызовов в src/ и scripts/).

# Stage 169 (аудит 4.4) — мёртвый код удалён (0 вызовов в src/ и scripts/).


# Pool of secondary stats for random generation (per task spec §1).
# Each entry: gear stat key → (type, label)
#   type "flat" → rolled value is a flat rating (added to *_rating in Step 1).
#   type "pct"  → rolled value is a percentage multiplier (added to *_pct in Step 2).
SECONDARY_STAT_POOL: list[tuple[str, str, str]] = [
    # (gear_key,           type,      label)
    ("hit_rating",         "flat",    "Меткость"),       # flat hit rating
    ("dodge_rating",       "flat",    "Уклонение"),      # flat dodge rating
    ("crit_rating",        "flat",    "Крит"),           # flat crit rating
    ("tough_rating",       "flat",    "Стойкость"),      # flat tough rating
    ("block_rating",       "flat",    "Блок"),           # flat block rating
    ("pierce_rating",      "flat",    "Пробитие"),       # flat pierce rating
    ("antiblock_rating",   "flat",    "Антиблок"),       # Stage 137 — снимает чужой блок (/16)
    ("atk_mul",            "pct",     "Множ. Атаки%"),   # +X% attack multiplier
    ("dodge_pct",          "pct",     "Множ. Уклона%"),  # +X% dodge multiplier
    ("crit_pct",           "pct",     "Множ. Крита%"),   # +X% crit multiplier
    ("hit_pct",            "pct",     "Множ. Меткости%"),# +X% hit multiplier
    ("tough_pct",          "pct",     "Множ. Стойкости%"),# +X% tough multiplier
    ("block_pct",          "pct",     "Множ. Блока%"),   # +X% block multiplier
    ("pierce_pct",         "pct",     "Множ. Пробития%"),# +X% pierce multiplier
    ("antiblock_pct",      "pct",     "Множ. Антиблока%"),# Stage 137 — +X% antiblock multiplier
]

SLOT_NAME_RU: dict[str, str] = {
    "weapon": "Оружие",
    "head": "Голова",
    "body": "Броня",
    "hands": "Перчатки",
    "belt": "Пояс",
    "boots": "Обувь",
    "accessory": "Аксессуар",
    "armor": "Броня",
    "amulet": "Аксессуар",
    "gloves": "Перчатки",
    "ring": "Аксессуар",
}

STAT_LABEL_RU: dict[str, str] = {
    "strength": "Сила", "agility": "Ловкость", "stamina": "Выносливость",
    "max_mp": "Макс. мана", "max_hp": "Макс. здоровье",
    "min_atk": "Мин. атака", "max_atk": "Макс. атака", "defense": "Защита",
    "hit_chance": "Меткость", "toughness": "Стойкость", "tough_rating": "Стойкость",
    "speed": "Скорость", "parry_chance": "Парри", "pierce": "Пробивание",
    "crit_chance": "Крит", "crit_rating": "Крит",
    "atk_mul": "Множ. атаки%", "max_hp_mul": "Множ. здоровья%",
    "def_mul": "Множ. защиты%", "dodge_mul": "Множ. уклона%",
    "hit_rating": "Меткость", "dodge_rating": "Уклонение",
    "block_rating": "Блок", "pierce_rating": "Пробитие",
    "antiblock_rating": "Антиблок",  # Stage 137
    "dodge_pct": "Множ. уклона%", "hit_pct": "Множ. меткости%",
    "crit_pct": "Множ. крита%", "tough_pct": "Множ. стойкости%",
    "block_pct": "Множ. блока%", "pierce_pct": "Множ. пробития%",
    "antiblock_pct": "Множ. антиблока%",  # Stage 137
}

# Stage 169 (аудит 4.4) — мёртвый код удалён (0 вызовов в src/ и scripts/).



# Stage 168 (аудит 5.1): rating_to_percent / combat_hit_chance /
# calc_dodge_rating / calc_hit_rating / calc_speed / calc_tough_rating /
# calc_block_rating / calc_pierce_rating — в combat/formulas.py
# (ре-экспорт в конце файла, старые импорты из config работают).


# Stage 168 (аудит 5.1): rating_to_crit_chance / rating_to_crit_damage /
# rating_to_tough_* / rating_to_block_chance / rating_to_antiblock_pct
# и пайплайн урона apply_crit_stage / apply_block_stage /
# apply_defense_stage — в combat/formulas.py (ре-экспорт в конце файла).


# Stage 168 (аудит 5.1): legacy BMV-хелпер calc_atk_mul_pct (живой) —
# в combat/formulas.py (ре-экспорт в конце файла). Легаси calc_max_hp_mul_pct /
# calc_def_mul_pct / stat_to_pct / rating_to_pct удалены (0 вызовов).

# Stage 168 (аудит 5.1): константы Stage 52 CRIT_K, STR_TO_CRIT_RATING,
# STA_TO_TOUGH_RATING, CRIT_MUL_BASE/PER_STR/CAP удалены (0 вызовов —
# Stage 137 считает крит через рейтинги /16). LEVEL_UP_* остаются здесь.

# === Stage 52 — LEVEL UP bonuses (new hybrid system) ===
# Level gives HP/MP/attack growth, but STR/AGI/STA grow very slowly
# so the main source of power is equipment/gems/enchants.
LEVEL_UP_HP: int = 50          # +50 max HP per level
LEVEL_UP_MP: int = 10          # +10 max MP per level
# Stage 204 — LEVEL_UP_MIN/MAX_ATK/STR/AGI/STA удалены (0 чтений: рост атаки
# и первичек считается в state.recalc_stats из собственных таблиц).

# === Stage 170 — магические числа из state.py вынесены в config (значения
# НЕ менялись — только перенос; см. MEMORY §«Магические числа») ===
LEVEL_XP_CURVE: int = 100            # max_xp = level * LEVEL_XP_CURVE (gain_xp)
ATK_TIME_MIN_MS: int = 400           # кламп медленной скорости (recalc_stats)
ATK_TIME_BASE_MS: int = 1500         # atk_time = ATK_TIME_BASE_MS / speed
ATK_TIME_SPEED_FLOOR: float = 0.1    # защита от деления на ~0
GEM_SYNTH_SUCCESS_PCT: int = 60      # шанс успеха синтеза камней (flat)
GEM_DROP_CHANCE: float = 0.10        # шанс дропа камня за победу
TEST_START_GOLD: int = 100000        # Stage 113 — тестовое золото (запрошено пользователем)
TEST_START_COUPONS: int = 10500      # Stage 165 — тестовые купоны (запрошено пользователем)


# Stage 168 (аудит 5.1): calc_crit_rating — в combat/formulas.py
# (ре-экспорт в конце файла). Легаси calc_parry_chance / calc_crit_chance /
# calc_crit_multiplier удалены (0 вызовов).

# Stage 169 (аудит 4.4) — мёртвый код удалён (0 вызовов в src/ и scripts/).
# Примечание: K гиперболы Защита/Пробивание — DEFENSE_BREAK_CONSTANT=1354
# в combat/formulas.py (единое имя; дубль DEFENSE_CONSTANT удалён).

# CHARACTER SHEET WINDOW (Stage 4 — per user request)
# ---------------------------------------------------------------------------
# Modal window that opens when clicking "Осмотреть персонажа" side banner.

# Stage 5 (per user request): window width reduced ~17% (480 → 400). Char sheet
# now slides IN FROM the edge of the screen (left or right banner click), instead
# of opening centered with scale animation. Height unchanged.
#
# Stage 7 (per user request): window width narrowed further by ~22%
# (400 → 310) so it takes up less screen space and the stats table stays
# readable with a slightly smaller font (font_charsheet_label/value now 13pt).
# Slide-in endpoints auto-adjusted via CHAR_SHEET_W.
#
# Stage 9 (per Fix 5a): window height increased from 540 → 660 (+120px) to
# fit a 10-slot skills grid (5×2, 86px tall) BELOW the stats table. The
# skills grid section reserves ~120px (label + grid + gaps) at the bottom
# of the window, above the close button.
CHAR_SHEET_W: int = 279  # Stage 98 — was 310, reduced 10% per user request.
# Stage 178 — ЕДИНАЯ высота окна характеристик у ИГРОКА и ВРАГА: компактная
# схема статов (ОЗ/МП → Атака/Скорость → 8 рейтингов 2 колонки ≈ 240px)
# + блок «Навыки» (86px). Раньше: игрок 592 (полная таблица), враг 380
# (константа CHAR_SHEET_H_ENEMY удалена вместе с раздельной таблицей).
CHAR_SHEET_H: int = 420  # Stage 179 — +40px: у игрока добавлены 2 строки первичных статов (Сила/Ловкость/Выносливость)
CHAR_SHEET_BG: tuple[int, int, int] = (24, 24, 27)         # zinc-900
CHAR_SHEET_ACCENT: tuple[int, int, int] = (234, 179, 8)    # gold
CHAR_SHEET_ANIM_DURATION: float = 0.3    # seconds — slide-in from edge (Stage 5)
# Stage 204 — CHAR_SHEET_BORDER/CHAR_SHEET_PADDING удалены (0 чтений:
# рамка/паддинг окна берутся из UI_THEME/MODAL_*).
# Margin from screen edge when char sheet is fully slid in (Stage 5).
CHAR_SHEET_EDGE_MARGIN: int = 0  # Stage 98 — was 20, shifted to edge per user request.

# Stage 7 — Ichigo attack sequence phases (multi-phase state machine).
# Replaces the single LungeAnimation for ATTACK events triggered by player.
# Per Stage 5 spec: RUN_FORWARD → ATTACK → RUN_BACK → DONE.
#
# Stage 7 base speed +10% per user request (all durations × 0.9):
#   RUN_FORWARD_DURATION: 0.8 → 0.72
#   ATTACK_DURATION:      0.5 → 0.45
#   RUN_BACK_DURATION:    0.8 → 0.72
# These are the x1 (base) durations; speed buttons (x2/x3/x4) further divide
# them by the speed multiplier at runtime (see PygameUI._update_attack_sequence).
ATTACK_SEQ_RUN_FORWARD_DURATION: float = 0.72   # seconds — run from start to near enemy (Stage 7: was 0.8)
ATTACK_SEQ_PAUSE_DURATION: float = 0.15          # Stage 97 — pause at enemy before striking
ATTACK_SEQ_ATTACK_DURATION: float = 0.45        # seconds — small final lunge + apply damage (Stage 7: was 0.5)
ATTACK_SEQ_RUN_BACK_DURATION: float = 0.72       # seconds — run back to start position (Stage 7: was 0.8)
# Stage 188 — «стойка победителя» после смертельного удара: пауза в HOLD-фазе
# перед запуском endgame (драматическая пауза; раньше HOLD был тупиком).
ATTACK_SEQ_HOLD_ENDGAME_DELAY: float = 0.9      # seconds
# Player attack endpoint: ~110px before enemy sprite.
# Stage 98 — user-requested: REACH_X = ENEMY_SPRITE_X - 110, STRIKE_X = REACH_X.
ATTACK_SEQ_PLAYER_REACH_X: int = ENEMY_SPRITE_X - 110    # 850
ATTACK_SEQ_PLAYER_STRIKE_X: int = ENEMY_SPRITE_X - 110    # 850 (= REACH, fixed at enemy)
# Enemy attack endpoint: ~110px after player sprite.
# Stage 98 — user-requested: REACH_X = PLAYER_SPRITE_X + 110, STRIKE_X = REACH_X.
ATTACK_SEQ_ENEMY_REACH_X: int = PLAYER_SPRITE_X + 110    # 430
ATTACK_SEQ_ENEMY_STRIKE_X: int = PLAYER_SPRITE_X + 110    # 430 (= REACH, fixed at player)

# Stage 5 — Enemy hit reaction: shake effect (no hit-animation folder for samurai).
# During hit timer, enemy sprite jitters ±3px horizontally to indicate impact.
ENEMY_HIT_SHAKE_AMPLITUDE: int = 3   # px — random x offset on hit

# Stage 5 — Combat log expand/collapse animation.
# Collapsed height = LOG_BAR_H (36px, single line centered).
# Expanded height = COMBAT_LOG_MAX_LINES * COMBAT_LOG_LINE_HEIGHT + padding.
COMBAT_LOG_EXPANDED_H: int = COMBAT_LOG_MAX_LINES * COMBAT_LOG_LINE_HEIGHT + 20  # 8*18+20 = 164
COMBAT_LOG_ANIM_DURATION: float = 0.25   # seconds — smooth height lerp


# ---------------------------------------------------------------------------
# STAGE 7 — BATTLE SPEED BUTTONS (x1 / x2 / x3 / x4)
# ---------------------------------------------------------------------------
# Per user request Stage 7: add 4 speed buttons at bottom-center of the BATTLE
# screen. Clicking x2/x3/x4 multiplies the dt-driven battle update rate by the
# chosen factor. Base speed is x1 (already +10% faster than Stage 6 due to the
# ATTACK_SEQ_*_DURATION and TURN_EVENT_DELAY reductions above).
#
# Allowed speed values (powers-of-two style progression).
BATTLE_SPEEDS: tuple[float, ...] = (1.0, 2.0, 3.0, 4.0)
BATTLE_SPEED_DEFAULT: float = 1.0

# Speed button geometry (rendered centered, above the combat log).
SPEED_BTN_W: int = 60
SPEED_BTN_H: int = 32
SPEED_BTN_GAP: int = 8
# Active (selected) speed button colors (emerald-500 bg, zinc-950 text).
SPEED_BTN_ACTIVE_BG: tuple[int, int, int] = (16, 185, 129)
SPEED_BTN_ACTIVE_FG: tuple[int, int, int] = (9, 9, 11)
# Inactive (non-selected) speed button colors (zinc-800 bg, zinc-400 text).
SPEED_BTN_INACTIVE_BG: tuple[int, int, int] = (39, 39, 42)
SPEED_BTN_INACTIVE_FG: tuple[int, int, int] = (161, 161, 170)
# Hover bg (slightly lighter than inactive).
SPEED_BTN_HOVER_BG: tuple[int, int, int] = (63, 63, 70)
# Click rect tags for each speed button.
SPEED_BTN_TAGS: tuple[str, ...] = (
    "speed_x1",
    "speed_x2",
    "speed_x3",
    "speed_x4",
)


# ---------------------------------------------------------------------------
# STAGE 7 — PARTICLE SYSTEM (sparks / blood on hit)
# ---------------------------------------------------------------------------
# Per user request Stage 7: spawn impact particles when a fighter takes damage.
# 60% sparks (yellow/orange), 40% blood (dark red — only on crits).
PARTICLE_MAX_COUNT: int = 200  # cap to avoid perf issues
PARTICLE_LIFE_MIN: float = 0.4   # seconds
PARTICLE_LIFE_MAX: float = 0.8
PARTICLE_SIZE_MIN: int = 3       # px (Stage 7 — bumped from 2 to make sparks visible)
PARTICLE_SIZE_MAX: int = 5       # px (Stage 7 — bumped from 4 to make sparks visible)
PARTICLE_SPEED_MIN: float = 80.0   # px/s
PARTICLE_SPEED_MAX: float = 200.0
PARTICLE_GRAVITY: float = 400.0   # px/s² (downward)
PARTICLE_HIT_COUNT_MIN: int = 8
PARTICLE_HIT_COUNT_MAX: int = 15
# Impact origin: chest height = SPRITE_BASE_Y - 60.
PARTICLE_IMPACT_Y_OFFSET: int = -60
# Particle colors. Stage 7: sparks are yellow/orange/deep-orange for visibility
# at small sizes (avoid near-white cream colors that look washed out).
PARTICLE_SPARK_COLORS: tuple[tuple[int, int, int], ...] = (
    (255, 200, 50),   # yellow
    (255, 120, 30),   # orange
    (255, 80, 0),     # deep orange (Stage 7: was bright cream — replaced for visibility)
)
PARTICLE_BLOOD_COLORS: tuple[tuple[int, int, int], ...] = (
    (180, 30, 30),    # dark red
    (140, 20, 20),    # deeper red
)

# --- Stage 71/72 — WORLD BOSS constants ---
WORLD_BOSS_MAX_HP: int = 50000

# --- Stage 89 — TOWER MODE constants ---
# Per TOWER_MODE_IMPLEMENTATION.md §9. Tower is a modal on MAP (not a
# separate GameState) — battles reuse GameState.BATTLE with _battle_mode.
TOWER_MAX_FLOOR: int = 100
# Stage 90 — attempt limit REMOVED. Tower is now endless (play until death).
# Stage 134 — legacy constants TOWER_MAX_ATTEMPTS / TOWER_ATTEMPT_REGEN_SECONDS
# deleted together with the tower-attempt fields they served.
TOWER_DEFAULT_START_FLOOR: int = 1
# Stage 204 — TOWER_MAP_BACKGROUND/TOWER_MODAL_W/H/TOWER_FLOOR_ROW_H удалены
# (0 чтений: модалка башни рендерится из собственных layout-констант render_tower).
TOWER_FLOORS_VISIBLE: int = 11           # rows visible before scroll
TOWER_SHOP_MODAL_W: int = 640
TOWER_SHOP_MODAL_H: int = 520
# Colors.
TOWER_BG: tuple[int, int, int] = (24, 24, 27)           # zinc-900
TOWER_BORDER: tuple[int, int, int] = (234, 179, 8)      # gold
TOWER_ACCENT: tuple[int, int, int] = (52, 211, 153)     # emerald (current floor)
TOWER_BOSS_COLOR: tuple[int, int, int] = (234, 179, 8)  # gold (boss floor)
TOWER_COMPLETED_COLOR: tuple[int, int, int] = (80, 220, 100)  # green (completed)
TOWER_SHARD_COLOR: tuple[int, int, int] = (167, 139, 250)     # violet (shards)

# Stage 72/102 — World Boss base stats (level 1).
# When killed, boss respawns with level+1 and ALL stats ×2.
# Stage 102 — DODGE now stored as RATING (not %). 0 = no dodge (player always hits).
WORLD_BOSS_BASE_MIN_ATK: int = 1000
WORLD_BOSS_BASE_MAX_ATK: int = 1500
WORLD_BOSS_BASE_DODGE: int = 0        # 0 dodge rating (player always hits)
WORLD_BOSS_BASE_SPEED: float = 1.0    # speed
WORLD_BOSS_BASE_TOUGH: int = 0        # 0 tough rating


# === Stage 180/181 — PLAYER BUFFS (расходники-бафы, реальное время) ==========
# Баф — ПРЕДМЕТ в инвентаре: клик игрока активирует его на duration_sec
# (реальное время, epoch seconds). Правила:
#   * бафы ОДНОГО kind СТАКАЮТСЯ между собой аддитивно: 50+100+150+200% = +500%
#     (множитель ×6.0); "atk" так же (+10% и +25% одновременно = +35%);
#   * повторная активация ТОГО ЖЕ buff_id ОБНОВЛЯЕТ время (expires = now +
#     duration) — НЕ прибавляет к остатку;
#   * kind="xp" — множитель к ЛЮБОМУ входящему XP (единая точка gain_xp:
#     бои, башня, гаунтлет, квесты);
#   * kind="atk" — % добавляется к общему множителю атаки Stage 107
#     (atk_mul_pct = Скрытый_Процент_Силы + gear_atk_mul + бафы).
# Иконки задаёт пользователь (icon_filename → assets/icons/items/).
BUFF_DB: dict[str, dict] = {
    "buff_xp_50": {
        "name": "Опыт +50%",
        "kind": "xp", "value": 50,
        "duration_sec": 3 * 3600,          # 3 часа
        "icon_filename": "buff_xp_50.gif",  # icon_big_food83.s110.gif (bigicon)
        "desc": "Скорость опыта 50%",
        "sell_price": 100,                 # Stage 187 — ручная продажа
    },
    "buff_xp_100": {
        "name": "Опыт +100%",
        "kind": "xp", "value": 100,
        "duration_sec": 3 * 3600,          # 3 часа
        "icon_filename": "buff_xp_100.gif",  # icon_big_food82.s110.gif (bigicon)
        "desc": "Скорость опыта 100%",
        "sell_price": 200,
    },
    "buff_xp_150": {
        "name": "Опыт +150%",
        "kind": "xp", "value": 150,
        "duration_sec": 1 * 3600,          # 1 час
        "icon_filename": "buff_xp_150.gif",  # icon_buff55.s110.gif (buff)
        "desc": "Скорость опыта 150%",
        "sell_price": 300,
    },
    "buff_xp_200": {
        "name": "Опыт +200%",
        "kind": "xp", "value": 200,
        "duration_sec": 1 * 3600,          # 1 час
        "icon_filename": "buff_xp_200.png",  # icon_bonusmachine_8.s110.png
        "desc": "Скорость опыта 200%",
        "sell_price": 400,
    },
    "buff_atk_10": {
        "name": "Атака +10%",
        "kind": "atk", "value": 10,
        "duration_sec": 2 * 3600,          # 2 часа
        "icon_filename": None,
        "desc": "Атака +10%",
        "sell_price": 100,
    },
    "buff_atk_25": {
        "name": "Атака +25%",
        "kind": "atk", "value": 25,
        "duration_sec": 1 * 3600,          # 1 час (по ТЗ — статы на 1 ч)
        "icon_filename": None,
        "desc": "Атака +25%",
        "sell_price": 250,
    },
}


def get_buff(buff_id: str) -> dict | None:
    """Stage 180 — определение бафа по id (None если id не баф)."""
    return BUFF_DB.get(buff_id)


# Stage 184 — РЕЦЕПТЫ СИНТЕЗА БАФОВ ОПЫТА: 3 одинаковых → 1 следующий вид.
# (исходный баф) → (результат, шанс %). 200% — терминальный, не синтезируется.
BUFF_SYNTH_RECIPES: dict[str, tuple[str, int]] = {
    "buff_xp_50": ("buff_xp_100", 75),
    "buff_xp_100": ("buff_xp_150", 50),
    "buff_xp_150": ("buff_xp_200", 25),
}
# Stage 72 — boss stands on the map (right of center), sprite X position.
WORLD_BOSS_MAP_SPRITE_X: int = 900    # px — boss sprite X on map (right of center 640)

# World Boss rank thresholds (by total damage dealt).
WORLD_BOSS_RANK_B: int = 500     # 500-1499
WORLD_BOSS_RANK_A: int = 1500    # 1500-2999
WORLD_BOSS_RANK_S: int = 3000    # 3000-4999
WORLD_BOSS_RANK_SS: int = 5000   # 5000-9999
WORLD_BOSS_RANK_SSS: int = 10000 # 10000+
WORLD_BOSS_REWARDS: dict[str, dict] = {
    "F":  {"gold": 50,   "label": "F"},
    "B":  {"gold": 200,  "label": "B"},
    "A":  {"gold": 500,  "label": "A"},
    "S":  {"gold": 1000, "label": "S"},
    "SS": {"gold": 2500, "label": "SS"},
    "SSS":{"gold": 5000, "label": "SSS"},
}
PARTICLE_BLOOD_FRACTION: float = 0.4   # 40% blood (only on crits)


# ---------------------------------------------------------------------------
# STAGE 8 — MAP TOP UI PANEL + REWARDS WINDOW + FLOATING DAMAGE NUMBERS
# ---------------------------------------------------------------------------
# Per Stage 8 spec: 3 new feature groups added on top of Stage 7.
#
# 1) MAP top UI panel — slimmer than the BATTLE HUD (64px vs 86px), shows
#    player avatar + level + HP/MP bars + EXP bar + gold amount on the MAP
#    screen. This gives the player progression visibility before entering
#    battle.
#
# 2) Victory/Defeat Rewards Window — replaces the auto-return endgame text
#    with a phased state machine: "text" (1.5s) → "rewards" (modal, waits
#    for "ОК" click) → "done" (return to MAP). Player gains XP/gold on
#    victory; defeat gives 0 XP/gold. Level-up is detected + displayed.
#
# 3) Floating Damage Numbers — spawn at the impact point when a fighter
#    takes damage. Crits are larger, gold-colored, with "Крит!" suffix.

# Maximum player level. Per Stage 8 spec: enforced in PlayerState.gain_xp
# (don't level beyond 80, cap xp at level 80's xp_to_next).
MAX_LEVEL: int = 80

# --- Stage 37 — UI DIMENSIONS REFERENCE ---
# All window sizes in one place for easy tuning.
#
# Screen:        1280 × 720
# Top panel:     y=0,    h=64   → bottom edge = 64
# Bottom bar:    y=664,  h=56   → top edge = 664
# Available:     y=64 to y=664 = 600px for modals
#
# Char sheet:    w=310, h=580 → y=(720-580)/2=70, bottom=650 < 664 ✓
# Inventory:     w=740, h=560 → y=(720-560)/2=80, bottom=640 < 664 ✓
# Skills modal:  w=380, h=392 → y=(720-392)/2=164, bottom=556 < 664 ✓
# Forge modal:   w=900, h=560 → y=(720-560)/2=80, bottom=640 < 664 ✓
#
# When char sheet + inventory both open:
#   Char sheet:  x=20,  w=310 → right=330
#   Inventory:    x=340, w=740 → right=1080
#   Gap: 10px, no overlap ✓

# --- Stage 64/66 — INVENTORY PAGINATION constants ---
# Stage 145 — МИНИ-СЛОТЫ: сетка мини-ячеек 27px (gap 1) в inv_rect. Спаны
# предметов: оружие 2×3, броня/прочее 2×2, кольца/расходники 1×1.
# Stage 167 — 12 колонок (окно уже); вместимость 96 видимых мини-ячеек.
ITEMS_PER_PAGE: int = 128  # Stage 167 — НЕ менять на 96: старые сейвы
# (16-колоночная сетка) держат предметы в слотах 96-127, урезание списка
# их ТЕРЯЛО бы. Вместимость страницы гейтится визуально (_can_visually_fit
# считает INV_COLS × INV_MAX_ROWS).
# Stage 204 — INVENTORY_PAGE_COUNT удалён (0 чтений: страницы = INVENTORY_PAGE_KEYS).
INVENTORY_PAGE_KEYS: tuple[int, ...] = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
INV_COLS: int = 12        # Stage 167 — было 16 (запрос: сузить окно инвентаря)
INV_MAX_ROWS: int = 8     # Stage 145 — мини-ряды (16×8 = 128 мини)
INV_CELL: int = 27        # Stage 145 — мини-слот (было 57)
INV_GAP: int = 1           # Stage 145 — зазор мини-сетки
# Stage 183 — стакание расходников: максимум копий одного item_id в ячейке.
ITEM_STACK_MAX: int = 99
# Stage 160 — прозрачность drag-призрака (0-255). Призрак рисуется верхним
# левым углом НА КОНЧИКЕ курсора (запрос пользователя); прозрачность делает
# видимой подсветку зоны/цели дропа под предметом (вместо оффсета +28).
DRAG_GHOST_ALPHA: int = 160
# Stage 212 — «полёт» иконки в целевую ячейку после дропа (ease-out lerp).
# Дроп читается глазами: предмет доезжает из точки курсора до клетки, клетка
# на время полёта рисуется пустой. 120мс — ниже порога «заметной задержки».
INV_FLIGHT_MS: int = 120


def item_span(item: dict) -> tuple[int, int]:
    """Stage 145/146/148 — визуальный размер предмета в мини-ячейках (w, h).

    Stage 182 — БАФЫ-расходники 1×1 (slot="consumable" из get_buff_item).
    Оружие 2×3 (вертикальное), броня/голова/руки/пояс/обувь 2×2,
    АМУЛЕТЫ и КОЛЬЦА 1×1 (Stage 148 — амулет занимает 1 слот, как кольца;
    мелкие расходники 1×1 (type в item_db — Stage 146).
    """
    if not item:
        return (1, 1)
    if item.get("is_buff") or item.get("slot") == "consumable":
        return (1, 1)
    slot = item.get("slot", "")
    itype = item.get("type", "") or item.get("item_type", "")
    if slot == "weapon":
        return (2, 3)
    if slot == "ring" or itype in ("ring", "amulet"):
        return (1, 1)
    return (2, 2)


# Stage 204 — WEAPON_SPAN удалён (0 чтений: используйте item_span()).

# --- Stage 47 — FORGE (Кузница) constants ---
MAX_ENCHANT: int = 20                    # max enchant level per item
ENCHANT_COST_BASE: int = 100             # base gold cost for 0→1
ENCHANT_COST_GROWTH: float = 1.15        # cost = BASE * (current_level + 1) ^ GROWTH
ENCHANT_STAT_MULTIPLIER: float = 0.05    # Stage 115 — +5% per enchant level (was 0.5 = +50%)

# --- Stage 138 — SYNTH (Синтез костюмов) + WARDROBE (Гардероб) constants ---
# Заточка костюма: главный (+N) + 2 катализатора (+0, та же модель) = шанс +N+1.
# Провал: сгорают ТОЛЬКО 2 катализатора, главный остаётся (можно пробовать снова).
# Шанс ступени +N -> +N+1: 92 - 3*N, кламп [2..92].
#   +0->+1: 92% · +1->+2: 89% (по ТЗ) · +14->+15: 50% · +30->+31: 2%
# Требуемый уровень игрока: до +15 линейно 0..42; +16..+31 линейно 42..80.
# Рост base_stats (Сила/Ловк/Вын): * (1 + 0.03*N) — на +31 почти удвоение.
# Матожидание полной заточки до +31 ≈ 220 базовых костюмов +0.
OUTFIT_SYNTH_MAX_PLUS: int = 31
OUTFIT_SYNTH_CHANCE_BASE: int = 92      # шанс 0->1
OUTFIT_SYNTH_CHANCE_STEP: int = 3       # -3% за ступень
OUTFIT_SYNTH_CHANCE_FLOOR: int = 2      # минимальный шанс
# Stage 165 — +10% к base_stats костюма за ступень (запрос пользователя:
# «статы были 10 15 8, стали выше, например 11 17 9»). 3% не давали видимого
# прироста на малых статах (int(10*1.03) == 10). Округление — половина вверх
# (int(x + 0.5)), чтобы 15*1.1 давало 17, а 8*1.1 — 9.
OUTFIT_SYNTH_STAT_PER_PLUS: float = 0.10  # +10% к base_stats костюма за ступень
OUTFIT_SYNTH_REQ_LEVEL_15: int = 42      # треб. уровень на +15
OUTFIT_SYNTH_REQ_LEVEL_MAX: int = 80     # треб. уровень на +31 (= MAX_LEVEL)


def outfit_synth_chance(current_plus: int) -> int:
    """Stage 138 — шанс синтеза ступени current_plus -> +1 (проценты 2..92)."""
    ch = OUTFIT_SYNTH_CHANCE_BASE - OUTFIT_SYNTH_CHANCE_STEP * current_plus
    return max(OUTFIT_SYNTH_CHANCE_FLOOR, ch)


def outfit_synth_required_level(plus: int) -> int:
    """Stage 138 — требуемый уровень игрока для костюма +plus.

    +0..+15: линейно 1 -> 42 (по ТЗ: +15 требует 42).
    +16..+31: линейно 42 -> 80.
    Stage 165 — минимум 1 (тултип костюма показывает «Треб. уровень 1»
    для +0; все игроки имеют уровень >= 1, семантика доступа не меняется).
    """
    if plus <= 0:
        return 1
    if plus >= OUTFIT_SYNTH_MAX_PLUS:
        return OUTFIT_SYNTH_REQ_LEVEL_MAX
    if plus <= 15:
        return round(plus * OUTFIT_SYNTH_REQ_LEVEL_15 / 15)
    span = OUTFIT_SYNTH_MAX_PLUS - 15
    return round(OUTFIT_SYNTH_REQ_LEVEL_15
                 + (plus - 15) * (OUTFIT_SYNTH_REQ_LEVEL_MAX - OUTFIT_SYNTH_REQ_LEVEL_15) / span)


def outfit_synth_stat_multiplier(plus: int) -> float:
    """Stage 138 — множитель base_stats костюма на ступени plus."""
    return 1.0 + OUTFIT_SYNTH_STAT_PER_PLUS * max(0, plus)

# Гардероб: 5 вертикальных слотов-хранилищ под костюмы на страницу,
# Stage 167 — 5 страниц (25 слотов) с пагинацией снизу окна.
WARDROBE_SLOTS: int = 25
WARDROBE_SLOTS_PER_PAGE: int = 5
WARDROBE_PAGES: int = 5

# --- Stage 51 — GEM SYSTEM (Камни) constants ---
MAX_GEM_LEVEL: int = 10                  # max gem upgrade level
MAX_GEM_SLOTS_PER_ITEM: int = 3          # max gem slots per weapon/gear
GEM_UPGRADE_COST_BASE: int = 50           # base gold cost for gem 1→2
GEM_UPGRADE_COST_GROWTH: float = 1.3     # cost = BASE * level ^ GROWTH
# Gem upgrade success chance decreases per level.
# Level 1→2 = 100%, each subsequent level: chance = max(10, 100 - (level-1)*10)
# So: 1→2=100%, 2→3=90%, 3→4=80%, ..., 9→10=20%
GEM_UPGRADE_CHANCE_BASE: int = 100
GEM_UPGRADE_CHANCE_DECAY: int = 10       # -10% per level above 1
GEM_UPGRADE_CHANCE_FLOOR: int = 10       # min 10% success
# Synthesis: combining 2 gems of same level → 1 gem of level+1.
# Success chance: 2 gems of level N → gem of level N+1, chance = 60% (flat).
# Example: weapon_wooden (base atk 3-5) at enchant 5:
#   scaled_atk = 3 * (1 + 5 * 0.5) = 3 * 3.5 = 10.5 → 10
#   enchant 10: 3 * (1 + 10 * 0.5) = 3 * 6 = 18
#   enchant 20: 3 * (1 + 20 * 0.5) = 3 * 11 = 33

# --- MAP top UI panel ---
# Stage 161 — панель сжата 64→52 (запрос пользователя): аватар 48→40,
# HP-бар 16→14, MP-бар 12→10, миникарта 120×56 → 110×46. Оступы/геометрия
# в _render_map_panel считаются от констант — больше нигде 64 не хардкодится.
MAP_PANEL_HEIGHT: int = 52
MAP_PANEL_BG: tuple[int, int, int] = (24, 24, 27)            # zinc-900
MAP_PANEL_BORDER: tuple[int, int, int] = (234, 179, 8)       # gold accent
MAP_AVATAR_SIZE: int = 40
MAP_HP_BAR_W: int = 200
# Stage 165 — «пирамида» полос вне боя (запрос пользователя): HP самая
# длинная, MP немного короче, EXP ещё немного короче. Значения не меняются —
# только визуальная ширина.
MAP_MP_BAR_W: int = 185  # Stage 167 — меньше разница «пирамиды» (было 170)
MAP_EXP_BAR_W: int = 170  # Stage 167 — меньше разница «пирамиды» (было 140)
MAP_HP_BAR_H: int = 14
MAP_MP_BAR_H: int = 10

# --- Stage 34 — Bottom UI bar (skills + inventory icons) ---
BOTTOM_BAR_HEIGHT: int = 56
BOTTOM_BAR_BORDER: tuple[int, int, int] = (63, 63, 70)      # zinc-700
BOTTOM_BAR_ICON_SIZE: int = 40
BOTTOM_BAR_ICON_GAP: int = 16
MAP_EXP_BAR_H: int = 10
MAP_EXP_BAR_BG: tuple[int, int, int] = (39, 39, 42)         # zinc-800
MAP_GOLD_ICON_COLOR: tuple[int, int, int] = (234, 179, 8)   # gold-500
MAP_GOLD_TEXT_COLOR: tuple[int, int, int] = (250, 204, 21)  # yellow-400
MAP_LEVEL_TEXT_COLOR: tuple[int, int, int] = (234, 179, 8)  # gold-500

# --- Stage 87 — UI polish: HP pulse + modal padding + card hover ---
HP_PULSE_FREQ_HZ: float = 1.0          # 1 Hz pulse — 1 cycle per second
HP_PULSE_RATIO: float = 0.25           # trigger pulse when HP < 25% of max
HP_PULSE_MIN: float = 0.55             # min brightness multiplier (darker phase)
HP_PULSE_MAX: float = 1.0              # max brightness multiplier (brighter phase)
MODAL_CONTENT_PADDING: int = 16        # standard content padding inside modals (p-4)
# Stage 204 — MODAL_GRID_PADDING удалён (0 чтений).
# Hover state for clickable cards (mob card on MAP screen).
MAP_CARD_HOVER_BG: tuple[int, int, int] = (39, 39, 42)      # zinc-800 (lighter than zinc-900)
MAP_CARD_HOVER_BORDER: tuple[int, int, int] = (234, 179, 8) # gold border on hover
# Stage 155 — hover-эффект: мягкое золотое свечение НАРУЖУ (SRCALPHA-слои с
# затуханием) вместо сплошного «тень-прямоугольника» (10,10,12) и утолщения
# рамки. GLOW_PAD — насколько свечение выходит за карточку (дизайн-px),
# GLOW_ALPHA — альфа самого внутреннего слоя.
MAP_CARD_HOVER_GLOW_PAD: int = 5
MAP_CARD_HOVER_GLOW_ALPHA: int = 90
# Stage 159 — плавный hover: время перехода idle↔hover (секунды). Альфа
# свечения, фон и рамка карточки мобов интерполируются за это время
# (раньше эффект включался/выключался мгновенно — «слишком резко»).
MAP_CARD_HOVER_SEC: float = 0.14
# Legacy hover-«тень» — используется магазином и misc-модалками (Stage 87);
# Stage 204 — MAP_CARD_HOVER_SHADOW удалён (0 чтений; цвет тени инлайн у потребителей).
MAP_CARD_HOVER_SHADOW_INSET: int = 4

# --- Endgame rewards window (Stage 8 — replaces 2.0s auto-return) ---
# Phase 1: "text" — show "Победа" or "Поражение" for ENDGAME_TEXT_DURATION.
# Phase 2: "rewards" — show modal window (width × height) with rewards.
# Phase 3: "done" — return to MAP via _exit_battle.
ENDGAME_TEXT_DURATION: float = 2.0   # seconds — Phase 1 text duration (Stage 71: 1.5→2.0 to let death anim play)
ENDGAME_WINDOW_W: int = 400
ENDGAME_WINDOW_H: int = 320
ENDGAME_WINDOW_BG: tuple[int, int, int] = (24, 24, 27)         # zinc-900
ENDGAME_WINDOW_BORDER: tuple[int, int, int] = (234, 179, 8)    # gold-500
ENDGAME_WINDOW_RADIUS: int = 12
ENDGAME_OK_BTN_W: int = 360
ENDGAME_OK_BTN_H: int = 44
ENDGAME_OK_BTN_BG: tuple[int, int, int] = (16, 185, 129)      # emerald-500
ENDGAME_OK_BTN_BG_HOVER: tuple[int, int, int] = (52, 211, 153)  # emerald-400
ENDGAME_OK_BTN_FG: tuple[int, int, int] = (255, 255, 255)
ENDGAME_WIN_COLOR: tuple[int, int, int] = (234, 179, 8)        # gold-500
ENDGAME_LOSE_COLOR: tuple[int, int, int] = (220, 38, 38)      # red-600
ENDGAME_LEVELUP_COLOR: tuple[int, int, int] = (16, 185, 129)  # emerald-500
ENDGAME_GOLD_COLOR: tuple[int, int, int] = (250, 204, 21)      # yellow-400

# --- Floating damage numbers (Stage 8) ---
DAMAGE_NUMBER_MAX_COUNT: int = 20      # cap to avoid clutter
DAMAGE_NUMBER_LIFE_MIN: float = 1.0     # seconds
DAMAGE_NUMBER_LIFE_MAX: float = 1.5
DAMAGE_NUMBER_CRIT_LIFE_MIN: float = 1.5
DAMAGE_NUMBER_CRIT_LIFE_MAX: float = 2.0
DAMAGE_NUMBER_VY_MIN: float = -90.0     # px/s — upward (negative = up)
DAMAGE_NUMBER_VY_MAX: float = -60.0
DAMAGE_NUMBER_JITTER: float = 10.0      # ±px horizontal jitter on spawn
DAMAGE_NUMBER_FONT_SIZE: int = 35     # Stage 9.1: was 80 (Stage 9), 20 (Stage 8 orig)
DAMAGE_NUMBER_CRIT_FONT_SIZE: int = 60  # Stage 9.1: was 128 (Stage 9), 32 (Stage 8 orig)
DAMAGE_NUMBER_COLOR: tuple[int, int, int] = (255, 255, 255)      # white
DAMAGE_NUMBER_CRIT_COLOR: tuple[int, int, int] = (234, 179, 8)   # gold-500
DAMAGE_NUMBER_POISON_COLOR: tuple[int, int, int] = (120, 200, 80)  # Stage 134 — poison DoT ticks
# Custom TTF font for damage numbers (user-provided, in fonts/ folder).
DAMAGE_NUMBER_FONT: str = "Ninja Naruto.ttf"
# Stage 9 (per user request): raised 150px higher (was -60, now -210).
# Damage numbers spawn at SPRITE_BASE_Y + DAMAGE_NUMBER_IMPACT_Y_OFFSET.
# With SPRITE_BASE_Y=740 (Stage 9) and offset=-210, spawn y = 740-210 = 530
# (was 540-60 = 480 in Stage 8). Combined with the 4× larger fonts, damage
# numbers are now much more visible and float higher above the impact point.
DAMAGE_NUMBER_IMPACT_Y_OFFSET: int = -210   # raised 150px higher (Stage 9: was -60)


# ---------------------------------------------------------------------------
# STAGE 9 — SKILLS UI (char sheet grid + MAP skills modal)
# ---------------------------------------------------------------------------
# Per Stage 9 spec (Fix 5):
#   * 10 skills slots arranged 5 columns × 2 rows in the character sheet.
#   * Slot 0 (top-left) is a placeholder skill (procedural colored square
#     with "S" letter — emerald bg). Slots 1-9 are empty (locked appearance).
#   * On the MAP screen, a circular "Навыки" button at bottom-right opens
#     a small modal showing the same 10-slot grid + "Закрыть" button.

# Skills grid geometry.
SKILLS_SLOT_SIZE: int = 40        # px — square slot
SKILLS_SLOT_GAP: int = 6          # px — gap between slots
SKILLS_GRID_COLS: int = 5
SKILLS_GRID_ROWS: int = 2
# Total grid width = 5 * 40 + 4 * 6 = 224 px.
SKILLS_GRID_W: int = SKILLS_GRID_COLS * SKILLS_SLOT_SIZE + (SKILLS_GRID_COLS - 1) * SKILLS_SLOT_GAP
SKILLS_GRID_H: int = SKILLS_GRID_ROWS * SKILLS_SLOT_SIZE + (SKILLS_GRID_ROWS - 1) * SKILLS_SLOT_GAP

# Slot colors (Stage 9 INFERRED — design choice).
SKILLS_SLOT_EMPTY_BG: tuple[int, int, int] = (39, 39, 42)         # zinc-800 (empty)
SKILLS_SLOT_EMPTY_BORDER: tuple[int, int, int] = (82, 82, 91)    # zinc-600 (empty border)
SKILLS_SLOT_ACTIVE_BG: tuple[int, int, int] = (16, 185, 129)     # emerald-500 (active skill)
SKILLS_SLOT_LABEL_COLOR: tuple[int, int, int] = (234, 179, 8)   # gold-500 ("Навыки" label)
# Stage 14 — INACTIVE skill slot colors (skill is in the deck but currently
# disabled via the toggle). Reuses zinc-800 bg + zinc-600 border so the
# slot looks "switched off" vs the emerald "active" appearance. The icon
# is rendered at 50% opacity via set_alpha (see _render_skills_grid).
SKILLS_SLOT_INACTIVE_BG: tuple[int, int, int] = (39, 39, 42)         # zinc-800 (dimmed)
SKILLS_SLOT_INACTIVE_BORDER: tuple[int, int, int] = (82, 82, 91)     # zinc-600 (dimmed)
SKILLS_SLOT_INACTIVE_ICON_ALPHA: int = 128                            # 50% opacity

# MAP skills button (circular, bottom-right).
# Stage 204 — SKILLS_BTN_RADIUS/BG/BG_HOVER/FG удалены (0 чтений: кнопка
# «Навыки» рисуется из MAP/bottom-bar констант).

# Skills modal window (centered, smaller than char sheet).
# Stage 10.1: SKILLS_MODAL_H bumped from 200 → 280 (+80 px) to add a 70 px
# tooltip area at the top (between the title and the skill grid). The tooltip
# shows the hovered skill's name + description + stats; when no slot is
# hovered, a dim placeholder text is shown.
#
# Stage 11 UI FIX 1: SKILLS_MODAL_W bumped from 280 → 380 (+100 px) so the
# Crystal Blade tooltip description ("Расходует 35 MP, увеличивает урон на
# 40% (×1.4), с шансом 40% замораживает врага на 2 хода.") fits on 2-3
# wrapped lines instead of overflowing the modal + overlapping the skill
# icons. SKILLS_TOOLTIP_MAX_LINE_WIDTH bumped from 40 → 50 chars per line
# to take advantage of the wider modal (fewer wrapped lines, easier read).
#
# Stage 14 — SKILLS_MODAL_H bumped ×1.4 from 280 → 392 (+112 px) to add
# room for an "active skills legend" below the grid + extra space for
# click-to-toggle affordance on each skill slot. The grid now has
# interactive slots (click to enable/disable a skill); the legend explains
# the color coding (emerald = active, dimmed = disabled).
SKILLS_MODAL_W: int = 380  # Stage 11: was 280 (+100 for tooltip overflow fix)
SKILLS_MODAL_H: int = 392
SKILLS_TOOLTIP_AREA_H: int = 120
SKILLS_TOOLTIP_PLACEHOLDER_COLOR: tuple[int, int, int] = (113, 113, 122)  # zinc-500
SKILLS_TOOLTIP_TITLE_COLOR: tuple[int, int, int] = (234, 179, 8)          # gold-500
SKILLS_TOOLTIP_DESC_COLOR: tuple[int, int, int] = (244, 244, 245)         # zinc-100
SKILLS_TOOLTIP_STATS_COLOR: tuple[int, int, int] = (250, 204, 21)        # yellow-400
SKILLS_TOOLTIP_MAX_LINE_WIDTH: int = 50  # Stage 11: was 40 (+10 for wider modal)
SKILLS_MODAL_BG: tuple[int, int, int] = (24, 24, 27)            # zinc-900
SKILLS_MODAL_BORDER: tuple[int, int, int] = (234, 179, 8)       # gold-500
SKILLS_MODAL_RADIUS: int = 12
SKILLS_MODAL_TITLE_COLOR: tuple[int, int, int] = (234, 179, 8) # gold-500
# Stage 204 — SKILLS_MODAL_CLOSE_* удалены (0 чтений: Х-кнопки рисует
# общий _draw_close_x_square на UI_THEME).


# ---------------------------------------------------------------------------
# DEBUFF ICON POSITIONING (Stage 12.1 — extracted for easy user tuning)
# ---------------------------------------------------------------------------
# These constants control WHERE debuff icons appear above a fighter's head.
# Adjust these values to change the position, size, and spacing of debuff
# icons. All measurements are in pixels.
#
# TO CUSTOMIZE: edit these constants in config.py, then restart the game.
# No code changes needed — _render_fighter reads these directly.

DEBUFF_ICON_SIZE: int = 32           # Size of each debuff icon (px, square)
DEBUFF_ICON_GAP: int = 4             # Horizontal gap between icons when multiple (px)
# Stage 204 — DEBUFF_ICON_Y_OFFSET/CENTERED/LEFT_PADDING удалены (0 чтений:
# иконки статусов рендерятся по _render_hud_status_icons).


# ---------------------------------------------------------------------------
# STAGE 10.1 — SKILL CONFIGURATION (centralized for easy tuning)
# ---------------------------------------------------------------------------
# Stage 11 REFACTOR: SKILL_CONFIG is now DERIVED from
# combat.skill_registry.SKILL_REGISTRY — the registry is the new single
# source of truth for skill definitions. SKILL_CONFIG is kept as a
# backward-compat dict for existing code that reads it (e.g., the tooltip
# renderer in pygame_ui.py). It mirrors the registry's data, extracting the
# "freeze_chance" / "freeze_duration" from the registry's on_hit_effects.
#
# To tune a skill or add a new one, edit
# combat.skill_registry.SKILL_REGISTRY — SKILL_CONFIG + CRYSTAL_BLADE_*
# constants below will automatically reflect the change.
#
# Per-skill keys in SKILL_CONFIG (backward-compat shape):
#   name                — display name (RU) shown in tooltips + combat log
#   role_id             — which role can use this skill (1 = Ichigo)
#   mp_cost             — MP deducted from attacker on trigger (0 = no MP cost)
#   trigger_chance      — 0..1 chance per turn (when MP >= cost)
#   freeze_chance       — 0..1 chance to freeze on trigger (0 = no freeze)
#   freeze_duration     — turns the target is frozen (skipped)
#   damage_multiplier   — multiplier applied to base damage roll (1.0 = no boost)
#   description         — tooltip description text (RU)


def _build_skill_config_from_registry() -> "dict[int, dict]":
    """Build the backward-compat SKILL_CONFIG dict from SKILL_REGISTRY.

    Stage 11 — extracts the freeze_chance / freeze_duration from each
    skill's on_hit_effects["freeze"] entry (if present). The role_id is
    inferred from the skill_id (currently only Ichigo's skills are
    registered, so role_id=1 for all known skills). For unknown skill_ids,
    role_id defaults to 0 (no role restriction).
    """
    # Lazy import to avoid circular dependency at module load time
    # (skill_registry imports only stdlib, so this is safe, but config
    # is the lowest layer — keep the import local to avoid any chance
    # of cycle if skill_registry ever imports config).
    from pockie_rpg.combat.skill_registry import SKILL_REGISTRY

    # Map known skill_ids → role_id (Ichigo's skills).
    # Stage 13 — Ichigo now has 6 skills (added Fireball, Thunderstorm,
    # Poison Dart, Crystal Shield). All belong to role_id=1 (Ichigo).
    # Future: derive from Role.skills instead of hardcoding here.
    _ROLE_BY_SKILL: dict[int, int] = {
        12006: 1,  # Crystal Blade — Ichigo only.
        15005: 1,  # Lightning Step — Ichigo only (Stage 12).
        10001: 1,  # Fireball — Ichigo only (Stage 13).
        14001: 1,  # Thunderstorm — Ichigo only (Stage 13).
        18003: 1,  # Poison Dart — Ichigo only (Stage 13).
        14002: 1,  # Crystal Shield — Ichigo only (Stage 13).
    }

    config: dict[int, dict] = {}
    for skill_id, skill in SKILL_REGISTRY.items():
        # Stage 11 — the freeze effect is named "freeze" in on_hit_effects
        # (the effect name that gets applied to StatusManager). Extract its
        # chance + duration for the backward-compat SKILL_CONFIG shape.
        freeze_params = skill.on_hit_effects.get("freeze", {})
        config[skill_id] = {
            "name": skill.name,
            "role_id": _ROLE_BY_SKILL.get(skill_id, 0),
            "mp_cost": skill.mp_cost,
            "trigger_chance": skill.trigger_chance,
            "freeze_chance": freeze_params.get("chance", 0.0),
            "freeze_duration": freeze_params.get("duration", 0),
            "damage_multiplier": skill.damage_multiplier,
            "description": skill.description,
        }
    return config


SKILL_CONFIG: dict[int, dict] = _build_skill_config_from_registry()


# Crystal Blade — Stage 204: алиасы-константы CRYSTAL_BLADE_* удалены (0 чтений:
# боевой движок читает SKILL_REGISTRY/skill-объекты; осталась только
# CRYSTAL_BLADE_FREEZE_DURATION — дефолт заморозки для fighter.py).
CRYSTAL_BLADE_FREEZE_DURATION: int = SKILL_CONFIG[12006]["freeze_duration"]

# Ice block overlay animation (Stage 10 — assets/extracted/ice_block/).
# 20 PNG frames at 163×136 each. Cycled at 8 FPS while active.
#
# Stage 10.1: ice block render size bumped ×2 (from 90×135 = BODY_SPRITE_W×H
# to 180×270). The larger overlay fully covers the fighter sprite for a more
# dramatic freeze visual. Center the ice block on the fighter's center.
#
# Stage 10.2: width +30% (180 → 234) per user request ("ice block +30%"
# — more visible, covers more horizontal space). Height unchanged (270).
ICE_BLOCK_FOLDER: str = "effects/ice_block"
ICE_BLOCK_FPS: int = 8
# Stage 10.2 — width ×1.3 (180 → 234). Height unchanged.
# Stage v132.1 — resized to match the shield dome (280×210) so both status
# overlays share the same footprint and sit on the ground consistently.
ICE_BLOCK_RENDER_W: int = 280
ICE_BLOCK_RENDER_H: int = 210
# Position offsets for the LOOPING ice block overlay (bound to the fighter's
# actual_x). centerY = SPRITE_BASE_Y - ICE_BLOCK_RENDER_H//2 + ICE_BLOCK_Y_OFFSET
# — the block "stands on the ground" and follows the fighter when it runs.
ICE_BLOCK_X_OFFSET: int = 5    # small rightward shift off the fighter center
ICE_BLOCK_Y_OFFSET: int = 25   # tweak so the base sits at the ground line


# ---------------------------------------------------------------------------
# STAGE 13 — EFFECT OVERLAYS (shield dome + poison + storm cloud + fireball)
# ---------------------------------------------------------------------------
# These are overlay animations rendered on top of a fighter when the
# corresponding status is active. Same pattern as ICE_BLOCK_* constants
# above (folder + FPS + render size).

# Shield dome overlay (Crystal Shield skill, 14002). 12 frames at 207×177
# each (shield_dome_effect). Rendered centered on the fighter while the
# "shield" status is active. Slightly larger than the sprite (×2 size)
# so the dome visibly surrounds the fighter.
SHIELD_DOME_FOLDER: str = "effects/shield_dome"
SHIELD_DOME_FPS: int = 8
# Stage v132.1 — resized 340×270 → 280×210 (same footprint as the ice block)
# and re-anchored to the fighter's actual_x so the dome follows the caster
# during run/hit-shake instead of floating on the base spawn point.
SHIELD_DOME_RENDER_W: int = 280
SHIELD_DOME_RENDER_H: int = 210
# Position offsets for the LOOPING shield dome overlay (bound to the fighter's
# actual_x). centerY = SPRITE_BASE_Y - SHIELD_DOME_RENDER_H//2 + SHIELD_DOME_Y_OFFSET
# — the dome "stands on the ground" and follows the caster when it moves.
SHIELD_DOME_X_OFFSET: int = -8   # small leftward shift off the fighter center
SHIELD_DOME_Y_OFFSET: int = 25   # tweak so the base sits at the ground line

# Storm cloud overlay (Thunderstorm skill, 14001). 6 frames at 155×71.
# Rendered above the fighter's head while the "thunder_cloud" status is
# active (cloud hovers over the target).
STORM_CLOUD_FOLDER: str = "effects/storm_cloud"
STORM_CLOUD_FPS: int = 6
STORM_CLOUD_RENDER_W: int = 180  # wide enough to hover over the fighter
STORM_CLOUD_RENDER_H: int = 80   # short height (cloud band)

# Poison overlay (Poison Dart skill, 18003). 15 frames. Rendered on top of
# the poisoned fighter (poison dripping visual).
POISON_OVERLAY_FOLDER: str = "effects/poison"
POISON_OVERLAY_FPS: int = 10
POISON_OVERLAY_RENDER_W: int = 120
POISON_OVERLAY_RENDER_H: int = 180

# Fireball overlay (Fireball skill, 10001). 25 frames at 722×361. Rendered
# on the TARGET during the cast (projectile visual). Only plays once per cast
# (not looping — the fireball flies once and is gone).
FIREBALL_OVERLAY_FOLDER: str = "effects/fireball"
# Stage 204 — FIREBALL_OVERLAY_FPS/RENDER_W/RENDER_H удалены (0 чтений:
# полёт файрбола играет ProjectileEffect со своими параметрами cast-секции).


# ---------------------------------------------------------------------------
# STAGE 14/189 — CAST EFFECT (one-shot) параметры файрбола — читает
# combat_replay (старт полёта, размер, FPS). Параметры остальных скиллов
# (storm cloud/shield dome/poison) удалены в Stage 204 — словарь
# _CAST_EFFECT_PARAMS в effects.py был мёртвым (0 чтений); они же были
# единственными читателями CAST_STORM_CLOUD_*/CAST_SHIELD_DOME_*/CAST_POISON_*.
# ---------------------------------------------------------------------------
# Position offsets from SPRITE_BASE_Y (negative = up on screen).
CAST_FIREBALL_Y_OFFSET: int = -100     # fireball lands at chest height on target
# Horizontal offset of the fireball's spawn point in FRONT of the caster
# (toward the enemy). Player casters add it (+X), enemy casters subtract it (-X),
# so the fireball appears ahead of the character instead of on top of it.
CAST_FIREBALL_CAST_OFFSET_X: int = 120   # fireball spawns 120px ahead of the caster (Stage 170: комментарий синхронизирован со значением)
CAST_FIREBALL_W: int = 300
CAST_FIREBALL_H: int = 200
CAST_FIREBALL_FPS: int = 15


# ---------------------------------------------------------------------------
# Stage 15 — TEST BATTLE MODE (skill debugging UI)
# ---------------------------------------------------------------------------
# A test/debug state where the player can manually trigger any skill to
# visually verify each one works (cast animation, status effect, damage
# number, etc.).
#
# Behavior:
#   * No countdown, no autobattle, no endgame, no speed buttons.
#   * Player MP refilled to max every frame (infinite MP).
#   * Enemy HP refilled to max if it drops below 1 (immortal enemy).
#   * The ONLY way to exit is clicking the "ВЫЙТИ" button (or ESC).
#   * Skill buttons at center of screen, clickable, each triggers one skill.
#
# Skill button layout (per Stage 15 spec):
#   * Each button = 80x80 px icon, with skill name + MP cost text below.
#   * Buttons in a horizontal row, centered horizontally + vertically.
#   * Total width = N x 80 + (N-1) x 10 (gap).
#   * For 6 skills: 6*80 + 5*10 = 530 px, centered at x = (1280-530)/2 = 375.
#   * Y position: center of screen ~y = 360 (above combat log).

TEST_SKILL_BTN_SIZE: int = 80          # skill button icon size (square)
TEST_SKILL_BTN_GAP: int = 10           # gap between buttons (px)
TEST_SKILL_BTN_Y: int = 360             # vertical center of skill buttons row
TEST_SKILL_BTN_NAME_FONT: int = 12     # skill name text below icon (bold)
TEST_SKILL_BTN_COST_FONT: int = 11     # MP cost text below name

# "ВЫЙТИ" (exit) button — large red, at bottom-right of battle screen.
TEST_EXIT_BTN_W: int = 120
TEST_EXIT_BTN_H: int = 44
TEST_EXIT_BTN_BG: tuple[int, int, int] = (220, 38, 38)          # red-600
TEST_EXIT_BTN_BG_HOVER: tuple[int, int, int] = (248, 113, 113)   # red-400
TEST_EXIT_BTN_FG: tuple[int, int, int] = (255, 255, 255)        # white text

# Skill button background colors (active + hover) — emerald accent
# matches the SPEED_BTN / SKILLS_BTN style for visual consistency.
TEST_SKILL_BTN_BG: tuple[int, int, int] = (39, 39, 42)             # zinc-800
TEST_SKILL_BTN_BG_HOVER: tuple[int, int, int] = (63, 63, 70)      # zinc-700
TEST_SKILL_BTN_BORDER: tuple[int, int, int] = (82, 82, 91)        # zinc-600
TEST_SKILL_BTN_BORDER_HOVER: tuple[int, int, int] = (234, 179, 8)  # gold
TEST_SKILL_BTN_NAME_COLOR: tuple[int, int, int] = (244, 244, 245)  # zinc-100
TEST_SKILL_BTN_COST_COLOR: tuple[int, int, int] = (250, 204, 21)  # yellow-400

# "ТЕСТ" entry button on the MAP screen (next to the skills button at
# bottom-right, but offset to the LEFT so it doesn't overlap).
TEST_ENTRY_BTN_W: int = 120
TEST_ENTRY_BTN_H: int = 44
TEST_ENTRY_BTN_BG: tuple[int, int, int] = (113, 113, 122)         # zinc-500 (debug)
TEST_ENTRY_BTN_BG_HOVER: tuple[int, int, int] = (161, 161, 170)  # zinc-400
TEST_ENTRY_BTN_FG: tuple[int, int, int] = (24, 24, 27)            # zinc-900 (dark text)

# Intro log line shown when entering TEST_BATTLE state.
TEST_BATTLE_INTRO_LOG: str = (
    "ТЕСТ РЕЖИМ: бесконечная мана, бессмертный враг. "
    "Нажмите кнопку навыка для проверки анимации."
)

# Log line prefix shown after triggering a skill in TEST_BATTLE.
TEST_BATTLE_TRIGGER_LOG: str = "[ТЕСТ] "


# ---------------------------------------------------------------------------
# COMPAT SHIM
# ---------------------------------------------------------------------------

# Allow `python -m pockie_rpg.main` from project root after `pip install -e .`
# by ensuring src/ is on sys.path when running from source tree without install.
_SRC_DIR: Path = Path(__file__).resolve().parents[1]
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


# ---------------------------------------------------------------------------
# Stage 168 (аудит 5.1) — BACKWARD-COMPAT RE-EXPORTS
# ---------------------------------------------------------------------------
# Боевая математика переехала в pockie_rpg.combat.formulas (модуль не зависит
# от config — разорвана циклическая зависимость «combat → config»). Все имена
# ре-экспортируются здесь, поэтому существующие импорты вида
#   from pockie_rpg.config import calc_hit_rating, RATING_PCT_STEP, ...
# продолжают работать БЕЗ правок. Новый код должен импортировать из
# pockie_rpg.combat.formulas напрямую.
from pockie_rpg.combat.formulas import (  # noqa: E402,F401
    BASE_HIT_CHANCE,
    BLOCK_DAMAGE_MULTIPLIER,
    CRIT_BASE_DAMAGE_PCT,
    CRIT_CHANCE_STEP,
    CRIT_DAMAGE_STEP,
    DEFAULT_BMV_PRICE_AGI,
    DEFAULT_BMV_PRICE_STA,
    DEFAULT_BMV_PRICE_STR,
    DEFAULT_GROWTH_AGI,
    DEFAULT_GROWTH_AGI_MAX,
    DEFAULT_GROWTH_STA,
    DEFAULT_GROWTH_STA_MAX,
    DEFAULT_GROWTH_STR,
    DEFAULT_GROWTH_STR_MAX,
    DEFENSE_BREAK_CONSTANT,
    HIT_CAP_PCT,
    HIT_FLOOR_PCT,
    RATING_PCT_STEP,
    SPEED_BASE_FLOAT,
    STA_TO_DEF,
    STA_TO_HP,
    STR_THRESHOLD_FOR_HIT,
    STR_TO_ATK,
    apply_block_stage,
    apply_crit_stage,
    apply_defense_stage,
    apply_pct_bonus,
    calc_atk_mul_pct,
    calc_block_rating,
    calc_crit_rating,
    calc_dodge_rating,
    calc_hit_rating,
    calc_pierce_rating,
    calc_speed,
    calc_tough_rating,
    collect_rating_pct,
    combat_hit_chance,
    rating_to_antiblock_pct,
    rating_to_block_chance,
    rating_to_crit_chance,
    rating_to_crit_damage,
    rating_to_tough_chance_reduction,
    rating_to_tough_damage_reduction,
)
