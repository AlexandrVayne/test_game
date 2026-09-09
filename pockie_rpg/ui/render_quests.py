"""QuestRendererMixin — Stage 172: сюжетные NPC на карте, диалог квестов,
окно навигации по заданиям.

Нативная часть (`_render_map_npcs`, `_render_quest_tracker`) вызывается из
`_render_map` (MAP мигрирован в Stage 153): весь код в ДИЗАЙН-координатах
через `_su`/`_su_rect`/`_su_font`/`_su_image`/`_su_text`. Диалог NPC —
legacy-модалка (как диалог стража Лас Ночеса): рисуется в legacy-слой через
`_render_modal_scaled(self._render_npc_dialog)` в pygame_ui.run().
"""
from __future__ import annotations

import os

import pygame

from pockie_rpg.data.npcs_db import NpcDef, get_npc, npcs_at_location
from pockie_rpg.data.quests_db import (
    STORY_QUESTS,
    get_story_quest,
)
from pockie_rpg.ui.animator import ClickRect


class QuestRendererMixin:
    """Renders story NPCs on the MAP, the NPC quest dialog and the quest tracker.

    Mixin: inherits ``self`` (screen, player, _click_rects, _mouse_pos,
    _map_location, asset_manager, _su-хелперы) from the host PygameUI class.
    """

    # ------------------------------------------------------------------
    # Сцена NPC на карте (нативная фаза MAP)
    # ------------------------------------------------------------------

    def _npc_avatar_path(self, npc: NpcDef) -> str:
        from pockie_rpg.config import ASSETS_DIR, NPC_AVATAR_DIR_NAME
        return str(ASSETS_DIR / NPC_AVATAR_DIR_NAME / npc.avatar_filename)

    def _npc_idle_frame_path(self, npc: NpcDef) -> str | None:
        """Аудит 2026-09 — os.listdir вынесен из кадра: раньше сканирование ФС
        выполнялось 60×/сек для каждого NPC (по вызову из _render_single_npc).
        Список кадров папки константен в сессии — кэшируется по idle_folder;
        ротация кадров остаётся динамической (pygame.time.get_ticks)."""
        from pockie_rpg.config import EXTRACTED_DIR
        if not npc.idle_folder:
            return None
        cache = getattr(self, "_npc_idle_frames_cache", None)
        if cache is None:
            cache = self._npc_idle_frames_cache = {}
        frames = cache.get(npc.idle_folder)
        if frames is None:
            try:
                frames = sorted(
                    (int(f.split(".")[0]), f)
                    for f in os.listdir(str(EXTRACTED_DIR / npc.idle_folder))
                    if f.endswith(".png") and f.split(".")[0].isdigit()
                )
            except OSError:
                frames = []  # папка отсутствует/недоступна — фиксируем пусто
            cache[npc.idle_folder] = frames
        if not frames:
            return None
        if npc.idle_fps > 0:
            idx = int(pygame.time.get_ticks() / 1000.0 * npc.idle_fps) % len(frames)
        else:
            idx = 0
        return str(EXTRACTED_DIR / npc.idle_folder / frames[idx][1])

    def _render_map_npcs(self) -> None:
        """Нарисовать всех NPC текущей локации (спрайт или текст-метка + индикатор)."""
        from pockie_rpg.config import MapLocation
        if self._map_location == MapLocation.LAS_NOCHES:
            return
        for npc in npcs_at_location(int(self._map_location)):
            if npc.map_text:
                self._render_text_label_npc(npc)
            else:
                self._render_single_npc(npc)

    def _load_npc_raw(self, path: str) -> pygame.Surface | None:
        """Сырая поверхность аватарки/кадра (кэш _su_image_raw_cache)."""
        raw_cache = getattr(self, "_su_image_raw_cache", None)
        if raw_cache is None:
            raw_cache = self._su_image_raw_cache = {}
        if path in raw_cache:
            return raw_cache[path]
        try:
            raw = pygame.image.load(path).convert_alpha()
        except Exception:
            raw = None
        raw_cache[path] = raw
        return raw

    def _render_text_label_npc(self, npc: NpcDef) -> None:
        """Stage 174 — NPC как кликабельная текстовая метка (без спрайта и
        аватара на карте; аватар — только внутри диалога). Плашка по центру
        (npc.label_x, npc.label_y); бейдж «!»/«?», стрелка цели и hover-бабл —
        НАД плашкой."""
        import math

        from pockie_rpg.config import (
            NPC_EXCLAMATION_COLOR,
            NPC_HOVER_BUBBLE_BG,
            NPC_HOVER_BUBBLE_BORDER,
            NPC_INDICATOR_BOB_AMP,
            NPC_INDICATOR_BOB_SPEED,
            NPC_INDICATOR_LIFT,
            NPC_INDICATOR_SIZE,
            NPC_READY_COLOR,
        )

        _s = max(0.001, getattr(self, "_render_scale", 1.0))
        text_surf = self._su_text(npc.map_text or npc.name, 14, (244, 244, 245), bold=True)
        plate_w = int(round(text_surf.get_width() / _s)) + 28
        plate_h = int(round(text_surf.get_height() / _s)) + 14
        plate = self._su_rect(
            npc.label_x - plate_w // 2, npc.label_y - plate_h // 2, plate_w, plate_h)
        hover = plate.collidepoint(self._mouse_pos)

        plate_bg = pygame.Surface(plate.size, pygame.SRCALPHA)
        plate_bg.fill((24, 24, 28, 236) if hover else (9, 9, 11, 205))
        self.screen.blit(plate_bg, plate.topleft)
        pygame.draw.rect(self.screen, (52, 211, 153) if hover else (82, 82, 91),
                         plate, self._su(2) if hover else self._su(1), border_radius=8)
        self.screen.blit(text_surf, text_surf.get_rect(center=plate.center))

        has_available, has_ready = self.player.story_quest_npc_indicators(npc.npc_id)
        arrow_target = self._quest_arrow_target()
        show_arrow = (
            arrow_target is not None and arrow_target[0] == "npc"
            and arrow_target[1].npc_id == npc.npc_id
        )

        top_y = npc.label_y - plate_h // 2
        if has_available or has_ready:
            symbol = "!" if has_available else "?"
            color = NPC_EXCLAMATION_COLOR if has_available else NPC_READY_COLOR
            phase = (pygame.time.get_ticks() / 1000.0) * NPC_INDICATOR_BOB_SPEED * 2 * math.pi
            bob = int(NPC_INDICATOR_BOB_AMP * 0.5 * (1.0 + math.sin(phase)))
            badge_size = self._su(NPC_INDICATOR_SIZE)
            badge_rect = pygame.Rect(
                self._su(npc.label_x) - badge_size // 2,
                self._su(top_y) - self._su(NPC_INDICATOR_LIFT) - badge_size + bob,
                badge_size, badge_size,
            )
            pygame.draw.circle(self.screen, (9, 9, 11), badge_rect.center,
                               badge_size // 2 + self._su(2))
            pygame.draw.circle(self.screen, color, badge_rect.center, badge_size // 2)
            pygame.draw.circle(self.screen, (20, 20, 24), badge_rect.center,
                               badge_size // 2, self._su(2))
            glyph = self._su_font(15, True).render(symbol, True, (20, 20, 24))
            self.screen.blit(glyph, glyph.get_rect(center=badge_rect.center))

        if show_arrow:
            tip_y = (top_y - NPC_INDICATOR_LIFT - NPC_INDICATOR_SIZE - 10
                     if has_available or has_ready
                     else top_y - NPC_INDICATOR_LIFT - 10)
            self._draw_quest_arrow(npc.label_x, tip_y)

        if hover and npc.hover_text:
            tip_surf = self._su_text(npc.hover_text, 13, (255, 255, 255), bold=True)
            tip_w = int(round(tip_surf.get_width() / _s)) + 24
            tip_h = int(round(tip_surf.get_height() / _s)) + 12
            bubble_x = npc.label_x - tip_w // 2
            bubble_y = top_y - NPC_INDICATOR_LIFT - NPC_INDICATOR_SIZE - tip_h - 8
            bubble_rect = self._su_rect(bubble_x, bubble_y, tip_w, tip_h)
            pygame.draw.rect(self.screen, NPC_HOVER_BUBBLE_BG, bubble_rect, border_radius=8)
            pygame.draw.rect(self.screen, NPC_HOVER_BUBBLE_BORDER, bubble_rect,
                             self._su(2), border_radius=8)
            tail_pts = [
                (self._su(bubble_x + tip_w // 2 - 8), self._su(bubble_y + tip_h)),
                (self._su(bubble_x + tip_w // 2), self._su(bubble_y + tip_h + 12)),
                (self._su(bubble_x + tip_w // 2 + 8), self._su(bubble_y + tip_h)),
            ]
            pygame.draw.polygon(self.screen, NPC_HOVER_BUBBLE_BG, tail_pts)
            pygame.draw.lines(self.screen, NPC_HOVER_BUBBLE_BORDER, False, tail_pts, self._su(2))
            self.screen.blit(tip_surf, (self._su(bubble_x + 12), self._su(bubble_y + 6)))

        self._click_rects.append(ClickRect(
            tag=f"map_npc:{npc.npc_id}",
            rect=plate.inflate(self._su(14), self._su(12)),
            on_click=lambda nid=npc.npc_id: self._open_npc_dialog(nid),
        ))

    def _render_single_npc(self, npc: NpcDef) -> None:
        import math

        from pockie_rpg.config import (
            NPC_EXCLAMATION_COLOR,
            NPC_HOVER_BUBBLE_BG,
            NPC_HOVER_BUBBLE_BORDER,
            NPC_INDICATOR_BOB_AMP,
            NPC_INDICATOR_BOB_SPEED,
            NPC_INDICATOR_LIFT,
            NPC_INDICATOR_SIZE,
            NPC_NAME_PLATE_BG,
            NPC_NAME_PLATE_TEXT,
            NPC_READY_COLOR,
        )

        frame_path = self._npc_idle_frame_path(npc)
        load_path = frame_path if frame_path is not None else self._npc_avatar_path(npc)
        raw_surf = self._load_npc_raw(load_path)
        if raw_surf is None:
            return
        rw, rh = raw_surf.get_size()
        sprite_w = max(1, int(npc.sprite_h * rw / max(1, rh)))
        sprite_surf = self._su_scaled(
            f"__npc__:{load_path}:{npc.sprite_h}", raw_surf, sprite_w, npc.sprite_h)

        nx = npc.ground_x - sprite_w // 2
        ny = npc.ground_y - npc.sprite_h

        shadow_w = max(40, int(sprite_w * 0.55))
        shadow_surf = pygame.Surface((self._su(shadow_w), self._su(18)), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surf, (0, 0, 0, 120),
                            (0, 0, self._su(shadow_w), self._su(18)))
        self.screen.blit(shadow_surf, (
            self._su(npc.ground_x - shadow_w // 2), self._su(npc.ground_y - 9)))

        self.screen.blit(sprite_surf, (self._su(nx), self._su(ny)))

        name_surf = self._su_text(npc.name, 12, NPC_NAME_PLATE_TEXT, bold=True)
        plate_w = name_surf.get_width() + self._su(14)
        plate_h = name_surf.get_height() + self._su(6)
        plate_rect = pygame.Rect(
            self._su(npc.ground_x) - plate_w // 2,
            self._su(npc.ground_y) + self._su(6),
            plate_w, plate_h,
        )
        plate_bg = pygame.Surface(plate_rect.size, pygame.SRCALPHA)
        plate_bg.fill(NPC_NAME_PLATE_BG)
        self.screen.blit(plate_bg, plate_rect.topleft)
        pygame.draw.rect(self.screen, (82, 82, 91), plate_rect, self._su(1), border_radius=4)
        self.screen.blit(name_surf, name_surf.get_rect(center=plate_rect.center))

        npc_rect = self._su_rect(nx - 8, ny - 8, sprite_w + 16, npc.sprite_h + 16)
        hover = npc_rect.collidepoint(self._mouse_pos)

        has_available, has_ready = self.player.story_quest_npc_indicators(npc.npc_id)

        # Stage 173 — стрелка-подсветка цели после «Перейти» (поверх бейджа).
        arrow_target = self._quest_arrow_target()
        show_arrow = (
            arrow_target is not None and arrow_target[0] == "npc"
            and arrow_target[1].npc_id == npc.npc_id
        )

        if has_available or has_ready:
            symbol = "!" if has_available else "?"
            color = NPC_EXCLAMATION_COLOR if has_available else NPC_READY_COLOR
            phase = (pygame.time.get_ticks() / 1000.0) * NPC_INDICATOR_BOB_SPEED * 2 * math.pi
            bob = int(NPC_INDICATOR_BOB_AMP * 0.5 * (1.0 + math.sin(phase)))
            badge_size = self._su(NPC_INDICATOR_SIZE)
            badge_rect = pygame.Rect(
                self._su(npc.ground_x) - badge_size // 2,
                self._su(ny) - self._su(NPC_INDICATOR_LIFT) - badge_size + bob,
                badge_size, badge_size,
            )
            pygame.draw.circle(self.screen, (9, 9, 11), badge_rect.center, badge_size // 2 + self._su(2))
            pygame.draw.circle(self.screen, color, badge_rect.center, badge_size // 2)
            pygame.draw.circle(self.screen, (20, 20, 24), badge_rect.center, badge_size // 2, self._su(2))
            glyph = self._su_font(15, True).render(symbol, True, (20, 20, 24))
            self.screen.blit(glyph, glyph.get_rect(center=badge_rect.center))

        if show_arrow:
            # Остриё — чуть выше бейджа «!»/«?» или головы, если бейджа нет.
            tip_y = (ny - NPC_INDICATOR_LIFT - NPC_INDICATOR_SIZE - 10
                     if has_available or has_ready
                     else ny - NPC_INDICATOR_LIFT - 10)
            self._draw_quest_arrow(npc.ground_x, tip_y)

        if hover and npc.hover_text:
            tip_surf = self._su_text(npc.hover_text, 13, (255, 255, 255), bold=True)
            _s = max(0.001, getattr(self, "_render_scale", 1.0))
            tip_w = int(round(tip_surf.get_width() / _s)) + 24
            tip_h = int(round(tip_surf.get_height() / _s)) + 12
            bubble_x = npc.ground_x - tip_w // 2
            bubble_y = ny - NPC_INDICATOR_LIFT - NPC_INDICATOR_SIZE - tip_h - 8
            bubble_rect = self._su_rect(bubble_x, bubble_y, tip_w, tip_h)
            pygame.draw.rect(self.screen, NPC_HOVER_BUBBLE_BG, bubble_rect, border_radius=8)
            pygame.draw.rect(self.screen, NPC_HOVER_BUBBLE_BORDER, bubble_rect, self._su(2), border_radius=8)
            tail_pts = [
                (self._su(bubble_x + tip_w // 2 - 8), self._su(bubble_y + tip_h)),
                (self._su(bubble_x + tip_w // 2), self._su(bubble_y + tip_h + 12)),
                (self._su(bubble_x + tip_w // 2 + 8), self._su(bubble_y + tip_h)),
            ]
            pygame.draw.polygon(self.screen, NPC_HOVER_BUBBLE_BG, tail_pts)
            pygame.draw.lines(self.screen, NPC_HOVER_BUBBLE_BORDER, False, tail_pts, self._su(2))
            self.screen.blit(tip_surf, (self._su(bubble_x + 12), self._su(bubble_y + 6)))
            pygame.draw.rect(self.screen, NPC_HOVER_BUBBLE_BORDER + (90,),
                             npc_rect.inflate(self._su(6), self._su(6)),
                             self._su(2), border_radius=10)

        self._click_rects.append(ClickRect(
            tag=f"map_npc:{npc.npc_id}",
            rect=npc_rect,
            on_click=lambda nid=npc.npc_id: self._open_npc_dialog(nid),
        ))

    # ------------------------------------------------------------------
    # Окно навигации по заданиям (HUD, правый нижний угол — Stage 173)
    # ------------------------------------------------------------------

    def _quest_tracker_lists(self) -> tuple[list[str], list[str]]:
        """(доступные, в процессе) — по цепочке."""
        from pockie_rpg.data.quests_db import STORY_QUEST_CHAIN
        available = [q for q in STORY_QUEST_CHAIN if self.player.story_quest_available(q)]
        active = [q for q in self.player.story_quests_active if q in STORY_QUESTS]
        return available, active

    def _quest_toggle_tracker(self) -> None:
        self._quest_tracker_collapsed = not self._quest_tracker_collapsed

    def _quest_set_tab(self, idx: int) -> None:
        self._quest_tracker_tab = idx

    def _quest_goal_display_text(self, quest_id: str) -> str:
        """Строка цели для трекера/диалога; kill_mobs получает счётчик
        «(2/3)» (Stage 173)."""
        quest = get_story_quest(quest_id)
        if quest is None:
            return ""
        if (quest.goal_type == "kill_mobs"
                and quest_id in self.player.story_quests_active):
            done, need = self.player.story_quest_kill_progress(quest_id)
            return f"{quest.goal_text} ({done}/{need})"
        return quest.goal_text

    def _quest_target_location(self, quest_id: str) -> int | None:
        """Куда ведёт «Перейти» (Stage 173): активный квест с невыполненной
        целью — на quest.location (место цели); не взятый или готовый к сдаче —
        к giver'у (взять/сдать можно только у него)."""
        quest = get_story_quest(quest_id)
        if quest is None:
            return None
        if (quest_id in self.player.story_quests_active
                and not self.player.story_quest_goal_done(quest_id)):
            return int(quest.location)
        giver = get_npc(quest.giver_npc)
        return int(giver.location) if giver is not None else int(quest.location)

    def _quest_go_to(self, quest_id: str) -> None:
        from pockie_rpg.config import (
            QUEST_ARROW_SEC,
            MapLocation,
        )
        from pockie_rpg.data.worldmap_db import LOCATION_MIN_UNLOCK
        quest = get_story_quest(quest_id)
        if quest is None:
            return
        target_loc = self._quest_target_location(quest_id)
        if target_loc is None:
            return
        prev = self._map_location
        self._go_to_location(target_loc)
        if int(self._map_location) == target_loc:
            if self._map_location != prev:
                # Stage 173 — стрелка-подсветка над целью (NPC или ряд мобов).
                self._quest_arrow_quest = quest_id
                self._quest_arrow_timer = QUEST_ARROW_SEC
            return
        if (target_loc != MapLocation.CITY
                and self.player.level < LOCATION_MIN_UNLOCK.get(target_loc, 0)):
            self._show_quest_feedback("Локация закрыта — нужен выше уровень")

    # ------------------------------------------------------------------
    # Стрелка-подсветка цели (Stage 173)
    # ------------------------------------------------------------------

    def _quest_arrow_target(self):
        """Валидная цель стрелки сейчас: ("npc", NpcDef) | ("mobs", None) | None.
        Пересчитывается каждый кадр из состояния игрока — стрелка сама гаснет
        при смене локации/сдаче квеста, таймер только ограничивает время."""
        if not self._quest_arrow_quest or self._quest_arrow_timer <= 0:
            return None
        quest = get_story_quest(self._quest_arrow_quest)
        if quest is None:
            return None
        loc = int(self._map_location)
        if (self._quest_arrow_quest in self.player.story_quests_active
                and not self.player.story_quest_goal_done(self._quest_arrow_quest)):
            if quest.goal_type == "kill_mobs":
                # Цель — бой: подсвечиваем ряд карточек мобов локации.
                return ("mobs", None) if int(quest.location) == loc else None
            target_id = (quest.goal_target if quest.goal_type == "talk_to"
                         else quest.giver_npc)
            npc = get_npc(target_id)
            if npc is not None and int(npc.location) == loc:
                return ("npc", npc)
            return None
        giver = get_npc(quest.giver_npc)
        if giver is not None and int(giver.location) == loc:
            return ("npc", giver)
        return None

    def _draw_quest_arrow(self, cx: int, tip_y: int) -> None:
        """Золотая стрелка остриём вниз, покачивается над (cx, tip_y)
        (дизайн-координаты). Рисуется ПОСЛЕ бейджа «!»/«?» — поверх."""
        import math

        from pockie_rpg.config import (
            QUEST_ARROW_BOB_AMP,
            QUEST_ARROW_BOB_SPEED,
            QUEST_ARROW_COLOR,
            QUEST_ARROW_H,
            QUEST_ARROW_OUTLINE,
            QUEST_ARROW_W,
        )
        phase = (pygame.time.get_ticks() / 1000.0) * QUEST_ARROW_BOB_SPEED * 2 * math.pi
        bob = int(QUEST_ARROW_BOB_AMP * 0.5 * (1.0 + math.sin(phase)))
        cx_su = self._su(cx)
        ty = self._su(tip_y + bob)
        w = self._su(QUEST_ARROW_W)
        h = self._su(QUEST_ARROW_H)
        main = [(cx_su - w // 2, ty - h), (cx_su + w // 2, ty - h), (cx_su, ty)]
        pad = self._su(3)
        big = [(main[0][0] - pad, main[0][1] - pad),
               (main[1][0] + pad, main[1][1] - pad),
               (main[2][0], main[2][1] + pad)]
        pygame.draw.polygon(self.screen, QUEST_ARROW_OUTLINE, big)
        pygame.draw.polygon(self.screen, QUEST_ARROW_COLOR, main)
        pygame.draw.lines(self.screen, QUEST_ARROW_OUTLINE, False, main, self._su(1))

    def _render_quest_mobs_arrow(self) -> None:
        """Стрелка над первым рядом карточек мобов (kill_mobs-цель после
        «Перейти»). Вызывается из _render_map ПОСЛЕ отрисовки карточек."""
        from pockie_rpg.config import (
            LOCATIONS_DB,
            MAP_CARD_GAP,
            MAP_CARD_W,
            MAP_PANEL_HEIGHT,
            SCREEN_WIDTH,
        )
        target = self._quest_arrow_target()
        if target is None or target[0] != "mobs":
            return
        loc_info = LOCATIONS_DB.get(int(self._map_location))
        if not loc_info:
            return
        mob_ids = loc_info.get("mobs", [])
        if not mob_ids:
            return
        row_w = len(mob_ids) * MAP_CARD_W + (len(mob_ids) - 1) * MAP_CARD_GAP
        row_x_start = (SCREEN_WIDTH - row_w) // 2
        card_y = 60 + MAP_PANEL_HEIGHT
        self._draw_quest_arrow(row_x_start + MAP_CARD_W // 2, card_y - 8)

    def _show_quest_feedback(self, text: str) -> None:
        from pockie_rpg.config import QUEST_DIALOG_FEEDBACK_SEC
        self._quest_feedback = text
        self._quest_feedback_timer = QUEST_DIALOG_FEEDBACK_SEC

    def _render_quest_tracker(self) -> None:
        from pockie_rpg.config import (
            QUEST_TRACKER_ACCENT,
            QUEST_TRACKER_BG,
            QUEST_TRACKER_BORDER,
            QUEST_TRACKER_BOTTOM_MARGIN,
            QUEST_TRACKER_HEADER_H,
            QUEST_TRACKER_MAX_NAME_CHARS,
            QUEST_TRACKER_MAX_ROWS,
            QUEST_TRACKER_ROW_H,
            QUEST_TRACKER_TAB_ACTIVE_BG,
            QUEST_TRACKER_TAB_H,
            QUEST_TRACKER_TAB_IDLE_BG,
            QUEST_TRACKER_W,
            QUEST_TRACKER_X,
            SCREEN_HEIGHT,
        )
        available, active = self._quest_tracker_lists()
        rows = active if self._quest_tracker_tab == 1 else available
        rows = rows[:QUEST_TRACKER_MAX_ROWS]

        if self._quest_tracker_collapsed:
            # Stage 174 — плавающая кнопка 44×44 удалена: сворачивание/разворачивание
            # — иконка «Т» в нижнем UI-баре (_render_bottom_bar). Здесь остаётся
            # только тост (над нижним баром, справа).
            from pockie_rpg.config import BOTTOM_BAR_HEIGHT
            self._render_quest_feedback(
                QUEST_TRACKER_X, SCREEN_HEIGHT - BOTTOM_BAR_HEIGHT - 8,
                QUEST_TRACKER_W, above=True)
            return

        header_h = QUEST_TRACKER_HEADER_H
        tabs_h = QUEST_TRACKER_TAB_H
        panel_h = header_h + tabs_h + len(rows) * QUEST_TRACKER_ROW_H + 10
        # Stage 173 — нижний якорь: низ панели на BOTTOM_MARGIN выше низа экрана,
        # верх вычисляется от фактической высоты контента.
        top = SCREEN_HEIGHT - QUEST_TRACKER_BOTTOM_MARGIN - panel_h
        panel_rect = self._su_rect(QUEST_TRACKER_X, top,
                                   QUEST_TRACKER_W, panel_h)
        panel_bg = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
        panel_bg.fill(QUEST_TRACKER_BG)
        self.screen.blit(panel_bg, panel_rect.topleft)
        pygame.draw.rect(self.screen, QUEST_TRACKER_BORDER, panel_rect,
                         self._su(1), border_radius=8)
        pygame.draw.rect(self.screen, QUEST_TRACKER_ACCENT,
                         (panel_rect.x, panel_rect.y, panel_rect.w, self._su(2)),
                         border_radius=2)

        header_rect = pygame.Rect(panel_rect.x + self._su(10), panel_rect.y + self._su(6),
                                  panel_rect.w - self._su(64), self._su(header_h - 10))
        title_surf = self._su_text("Задания", 14, QUEST_TRACKER_ACCENT, bold=True)
        self.screen.blit(title_surf, title_surf.get_rect(midleft=header_rect.midleft))

        collapse_rect = pygame.Rect(panel_rect.right - self._su(28), panel_rect.y + self._su(5),
                                    self._su(22), self._su(20))
        col_hover = collapse_rect.collidepoint(self._mouse_pos)
        pygame.draw.rect(self.screen, (80, 80, 90) if col_hover else (52, 52, 58),
                         collapse_rect, border_radius=4)
        sign = self._su_text("—", 12, (255, 255, 255), bold=True)
        self.screen.blit(sign, sign.get_rect(center=collapse_rect.center))
        self._click_rects.append(ClickRect(
            tag="quest_tracker_collapse", rect=collapse_rect,
            on_click=self._quest_toggle_tracker, priority=True))

        tab_w = (QUEST_TRACKER_W - 12) // 2
        for tab_idx, (tab_name, count) in enumerate(
                (("Доступные", len(available)), ("В процессе", len(active)))):
            tab_rect = self._su_rect(QUEST_TRACKER_X + 6 + tab_idx * (tab_w + 2),
                                     top + header_h, tab_w, tabs_h - 6)
            is_cur = self._quest_tracker_tab == tab_idx
            pygame.draw.rect(self.screen,
                             QUEST_TRACKER_TAB_ACTIVE_BG if is_cur else QUEST_TRACKER_TAB_IDLE_BG,
                             tab_rect, border_radius=5)
            if is_cur:
                pygame.draw.rect(self.screen, QUEST_TRACKER_ACCENT, tab_rect, self._su(1), border_radius=5)
            tab_surf = self._su_text(f"{tab_name} ({count})", 11,
                                     (255, 255, 255) if is_cur else (161, 161, 170), bold=is_cur)
            self.screen.blit(tab_surf, tab_surf.get_rect(center=tab_rect.center))
            self._click_rects.append(ClickRect(
                tag=f"quest_tracker_tab_{tab_idx}", rect=tab_rect,
                on_click=lambda i=tab_idx: self._quest_set_tab(i), priority=True))

        row_y = top + header_h + tabs_h
        for qid in rows:
            quest = STORY_QUESTS.get(qid)
            if quest is None:
                continue
            row_rect = self._su_rect(QUEST_TRACKER_X + 6, row_y + 2, QUEST_TRACKER_W - 12,
                                     QUEST_TRACKER_ROW_H - 4)
            row_hover = row_rect.collidepoint(self._mouse_pos)
            if row_hover:
                pygame.draw.rect(self.screen, (39, 39, 44), row_rect, border_radius=6)
            is_ready = self.player.story_quest_goal_done(qid)
            dot_color = (52, 211, 153) if is_ready else (
                QUEST_TRACKER_ACCENT if self._quest_tracker_tab == 0 else (113, 113, 122))
            pygame.draw.circle(self.screen, dot_color,
                               (row_rect.x + self._su(9), row_rect.y + self._su(12)), self._su(4))
            name = quest.name
            if len(name) > QUEST_TRACKER_MAX_NAME_CHARS:
                name = name[: QUEST_TRACKER_MAX_NAME_CHARS - 1] + "…"
            name_surf = self._su_text(name, 12, (244, 244, 245), bold=True)
            self.screen.blit(name_surf, (row_rect.x + self._su(20), row_rect.y + self._su(4)))
            goal_name = self._quest_goal_display_text(qid)
            if len(goal_name) > 30:
                goal_name = goal_name[:29] + "…"
            goal_surf = self._su_text(goal_name, 10, (161, 161, 170))
            self.screen.blit(goal_surf, (row_rect.x + self._su(20), row_rect.y + self._su(22)))

            # Stage 173 — «Вы здесь» теперь по ЦЕЛЕВОЙ локации (зависит от
            # состояния: невзятый/готовый квест → giver, активный → место цели).
            target_loc = self._quest_target_location(qid)
            here = (target_loc is not None
                    and int(self._map_location) == int(target_loc))
            go_rect = pygame.Rect(row_rect.right - self._su(76), row_rect.y + self._su(6),
                                  self._su(70), self._su(20))
            go_hover = go_rect.collidepoint(self._mouse_pos)
            if here:
                pygame.draw.rect(self.screen, (39, 39, 42), go_rect, border_radius=4)
                pygame.draw.rect(self.screen, (63, 63, 70), go_rect, self._su(1), border_radius=4)
                go_surf = self._su_text("Вы здесь", 10, (113, 113, 122), bold=True)
            else:
                pygame.draw.rect(self.screen, (22, 101, 52) if go_hover else (22, 72, 38),
                                 go_rect, border_radius=4)
                pygame.draw.rect(self.screen, (134, 239, 172) if go_hover else (52, 211, 153),
                                 go_rect, self._su(1), border_radius=4)
                go_surf = self._su_text("Перейти →", 10, (255, 255, 255), bold=True)
            self.screen.blit(go_surf, go_surf.get_rect(center=go_rect.center))
            if not here:
                self._click_rects.append(ClickRect(
                    tag=f"quest_go_to_{qid}", rect=go_rect,
                    on_click=lambda q=qid: self._quest_go_to(q), priority=True))
            row_y += QUEST_TRACKER_ROW_H

        # Тост — НАД панелью (панель прижата к низу экрана).
        self._render_quest_feedback(QUEST_TRACKER_X, panel_rect.top, QUEST_TRACKER_W,
                                    above=True)

    def _render_quest_feedback(self, x: int, y: int, w: int, above: bool = False) -> None:
        """Тост-подсказка. above=True — тост ПРИЖИМАЕТСЯ НИЗОМ к y (панель в
        нижнем углу, иначе тост ушёл бы за экран)."""
        if not self._quest_feedback or self._quest_feedback_timer <= 0:
            return
        from pockie_rpg.config import SCREEN_WIDTH
        fb_surf = self._su_text(self._quest_feedback, 11, (250, 204, 21))
        pad = self._su(8)
        fb_rect = pygame.Rect(self._su(x), self._su(y),
                              fb_surf.get_width() + pad * 2,
                              fb_surf.get_height() + pad)
        if above:
            fb_rect.bottom = self._su(y) - self._su(6)
        if fb_rect.right > self._su(SCREEN_WIDTH) - self._su(8):
            fb_rect.right = self._su(SCREEN_WIDTH) - self._su(8)
        bg = pygame.Surface(fb_rect.size, pygame.SRCALPHA)
        bg.fill((9, 9, 11, 214))
        self.screen.blit(bg, fb_rect.topleft)
        pygame.draw.rect(self.screen, (234, 179, 8), fb_rect, self._su(1), border_radius=6)
        self.screen.blit(fb_surf, fb_surf.get_rect(center=fb_rect.center))

    # ------------------------------------------------------------------
    # Диалог NPC (legacy-модалка через _render_modal_scaled)
    # ------------------------------------------------------------------

    def _open_npc_dialog(self, npc_id: str) -> None:
        npc = get_npc(npc_id)
        if npc is None:
            return
        self._quest_dialog_npc = npc_id
        import random as _r
        _rng = _r.Random()  # локальный экземпляр — глобальный RNG не трогаем (урок A1)
        self._quest_dialog_flavor = (
            _rng.choice(npc.flavor) if npc.flavor else npc.hover_text)

    def _close_npc_dialog(self) -> None:
        self._quest_dialog_npc = None

    def _npc_dialog_context(self, npc: NpcDef) -> dict:
        """Что показывать в диалоге: turn_in / offer / reminder / flavor."""
        ready = [
            qid for qid in self.player.active_story_quests_at(npc.npc_id)
            if self.player.story_quest_goal_done(qid)
        ]
        if ready:
            return {"kind": "turn_in", "quest_id": ready[0]}
        available = [
            qid for qid, q in STORY_QUESTS.items()
            if q.giver_npc == npc.npc_id and self.player.story_quest_available(qid)
        ]
        if available:
            return {"kind": "offer", "quest_id": available[0]}
        waiting = [
            qid for qid in self.player.active_story_quests_at(npc.npc_id)
            if not self.player.story_quest_goal_done(qid)
        ]
        if waiting:
            return {"kind": "reminder", "quest_id": waiting[0]}
        return {"kind": "flavor"}

    def _quest_accept(self, quest_id: str) -> None:
        if self.player.accept_story_quest(quest_id):
            self._save_player()

    def _quest_turn_in(self, quest_id: str) -> None:
        from pockie_rpg.data.item_db import get_equipment
        result = self.player.turn_in_story_quest(quest_id)
        if result is None:
            return
        if result.get("item_failed"):
            self._show_quest_feedback("Инвентарь полон — освободите место!")
            return
        parts = []
        if result["xp"]:
            parts.append(f"+{result['xp']} опыта")
        if result["gold"]:
            parts.append(f"+{result['gold']} золота")
        if result["coupons"]:
            parts.append(f"+{result['coupons']} купонов")
        if result["item"]:
            item = get_equipment(result["item"])
            parts.append(f"получено: {item['name']}" if item else "получен предмет")
        if result["leveled_up"]:
            parts.append("НОВЫЙ УРОВЕНЬ!")
        self._show_quest_feedback("Задание выполнено: " + ", ".join(parts))
        self._gold_flash_timer = 1.0
        self._gold_flash_amount = result["gold"]
        self._save_player()

    def _quest_reward_lines(self, quest_id: str) -> list[str]:
        from pockie_rpg.data.item_db import get_equipment
        quest = get_story_quest(quest_id)
        if quest is None:
            return []
        lines = []
        if quest.reward_xp:
            lines.append(f"Опыт: {quest.reward_xp}")
        if quest.reward_gold:
            lines.append(f"Золото: {quest.reward_gold}")
        if quest.reward_coupons:
            lines.append(f"Купоны: {quest.reward_coupons}")
        if quest.reward_item:
            item = get_equipment(quest.reward_item)
            item_name = item["name"] if item else quest.reward_item
            lines.append(f"Предмет: {item_name}")
        if not lines:
            lines.append("Нет награды")
        return lines

    def _wrap_dialog_text(self, text: str, font: pygame.font.Font, max_width: int) -> list[str]:
        """Перенос по словам под заданную ширину (дизайн-координаты)."""
        words = text.split()
        if not words:
            return [""]
        lines: list[str] = []
        cur = words[0]
        for word in words[1:]:
            probe = f"{cur} {word}"
            if font.size(probe)[0] <= max_width:
                cur = probe
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
        return lines

    # ------------------------------------------------------------------
    # Stage 174 — общие элементы ЕДИНОГО окна NPC (сюжетные диалоги И
    # диалоги стража Лас Ночеса): рамка, разделитель секций, маленькая кнопка.
    # ------------------------------------------------------------------

    def _npc_window_frame(self, x: int, y: int, w: int, h: int,
                          accent: tuple[int, int, int]) -> None:
        """Рамка единого окна NPC: тёмный фон + акцентный контур + полоса сверху."""
        pygame.draw.rect(self.screen, (24, 24, 27), (x, y, w, h), border_radius=12)
        pygame.draw.rect(self.screen, accent, (x, y, w, h), 2, border_radius=12)
        pygame.draw.rect(self.screen, accent, (x, y, w, 6), border_radius=3)

    def _npc_window_divider(self, x: int, y: int, w: int) -> None:
        """Жёсткий горизонтальный разделитель секций внутри окна NPC."""
        pygame.draw.line(self.screen, (82, 82, 91), (x, y), (x + w, y), self._su(1))

    def _npc_window_button(self, rect: pygame.Rect, label: str,
                           base: tuple[int, int, int],
                           hover_bg: tuple[int, int, int],
                           text_color: tuple[int, int, int],
                           tag: str, on_click) -> None:
        """Маленькая кнопка единого окна NPC (шрифт banner 14 bold, h=28)."""
        hover = rect.collidepoint(self._mouse_pos)
        pygame.draw.rect(self.screen, hover_bg if hover else base, rect, border_radius=6)
        pygame.draw.rect(self.screen, (255, 255, 255), rect, self._su(1), border_radius=6)
        lbl = self.font_banner.render(label, True, text_color)
        self.screen.blit(lbl, lbl.get_rect(center=rect.center))
        self._click_rects.append(ClickRect(
            tag=tag, rect=rect, on_click=on_click, priority=True))

    def _render_npc_dialog(self) -> None:
        """Stage 174 — ЕДИНОЕ окно диалога NPC для ВСЕХ случаев
        (offer / turn_in / reminder / flavor — и тот же стиль у стража ЛН):
        • ширина QUEST_DIALOG_W, высота ДИНАМИЧЕСКАЯ (MIN_H..MAX_H) — окно
          сжимается, если текста мало;
        • жёсткие секции: ШАПКА (аватар + имя) | ЗАДАНИЕ/описание | НАГРАДЫ,
          разделённые линиями `_npc_window_divider`;
        • маленькие кнопки (QUEST_DIALOG_BTN_H=28)."""
        from pockie_rpg.config import (
            MODAL_CONTENT_PADDING,
            QUEST_DIALOG_ACCENT,
            QUEST_DIALOG_BTN_H,
            QUEST_DIALOG_FLAVOR_ACCENT,
            QUEST_DIALOG_HEADER_H,
            QUEST_DIALOG_MAX_H,
            QUEST_DIALOG_MIN_H,
            QUEST_DIALOG_PORTRAIT_SIZE,
            QUEST_DIALOG_W,
            SCREEN_HEIGHT,
            SCREEN_WIDTH,
        )
        npc = get_npc(self._quest_dialog_npc or "")
        if npc is None:
            self._quest_dialog_npc = None
            return

        ctx = self._npc_dialog_context(npc)
        quest = (get_story_quest(ctx["quest_id"])
                 if ctx["kind"] in ("offer", "turn_in", "reminder") else None)
        accent = (QUEST_DIALOG_FLAVOR_ACCENT if ctx["kind"] == "flavor"
                  else QUEST_DIALOG_ACCENT)

        pad = MODAL_CONTENT_PADDING
        modal_w = QUEST_DIALOG_W
        inner_x = pad
        inner_w = modal_w - pad * 2
        name_font = self.font_button
        body_font = self.font_small
        head_font = self.font_banner

        # --- Измерение контента (строки секций) ---------------------------
        # (текст, цвет, шрифт) — высота строки берётся из font.size.
        body_lines: list[tuple[str, tuple[int, int, int], pygame.font.Font]] = []
        rew_lines: list[tuple[str, tuple[int, int, int], pygame.font.Font]] = []
        if ctx["kind"] == "offer" and quest is not None:
            body_lines.append((f"Задание: {quest.name}", accent, head_font))
            body_lines.extend(
                (ln, (255, 255, 255), body_font)
                for ln in self._wrap_dialog_text(quest.description, body_font, inner_w))
            body_lines.append((
                f"Цель: {self._quest_goal_display_text(quest.quest_id)}",
                (134, 239, 172), body_font))
        elif ctx["kind"] == "turn_in" and quest is not None:
            body_lines.append((f"Задание выполнено: {quest.name}", (52, 211, 153), head_font))
            body_lines.extend(
                (ln, (255, 255, 255), body_font)
                for ln in self._wrap_dialog_text(quest.turn_in_text, body_font, inner_w))
        elif ctx["kind"] == "reminder" and quest is not None:
            body_lines.append((f"Задание: {quest.name}", accent, head_font))
            body_lines.extend(
                (ln, (255, 255, 255), body_font)
                for ln in self._wrap_dialog_text(quest.reminder_text, body_font, inner_w))
            body_lines.append((
                f"Цель: {self._quest_goal_display_text(quest.quest_id)}",
                (134, 239, 172), body_font))
        else:
            body_lines.extend(
                (ln, (255, 255, 255), body_font)
                for ln in self._wrap_dialog_text(
                    self._quest_dialog_flavor or npc.hover_text, body_font, inner_w))
        if ctx["kind"] in ("offer", "turn_in") and quest is not None:
            rew_lines.append(("Награда:", (180, 180, 200), body_font))
            rew_lines.extend(
                (f"• {ln}", (250, 204, 21), body_font)
                for ln in self._quest_reward_lines(quest.quest_id))

        body_h = sum(f.size(t)[1] + 4 for t, _c, f in body_lines)
        rew_h = (sum(f.size(t)[1] + 4 for t, _c, f in rew_lines) + 4) if rew_lines else 0
        section_gap = 10          # воздух вокруг разделителя
        btn_zone = QUEST_DIALOG_BTN_H + pad
        modal_h = (pad + QUEST_DIALOG_HEADER_H + section_gap + body_h
                   + (section_gap + rew_h if rew_lines else 0)
                   + btn_zone + 6)
        modal_h = max(QUEST_DIALOG_MIN_H, min(QUEST_DIALOG_MAX_H, modal_h))

        modal_x = (SCREEN_WIDTH - modal_w) // 2
        modal_y = (SCREEN_HEIGHT - modal_h) // 2

        # --- Рамка + шапка (аватар + имя + роль) --------------------------
        self._npc_window_frame(modal_x, modal_y, modal_w, modal_h, accent)
        avatar_path = self._npc_avatar_path(npc)
        raw_portrait = self._load_npc_raw(avatar_path)
        portrait = None
        if raw_portrait is not None:
            prw, prh = raw_portrait.get_size()
            pw = max(1, int(QUEST_DIALOG_PORTRAIT_SIZE * prw / max(1, prh)))
            portrait = self._su_image(avatar_path, pw, QUEST_DIALOG_PORTRAIT_SIZE)
        portrait_rect = pygame.Rect(modal_x + pad, modal_y + pad,
                                    QUEST_DIALOG_PORTRAIT_SIZE, QUEST_DIALOG_PORTRAIT_SIZE)
        pygame.draw.rect(self.screen, (40, 40, 50), portrait_rect, border_radius=6)
        pygame.draw.rect(self.screen, accent, portrait_rect, 1, border_radius=6)
        if portrait is not None:
            self.screen.blit(portrait, portrait.get_rect(center=portrait_rect.center))

        name_x = modal_x + pad + QUEST_DIALOG_PORTRAIT_SIZE + 12
        name_surf = name_font.render(npc.name, True, accent)
        self.screen.blit(name_surf, (name_x, modal_y + pad + 6))
        role_surf = body_font.render(npc.title, True, (180, 180, 200))
        self.screen.blit(role_surf, (name_x, modal_y + pad + 36))

        header_bottom = modal_y + pad + QUEST_DIALOG_HEADER_H - 4
        self._npc_window_divider(modal_x + pad, header_bottom, inner_w)

        # --- Секция ЗАДАНИЕ / описание ------------------------------------
        text_x = modal_x + inner_x
        text_y = header_bottom + section_gap
        for text, color, font in body_lines:
            self.screen.blit(font.render(text, True, color), (text_x, text_y))
            text_y += font.size(text)[1] + 4

        # --- Секция НАГРАДЫ (жёстко отделена) -----------------------------
        if rew_lines:
            rew_top = text_y + section_gap - 4
            self._npc_window_divider(modal_x + pad, rew_top, inner_w)
            text_y = rew_top + section_gap
            for text, color, font in rew_lines:
                self.screen.blit(font.render(text, True, color), (text_x, text_y))
                text_y += font.size(text)[1] + 4

        # --- Маленькие кнопки ----------------------------------------------
        btn_h = QUEST_DIALOG_BTN_H
        btn_gap = 10
        btn_y = modal_y + modal_h - btn_h - pad
        if ctx["kind"] == "offer" and quest is not None:
            accept_w = max(120, head_font.size("Принять задание")[0] + 26)
            close_w = max(96, head_font.size("Закрыть")[0] + 26)
            total_w = accept_w + close_w + btn_gap
            btn_x0 = modal_x + (modal_w - total_w) // 2
            self._npc_window_button(
                pygame.Rect(btn_x0, btn_y, accept_w, btn_h), "Принять задание",
                (52, 211, 153), (80, 240, 180), (20, 20, 20), "quest_accept",
                lambda q=quest.quest_id: self._quest_accept(q))
            self._npc_window_button(
                pygame.Rect(btn_x0 + accept_w + btn_gap, btn_y, close_w, btn_h),
                "Закрыть", (63, 63, 70), (80, 80, 90), (255, 255, 255),
                "quest_dialog_close", self._close_npc_dialog)
        elif ctx["kind"] == "turn_in" and quest is not None:
            claim_w = max(120, head_font.size("Получить награду")[0] + 26)
            close_w = max(96, head_font.size("Закрыть")[0] + 26)
            total_w = claim_w + close_w + btn_gap
            btn_x0 = modal_x + (modal_w - total_w) // 2
            self._npc_window_button(
                pygame.Rect(btn_x0, btn_y, claim_w, btn_h), "Получить награду",
                (234, 179, 8), (250, 204, 21), (20, 20, 20), "quest_turn_in",
                lambda q=quest.quest_id: self._quest_turn_in(q))
            self._npc_window_button(
                pygame.Rect(btn_x0 + claim_w + btn_gap, btn_y, close_w, btn_h),
                "Закрыть", (63, 63, 70), (80, 80, 90), (255, 255, 255),
                "quest_dialog_close", self._close_npc_dialog)
        else:
            close_w = max(96, head_font.size("Закрыть")[0] + 26)
            self._npc_window_button(
                pygame.Rect(modal_x + (modal_w - close_w) // 2, btn_y, close_w, btn_h),
                "Закрыть", (63, 63, 70), (80, 80, 90), (255, 255, 255),
                "quest_dialog_close", self._close_npc_dialog)
