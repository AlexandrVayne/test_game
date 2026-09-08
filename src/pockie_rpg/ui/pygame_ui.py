"""PygameUI — main UI controller (MAP <-> BATTLE <-> TEST_BATTLE FSM).

Composition over a giant class: helper classes (IdleAnimator,
AttackSequence, particle/effect systems) live in dedicated modules, and
per-state behaviour is split into mixins (CombatReplayMixin,
BattleRendererMixin, MapRendererMixin, TestBattleMixin). PygameUI inherits
all mixins so every method stays accessible via self.
"""
from __future__ import annotations

import math
import random
import time

import pygame

from pockie_rpg.combat.fighter import Fighter
from pockie_rpg.config import (
    BATTLE_SPEED_DEFAULT,
    BATTLE_SPEEDS,
    CHAR_SHEET_ANIM_DURATION,
    COMBAT_LOG_ANIM_DURATION,
    COMBAT_LOG_EXPANDED_H,
    COMBAT_LOG_MAX_LINES,
    COUNTDOWN_FONT_SIZE,
    FPS,
    FRAMELESS_ENABLED,
    LOG_BAR_H,
    MAX_LEVEL,
    MOB_TO_MOTION,
    MODAL_SCALE_INVENTORY,
    NATIVE_MODAL_REGISTRY,
    POISON_OVERLAY_FOLDER,
    POISON_OVERLAY_FPS,
    POISON_OVERLAY_RENDER_H,
    POISON_OVERLAY_RENDER_W,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SHIELD_DOME_FOLDER,
    SHIELD_DOME_FPS,
    SHIELD_DOME_RENDER_H,
    SHIELD_DOME_RENDER_W,
    SLOT_MACHINE_COOLDOWN_SEC,
    SLOT_MACHINE_FACES,
    SLOT_MACHINE_PERFECT_GOLD_MULT,
    SLOT_MACHINE_POOL,
    SLOT_MACHINE_SPIN_SEC,
    SLOT_MACHINE_SPIN_SLOWDOWN_SEC,
    SLOT_MACHINE_SPIN_STOP_STAGGER,
    SLOT_MACHINE_SPIN_TICK,
    SOUND_ENABLED,
    STORM_CLOUD_FOLDER,
    STORM_CLOUD_FPS,
    STORM_CLOUD_RENDER_H,
    STORM_CLOUD_RENDER_W,
    WINDOW_TITLE,
    BattleMode,
    GameState,
    compute_ui_scale,
)
from pockie_rpg.data.quests_db import get_story_quest
from pockie_rpg.game.save_load import SaveManager, load_player_state
from pockie_rpg.game.state import (
    ENEMY_MOBS,
    ROLES,
    STARTER_SUITS,
    create_default_player,
)
from pockie_rpg.ui.animator import ClickRect, IdleAnimator
from pockie_rpg.ui.assets import AssetManager
from pockie_rpg.ui.combat_replay import CombatReplayMixin
from pockie_rpg.ui.effects import (
    CastEffect,
    EffectOverlay,
    IceBlockEffect,
    ProjectileEffect,
)
from pockie_rpg.ui.particles import DamageNumberSystem, ParticleSystem
from pockie_rpg.ui.render_battle import BattleRendererMixin
from pockie_rpg.ui.render_forge import ForgeRendererMixin
from pockie_rpg.ui.render_inventory import InventoryRendererMixin
from pockie_rpg.ui.render_las_noches import LasNochesRendererMixin
from pockie_rpg.ui.render_map import MapRendererMixin
from pockie_rpg.ui.render_misc_modals import MiscModalsRendererMixin
from pockie_rpg.ui.render_quests import QuestRendererMixin
from pockie_rpg.ui.render_quick_battle import QuickBattleRendererMixin
from pockie_rpg.ui.render_shop import ShopRendererMixin
from pockie_rpg.ui.render_skills_charsheet import SkillsCharSheetRendererMixin
from pockie_rpg.ui.render_slot_machine import SlotMachineRendererMixin
from pockie_rpg.ui.render_synth import SynthRendererMixin, WardrobeRendererMixin
from pockie_rpg.ui.render_test_panel import TestPanelRendererMixin
from pockie_rpg.ui.render_tower import TowerRendererMixin
from pockie_rpg.ui.render_world_boss import WorldBossRendererMixin
from pockie_rpg.ui.render_worldmap import WorldMapRendererMixin
from pockie_rpg.ui.scaling import ScalableRendererMixin
from pockie_rpg.ui.test_battle import TestBattleMixin


class PygameUI(
    ScalableRendererMixin,
    CombatReplayMixin,
    BattleRendererMixin,
    MapRendererMixin,
    WorldMapRendererMixin,
    WorldBossRendererMixin,
    SkillsCharSheetRendererMixin,
    QuickBattleRendererMixin,
    InventoryRendererMixin,
    ForgeRendererMixin,
    ShopRendererMixin,
    TowerRendererMixin,
    LasNochesRendererMixin,
    MiscModalsRendererMixin,
    SlotMachineRendererMixin,
    SynthRendererMixin,
    WardrobeRendererMixin,
    QuestRendererMixin,
    TestPanelRendererMixin,
    TestBattleMixin,
):
    """Main UI controller (MAP <-> BATTLE <-> TEST_BATTLE FSM)."""

    def __init__(self) -> None:
        pygame.init()
        if SOUND_ENABLED:
            try:
                pygame.mixer.init()
            except pygame.error:
                pass

        # Stage 139.2 — окно на весь рабочий стол, UI 1:1 в центре.
        # Экранная поверхность = реальный размер монитора; вся игра рисует
        # в буфер 1280×720 (self.screen), композит — в _present_fullscreen().
        try:
            desk_w, desk_h = pygame.display.get_desktop_sizes()[0]
        except Exception:
            desk_w, desk_h = SCREEN_WIDTH, SCREEN_HEIGHT
        if FRAMELESS_ENABLED:
            self._fullscreen_monitor = pygame.display.set_mode(
                (desk_w, desk_h), pygame.NOFRAME
            )
        else:
            self._fullscreen_monitor = pygame.display.set_mode(
                (desk_w, desk_h)
            )
        self.screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        self._fullscreen_game = self.screen
        # Stage 153 — слой legacy-оверлеев: когда БАЗОВЫЙ экран рисуется нативно
        # (MAP на 2К), немигрированные модалки пишутся в этот прозрачный буфер
        # 1280×720, затем он растягивается ×2 и накладывается на монитор.
        self._legacy_layer: pygame.Surface = pygame.Surface(
            (SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA
        )
        self._legacy_layer_scaled: pygame.Surface | None = None
        self._legacy_layer_used: bool = False
        # Stage 150/158 — Hi-DPI: нативный путь при ЦЕЛОЧИСЛЕННОМ масштабе
        # монитора (×2/×3 — см. compute_ui_scale). Иначе (окно 1280×720,
        # дробные разрешения типа 2048×1152 от Windows 125% без DPI-aware)
        # — legacy-режим с MODAL_SCALE=1.0 (один растяг, без shrink-мыла).
        try:
            _mon_w, _mon_h = self._fullscreen_monitor.get_size()
        except Exception:
            _mon_w, _mon_h = SCREEN_WIDTH, SCREEN_HEIGHT
        self._ui_scale: float = compute_ui_scale(_mon_w, _mon_h)
        # Stage 151 — текущий масштаб рендера (1.0 legacy-фаза; UI_SCALE
        # во время native-фазы в _render_native_overlays).
        self._render_scale: float = 1.0
        pygame.display.set_caption(WINDOW_TITLE)
        self.clock: pygame.time.Clock = pygame.time.Clock()
        # Stage 139.2 — композит-режим активен с запуска (окно = весь рабочий
        # стол, UI 1:1 в центре, вокруг блюр). _fullscreen_on = маркер режима
        # «окно на весь монитор» (F11 переключает с обычным окном 1280×720).
        self._fullscreen_on: bool = True
        self._fullscreen_bg: pygame.Surface | None = None
        # Stage 140 — снапшот фона локации (делается при входе в бой;
        # фон боя НЕ меняется — блюрится снимок места входа).
        self._battle_bg_snapshot: pygame.Surface | None = None

        self.font_title: pygame.font.Font = pygame.font.SysFont(
            "dejavusans,arial", 28, bold=True
        )
        self.font_subtitle: pygame.font.Font = pygame.font.SysFont(
            "dejavusans,arial", 18
        )
        self.font_body: pygame.font.Font = pygame.font.SysFont(
            "dejavusans,arial", 16
        )
        self.font_small: pygame.font.Font = pygame.font.SysFont(
            "dejavusans,arial", 13
        )
        self.font_vs: pygame.font.Font = pygame.font.SysFont(
            "dejavusans,arial", 22, bold=True
        )
        self.font_button: pygame.font.Font = pygame.font.SysFont(
            "dejavusans,arial", 18, bold=True
        )
        self.font_banner: pygame.font.Font = pygame.font.SysFont(
            "dejavusans,arial", 14, bold=True
        )
        self.font_countdown: pygame.font.Font = pygame.font.SysFont(
            "dejavusans,arial", COUNTDOWN_FONT_SIZE, bold=True
        )
        self.font_endgame: pygame.font.Font = pygame.font.SysFont(
            "dejavusans,arial", 60, bold=True
        )
        self.font_charsheet_title: pygame.font.Font = pygame.font.SysFont(
            "dejavusans,arial", 28, bold=True
        )
        # Stage 177 — шрифт ИМЕНИ в шапке окна характеристик (18px: «Черный
        # самурай» влезает в 279px рядом с «Ур.N»; 28px обрезался до «Черный с…»).
        self.font_charsheet_name: pygame.font.Font = pygame.font.SysFont(
            "dejavusans,arial", 18, bold=True
        )
        self.font_charsheet_level: pygame.font.Font = pygame.font.SysFont(
            "dejavusans,arial", 16, bold=True
        )
        self.font_charsheet_label: pygame.font.Font = pygame.font.SysFont(
            "dejavusans,arial", 13
        )
        self.font_charsheet_value: pygame.font.Font = pygame.font.SysFont(
            "dejavusans,arial", 13, bold=True
        )
        self.font_charsheet_close: pygame.font.Font = pygame.font.SysFont(
            "dejavusans,arial", 16, bold=True
        )
        self.font_speed_btn: pygame.font.Font = pygame.font.SysFont(
            "dejavusans,arial", 14, bold=True
        )
        self.font_skills_label: pygame.font.Font = pygame.font.SysFont(
            "dejavusans,arial", 12, bold=True
        )
        self.font_skills_letter: pygame.font.Font = pygame.font.SysFont(
            "dejavusans,arial", 18, bold=True
        )
        self.font_skills_modal_title: pygame.font.Font = pygame.font.SysFont(
            "dejavusans,arial", 18, bold=True
        )
        self.font_skills_modal_close: pygame.font.Font = pygame.font.SysFont(
            "dejavusans,arial", 14, bold=True
        )
        self.font_skills_btn_letter: pygame.font.Font = pygame.font.SysFont(
            "dejavusans,arial", 24, bold=True
        )
        self.font_skills_tooltip_title: pygame.font.Font = pygame.font.SysFont(
            "dejavusans,arial", 14, bold=True
        )
        self.font_skills_tooltip_desc: pygame.font.Font = pygame.font.SysFont(
            "dejavusans,arial", 11
        )
        self.font_skills_tooltip_stats: pygame.font.Font = pygame.font.SysFont(
            "dejavusans,arial", 10
        )

        self.asset_manager: AssetManager = AssetManager()

        loaded = load_player_state()
        if loaded is not None:
            self.player = loaded
            if self.player.level < 1:
                self.player.level = 1
            if self.player.level > MAX_LEVEL:
                self.player.level = MAX_LEVEL
            if self.player.xp < 0:
                self.player.xp = 0
            if self.player.gold < 0:
                self.player.gold = 0
            _player_role = ROLES.get(self.player.role_id)
            if _player_role is not None:
                valid_ids = set(_player_role.skills)
                filtered = [
                    sid for sid in self.player.active_skills if sid in valid_ids
                ]
                # Stage 88 — Fix 2.6: do NOT fall back to full role set when
                # filtered is empty. An empty filtered list means the user
                # intentionally disabled all skills (basic-attack-only build).
                # Only replace active_skills with the filtered list (removes
                # stale/invalid skill IDs from old saves).
                self.player.active_skills = filtered
        else:
            self.player = create_default_player()
        self.state: GameState = GameState.MAP

        # Stage 88 — Fix 2.5: debounced autosave manager. Tracks dirty state
        # and flushes to disk after AUTOSAVE_DEBOUNCE_SECONDS of inactivity,
        # on screen transitions, and on QUIT. All player mutations should call
        # self.save_mgr.mark_dirty() instead of save_player_state() directly.
        self.save_mgr: SaveManager = SaveManager(self.player)
        # Stage 171 — B3: провайдер слотов синтеза для компакции сейва
        # (to_dict читает живые слоты В МОМЕНТ сохранения).
        self._bind_synth_slots_provider(self.player)

        self.target_mob_id: str = "mob_1"

        self._click_rects: list = []

        self._mouse_pos: tuple[int, int] = (0, 0)

        self._player_animator: IdleAnimator | None = None
        self._enemy_animator: IdleAnimator | None = None

        self._player_fighter: Fighter | None = None
        self._enemy_fighter: Fighter | None = None

        self._player_hp_display: float = 0.0
        self._player_mp_display: float = 0.0
        self._enemy_hp_display: float = 0.0
        self._enemy_mp_display: float = 0.0

        self._active_attack_seq = None

        self._player_hit_timer: float = 0.0
        self._enemy_hit_timer: float = 0.0
        self._enemy_shake_timer: float = 0.0

        self._countdown_active: bool = False
        self._countdown_timer: float = 0.0
        self._countdown_phase_idx: int = 0

        self._combat_replay = None
        self._replay_event_idx: int = 0
        self._replay_timer: float = 0.0

        self._endgame_active: bool = False
        self._endgame_text: str = ""
        self._endgame_phase: str = "text"
        self._endgame_text_timer: float = 0.0
        self._endgame_xp_gained: int = 0
        self._endgame_gold_gained: int = 0
        self._endgame_leveled_up: bool = False
        self._endgame_old_level: int = 1
        self._endgame_new_level: int = 1
        self._endgame_timer: float = 0.0

        self._combat_log_lines: list[str] = []
        self._combat_log_expanded: bool = False
        self._combat_log_height_display: float = float(LOG_BAR_H)

        # Stage 60 — dual char sheets: player + enemy can be open simultaneously.
        self._char_sheet_open: bool = False
        self._char_sheet_target: str = "player"
        self._char_sheet_origin: str = "left"
        self._char_sheet_anim_t: float = 0.0
        self._char_sheet_closing: bool = False
        # Second char sheet (for the other fighter in battle).
        self._char_sheet2_open: bool = False
        self._char_sheet2_target: str = "enemy"
        self._char_sheet2_origin: str = "right"
        self._char_sheet2_anim_t: float = 0.0
        self._char_sheet2_closing: bool = False

        self._battle_speed: float = float(BATTLE_SPEED_DEFAULT)

        self._particles: ParticleSystem = ParticleSystem()
        self._damage_numbers: DamageNumberSystem = DamageNumberSystem()

        self._speed_buttons_y_offset: float = 0.0

        self._skills_modal_open: bool = False
        self._quick_battle_modal_open: bool = False
        self._quick_battle_result: dict | None = None
        self._inventory_modal_open: bool = False
        self._forge_modal_open: bool = False  # Stage 47 — Кузница
        self._shop_modal_open: bool = False    # Stage 59 — Магазин
        # Stage 128 — Modal fade-in/out animation state.
        # _modal_fade_alpha: 0.0 (invisible) → 1.0 (fully visible).
        # _modal_fade_target: the target alpha (1.0 when opening, 0.0 when closing).
        # _modal_fade_speed: how fast the fade animates (per second).
        # When a modal opens, alpha ramps from 0→1 over ~0.15s.
        # When a modal closes, alpha ramps from 1→0 over ~0.15s before the modal
        # actually disappears.
        self._modal_fade_alpha: float = 0.0
        self._modal_fade_target: float = 0.0
        self._modal_fade_speed: float = 8.0  # ~0.125s for full fade
        self._modal_fade_closing: bool = False  # True during fade-out
        self._shop_active_tab: int = 0
        self._shop_equipment_page: int = 0
        # Stage 131 — new shop: 5 random items based on player level.
        self._shop_items: list[str] = []
        self._shop_last_level: int = -1
        self._shop_eq_subtab: int = 0
        # Stage 70 — titles modal (Звания).
        self._titles_modal_open: bool = False
        # Stage 89 — TOWER MODE modals + battle context.
        # _tower_modal_open: the main Tower floor-list modal.
        # _tower_shop_open: the Tower Shop modal (buys materials with shards).
        # _tower_selected_floor: which floor row is currently highlighted.
        # _tower_scroll_offset: vertical scroll position of the floor list.
        # _tower_tooltip_key: hovered shop item key (for tooltip rendering).
        # _tower_tooltip_timer: hover timer (tooltip appears after 0.5s).
        # _tower_result: dict shown in the result modal after a tower battle.
        # _battle_mode: BattleMode — disambiguates the endgame flow. Set in
        #   _enter_battle / _enter_tower_battle / _enter_world_boss_fight.
        #   Read in _apply_endgame_rewards.
        # _tower_active_floor: the floor being fought (cleared on _exit_battle).
        # _tower_active_is_boss: whether the active floor is a boss floor.
        # _tower_active_modifiers: the active floor's modifier IDs (metadata).
        # _tower_reward_applied: guards against double-applying rewards.
        self._tower_modal_open: bool = False
        self._tower_shop_open: bool = False
        self._tower_selected_floor: int = 1
        self._tower_scroll_offset: int = 0
        self._tower_tooltip_key: str | None = None
        self._tower_tooltip_timer: float = 0.0
        self._tower_result: dict | None = None
        self._battle_mode: BattleMode = BattleMode.NORMAL
        self._tower_active_floor: int | None = None
        self._tower_active_is_boss: bool = False
        self._tower_active_modifiers: tuple[str, ...] = ()
        self._tower_reward_applied: bool = False
        # Stage 133 — slot machine «3 лица → бой» (Локация 1).
        # Modal state.
        self._slot_machine_modal_open: bool = False
        self._slot_faces: list[str] = []       # rolled mob_ids (len 3 after roll)
        self._slot_rolled: bool = False        # roll finished animating (battle ready)
        self._slot_result: dict | None = None  # gauntlet result modal data
        # Stage 134 — spin animation state (reels stop left-to-right).
        self._slot_spin_active: bool = False
        self._slot_spin_timer: float = 0.0
        self._slot_spin_shown: list[str] = []    # currently displayed face per reel
        self._slot_spin_result: list[str] = []   # final face per reel
        self._slot_spin_flip_accum: list[float] = []
        # Gauntlet battle-chain state (carried between the 3 rounds).
        self._gauntlet_active: bool = False
        self._gauntlet_enemies: list[str] = []
        self._gauntlet_round: int = 0
        self._gauntlet_hp: float = 0.0
        self._gauntlet_mp: float = 0.0
        self._gauntlet_defeated: int = 0
        self._gauntlet_gold: int = 0
        self._gauntlet_xp: int = 0
        # Stage 133 — shop feedback toast (inventory-full warning).
        self._shop_feedback: str | None = None
        self._shop_feedback_timer: float = 0.0
        # Stage 91 — Las Noches guardian dialog state.
        # None = no dialog, "welcome" = first window, "shop_offer" = second window.
        self._las_noches_dialog: str | None = None
        # Stage 172 — сюжетные NPC: диалог квестов + трекер заданий.
        self._quest_dialog_npc: str | None = None   # NpcDef.npc_id или None
        self._quest_dialog_flavor: str = ""          # реплика flavor-диалога
        self._quest_tracker_tab: int = 0             # 0=доступные, 1=в процессе
        self._quest_tracker_collapsed: bool = False
        self._quest_feedback: str | None = None      # тост о награде/цели
        self._quest_feedback_timer: float = 0.0
        # Stage 173 — стрелка-подсветка цели после «Перейти».
        self._quest_arrow_quest: str | None = None   # quest_id стрелки
        self._quest_arrow_timer: float = 0.0         # сек до исчезновения
        # Stage 165 — система блюр-подложек модалок (_blur_backdrops /
        # _blur_backdrop_started / _render_blur_backdrop) УДАЛЕНА: окна
        # открываются поверх НЕИЗМЕННОЙ живой сцены (как «Карта мира»/магазин).
        # Stage 95 — Daily Quests modal.
        self._daily_quest_modal_open: bool = False
        # Stage 71/72/73/77 — World Boss state.
        self._world_boss_active: bool = False    # boss is spawned on map
        self._world_boss_damage_dealt: int = 0  # damage in current fight
        self._world_boss_rank: str = ""         # "F", "B", "A", "S", "SS", "SSS"
        self._world_boss_killed: bool = False   # boss was killed this fight
        self._world_boss_error: bool = False    # Stage 77 — no attempts error
        self._world_boss_item_drop: str | None = None  # Stage 77 — SSS drop item name
        self._boss_flash_timer: float = 0.0     # Stage 73 — attack flash effect timer
        self._hp_pulse_timer: float = 0.0       # Stage 87 — HP bar pulse at <25%
        # Stage 78 — pre-load boss animation frames (avoid lag on first render).
        self._preload_boss_anim()
        self._arena_active: bool = False       # Stage 59 — Арена
        # Stage 51 — forge active tab: 0=Заточка, 1=Камни, 2=Синтез.
        self._forge_active_tab: int = 0
        # Stage 51 — synthesis selected gem slots (instance ids or None).
        self._forge_synthesis_a: str | None = None
        self._forge_synthesis_b: str | None = None
        # Stage 51 — gems tab: currently selected gem instance id (for upgrade).
        self._forge_selected_gem: str | None = None
        # Stage 51 — gems tab: currently selected gear slot (for socketing).
        self._forge_selected_slot: str = "weapon"

        # Stage 45 — current location (CITY, LOC1, LOC2, LOC3, LOC4).
        from pockie_rpg.config import MapLocation
        self._map_location = MapLocation.LOC1
        self._prev_location = MapLocation.LOC1  # remember last combat location

        # Stage 135 — world map modal («Sakura of mainland»).
        self._worldmap_modal_open: bool = False
        self._worldmap_hovered_zone: int | None = None
        self._worldmap_selected_zone: int | None = None
        self._worldmap_locked_timer: float = 0.0
        self._worldmap_locked_name: str = ""
        # Stage 152 — fade модалок живёт в общем реестре ScalableRendererMixin
        # (_modal_fades[key]); поля per-модалку больше не нужны.
        self._modal_fades: dict[str, float] = {}
        self._fade_buffers: dict[tuple[int, int], pygame.Surface] = {}
        # Stage 152 — отладочный оверлей Hi-DPI (тумблер F10).
        self._debug_overlay: bool = False
        self._debug_frame_ms: float = 0.0
        # Stage 138 — SYNTH (синтез костюмов) + WARDROBE (гардероб) — ПРАВИЛО 9.
        # Stage 164 — слоты хранят item_id (предмет физически вне инвентаря).
        # Stage 166 — _synth_result_item: результат синтеза (+N+1) ОСТАЁТСЯ
        # в слоте результата, пока игрок не заберёт его кликом в инвентарь.
        self._synth_modal_open: bool = False
        self._synth_main_item: str | None = None
        self._synth_cat1_item: str | None = None
        self._synth_cat2_item: str | None = None
        self._synth_result_item: str | None = None
        self._synth_result_msg: str = ""
        self._synth_success_flash: float = 0.0
        self._wardrobe_modal_open: bool = False
        self._wardrobe_layout: list = []
        # Stage 143 — суб-меню качества у «Продать» в инвентаре.
        self._inv_sell_menu_open: bool = False

        # Stage 28 — drag-and-drop state for the inventory modal.
        # _drag_item_id: the item being dragged (or None).
        # _drag_source: ('inv', index) | ('gear', slot_name) | None
        self._drag_item_id: str | None = None
        self._drag_source: tuple | None = None
        # Stage 64 — current inventory page (1, 2, or 3). Each page holds
        # ITEMS_PER_PAGE = 48 slots. Switching pages resets the drag and
        # context-menu state so phantom items don't leak between tabs.
        self._inv_current_page: int = 1
        # Stage 64 — LMB drag gesture tracking.
        # On MOUSEBUTTONDOWN we record the down position + source slot. If the
        # cursor moves beyond _DRAG_THRESHOLD pixels before MOUSEBUTTONUP, the
        # gesture becomes a real drag (swap on release). Otherwise it's a click
        # (opens the context menu — preserves existing UX).
        self._mouse_down_pos: tuple[int, int] | None = None
        self._mouse_down_slot: tuple[str, int] | None = None  # ("inv", slot_idx) | ("gear", slot_name) | None
        self._DRAG_THRESHOLD: int = 5  # px of movement before a click becomes a drag

        # Stage 36 — context menu state for inventory items.
        self._context_menu_item_id: str | None = None
        self._context_menu_pos: tuple[int, int] = (0, 0)
        # Stage 66 — source slot (page, slot_idx) the context menu item came
        # from. Used by _use_item to pass source_slot to equip_gear_item so
        # the old item goes to the exact clicked slot (not first empty).
        # None when the menu was opened from a gear slot (unequip, not equip).
        self._context_menu_source_slot: tuple[int, int] | None = None
        # Stage 185 — микро-меню ПКМ (инвентарь): item_id + стак-слот +
        # позиция мыши (меню рисуется справа от курсора, горизонтальные
        # кнопки: Использовать / Разделить / Разделить на 1 / Продать).
        self._micromenu_item_id: str | None = None
        self._micromenu_slot: tuple[int, int] | None = None  # (page, slot_idx)
        self._micromenu_pos: tuple[int, int] = (0, 0)
        self._micromenu_rects: dict[str, pygame.Rect] = {}

        # Stage 38 — gold flash effect on sell.
        self._gold_flash_timer: float = 0.0
        self._gold_flash_amount: int = 0

        # Stage 43 — combat debug logging.
        self._combat_debug: bool = False
        self._combat_debug_lines: list[str] = []

        # Stage 109 — Test Panel (admin/dev panel for weapon balance testing).
        self._init_test_panel_state()

        self._player_ice: IceBlockEffect = IceBlockEffect()
        self._enemy_ice: IceBlockEffect = IceBlockEffect()

        self._player_shield: EffectOverlay = EffectOverlay(
            SHIELD_DOME_FOLDER, SHIELD_DOME_FPS,
            SHIELD_DOME_RENDER_W, SHIELD_DOME_RENDER_H,
        )
        self._enemy_shield: EffectOverlay = EffectOverlay(
            SHIELD_DOME_FOLDER, SHIELD_DOME_FPS,
            SHIELD_DOME_RENDER_W, SHIELD_DOME_RENDER_H,
        )
        self._player_cloud: EffectOverlay = EffectOverlay(
            STORM_CLOUD_FOLDER, STORM_CLOUD_FPS,
            STORM_CLOUD_RENDER_W, STORM_CLOUD_RENDER_H,
        )
        self._enemy_cloud: EffectOverlay = EffectOverlay(
            STORM_CLOUD_FOLDER, STORM_CLOUD_FPS,
            STORM_CLOUD_RENDER_W, STORM_CLOUD_RENDER_H,
        )
        self._player_poison: EffectOverlay = EffectOverlay(
            POISON_OVERLAY_FOLDER, POISON_OVERLAY_FPS,
            POISON_OVERLAY_RENDER_W, POISON_OVERLAY_RENDER_H,
        )
        self._enemy_poison: EffectOverlay = EffectOverlay(
            POISON_OVERLAY_FOLDER, POISON_OVERLAY_FPS,
            POISON_OVERLAY_RENDER_W, POISON_OVERLAY_RENDER_H,
        )

        self._cast_effect: CastEffect = CastEffect()
        self._projectile_effect: ProjectileEffect = ProjectileEffect()

        self._last_skills_grid_slots: list = []

    def run(self) -> None:
        """Main event loop. Exits on QUIT or ESC-from-MAP.

        Аудит 2026-09 — KeyboardInterrupt (Ctrl+C в терминале) больше не даёт
        сырой traceback: цикл прерывается штатно, pending-сейв сбрасывается
        в finally (flush сам no-op, если нечего сохранять).
        """
        try:
            self._run_loop()
        except KeyboardInterrupt:
            pass  # Ctrl+C — штатный выход
        finally:
            # Ctrl+C обходит QUIT-ветку с flush — страхуемся здесь.
            if self.save_mgr is not None:
                self.save_mgr.flush()

    def _run_loop(self) -> None:
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            self._mouse_pos = self._ui_mouse_pos(pygame.mouse.get_pos())

            for event in pygame.event.get():
                # Stage 139 — ремап мыши для боевого окна (fullscreen-композит).
                if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP,
                                  pygame.MOUSEMOTION, pygame.MOUSEWHEEL):
                    self._map_battle_mouse(event)
                if event.type == pygame.QUIT:
                    # Stage 164 — костюмы из слотов синтеза возвращаются в
                    # инвентарь перед сохранением (окно могло быть открыто).
                    self._synth_return_all_to_inventory()
                    # Stage 88 — Fix 2.5: flush any pending autosave before exiting.
                    self.save_mgr.flush()
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        # Stage 133 — FULL ESC cascade. Previously ESC inside
                        # shop/forge/inventory/titles/quick-battle FELL THROUGH
                        # to running=False and QUIT the game.
                        # Order: TestPanel → Las Noches dialog → Tower result →
                        # Slot result → Daily Quest → Tower Shop → Tower modal →
                        # Slot machine → Quick Battle modal → Quick Battle result →
                        # Titles → Shop → Forge → Inventory → Char sheet 2 →
                        # Char sheet 1 → Skills → _exit_battle → _exit_test_battle → quit.
                        if self._test_panel_open:
                            self._close_test_panel()
                        elif self._worldmap_modal_open:
                            self._close_worldmap_modal()
                        elif self._quest_dialog_npc is not None:
                            self._close_npc_dialog()
                        elif self._wardrobe_modal_open:
                            self._close_wardrobe_modal()
                        elif self._synth_modal_open:
                            self._close_synth_modal()
                        elif self._las_noches_dialog is not None:
                            self._las_noches_dialog = None
                        elif self._tower_result is not None:
                            self._close_tower_result()
                        elif self._slot_result is not None:
                            self._close_slot_result()
                        elif self._daily_quest_modal_open:
                            self._close_daily_quest_modal()
                        elif self._tower_shop_open:
                            self._close_tower_shop()
                        elif self._tower_modal_open:
                            self._close_tower()
                        elif self._slot_machine_modal_open:
                            self._close_slot_machine_modal()
                        elif self._quick_battle_modal_open:
                            self._close_quick_battle_modal()
                        elif self._quick_battle_result is not None:
                            self._close_quick_battle_result()
                        elif self._titles_modal_open:
                            self._close_titles_modal()
                        elif self._shop_modal_open:
                            self._close_shop()
                        elif self._forge_modal_open:
                            self._close_forge_modal()
                        elif self._inventory_modal_open:
                            self._close_inventory_modal()
                        elif self._char_sheet2_open and not self._char_sheet2_closing:
                            self._close_char_sheet2()
                        elif self._char_sheet_open and not self._char_sheet_closing:
                            self._close_char_sheet()
                        elif self.state == GameState.MAP and self._skills_modal_open:
                            self._close_skills_modal()
                        elif self.state == GameState.BATTLE:
                            self._exit_battle()
                        elif self.state == GameState.TEST_BATTLE:
                            self._exit_test_battle()
                        else:
                            running = False
                    elif event.key == pygame.K_F12:
                        # Stage 43 — toggle combat debug logging.
                        self._combat_debug = not self._combat_debug
                        if self._combat_debug:
                            self._combat_debug_lines = []
                            print("[DEBUG] Combat debug logging ENABLED (F12)")
                        else:
                            self._save_combat_debug_log()
                            print("[DEBUG] Combat debug log saved to data/combat_debug.txt (F12)")
                    elif event.key == pygame.K_F9:
                        # Stage 109 — toggle test panel (admin/dev panel).
                        self._toggle_test_panel()
                    elif event.key == pygame.K_F10:
                        # Stage 152 — отладочный оверлей Hi-DPI (масштабы, кэши).
                        self._debug_overlay = not self._debug_overlay
                    elif event.key == pygame.K_F11:
                        # Stage 139 — toggle fullscreen ↔ windowed 1280×720.
                        self._toggle_fullscreen()
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    # Stage 98 — click outside char sheet closes both sheets.
                    if self.state == GameState.BATTLE:
                        clicked_in_sheet = False
                        if self._char_sheet_open and not self._char_sheet_closing:
                            if hasattr(self, "_char_sheet_rect") and self._char_sheet_rect.collidepoint(event.pos):
                                clicked_in_sheet = True
                        if self._char_sheet2_open and not self._char_sheet2_closing:
                            if hasattr(self, "_char_sheet2_rect") and self._char_sheet2_rect.collidepoint(event.pos):
                                clicked_in_sheet = True
                        if not clicked_in_sheet and (self._char_sheet_open or self._char_sheet2_open):
                            self._close_char_sheet()
                            self._close_char_sheet2()
                    # Stage 185/186 fix — микро-меню: клик ПО кнопкам проходит
                    # в _handle_click (кнопки зарегистрированы priority=True —
                    # сработают). Клик МИМО кнопок закрывает меню и съедается
                    # (не запускает drag по предмету под курсором).
                    if self._micromenu_item_id is not None:
                        hit = any(
                            r.collidepoint(self._inv_native_pos(event.pos))
                            for r in self._micromenu_rects.values()
                        )
                        if not hit:
                            self._close_micromenu()
                        # Stage 186 fix — НИКАКОГО continue в обеих ветках:
                        # continue здесь пропускал _handle_click, и кнопки
                        # меню никогда не получали клики (баг «клик не
                        # работает»). _handle_click ниже сам диспетчеризует
                        # priority-кнопки меню или съест клик (modal_open).
                    # Stage 186 — Shift+клик по СТАКУ ≥2 = «Разделить на 1»
                    # (без открытия меню, как в Diablo/Path of Exile).
                    elif (self._inventory_modal_open
                          and self._micromenu_item_id is None
                          and pygame.key.get_mods() & pygame.KMOD_SHIFT):
                        if self._shift_click_split_one(event.pos):
                            continue  # съедено стак-делением — без drag/жестов
                    # Stage 64 — LMB down. We don't immediately open the
                    # context menu; instead we record the down position +
                    # source slot. If the cursor moves beyond _DRAG_THRESHOLD
                    # before release, it's a drag; otherwise the release
                    # handler opens the context menu (preserves the existing
                    # click → menu UX).
                    if self._context_menu_item_id is not None:
                        # Click while menu open → check if on menu buttons.
                        matched = self._handle_click(event.pos)
                        # Stage 61 — if click didn't match any menu button, close the menu.
                        if matched is None:
                            self._context_menu_item_id = None
                    elif self._handle_window_close_click(event.pos):
                        # Stage 159 — квадратный Х в углу окна: приоритет над
                        # drag-захватом шапки (кнопка приклеена к углу).
                        pass
                    elif self._begin_window_drag(event.pos):
                        # Stage 156/157 — захват шапки окна (общий реестр):
                        # перетаскивание окна, клик НЕ диспетчируется дальше.
                        pass
                    elif (getattr(self, "_synth_modal_open", False)
                            and self._synth_slot_drag_begin(event.pos)):
                        # Stage 157 — удержание ЗАПОЛНЕННОГО слота синтеза:
                        # при движении = перенос между слотами; при отпускании
                        # без движения = обычный клик (очистка через
                        # _handle_click → _synth_pick_item). Клик не
                        # диспетчируется здесь — иначе слот бы очищался
                        # СРАЗУ и переносить было бы нечего.
                        pass
                    else:
                        # Stage 186 — при открытом микро-меню drag/жест не
                        # начинаются: лёгкое движение мыши при клике на кнопку
                        # не должно тащить предмет под ней. Кнопки
                        # диспетчеризуются через _handle_click (priority).
                        if self._micromenu_item_id is None:
                            self._mouse_down_pos = event.pos
                            self._mouse_down_slot = self._slot_at(event.pos)
                        # Dispatch the click to normal handlers too (so tab
                        # buttons / close-X / sort buttons still work).
                        self._handle_click(event.pos)
                elif event.type == pygame.MOUSEMOTION:
                    # Stage 157 — перетаскивание окон за шапку (общий реестр).
                    if self._window_drag_key() is not None:
                        self._update_window_drag(event.pos)
                    # Stage 157 — перенос между слотами синтеза (порог).
                    if getattr(self, "_synth_modal_open", False):
                        self._synth_slot_drag_motion(event.pos)
                    # Stage 64 — if LMB is held and we have a down-slot, and
                    # the cursor moved beyond the drag threshold, start a
                    # drag (only if not already dragging).
                    if self._drag_item_id is not None:
                        # Already dragging — mouse_pos is updated each frame.
                        pass
                    elif self._mouse_down_pos is not None and self._mouse_down_slot is not None:
                        dx = event.pos[0] - self._mouse_down_pos[0]
                        dy = event.pos[1] - self._mouse_down_pos[1]
                        if (dx * dx + dy * dy) >= (self._DRAG_THRESHOLD * self._DRAG_THRESHOLD):
                            self._try_start_drag(self._mouse_down_pos)
                    # Stage 135 — world map hover hit-test (mousemove).
                    if self._worldmap_modal_open:
                        self._update_worldmap_hover(event.pos)
                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    # Stage 157 — LMB up при переносе между слотами синтеза.
                    slot_drag_was_active = False
                    if getattr(self, "_synth_modal_open", False):
                        slot_drag_was_active = self._synth_slot_drag_active()
                        self._synth_slot_drag_finish(event.pos)
                    # Stage 157 — отпущена шапка окна (перетаскивание конца).
                    self._end_window_drag()
                    # Stage 64 — LMB up. Decide between drag-finish and click.
                    if self._drag_item_id is not None:
                        # A real drag was in flight — finish it (swap/equip).
                        self._finish_drag(event.pos)
                        # Clear gesture tracking (drag was the gesture).
                        self._mouse_down_pos = None
                        self._mouse_down_slot = None
                    elif slot_drag_was_active:
                        # Слот-drag завершён — это была не клик-жеста.
                        self._mouse_down_pos = None
                        self._mouse_down_slot = None
                    elif self._mouse_down_pos is not None:
                        # It was a click (no drag started). Stage 185 — старое
                        # контекст-меню ЛКМ УДАЛЕНО: клик по предмету ничего
                        # не открывает (действия — в микро-меню ПКМ). Клик-
                        # rect'ы (вкладки/крестики/кнопки) диспетчеризуются
                        # в MOUSEBUTTONDOWN-ветке.
                        self._mouse_down_pos = None
                        self._mouse_down_slot = None
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                    # Stage 164 — ПКМ по слоту синтеза ВОЗВРАЩАЕТ костюм в
                    # инвентарь; слот синтеза — верхний слой, поэтому первым.
                    if self._synth_modal_open and self._handle_synth_right_click(event.pos):
                        pass
                    elif self._inventory_modal_open:
                        # Stage 185 — ПКМ открывает МИКРО-МЕНЮ (не активирует).
                        self._handle_right_click(event.pos)
                elif event.type == pygame.MOUSEWHEEL:
                    # Stage 89 — mousewheel scrolls the Tower floor list.
                    if self._tower_modal_open and not self._tower_shop_open:
                        self._scroll_tower(-event.y)

            if self.state == GameState.BATTLE:
                self._update_battle(dt)
            elif self.state == GameState.TEST_BATTLE:
                self._update_test_battle(dt)

            self._update_char_sheet_anim(dt)
            self._update_combat_log_anim(dt)

            # Stage 128 — Modal fade-in/out animation.
            self._update_modal_fade(dt)

            # Stage 73 — update boss flash timer (fades over 1 second).
            if self._boss_flash_timer > 0:
                self._boss_flash_timer = max(0.0, self._boss_flash_timer - dt)

            # Stage 87 — HP bar pulse timer (always advances; consumed by _render_*_bar
            # only when ratio < HP_PULSE_RATIO). Wraps every 3600s to avoid float drift.
            self._hp_pulse_timer = (self._hp_pulse_timer + dt) % 3600.0

            # Stage 198 — таймер shine-sweep по полоскам HUD (период в config;
            # тикает всегда — блик декоративный, на скорость боя не завязан).
            self._bar_shine_timer = getattr(self, "_bar_shine_timer", 0.0) + dt

            # Stage 200 — fade-in подложек имён при входе в BATTLE:
            # 0→1 за name_plate_fade_sec (из HUD_THEME), сброс в _enter_battle.
            if self.state == GameState.BATTLE:
                from pockie_rpg.config import HUD_THEME
                fade_speed = 1.0 / max(0.001, float(
                    HUD_THEME["name_plate_fade_sec"]))
                self._hud_plate_fade = min(
                    1.0, getattr(self, "_hud_plate_fade", 0.0) + dt * fade_speed
                )

            # Stage 88 — Fix 2.5: debounced autosave — flush after 0.5s of
            # inactivity following the last mark_dirty() call.
            self.save_mgr.update(dt)

            # Stage 74 — update boss animation (idle frame cycling at 6 FPS).
            if hasattr(self, "_update_boss_anim"):
                self._update_boss_anim(dt)

            # Stage 133 — shop feedback toast timer (inventory-full message).
            if self._shop_feedback_timer > 0:
                self._shop_feedback_timer = max(0.0, self._shop_feedback_timer - dt)
                if self._shop_feedback_timer == 0.0:
                    self._shop_feedback = None

            # Stage 172 — тост квестов (награда получена / цель выполнена).
            if self._quest_feedback_timer > 0:
                self._quest_feedback_timer = max(0.0, self._quest_feedback_timer - dt)
                if self._quest_feedback_timer == 0.0:
                    self._quest_feedback = None
            # Stage 173 — таймер стрелки-подсветки цели.
            if self._quest_arrow_timer > 0:
                self._quest_arrow_timer = max(0.0, self._quest_arrow_timer - dt)
                if self._quest_arrow_timer == 0.0:
                    self._quest_arrow_quest = None
            # Stage 172 — тост «цель use_item выполнена» (надет целевой предмет).
            if self.state == GameState.MAP:
                done_now = frozenset(self.player.story_quests_goal_done)
                prev_done = getattr(self, "_quest_prev_goal_done", None)
                if prev_done is not None and done_now > prev_done:
                    new_id = next(iter(done_now - prev_done), None)
                    quest = get_story_quest(new_id) if new_id else None
                    if quest is not None:
                        self._show_quest_feedback(
                            f"Цель выполнена: «{quest.name}» — доложите Старейшине")
                self._quest_prev_goal_done = done_now

            # Stage 135 — world map «зона закрыта» toast timer.
            if self._worldmap_locked_timer > 0:
                self._worldmap_locked_timer = max(0.0, self._worldmap_locked_timer - dt)

            # Stage 134 — slot machine spin animation (modal open on MAP).
            if self._slot_machine_modal_open and self._slot_spin_active:
                self._update_slot_spin(dt)

            # Stage 77 — regen boss attempts (30 min per attempt, max 3).
            # Stage 78 — uses module-level `import time` (was per-frame import).
            if (self.player.world_boss_attempts < 3
                    and self.player.world_boss_next_attempt_ts is not None):
                now = time.time()
                if now >= self.player.world_boss_next_attempt_ts:
                    self.player.world_boss_attempts += 1
                    if self.player.world_boss_attempts >= 3:
                        self.player.world_boss_next_attempt_ts = None
                    else:
                        self.player.world_boss_next_attempt_ts = now + 1800
                    self._save_player()

            # Stage 73 — update endgame for instant boss fights (state stays MAP).
            if self.state == GameState.MAP and self._endgame_active:
                self._update_endgame(dt)

            # Stage 136/152 — fade-in модалок (общий реестр _modal_fades).
            if self._worldmap_modal_open:
                self._update_worldmap_fade(dt)
            if self._inventory_modal_open:
                self._modal_fade_tick("inventory", dt)

            # Stage 109 — update test panel toast timer.
            if self._test_panel_open:
                self._update_test_panel_toast(dt)

            if self.state == GameState.MAP:
                if self._arena_active:
                    # Arena is a full-screen location — skip MAP entirely.
                    self._render_arena()
                else:
                    # Stage 153 — БАЗОВЫЙ ЭКРАН НАТИВНО: на 2К MAP рисуется
                    # прямо на монитор (1:1 в физических пикселях), а
                    # немигрированные модалки уходят в legacy-слой (буфер
                    # 1280×720 → ×2 → монитор). См. _begin_native_base_frame.
                    native_base = self._begin_native_base_frame()
                    self._render_map()
                    if native_base:
                        self._end_native_base_screen()
                    # Stage 159 — диалог стража Лас Ночеса: legacy-фаза
                    # (раньше рендерился внутри _render_map — на нативном 2К
                    # дизайн-координаты давали окно в верхне-левом квадранте).
                    if self._las_noches_dialog is not None:
                        self._render_modal_scaled(self._render_las_noches_dialog)
                    # Stage 172 — диалог сюжетного NPC (аватарка + квест).
                    if self._quest_dialog_npc is not None:
                        self._render_modal_scaled(self._render_npc_dialog)
                    # Stage 140 — модалки рендерятся через _render_modal_scaled
                    # (под-буфер + blit с MODAL_SCALE=0.5 → вдвое меньше).
                    if self._skills_modal_open:
                        self._render_modal_scaled(self._render_skills_modal)
                    if self._char_sheet_open:
                        self._render_modal_scaled(self._render_char_sheet)
                    if self._char_sheet2_open:
                        self._render_modal_scaled(self._render_char_sheet2)
                    if self._quick_battle_modal_open:
                        self._render_modal_scaled(self._render_quick_battle_modal)
                    if self._quick_battle_result is not None:
                        self._render_modal_scaled(self._render_quick_battle_result)
                    if self._inventory_modal_open and not self._native_overlays_will_render():
                        # Stage 150 — мигрированный (нативный) инвентарь
                        # рендерится в _render_native_overlays(), не здесь.
                        # Stage 152 — fade-in 0.15с (общий механизм).
                        self._render_with_fade(
                            "inventory",
                            self._render_modal_scaled,
                            self._render_inventory_modal,
                            scale=MODAL_SCALE_INVENTORY,
                        )
                    if self._forge_modal_open and not self._native_overlays_will_render():
                        # Stage 152 — нативная кузница рисуется в native-фазе.
                        self._render_modal_scaled(self._render_forge_modal)
                    if self._shop_modal_open and not self._native_overlays_will_render():
                        # Stage 157 — магазин мигрирован (нативный рендер).
                        self._render_modal_scaled(self._render_shop_modal)
                    if self._titles_modal_open and not self._native_overlays_will_render():
                        # Stage 156 — звания мигрированы (нативный рендер).
                        self._render_modal_scaled(self._render_titles_modal)
                    # Stage 89 — Tower modal + shop + result.
                    if self._tower_modal_open:
                        self._render_modal_scaled(self._render_tower_modal)
                    if self._tower_shop_open:
                        self._render_modal_scaled(self._render_tower_shop)
                    if self._tower_result is not None:
                        self._render_modal_scaled(self._render_tower_result)
                    # Stage 95 — Daily Quests modal.
                    if self._daily_quest_modal_open:
                        self._render_modal_scaled(self._render_daily_quest_modal)
                    # Stage 133 — slot machine modal + gauntlet result modal.
                    if self._slot_machine_modal_open:
                        self._render_modal_scaled(self._render_slot_machine_modal)
                    if self._slot_result is not None:
                        self._render_modal_scaled(self._render_slot_result)
                    self._render_bottom_bar()
                    # Stage 135 — world map modal (поверх bottom bar, ниже TestPanel).
                    if self._worldmap_modal_open:
                        self._render_worldmap_modal()
                    # Stage 138 — synth + wardrobe модалки (поверх инвентаря).
                    # Stage 156 — мигрированы нативно: в native-фазе рисуются
                    # в _render_native_overlays() (порядок: после инвентаря).
                    if self._synth_modal_open and not self._native_overlays_will_render():
                        self._render_modal_scaled(self._render_synth_modal)
                    if self._wardrobe_modal_open and not self._native_overlays_will_render():
                        self._render_modal_scaled(self._render_wardrobe_modal)
                    if self._context_menu_item_id is not None and not self._native_overlays_will_render():
                        # Stage 151 — при нативном инвентаре контекст-меню
                        # рендерится в native-фазе (поверх композита).
                        self._render_context_menu()
                    # Stage 109 — Test Panel (admin/dev panel, F9).
                    if self._test_panel_open:
                        self._render_test_panel()
                    # Stage 73 — render endgame overlay for instant boss fights.
                    if self._endgame_active:
                        self._render_endgame()
            elif self.state == GameState.BATTLE:
                self._render_battle()
                if self._countdown_active:
                    self._render_countdown()
                if self._endgame_active:
                    self._render_endgame()
                if self._char_sheet_open:
                    self._render_modal_scaled(self._render_char_sheet)
                if self._char_sheet2_open:
                    self._render_modal_scaled(self._render_char_sheet2)
            elif self.state == GameState.TEST_BATTLE:
                self._render_test_battle()
                if self._char_sheet_open:
                    self._render_modal_scaled(self._render_char_sheet)
                if self._char_sheet2_open:
                    self._render_modal_scaled(self._render_char_sheet2)

            # Stage 139 — композит fullscreen (блюр-фон + окно) или обычный flip.
            # Stage 150 — порядок кадра: legacy-композит (БЕЗ flip) → нативные
            # Hi-DPI-модалки прямо на поверхность монитора → flip.
            # Stage 164 — drag-призрак рисуется ПОВЕРХ всех окон: в
            # legacy-фазе — в буфер до композита, в native-фазе — после
            # нативных модалок (см. _render_drag_ghost_topmost).
            if not self._native_overlays_will_render():
                self._render_drag_ghost_topmost()
            self._present_fullscreen(flip=False)
            self._render_native_overlays()
            if self._native_overlays_will_render():
                self._render_drag_ghost_topmost()
            # Stage 152 — отладочный оверлей поверх ВСЕГО (после нативной фазы,
            # чтобы был виден и на 2К). ClickRect'ы не добавляет.
            if self._debug_overlay:
                self._debug_frame_ms = dt * 1000.0
                self._render_debug_overlay()
            pygame.display.flip()

    def _render_debug_overlay(self) -> None:
        """Stage 152 — F10: масштабы, native-путь, ClickRect'ы, кэши, время кадра.

        Рисуется на поверхность монитора (если fullscreen) или на буфер игры;
        НЕ регистрирует ClickRect'ы и не влияет на hit-тест.
        """
        target = self._fullscreen_monitor if self._fullscreen_monitor is not None else self.screen
        native_on = self._native_overlays_will_render()
        total_rects = len(self._click_rects)
        native_rects = sum(1 for cr in self._click_rects if getattr(cr, "native", False))
        modals = [
            name for name, flag in (
                ("inventory", self._inventory_modal_open),
                ("forge", self._forge_modal_open),
                ("shop", self._shop_modal_open),
                ("worldmap", self._worldmap_modal_open),
                ("skills", self._skills_modal_open),
                ("charsheet", self._char_sheet_open),
                ("tower", self._tower_modal_open),
                ("slot", self._slot_machine_modal_open),
                ("synth", self._synth_modal_open),
                ("testpanel", self._test_panel_open),
            ) if flag
        ]
        mon = self._fullscreen_monitor.get_size() if self._fullscreen_monitor is not None else None
        fps = 1000.0 / self._debug_frame_ms if self._debug_frame_ms > 0.01 else 0.0
        from pockie_rpg.config import MODAL_SCALE, MODAL_SCALE_2K
        modal_scale = MODAL_SCALE_2K if (mon is not None and self._ui_scale > 1.0) else MODAL_SCALE
        caches = (
            f"icons={len(getattr(self, '_gear_icon_scaled_cache', {}))} "
            f"fonts={len(getattr(self, '_su_font_cache', {}))} "
            f"grad={len(getattr(self, '_panel_gradient_cache', {}))} "
            f"pose={len(getattr(self, '_char_pose_scaled_cache', {}))} "
            f"fade={len(getattr(self, '_fade_buffers', {}))} "
            f"surf={len(getattr(self, '_su_surface_cache', {}))} "
            f"img={len(getattr(self, '_su_image_raw_cache', {}))}"
        )
        lines = [
            f"F10 DEBUG  {self._debug_frame_ms:5.1f} ms  ({fps:4.0f} fps)",
            f"ui_scale={self._ui_scale:.2f}  render_scale={self._render_scale:.2f}  modal_scale={modal_scale:.2f}",
            f"monitor={mon}  buffer={self.screen.get_size()}",
            f"native path: {'ON' if native_on else 'off'}  registry={sorted(NATIVE_MODAL_REGISTRY)}",
            # Stage 153 — базовый экран нативно + слой legacy-модалок.
            f"native base: {'ON' if getattr(self, '_native_base_active', False) else 'off'}"
            f"  legacy layer: {'used' if self._legacy_layer_used else 'idle'}",
            f"ClickRects: {total_rects} (native {native_rects})",
            f"state={self.state.name}  loc={self._map_location.name}  mode={self._battle_mode.name}",
            f"modals: {', '.join(modals) if modals else '—'}",
            f"caches: {caches}",
        ]
        # Stage 171 — B2: отчёт о целостности последней загрузки сейва.
        from pockie_rpg.game import save_load as save_load_mod
        _rep = save_load_mod.LAST_LOAD_REPORT
        if _rep is not None:
            lines.append(
                f"load: источник={_rep['source']}  проблем={len(_rep['issues'])}"
            )
            lines.extend(f"  ! {_msg}" for _msg in _rep["issues"][:4])
            if len(_rep["issues"]) > 4:
                lines.append(f"  … ещё {len(_rep['issues']) - 4}")
        else:
            lines.append("load: отчёта нет (новая игра)")
        # Stage 189 — страж зависания боя: видим только когда сработал.
        wd_time = getattr(self, "_watchdog_event_time", 0.0)
        wd_reports = getattr(self, "_watchdog_reports", 0)
        if self.state == GameState.BATTLE and wd_reports > 0:
            lines.append(
                f"WATCHDOG: срабатываний={wd_reports}  простой={wd_time:.0f}с "
                f"(детали в боевом логе F12)"
            )
        font = pygame.font.SysFont("consolas,dejavusansmono,couriernew", 15)
        surfs = [font.render(t, True, (232, 232, 236)) for t in lines]
        pad = 8
        w = max(s.get_width() for s in surfs) + pad * 2
        h = sum(s.get_height() + 2 for s in surfs) + pad * 2
        x = target.get_width() - w - 12
        y = 12
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        panel.fill((9, 9, 11, 214))
        target.blit(panel, (x, y))
        pygame.draw.rect(target, (82, 82, 91), pygame.Rect(x, y, w, h), 1)
        cy = y + pad
        for s in surfs:
            target.blit(s, (x + pad, cy))
            cy += s.get_height() + 2

    def _present_fullscreen(self, flip: bool = True) -> None:
        """Stage 139.3 — ВСЯ игра на весь монитор; бой — окно 60% + блюр.

        Stage 150 — параметр flip=False: скомпоновать legacy-контент на
        мониторе БЕЗ flip (flip делает run() ПОСЛЕ нативных Hi-DPI-модалок).

        Вся игра растягивается smoothscale 1280×720 → размер монитора
        (2560×1440 на 2К, ~6мс). В BATTLE/TEST_BATTLE поверх — боевое
        окно 60% размера ЭКРАНА в центре (smoothscale от буфера), вокруг —
        блюр-фон + затемнение + рамки. Мышь ремапится в _map_battle_mouse().
        """
        if self._fullscreen_monitor is None:
            if flip:
                pygame.display.flip()
            return
        from pockie_rpg.config import (
            BATTLE_BG_DIM_ALPHA,
            BATTLE_BG_REFRESH_SEC,
            BATTLE_WINDOW_SCALE,
            GAME_WINDOW_BORDER,
            GAME_WINDOW_BORDER_W,
        )
        mw, mh = self._fullscreen_monitor.get_size()
        if self.state in (GameState.BATTLE, GameState.TEST_BATTLE):
            # --- БОЙ: фон = СНАПШОТ локации входа + затемнение как у «Карты
            # мира» (Stage 166). Раньше (Stage 165) фон был без изменений;
            # по запросу пользователя вокруг боевого окна возвращено
            # затемнение (0,0,0,BATTLE_BG_DIM_ALPHA=165) — РОВНО тот же
            # слой, что рисует модалка карты мира. Блюра по-прежнему НЕТ:
            # резкий снапшот + затемнение, окно боя появляется в центре.
            #
            # Аудит 2026-09 — «живой» фон (запрос: фон боя не должен быть
            # картинкой): стоп-кадр карты пере-снимается каждые
            # BATTLE_BG_REFRESH_SEC (0.25с = 4×/сек) — NPC/бейджи карты
            # продолжают двигаться. Стоимость: 4 оффскрин-рендера карты в
            # секунду вместо 60 — на кадр боя почти не влияет.
            now_s = pygame.time.get_ticks() / 1000.0
            if now_s - getattr(self, "_battle_bg_refresh_ts", -1e9) >= BATTLE_BG_REFRESH_SEC:
                self._battle_bg_refresh_ts = now_s
                fresh = self._snapshot_map_scene()
                if fresh is not None:
                    self._battle_bg_snapshot = fresh
            bg_src = self._battle_bg_snapshot if self._battle_bg_snapshot is not None else self._fullscreen_game
            if bg_src.get_size() == (mw, mh):
                bg = bg_src
            else:
                bg = pygame.transform.smoothscale(bg_src, (mw, mh))
            self._fullscreen_monitor.blit(bg, (0, 0))
            self._fullscreen_monitor.blit(
                self._fullscreen_dim_shade((mw, mh), BATTLE_BG_DIM_ALPHA), (0, 0))
            win_w = int(mw * BATTLE_WINDOW_SCALE)
            win_h = int(mh * BATTLE_WINDOW_SCALE)
            win_x = (mw - win_w) // 2
            win_y = (mh - win_h) // 2
            window_surf = pygame.transform.smoothscale(
                self._fullscreen_game, (win_w, win_h)
            )
            self._fullscreen_monitor.blit(window_surf, (win_x, win_y))
            pygame.draw.rect(
                self._fullscreen_monitor, (0, 0, 0),
                (win_x - 3, win_y - 3, win_w + 6, win_h + 6), 3,
            )
            pygame.draw.rect(
                self._fullscreen_monitor, GAME_WINDOW_BORDER,
                (win_x, win_y, win_w, win_h), GAME_WINDOW_BORDER_W,
            )
        else:
            # --- MAP и прочие: ВСЯ игра на весь монитор (без окна). ---
            # Stage 153 — если базовый экран уже отрисован НАТИВНО (прямо на
            # монитор), растягивать буфер 1280×720 НЕЛЬЗЯ — он затрёт нативный
            # кадр. Вместо этого накладываем только слой legacy-модалок.
            if getattr(self, "_native_base_active", False):
                if self._legacy_layer_used:
                    scaled = self._legacy_layer_scaled
                    if scaled is None or scaled.get_size() != (mw, mh):
                        scaled = pygame.Surface((mw, mh), pygame.SRCALPHA)
                        self._legacy_layer_scaled = scaled
                    pygame.transform.scale(self._legacy_layer, (mw, mh), scaled)
                    self._fullscreen_monitor.blit(scaled, (0, 0))
                # Вернуть self.screen на игровой буфер (следующий кадр —
                # legacy-путь до нового _begin_native_base_frame).
                self.screen = self._fullscreen_game
                self._native_base_active = False
            else:
                game_surf = pygame.transform.smoothscale(
                    self._fullscreen_game, (mw, mh)
                )
                self._fullscreen_monitor.blit(game_surf, (0, 0))
        # Stage 150 — flip делает run() после нативных Hi-DPI-модалок.
        if flip:
            pygame.display.flip()

    def _fullscreen_dim_shade(self, size: tuple[int, int],
                              alpha: int) -> pygame.Surface:
        """Stage 166 — кэшированный чёрный SRCALPHA-слой для фона боя.

        Аналог asset_manager.get_overlay, но размером с МОНИТОР (слой
        применяется в _present_fullscreen в координатах монитора, вне
        контекста self.screen). Кэш по (size, alpha) — поверхность
        заполняется один раз, дальше только blit.
        """
        cache = getattr(self, "_fullscreen_dim_shade_cache", None)
        if cache is None:
            cache = self._fullscreen_dim_shade_cache = {}
        key = (size, int(alpha))
        surf = cache.get(key)
        if surf is None:
            surf = pygame.Surface(size, pygame.SRCALPHA)
            surf.fill((0, 0, 0, int(alpha)))
            cache[key] = surf
        return surf

    def _native_base_will_render(self) -> bool:
        """Stage 153 — рисуется ли БАЗОВЫЙ экран нативно в этом кадре.

        Условия: включён нативный путь (монитор 2560×1440) И текущий экран
        мигрирован (пока только MAP; арена/бой/тест-бой — legacy).
        """
        if self._fullscreen_monitor is None or self._ui_scale <= 1.0:
            return False
        if self.state != GameState.MAP or self._arena_active:
            return False
        return "map" in NATIVE_MODAL_REGISTRY

    def _begin_native_base_frame(self) -> bool:
        """Stage 153 — начать кадр с НАТИВНЫМ базовым экраном.

        Возвращает True, если базовый экран будет отрисован нативно (тогда
        `self.screen` = монитор, `_mouse_pos` ×UI_SCALE, `_render_scale` =
        UI_SCALE; вызывающий обязан после рендера экрана вызвать
        `_end_native_base_screen()`).

        False — legacy-кадр как раньше (буфер 1280×720 → `_present_fullscreen`).
        """
        self._legacy_layer_used = False
        self._native_base_active = False
        if not self._native_base_will_render():
            return False
        s = self._ui_scale
        self._native_base_saved = (self.screen, self._mouse_pos, self._render_scale)
        self.screen = self._fullscreen_monitor
        self._mouse_pos = (int(self._mouse_pos[0] * s), int(self._mouse_pos[1] * s))
        self._render_scale = s
        self._native_base_active = True
        return True

    def _end_native_base_screen(self) -> None:
        """Stage 153 — завершить нативный базовый экран, открыть legacy-слой.

        ClickRect'ы базового экрана помечаются `native=True`; дальше рендер
        немигрированных модалок идёт в прозрачный слой 1280×720
        (`_legacy_layer`), который накладывается на монитор в
        `_present_fullscreen`. `_render_scale`/`_mouse_pos` возвращаются к
        legacy-значениям, поэтому код модалок не меняется.
        """
        if not getattr(self, "_native_base_active", False):
            return
        # Stage 159 — БАГФИКС СДВИГА КЛИКОВ НА 2К: раньше помечался срез
        # [от индекса СТАРОГО списка], но _render_map каждый кадр делает
        # self._click_rects = [] (rebind), поэтому срез оказывался пуст и
        # базовые ClickRect'ы со 2-го кадра оставались native=False —
        # хиттест сравнивал дизайн-позицию клика с нативным (×2) rect'ом,
        # и зона клика всех иконок MAP уезжала в верхне-левый квадрант.
        # Сейчас список содержит ТОЛЬКО rect'ы базового рендера — помечаем все.
        for cr in self._click_rects:
            cr.native = True
        screen, mouse, scale = self._native_base_saved
        self._mouse_pos = mouse
        self._render_scale = scale
        # Прозрачный слой для legacy-модалок этого кадра.
        self._legacy_layer.fill((0, 0, 0, 0))
        self.screen = self._legacy_layer
        self._legacy_layer_used = True

    def _native_overlays_will_render(self) -> bool:
        """Stage 150 — отрисуется ли в этом кадре хоть одна нативная модалка.

        Используется диспетчером, чтобы ПРОПУСТИТЬ legacy-рендер модалки,
        которая мигрирована (иначе она рисовалась бы дважды: legacy + native).
        Stage 152 — добавлена кузница. Stage 156 — synth/wardrobe.
        """
        if self._fullscreen_monitor is None or self._ui_scale <= 1.0:
            return False
        if "inventory" in NATIVE_MODAL_REGISTRY and self._inventory_modal_open:
            return True
        if "forge" in NATIVE_MODAL_REGISTRY and self._forge_modal_open:
            return True
        if "synth" in NATIVE_MODAL_REGISTRY and self._synth_modal_open:
            return True
        if "wardrobe" in NATIVE_MODAL_REGISTRY and self._wardrobe_modal_open:
            return True
        if "titles" in NATIVE_MODAL_REGISTRY and self._titles_modal_open:
            return True
        if "shop" in NATIVE_MODAL_REGISTRY and self._shop_modal_open:
            return True
        return False

    def _render_native_overlays(self) -> None:
        """Stage 150 — нативные Hi-DPI-модалки ПОВЕРХ legacy-композита.

        Рисует мигрированные модалки прямо на поверхность монитора
        (self.screen временно = монитор, self._mouse_pos временно = native
        ×UI_SCALE — рендерный код продолжает читать self._mouse_pos как
        обычно). ClickRect'ы, добавленные на этом этапе, помечаются
        native=True — их hit-тест идёт по нативным координатам мыши.
        """
        if not self._native_overlays_will_render():
            return
        overlays = []
        if "inventory" in NATIVE_MODAL_REGISTRY and self._inventory_modal_open:
            # Stage 152 — fade-in инвентаря работает и в нативной фазе
            # (_render_with_fade держит буфер размера монитора).
            overlays.append(
                lambda: self._render_with_fade("inventory", self._render_inventory_modal)
            )
            # Stage 151 — контекст-меню предмета живёт в системе координат
            # инвентаря: нативный инвентарь → нативное меню.
            if self._context_menu_item_id is not None:
                overlays.append(self._render_context_menu)
            # Stage 185 — микро-меню ПКМ поверх инвентаря (нативный слой).
            if self._micromenu_item_id is not None:
                overlays.append(self._render_micromenu)
        if "forge" in NATIVE_MODAL_REGISTRY and self._forge_modal_open:
            # Stage 152 — кузница нативно (тултип гема рисуется внутри).
            overlays.append(self._render_forge_modal)
        if "synth" in NATIVE_MODAL_REGISTRY and self._synth_modal_open:
            # Stage 156 — синтез нативно.
            overlays.append(self._render_synth_modal)
        if "wardrobe" in NATIVE_MODAL_REGISTRY and self._wardrobe_modal_open:
            # Stage 156 — гардероб нативно.
            overlays.append(self._render_wardrobe_modal)
        if "titles" in NATIVE_MODAL_REGISTRY and self._titles_modal_open:
            # Stage 156 — звания нативно (открываются поверх инвентаря).
            overlays.append(self._render_titles_modal)
        if "shop" in NATIVE_MODAL_REGISTRY and self._shop_modal_open:
            # Stage 157 — магазин нативно (тултип предметов рисуется внутри).
            overlays.append(self._render_shop_modal)
        if not overlays:
            return
        real_screen = self.screen
        real_mouse = self._mouse_pos
        real_scale = self._render_scale
        s = self._ui_scale
        self.screen = self._fullscreen_monitor
        self._mouse_pos = (int(real_mouse[0] * s), int(real_mouse[1] * s))
        self._render_scale = s
        n0 = len(self._click_rects)
        try:
            for fn in overlays:
                fn()
        finally:
            for cr in self._click_rects[n0:]:
                cr.native = True
            self.screen = real_screen
            self._mouse_pos = real_mouse
            self._render_scale = real_scale

    def _render_active_drag_ghosts(self) -> None:
        """Stage 164 — активные drag-призраки (инвентарь + слоты синтеза).

        Вызывается в КОНКРЕТНОЙ фазе рендера: legacy (буфер до композита)
        или native (монитор, поверх всех модалок). Призрак рисуется
        ПОСЛЕДНИМ в кадре — он больше не прячется за окнами синтеза/
        гардероба (жалоба пользователя: костюм пропадал при переносе).
        """
        if self._drag_item_id is not None:
            self._render_dragged_icon()
        if getattr(self, "_synth_slot_drag", None) is not None:
            self._render_synth_slot_drag_ghost()

    def _render_drag_ghost_topmost(self) -> None:
        """Stage 164 — drag-призрак ПОВЕРХ ВСЕХ окон.

        Если в кадре есть нативные модалки (2K-путь) — призрак рисуется на
        мониторе в нативной фазе (после _render_native_overlays); иначе —
        в legacy-буфер до композита (вызов в run() ПЕРЕД
        _present_fullscreen). В обоих случаях призрак оказывается верхним
        слоем кадра.
        """
        if (self._drag_item_id is None
                and getattr(self, "_synth_slot_drag", None) is None):
            return
        if self._native_overlays_will_render():
            real_screen = self.screen
            real_mouse = self._mouse_pos
            real_scale = self._render_scale
            s = self._ui_scale
            self.screen = self._fullscreen_monitor
            self._mouse_pos = (int(real_mouse[0] * s), int(real_mouse[1] * s))
            self._render_scale = s
            try:
                self._render_active_drag_ghosts()
            finally:
                self.screen = real_screen
                self._mouse_pos = real_mouse
                self._render_scale = real_scale
        else:
            self._render_active_drag_ghosts()

    def _map_battle_mouse(self, event) -> None:
        """Stage 139.3 — ремап мыши: координаты окна монитора → UI 1280×720.

        MAP/прочие: игра растянута на весь монитор — линейный обратный масштаб.
        BATTLE/TEST_BATTLE: игровая сцена в окне 60% монитора — переводим
        позицию внутри окна → UI-координаты. Клики вне окна клампятся.
        """
        pos = getattr(event, "pos", None)
        if pos is None:
            return
        if self._fullscreen_monitor is None:
            return
        from pockie_rpg.config import BATTLE_WINDOW_SCALE
        mw, mh = self._fullscreen_monitor.get_size()
        mx, my = pos
        if self.state in (GameState.BATTLE, GameState.TEST_BATTLE):
            win_w = int(mw * BATTLE_WINDOW_SCALE)
            win_h = int(mh * BATTLE_WINDOW_SCALE)
            win_x = (mw - win_w) // 2
            win_y = (mh - win_h) // 2
            ux = (mx - win_x) * SCREEN_WIDTH / win_w
            uy = (my - win_y) * SCREEN_HEIGHT / win_h
        else:
            # Полное растяжение: монитор → UI линейно.
            ux = mx * SCREEN_WIDTH / mw
            uy = my * SCREEN_HEIGHT / mh
        ux = max(0, min(SCREEN_WIDTH - 1, ux))
        uy = max(0, min(SCREEN_HEIGHT - 1, uy))
        try:
            event.pos = (int(round(ux)), int(round(uy)))
        except Exception:
            pass

    def _ui_mouse_pos(self, pos: tuple[int, int]) -> tuple[int, int]:
        """Stage 139.2 — get_pos() → UI-координаты (универсальный ремап)."""
        evt = pygame.event.Event(pygame.MOUSEMOTION, {"pos": pos})
        self._map_battle_mouse(evt)
        return evt.pos

    def _render_modal_scaled(self, render_fn, *args, scale=None, **kwargs) -> None:
        """Stage 140/141 — отрендерить модалку в под-буфер и блитить с масштабом.

        scale: коэффициент (None → авто). Stage 141: инвентарь передаёт
        MODAL_SCALE_INVENTORY=1.0 (сетка 57, иконки 51×51 1:1).
        Stage 152 — авто-выбор: на НАТИВНОМ 2К (монитор + _ui_scale>1) берётся
        MODAL_SCALE_2K=1.0 (прямой рендер, один апскейл ×2 — крупнее и чётче),
        иначе MODAL_SCALE=0.5 (оконный режим/не-2К — поведение как раньше).
        render_fn рисует в self.screen (как обычно). Подмена: self.screen
        временно = полноэкранный под-буфер; после рендера содержимое блитится
        уменьшенным по центру, ClickRect'ы/layout'ы масштабируются, мышь на
        время рендера переводится в координаты полного буфера.
        """
        if scale is None:
            from pockie_rpg.config import MODAL_SCALE, MODAL_SCALE_2K
            if self._fullscreen_monitor is not None and self._ui_scale > 1.0:
                scale = MODAL_SCALE_2K
            else:
                scale = MODAL_SCALE
        if scale >= 1.0:
            render_fn(*args, **kwargs)
            return
        real_screen = self.screen
        # Полный под-буфер: модалки рисуют по абсолютным координатам 1280×720.
        sub = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        self.screen = sub
        # Мышь: переводим UI-координаты → координаты полного буфера
        # (hover-эффекты внутри модалки должны срабатывать корректно).
        off_x = (SCREEN_WIDTH - int(SCREEN_WIDTH * scale)) // 2
        off_y = (SCREEN_HEIGHT - int(SCREEN_HEIGHT * scale)) // 2
        real_mouse = self._mouse_pos
        self._mouse_pos = (
            int((real_mouse[0] - off_x) / scale),
            int((real_mouse[1] - off_y) / scale),
        )
        n_before = len(self._click_rects)
        try:
            render_fn(*args, **kwargs)
        finally:
            self.screen = real_screen
            self._mouse_pos = real_mouse
        # Blit уменьшенной копии по центру.
        small_w = int(SCREEN_WIDTH * scale)
        small_h = int(SCREEN_HEIGHT * scale)
        small = pygame.transform.smoothscale(sub, (small_w, small_h))
        sub_scaled = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        sub_scaled.blit(
            small,
            (off_x, off_y),
        )
        real_screen.blit(sub_scaled, (0, 0))

        def _scaled_rect(r: pygame.Rect) -> pygame.Rect:
            return pygame.Rect(
                off_x + int(r.x * scale), off_y + int(r.y * scale),
                max(2, int(r.w * scale)), max(2, int(r.h * scale)),
            )

        # ClickRect'ы, добавленные за время рендера модалки.
        for cr in self._click_rects[n_before:]:
            cr.rect = _scaled_rect(cr.rect)
        # Stage 140 — layout'ы инвентаря (drag&drop работает по UI-мыши):
        # масштабируем сохранённые при рендере координаты ячеек.
        if hasattr(self, "_inv_layout") and self._inv_layout:
            self._inv_layout = [
                (idx, _scaled_rect(r), span) for idx, r, span in self._inv_layout
            ]
        if hasattr(self, "_gear_layout") and self._gear_layout:
            self._gear_layout = {
                name: _scaled_rect(r) for name, r in self._gear_layout.items()
            }
        if hasattr(self, "_inv_tab_rects") and self._inv_tab_rects:
            self._inv_tab_rects = {
                p: _scaled_rect(r) for p, r in self._inv_tab_rects.items()
            }
        # Stage 140 — слоты гардероба (клики/drag). Stage 164 — лента
        # костюмов синтеза (_synth_outfit_strip) удалена вместе со старой
        # loc-моделью слотов.
        if getattr(self, "_wardrobe_layout", None):
            self._wardrobe_layout = [_scaled_rect(r) for r in self._wardrobe_layout]

    def _toggle_fullscreen(self) -> None:
        """Stage 139.2 — F11: обычное окно 1280×720 ↔ окно на весь монитор.

        Оба режима композитные (UI-буфер 1280×720); F11 переключает размер
        ОКНА: рабочий стол ↔ маленькое окно. set_mode ВОЗВРАЩАЕТ surface —
        надёжнее get_surface() (в dummy после повторного set_mode get_surface
        может вернуть None).

        Stage 158 — БАГФИКС: в конце метода жил pygame.quit() (наследие
        до-Stage-139 semantics «F11 = выход»): display умирал, следующий кадр
        падал с «Surface is not initialized» на первом blit. Убрано — F11
        ПЕРЕКЛЮЧАЕТ окно и продолжает цикл. Кэш _su_overlay/fade-буферов
        чистится: их размеры привязаны к старой поверхности монитора.
        """
        if self._fullscreen_on:
            # весь монитор → маленькое окно 1280×720 (без композита).
            self._fullscreen_monitor = None
            self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
            self._fullscreen_game = None
            self._fullscreen_on = False
            # Stage 158 — нативный путь выключен в маленьком окне.
            self._ui_scale = 1.0
        else:
            # маленькое окно → весь рабочий стол (Stage 139.2, NOFRAME).
            try:
                desk_w, desk_h = pygame.display.get_desktop_sizes()[0]
            except Exception:
                desk_w, desk_h = SCREEN_WIDTH, SCREEN_HEIGHT
            flags = pygame.NOFRAME if FRAMELESS_ENABLED else 0
            self._fullscreen_monitor = pygame.display.set_mode(
                (desk_w, desk_h), flags
            )
            self._fullscreen_game = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            self.screen = self._fullscreen_game
            self._fullscreen_on = True
            # Stage 158 — пересчёт нативного масштаба (при DPI-aware
            # рабочий стол = физические пиксели монитора).
            try:
                mw, mh = self._fullscreen_monitor.get_size()
            except Exception:
                mw, mh = SCREEN_WIDTH, SCREEN_HEIGHT
            self._ui_scale = compute_ui_scale(mw, mh)
        # Stage 158 — кэши размером «старой поверхности» недействительны.
        self._su_overlay_cache = {}
        self._fade_buffers = {}
        self._panel_gradient_cache = {}
        self._legacy_layer_scaled = None
        # НЕ quit: цикл продолжается.

    def _enter_battle(self) -> None:
        """Transition MAP -> BATTLE."""
        suit = STARTER_SUITS.get(self.player.suit_id)
        enemy = ENEMY_MOBS.get(self.target_mob_id)
        if suit is None or enemy is None:
            return
        # Stage 95 — track daily quest: arena fights (if arena is active).
        if self._arena_active:
            self._track_daily_quest("arena_fights")
        # Stage 89 — mark battle mode for endgame reward dispatch.
        self._battle_mode = BattleMode.NORMAL
        self._tower_active_floor = None
        self._tower_active_is_boss = False
        self._tower_active_modifiers = ()
        self._tower_reward_applied = False

        player_role = ROLES.get(self.player.role_id)
        enemy_role = ROLES.get(enemy.role_id)
        if player_role is None or enemy_role is None:
            return

        self._player_fighter = Fighter.from_player_state(self.player, player_role)
        self._enemy_fighter = Fighter.from_role(
            enemy_role,
            is_player=False,
            level=enemy.level,
            hp_mul=enemy.hp_mul,
            atk_mul=enemy.atk_mul,
        )

        player_flip = self.asset_manager.needs_flip_for_player(suit.motion_folder)
        self._player_animator = IdleAnimator(
            folder=suit.motion_folder,
            flip=player_flip,
            phase=0.0,
            is_player=True,
            action="idle",
            idle_folder=suit.motion_folder,
        )

        enemy_motion_folder = MOB_TO_MOTION.get(enemy.mob_id, "samurai_idle")
        enemy_flip = self.asset_manager.needs_flip_for_enemy(
            enemy_motion_folder, mob_id=enemy.mob_id
        )
        self._enemy_animator = IdleAnimator(
            folder=enemy_motion_folder,
            flip=enemy_flip,
            phase=math.pi,
            is_player=False,
            role_id=enemy.role_id,
            action="idle",
            idle_folder=enemy_motion_folder,
        )

        self._player_hp_display = float(self._player_fighter.hp)
        self._player_mp_display = float(self._player_fighter.mp)
        self._enemy_hp_display = float(self._enemy_fighter.hp)
        self._enemy_mp_display = float(self._enemy_fighter.mp)

        self._active_attack_seq = None
        self._player_hit_timer = 0.0
        self._enemy_hit_timer = 0.0
        self._enemy_shake_timer = 0.0

        self._combat_replay = None
        self._replay_event_idx = 0
        self._replay_timer = 0.0
        self._endgame_active = False
        self._endgame_timer = 0.0
        self._combat_log_lines.clear()
        self._combat_log_expanded = False
        self._combat_log_height_display = float(LOG_BAR_H)
        self._speed_buttons_y_offset = 0.0

        self._countdown_active = True
        self._countdown_timer = 0.0
        self._countdown_phase_idx = 0

        self._char_sheet_open = False
        self._char_sheet_closing = False
        self._char_sheet_anim_t = 0.0
        self._char_sheet_origin = "left"
        self._char_sheet2_open = False
        self._char_sheet2_closing = False
        self._char_sheet2_anim_t = 0.0
        self._char_sheet2_origin = "right"

        self._battle_speed = float(BATTLE_SPEED_DEFAULT)
        self._particles.clear()
        self._damage_numbers.clear()
        self._player_ice.deactivate()
        self._enemy_ice.deactivate()
        self._player_shield.deactivate()
        self._enemy_shield.deactivate()
        self._player_cloud.deactivate()
        self._enemy_cloud.deactivate()
        self._player_poison.deactivate()
        self._enemy_poison.deactivate()
        self._cast_effect.deactivate()
        self._projectile_effect.deactivate()

        # Stage 160 — снапшот фона локации для боя (фон не меняется в бою).
        self._capture_battle_bg_snapshot()

        self.state = GameState.BATTLE
        # Stage 200 — подложки имён появляются с fade при каждом входе в бой.
        self._hud_plate_fade = 0.0

    def _exit_battle(self) -> None:
        """Transition BATTLE -> MAP."""
        # Stage 170 — ESC посреди гантлета: корректная финализация вместо
        # «сгоревшего» ролла (до recalc_stats/flush — как в
        # _finish_gauntlet_round; для завершённого/чужого режима — no-op).
        self._finalize_gauntlet_on_exit()
        self.player.recalc_stats()  # ensure cached stats reflect current gear
        # Stage 134 — slot gauntlet carries remaining HP/MP out of the chain
        # (sync in _finish_gauntlet_round is authoritative); full-heal only
        # for the other battle modes.
        if self._battle_mode != BattleMode.SLOT_GAUNTLET:
            self.player.current_hp = self.player.stats.max_hp
            self.player.current_mp = self.player.stats.max_mp
        # Stage 88 — Fix 2.5: flush pending save on screen transition (so
        # battle rewards are persisted before any further UI interaction).
        self.save_mgr.flush()

        # Stage 89/92 — clear Tower battle context (per §17 item 6).
        # Stage 92 — Tower battles return to Las Noches (not City), and the
        # Tower result modal is shown on the MAP screen automatically.
        was_tower = (self._battle_mode == BattleMode.TOWER)
        if was_tower:
            # Return to Las Noches (the Tower hub).
            from pockie_rpg.config import MapLocation
            self._map_location = MapLocation.LAS_NOCHES
            # The Tower result modal will be shown via _render_tower_result.
            # No need to reopen the Tower floor-list modal — the result modal
            # handles that via _close_tower_result().
        self._battle_mode = BattleMode.NORMAL
        self._tower_active_floor = None
        self._tower_active_is_boss = False
        self._tower_active_modifiers = ()
        self._tower_reward_applied = False

        self.state = GameState.MAP
        self._player_animator = None
        self._enemy_animator = None
        self._player_fighter = None
        self._enemy_fighter = None
        self._active_attack_seq = None
        self._player_hit_timer = 0.0
        self._enemy_hit_timer = 0.0
        self._enemy_shake_timer = 0.0
        self._countdown_active = False
        self._countdown_timer = 0.0
        self._countdown_phase_idx = 0
        self._combat_replay = None
        self._replay_event_idx = 0
        self._replay_timer = 0.0
        self._endgame_active = False
        self._endgame_text = ""
        self._endgame_phase = "text"
        self._endgame_text_timer = 0.0
        self._endgame_xp_gained = 0
        self._endgame_gold_gained = 0
        self._endgame_leveled_up = False
        self._endgame_old_level = 1
        self._endgame_new_level = 1
        self._combat_log_lines.clear()
        self._combat_log_expanded = False
        self._combat_log_height_display = float(LOG_BAR_H)
        self._speed_buttons_y_offset = 0.0
        self._skills_modal_open = False
        self._char_sheet_open = False
        self._char_sheet_closing = False
        self._char_sheet_anim_t = 0.0
        self._char_sheet_origin = "left"
        # Stage 63 — also reset slot 2 on exit battle.
        self._char_sheet2_open = False
        self._char_sheet2_closing = False
        self._char_sheet2_anim_t = 0.0
        self._char_sheet2_origin = "right"

        self._battle_speed = float(BATTLE_SPEED_DEFAULT)
        self._particles.clear()
        self._damage_numbers.clear()
        self._player_ice.deactivate()
        self._enemy_ice.deactivate()
        self._player_shield.deactivate()
        self._enemy_shield.deactivate()
        self._player_cloud.deactivate()
        self._enemy_cloud.deactivate()
        self._player_poison.deactivate()
        self._enemy_poison.deactivate()
        self._cast_effect.deactivate()
        self._projectile_effect.deactivate()
        # Stage 71/72/77 — reset World Boss fight state (but keep boss HP + attempts).
        self._world_boss_active = False
        self._world_boss_damage_dealt = 0
        self._world_boss_rank = ""
        self._world_boss_killed = False
        self._world_boss_error = False
        self._world_boss_item_drop = None

    def _open_char_sheet(self, target: str, origin: str = "left") -> None:
        """Stage 63/97 — Open char sheet.

        Stage 97 — in BATTLE, clicking EITHER target opens BOTH sheets
        simultaneously. Closing one closes both.
        """
        if self.state == GameState.BATTLE:  # open both simultaneously
            # If either is already open, close both.
            if self._char_sheet_open or self._char_sheet2_open:
                self._close_char_sheet()
                self._close_char_sheet2()
                return
            # Open player (slot 1, left).
            self._char_sheet_open = True
            self._char_sheet_target = "player"
            self._char_sheet_origin = "left"
            self._char_sheet_anim_t = 1.0
            self._char_sheet_closing = False
            # Open enemy (slot 2, right) simultaneously.
            self._char_sheet2_open = True
            self._char_sheet2_target = "enemy"
            self._char_sheet2_origin = "right"
            self._char_sheet2_anim_t = 1.0
            self._char_sheet2_closing = False
        else:
            # MAP / TEST — single window (slot 1 only).
            if self._char_sheet_open and self._char_sheet_target == target:
                self._close_char_sheet()
            else:
                self._char_sheet_open = True
                self._char_sheet_target = target
                self._char_sheet_origin = origin
                self._char_sheet_anim_t = 1.0
                self._char_sheet_closing = False

    def _close_char_sheet2(self) -> None:
        """Stage 63/97 — close the second char sheet (enemy, right side).
        Stage 97 — closing either sheet closes BOTH."""
        if not self._char_sheet2_open:
            return
        self._char_sheet2_closing = True
        # Stage 97 — also close the player sheet.
        if self._char_sheet_open:
            self._char_sheet_closing = True

    def _close_char_sheet(self) -> None:
        """Stage 63/97 — close the character sheet modal.
        Stage 97 — closing either sheet closes BOTH."""
        if not self._char_sheet_open:
            return
        self._char_sheet_closing = True
        # Stage 97 — also close the enemy sheet.
        if self._char_sheet2_open:
            self._char_sheet2_closing = True

    def _open_skills_modal(self) -> None:
        """Open the skills modal on the MAP screen."""
        self._skills_modal_open = True

    def _close_skills_modal(self) -> None:
        """Close the skills modal on the MAP screen."""
        self._skills_modal_open = False

    def _reset_player_progression(self) -> None:
        """Reset player to level 1 with base stats. Stage 78 — also reset boss.

        Stage 182 — сброс также снимает все активные бафы (reset_progression
        очищает active_buffs — иконки под аватаркой исчезают сразу).
        """
        self.player.reset_progression()
        # Stage 78 — reset World Boss to level 1, full HP, 3 attempts.
        self.player.world_boss_hp = None
        self.player.world_boss_attempts = 3
        self.player.world_boss_next_attempt_ts = None
        self._spawn_world_boss()  # re-spawn fresh boss at level 1
        # Stage 88 — Fix 2.5: use debounced autosave instead of direct save.
        self.save_mgr.mark_dirty()

    def _debug_level_up(self) -> None:
        """Stage 51 — debug +1 level button. Forces one level-up by adding
        enough XP to trigger exactly one level. For testing all player levels.
        """
        from pockie_rpg.config import MAX_LEVEL
        if self.player.level >= MAX_LEVEL:
            return
        # Add exactly enough XP to trigger one level-up.
        self.player.current_xp = self.player.max_xp
        self.player.gain_xp(0)  # gain_xp processes the level-up loop
        # Refresh cached HP/MP to new max after stat growth.
        self.player.recalc_stats()
        self.player.current_hp = self.player.stats.max_hp
        self.player.current_mp = self.player.stats.max_mp
        self._save_player()

    def _open_quick_battle_modal(self) -> None:
        self._quick_battle_modal_open = True

    def _close_quick_battle_modal(self) -> None:
        self._quick_battle_modal_open = False

    def _close_quick_battle_result(self) -> None:
        self._quick_battle_result = None
        # Stage 119 — reset loot grid pagination page back to 0 for next session.
        self._loot_page = 0

    def _open_inventory_modal(self) -> None:
        self._inventory_modal_open = True
        self._modal_fade_target = 1.0  # Stage 128 — fade in.
        self._modal_fade_begin("inventory")  # Stage 152 — общий fade 0.15с.

    def _close_inventory_modal(self) -> None:
        self._inventory_modal_open = False
        self._modal_fade_target = 0.0  # Stage 128 — fade out.
        self._modal_fade_end("inventory")

    # -----------------------------------------------------------------
    # Stage 128 — Modal fade-in/out animation
    # -----------------------------------------------------------------

    def _update_modal_fade(self, dt: float) -> None:
        """Stage 128 — Animate the modal fade alpha toward the target.

        When a modal opens, alpha ramps from current → 1.0.
        When a modal closes, alpha ramps from current → 0.0.
        The fade is smooth (linear interpolation at _modal_fade_speed per second).
        """
        if self._modal_fade_alpha == self._modal_fade_target:
            return  # already at target, no animation needed.
        delta = self._modal_fade_speed * dt
        if self._modal_fade_target > self._modal_fade_alpha:
            self._modal_fade_alpha = min(self._modal_fade_target, self._modal_fade_alpha + delta)
        else:
            self._modal_fade_alpha = max(self._modal_fade_target, self._modal_fade_alpha - delta)

    def _get_modal_fade_alpha(self) -> float:
        """Stage 128 — Get the current modal fade alpha (0.0-1.0).

        Used by modal render methods to apply a semi-transparent overlay
        during the fade animation. When alpha < 1.0, the modal is still
        animating in (or out). The render method can use this to:
          - Scale the modal position (slide-in effect)
          - Apply alpha to the modal background
          - Skip rendering child elements when alpha is very low
        """
        return self._modal_fade_alpha

    def _set_inv_page(self, page: int) -> None:
        """Stage 64 — switch the inventory modal to page 1, 2, or 3.

        Switching pages closes the context menu and resets click-gesture
        tracking (so a click that started on page 1 doesn't open a menu
        on page 2).

        Stage 67 — **does NOT cancel an in-flight drag**. The drag continues
        across page switches so the player can move items between pages:
        start dragging on page 1, click tab "2", release on a page-2 slot.
        """
        from pockie_rpg.config import INVENTORY_PAGE_KEYS
        if page not in INVENTORY_PAGE_KEYS:
            page = 1
        if self._inv_current_page == page:
            return
        self._inv_current_page = page
        # Stage 67 — keep drag alive across page switches (cross-page drag).
        # Only reset click-gesture tracking.
        self._mouse_down_pos = None
        self._mouse_down_slot = None
        # Stage 185 — микро-меню ПКМ закрывается при смене страницы.
        self._close_micromenu()

    def _toggle_sell_menu(self) -> None:
        """Stage 143 — раскрыть/закрыть суб-меню качества у кнопки «Продать»."""
        self._inv_sell_menu_open = not getattr(self, "_inv_sell_menu_open", False)

    def _sell_all_rarity(self, rarity: str) -> None:
        """Stage 143 — продать ВСЕ предметы указанного качества из инвентаря.

        Замена «Продать серые» (Stage 119): игрок выбирает качество в
        суб-меню (Grey/Blue/Purple/Gold/Red) — все предметы этого качества
        продаются автоматически. Не трогает надетый гир. Авто-прод удалён.
        Stage 187 — массовая продажа НЕ трогает БАФЫ и КОСТЮМЫ (слот
        consumable/outfit): она предназначена только для экипировки.
        """
        if self.player is None:
            return
        from pockie_rpg.config import INVENTORY_PAGE_KEYS
        from pockie_rpg.data.item_db import get_sell_price

        sold_count = 0
        total_gold = 0
        items_to_sell: list[str] = []
        for page in INVENTORY_PAGE_KEYS:
            for iid in self.player.inv_page_slots(page):
                if iid is None:
                    continue
                # Stage 183 — распаковка стака: продаётся каждый предмет стака.
                sid = self.player.slot_item_id(iid)
                if sid is None:
                    continue
                item = self.player.get_item_definition(sid)
                if item is None:
                    continue
                # Stage 187 — бафы и костюмы не продаются массово.
                if item.get("is_buff") or item.get("slot") == "outfit":
                    continue
                if item.get("rarity") == rarity:
                    price = item.get("sell_price", 0)
                    if price <= 0:
                        price = get_sell_price(sid)
                    if price > 0:
                        items_to_sell.extend([sid] * self.player.slot_count(iid))

        for iid in items_to_sell:
            item = self.player.get_item_definition(iid)
            if item is None:
                continue
            price = item.get("sell_price", 0)
            if price <= 0:
                price = get_sell_price(iid)
            if price <= 0:
                continue
            self.player.inv_remove(iid)
            if iid in self.player.generated_weapons:
                del self.player.generated_weapons[iid]
            # Stage 148 — удалить якорь проданного предмета (липкий layout).
            if hasattr(self, "_inv_item_anchor_memory"):
                self._inv_item_anchor_memory.pop(iid, None)
            self.player.gain_gold(price)
            sold_count += 1
            total_gold += price

        # Закрыть суб-меню после действия; якорная память не трогается —
        # Stage 148: непроданные предметы сохраняют свои позиции (липкий layout).
        self._inv_sell_menu_open = False
        if sold_count > 0:
            self._gold_flash_timer = 1.0
            self._gold_flash_amount = total_gold
            self._save_player()
            if hasattr(self, "_test_panel_toast"):
                self._test_panel_toast = f"Продано {sold_count} предм. (+{total_gold} зол.)"
                self._test_panel_toast_timer = 2.5
        else:
            if hasattr(self, "_test_panel_toast"):
                self._test_panel_toast = "Нет предметов этого качества"
                self._test_panel_toast_timer = 2.0

    def _sort_inventory(self) -> None:
        """Stage 67/117/148 — sort inventory: group items by slot type, then redistribute.

        Canonical order: weapon → head → body → hands → belt → boots → accessory.
        Within each group, items are sorted by item_level ascending.
        All pages are cleared, then items are packed page 1 → 2 → 3 in order.

        Stage 117 — now uses player.get_item_definition() instead of get_equipment()
        so generated items (gen_w_*) are sorted correctly by their slot + level.

        Stage 148 — ЕДИНСТВЕННЫЙ авто-перепаковщик: сбрасывает якорную
        память ЛИШЬ для отсортированных страниц, после чего layout заново
        «прилипает» к свежеупакованным позициям. Ручные drag-перемещения
        НЕ сортируют ничего автоматически.
        """
        from pockie_rpg.config import INVENTORY_PAGE_KEYS

        # 1. Collect all items across all pages.
        # Stage 183 — стаки разворачиваются в N копий item_id: после
        # перераспределения через inv_add стак снова соберётся в одну ячейку.
        all_items: list[str] = []
        for page in INVENTORY_PAGE_KEYS:
            for iid in self.player.inv_page_slots(page):
                if iid is None:
                    continue
                sid = self.player.slot_item_id(iid)
                if sid is None:
                    continue
                all_items.extend([sid] * self.player.slot_count(iid))

        if not all_items:
            return  # nothing to sort.

        # 2. Sort by (slot_order, item_level).
        slot_order = {
            "weapon": 0, "head": 1, "body": 2, "hands": 3,
            "belt": 4, "boots": 5, "accessory": 6,
        }

        def sort_key(item_id: str):
            # Stage 117 — use get_item_definition for generated items.
            gear = self.player.get_item_definition(item_id)
            if gear is None:
                return (99, 0)
            return (slot_order.get(gear.get("slot", ""), 99), gear.get("item_level", 1))

        all_items.sort(key=sort_key)

        # 3. Clear all pages, then redistribute in sorted order.
        for page in INVENTORY_PAGE_KEYS:
            slots = self.player.inv_page_slots(page)
            for i in range(len(slots)):
                slots[i] = None
        # Stage 147/148 — якорная память сбрасывается (сортировка = единственный
        # авто-перепаковщик; новые позиции заново «прилипнут» при рендере).
        if hasattr(self, "_inv_item_anchor_memory"):
            self._inv_item_anchor_memory.clear()
        for item_id in all_items:
            self.player.inv_add(item_id)

        self._save_player()

    def _open_forge_modal(self) -> None:
        """Stage 47 — open the Forge (Кузница) modal."""
        self._forge_modal_open = True
        # Close inventory to avoid overlap.
        self._inventory_modal_open = False

    def _open_shop(self) -> None:
        """Stage 59/131 — open the Shop modal."""
        self._shop_modal_open = True
        self._shop_active_tab = 0
        if self.player.level != self._shop_last_level or not self._shop_items:
            self._generate_shop_items()

    def _close_shop(self) -> None:
        """Stage 59 — close the Shop modal."""
        self._shop_modal_open = False

    def _generate_shop_items(self) -> None:
        """Stage 131 — Generate 5 random shop items based on player level.

        Rules:
        - Items are Grey or Blue only.
        - Item level matches player level (closest WEAPON_LEVELS).
        - At least 1 weapon always.
        - Other 4 are random types from all 7 slots.
        """
        import random as _rng

        from pockie_rpg.config import WEAPON_LEVELS

        player_lvl = self.player.level
        closest = min(WEAPON_LEVELS, key=lambda lv: abs(lv - player_lvl))
        item_types = ["weapon", "armor", "boots", "ring", "gloves", "belt", "head"]
        result: list[str] = []

        result.append(self.player.give_test_item(closest, _rng.choice(["Grey", "Blue"]), "weapon"))
        for _ in range(4):
            t = _rng.choice(item_types)
            r = _rng.choice(["Grey", "Blue"])
            gen_id = self.player.give_test_item(closest, r, t)
            if gen_id:
                result.append(gen_id)

        self._shop_items = [g for g in result if g]
        self._shop_last_level = player_lvl
        self._shop_equipment_page = 0

    def _refresh_shop(self) -> None:
        """Stage 131 — Refresh shop items for 10k gold."""
        SHOP_REFRESH_COST = 10000
        if self.player.gold < SHOP_REFRESH_COST:
            self._test_panel_toast = "Недостаточно золота!"
            self._test_panel_toast_timer = 2.0
            return
        self.player.gain_gold(-SHOP_REFRESH_COST)
        self._generate_shop_items()
        self._test_panel_toast = "Ассортимент обновлён!"
        self._test_panel_toast_timer = 2.0
        self._save_player()

    # ------------------------------------------------------------------
    # Stage 89 — TOWER MODE methods (per TOWER_MODE_IMPLEMENTATION.md)
    # ------------------------------------------------------------------

    def _open_tower(self) -> None:
        """Stage 91 — City Tower card now navigates to Las Noches location
        (not directly to the Tower modal). The guardian NPC there opens the
        dialog flow → Tower modal.
        """
        from pockie_rpg.config import MapLocation
        self._map_location = MapLocation.LAS_NOCHES
        # Close all Tower modals so they don't show over the Las Noches scene.
        self._tower_modal_open = False
        self._tower_shop_open = False
        self._tower_result = None
        # Reset dialog state.
        self._las_noches_dialog = None  # None | "welcome" | "shop_offer"

    def _enter_las_noches_guardian(self) -> None:
        """Stage 91 — click on the Las Noches guardian NPC.

        Opens the first dialog window (welcome + warning). Player chooses
        Cancel (close) or Accept (proceed to shop offer window).
        Stage 161 — вместо чёрного затемнения фон диалога = разовый блюр
        экрана локации. Stage 165 — подложки больше НЕТ: диалог рисуется
        поверх неизменённой сцены (как «Карта мира»/магазин).
        """
        self._las_noches_dialog = "welcome"

    def _las_noches_cancel(self) -> None:
        """Stage 91 — Cancel button in the welcome dialog."""
        self._las_noches_dialog = None

    def _las_noches_accept(self) -> None:
        """Stage 91 — Accept button in the welcome dialog → shop offer."""
        self._las_noches_dialog = "shop_offer"

    def _las_noches_back(self) -> None:
        """Stage 91 — Back button in the shop offer dialog → welcome."""
        self._las_noches_dialog = "welcome"

    def _las_noches_open_shop(self) -> None:
        """Stage 91 — Shop button in the shop offer dialog → Tower Shop."""
        self._las_noches_dialog = None
        self._open_tower_shop()

    def _las_noches_enter_tower(self) -> None:
        """Stage 91 — Enter button in the shop offer dialog → Tower modal."""
        self._las_noches_dialog = None
        self._tower_modal_open = True
        self._tower_shop_open = False
        self._tower_result = None
        # Center the view on the current floor.
        self._tower_selected_floor = self.player.tower_current_floor
        self._tower_scroll_offset = max(0, self._tower_selected_floor - 5)

    def _exit_las_noches(self) -> None:
        """Stage 91 — return from Las Noches to the City."""
        from pockie_rpg.config import MapLocation
        self._map_location = MapLocation.CITY
        self._las_noches_dialog = None

    def _close_tower(self) -> None:
        """Close the Tower modal."""
        self._tower_modal_open = False
        self._tower_shop_open = False

    def _open_tower_shop(self) -> None:
        """Open the Tower Shop sub-modal."""
        self._tower_shop_open = True

    def _close_tower_shop(self) -> None:
        """Close the Tower Shop sub-modal."""
        self._tower_shop_open = False

    def _select_tower_floor(self, floor: int) -> None:
        """Select a floor row in the Tower modal (highlights it)."""
        self._tower_selected_floor = floor

    def _scroll_tower(self, delta: int) -> None:
        """Scroll the Tower floor list up/down by ``delta`` rows."""
        from pockie_rpg.config import TOWER_FLOORS_VISIBLE, TOWER_MAX_FLOOR
        max_offset = max(0, TOWER_MAX_FLOOR - TOWER_FLOORS_VISIBLE)
        self._tower_scroll_offset = max(0, min(max_offset, self._tower_scroll_offset + delta))

    def _enter_tower_battle(self, floor: int) -> None:
        """Transition MAP -> BATTLE for a Tower fight.

        Per §12: validates the floor, consumes an attempt, builds the player
        + enemy Fighters, and reuses the same replay infrastructure as
        normal battles. Sets ``_battle_mode = BattleMode.TOWER`` so the endgame flow
        dispatches to ``_finish_tower_battle``.
        """
        from pockie_rpg.combat.fighter import Fighter
        from pockie_rpg.data.enemy_db import ENEMY_DB
        from pockie_rpg.data.tower_db import get_tower_boss, get_tower_floor

        tower_floor = get_tower_floor(floor)
        if tower_floor is None:
            return
        # Consume attempt (defensive — caller checks can_enter_tower first).
        if not self.player.start_tower_attempt(floor):
            return

        # Look up the enemy template (visual + base stats).
        enemy_tmpl = ENEMY_DB.get(tower_floor.enemy_id)
        if enemy_tmpl is None:
            return
        enemy_role = ROLES.get(enemy_tmpl.role_id)
        player_role = ROLES.get(self.player.role_id)
        if player_role is None or enemy_role is None:
            return

        # Build the player Fighter (same as normal battle).
        suit = STARTER_SUITS.get(self.player.suit_id)
        if suit is None:
            return
        self._player_fighter = Fighter.from_player_state(self.player, player_role)

        # Build the enemy Fighter with Tower multipliers + boss skill deck.
        boss = get_tower_boss(floor) if tower_floor.is_boss else None
        boss_skills = boss.skills if boss is not None else enemy_tmpl.skills
        self._enemy_fighter = Fighter.from_role(
            enemy_role,
            is_player=False,
            level=enemy_tmpl.level,
            hp_mul=enemy_tmpl.hp_mul * tower_floor.hp_multiplier,
            atk_mul=enemy_tmpl.atk_mul * tower_floor.attack_multiplier,
            skills=tuple(boss_skills) if boss_skills else (),
        )
        # Apply simple pre-battle modifiers (boss_fast_start → bonus action points).
        if "boss_fast_start" in tower_floor.modifiers:
            # Stage 91 — use starting_action_points (FightSystem.fight() reads
            # this field instead of resetting action_points to 0.0).
            self._enemy_fighter.starting_action_points = 0.5  # half-turn head start
        if "boss_poison_resistance" in tower_floor.modifiers:
            self._enemy_fighter.tough_rating += 200

        # Animators (reuse existing motion mapping).
        player_flip = self.asset_manager.needs_flip_for_player(suit.motion_folder)
        self._player_animator = IdleAnimator(
            folder=suit.motion_folder, flip=player_flip, phase=0.0,
            is_player=True, action="idle", idle_folder=suit.motion_folder,
        )
        # Enemy motion folder — tower floors use existing mob IDs, so look up
        # via the enemy_id. For flower_1 it's "flower/idle", for samurai_* it's
        # "samurai/idle" / "blue_swordsman/idle" / "black_samurai/idle".
        enemy_motion_folder = self._tower_enemy_motion_folder(tower_floor.enemy_id)
        enemy_flip = self.asset_manager.needs_flip_for_enemy(enemy_motion_folder)
        self._enemy_animator = IdleAnimator(
            folder=enemy_motion_folder, flip=enemy_flip, phase=math.pi,
            is_player=False, role_id=enemy_tmpl.role_id, action="idle",
            idle_folder=enemy_motion_folder,
        )

        # Reset all battle state (mirrors _enter_battle).
        self._player_hp_display = float(self._player_fighter.hp)
        self._player_mp_display = float(self._player_fighter.mp)
        self._enemy_hp_display = float(self._enemy_fighter.hp)
        self._enemy_mp_display = float(self._enemy_fighter.mp)
        self._active_attack_seq = None
        self._player_hit_timer = 0.0
        self._enemy_hit_timer = 0.0
        self._enemy_shake_timer = 0.0
        self._combat_replay = None
        self._replay_event_idx = 0
        self._replay_timer = 0.0
        self._endgame_active = False
        self._endgame_timer = 0.0
        self._combat_log_lines.clear()
        self._combat_log_expanded = False
        self._combat_log_height_display = float(LOG_BAR_H)
        self._speed_buttons_y_offset = 0.0
        self._countdown_active = True
        self._countdown_timer = 0.0
        self._countdown_phase_idx = 0
        self._char_sheet_open = False
        self._char_sheet_closing = False
        self._char_sheet_anim_t = 0.0
        self._char_sheet2_open = False
        self._char_sheet2_closing = False
        self._char_sheet2_anim_t = 0.0
        self._battle_speed = float(BATTLE_SPEED_DEFAULT)
        self._particles.clear()
        self._damage_numbers.clear()
        self._player_ice.deactivate()
        self._enemy_ice.deactivate()
        self._player_shield.deactivate()
        self._enemy_shield.deactivate()
        self._player_cloud.deactivate()
        self._enemy_cloud.deactivate()
        self._player_poison.deactivate()
        self._enemy_poison.deactivate()
        self._cast_effect.deactivate()
        self._projectile_effect.deactivate()

        # Stage 89 — set Tower battle context.
        self._battle_mode = BattleMode.TOWER
        self._tower_active_floor = floor
        self._tower_active_is_boss = tower_floor.is_boss
        self._tower_active_modifiers = tower_floor.modifiers
        self._tower_reward_applied = False
        # Close the Tower modal so it doesn't show during battle.
        self._tower_modal_open = False
        self._tower_shop_open = False

        # Stage 160 — снапшот фона локации для боя.
        self._capture_battle_bg_snapshot()

        self.state = GameState.BATTLE
        # Stage 200 — подложки имён появляются с fade при каждом входе в бой.
        self._hud_plate_fade = 0.0

    @staticmethod
    def _tower_enemy_motion_folder(enemy_id: str) -> str:
        """Map a Tower floor's enemy_id to a motion folder.

        Tower floors reuse existing enemies (samurai_*, flower_1). The motion
        folder is derived from the enemy's role_id, not the enemy_id, so we
        map by name prefix here.
        """
        # flower_1 → flower/idle
        if enemy_id.startswith("flower"):
            return "flower/idle"
        # samurai_1, samurai_4, samurai_7, samurai_10 → samurai/idle (role 10001)
        # samurai_2, samurai_5, samurai_8, samurai_11 → blue_swordsman/idle (10002)
        # samurai_3, samurai_6, samurai_9, samurai_12 → black_samurai/idle (10004)
        # Use the legacy MOB_TO_MOTION mapping by trying common keys.
        # Map by index: 1,4,7,10 → samurai; 2,5,8,11 → blue; 3,6,9,12 → black.
        try:
            suffix = int(enemy_id.split("_")[-1])
        except (ValueError, IndexError):
            return "samurai/idle"
        idx = ((suffix - 1) % 3) + 1  # 1, 2, or 3
        if idx == 2:
            return "blue_swordsman/idle"
        if idx == 3:
            return "black_samurai/idle"
        return "samurai/idle"

    def _finish_tower_battle(self) -> None:
        """Apply Tower battle rewards after victory/defeat.

        Per §13: called from the endgame flow when ``_battle_mode == BattleMode.TOWER``.
        - On defeat: no reward, return to Tower modal.
        - On victory: complete the floor, award first-clear or repeat reward,
          add shards/materials/gold/xp, save, show result modal.
        Guards against double-application via ``_tower_reward_applied``.
        """
        if self._tower_reward_applied:
            return
        self._tower_reward_applied = True
        from pockie_rpg.data.tower_db import get_tower_reward

        floor = self._tower_active_floor
        if floor is None:
            return
        is_victory = (self._endgame_text == "Победа")

        if not is_victory:
            # Defeat — no reward, just show the result.
            self._tower_result = {
                "victory": False,
                "floor": floor,
                "is_boss": self._tower_active_is_boss,
                "gold": 0,
                "shards": 0,
                "xp": 0,
                "items": [],
                "materials": {},
                "first_clear": False,
            }
            return

        # Victory — complete the floor (marks first-clear claim).
        is_first_clear = self.player.complete_tower_floor(floor)
        reward = get_tower_reward(floor, first_clear=is_first_clear)
        # Stage 95 — track daily quest: tower floors.
        self._track_daily_quest("tower_floors")

        # Apply rewards.
        old_level = self.player.level
        self.player.gain_gold(reward.gold)
        self.player.add_tower_shards(reward.tower_shards)
        # Stage 94 — XP is accumulated (not applied directly). Player claims it
        # via the "Получить" button in the Tower modal.
        if reward.xp > 0:
            self.player.tower_pending_xp += reward.xp
        # Items — add to inventory (skip if inv full — convert to gold).
        items_added = []
        for item_id in reward.items:
            if self.player.inv_add(item_id):
                items_added.append(item_id)
            else:
                # Inventory full — convert item to gold (sell price).
                from pockie_rpg.data.item_db import get_sell_price
                sell_price = get_sell_price(item_id) if hasattr(get_sell_price, "__call__") else 50
                self.player.gain_gold(sell_price)
                items_added.append(f"{item_id} → {sell_price} зол.")
        # Materials.
        materials_added = {}
        for mat_id, amt in reward.materials:
            self.player.add_tower_material(mat_id, amt)
            materials_added[mat_id] = materials_added.get(mat_id, 0) + amt
        # Title reward.
        if reward.title_id is not None:
            # Just store the title id — the titles system can display it later.
            pass

        # Save state.
        self.save_mgr.mark_dirty()

        self._tower_result = {
            "victory": True,
            "floor": floor,
            "is_boss": self._tower_active_is_boss,
            "gold": reward.gold,
            "shards": reward.tower_shards,
            "xp": reward.xp,
            "items": items_added,
            "materials": materials_added,
            "first_clear": is_first_clear,
            "leveled_up": self.player.level > old_level,
            "new_level": self.player.level,
        }

    def _close_tower_result(self) -> None:
        """Close the Tower result modal and return to the Tower floor list."""
        self._tower_result = None
        # Reopen the Tower modal to show updated progress.
        self._tower_modal_open = True
        self._tower_selected_floor = self.player.tower_current_floor
        self._tower_scroll_offset = max(0, self._tower_selected_floor - 5)

    # ------------------------------------------------------------------
    # Stage 133 — SLOT MACHINE «3 лица → бой» (Локация 1)
    # ------------------------------------------------------------------

    def _open_slot_machine_modal(self) -> None:
        """Open the slot machine modal (map icon, Location 1 only).

        Stage 167 — до первой прокрутки барабаны показывают аватарки врагов
        из пула (вместо «?»), случайно перемешанные при каждом открытии.
        """
        self._slot_machine_modal_open = True
        pool = [m for m in SLOT_MACHINE_POOL if m in ENEMY_MOBS]
        self._slot_idle_faces = (
            [random.choice(pool) for _ in range(SLOT_MACHINE_FACES)]
            if pool else []
        )

    def _close_slot_machine_modal(self) -> None:
        self._slot_machine_modal_open = False
        if self._slot_spin_active:
            # Roll never finished animating — cancel, nothing to record.
            self._slot_spin_active = False
            self._slot_rolled = False
            self._slot_faces = []
            return
        # Stage 163 — история прокруток удалена: незыгранная прокрутка
        # просто сбрасывается, ничего не записывается и не сохраняется.
        self._slot_rolled = False
        self._slot_faces = []

    def _close_slot_result(self) -> None:
        self._slot_result = None

    def _slot_cooldown_remaining(self) -> float:
        """Seconds left until the next roll is allowed (0 = ready)."""
        if self.player.slot_next_roll_ts is None:
            return 0.0
        return max(0.0, self.player.slot_next_roll_ts - time.time())

    def _slot_machine_roll(self) -> None:
        """Roll 3 random faces from the Location 1 mob pool.

        Cooldown starts immediately (consumed even if the player never
        starts the fights). The reels animate for ~2s via _update_slot_spin;
        «В бой!» unlocks when the animation finishes (_slot_rolled = True).
        """
        if self._slot_rolled or self._slot_spin_active:
            return
        if self._slot_cooldown_remaining() > 0.0:
            return
        pool = [m for m in SLOT_MACHINE_POOL if m in ENEMY_MOBS]
        if not pool:
            return
        self._slot_faces = [random.choice(pool) for _ in range(SLOT_MACHINE_FACES)]
        self._slot_spin_result = list(self._slot_faces)
        self._slot_spin_shown = [random.choice(pool) for _ in range(SLOT_MACHINE_FACES)]
        self._slot_spin_flip_accum = [0.0] * SLOT_MACHINE_FACES
        self._slot_spin_timer = 0.0
        self._slot_spin_active = True
        self.player.slot_next_roll_ts = time.time() + SLOT_MACHINE_COOLDOWN_SEC
        self.save_mgr.mark_dirty()

    def _update_slot_spin(self, dt: float) -> None:
        """Stage 134 — spin animation: each reel flips random faces every
        SPIN_TICK until its stop moment (SPIN_SEC + i * STOP_STAGGER); during
        the last SPIN_SLOWDOWN_SEC before stopping the tick doubles (braking
        effect). When all reels stopped → _slot_rolled = True."""
        pool = [m for m in SLOT_MACHINE_POOL if m in ENEMY_MOBS] or list(SLOT_MACHINE_POOL)
        self._slot_spin_timer += dt
        all_stopped = True
        for i in range(SLOT_MACHINE_FACES):
            stop_at = SLOT_MACHINE_SPIN_SEC + i * SLOT_MACHINE_SPIN_STOP_STAGGER
            if self._slot_spin_timer >= stop_at:
                self._slot_spin_shown[i] = self._slot_spin_result[i]
                continue
            all_stopped = False
            tick = SLOT_MACHINE_SPIN_TICK
            if stop_at - self._slot_spin_timer <= SLOT_MACHINE_SPIN_SLOWDOWN_SEC:
                tick *= 2.0
            self._slot_spin_flip_accum[i] += dt
            while self._slot_spin_flip_accum[i] >= tick:
                self._slot_spin_flip_accum[i] -= tick
                self._slot_spin_shown[i] = random.choice(pool)
        if all_stopped:
            self._slot_spin_active = False
            self._slot_rolled = True

    def _start_slot_gauntlet(self) -> None:
        """Leave the modal and start the 3-round battle chain (1v1 each)."""
        if not self._slot_rolled or not self._slot_faces:
            return
        if any(m not in ENEMY_MOBS for m in self._slot_faces):
            self._slot_rolled = False
            self._slot_faces = []
            return
        self._gauntlet_active = True
        self._gauntlet_enemies = list(self._slot_faces)
        self._gauntlet_round = 0
        self._gauntlet_hp = float(self.player.current_hp)
        self._gauntlet_mp = float(self.player.current_mp)
        self._gauntlet_defeated = 0
        self._gauntlet_gold = 0
        self._gauntlet_xp = 0
        self._slot_rolled = False
        self._slot_machine_modal_open = False
        self._enter_gauntlet_battle()

    def _enter_gauntlet_battle(self) -> None:
        """Enter the current gauntlet round (mirrors _enter_battle).

        The player fighter carries HP/MP over from the previous round with
        NO regen and NO restore between rounds.
        """
        if not self._gauntlet_active:
            return
        if self._gauntlet_round >= len(self._gauntlet_enemies):
            self._gauntlet_active = False
            return
        enemy = ENEMY_MOBS.get(self._gauntlet_enemies[self._gauntlet_round])
        suit = STARTER_SUITS.get(self.player.suit_id)
        player_role = ROLES.get(self.player.role_id)
        enemy_role = ROLES.get(enemy.role_id) if enemy is not None else None
        if suit is None or player_role is None or enemy is None or enemy_role is None:
            self._gauntlet_active = False
            return

        self._battle_mode = BattleMode.SLOT_GAUNTLET
        self._tower_active_floor = None
        self._tower_active_is_boss = False
        self._tower_active_modifiers = ()
        self._tower_reward_applied = False
        self.target_mob_id = enemy.mob_id

        self._player_fighter = Fighter.from_player_state(self.player, player_role)
        self._player_fighter.hp = max(1, int(self._gauntlet_hp))
        self._player_fighter.mp = max(0, int(self._gauntlet_mp))
        self._enemy_fighter = Fighter.from_role(
            enemy_role,
            is_player=False,
            level=enemy.level,
            hp_mul=enemy.hp_mul,
            atk_mul=enemy.atk_mul,
        )

        player_flip = self.asset_manager.needs_flip_for_player(suit.motion_folder)
        self._player_animator = IdleAnimator(
            folder=suit.motion_folder,
            flip=player_flip,
            phase=0.0,
            is_player=True,
            action="idle",
            idle_folder=suit.motion_folder,
        )
        enemy_motion_folder = MOB_TO_MOTION.get(enemy.mob_id, "samurai_idle")
        enemy_flip = self.asset_manager.needs_flip_for_enemy(
            enemy_motion_folder, mob_id=enemy.mob_id
        )
        self._enemy_animator = IdleAnimator(
            folder=enemy_motion_folder,
            flip=enemy_flip,
            phase=math.pi,
            is_player=False,
            role_id=enemy.role_id,
            action="idle",
            idle_folder=enemy_motion_folder,
        )

        self._player_hp_display = float(self._player_fighter.hp)
        self._player_mp_display = float(self._player_fighter.mp)
        self._enemy_hp_display = float(self._enemy_fighter.hp)
        self._enemy_mp_display = float(self._enemy_fighter.mp)
        self._reset_battle_common_state()
        # Stage 161 — фон боя = экран локации с UI (оффскрин-рендер).
        self._capture_battle_bg_snapshot()
        self.state = GameState.BATTLE
        # Stage 200 — подложки имён появляются с fade при каждом входе в бой.
        self._hud_plate_fade = 0.0

    def _snapshot_map_scene(self) -> pygame.Surface | None:
        """Stage 161 — оффскрин-рендер ТЕКУЩЕГО экрана локации (с UI).

        Рисует базовый экран (MAP или арена) + нижний бар в поверхность
        1280×720 — ровно то, что игрок видит на экране в момент вызова:
        фон локации, спрайт, карточки мобов, ВЕРХНЯЯ ПАНЕЛЬ и НИЖНИЙ БАР.
        Используется для фона боя (блюр вокруг боевого окна) и фона
        диалога стража Лас Ночеса (блюр вместо чёрного затемнения).

        ClickRect'ы временной отрисовки собираются в отдельный список и
        выбрасываются; `_render_scale` принудительно 1.0 (дизайн-пространство).
        Снапшоты ФРЕЙМБУФЕРА запрещены (RULES §Hi-DPI) — поэтому это ПОЛНОЦЕННЫЙ
        повторный рендер сцены, а не копия `_fullscreen_game` (тот буфер на
        нативном 2К-пути не обновляется).
        """
        saved_screen = self.screen
        saved_rects = self._click_rects
        saved_scale = getattr(self, "_render_scale", 1.0)
        snap = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        try:
            self.screen = snap
            self._click_rects = []
            self._render_scale = 1.0
            if self._arena_active:
                self._render_arena()
            else:
                self._render_map()
                self._render_bottom_bar()
        except Exception:
            return None
        finally:
            self.screen = saved_screen
            self._click_rects = saved_rects
            self._render_scale = saved_scale
        return snap

    def _capture_battle_bg_snapshot(self) -> None:
        """Stage 161 — фон боя = ЭКРАН локации (с UI), размытый в present.

        Stage 140 снимал копию `_fullscreen_game` при входе в бой — на
        нативном 2К-пути (Stage 153) буфер не обновлялся, фон был ЧЁРНЫМ.
        Stage 160 брал ассет фона локации — но по запросу пользователя фон
        боя должен быть «той локацией, откуда зашёл в бой, со всем UI».
        Теперь снапшот — оффскрин-рендер всей сцены MAP (карточки мобов,
        верхняя панель, нижний бар) через `_snapshot_map_scene`; при провале
        — прежний фолбэк на ассет фона.
        """
        from pockie_rpg.config import BATTLE_BACKGROUND, LOCATIONS_DB

        snap = self._snapshot_map_scene()
        if snap is not None:
            self._battle_bg_snapshot = snap
            return
        if self._battle_mode == BattleMode.TOWER and self._tower_active_floor is not None:
            from pockie_rpg.config import get_tower_battle_bg
            bg_name = get_tower_battle_bg(self._tower_active_floor)
        else:
            loc_info = LOCATIONS_DB.get(int(self._map_location))
            bg_name = loc_info["bg"] if loc_info else BATTLE_BACKGROUND
        bg = self.asset_manager.get_background(bg_name)
        if bg.get_size() == (SCREEN_WIDTH, SCREEN_HEIGHT):
            self._battle_bg_snapshot = bg.copy()
        else:
            self._battle_bg_snapshot = pygame.transform.smoothscale(
                bg, (SCREEN_WIDTH, SCREEN_HEIGHT)
            )

    # Stage 165 — _render_blur_backdrop / _invalidate_blur_backdrop УДАЛЕНЫ:
    # блюр-подложки модалок вызывали «резкую вспышку» при открытии окна
    # (вся сцена подменялась размытым снапшотом). Теперь окна рисуются
    # поверх неизменённой живой сцены — как «Карта мира» и магазин.

    def _reset_battle_common_state(self) -> None:
        """Stage 133 — battle-entry resets shared by _enter_battle flows."""
        self._active_attack_seq = None
        self._player_hit_timer = 0.0
        self._enemy_hit_timer = 0.0
        self._enemy_shake_timer = 0.0
        self._combat_replay = None
        self._replay_event_idx = 0
        self._replay_timer = 0.0
        self._endgame_active = False
        self._endgame_timer = 0.0
        self._combat_log_lines.clear()
        self._combat_log_expanded = False
        self._combat_log_height_display = float(LOG_BAR_H)
        self._speed_buttons_y_offset = 0.0
        self._countdown_active = True
        self._countdown_timer = 0.0
        self._countdown_phase_idx = 0
        self._char_sheet_open = False
        self._char_sheet_closing = False
        self._char_sheet_anim_t = 0.0
        self._char_sheet_origin = "left"
        self._char_sheet2_open = False
        self._char_sheet2_closing = False
        self._char_sheet2_anim_t = 0.0
        self._char_sheet2_origin = "right"
        self._battle_speed = float(BATTLE_SPEED_DEFAULT)
        self._particles.clear()
        self._damage_numbers.clear()
        self._player_ice.deactivate()
        self._enemy_ice.deactivate()
        self._player_shield.deactivate()
        self._enemy_shield.deactivate()
        self._player_cloud.deactivate()
        self._enemy_cloud.deactivate()
        self._player_poison.deactivate()
        self._enemy_poison.deactivate()
        self._cast_effect.deactivate()
        self._projectile_effect.deactivate()

    def _finish_gauntlet_round(self) -> None:
        """End-of-round dispatch for the slot machine gauntlet.

        Victory + rounds remaining → chain into the next round (HP/MP carry
        over, no regen). Otherwise → apply gold+xp rewards, teardown via
        _exit_battle, show the result modal on the MAP.
        """
        if not self._gauntlet_active:
            return
        winner = self._combat_replay.winner if self._combat_replay is not None else 1
        enemy = ENEMY_MOBS.get(self._gauntlet_enemies[self._gauntlet_round])
        if enemy is None:
            self._abort_gauntlet()
            return

        round_won = (winner == 0)
        if round_won:
            self._gauntlet_defeated += 1
            self._gauntlet_gold += enemy.gold_reward
            self._gauntlet_xp += enemy.xp_reward
            self.player.record_defeat(enemy.mob_id)

        has_next = round_won and (self._gauntlet_round + 1) < len(self._gauntlet_enemies)
        if has_next:
            self._gauntlet_round += 1
            self._gauntlet_hp = float(max(1, self._player_fighter.hp))
            self._gauntlet_mp = float(max(0, self._player_fighter.mp))
            self._combat_replay = None
            self._enter_gauntlet_battle()
            return

        # Stage 170 — награды/синк HP/MP/result — общий метод с ESC-выходом.
        self._settle_gauntlet_rewards()
        self._abort_gauntlet()
        self.save_mgr.mark_dirty()
        self._exit_battle()

    def _settle_gauntlet_rewards(self) -> None:
        """Stage 170 — общая финализация наград гантлета (нормальное
        завершение в _finish_gauntlet_round и ESC-выход через
        _finalize_gauntlet_on_exit).

        Начисляет накопленные _gauntlet_gold/_gauntlet_xp (perfect-бонус —
        только за полный прогон 3/3), синхронизирует HP/MP текущего бойца
        обратно в PlayerState (кламп 1 HP / 0 MP) и заполняет _slot_result.
        Кулдаун слот-машины НЕ трогает (ролл уже потрачен).
        """
        level_before = self.player.level
        perfect = (
            self._gauntlet_defeated == len(self._gauntlet_enemies) == SLOT_MACHINE_FACES
        )
        gold_total = self._gauntlet_gold
        if perfect and gold_total > 0:
            # Stage 134 — perfect 3/3 bonus; ceil rounds in the player's favor.
            gold_total = int(math.ceil(gold_total * SLOT_MACHINE_PERFECT_GOLD_MULT))
        if gold_total > 0:
            self.player.gain_gold(gold_total)
        if self._gauntlet_xp > 0:
            self.player.gain_xp(self._gauntlet_xp)
        # Stage 134 — carry remaining fighter HP/MP back to the player
        # (death outside battle doesn't exist → clamp at 1 HP / 0 MP).
        if self._player_fighter is not None:
            self.player.current_hp = max(1, int(self._player_fighter.hp))
            self.player.current_mp = max(0, int(self._player_fighter.mp))
        # Stage 163 — запись в player.slot_history удалена (история убрана).
        self._slot_result = {
            "faces": list(self._gauntlet_enemies),
            "defeated": self._gauntlet_defeated,
            "total": len(self._gauntlet_enemies),
            "gold": gold_total,
            "xp": self._gauntlet_xp,
            "perfect": perfect,
            "leveled_up": self.player.level > level_before,
            "new_level": self.player.level,
        }

    def _finalize_gauntlet_on_exit(self) -> None:
        """Stage 170 — корректный выход из боя посреди гантлета (ESC).

        Раньше _exit_battle сбрасывал _battle_mode, но оставлял
        _gauntlet_active=True висеть: золото/опыт за победы в предыдущих
        раундах «сгорали», а result-модалка не показывалась. Теперь при
        выходе в режиме SLOT_GAUNTLET незавершённая цепочка финализируется:
        победы ДО текущего (незавершённого) раунда начисляются, HP/MP
        синхронизируются, очередь врагов очищается, result-модалка
        показывается на MAP. Для чужих режимов/завершённого гантлета — no-op.
        """
        if self._battle_mode != BattleMode.SLOT_GAUNTLET or not self._gauntlet_active:
            return
        self._settle_gauntlet_rewards()
        self._abort_gauntlet()
        self.save_mgr.mark_dirty()

    def _abort_gauntlet(self) -> None:
        """Clear gauntlet chain state (after finish or fatal error)."""
        self._gauntlet_active = False
        self._gauntlet_enemies = []
        self._gauntlet_round = 0
        self._gauntlet_hp = 0.0
        self._gauntlet_mp = 0.0
        self._gauntlet_defeated = 0
        self._gauntlet_gold = 0
        self._gauntlet_xp = 0

    def _tower_claim_xp(self) -> None:
        """Stage 94 — claim accumulated Tower XP and exit."""
        if self.player.tower_pending_xp > 0:
            self.player.gain_xp(self.player.tower_pending_xp)
            self.player.tower_pending_xp = 0
            self.save_mgr.mark_dirty()
        # Close the Tower modal and return to Las Noches.
        self._tower_modal_open = False
        from pockie_rpg.config import MapLocation
        self._map_location = MapLocation.LAS_NOCHES

    def _tower_continue(self) -> None:
        """Stage 94 — continue to the next floor (enter battle)."""
        floor = self.player.tower_current_floor
        if self.player.can_enter_tower(floor):
            self._enter_tower_battle(floor)

    def _buy_tower_material(self, material_id: str, cost: int) -> None:
        """Buy a Tower material with shards (Stage 89 — simple purchase)."""
        if not self.player.spend_tower_shards(cost):
            return
        self.player.add_tower_material(material_id, 1)
        self.save_mgr.mark_dirty()

    def _buy_tower_consumable(self, item_key: str, cost: int) -> None:
        """Stage 89 — disabled placeholder. Does NOT change state.

        Per §8: disabled items must not change player state. The UI shows
        them with a "Скоро" tooltip but the click handler is a no-op.
        """
        return

    def _set_shop_tab(self, tab: int) -> None:
        """Stage 59 — switch shop tab (0=снаряжение, 1=самоцветы)."""
        self._shop_active_tab = tab
        # Stage 67 — reset equipment page when switching tabs.
        self._shop_equipment_page = 0

    def _set_shop_eq_subtab(self, subtab: int) -> None:
        """Stage 69 — switch equipment sub-tab (0=всё, 1=оружие, 2=броня)."""
        self._shop_eq_subtab = subtab
        self._shop_equipment_page = 0  # reset to first page

    def _open_titles_modal(self) -> None:
        """Stage 70 — open the Titles (Звания) modal."""
        self._titles_modal_open = True

    def _open_settings_modal(self) -> None:
        """Stage 94 — settings placeholder. Opens the skills modal for now
        (settings not yet implemented as a separate modal)."""
        # Stage 94 — placeholder: for now, settings opens the titles modal
        # (which shows player stats + title bonuses). A dedicated settings
        # modal can be added later.
        self._titles_modal_open = True

    def _exit_game_from_bar(self) -> None:
        """Stage 94 — exit button in the bottom bar. Saves + quits."""
        import pygame
        self.save_mgr.flush()
        pygame.event.post(pygame.event.Event(pygame.QUIT))

    # ------------------------------------------------------------------
    # Stage 95 — Daily Quests
    # ------------------------------------------------------------------

    def _open_daily_quest_modal(self) -> None:
        """Stage 95 — open the Daily Quest tracker modal."""
        self.player.check_daily_quest_reset()
        self._daily_quest_modal_open = True

    def _close_daily_quest_modal(self) -> None:
        """Stage 95 — close the Daily Quest modal."""
        self._daily_quest_modal_open = False

    def _claim_daily_quest(self, quest_id: str) -> None:
        """Stage 95 — claim a completed daily quest reward."""
        if self.player.claim_daily_quest(quest_id):
            self.save_mgr.mark_dirty()

    def _track_daily_quest(self, quest_id: str) -> None:
        """Stage 95 — increment daily quest progress (called from battle handlers)."""
        self.player.add_daily_quest_progress(quest_id)

    def _close_titles_modal(self) -> None:
        """Stage 70 — close the Titles modal."""
        self._titles_modal_open = False

    def _activate_title(self, title_id: str) -> None:
        """Stage 70 — activate a title (sets player.active_title + recalc stats)."""
        from pockie_rpg.data.titles_db import get_title
        title = get_title(title_id)
        if title is None:
            return
        # Toggle: if already active, deactivate.
        if self.player.active_title == title_id:
            self.player.active_title = None
        else:
            self.player.active_title = title_id
        self.player.recalc_stats()
        # Refresh cached HP/MP.
        self.player._cached_hp = self.player.stats.max_hp
        self.player._cached_mp = self.player.stats.max_mp
        self._save_player()

    # ===================================================================
    # Stage 71 — WORLD BOSS
    # ===================================================================

    def _spawn_world_boss(self) -> None:
        """Stage 72 — spawn the World Boss on a random location 1-4.

        Boss base stats (level 1): 50000 HP, 1000-1500 atk, 0% crit/dodge,
        1.0 speed, 0% pierce/tough. When killed, respawns with level+1 and
        ALL stats ×2.
        """
        import random

        from pockie_rpg.config import (
            WORLD_BOSS_BASE_MAX_ATK,
            WORLD_BOSS_BASE_MIN_ATK,
            WORLD_BOSS_MAX_HP,
        )
        if self.player.world_boss_hp is None:
            loc = random.randint(1, 4)
            self.player.world_boss_hp = {
                "level": 1,
                "max_hp": WORLD_BOSS_MAX_HP,
                "current_hp": WORLD_BOSS_MAX_HP,
                "location": loc,
                "min_atk": WORLD_BOSS_BASE_MIN_ATK,
                "max_atk": WORLD_BOSS_BASE_MAX_ATK,
                "killed_count": 0,
            }
            self.player.world_boss_attempts = 3
            self._save_player()

    def _respawn_world_boss(self) -> None:
        """Stage 72 — respawn boss with level+1 and stats ×2."""
        import random
        if self.player.world_boss_hp is None:
            self._spawn_world_boss()
            return
        boss = self.player.world_boss_hp
        new_level = boss.get("level", 1) + 1
        # Stats ×2 per level.
        old_max_hp = boss.get("max_hp", 50000)
        old_min_atk = boss.get("min_atk", 1000)
        old_max_atk = boss.get("max_atk", 1500)
        boss["level"] = new_level
        boss["max_hp"] = old_max_hp * 2
        boss["current_hp"] = boss["max_hp"]
        boss["min_atk"] = old_min_atk * 2
        boss["max_atk"] = old_max_atk * 2
        boss["killed_count"] = boss.get("killed_count", 0) + 1
        # New random location.
        boss["location"] = random.randint(1, 4)
        # Reset attempts.
        self.player.world_boss_attempts = 3
        self._save_player()

    def _enter_world_boss_fight(self) -> None:
        """Stage 77 — instant battle with the World Boss (no animation).

        - 3 attempts max (no auto-reset).
        - If attempts=0: show error modal "Попытки закончились".
        - If attempts>0: run fight, show results modal with rank + reward.
        - SSS rank: 30% chance to drop random weapon/armor L25.
        - Timer: 30 min per attempt regen (displayed near boss sprite).
        """
        import time

        from pockie_rpg.combat.fight import FightSystem
        from pockie_rpg.combat.fighter import Fighter
        from pockie_rpg.config import (
            WORLD_BOSS_BASE_DODGE,
            WORLD_BOSS_BASE_SPEED,
            WORLD_BOSS_BASE_TOUGH,
            WORLD_BOSS_REWARDS,
        )
        from pockie_rpg.game.state import ROLES
        # Check attempts — NO auto-reset (Stage 77).
        if self.player.world_boss_attempts <= 0:
            # Stage 89 — mark battle mode (so endgame knows it's boss).
            self._battle_mode = BattleMode.WORLD_BOSS
            # Stage 79 — skip "text" phase, go DIRECTLY to "rewards" phase
            # with the error message (no "Награды" title, no XP/gold lines).
            self._world_boss_error = True
            self._endgame_text = "Попытки закончились"
            self._endgame_active = True
            self._endgame_phase = "rewards"  # Stage 79 — skip text phase.
            self._endgame_text_timer = 0.0
            self._endgame_xp_gained = 0
            self._endgame_gold_gained = 0
            self._endgame_leveled_up = False
            self._endgame_old_level = self.player.level
            self._endgame_new_level = self.player.level
            self._combat_replay = None
            self._world_boss_active = True
            self._world_boss_damage_dealt = 0
            self._world_boss_rank = ""
            self._world_boss_killed = False
            self._world_boss_item_drop = None
            return
        boss = self.player.world_boss_hp
        if boss is None or boss["current_hp"] <= 0:
            return
        # Stage 89 — mark battle mode (so endgame knows it's boss).
        self._battle_mode = BattleMode.WORLD_BOSS
        self._tower_active_floor = None
        self._tower_reward_applied = False
        # Decrement attempts + start timer if needed.
        self.player.world_boss_attempts -= 1
        if self.player.world_boss_attempts < 3 and self.player.world_boss_next_attempt_ts is None:
            self.player.world_boss_next_attempt_ts = time.time() + 1800  # 30 min
        self._world_boss_damage_dealt = 0
        # Stage 95 — track daily quest: attack World Boss.
        self._track_daily_quest("world_boss")
        # Create fighters.
        player_role = ROLES.get(self.player.role_id)
        enemy_role = ROLES.get(10001)
        if player_role is None or enemy_role is None:
            return
        player_fighter = Fighter.from_player_state(self.player, player_role)
        boss_max_hp = boss["current_hp"]
        enemy_fighter = Fighter.from_role(
            enemy_role, is_player=False, level=80,
            hp_mul=float(boss_max_hp) / enemy_role.max_hp, atk_mul=1.0,
        )
        enemy_fighter.max_hp = boss_max_hp
        enemy_fighter.hp = boss_max_hp
        enemy_fighter.min_atk = boss.get("min_atk", 1000)
        enemy_fighter.max_atk = boss.get("max_atk", 1500)
        enemy_fighter.dodge_chance = WORLD_BOSS_BASE_DODGE
        enemy_fighter.speed = WORLD_BOSS_BASE_SPEED
        enemy_fighter.tough_rating = WORLD_BOSS_BASE_TOUGH
        # Run fight instantly.
        system = FightSystem(player_fighter, enemy_fighter)
        replay = system.fight()
        damage_dealt = 0
        for fv in replay.values:
            if fv.role == 0 and fv.event.name in ("ATTACK", "POISON_DAMAGE", "CLOUD_STRIKE"):
                if fv.damage > 0:
                    damage_dealt += fv.damage
        self._world_boss_damage_dealt = damage_dealt
        boss["current_hp"] = max(0, boss["current_hp"] - damage_dealt)
        rank = self._get_world_boss_rank(damage_dealt)
        self._world_boss_rank = rank
        reward = WORLD_BOSS_REWARDS.get(rank, WORLD_BOSS_REWARDS["F"])
        gold_reward = reward["gold"]
        self.player.gain_gold(gold_reward)
        # Stage 77 — SSS rank: 30% chance to drop random weapon/armor L25.
        item_drop = None
        if rank == "SSS":
            import random
            if random.random() < 0.30:
                from pockie_rpg.data.item_db import EQUIPMENT_DB, get_equipment
                # Find all L25 items (weapon + armor).
                l25_items = [iid for iid, d in EQUIPMENT_DB.items()
                             if d.get("item_level", 1) == 25 and iid != "suit_ichigo"]
                if l25_items:
                    drop_id = random.choice(l25_items)
                    self.player.inv_add(drop_id)
                    drop_item = get_equipment(drop_id)
                    item_drop = drop_item.get("name", drop_id) if drop_item else drop_id
        self._world_boss_item_drop = item_drop
        boss_killed = boss["current_hp"] <= 0
        if boss_killed:
            self._respawn_world_boss()
        self._save_player()
        # Show results modal.
        self._world_boss_active = True
        self._world_boss_error = False
        self.target_mob_id = "world_boss"
        self._boss_flash_timer = 1.0
        self._endgame_text = "Бой с боссом"
        self._endgame_active = True
        self._endgame_phase = "text"
        self._endgame_text_timer = 0.0
        self._endgame_xp_gained = 0
        self._endgame_gold_gained = gold_reward
        self._endgame_leveled_up = False
        self._endgame_old_level = self.player.level
        self._endgame_new_level = self.player.level
        self._combat_replay = None
        self._world_boss_killed = boss_killed

    def _get_world_boss_rank(self, damage: int) -> str:
        """Stage 71 — calculate rank based on damage dealt."""
        from pockie_rpg.config import (
            WORLD_BOSS_RANK_A,
            WORLD_BOSS_RANK_B,
            WORLD_BOSS_RANK_S,
            WORLD_BOSS_RANK_SS,
            WORLD_BOSS_RANK_SSS,
        )
        if damage >= WORLD_BOSS_RANK_SSS:
            return "SSS"
        elif damage >= WORLD_BOSS_RANK_SS:
            return "SS"
        elif damage >= WORLD_BOSS_RANK_S:
            return "S"
        elif damage >= WORLD_BOSS_RANK_A:
            return "A"
        elif damage >= WORLD_BOSS_RANK_B:
            return "B"
        else:
            return "F"

    def _shop_equipment_prev_page(self) -> None:
        """Stage 67 — go to the previous equipment page in the shop."""
        if self._shop_equipment_page > 0:
            self._shop_equipment_page -= 1

    def _shop_equipment_next_page(self) -> None:
        """Stage 67 — go to the next equipment page in the shop."""
        from pockie_rpg.data.item_db import EQUIPMENT_DB, get_equipment
        all_items = [item_id for item_id in EQUIPMENT_DB.keys() if item_id != "suit_ichigo"]
        # Stage 69 — filter by sub-tab.
        if self._shop_eq_subtab == 1:  # оружие
            shop_items = [iid for iid in all_items if get_equipment(iid) and get_equipment(iid).get("slot") == "weapon"]
        elif self._shop_eq_subtab == 2:  # броня
            shop_items = [iid for iid in all_items if get_equipment(iid) and get_equipment(iid).get("slot") != "weapon"]
        else:
            shop_items = all_items
        items_per_page = 12  # 4 cols × 3 rows
        max_page = max(0, (len(shop_items) - 1) // items_per_page)
        if self._shop_equipment_page < max_page:
            self._shop_equipment_page += 1

    def _buy_item(self, item_id: str) -> None:
        """Stage 59/133 — buy an equipment item from the shop.

        Stage 133 — inventory capacity is checked BEFORE charging gold.
        inv_add() can silently fail on a full paged inventory, which used to
        eat the gold with no item. On a full inventory gold is NOT charged
        and a short toast is shown. No auto-sell here (unlike the battle
        flow) — the player decides what to sell.
        """
        from pockie_rpg.data.item_db import get_equipment
        item = get_equipment(item_id)
        if item is None:
            return
        price = item.get("sell_price", 50) * 5  # buy price = 5x sell price
        if self.player.gold < price:
            return
        if not self.player.inv_has_space(item_id):
            self._shop_feedback = "Инвентарь полон! Освободите место."
            self._shop_feedback_timer = 2.5
            return
        self.player.gold -= price
        self.player.inv_add(item_id)
        self._save_player()

    def _buy_gem(self, gem_type: str) -> None:
        """Stage 59 — buy a gem L1 from the shop."""
        price = 100  # flat price for L1 gem
        if self.player.gold < price:
            return
        self.player.gold -= price
        self.player.add_gem(gem_type, 1)
        self._save_player()

    def _enter_arena(self) -> None:
        """Stage 59 — enter the Arena location."""
        self._arena_active = True

    def _exit_arena(self) -> None:
        """Stage 59 — exit the Arena back to city."""
        self._arena_active = False

    def _close_forge_modal(self) -> None:
        """Stage 47 — close the Forge modal."""
        self._forge_modal_open = False

    def _upgrade_gear_item(self, slot: str) -> None:
        """Stage 47 — upgrade the enchant level of the item in `slot`."""
        self.player.upgrade_gear(slot)
        self.player.current_hp = min(self.player.current_hp or self.player.stats.max_hp,
                                     self.player.stats.max_hp)
        self.player.current_mp = min(self.player.current_mp or self.player.stats.max_mp,
                                     self.player.stats.max_mp)
        self._save_player()

    # ------------------------------------------------------------------
    # Stage 51 — Forge tab + gem handlers
    # ------------------------------------------------------------------

    def _set_forge_tab(self, tab: int) -> None:
        """Switch the forge modal to the given tab (0=Заточка, 1=Камни, 2=Синтез)."""
        self._forge_active_tab = tab
        # Reset transient selection state on tab switch.
        self._forge_selected_gem = None
        self._forge_synthesis_a = None
        self._forge_synthesis_b = None

    def _forge_select_gear_slot(self, slot: str) -> None:
        """Select a gear slot in the gems tab (for socketing)."""
        self._forge_selected_slot = slot
        self._forge_selected_gem = None

    def _forge_select_gem(self, gem_id: str) -> None:
        """Select a gem instance in the gems tab (for upgrade or socketing)."""
        # If in synthesis tab, place into the first empty synthesis slot.
        if self._forge_active_tab == 2:
            if self._forge_synthesis_a is None:
                self._forge_synthesis_a = gem_id
            elif self._forge_synthesis_b is None and gem_id != self._forge_synthesis_a:
                self._forge_synthesis_b = gem_id
            return
        self._forge_selected_gem = gem_id

    def _forge_socket_selected_gem(self, slot_index: int) -> None:
        """Socket the currently selected gem into slot_index of the active gear slot."""
        if self._forge_selected_gem is None:
            return
        self.player.socket_gem(self._forge_selected_slot, slot_index, self._forge_selected_gem)
        self._forge_selected_gem = None
        self._save_player()

    def _forge_unsocket_gem(self, slot: str, slot_index: int) -> None:
        """Remove a gem from a gear slot back to inventory."""
        self.player.unsocket_gem(slot, slot_index)
        self._save_player()

    def _forge_upgrade_gem(self, gem_id: str) -> None:
        """Upgrade a gem's level by 1 (with success chance + gold cost)."""
        self.player.upgrade_gem(gem_id)
        self._save_player()

    def _forge_synthesis_clear_a(self) -> None:
        """Clear synthesis slot A."""
        self._forge_synthesis_a = None

    def _forge_synthesis_clear_b(self) -> None:
        """Clear synthesis slot B."""
        self._forge_synthesis_b = None

    def _forge_do_synthesis(self) -> None:
        """Execute synthesis: combine gems A + B into a result gem."""
        if self._forge_synthesis_a is None or self._forge_synthesis_b is None:
            return
        self.player.synthesize_gems(self._forge_synthesis_a, self._forge_synthesis_b)
        self._forge_synthesis_a = None
        self._forge_synthesis_b = None
        self._save_player()

    def _forge_debug_add_gem(self, gem_type: str) -> None:
        """Debug helper: add a gem to inventory for testing (no cost)."""
        self.player.add_gem(gem_type, 1)
        self._save_player()

    def _scroll_gems(self, direction: int) -> None:
        """Stage 55 — scroll gem grid in forge."""
        if not hasattr(self, "_forge_gem_scroll"):
            self._forge_gem_scroll = 0
        self._forge_gem_scroll += direction
        if self._forge_gem_scroll < 0:
            self._forge_gem_scroll = 0

    def _forge_spam_gems(self) -> None:
        """Stage 54 — spam button: adds 10 random gems (level 1-5) for testing."""
        import random as _r
        gem_types = ["gem_red", "gem_blue", "gem_green", "gem_yellow", "gem_orange"]
        for _ in range(10):
            gtype = _r.choice(gem_types)
            level = _r.randint(1, 5)
            self.player.add_gem(gtype, level)
        self._save_player()

    def _toggle_map_location(self) -> None:
        """Stage 45 — toggle between CITY and last combat location.
        Stage 91 — Las Noches also returns to City via this toggle."""
        from pockie_rpg.config import MapLocation
        if self._map_location == MapLocation.CITY:
            self._map_location = self._prev_location
        else:
            # From any non-CITY location (LOC1-4 or LAS_NOCHES), return to City.
            self._prev_location = self._map_location if self._map_location != MapLocation.LAS_NOCHES else self._prev_location
            self._map_location = MapLocation.CITY
            self._las_noches_dialog = None

    def _go_to_location(self, loc: int) -> None:
        """Stage 46 — switch to a specific location. Stage 135 — CITY allowed +
        level gate (страховка; UI карты уже не даёт кликнуть закрытую зону).
        Единственный источник правды — data/worldmap_db.LOCATION_MIN_UNLOCK,
        вычисленная из WORLD_ZONES[zone_id].unlock_level."""
        from pockie_rpg.config import LOCATIONS_DB, MapLocation
        from pockie_rpg.data.worldmap_db import LOCATION_MIN_UNLOCK
        if loc == MapLocation.CITY:
            self._map_location = MapLocation.CITY
            self._las_noches_dialog = None
            return
        loc_info = LOCATIONS_DB.get(loc)
        if loc_info is None:
            return
        if self.player.level < LOCATION_MIN_UNLOCK.get(loc, 0):
            return
        self._map_location = MapLocation(loc)
        self._prev_location = self._map_location

    def _save_combat_debug_log(self) -> None:
        """Stage 43 — save combat debug log to file."""
        if not self._combat_debug_lines:
            return
        import os
        log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                                "data", "combat_debug.txt")
        with open(log_path, "w", encoding="utf-8") as f:
            for line in self._combat_debug_lines:
                f.write(line + "\n")
        print(f"[DEBUG] {len(self._combat_debug_lines)} lines written to {log_path}")

    def _get_sell_price(self, item_id: str) -> int:
        """Stage 187 — цена продажи с поддержкой костюмов-инстансов.

        Бафы/шмот — item_db.get_sell_price; outfit_inst_N — база модели
        50 зол × (1 + плюс × 0.5) (синтез поднимает цену).
        """
        from pockie_rpg.data.item_db import get_sell_price
        if item_id.startswith("outfit_inst_"):
            plus = self.player._outfit_plus_of(item_id, self.player)
            return int(50 * (1 + 0.5 * plus))
        return get_sell_price(item_id)

    def _sell_item(self, item_id: str) -> None:
        """Stage 38 — sell an item: remove from inventory/gear + add gold + flash.

        Stage 187 — РУЧНАЯ ПРОДАЖА ЛЮБЫХ предметов через микро-меню:
        бафы (1 шт. из стака — inv_remove декрементирует), костюмы (базовые
        50 зол, инстансы — с плюсом), шмот. sell_price=0 (сюжетный weapon_
        novice) — продаёте не получается, честный лог.
        """
        price = self._get_sell_price(item_id)
        if price <= 0:
            self._add_log_line("Этот предмет нельзя продать")
            self._context_menu_item_id = None
            return
        # Check if it's in inventory.
        # Stage 64 — paged inventory: use inv_find/inv_remove instead of `in`/`.remove`.
        if self.player.inv_find(item_id) is not None:
            self.player.inv_remove(item_id)
            # Stage 187 — проданный костюм-инстанс удаляется из хранилища
            # (иначе оставался «висеть» до компакции сейва).
            if item_id.startswith("outfit_inst_"):
                self.player.outfit_instances.pop(item_id, None)
        else:
            # Check if it's equipped.
            for slot, iid in list(self.player.equipped_gear.items()):
                if iid == item_id:
                    self.player.equipped_gear[slot] = None
                    self.player.recalc_stats()
                    self.player._cached_hp = self.player.stats.max_hp
                    self.player._cached_mp = self.player.stats.max_mp
                    break
        self.player.gain_gold(price)
        # Stage 38 — gold flash effect.
        self._gold_flash_timer = 1.0
        self._gold_flash_amount = price
        self._context_menu_item_id = None
        self._context_menu_source_slot = None
        self._save_player()

    def _use_item(self, item_id: str) -> None:
        """Stage 45 — equip/unequip item (like right-click).

        Stage 66 — passes source_slot to equip_gear_item so the old item
        goes to the exact clicked slot (not the first empty slot).
        Stage 181 — баф сюда не доходит (своё меню), но defensive: активируем.
        """
        # Stage 181 — баф: активировать.
        bdef = self.player.get_item_definition(item_id)
        if bdef is not None and bdef.get("is_buff"):
            ok, msg = self.player.activate_buff(item_id)
            self._add_log_line(msg)
            self._context_menu_item_id = None
            self._context_menu_source_slot = None
            self._save_player()
            return
        # Check if it's in inventory → equip.
        # Stage 64 — paged inventory: use inv_find instead of `in`.
        if self.player.inv_find(item_id) is not None:
            # Stage 66 — use the source slot recorded when the context menu
            # was opened. This preserves slot position on swap.
            self.player.equip_gear_item(
                item_id,
                source_slot=self._context_menu_source_slot,
            )
        else:
            # Check if it's equipped → unequip (but not outfit).
            for slot, iid in list(self.player.equipped_gear.items()):
                if iid == item_id and slot != "outfit":
                    self._unequip_gear_item(slot)
                    break
        self._context_menu_item_id = None
        self._context_menu_source_slot = None
        self._save_player()

    def _close_context_menu(self) -> None:
        """Stage 66 — close the context menu and clear its source-slot tracking."""
        self._context_menu_item_id = None
        self._context_menu_source_slot = None

    def _render_buff_context_menu(self, item_id: str) -> None:
        """Stage 181 — контекстное меню бафа: «Активировать» + «Отмена».

        Активация списывает 1 предмет из инвентаря и вешает баф на реальное
        время (player.activate_buff). Результат — строка в боевом логе.
        """
        from pockie_rpg.data.item_db import get_buff_item
        item = get_buff_item(item_id) or {}
        su = self._su
        mx, my = self._context_menu_pos
        menu_w = 160
        menu_h = 86
        if mx + menu_w > SCREEN_WIDTH:
            mx = SCREEN_WIDTH - menu_w - 4
        if my + menu_h > SCREEN_HEIGHT:
            my = SCREEN_HEIGHT - menu_h - 4
        mx, my = self._inv_native_pos((mx, my))
        menu_rect = pygame.Rect(su(mx), su(my), su(menu_w), su(menu_h))
        pygame.draw.rect(self.screen, (30, 30, 35), menu_rect, border_radius=6)
        pygame.draw.rect(self.screen, (234, 179, 8), menu_rect, su(2), border_radius=6)
        name_surf = self._su_font(13).render(item.get("name", item_id), True, (255, 255, 255))
        self.screen.blit(name_surf, (su(mx + 8), su(my + 6)))

        # «Активировать».
        act_rect = pygame.Rect(su(mx + 4), su(my + 24), su(menu_w - 8), su(24))
        act_hover = act_rect.collidepoint(self._mouse_pos)
        act_bg = (20, 60, 40) if act_hover else (15, 40, 25)
        pygame.draw.rect(self.screen, act_bg, act_rect, border_radius=4)
        pygame.draw.rect(self.screen, (80, 220, 100) if act_hover else (60, 80, 60),
                         act_rect, 1, border_radius=4)
        act_surf = self._su_font(13).render("Активировать", True, (80, 220, 100))
        self.screen.blit(act_surf, (su(mx + 8), su(my + 28)))

        # «Отмена».
        cancel_rect = pygame.Rect(su(mx + 4), su(my + 52), su(menu_w - 8), su(22))
        cancel_hover = cancel_rect.collidepoint(self._mouse_pos)
        cancel_bg = (40, 40, 45) if cancel_hover else (30, 30, 35)
        pygame.draw.rect(self.screen, cancel_bg, cancel_rect, border_radius=4)
        cancel_surf = self._su_font(13).render("Отмена", True, (150, 150, 155))
        self.screen.blit(cancel_surf, (su(mx + 8), su(my + 54)))

        def _do_activate() -> None:
            ok, msg = self.player.activate_buff(item_id)
            self._add_log_line(msg)
            self._close_context_menu()
            self._save_player()

        self._click_rects.append(ClickRect(
            tag="activate_buff", rect=act_rect, on_click=_do_activate,
        ))
        self._click_rects.append(ClickRect(
            tag="cancel_context_menu", rect=cancel_rect,
            on_click=self._close_context_menu,
        ))

    def _render_context_menu(self) -> None:
        """Stage 45 — context menu with Use + Sell + Cancel.

        Stage 151 — координаты дизайн-пространства, отрисовка через self._su();
        при нативном инвентаре меню рендерится в native-фазе (позиция клика
        конвертируется в native через self._inv_native_pos()).
        """
        if self._context_menu_item_id is None:
            return
        from pockie_rpg.data.item_db import get_equipment, get_outfit, get_sell_price
        item_id = self._context_menu_item_id
        # Stage 181 — БАФ: своё меню «Активировать» + «Отмена» (без экипировки/
        # продажи). Активация списывает предмет и вешает баф на реальное время.
        if self.player.get_item_definition(item_id) is not None and \
                (self.player.get_item_definition(item_id) or {}).get("is_buff"):
            self._render_buff_context_menu(item_id)
            return
        # Check if it's an outfit (no use/sell for outfits).
        if get_outfit(item_id) is not None:
            self._context_menu_item_id = None
            return
        item = get_equipment(item_id)
        if item is None:
            self._context_menu_item_id = None
            return
        su = self._su
        mx, my = self._context_menu_pos
        menu_w = 160
        menu_h = 110  # Stage 45 — increased for "Use" button
        if mx + menu_w > SCREEN_WIDTH:
            mx = SCREEN_WIDTH - menu_w - 4
        if my + menu_h > SCREEN_HEIGHT:
            my = SCREEN_HEIGHT - menu_h - 4
        # Stage 151 — native-фаза: позиция клика → native (layout'ы нативные).
        mx, my = self._inv_native_pos((mx, my))
        menu_rect = pygame.Rect(su(mx), su(my), su(menu_w), su(menu_h))
        pygame.draw.rect(self.screen, (30, 30, 35), menu_rect, border_radius=6)
        pygame.draw.rect(self.screen, (234, 179, 8), menu_rect, su(2), border_radius=6)
        # Item name.
        name_surf = self._su_font(13).render(item["name"], True, (255, 255, 255))
        self.screen.blit(name_surf, (su(mx + 8), su(my + 6)))

        # "Use" button (equip/unequip).
        is_equipped = any(iid == item_id for iid in self.player.equipped_gear.values())
        use_text = "Снять" if is_equipped else "Использовать"
        use_rect = pygame.Rect(su(mx + 4), su(my + 24), su(menu_w - 8), su(24))
        use_hover = use_rect.collidepoint(self._mouse_pos)
        use_bg = (20, 60, 40) if use_hover else (15, 40, 25)
        pygame.draw.rect(self.screen, use_bg, use_rect, border_radius=4)
        pygame.draw.rect(self.screen, (80, 220, 100) if use_hover else (60, 80, 60),
                         use_rect, 1, border_radius=4)
        use_surf = self._su_font(13).render(use_text, True, (80, 220, 100))
        self.screen.blit(use_surf, (su(mx + 8), su(my + 28)))

        # Sell button.
        sell_price = get_sell_price(item_id)
        sell_text = f"Продать ({sell_price} зол.)"
        sell_rect = pygame.Rect(su(mx + 4), su(my + 50), su(menu_w - 8), su(24))
        sell_hover = sell_rect.collidepoint(self._mouse_pos)
        sell_bg = (60, 40, 20) if sell_hover else (40, 30, 15)
        pygame.draw.rect(self.screen, sell_bg, sell_rect, border_radius=4)
        pygame.draw.rect(self.screen, (234, 179, 8) if sell_hover else (80, 80, 80),
                         sell_rect, 1, border_radius=4)
        sell_surf = self._su_font(13).render(sell_text, True, (234, 179, 8))
        self.screen.blit(sell_surf, (su(mx + 8), su(my + 54)))

        # Cancel button.
        cancel_rect = pygame.Rect(su(mx + 4), su(my + 78), su(menu_w - 8), su(22))
        cancel_hover = cancel_rect.collidepoint(self._mouse_pos)
        cancel_bg = (40, 40, 45) if cancel_hover else (30, 30, 35)
        pygame.draw.rect(self.screen, cancel_bg, cancel_rect, border_radius=4)
        cancel_surf = self._su_font(13).render("Отмена", True, (150, 150, 155))
        self.screen.blit(cancel_surf, (su(mx + 8), su(my + 80)))
        # Register click rects.
        item_id = self._context_menu_item_id
        self._click_rects.append(ClickRect(
            tag="use_item",
            rect=use_rect,
            on_click=lambda: self._use_item(item_id),
        ))
        self._click_rects.append(ClickRect(
            tag="sell_item",
            rect=sell_rect,
            on_click=lambda: self._sell_item(item_id),
        ))
        self._click_rects.append(ClickRect(
            tag="cancel_context_menu",
            rect=cancel_rect,
            on_click=self._close_context_menu,
        ))

    def _run_quick_battle(self, count: int) -> None:
        """Run N battles without animation, collect results.

        Stage 113 — now uses player.process_battle_rewards() for each battle,
        ensuring weapon/armor drops work correctly in x1 and x10 modes.
        Each battle independently rolls drop chances.
        """
        from pockie_rpg.combat.fight import FightSystem
        from pockie_rpg.combat.fighter import Fighter
        from pockie_rpg.game.state import ENEMY_MOBS, ROLES

        enemy = ENEMY_MOBS.get(self.target_mob_id)
        if enemy is None:
            return
        enemy_role = ROLES.get(enemy.role_id)
        if enemy_role is None:
            return

        level_before = self.player.level
        wins = 0
        losses = 0
        total_xp = 0
        total_gold = 0
        all_gems = []
        # Stage 119 — unified single list of equipment drops (max 1 per battle,
        # so up to 10 entries for x10). Replaces per-type lists.
        all_equipment_drops = []

        loc_id = int(self._map_location) if hasattr(self, "_map_location") else 1

        for _ in range(count):
            # Rebuild fighters each battle (HP/MP reset).
            p = Fighter.from_player_state(self.player, enemy_role)
            e = Fighter.from_role(enemy_role, is_player=False, level=enemy.level,
                                   hp_mul=enemy.hp_mul, atk_mul=enemy.atk_mul)
            fs = FightSystem(p, e)
            save = fs.fight()

            if save.winner == 0:
                wins += 1
                # Stage 113 — call server-side process_battle_rewards.
                rewards = self.player.process_battle_rewards(
                    is_victory=True,
                    enemy_mob_id=enemy.mob_id,
                    location_id=loc_id,
                    enemy_xp=enemy.xp_reward,
                    enemy_gold=enemy.gold_reward,
                )
                total_xp += rewards["xp"]
                total_gold += rewards["gold"]
                all_gems.extend(rewards["gems"])
                # Stage 119 — unified equipment_drop (max 1 per battle).
                if rewards.get("equipment_drop"):
                    all_equipment_drops.append(rewards["equipment_drop"])
            else:
                losses += 1
                # On defeat, still process (no rewards, but resets state).
                self.player.process_battle_rewards(
                    is_victory=False,
                    enemy_mob_id=enemy.mob_id,
                    location_id=loc_id,
                )

        self.player.recalc_stats()
        self.player.current_hp = self.player.stats.max_hp
        self.player.current_mp = self.player.stats.max_mp
        self.save_mgr.mark_dirty()

        # Track daily quest: kill mobs (count all wins).
        for _ in range(wins):
            self._track_daily_quest("kill_mobs")

        self._quick_battle_modal_open = False
        self._quick_battle_result = {
            "count": count,
            "wins": wins,
            "losses": losses,
            "xp_gained": total_xp,
            "gold_gained": total_gold,
            "level_before": level_before,
            "level_after": self.player.level,
            "gems_dropped": all_gems,
            # Stage 119 — unified equipment drops list.
            "equipment_drops": all_equipment_drops,
        }

    def _toggle_player_skill(self, skill_id: int) -> None:
        """Toggle whether a player's skill is active (enabled)."""
        if self.player is None:
            return
        from pockie_rpg.game.state import ROLES
        role = ROLES.get(self.player.role_id)
        if role is None or skill_id not in role.skills:
            return
        active = self.player.active_skills
        # Stage 88 — Fix 2.6: removed the `if len(active) <= 1: return` guard
        # that prevented disabling the last skill. Users can now play with all
        # skills disabled (basic-attack-only build). An empty active_skills
        # list is a valid state and Fighter.from_player_state handles it.
        if skill_id in active:
            active.remove(skill_id)
        else:
            active.append(skill_id)
        # Stage 88 — Fix 2.5: use debounced autosave instead of direct save.
        self.save_mgr.mark_dirty()

    def _handle_click(self, pos: tuple[int, int]) -> None:
        """Dispatch click to registered rects (first match wins).

        Stage 57 — Block ALL clicks from reaching mob cards when any modal is open.
        When a modal is open, only modal-related click_rects are processed.
        Mob card tags (open_quick_battle, open_player_sheet_from_map) are skipped.
        """
        # Stage 109 — Test Panel has highest priority (modal overlay).
        if self._test_panel_open:
            self._handle_test_panel_click(pos)
            return

        # Stage 135 — world map modal: клики вне панели закрывают её, внутри —
        # хиттест зон. Нижние клики блокируются ранним return.
        if self._worldmap_modal_open:
            self._handle_worldmap_click(pos)
            return None

        # Stage 138 — synth/wardrobe модалки: полный приоритет.
        # Крестики (close_x_btn) и кнопки «Вынуть» зарегистрированы в
        # _click_rects — проверяем их ПЕРЕД специализированной логикой
        # (ранний return раньше съедал клик и крестик не работал).
        # Stage 162 — клики ВНЕ окон (в т.ч. по предметам инвентаря) больше
        # НЕ закрывают их: игрок перетаскивает костюмы в слоты синтеза/
        # гардероба. Закрытие — только крестик/Escape/кнопки.
        if self._synth_modal_open or self._wardrobe_modal_open:
            for click_rect in self._click_rects:
                if self._click_rect_hit(click_rect, pos):
                    click_rect.on_click()
                    return None
            if self._synth_modal_open:
                self._handle_synth_click(pos)
            return None

        # Stage 61 — char sheet is NOT a modal blocker in battle.
        # In battle, char sheet should not block clicking the other banner.
        if self.state == GameState.BATTLE:
            modal_open = (
                self._inventory_modal_open or
                self._forge_modal_open or
                self._quick_battle_modal_open or
                self._skills_modal_open or
                self._shop_modal_open or
                self._titles_modal_open
            )
        else:
            modal_open = (
                self._inventory_modal_open or
                self._forge_modal_open or
                self._char_sheet_open or
                self._char_sheet2_open or
                self._quick_battle_modal_open or
                self._skills_modal_open or
                self._shop_modal_open or
                self._titles_modal_open or
                self._tower_modal_open or
                self._tower_shop_open or
                self._daily_quest_modal_open or
                self._slot_machine_modal_open or
                (self._las_noches_dialog is not None) or
                (self._tower_result is not None) or
                (self._slot_result is not None) or
                # Stage 172 — диалог сюжетного NPC.
                (self._quest_dialog_npc is not None)
            )
        matched_tag = None
        # Stage 174 — ДВА ПРОХОДА: сначала priority-rect'ы (HUD поверх карты:
        # трекер заданий, кнопки диалогов NPC), затем остальные. Раньше побеждал
        # первый совпавший rect ПО ПОРЯДКУ РЕГИСТРАЦИИ — страж Лас Ночеса
        # (зарегистрирован раньше трекера) перехватывал клики по панели
        # заданий, лежащей на его спрайте.
        for pass_priority in (True, False):
            for click_rect in self._click_rects:
                if click_rect.priority is not pass_priority:
                    continue
                if self._click_rect_hit(click_rect, pos):
                    tag = getattr(click_rect, "tag", "")
                    # Stage 57/81 — skip mob card + boss clicks when any modal is open.
                    # Stage 172 — NPC и трекер заданий тоже инертны под модалками.
                    # Stage 174 — страж ЛН в skip-листе: его rect налезает на
                    # кнопки диалогов (иначе перехватывал их клики).
                    if modal_open and (
                        tag in (
                            "open_quick_battle", "open_player_sheet_from_map",
                            "enter_test_battle", "reset_progression", "debug_level_up",
                            "toggle_minimap", "open_worldmap",
                            "enter_arena", "open_shop",
                            "enter_world_boss",  # Stage 81 — prevent click-through to boss.
                            "open_tower",  # Stage 89 — Tower card.
                            "open_slot_machine",  # Stage 133 — slot machine map icon.
                            "las_noches_guardian",  # Stage 174 — see above.
                        )
                        or tag.startswith("map_npc:")
                        or tag.startswith("quest_tracker_")
                        or tag.startswith("quest_go_to_")
                    ):
                        continue  # skip, try next rect
                    click_rect.on_click()
                    matched_tag = tag
                    break
            if matched_tag is not None:
                break
        # If modal is open and no modal-related rect was matched, consume the click.
        if modal_open and matched_tag is None:
            return None  # consume click, don't let it fall through to mobs
        return matched_tag

    def _click_rect_hit(self, click_rect: ClickRect, pos: tuple[int, int]) -> bool:
        """Stage 150 — hit-тест ClickRect в СВОЁМ координатном пространстве.

        native=True (мигрированный рендер): rect в нативных координатах
        (×UI_SCALE), сравниваем с native-позицией. Legacy: дизайн-позиция.
        """
        if getattr(click_rect, "native", False):
            s = self._ui_scale
            return click_rect.rect.collidepoint(
                (int(pos[0] * s), int(pos[1] * s))
            )
        return click_rect.rect.collidepoint(pos)

    def _inv_native_pos(self, pos: tuple[int, int]) -> tuple[int, int]:
        """Stage 150/151 — позиция события → пространство инвентарных layout'ов.

        Инвентарь мигрирован (нативный рендер) → layout'ы хранят native-rect'ы,
        события приходят в дизайн-координатах — конвертируем ×UI_SCALE.
        Иначе (legacy-инвентарь: маленькое окно / не-2К монитор) — как есть.
        """
        if (self._ui_scale > 1.0 and self._fullscreen_monitor is not None
                and "inventory" in NATIVE_MODAL_REGISTRY
                and self._inventory_modal_open):
            return (int(pos[0] * self._ui_scale), int(pos[1] * self._ui_scale))
        return pos

    def _handle_right_click(self, pos: tuple[int, int]) -> None:
        """Stage 29 — right-click in inventory: equip from inv / unequip from slot."""
        pos = self._inv_native_pos(pos)  # Stage 150 — native layout'ы.
        if not hasattr(self, "_gear_layout") or not hasattr(self, "_inv_layout"):
            return
        # Check gear slots first — right-click on an equipped item → unequip.
        for slot_name, rect in self._gear_layout.items():
            if rect.collidepoint(pos):
                item_id = self.player.equipped_gear.get(slot_name)
                if item_id is not None:
                    self._unequip_gear_item(slot_name)
                return
        # Stage 185 — ПКМ по предмету инвентаря = ОТКРЫТЬ МИКРО-МЕНЮ
        # (прежняя автоактивация/автоодевание удалены по запросу).
        for idx, rect, span in self._inv_layout:
            if rect.collidepoint(pos):
                slots = self.player.inv_page_slots(self._inv_current_page)
                if 0 <= idx < len(slots) and slots[idx] is not None:
                    item_id = self.player.slot_item_id(slots[idx])
                    if item_id:
                        self._open_micromenu(
                            item_id,
                            (self._inv_current_page, idx),
                            pos,
                        )
                return

    def _open_micromenu(self, item_id: str,
                        slot: tuple[int, int],
                        pos: tuple[int, int]) -> None:
        """Stage 185 — открыть микро-меню ПКМ справа от курсора."""
        self._micromenu_item_id = item_id
        self._micromenu_slot = slot
        self._micromenu_pos = pos

    def _shift_click_split_one(self, pos: tuple[int, int]) -> bool:
        """Stage 186 — Shift+ЛКМ по стак-ячейке: перенести 1 шт. в пустую
        ячейку (быстрая раскладка бафов). Возвращает True, если клик съеден
        (попал в стак ≥2)."""
        pos_n = self._inv_native_pos(pos)
        if not hasattr(self, "_inv_layout"):
            return False
        page_slots = self.player.inv_page_slots(self._inv_current_page)
        for slot_idx, rect, span in self._inv_layout:
            if not rect.collidepoint(pos_n):
                continue
            if not (0 <= slot_idx < len(page_slots)):
                return False
            entry = page_slots[slot_idx]
            if entry is None or not isinstance(entry, dict):
                return False  # не стак — обычная обработка клика
            count = int(entry.get("count", 1))
            if count < 2:
                return False  # делить нечего
            if self.player.inv_split(self._inv_current_page, slot_idx, 1):
                self._save_player()
            return True
        return False

    def _close_micromenu(self) -> None:
        self._micromenu_item_id = None
        self._micromenu_slot = None
        self._micromenu_rects = {}

    def _micromenu_use(self) -> None:
        """«Использовать»: баф → активировать (1 шт.), шмот → надеть
        ( equip_gear_item сам проверяет требование уровня)."""
        item_id = self._micromenu_item_id
        slot = self._micromenu_slot
        if not item_id:
            self._close_micromenu()
            return
        bdef = self.player.get_item_definition(item_id)
        if bdef is not None and bdef.get("is_buff"):
            ok, msg = self.player.activate_buff(item_id)
            self._add_log_line(msg)
        else:
            self.player.equip_gear_item(item_id, source_slot=slot)
        self._close_micromenu()
        self._save_player()

    def _micromenu_split(self, take: int) -> None:
        """«Разделить» (половина) / «Разделить на 1» (одна штука)."""
        item_id = self._micromenu_item_id
        slot = self._micromenu_slot
        if not item_id or slot is None:
            self._close_micromenu()
            return
        page, idx = slot
        entry = self.player.inv_page_slots(page)[idx]
        count = self.player.slot_count(entry)
        # «Разделить» = пополам (чёт: 10→5+5; нечёт: 7→4+3 — большая часть
        # остаётся в исходной ячейке).
        if take <= 0:
            take = max(1, count // 2)
        if not self.player.inv_split(page, idx, take):
            self._add_log_line("Нет пустой ячейки для разделения")
        self._close_micromenu()
        self._save_player()

    def _micromenu_sell(self) -> None:
        """«Продать»: продать 1 предмет из стака (как прежняя «Продать»)."""
        item_id = self._micromenu_item_id
        self._close_micromenu()
        if item_id:
            self._sell_item(item_id)

    def _render_micromenu(self) -> None:
        """Stage 185/186 — микро-меню ПКМ: ВЕРТИКАЛЬНЫЙ столбец кнопок
        СПРАВА от курсора (запрос пользователя).

        Кнопки: Использовать | Разделить | Разделить на 1 | Продать.
        Разделения — только для стаков count >= 2. Клик мимо меню закрывает
        (см. LMB-down ветку). Ректы native=True (инвентарь — нативный рендер)
        и priority=True (меню поверх всего).
        """
        if self._micromenu_item_id is None:
            return
        if not self._inventory_modal_open:
            self._close_micromenu()
            return
        slot = self._micromenu_slot
        entry = None
        if slot is not None:
            page, idx = slot
            slots = self.player.inv_page_slots(page)
            if 0 <= idx < len(slots):
                entry = slots[idx]
        if entry is None:
            self._close_micromenu()
            return
        count = self.player.slot_count(entry)

        f_btn = self._su_font(11)
        # Stage 187 — цена продажи на кнопке (бафы/костюмы/шмот, за 1 шт.).
        sell_price = self._get_sell_price(self._micromenu_item_id)
        sell_label = f"Продать ({sell_price})" if sell_price > 0 else "Нельзя продать"
        btn_texts: list[tuple[str, str]] = [("use", "Использовать")]
        if count >= 2:
            btn_texts.append(("split_half", "Разделить"))
            btn_texts.append(("split_one", "Разделить на 1"))
        btn_texts.append(("sell", sell_label))

        # Меню живёт в системе координат инвентаря (нативной при 2К).
        su = self._su
        btn_w = su(128)
        btn_h = su(22)
        btn_gap = su(2)
        total_h = len(btn_texts) * btn_h + (len(btn_texts) - 1) * btn_gap
        # Stage 186 fix — _micromenu_pos УЖЕ в нативных координатах
        # (_handle_right_click конвертирует до сохранения). Повторный вызов
        # _inv_native_pos давал ×4 — меню «улетало» за экран.
        mx, my = self._micromenu_pos
        # Правее от курсора, верх кнопок — на уровне курсора.
        x0 = mx + su(8)
        if x0 + btn_w > self.screen.get_width() - 8:
            x0 = mx - su(8) - btn_w  # у правого края — влево от курсора
        y0 = my
        if y0 + total_h > self.screen.get_height() - 8:
            y0 = self.screen.get_height() - 8 - total_h
        y0 = max(8, y0)

        self._micromenu_rects = {}
        y = y0
        can_sell = sell_price > 0
        for action, label in btn_texts:
            rect = pygame.Rect(x0, y, btn_w, btn_h)
            y += btn_h + btn_gap
            hover = rect.collidepoint(self._mouse_pos) and not (
                action == "sell" and not can_sell)
            accent = (234, 179, 8)
            if action == "use":
                bg = (20, 60, 40) if hover else (15, 40, 25)
                border = (80, 220, 100) if hover else (60, 80, 60)
                fg = (80, 220, 100)
            elif action == "sell":
                # Stage 187 — нельзя продать: тусклая кнопка, клик игнор.
                bg = (60, 40, 20) if hover else (40, 30, 15)
                border = (234, 179, 8) if hover else (80, 80, 80)
                fg = (234, 179, 8) if can_sell else (110, 110, 115)
            else:
                bg = (60, 50, 10) if hover else (40, 40, 45)
                border = accent if hover else (82, 82, 91)
                fg = (255, 255, 255) if hover else (200, 200, 205)
            pygame.draw.rect(self.screen, bg, rect, border_radius=4)
            pygame.draw.rect(self.screen, border, rect, 1, border_radius=4)
            lbl = f_btn.render(label, True, fg)
            self.screen.blit(lbl, lbl.get_rect(midleft=(rect.x + su(10), rect.centery)))
            self._micromenu_rects[action] = rect

        actions = {
            "use": self._micromenu_use,
            "split_half": lambda: self._micromenu_split(0),
            "split_one": lambda: self._micromenu_split(1),
            "sell": self._micromenu_sell,
        }
        for action, rect in self._micromenu_rects.items():
            # Stage 187 — «Нельзя продать» не регистрируется как кнопка.
            if action == "sell" and not can_sell:
                continue
            self._click_rects.append(ClickRect(
                tag=f"micromenu_{action}",
                rect=rect,
                on_click=actions[action],
                native=True,
                priority=True,
            ))

    def _slot_at(self, pos: tuple[int, int]) -> tuple[str, int | str] | None:
        """Stage 64 — return the slot under the cursor, or None.

        Returns ("inv", slot_idx) for inventory cells on the current page,
        or ("gear", slot_name) for equipped-gear cells. Used by the LMB
        gesture tracker to remember where a click started so we can later
        decide whether to treat the gesture as a drag (swap) or a click
        (open context menu).
        """
        pos = self._inv_native_pos(pos)  # Stage 150 — native layout'ы.
        if not hasattr(self, "_gear_layout") or not hasattr(self, "_inv_layout"):
            return None
        # Gear slots first.
        for slot_name, rect in self._gear_layout.items():
            if rect.collidepoint(pos):
                return ("gear", slot_name)
        # Inventory cells on the current page.
        for idx, rect, span in self._inv_layout:
            if rect.collidepoint(pos):
                return ("inv", idx)
        return None

    def _add_log_line(self, text: str) -> None:
        """Append a line to the combat log, trimming to COMBAT_LOG_MAX_LINES."""
        self._combat_log_lines.append(text)
        if len(self._combat_log_lines) > COMBAT_LOG_MAX_LINES:
            self._combat_log_lines = self._combat_log_lines[-COMBAT_LOG_MAX_LINES:]

    def _toggle_combat_log(self) -> None:
        """Toggle the combat log between collapsed and expanded states."""
        self._combat_log_expanded = not self._combat_log_expanded

    def _set_battle_speed(self, speed: float) -> None:
        """Set the battle speed multiplier (clamped to nearest valid)."""
        if speed not in BATTLE_SPEEDS:
            speed = min(BATTLE_SPEEDS, key=lambda s: abs(s - speed))
        self._battle_speed = float(speed)

    def _update_char_sheet_anim(self, dt: float) -> None:
        """Advance the char sheet slide animation (both slots)."""
        step = dt / max(0.001, CHAR_SHEET_ANIM_DURATION)
        # Slot 1.
        if self._char_sheet_open:
            if self._char_sheet_closing:
                self._char_sheet_anim_t = max(0.0, self._char_sheet_anim_t - step)
                if self._char_sheet_anim_t <= 0.0:
                    self._char_sheet_open = False
                    self._char_sheet_closing = False
                    self._char_sheet_anim_t = 0.0
            else:
                self._char_sheet_anim_t = min(1.0, self._char_sheet_anim_t + step)
        # Slot 2.
        if self._char_sheet2_open:
            if self._char_sheet2_closing:
                self._char_sheet2_anim_t = max(0.0, self._char_sheet2_anim_t - step)
                if self._char_sheet2_anim_t <= 0.0:
                    self._char_sheet2_open = False
                    self._char_sheet2_closing = False
                    self._char_sheet2_anim_t = 0.0
            else:
                self._char_sheet2_anim_t = min(1.0, self._char_sheet2_anim_t + step)

    def _update_combat_log_anim(self, dt: float) -> None:
        """Lerp the displayed combat log height toward target."""
        target = float(
            COMBAT_LOG_EXPANDED_H if self._combat_log_expanded else LOG_BAR_H
        )
        step = dt / max(0.001, COMBAT_LOG_ANIM_DURATION)
        diff = target - self._combat_log_height_display
        self._combat_log_height_display += diff * min(1.0, step * 4.0)
        if abs(target - self._combat_log_height_display) < 0.5:
            self._combat_log_height_display = target

        self._speed_buttons_y_offset = -(
            self._combat_log_height_display - float(LOG_BAR_H)
        )
