"""Impact particles + floating damage numbers."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

import pygame

from pockie_rpg.config import (
    DAMAGE_NUMBER_COLOR,
    DAMAGE_NUMBER_CRIT_COLOR,
    DAMAGE_NUMBER_CRIT_FONT_SIZE,
    DAMAGE_NUMBER_CRIT_LIFE_MAX,
    DAMAGE_NUMBER_CRIT_LIFE_MIN,
    DAMAGE_NUMBER_FONT,
    DAMAGE_NUMBER_FONT_SIZE,
    DAMAGE_NUMBER_JITTER,
    DAMAGE_NUMBER_LIFE_MAX,
    DAMAGE_NUMBER_LIFE_MIN,
    DAMAGE_NUMBER_MAX_COUNT,
    DAMAGE_NUMBER_POISON_COLOR,
    DAMAGE_NUMBER_VY_MAX,
    DAMAGE_NUMBER_VY_MIN,
    FONTS_DIR,
    PARTICLE_BLOOD_COLORS,
    PARTICLE_BLOOD_FRACTION,
    PARTICLE_GRAVITY,
    PARTICLE_HIT_COUNT_MAX,
    PARTICLE_HIT_COUNT_MIN,
    PARTICLE_LIFE_MAX,
    PARTICLE_LIFE_MIN,
    PARTICLE_MAX_COUNT,
    PARTICLE_SIZE_MAX,
    PARTICLE_SIZE_MIN,
    PARTICLE_SPARK_COLORS,
    PARTICLE_SPEED_MAX,
    PARTICLE_SPEED_MIN,
)


@dataclass(slots=True)
class Particle:
    """A single impact particle (spark or blood drop)."""

    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    color: tuple[int, int, int]
    size: int
    gravity: float
    alive: bool = True


class ParticleSystem:
    """Manages impact particles (sparks + blood) during combat."""

    # Аудит 2026-09 — общий кэш кругов частиц (см. render docstring).
    # Ключи конечны: size × color × 16 альфа-бакетов. set_alpha() на кэширо-
    # ванной поверхности допустим: он дешёв и применяется непосредственно
    # перед blit'ом (внутри кадра одна частица = один blit).
    _circle_cache: dict[tuple[int, tuple[int, int, int], int], pygame.Surface] = {}

    def __init__(self) -> None:
        self._particles: list[Particle] = []

    def spawn_hit(self, x: float, y: float, is_crit: bool = False) -> None:
        """Spawn 8-15 particles at the given impact point."""
        count = random.randint(PARTICLE_HIT_COUNT_MIN, PARTICLE_HIT_COUNT_MAX)
        for _ in range(count):
            if is_crit and random.random() < PARTICLE_BLOOD_FRACTION:
                color = random.choice(PARTICLE_BLOOD_COLORS)
            else:
                color = random.choice(PARTICLE_SPARK_COLORS)

            angle = random.uniform(0.0, math.pi * 2.0)
            speed = random.uniform(PARTICLE_SPEED_MIN, PARTICLE_SPEED_MAX)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed - random.uniform(20.0, 80.0)

            life = random.uniform(PARTICLE_LIFE_MIN, PARTICLE_LIFE_MAX)
            size = random.randint(PARTICLE_SIZE_MIN, PARTICLE_SIZE_MAX)

            self._particles.append(
                Particle(
                    x=x,
                    y=y,
                    vx=vx,
                    vy=vy,
                    life=life,
                    max_life=life,
                    color=color,
                    size=size,
                    gravity=PARTICLE_GRAVITY,
                    alive=True,
                )
            )

        if len(self._particles) > PARTICLE_MAX_COUNT:
            overflow = len(self._particles) - PARTICLE_MAX_COUNT
            self._particles = self._particles[overflow:]

    def update(self, dt: float) -> None:
        """Advance all particles: apply velocity + gravity, decrement life."""
        if not self._particles:
            return
        alive: list[Particle] = []
        for p in self._particles:
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.vy += p.gravity * dt
            p.life -= dt
            if p.life > 0.0:
                alive.append(p)
        self._particles = alive

    def render(self, screen: pygame.Surface) -> None:
        """Render all alive particles as small alpha-blended circles.

        Аудит 2026-09 — кэш кругов: раньше Surface создавалась и растеризо-
        валась (draw.circle) для КАЖДОЙ частицы КАЖДЫЙ кадр (до сотен
        аллокаций/кадр). Пространство ключей КОНЕЧНО: size 3..5 × 5 цветов ×
        16 альфа-бакетов = 240 поверхностей максимум — кэш строится один раз
        и только переключает альфу (set_alpha) перед blit'ом.
        """
        cache = ParticleSystem._circle_cache
        for p in self._particles:
            if p.life <= 0.0:
                continue
            alpha = max(0, min(255, int((p.life / p.max_life) * 255)))
            if alpha <= 0:
                continue
            size = max(1, p.size)
            bucket = alpha // 16
            key = (size, p.color, bucket)
            surf = cache.get(key)
            if surf is None:
                surf = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
                pygame.draw.circle(
                    surf,
                    (p.color[0], p.color[1], p.color[2], (bucket + 1) * 16 - 1),
                    (size, size),
                    size,
                )
                cache[key] = surf
            surf.set_alpha(max(48, min(255, alpha)))
            screen.blit(surf, (int(p.x - size), int(p.y - size)))

    def clear(self) -> None:
        """Remove all particles."""
        self._particles.clear()

    def __len__(self) -> int:
        return len(self._particles)


@dataclass(slots=True)
class DamageNumber:
    """A single floating damage number or status text (miss/dodge/parry).

    Stage 97 — two-phase animation:
    1. FLASH: number appears at impact point, flashes/pulses for ~1 second.
    2. FLOAT: number floats upward with alpha fading.
    """

    x: float
    y: float
    damage: int
    is_crit: bool
    life: float
    max_life: float
    vy: float
    color: tuple[int, int, int]
    font_size: int
    # Stage 50 — custom text (for "Промах!", "Уклон!", "Парри!", "Крит!").
    custom_text: str = ""
    # Stage 97 — flash phase duration (number stays at impact point, flashing).
    flash_duration: float = 0.8
    # Stage 97 — current age (0 at spawn, increments by dt).
    age: float = 0.0

    @property
    def alpha(self) -> int:
        """Return current alpha (0..255) based on phase + remaining life ratio."""
        if self.age < self.flash_duration:
            # Flash phase — full alpha with slight pulsing.
            return 255
        # Float phase — alpha fades with remaining life.
        if self.max_life <= 0:
            return 0
        ratio = max(0.0, min(1.0, self.life / self.max_life))
        return int(255 * ratio)

    @property
    def scale(self) -> float:
        """Stage 97 — scale factor during flash phase (pulsing effect)."""
        if self.age < self.flash_duration:
            # Pulse: 1.0 → 1.3 → 1.0 during flash phase.
            t = self.age / max(0.001, self.flash_duration)
            return 1.0 + 0.3 * math.sin(t * math.pi)
        return 1.0

    @property
    def is_flashing(self) -> bool:
        """Stage 97 — True if still in the flash phase (not yet floating up)."""
        return self.age < self.flash_duration

    @property
    def text(self) -> str:
        """Return display text: custom_text if set, else damage + crit."""
        if self.custom_text:
            return self.custom_text
        if self.is_crit:
            return f"-{self.damage} Крит!"
        return f"-{self.damage}"


class DamageNumberSystem:
    """Manages floating damage numbers during combat."""

    def __init__(self) -> None:
        self._numbers: list[DamageNumber] = []
        self._font_cache: dict[int, pygame.font.Font] = {}

    def _get_font(self, size: int) -> pygame.font.Font:
        """Return (and cache) the damage font for the given size.

        Uses the user-provided TTF file (fonts/<DAMAGE_NUMBER_FONT>); falls back
        to the system DejaVu Sans if the file is missing or fails to load.
        """
        if size not in self._font_cache:
            font_path = FONTS_DIR / DAMAGE_NUMBER_FONT
            try:
                font = pygame.font.Font(str(font_path), size)
                font.set_bold(True)
                self._font_cache[size] = font
            except (OSError, FileNotFoundError, pygame.error):
                self._font_cache[size] = pygame.font.SysFont(
                    "dejavusans,arial", size, bold=True
                )
        return self._font_cache[size]

    def spawn(
        self,
        damage: int,
        x: float,
        y: float,
        is_crit: bool = False,
        is_poison: bool = False,
    ) -> None:
        """Spawn a single damage number at the given impact point."""
        if is_crit:
            color = DAMAGE_NUMBER_CRIT_COLOR
            font_size = DAMAGE_NUMBER_CRIT_FONT_SIZE
            life = random.uniform(DAMAGE_NUMBER_CRIT_LIFE_MIN, DAMAGE_NUMBER_CRIT_LIFE_MAX)
        elif is_poison:
            color = DAMAGE_NUMBER_POISON_COLOR
            font_size = DAMAGE_NUMBER_FONT_SIZE
            life = random.uniform(DAMAGE_NUMBER_LIFE_MIN, DAMAGE_NUMBER_LIFE_MAX)
        else:
            color = DAMAGE_NUMBER_COLOR
            font_size = DAMAGE_NUMBER_FONT_SIZE
            life = random.uniform(DAMAGE_NUMBER_LIFE_MIN, DAMAGE_NUMBER_LIFE_MAX)

        vy = random.uniform(DAMAGE_NUMBER_VY_MIN, DAMAGE_NUMBER_VY_MAX)
        jitter_x = random.uniform(-DAMAGE_NUMBER_JITTER, DAMAGE_NUMBER_JITTER)

        self._numbers.append(
            DamageNumber(
                x=x + jitter_x,
                y=y,
                damage=damage,
                is_crit=is_crit,
                life=life,
                max_life=life,
                vy=vy,
                color=color,
                font_size=font_size,
            )
        )

        if len(self._numbers) > DAMAGE_NUMBER_MAX_COUNT:
            overflow = len(self._numbers) - DAMAGE_NUMBER_MAX_COUNT
            self._numbers = self._numbers[overflow:]

    def spawn_text(
        self,
        text: str,
        x: float,
        y: float,
        color: tuple[int, int, int] = (255, 255, 255),
        font_size: int = 48,
        life: float = 2.5,
    ) -> None:
        """Stage 50 — spawn a floating status text (miss/dodge/parry/crit).

        Longer life than damage numbers (2.5s vs ~1.2s) so the player has
        time to read the status effect.
        """
        vy = random.uniform(DAMAGE_NUMBER_VY_MIN * 0.5, DAMAGE_NUMBER_VY_MAX * 0.5)
        jitter_x = random.uniform(-DAMAGE_NUMBER_JITTER, DAMAGE_NUMBER_JITTER)
        self._numbers.append(
            DamageNumber(
                x=x + jitter_x,
                y=y,
                damage=0,
                is_crit=False,
                life=life,
                max_life=life,
                vy=vy,
                color=color,
                font_size=font_size,
                custom_text=text,
            )
        )
        if len(self._numbers) > DAMAGE_NUMBER_MAX_COUNT:
            overflow = len(self._numbers) - DAMAGE_NUMBER_MAX_COUNT
            self._numbers = self._numbers[overflow:]

    def update(self, dt: float) -> None:
        """Advance all damage numbers: age, then float + fade."""
        if not self._numbers:
            return
        alive: list[DamageNumber] = []
        for n in self._numbers:
            n.age += dt
            # Stage 97 — only float up after flash phase ends.
            if not n.is_flashing:
                n.y += n.vy * dt
                n.life -= dt
            if n.life > 0.0:
                alive.append(n)
        self._numbers = alive

    def render(self, screen: pygame.Surface) -> None:
        """Render all alive damage numbers with alpha + scale (flash phase)."""
        for n in self._numbers:
            if n.life <= 0.0:
                continue
            alpha = n.alpha
            if alpha <= 0:
                continue
            font = self._get_font(n.font_size)
            text_surf = font.render(n.text, True, n.color)
            text_surf.set_alpha(alpha)
            # Stage 97 — scale during flash phase (pulsing effect).
            if n.is_flashing:
                scale = n.scale
                if scale != 1.0:
                    sw = max(1, int(text_surf.get_width() * scale))
                    sh = max(1, int(text_surf.get_height() * scale))
                    text_surf = pygame.transform.smoothscale(text_surf, (sw, sh))
            text_rect = text_surf.get_rect(center=(int(n.x), int(n.y)))
            screen.blit(text_surf, text_rect.topleft)

    def clear(self) -> None:
        """Remove all damage numbers."""
        self._numbers.clear()

    def __len__(self) -> int:
        return len(self._numbers)
