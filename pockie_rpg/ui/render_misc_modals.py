"""MiscModalsRendererMixin - Titles + Arena + Daily Quest modal rendering.

Extracted verbatim from render_map.py during the Stage 96 mixin refactor.
"""
from __future__ import annotations

import random

import pygame

from pockie_rpg.config import (
    MAP_CARD_HOVER_SHADOW_INSET,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)
from pockie_rpg.ui.animator import ClickRect


class MiscModalsRendererMixin:
    """Renders miscellaneous modals: Titles list + Arena board + Daily Quest tracker.

    Mixin: inherits ``self`` (screen, fonts, player, _click_rects,
    _mouse_pos, asset_manager) from the host PygameUI class.
    """

    _arena_cards: list[dict[str, int | str]] | None = None

    def _ensure_arena_cards(self) -> list[dict[str, int | str]]:
        """Stage 170 — карточки арены генерируются ОДИН раз локальным Random(42)
        (раньше random.seed(42) сеял ГЛОБАЛЬНЫЙ random каждый кадр рендера и
        портил боевые броски combat/damage.py + combat/fight.py)."""
        if self._arena_cards is None:
            rng = random.Random(42)
            bot_names = [
                "Тень", "Ронин", "Страж", "Призрак", "Берсерк",
                "Монах", "Самурай", "Ниндзя", "Воин", "Охотник",
                "Ассасин", "Паладин", "Дракон", "Ворон", "Феникс",
            ]
            self._arena_cards = [
                {
                    "name": bot_names[i] if i < len(bot_names) else f"Бот {i + 1}",
                    "lvl": rng.randint(5, 50),
                    "rank": rng.randint(1, 100),
                }
                for i in range(15)
            ]
        return self._arena_cards

    def _render_titles_modal(self) -> None:
        """Stage 70 — render the Titles modal with all 12 titles.

        Each title is a row showing: name + tier + stat bonuses + Activate button.
        The active title is highlighted with a golden border.
        Clicking Activate toggles the title (activate if inactive, deactivate if active).

        Stage 156 — НАТИВНЫЙ рендер (раньше буфер 1280×720 → растяжение ×2 =
        «мыло» + мелкий текст): все координаты через self._su(), шрифты через
        self._su_font(). Фикс вёрстки: имя/тир/статы в 2 колонки с обрезкой
        «…» — текст больше не наезжает и не вылезает за кнопки.
        """
        from pockie_rpg.data.titles_db import get_all_titles, get_title

        su = self._su
        modal_w = 560
        modal_h = 580
        # Stage 157 — перетаскиваемое окно (общий реестр, persist в сейве).
        modal_x, modal_y = self._window_pos("titles", modal_w, modal_h)
        modal_y = max(64, modal_y)

        # Stage 156 — затемнение нативного размера (не квадрат-подложка).
        self.screen.blit(self._su_overlay(140), (0, 0))

        modal_r = pygame.Rect(su(modal_x), su(modal_y), su(modal_w), su(modal_h))
        pygame.draw.rect(self.screen, (20, 20, 24), modal_r, border_radius=10)
        pygame.draw.rect(self.screen, (234, 179, 8),
                        (modal_r.x, modal_r.y, modal_r.w, su(6)), border_radius=3)

        # Stage 157/158 — общая шапка (drag + persist) + выносной крестик.
        self._render_window_titlebar(
            "titles", modal_r, "Звания",
            (234, 179, 8), True, open_attr="_titles_modal_open",
            on_close=self._close_titles_modal,
        )

        # Stage 158 — внутренняя close-кнопка УДАЛЁНА (выносной крестик
        # рисует шапка справа от окна).

        # Active title indicator.
        active_title_id = getattr(self.player, "active_title", None)
        active_title = get_title(active_title_id) if active_title_id else None
        if active_title:
            active_text = f"Активно: {active_title['name']}"
            active_surf = self._su_font(16, bold=True).render(active_text, True, (234, 179, 8))
        else:
            active_surf = self._su_font(16, bold=True).render("Активно: Нет звания",
                                                              True, (113, 113, 122))
        self.screen.blit(active_surf, (modal_r.x + su(16), modal_r.y + su(48)))

        # List of titles.
        from pockie_rpg.config import STAT_LABEL_RU as stat_label_map

        list_y = modal_r.y + su(84)
        row_h = su(38)
        list_w = modal_r.w - su(24)
        all_titles = get_all_titles()
        btn_w = su(96)
        btn_h = su(26)
        name_col_w = su(150)
        stats_col_x = su(170)

        for i, title in enumerate(all_titles):
            row_rect = pygame.Rect(modal_r.x + su(12),
                                   list_y + i * row_h, list_w, row_h - su(4))
            if row_rect.bottom > modal_r.bottom - su(10):
                break
            is_active = (title["id"] == active_title_id)
            row_hover = row_rect.collidepoint(self._mouse_pos)
            if is_active:
                bg = (60, 50, 10)
                border = (234, 179, 8)
            elif row_hover:
                bg = (45, 45, 50)
                border = (100, 100, 110)
            else:
                bg = (35, 35, 40)
                border = (60, 60, 65)
            pygame.draw.rect(self.screen, bg, row_rect, border_radius=6)
            pygame.draw.rect(self.screen, border, row_rect,
                             su(2) if is_active else 1, border_radius=6)

            # Колонка 1: имя (крупно) + тир (мелко, под именем).
            name_font = self._su_font(15, bold=True)
            name_text = f"{title['name']}"
            name_surf = name_font.render(name_text, True,
                                         (255, 255, 255) if is_active else (200, 200, 205))
            # Stage 156 — обрезка «…»: имя не наезжает на колонку статов.
            if name_surf.get_width() > name_col_w:
                while name_surf.get_width() > name_col_w - su(10) and len(name_text) > 3:
                    name_text = name_text[:-1]
                    name_surf = name_font.render(name_text + "…", True,
                                                 (255, 255, 255) if is_active else (200, 200, 205))
            self.screen.blit(name_surf, (row_rect.x + su(8), row_rect.y + su(3)))
            tier_surf = self._su_font(11).render(f"Тир {title['tier']}",
                                                 True, (180, 180, 200))
            self.screen.blit(tier_surf, (row_rect.x + su(8), row_rect.y + su(21)))

            # Колонка 2: статы (до кнопки, обрезка «…» при 3+ строках).
            stats = title.get("stats", {})
            stat_parts = []
            for sk, val in stats.items():
                lbl = stat_label_map.get(sk, sk)
                stat_parts.append(f"+{val} {lbl}")
            btn_left = row_rect.right - btn_w - su(8)
            stats_max_w = btn_left - (row_rect.x + stats_col_x) - su(8)
            stat_font = self._su_font(12)
            stat_text = " · ".join(stat_parts)
            stat_surf = stat_font.render(stat_text, True, (80, 220, 100))
            if stat_surf.get_width() > stats_max_w:
                while stat_surf.get_width() > stats_max_w - su(10) and len(stat_text) > 3:
                    stat_text = stat_text[:-1]
                    stat_surf = stat_font.render(stat_text + "…", True, (80, 220, 100))
            self.screen.blit(stat_surf, (row_rect.x + stats_col_x,
                                         stat_surf.get_rect(
                                             centery=row_rect.centery).y))

            # Кнопка Активировать/Снять (текст влезает: «Активировать» 12pt
            # в кнопке 96×26 дизайн — замер по шрифту).
            btn_rect = pygame.Rect(btn_left, row_rect.y + su(5), btn_w, btn_h)
            btn_hover = btn_rect.collidepoint(self._mouse_pos)
            if is_active:
                btn_bg = (200, 30, 30) if btn_hover else (150, 20, 20)
                btn_fg = (255, 255, 255)
                btn_text = "Снять"
            else:
                btn_bg = (234, 179, 8) if btn_hover else (180, 83, 9)
                btn_fg = (20, 20, 20) if btn_hover else (255, 255, 255)
                btn_text = "Активировать"
            pygame.draw.rect(self.screen, btn_bg, btn_rect, border_radius=4)
            btn_surf = self._su_font(12).render(btn_text, True, btn_fg)
            # Stage 156 — страховка: если текст шире кнопки, ужимаем шрифт.
            if btn_surf.get_width() > btn_w - su(8):
                fs = 12
                while btn_surf.get_width() > btn_w - su(8) and fs > 8:
                    fs -= 1
                    btn_surf = self._su_font(fs).render(btn_text, True, btn_fg)
            self.screen.blit(btn_surf, btn_surf.get_rect(center=btn_rect.center))
            _tid = title["id"]
            self._click_rects.append(ClickRect(
                tag=f"activate_title_{title['id']}",
                rect=btn_rect,
                on_click=lambda t=_tid: self._activate_title(t),
            ))

    def _render_arena(self) -> None:
        """Stage 59 — render the Arena location."""
        # Arena background.
        try:
            bg = self.asset_manager.get_background("fightbg_3101.jpg")
            self.screen.blit(bg, (0, 0))
        except Exception:
            pygame.draw.rect(self.screen, (30, 30, 35), (0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))

        overlay = self.asset_manager.get_overlay(80)
        self.screen.blit(overlay, (0, 0))

        self._click_rects = []

        # Top panel: rank + battles left.
        panel_rect = pygame.Rect(0, 0, SCREEN_WIDTH, 64)
        pygame.draw.rect(self.screen, (20, 20, 24), panel_rect)
        pygame.draw.rect(self.screen, (234, 179, 8), pygame.Rect(0, 0, SCREEN_WIDTH, 4))

        rank_text = "Ваше место: 42"  # placeholder
        rank_surf = self.font_button.render(rank_text, True, (234, 179, 8))
        self.screen.blit(rank_surf, (20, 20))

        battles_text = "Доступно боев: 12/15"  # placeholder
        battles_surf = self.font_button.render(battles_text, True, (255, 255, 255))
        self.screen.blit(battles_surf, (SCREEN_WIDTH - battles_surf.get_width() - 20, 20))

        # Center: 3 rows x 5 columns = 15 opponent cards.
        card_w = 140
        card_h = 140
        gap_x = 8
        gap_y = 8
        cols = 5
        total_w = cols * card_w + (cols - 1) * gap_x
        x0 = (SCREEN_WIDTH - total_w) // 2
        y0 = 80

        arena_cards = self._ensure_arena_cards()
        for i in range(15):
            row = i // cols
            col = i % cols
            cx = x0 + col * (card_w + gap_x)
            cy = y0 + row * (card_h + gap_y)
            card_rect = pygame.Rect(cx, cy, card_w, card_h)
            hover = card_rect.collidepoint(self._mouse_pos)
            # Stage 87 — outer drop shadow on hover.
            if hover:
                shadow_inset = MAP_CARD_HOVER_SHADOW_INSET
                shadow_rect = pygame.Rect(
                    cx - shadow_inset, cy - shadow_inset,
                    card_w + shadow_inset * 2, card_h + shadow_inset * 2,
                )
                pygame.draw.rect(self.screen, (10, 10, 12), shadow_rect, border_radius=10)
            pygame.draw.rect(self.screen, (40, 40, 45) if not hover else (50, 50, 55), card_rect, border_radius=8)
            pygame.draw.rect(self.screen, (234, 179, 8) if hover else (80, 80, 85), card_rect, 2 if hover else 1, border_radius=8)

            # Avatar (procedural circle).
            pygame.draw.circle(self.screen, (60, 60, 70), (cx + card_w // 2, cy + 24), 18)
            pygame.draw.circle(self.screen, (234, 179, 8), (cx + card_w // 2, cy + 24), 18, 2)

            card = arena_cards[i]
            name = str(card["name"])
            name_surf = self.font_small.render(name, True, (255, 255, 255))
            self.screen.blit(name_surf, name_surf.get_rect(center=(cx + card_w // 2, cy + 50)))

            lvl = int(card["lvl"])
            lvl_surf = self.font_small.render(f"Ур. {lvl}", True, (234, 179, 8))
            self.screen.blit(lvl_surf, lvl_surf.get_rect(center=(cx + card_w // 2, cy + 68)))

            rank = int(card["rank"])
            rank_surf = self.font_small.render(f"Ранг: {rank}", True, (180, 180, 200))
            self.screen.blit(rank_surf, rank_surf.get_rect(center=(cx + card_w // 2, cy + 84)))

            # Challenge button.
            btn_w = 80
            btn_h = 24
            btn_rect = pygame.Rect(cx + (card_w - btn_w) // 2, cy + card_h - btn_h - 8, btn_w, btn_h)
            btn_hover = btn_rect.collidepoint(self._mouse_pos)
            bg_col = (234, 179, 8) if btn_hover else (180, 83, 9)
            pygame.draw.rect(self.screen, bg_col, btn_rect, border_radius=6)
            challenge_text = self.font_small.render("Вызов", True, (20, 20, 20) if btn_hover else (255, 255, 255))
            self.screen.blit(challenge_text, challenge_text.get_rect(center=btn_rect.center))
            # Note: challenge button is visual placeholder for now.

        # Bottom: back button + reward button (raised above bottom bar).
        back_w = 160
        back_h = 44
        back_x = 20
        back_y = SCREEN_HEIGHT - 130
        back_rect = pygame.Rect(back_x, back_y, back_w, back_h)
        back_hover = back_rect.collidepoint(self._mouse_pos)
        pygame.draw.rect(self.screen, (80, 80, 85) if back_hover else (50, 50, 55), back_rect, border_radius=8)
        back_text = self.font_button.render("← Назад", True, (255, 255, 255))
        self.screen.blit(back_text, back_text.get_rect(center=back_rect.center))
        self._click_rects.append(ClickRect(tag="exit_arena", rect=back_rect, on_click=self._exit_arena))

        reward_w = 260
        reward_h = 44
        reward_x = SCREEN_WIDTH - reward_w - 20
        reward_y = back_y
        reward_rect = pygame.Rect(reward_x, reward_y, reward_w, reward_h)
        reward_hover = reward_rect.collidepoint(self._mouse_pos)
        pygame.draw.rect(self.screen, (234, 179, 8) if reward_hover else (180, 83, 9), reward_rect, border_radius=8)
        reward_text = self.font_button.render("Забрать награду за ранг", True, (20, 20, 20) if reward_hover else (255, 255, 255))
        self.screen.blit(reward_text, reward_text.get_rect(center=reward_rect.center))
        # Visual placeholder for reward button.

    def _render_daily_quest_modal(self) -> None:
        """Stage 95 — render the Daily Quest tracker modal."""
        from pockie_rpg.config import (
            MODAL_CONTENT_PADDING,
            SCREEN_HEIGHT,
            SCREEN_WIDTH,
        )
        from pockie_rpg.data.daily_quests import DAILY_QUEST_ORDER, DAILY_QUESTS

        pad = MODAL_CONTENT_PADDING
        modal_w = 480
        modal_h = 440
        modal_x = (SCREEN_WIDTH - modal_w) // 2
        modal_y = (SCREEN_HEIGHT - modal_h) // 2

        # Solid modal background.
        pygame.draw.rect(self.screen, (24, 24, 27), (modal_x, modal_y, modal_w, modal_h), border_radius=12)
        pygame.draw.rect(self.screen, (234, 179, 8), (modal_x, modal_y, modal_w, modal_h), 2, border_radius=12)
        pygame.draw.rect(self.screen, (234, 179, 8), (modal_x, modal_y, modal_w, 6), border_radius=3)

        # Title.
        title = self.font_title.render("Дневные задания", True, (234, 179, 8))
        self.screen.blit(title, title.get_rect(center=(modal_x + modal_w // 2, modal_y + 36)))

        # Quest rows.
        row_h = 70
        row_y = modal_y + 70
        for quest_id in DAILY_QUEST_ORDER:
            quest = DAILY_QUESTS.get(quest_id)
            if quest is None:
                continue
            row_rect = pygame.Rect(modal_x + pad, row_y, modal_w - 2 * pad, row_h - 8)
            hover = row_rect.collidepoint(self._mouse_pos)
            # Row background.
            pygame.draw.rect(self.screen, (39, 39, 42) if not hover else (50, 50, 55), row_rect, border_radius=6)
            border_col = (234, 179, 8) if hover else (63, 63, 70)
            pygame.draw.rect(self.screen, border_col, row_rect, 1, border_radius=6)

            # Quest name + description.
            name_surf = self.font_button.render(quest.name, True, (255, 255, 255))
            self.screen.blit(name_surf, (row_rect.x + 12, row_rect.y + 4))
            desc_surf = self.font_small.render(quest.description, True, (180, 180, 200))
            self.screen.blit(desc_surf, (row_rect.x + 12, row_rect.y + 28))

            # Progress or claim button.
            progress = self.player.daily_quest_progress.get(quest_id, 0)
            is_complete = progress >= quest.target
            is_claimed = quest_id in self.player.daily_quest_claimed

            if is_claimed:
                # Already claimed — show "Получено".
                claim_text = "✓ Получено"
                claim_surf = self.font_small.render(claim_text, True, (80, 220, 100))
                self.screen.blit(claim_surf, (row_rect.right - claim_surf.get_width() - 12, row_rect.y + 8))
                # Reward summary.
                reward_text = f"Награда: {quest.reward_gold} зол · {quest.reward_xp} опыта"
                if quest.reward_shards > 0:
                    reward_text += f" · {quest.reward_shards}◈"
                reward_surf = self.font_small.render(reward_text, True, (167, 139, 250))
                self.screen.blit(reward_surf, (row_rect.right - reward_surf.get_width() - 12, row_rect.y + 28))
            elif is_complete:
                # Complete but not claimed — show "Получить" button.
                btn_w = 100
                btn_h = 28
                btn_x = row_rect.right - btn_w - 12
                btn_y = row_rect.y + (row_h - 8 - btn_h) // 2
                btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
                btn_hover = btn_rect.collidepoint(self._mouse_pos)
                btn_bg = (250, 204, 21) if btn_hover else (234, 179, 8)
                pygame.draw.rect(self.screen, btn_bg, btn_rect, border_radius=6)
                pygame.draw.rect(self.screen, (255, 255, 255), btn_rect, 1, border_radius=6)
                btn_lbl = self.font_button.render("Получить", True, (20, 20, 20))
                self.screen.blit(btn_lbl, btn_lbl.get_rect(center=btn_rect.center))
                _qid = quest_id
                self._click_rects.append(ClickRect(
                    tag=f"dq_claim_{quest_id}",
                    rect=btn_rect,
                    on_click=lambda q=_qid: self._claim_daily_quest(q),
                ))
                # Reward summary.
                reward_text = f"Награда: {quest.reward_gold} зол · {quest.reward_xp} опыта"
                if quest.reward_shards > 0:
                    reward_text += f" · {quest.reward_shards}◈"
                reward_surf = self.font_small.render(reward_text, True, (167, 139, 250))
                self.screen.blit(reward_surf, (row_rect.x + 12, row_rect.y + 48))
            else:
                # In progress — show progress text.
                prog_text = f"{progress} / {quest.target}"
                prog_surf = self.font_button.render(prog_text, True, (80, 220, 100))
                self.screen.blit(prog_surf, (row_rect.right - prog_surf.get_width() - 12, row_rect.y + 8))
                # Reward summary.
                reward_text = f"Награда: {quest.reward_gold} зол · {quest.reward_xp} опыта"
                if quest.reward_shards > 0:
                    reward_text += f" · {quest.reward_shards}◈"
                reward_surf = self.font_small.render(reward_text, True, (167, 139, 250))
                self.screen.blit(reward_surf, (row_rect.x + 12, row_rect.y + 48))

            row_y += row_h

        # Close button.
        btn_w = 120
        btn_h = 36
        close_x = modal_x + (modal_w - btn_w) // 2
        close_y = modal_y + modal_h - btn_h - pad
        close_rect = pygame.Rect(close_x, close_y, btn_w, btn_h)
        close_hover = close_rect.collidepoint(self._mouse_pos)
        close_bg = (220, 38, 38) if close_hover else (180, 30, 30)
        pygame.draw.rect(self.screen, close_bg, close_rect, border_radius=6)
        pygame.draw.rect(self.screen, (255, 255, 255), close_rect, 1, border_radius=6)
        close_lbl = self.font_button.render("Закрыть", True, (255, 255, 255))
        self.screen.blit(close_lbl, close_lbl.get_rect(center=close_rect.center))
        self._click_rects.append(ClickRect(tag="dq_close", rect=close_rect, on_click=self._close_daily_quest_modal))
