"""LasNochesRendererMixin - Las Noches guardian scene + dialog modals.

Extracted verbatim from render_map.py during the Stage 96 mixin refactor.

Stage 153 — Hi-DPI: `_render_las_noches_scene` вызывается ВНУТРИ `_render_map`,
поэтому мигрирован вместе с MAP (дизайн-координаты + `_su`/`_su_font`/`_su_image`).
Диалоги (`_render_las_noches_dialog` и его окна) остались legacy — они рисуются
в слое немигрированных модалок (см. `pygame_ui._end_native_base_screen`).
"""
from __future__ import annotations

import pygame

from pockie_rpg.ui.animator import ClickRect


class LasNochesRendererMixin:
    """Renders Las Noches: guardian scene on the MAP + 2 dialog windows.

    Mixin: inherits ``self`` (screen, fonts, player, _click_rects,
    _mouse_pos, _las_noches_dialog, asset_manager) from the host PygameUI class.
    """

    def _render_las_noches_scene(self) -> None:
        """Render the Las Noches location: guardian NPC on the right edge + title.

        Per DEVELOPMENT_RULES §6: uses AssetManager for sprite loading (no
        direct pygame.image.load). The guardian is a static NPC (single idle
        frame) — click opens the dialog flow.

        Stage 92 — uses las_noches.png (user-provided sprite, not programmatically
        altered). Hover effect: sprite-contour glow (mask-based) instead of square.

        Stage 93 — title text moved above the guardian's head (not top-center).
        Title is larger + bold. Back button removed (user navigates via minimap).

        Stage 153 — Hi-DPI: спрайт стража масштабируется под текущее пространство
        рендера (кэш `_su_scaled`), геометрия — через `_su`. Дизайн-размеры
        считаются в 1280×720, как раньше.
        """
        from pockie_rpg.config import (
            EXTRACTED_DIR,
            LAS_NOCHES_GUARDIAN_FILENAME,
            LAS_NOCHES_GUARDIAN_FOLDER,
            LAS_NOCHES_GUARDIAN_SCALE,
            MAP_PANEL_HEIGHT,
            SCREEN_HEIGHT,
            SCREEN_WIDTH,
        )

        # Guardian sprite on the right edge.
        # Stage 92 — load las_noches.png directly (user-provided, not altered).
        # Stage 153 — загрузка через кэш (_su_image_raw_cache), без per-frame IO.
        guardian_path = str(EXTRACTED_DIR / LAS_NOCHES_GUARDIAN_FOLDER / LAS_NOCHES_GUARDIAN_FILENAME)
        raw_cache = getattr(self, "_su_image_raw_cache", None)
        if raw_cache is None:
            raw_cache = self._su_image_raw_cache = {}
        if guardian_path in raw_cache:
            guardian_surf = raw_cache[guardian_path]
        else:
            try:
                guardian_surf = pygame.image.load(guardian_path).convert_alpha()
            except Exception:
                guardian_surf = None
            raw_cache[guardian_path] = guardian_surf
        if guardian_surf is None:
            # Fallback to AssetManager motion sprite (uses 1.png).
            guardian_surf = self.asset_manager.get_motion_sprite(
                LAS_NOCHES_GUARDIAN_FOLDER, 1,
            )
        # Дизайн-размеры спрайта (как до Stage 153).
        gw, gh = guardian_surf.get_size()
        scale = LAS_NOCHES_GUARDIAN_SCALE
        sgw, sgh = int(gw * scale), int(gh * scale)
        # Финальная поверхность — в пространстве рендера (кэш по (ключ, размер)).
        scaled = self._su_scaled(f"__ln_guardian__:{guardian_path}", guardian_surf, sgw, sgh)
        nw, nh = scaled.get_size()
        # Position at right edge (Stage 93 — user-requested: x offset 0, y offset 60).
        guardian_x = SCREEN_WIDTH - sgw - 0
        guardian_y = SCREEN_HEIGHT - sgh - 60

        title_text = "Лас Ночес — страж ждёт тебя у входа в Башню"
        title_surf = self._su_font(18, True).render(title_text, True, (240, 230, 255))
        title_w_design = int(round(title_surf.get_width() / max(0.001, getattr(self, "_render_scale", 1.0))))
        title_h_design = int(round(title_surf.get_height() / max(0.001, getattr(self, "_render_scale", 1.0))))
        title_x = guardian_x + (sgw - title_w_design) // 2
        title_y = max(70 + MAP_PANEL_HEIGHT, guardian_y - title_h_design - 20)
        title_bg = self._su_rect(title_x - 12, title_y - 4, title_w_design + 24, title_h_design + 8)
        pygame.draw.rect(self.screen, (0, 0, 0), title_bg, border_radius=4)
        pygame.draw.rect(self.screen, (167, 139, 250), title_bg, self._su(1), border_radius=4)
        self.screen.blit(title_surf, (self._su(title_x), self._su(title_y)))

        shadow_w = int(sgw * 0.6)
        shadow_h = 20
        shadow_surf = pygame.Surface((self._su(shadow_w), self._su(shadow_h)), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surf, (0, 0, 0, 120),
                            (0, 0, self._su(shadow_w), self._su(shadow_h)))
        self.screen.blit(shadow_surf, (self._su(guardian_x + (sgw - shadow_w) // 2),
                                       self._su(guardian_y + sgh - 10)))
        self.screen.blit(scaled, (self._su(guardian_x), self._su(guardian_y)))

        guardian_rect = self._su_rect(guardian_x - 10, guardian_y - 10, sgw + 20, sgh + 20)
        guardian_hover = guardian_rect.collidepoint(self._mouse_pos)
        if guardian_hover:
            glow_color = (52, 211, 153, 120)
            pad = self._su(12)
            glow_surf = pygame.Surface((nw + pad * 2, nh + pad * 2), pygame.SRCALPHA)
            for dx, dy in [(-4, 0), (4, 0), (0, -4), (0, 4), (-3, -3), (3, -3), (-3, 3), (3, 3), (-5, 0), (5, 0), (0, -5), (0, 5)]:
                glow_surf.blit(scaled, (pad + self._su(dx), pad + self._su(dy)),
                               special_flags=pygame.BLEND_RGBA_ADD)
            tint = pygame.Surface(glow_surf.get_size(), pygame.SRCALPHA)
            tint.fill(glow_color)
            glow_surf.blit(tint, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            glow_surf.blit(scaled, (pad, pad), special_flags=pygame.BLEND_RGBA_SUB)
            self.screen.blit(glow_surf, (self._su(guardian_x) - pad, self._su(guardian_y) - pad))
            self.screen.blit(scaled, (self._su(guardian_x), self._su(guardian_y)))

            tip_text = "Ohhh, ты хочешь войти?"
            tip_surf = self._su_font(16, True).render(tip_text, True, (255, 255, 255))
            _s = max(0.001, getattr(self, "_render_scale", 1.0))
            tip_w = int(round(tip_surf.get_width() / _s)) + 24
            tip_h = int(round(tip_surf.get_height() / _s)) + 12
            bubble_x = guardian_x - tip_w - 20
            bubble_y = guardian_y + sgh // 2 - tip_h // 2
            if bubble_x < 10:
                bubble_x = 10

            bubble_rect = self._su_rect(bubble_x, bubble_y, tip_w, tip_h)
            pygame.draw.rect(self.screen, (30, 30, 35), bubble_rect, border_radius=8)
            pygame.draw.rect(self.screen, (52, 211, 153), bubble_rect, self._su(2), border_radius=8)

            tail_pts = [
                (self._su(bubble_x + tip_w), self._su(bubble_y + tip_h // 2 - 8)),
                (self._su(bubble_x + tip_w + 16), self._su(bubble_y + tip_h // 2)),
                (self._su(bubble_x + tip_w), self._su(bubble_y + tip_h // 2 + 8)),
            ]
            pygame.draw.polygon(self.screen, (30, 30, 35), tail_pts)
            pygame.draw.lines(self.screen, (52, 211, 153), False, tail_pts, self._su(2))

            self.screen.blit(tip_surf, (self._su(bubble_x + 12), self._su(bubble_y + 6)))

        self._click_rects.append(ClickRect(
            tag="las_noches_guardian",
            rect=guardian_rect,
            on_click=self._enter_las_noches_guardian,
        ))

    def _render_las_noches_dialog(self) -> None:
        """Render the Las Noches guardian dialog windows.

        Two stages:
          - "welcome": greeting + warning about Tower danger.
            Buttons: [Отмена] [Принять]
          - "shop_offer": explains the Tower Shop (buy items with stones).
            Buttons: [Магазин] [Войти в Башню]

        Stage 174 — окна переведены на ЕДИНУЮ систему окон NPC (общие рамка/
        разделители/маленькие кнопки из QuestRendererMixin: `_npc_window_*`).
        Высота ДИНАМИЧЕСКАЯ — по числу строк текста.

        Per user request: windows must NOT be see-through (solid background).
        """

        if self._las_noches_dialog == "welcome":
            self._render_las_noches_welcome_dialog()
        elif self._las_noches_dialog == "shop_offer":
            self._render_las_noches_shop_offer_dialog()

    def _ln_dialog_layout(self, text_lines: list[str],
                          accent: tuple[int, int, int],
                          extra_h: int = 0) -> tuple[int, int, int, int, int]:
        """Единая геометрия окна стража ЛН: (modal_x, modal_y, modal_w, modal_h,
        text_y_start). Считает высоту по строкам (динамическая высота Stage 174);
        extra_h — дополнительная высота контента сверх text_lines."""
        from pockie_rpg.config import (
            MODAL_CONTENT_PADDING,
            QUEST_DIALOG_HEADER_H,
            QUEST_DIALOG_MAX_H,
            QUEST_DIALOG_MIN_H,
            QUEST_DIALOG_W,
            SCREEN_HEIGHT,
            SCREEN_WIDTH,
        )
        pad = MODAL_CONTENT_PADDING
        modal_w = QUEST_DIALOG_W
        body_font = self.font_small
        body_h = sum(body_font.size(ln)[1] + 4 for ln in text_lines) + extra_h
        btn_zone = 28 + pad
        modal_h = (pad + QUEST_DIALOG_HEADER_H + 10 + body_h + btn_zone + 6)
        modal_h = max(QUEST_DIALOG_MIN_H, min(QUEST_DIALOG_MAX_H, modal_h))
        modal_x = (SCREEN_WIDTH - modal_w) // 2
        modal_y = (SCREEN_HEIGHT - modal_h) // 2
        header_bottom = modal_y + pad + QUEST_DIALOG_HEADER_H - 4
        return modal_x, modal_y, modal_w, modal_h, header_bottom + 10

    def _render_ln_dialog_header(self, modal_x: int, modal_y: int, modal_w: int,
                                 modal_h: int, accent: tuple[int, int, int]) -> None:
        """Шапка единого окна стража ЛН: рамка + портрет + имя + роль + линия."""
        from pockie_rpg.config import (
            EXTRACTED_DIR,
            LAS_NOCHES_GUARDIAN_FILENAME,
            LAS_NOCHES_GUARDIAN_FOLDER,
            MODAL_CONTENT_PADDING,
            QUEST_DIALOG_HEADER_H,
            QUEST_DIALOG_PORTRAIT_SIZE,
        )
        pad = MODAL_CONTENT_PADDING
        self._npc_window_frame(modal_x, modal_y, modal_w, modal_h, accent)

        # Stage 92 — use las_noches.png for the portrait (кэш raw+smoothscale).
        portrait_path = str(EXTRACTED_DIR / LAS_NOCHES_GUARDIAN_FOLDER / LAS_NOCHES_GUARDIAN_FILENAME)
        raw_cache = getattr(self, "_su_image_raw_cache", None)
        if raw_cache is None:
            raw_cache = self._su_image_raw_cache = {}
        if portrait_path in raw_cache:
            guardian_surf = raw_cache[portrait_path]
        else:
            try:
                guardian_surf = pygame.image.load(portrait_path).convert_alpha()
            except Exception:
                guardian_surf = None
            raw_cache[portrait_path] = guardian_surf
        if guardian_surf is None:
            guardian_surf = self.asset_manager.get_motion_sprite(LAS_NOCHES_GUARDIAN_FOLDER, 1)
        portrait = self._su_scaled(
            f"__ln_portrait__:{portrait_path}", guardian_surf,
            QUEST_DIALOG_PORTRAIT_SIZE, QUEST_DIALOG_PORTRAIT_SIZE)
        portrait_rect = pygame.Rect(modal_x + pad, modal_y + pad,
                                    QUEST_DIALOG_PORTRAIT_SIZE, QUEST_DIALOG_PORTRAIT_SIZE)
        pygame.draw.rect(self.screen, (40, 40, 50), portrait_rect, border_radius=6)
        pygame.draw.rect(self.screen, accent, portrait_rect, 1, border_radius=6)
        self.screen.blit(portrait, portrait.get_rect(center=portrait_rect.center))

        name_x = modal_x + pad + QUEST_DIALOG_PORTRAIT_SIZE + 12
        name_surf = self.font_button.render("Страж Лас Ночеса", True, accent)
        self.screen.blit(name_surf, (name_x, modal_y + pad + 6))
        role_surf = self.font_small.render("Хранитель Башни", True, (180, 180, 200))
        self.screen.blit(role_surf, (name_x, modal_y + pad + 36))

        header_bottom = modal_y + pad + QUEST_DIALOG_HEADER_H - 4
        self._npc_window_divider(modal_x + pad, header_bottom, modal_w - pad * 2)

    def _render_las_noches_welcome_dialog(self) -> None:
        """First dialog window: greeting + warning + Cancel/Accept.

        Stage 174 — единый стиль окон NPC (рамка/секции/маленькие кнопки),
        динамическая высота по строкам.
        """
        from pockie_rpg.config import MODAL_CONTENT_PADDING, QUEST_DIALOG_BTN_H

        accent = (167, 139, 250)
        text_lines = [
            "Добро пожаловать, странник.",
            "",
            "Ты ступил на пески Лас Ночеса —",
            "последнего рубежа перед Башней.",
            "",
            "Башня опасна. На каждом десятом",
            "этаже тебя ждёт босс. Многие воины",
            "восходили туда — немногие вернулись.",
            "",
            "Готов ли ты принять вызов?",
        ]
        modal_x, modal_y, modal_w, modal_h, text_y = self._ln_dialog_layout(
            text_lines, accent)
        self._render_ln_dialog_header(modal_x, modal_y, modal_w, modal_h, accent)

        pad = MODAL_CONTENT_PADDING
        for line in text_lines:
            if line:
                line_surf = self.font_small.render(line, True, (255, 255, 255))
                self.screen.blit(line_surf, (modal_x + pad, text_y))
            text_y += self.font_small.size(line)[1] + 4

        # Маленькие кнопки: [Отмена] [Принять] (Stage 174 — единый стиль).
        btn_h = QUEST_DIALOG_BTN_H
        btn_gap = 10
        btn_w = 120
        total_btn_w = 2 * btn_w + btn_gap
        btn_x0 = modal_x + (modal_w - total_btn_w) // 2
        btn_y = modal_y + modal_h - btn_h - pad
        self._npc_window_button(
            pygame.Rect(btn_x0, btn_y, btn_w, btn_h), "Отмена",
            (180, 30, 30), (220, 38, 38), (255, 255, 255),
            "ln_cancel", self._las_noches_cancel)
        self._npc_window_button(
            pygame.Rect(btn_x0 + btn_w + btn_gap, btn_y, btn_w, btn_h), "Принять",
            (52, 211, 153), (80, 240, 180), (20, 20, 20),
            "ln_accept", self._las_noches_accept)

    def _render_las_noches_shop_offer_dialog(self) -> None:
        """Second dialog window: Tower Shop explanation + Shop/Enter buttons.

        Stage 174 — единый стиль окон NPC, динамическая высота.
        """
        from pockie_rpg.config import MODAL_CONTENT_PADDING, QUEST_DIALOG_BTN_H

        accent = (234, 179, 8)
        shards_text = f"◈ {self.player.tower_shards} осколков"
        text_lines = [
            "Внутри Башни ты соберёшь осколки —",
            "валюту, которую нельзя добыть иначе.",
            "",
            "За осколки ты можешь купить у меня:",
            "  • материалы 5 стихий (огонь, лёд,",
            "    молния, тень, древнее ядро)",
            "  • зелья и свитки (скоро)",
            "  • фрагменты костюмов (скоро)",
            "",
            "Чем выше этаж — тем больше осколков.",
            "Боссы каждые 10 этажей дают bonus.",
            "",
            "Готов войти или сначала заглянешь",
            "в магазин?",
        ]
        modal_x, modal_y, modal_w, modal_h, text_y = self._ln_dialog_layout(
            text_lines, accent, extra_h=28)
        self._render_ln_dialog_header(modal_x, modal_y, modal_w, modal_h, accent)

        pad = MODAL_CONTENT_PADDING
        # Баланс осколков — первая строка тела (акцентный цвет; extra_h учтён
        # в высоте окна).
        shards_surf = self.font_banner.render(shards_text, True, (167, 139, 250))
        self.screen.blit(shards_surf, (modal_x + pad, text_y))
        text_y += self.font_banner.size(shards_text)[1] + 6
        for line in text_lines:
            if line:
                line_surf = self.font_small.render(line, True, (255, 255, 255))
                self.screen.blit(line_surf, (modal_x + pad, text_y))
            text_y += self.font_small.size(line)[1] + 4

        # Маленькие кнопки: [← Назад] [Магазин] [Войти в Башню].
        btn_h = QUEST_DIALOG_BTN_H
        btn_gap = 10
        btn_w = 132
        total_btn_w = 3 * btn_w + 2 * btn_gap
        btn_x0 = modal_x + (modal_w - total_btn_w) // 2
        btn_y = modal_y + modal_h - btn_h - pad
        self._npc_window_button(
            pygame.Rect(btn_x0, btn_y, btn_w, btn_h), "← Назад",
            (63, 63, 70), (80, 80, 90), (255, 255, 255),
            "ln_back", self._las_noches_back)
        self._npc_window_button(
            pygame.Rect(btn_x0 + btn_w + btn_gap, btn_y, btn_w, btn_h), "Магазин",
            (234, 179, 8), (250, 204, 21), (20, 20, 20),
            "ln_shop", self._las_noches_open_shop)
        self._npc_window_button(
            pygame.Rect(btn_x0 + 2 * (btn_w + btn_gap), btn_y, btn_w, btn_h),
            "Войти в Башню", (52, 211, 153), (80, 240, 180), (20, 20, 20),
            "ln_enter_tower", self._las_noches_enter_tower)
