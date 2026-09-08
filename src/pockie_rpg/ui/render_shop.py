"""ShopRendererMixin — Магазин modal (equipment + gems tabs).

Extracted verbatim from render_map.py (Stage 89 refactor-96a). The methods
here are copies of the original implementations; PygameUI inherits from
this mixin so `self` is bound to the full UI instance.

Stage 157 — НАТИВНЫЙ рендер (раньше буфер 1280×720 → растяжение ×2 = «мыло»):
координаты через self._su() / _su_rect(), шрифты через _su_font(),
затемнение через _su_overlay(). Вёрстка пересчитана: карточки оборудования
5×140 (иконки 64), карточки гемов 5×130 (иконки 48), тултип предметов
native. Кнопки «Обновить» и пагинация гемов перенесены с хардкода
(refresh_y=580, nav_y=640) на привязку к низу модалки.
"""
from __future__ import annotations

import pygame

from pockie_rpg.config import SCREEN_HEIGHT, SCREEN_WIDTH
from pockie_rpg.ui.animator import ClickRect


class ShopRendererMixin:
    """Renders the Shop (Магазин) modal with equipment and gems tabs."""

    def _render_shop_modal(self) -> None:
        """Stage 59/157 — render the Shop modal with 2 tabs (equipment + gems)."""
        su = self._su
        modal_w = 800
        modal_h = 560
        # Stage 157 — перетаскиваемое окно (общий реестр, persist в сейве).
        modal_x, modal_y = self._window_pos("shop", modal_w, modal_h)

        # Stage 157 — нативное затемнение (не квадрат-подложка из буфера).
        self.screen.blit(self._su_overlay(140), (0, 0))

        modal_r = pygame.Rect(su(modal_x), su(modal_y), su(modal_w), su(modal_h))
        pygame.draw.rect(self.screen, (20, 20, 24), modal_r, border_radius=10)
        pygame.draw.rect(self.screen, (234, 179, 8),
                        (modal_r.x, modal_r.y, modal_r.w, su(6)), border_radius=3)

        # Stage 157/158 — общая шапка: заголовок + золото + drag + persist +
        # ВЫНОСНОЙ крестик справа.
        self._render_window_titlebar(
            "shop", modal_r, "Магазин",
            (234, 179, 8), True,
            right_text=f"Золото: {self.player.gold}",
            open_attr="_shop_modal_open",
            on_close=self._close_shop,
        )

        # Tab buttons.
        tab_names = ["Снаряжение", "Самоцветы"]
        tab_w = 110
        tab_h = 32
        tab_gap = 6
        tabs_total_w = 2 * tab_w + tab_gap
        tab_x0 = modal_x + (modal_w - tabs_total_w) // 2
        tab_y = modal_y + 50
        for i, name in enumerate(tab_names):
            t_rect = pygame.Rect(su(tab_x0 + i * (tab_w + tab_gap)), su(tab_y),
                                 su(tab_w), su(tab_h))
            is_active = (self._shop_active_tab == i)
            hover = t_rect.collidepoint(self._mouse_pos)
            if is_active:
                bg = (234, 179, 8)
                fg = (20, 20, 20)
            elif hover:
                bg = (60, 50, 10)
                fg = (255, 255, 255)
            else:
                bg = (40, 40, 45)
                fg = (180, 180, 185)
            pygame.draw.rect(self.screen, bg, t_rect, border_radius=6)
            tab_surf = self._su_font(16, bold=True).render(name, True, fg)
            self.screen.blit(tab_surf, tab_surf.get_rect(center=t_rect.center))
            _tab_idx = i
            self._click_rects.append(ClickRect(
                tag=f"shop_tab_{i}",
                rect=t_rect,
                on_click=lambda t=_tab_idx: self._set_shop_tab(t),
            ))

        # Stage 158 — внутренняя close-кнопка УДАЛЁНА (выносной крестик
        # рисует шапка справа от окна).

        # Stage 133 — feedback toast (inventory full / other shop warnings).
        if self._shop_feedback and self._shop_feedback_timer > 0:
            fb_surf = self._su_font(16, bold=True).render(self._shop_feedback,
                                                          True, (240, 90, 60))
            fb_bg = pygame.Rect(
                modal_r.centerx - fb_surf.get_width() // 2 - su(14),
                modal_r.y + su(52),
                fb_surf.get_width() + su(28),
                su(30),
            )
            pygame.draw.rect(self.screen, (44, 24, 20), fb_bg, border_radius=6)
            pygame.draw.rect(self.screen, (240, 90, 60), fb_bg, 1, border_radius=6)
            self.screen.blit(fb_surf, (fb_bg.x + su(14), fb_bg.y + su(6)))

        content_y = tab_y + tab_h + 10
        content_h = modal_y + modal_h - content_y - 10

        if self._shop_active_tab == 0:
            self._render_shop_equipment(modal_x, content_y, modal_w, content_h)
        else:
            self._render_shop_gems(modal_x, content_y, modal_w, content_h)

    def _render_shop_equipment(self, modal_x: int, content_y: int,
                               modal_w: int, content_h: int) -> None:
        """Stage 131/157 — shop: 5 level-based items, no sub-tabs, refresh button."""
        from pockie_rpg.config import SLOT_NAME_RU

        su = self._su
        shop_item_ids = getattr(self, "_shop_items", [])
        if not shop_item_ids:
            self._generate_shop_items()
            shop_item_ids = self._shop_items

        card_w = 140
        card_h = 120
        gap = 12
        cols = 5
        total_w = cols * card_w + (cols - 1) * gap
        start_x = modal_x + (modal_w - total_w) // 2
        start_y = content_y + 10

        hovered_shop_item_id = None

        for i, item_id in enumerate(shop_item_ids[:5]):
            item = self.player.get_item_definition(item_id) if hasattr(self, "player") else None
            if item is None:
                from pockie_rpg.data.item_db import get_equipment
                item = get_equipment(item_id)
            if item is None:
                continue

            card_rect = pygame.Rect(su(start_x + i * (card_w + gap)), su(start_y),
                                     su(card_w), su(card_h))
            hover = card_rect.collidepoint(self._mouse_pos)

            if hover:
                shadow = pygame.Surface((card_rect.w + su(8), card_rect.h + su(8)),
                                        pygame.SRCALPHA)
                pygame.draw.rect(shadow, (234, 179, 8, 30),
                                 (0, 0, card_rect.w + su(8), card_rect.h + su(8)),
                                 border_radius=10)
                self.screen.blit(shadow, (card_rect.x - su(4), card_rect.y - su(4)))

            from pockie_rpg.config import RARITY_RGB, RARITY_SLOT_BG
            rarity = item.get("rarity", "Grey")
            bg = RARITY_SLOT_BG.get(rarity, (40, 40, 45))
            border = RARITY_RGB.get(rarity, (82, 82, 91))
            pygame.draw.rect(self.screen, bg, card_rect, border_radius=8)
            pygame.draw.rect(self.screen, border, card_rect,
                             su(2) if hover else 1, border_radius=8)

            icon_rect = pygame.Rect(card_rect.x + (card_rect.w - su(48)) // 2,
                                    card_rect.y + su(8), su(48), su(48))
            self._blit_gear_icon(item, icon_rect)

            name = item.get("name", "?")
            if len(name) > 18:
                name = name[:17] + "…"
            name_font = self._su_font(13)
            name_surf = name_font.render(name, True, (255, 255, 255))
            # Stage 157 — обрезка «…» по фактической ширине (не по символам).
            if name_surf.get_width() > card_rect.w - su(8):
                while name_surf.get_width() > card_rect.w - su(14) and len(name) > 3:
                    name = name[:-1]
                    name_surf = name_font.render(name + "…", True, (255, 255, 255))
            self.screen.blit(name_surf, name_surf.get_rect(
                center=(card_rect.centerx, card_rect.y + su(64))))

            slot_lbl = SLOT_NAME_RU.get(item.get("slot", ""), "?")
            lvl_text = f"{slot_lbl} · Ур.{item.get('item_level', 1)}"
            lvl_surf = self._su_font(13).render(lvl_text, True, (180, 180, 200))
            self.screen.blit(lvl_surf, lvl_surf.get_rect(
                center=(card_rect.centerx, card_rect.y + su(80))))

            price = item.get("sell_price", 50) * 5
            btn_rect = pygame.Rect(card_rect.x + su(6),
                                   card_rect.bottom - su(22) - su(6),
                                   card_rect.w - su(12), su(22))
            can_afford = self.player.gold >= price
            btn_hover = btn_rect.collidepoint(self._mouse_pos)
            if not can_afford:
                bg_btn = (50, 30, 30)
                fg_btn = (200, 100, 100)
            elif btn_hover:
                bg_btn = (234, 179, 8)
                fg_btn = (20, 20, 20)
            else:
                bg_btn = (180, 83, 9)
                fg_btn = (255, 255, 255)
            pygame.draw.rect(self.screen, bg_btn, btn_rect, border_radius=4)
            btn_text = self._su_font(13).render(f"{price} зол.", True, fg_btn)
            self.screen.blit(btn_text, btn_text.get_rect(center=btn_rect.center))
            _iid = item_id
            self._click_rects.append(ClickRect(
                tag=f"shop_buy_{item_id}", rect=btn_rect,
                on_click=lambda i=_iid: self._buy_item(i),
            ))

            if hover:
                hovered_shop_item_id = item_id

        # Stage 157 — «Обновить» привязана к НИЗУ модалки (было refresh_y=580
        # хардкодом — на другой вёрстке уезжала за пределы окна).
        refresh_w = 200
        refresh_h = 36
        modal_bottom = su((SCREEN_HEIGHT - 560) // 2 + 560)
        refresh_rect = pygame.Rect(
            su(modal_x) + (su(800) - su(refresh_w)) // 2,
            modal_bottom - su(refresh_h) - su(10),
            su(refresh_w), su(refresh_h),
        )
        refresh_hover = refresh_rect.collidepoint(self._mouse_pos)
        refresh_cost = 10000
        can_refresh = self.player.gold >= refresh_cost
        if not can_refresh:
            bg_r = (50, 30, 30)
            fg_r = (200, 100, 100)
        elif refresh_hover:
            bg_r = (234, 179, 8)
            fg_r = (20, 20, 20)
        else:
            bg_r = (180, 83, 9)
            fg_r = (255, 255, 255)
        pygame.draw.rect(self.screen, bg_r, refresh_rect, border_radius=8)
        refresh_text = self._su_font(16, bold=True).render(
            f"Обновить ({refresh_cost} зол.)", True, fg_r)
        self.screen.blit(refresh_text, refresh_text.get_rect(center=refresh_rect.center))
        self._click_rects.append(ClickRect(tag="shop_refresh", rect=refresh_rect,
                                           on_click=self._refresh_shop))

        if hovered_shop_item_id is not None:
            self._render_shop_tooltip(hovered_shop_item_id, modal_x, modal_y=0)

    def _render_shop_tooltip(self, item_id: str, modal_x: int, modal_y: int) -> None:
        """Stage 69/157 — item tooltip on shop card hover (native render).

        Reuses the inventory tooltip layout but positioned to the right of
        the shop modal (or left if no room).
        """
        from pockie_rpg.data.item_db import get_equipment
        su = self._su
        gear = get_equipment(item_id)
        if gear is None:
            return
        tip_w = 240
        stats = gear.get("stats", {})
        stats_count = len(stats)
        # Stage 177 — «Продажа» удалена: статы с 68, окно ниже (−16).
        tip_h = max(124, 82 + stats_count * 18)
        # Position to the right of the shop modal.
        tip_x = modal_x + 800 + 8  # modal_w=800, so modal_right = modal_x+800
        tip_y = (SCREEN_HEIGHT - tip_h) // 2
        if tip_x + tip_w > SCREEN_WIDTH:
            tip_x = modal_x - tip_w - 8  # left side if no room on right.
        if tip_x < 8:
            tip_x = 8
        tip_rect = pygame.Rect(su(tip_x), su(tip_y), su(tip_w), su(tip_h))
        pygame.draw.rect(self.screen, (15, 15, 18), tip_rect, border_radius=8)
        pygame.draw.rect(self.screen, (234, 179, 8), tip_rect, 2, border_radius=8)
        pygame.draw.rect(self.screen, (234, 179, 8),
                         (tip_rect.x, tip_rect.y, tip_rect.w, su(4)), border_radius=2)

        from pockie_rpg.config import SLOT_NAME_RU as slot_name_map
        slot_name = slot_name_map.get(gear["slot"], gear["slot"])
        slot_label = self._su_font(13).render(slot_name.upper(), True, (234, 179, 8))
        self.screen.blit(slot_label, (tip_rect.x + su(12), tip_rect.y + su(12)))
        name_surf = self._su_font(16, bold=True).render(gear["name"], True, (255, 255, 255))
        self.screen.blit(name_surf, (tip_rect.x + su(12), tip_rect.y + su(32)))
        item_level = gear.get("item_level", 1)
        level_surf = self._su_font(13).render(f"Ур. предмета: {item_level}",
                                              True, (180, 180, 200))
        self.screen.blit(level_surf, (tip_rect.x + su(12), tip_rect.y + su(50)))
        # Stage 177 — строка «Продажа: N зол.» удалена из тултипа.
        from pockie_rpg.config import STAT_LABEL_RU as stat_label_map
        stat_y = tip_rect.y + su(68)  # Stage 177 — было 84 (после удаления «Продажа»)
        if not stats:
            no_bonus = self._su_font(13).render("(нет бонусов)", True, (113, 113, 122))
            self.screen.blit(no_bonus, (tip_rect.x + su(12), stat_y))
        else:
            from pockie_rpg.data.item_db import scale_gear_stat
            for stat_key, value in stats.items():
                label = stat_label_map.get(stat_key, stat_key)
                scaled = scale_gear_stat(value, item_level)
                sign = "+" if scaled >= 0 else ""
                line = f"{sign}{scaled}  {label}"
                stat_surf = self._su_font(13).render(line, True, (80, 220, 100))
                max_text_w = tip_rect.w - su(24)
                if stat_surf.get_width() > max_text_w:
                    while stat_surf.get_width() > max_text_w and len(label) > 2:
                        label = label[:-1]
                        line = f"{sign}{scaled}  {label}…"
                        stat_surf = self._su_font(13).render(line, True, (80, 220, 100))
                self.screen.blit(stat_surf, (tip_rect.x + su(12), stat_y))
                stat_y += su(18)

    def _render_shop_gems(self, modal_x: int, content_y: int,
                          modal_w: int, content_h: int) -> None:
        """Stage 59/70/157 — shop tab 1: gems L1 with buy buttons.

        Stage 157 — вёрстка нативная; пагинация привязана к низу модалки
        (было nav_y=640 хардкодом).
        """
        from pockie_rpg.config import GEM_ICON_DIR
        from pockie_rpg.data.item_db import GEMS_DB, get_gem_icon_filename

        su = self._su
        gem_types = ["gem_red", "gem_blue", "gem_green", "gem_yellow", "gem_orange"]
        card_w = 130
        card_h = 160
        gap = 20
        total_w = 5 * card_w + 4 * gap
        start_x = su(modal_x) + (su(modal_w) - su(total_w)) // 2
        start_y = su(content_y + 10)

        for i, gtype in enumerate(gem_types):
            cx = start_x + su(i * (card_w + gap))
            cy = start_y
            gem_def = GEMS_DB.get(gtype)
            if gem_def is None:
                continue
            card_rect = pygame.Rect(cx, cy, su(card_w), su(card_h))
            hover = card_rect.collidepoint(self._mouse_pos)
            # Stage 87/157 — мягкая тень hover (SRCALPHA, не сплошной канвас).
            if hover:
                shadow = pygame.Surface((card_rect.w + su(8), card_rect.h + su(8)),
                                        pygame.SRCALPHA)
                pygame.draw.rect(shadow, (10, 10, 12, 160),
                                 (0, 0, card_rect.w + su(8), card_rect.h + su(8)),
                                 border_radius=10)
                self.screen.blit(shadow, (card_rect.x - su(4), card_rect.y - su(4)))
            pygame.draw.rect(self.screen, (40, 40, 45) if not hover else (50, 50, 55),
                             card_rect, border_radius=8)
            pygame.draw.rect(self.screen, (234, 179, 8) if hover else (60, 60, 65),
                             card_rect, 1, border_radius=8)

            # Gem icon.
            icon_file = get_gem_icon_filename(gtype, 1)
            icon_path = str(GEM_ICON_DIR / icon_file)
            icon_rect = pygame.Rect(cx + (su(card_w) - su(48)) // 2, cy + su(8),
                                    su(48), su(48))
            self._draw_gem_icon(icon_rect, icon_path, 1)

            name_surf = self._su_font(13).render(gem_def["name"], True, (255, 255, 255))
            self.screen.blit(name_surf, name_surf.get_rect(
                center=(cx + su(card_w) // 2, cy + su(64))))
            bonus = gem_def.get("base_bonus", 5)
            stat_lbl = gem_def.get("stat_label", "")
            info_surf = self._su_font(13).render(f"+{bonus} {stat_lbl}",
                                                 True, (80, 220, 100))
            self.screen.blit(info_surf, info_surf.get_rect(
                center=(cx + su(card_w) // 2, cy + su(82))))

            # Buy button.
            price = 100
            btn_rect = pygame.Rect(cx + su(8), cy + su(card_h) - su(28) - su(8),
                                   su(card_w) - su(16), su(28))
            can_afford = self.player.gold >= price
            btn_hover = btn_rect.collidepoint(self._mouse_pos)
            if not can_afford:
                bg = (50, 30, 30)
                fg = (200, 100, 100)
            elif btn_hover:
                bg = (234, 179, 8)
                fg = (20, 20, 20)
            else:
                bg = (180, 83, 9)
                fg = (255, 255, 255)
            pygame.draw.rect(self.screen, bg, btn_rect, border_radius=6)
            btn_text = self._su_font(13).render(f"Купить ({price} зол.)", True, fg)
            self.screen.blit(btn_text, btn_text.get_rect(center=btn_rect.center))
            _gt = gtype
            self._click_rects.append(ClickRect(tag=f"shop_buy_gem_{gtype}",
                                               rect=btn_rect,
                                               on_click=lambda g=_gt: self._buy_gem(g)))

        # Stage 70/157 — page indicator docked to the modal bottom.
        page_text = f"1 / 1  ({len(gem_types)} камней)"
        page_surf = self._su_font(13).render(page_text, True, (234, 179, 8))
        modal_r_bottom = su((SCREEN_HEIGHT - 560) // 2 + 560)
        page_x = su(modal_x) + (su(modal_w) - page_surf.get_width()) // 2
        self.screen.blit(page_surf, (page_x, modal_r_bottom - su(34)))
