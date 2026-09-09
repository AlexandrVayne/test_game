"""Stage 202 — единая «панель у курсора» (тултипы статусов и лута).

Одна реализация отрисовки панели (фон/рамка/скругление/акцент) и одного
размещения: у курсора с флипом у краёв ЛИБО у якорного прямоугольника —
центр над ним, при нехватке места — под ним. До Stage 202 было две
независимые реализации с дублированной _su-геометрией:
_render_status_tooltip (render_battle) и _render_loot_tooltip
(render_quick_battle).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pygame


@dataclass(slots=True)
class TooltipLine:
    """Строка панели: текст + цвет + размер шрифта (design-px).

    space_before — отступ сверху в design-px (0 у первой строки).
    Stage 203 — `rule=True`: вместо текста рисуется горизонтальная
    линия-разделитель цветом `color` (текст/шрифт игнорируются).
    """

    text: str
    color: tuple[int, int, int] = (212, 212, 216)
    size: int = 13
    bold: bool = False
    space_before: int = 0
    rule: bool = False


@dataclass(slots=True)
class PanelStyle:
    """Оформление панели; все размеры design-px (умножаются на _su).

    Stage 203 — `min_w`: минимальная ширина панели в design-px
    (тултип бафов MAP: панель не уже 170 даже при коротком тексте).
    """

    bg: tuple[int, int, int, int] = (15, 15, 18, 235)
    border: tuple[int, int, int] = (82, 82, 91)
    border_w: int = 1
    radius: int = 8
    pad_x: int = 8
    pad_y: int = 8
    accent: tuple[int, int, int] | None = None
    accent_h: int = 3
    min_w: int = 0


def render_tooltip_panel(
    owner: Any,
    lines: list[TooltipLine],
    *,
    cursor: tuple[int, int] | None = None,
    anchor: pygame.Rect | None = None,
    style: PanelStyle | None = None,
    wrap_width: int = 0,
    offset: int = 16,
    margin: int = 8,
    prefer_below: bool = False,
) -> None:
    """Нарисовать панель со строками `lines` на owner.screen.

    owner — рендерер с _su()/_su_font() (ScalableRendererMixin). Тексты и
    геометрия — design-единицы, отрисовка нативная (×_su). Позиция:
    cursor=(x, y) — дизайн-позиция мыши (панель справа-снизу курсора,
    флип влево/вверх у краёв экрана); либо anchor — дизайн-Rect (панель
    по центру НАД ним, при нехватке места — ПОД ним; Stage 203 —
    prefer_below=True меняет приоритет: ПОД ним, флип НАД ним — тултип
    бафов MAP). wrap_width — design-ширина переноса длинных строк
    (0 — без переноса). offset — отступ панели от курсора; margin —
    минимальный зазор до краёв экрана.
    """
    if cursor is None and anchor is None:
        return
    if not lines:
        return
    st = style or PanelStyle()
    su = owner._su
    scr = owner.screen

    flat: list[TooltipLine] = []
    for line in lines:
        if line.rule:
            flat.append(line)
            continue
        font = owner._su_font(line.size, bold=line.bold)
        if wrap_width > 0 and font.size(line.text)[0] > su(wrap_width):
            parts: list[str] = []
            cur = ""
            for word in line.text.split():
                trial = f"{cur} {word}" if cur else word
                if cur and font.size(trial)[0] > su(wrap_width):
                    parts.append(cur)
                    cur = word
                else:
                    cur = trial
            if cur:
                parts.append(cur)
        else:
            parts = [line.text]
        for i, part in enumerate(parts):
            flat.append(
                TooltipLine(part, line.color, line.size, line.bold,
                            line.space_before if i == 0 else 0)
            )

    rendered: list[tuple[pygame.Surface | None, int, TooltipLine]] = []
    max_w = 0
    fonts: dict[tuple[int, bool], pygame.font.Font] = {}
    for ln in flat:
        if ln.rule:
            rendered.append((None, ln.space_before, ln))
            continue
        key = (ln.size, ln.bold)
        f = fonts.get(key)
        if f is None:
            f = owner._su_font(ln.size, bold=ln.bold)
            fonts[key] = f
        surf = f.render(ln.text, True, ln.color)
        rendered.append((surf, ln.space_before, ln))
        if surf.get_width() > max_w:
            max_w = surf.get_width()

    w = max(su(st.min_w), max_w + su(st.pad_x) * 2)
    h = su(st.pad_y) * 2 + sum(su(sb) + (s.get_height() if s else su(1))
                               for s, sb, _ in rendered)
    panel = pygame.Surface((max(1, w), max(1, h)), pygame.SRCALPHA)
    pygame.draw.rect(panel, st.bg, panel.get_rect(), border_radius=su(st.radius))
    pygame.draw.rect(panel, st.border, panel.get_rect(),
                     max(1, su(st.border_w)), border_radius=su(st.radius))
    if st.accent is not None and st.accent_h > 0:
        pygame.draw.rect(panel, st.accent,
                         pygame.Rect(0, 0, w, su(st.accent_h)),
                         border_radius=su(2))
    y = su(st.pad_y)
    for surf, sb, ln in rendered:
        y += su(sb)
        if surf is None:
            pygame.draw.line(panel, ln.color,
                             (su(st.pad_x), y), (w - su(st.pad_x), y), 1)
            y += su(1)
            continue
        panel.blit(surf, (su(st.pad_x), y))
        y += surf.get_height()

    scr_w, scr_h = scr.get_size()
    if anchor is not None:
        tx = su(anchor.x) + su(anchor.w) // 2 - w // 2
        if prefer_below:
            ty = su(anchor.y) + su(anchor.h) + su(6)
            if ty + h > scr_h - su(margin):
                ty = su(anchor.y) - h - su(6)
        else:
            ty = su(anchor.y) - h - su(6)
            if ty < su(margin):
                ty = su(anchor.y) + su(anchor.h) + su(6)
    else:
        mx, my = cursor
        tx = su(mx) + su(offset)
        ty = su(my) + su(offset)
        if tx + w > scr_w - su(margin):
            tx = su(mx) - su(offset) - w
        if ty + h > scr_h - su(margin):
            ty = su(my) - su(offset) - h
    tx = max(su(margin), min(tx, scr_w - w - su(margin)))
    ty = max(su(margin), min(ty, scr_h - h - su(margin)))
    scr.blit(panel, (tx, ty))
