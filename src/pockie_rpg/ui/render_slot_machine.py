"""SlotMachineRendererMixin — слот-машина «3 лица → бой» (Stage 133/134).

Modal UI for the Location 1 slot machine: roll 3 random mob faces (spin
animation ~2s, reels stop left-to-right), then fight them in 3 sequential
1v1 battles (HP/MP carry over, no regen). Battle chaining lives in
pygame_ui.py (_enter_gauntlet_battle / _finish_gauntlet_round); this mixin
only renders and registers clicks.

Stage 163 — история прокруток УДАЛЕНА полностью (окно + данные + логика
записи); окно сужено 560×560 → 420×360.
Stage 167 — тексты удалены (подзаголовок под названием и заметки под
кнопкой «Крутить» — запрос пользователя), окно ниже: 420×260; ДО прокрутки
в барабанах видны аватарки врагов из пула (вместо «?»).
"""
from __future__ import annotations

import pygame

from pockie_rpg.config import (
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)
from pockie_rpg.ui.animator import ClickRect

_SLOT_GOLD = (234, 179, 8)
_SLOT_PANEL_BG = (20, 20, 24)
_SLOT_CELL_BG = (39, 39, 44)
_SLOT_CELL_BORDER = (63, 63, 70)
_SLOT_TEXT_DIM = (161, 161, 170)


class SlotMachineRendererMixin:
    """Renders the slot machine modal + the gauntlet result modal."""

    def _render_slot_machine_modal(self) -> None:
        """Stage 133/134 — roll modal: 3 барабана (анимация) + кнопка.

        Stage 163 — история прокруток удалена (окно стало ниже/уже).
        Stage 167 — без подзаголовка и заметок; до прокрутки — аватарки
        врагов (нейтральная «заглушка» из пула вместо вопросиков).
        """
        modal_w = 420
        modal_h = 260
        modal_x = (SCREEN_WIDTH - modal_w) // 2
        modal_y = (SCREEN_HEIGHT - modal_h) // 2

        # Stage 165 — подложки больше НЕТ (блюр/затемнение давали «резкую
        # вспышку» при открытии): окно рисуется поверх НЕИЗМЕННОЙ живой сцены
        # (как «Карта мира»/магазин).

        modal_rect = pygame.Rect(modal_x, modal_y, modal_w, modal_h)
        pygame.draw.rect(self.screen, _SLOT_PANEL_BG, modal_rect, border_radius=10)
        pygame.draw.rect(self.screen, _SLOT_GOLD, pygame.Rect(modal_x, modal_y, modal_w, 6), border_radius=3)

        title_surf = self.font_title.render("Слот-машина", True, _SLOT_GOLD)
        # Stage 164 — заголовок по ЦЕНТРУ окна (как во всех окнах игры).
        self.screen.blit(title_surf,
                         title_surf.get_rect(midtop=(modal_x + modal_w // 2,
                                                     modal_y + 14)))

        close_rect = pygame.Rect(modal_x + modal_w - 40, modal_y + 12, 28, 28)
        close_hover = close_rect.collidepoint(self._mouse_pos)
        pygame.draw.rect(self.screen, (200, 30, 30) if close_hover else (150, 20, 20), close_rect, border_radius=6)
        x_surf = self.font_button.render("×", True, (255, 255, 255))
        self.screen.blit(x_surf, x_surf.get_rect(center=close_rect.center))
        self._click_rects.append(ClickRect(tag="close_slot_machine", rect=close_rect, on_click=self._close_slot_machine_modal))

        cell = 96
        gap = 24
        row_w = 3 * cell + 2 * gap
        cell_x0 = modal_x + (modal_w - row_w) // 2
        cell_y = modal_y + 64
        idle_faces = getattr(self, "_slot_idle_faces", None) or []
        for i in range(3):
            rect = pygame.Rect(cell_x0 + i * (cell + gap), cell_y, cell, cell)
            pygame.draw.rect(self.screen, _SLOT_CELL_BG, rect, border_radius=8)
            face_id = None
            if self._slot_spin_active and i < len(self._slot_spin_shown):
                face_id = self._slot_spin_shown[i]
            elif self._slot_rolled and i < len(self._slot_faces):
                face_id = self._slot_faces[i]
            if face_id is None and i < len(idle_faces):
                face_id = idle_faces[i]
            if face_id is not None:
                avatar = self.asset_manager.get_enemy_avatar(face_id, cell - 12)
                self.screen.blit(avatar, avatar.get_rect(center=rect.center))
                border = _SLOT_GOLD if (self._slot_rolled or self._slot_spin_active) else _SLOT_CELL_BORDER
            else:
                q_surf = self.font_skills_btn_letter.render("?", True, (113, 113, 122))
                self.screen.blit(q_surf, q_surf.get_rect(center=rect.center))
                border = _SLOT_CELL_BORDER
            pygame.draw.rect(self.screen, border, rect, 2, border_radius=8)

        btn_w = 220
        btn_h = 48
        btn_rect = pygame.Rect(modal_x + (modal_w - btn_w) // 2, modal_y + 186, btn_w, btn_h)
        cooldown = self._slot_cooldown_remaining()
        hover = btn_rect.collidepoint(self._mouse_pos) and not self._slot_spin_active
        if self._slot_spin_active:
            label = "Крутит…"
            enabled = False
            btn_bg = (40, 40, 45)
        elif self._slot_rolled:
            label = "В бой!"
            enabled = True
            btn_bg = (22, 130, 90) if hover else (20, 110, 76)
        elif cooldown > 0.0:
            label = f"Крутить ({int(cooldown) + 1}с)"
            enabled = False
            btn_bg = (40, 40, 45)
        else:
            label = "Крутить"
            enabled = True
            btn_bg = (160, 120, 10) if hover else (130, 98, 8)
        pygame.draw.rect(self.screen, btn_bg, btn_rect, border_radius=8)
        pygame.draw.rect(self.screen, _SLOT_GOLD if enabled else _SLOT_CELL_BORDER, btn_rect, 2, border_radius=8)
        btn_surf = self.font_button.render(label, True, (255, 255, 255) if enabled else _SLOT_TEXT_DIM)
        self.screen.blit(btn_surf, btn_surf.get_rect(center=btn_rect.center))
        if self._slot_rolled and not self._slot_spin_active:
            self._click_rects.append(ClickRect(tag="slot_start", rect=btn_rect, on_click=self._start_slot_gauntlet))
        elif cooldown <= 0.0 and not self._slot_spin_active and not self._slot_rolled:
            self._click_rects.append(ClickRect(tag="slot_roll", rect=btn_rect, on_click=self._slot_machine_roll))
        # Stage 167 — заметки «Награда…» / «Бонус…» УДАЛЕНЫ (запрос
        # пользователя): окно заканчивается кнопкой.

    def _render_slot_result(self) -> None:
        """Stage 133 — gauntlet result modal (после 3 боёв или смерти)."""
        result = self._slot_result
        if result is None:
            return
        modal_w = 480
        modal_h = 380
        modal_x = (SCREEN_WIDTH - modal_w) // 2
        modal_y = (SCREEN_HEIGHT - modal_h) // 2

        # Stage 165 — подложки больше НЕТ: окно результата поверх живой сцены.

        modal_rect = pygame.Rect(modal_x, modal_y, modal_w, modal_h)
        pygame.draw.rect(self.screen, _SLOT_PANEL_BG, modal_rect, border_radius=10)
        pygame.draw.rect(
            self.screen,
            _SLOT_GOLD if result["defeated"] == result["total"] else (150, 30, 30),
            pygame.Rect(modal_x, modal_y, modal_w, 6),
            border_radius=3,
        )

        if result["defeated"] == result["total"]:
            title = "Все три побеждены!"
            title_color = _SLOT_GOLD
        elif result["defeated"] > 0:
            title = f"Побеждено: {result['defeated']} из {result['total']}"
            title_color = (255, 255, 255)
        else:
            title = "Поражение в первом же бою"
            title_color = (220, 80, 80)
        title_surf = self.font_title.render(title, True, title_color)
        self.screen.blit(title_surf, (modal_x + (modal_w - title_surf.get_width()) // 2, modal_y + 20))

        face_size = 64
        gap = 20
        row_w = result["total"] * face_size + (result["total"] - 1) * gap
        face_x0 = modal_x + (modal_w - row_w) // 2
        face_y = modal_y + 78
        for i, face_id in enumerate(result["faces"]):
            rect = pygame.Rect(face_x0 + i * (face_size + gap), face_y, face_size, face_size)
            pygame.draw.rect(self.screen, _SLOT_CELL_BG, rect, border_radius=6)
            avatar = self.asset_manager.get_enemy_avatar(face_id, face_size - 8)
            self.screen.blit(avatar, avatar.get_rect(center=rect.center))
            if i < result["defeated"]:
                border = _SLOT_GOLD
            else:
                border = (150, 30, 30)
            pygame.draw.rect(self.screen, border, rect, 2, border_radius=6)
            mark = "✓" if i < result["defeated"] else "✗"
            mark_color = _SLOT_GOLD if i < result["defeated"] else (220, 80, 80)
            mark_surf = self.font_button.render(mark, True, mark_color)
            self.screen.blit(mark_surf, mark_surf.get_rect(center=(rect.centerx, rect.bottom + 14)))

        lines = [
            f"Золото: +{result['gold']}",
            f"Опыт: +{result['xp']}",
        ]
        if result.get("perfect"):
            lines.append("Бонус ×1.5 за 3/3!")
        if result["leveled_up"]:
            lines.append(f"НОВЫЙ УРОВЕНЬ: {result['new_level']}!")
        line_y = face_y + face_size + 44
        for line in lines:
            color = (250, 204, 21) if line.startswith("Бонус") else (255, 255, 255)
            surf = self.font_button.render(line, True, color)
            self.screen.blit(surf, (modal_x + (modal_w - surf.get_width()) // 2, line_y))
            line_y += 26

        btn_w = 160
        btn_h = 44
        btn_rect = pygame.Rect(modal_x + (modal_w - btn_w) // 2, modal_y + modal_h - 62, btn_w, btn_h)
        hover = btn_rect.collidepoint(self._mouse_pos)
        pygame.draw.rect(self.screen, (22, 130, 90) if hover else (20, 110, 76), btn_rect, border_radius=8)
        ok_surf = self.font_button.render("OK", True, (255, 255, 255))
        self.screen.blit(ok_surf, ok_surf.get_rect(center=btn_rect.center))
        self._click_rects.append(ClickRect(tag="slot_result_ok", rect=btn_rect, on_click=self._close_slot_result))
