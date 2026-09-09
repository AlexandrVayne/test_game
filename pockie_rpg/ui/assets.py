"""AssetManager — singleton-ish loader for sprites, backgrounds, avatars.

Per §4.3: imports `pygame`, stdlib, `config.ASSETS_DIR`. NO combat/data imports.

Responsibilities:
  * Load + cache (LRU) pygame surfaces.
  * Provide motion-sprite cycling for idle/attack/hit/death animations.
  * Detect sprite facing (LEFT/RIGHT) for flip correction (per §8.2).
  * Graceful placeholder fallback (per rule 10): never returns None.

Per §7.7 + §8.2: hero sprite intrinsically faces LEFT → flip to RIGHT;
enemy sprite intrinsically faces RIGHT → flip to LEFT; mob_1 ALWAYS flipped.
"""
from __future__ import annotations

import math
from collections import OrderedDict
from pathlib import Path

import pygame

from pockie_rpg.config import (
    AVATAR_DIR,
    BACKGROUNDS_DIR,
    BODY_SPRITE_H,
    BODY_SPRITE_W,
    EXTRACTED_DIR,
    INTRINSIC_FACING,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SKILL_ICON_DIR,
    SpriteFacing,
)

# Maximum number of cached surfaces (LRU eviction after this).
_LRU_MAX: int = 128


class AssetManager:
    """LRU-cached loader for game assets.

    A single instance per UI session. Safe to construct multiple instances
    (no module-level global state) — each maintains its own cache.
    """

    def __init__(self) -> None:
        self._bg_cache: OrderedDict[str, pygame.Surface] = OrderedDict()
        self._motion_cache: OrderedDict[tuple[str, int, int, int], pygame.Surface] = (
            OrderedDict()
        )
        self._avatar_cache: OrderedDict[str, pygame.Surface] = OrderedDict()
        self._frame_counts: dict[str, int] = {}
        # Stage 91 — cache folder → frame file list (per DEVELOPMENT_RULES §8.2).
        # Avoids repeated _list_motion_frames() calls when a frame isn't in cache.
        self._frame_files: dict[str, tuple] = {}
        self._facing_cache: dict[str, SpriteFacing] = dict(INTRINSIC_FACING)
        self._placeholder: pygame.Surface | None = None
        # Stage 10 — separate cache for skill icons (loaded from SKILL_ICON_DIR).
        self._skill_icon_cache: OrderedDict[str, pygame.Surface] = OrderedDict()
        # Stage 91 — overlay cache (per DEVELOPMENT_RULES §8.1).
        # Caches full-screen SRCALPHA surfaces by alpha value (60, 80, 140, ...).
        self._overlay_cache: dict[int, pygame.Surface] = {}
        # Stage 204 — _font_cache удалён вместе с get_font (0 вызовов:
        # шрифты идут через _su_font/_su_text-кэши).
        # Stage 80 — pre-load enemy avatars at startup (avoid lag on first render).
        self._preload_enemy_avatars()

    def _preload_enemy_avatars(self) -> None:
        """Stage 80 — pre-load all enemy avatar PNGs as convert_alpha()."""
        for mob_id, filename in self._MOB_AVATAR_FILES.items():
            avatar_path = str(AVATAR_DIR / filename)
            try:
                img = pygame.image.load(avatar_path).convert_alpha()
                self._avatar_cache[f"enemy_{mob_id}_72"] = img
            except Exception:
                pass  # will use placeholder on demand

    # -----------------------------------------------------------------
    # PLACEHOLDER FALLBACK (per rule 10)
    # -----------------------------------------------------------------

    def _get_placeholder(self, w: int, h: int) -> pygame.Surface:
        """Return a magenta/black placeholder surface of given size.

        Used when an asset file is missing — never returns None (rule 10).
        Marked as explicit design choice, not a TODO.
        """
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        # Magenta fill + black cross = obvious "missing asset" indicator.
        surf.fill((255, 0, 255, 128))
        pygame.draw.line(surf, (0, 0, 0, 255), (0, 0), (w, h), 3)
        pygame.draw.line(surf, (0, 0, 0, 255), (w, 0), (0, h), 3)
        pygame.draw.rect(surf, (0, 0, 0, 255), surf.get_rect(), 2)
        return surf

    # -----------------------------------------------------------------
    # BACKGROUNDS
    # -----------------------------------------------------------------

    def get_background(self, filename: str) -> pygame.Surface:
        """Load + scale a background JPG to 1280×720 (per §10.4)."""
        if filename in self._bg_cache:
            self._bg_cache.move_to_end(filename)
            return self._bg_cache[filename]

        path = BACKGROUNDS_DIR / filename
        if not path.exists():
            surf = self._get_placeholder(SCREEN_WIDTH, SCREEN_HEIGHT)
        else:
            try:
                loaded = pygame.image.load(str(path)).convert()
                surf = pygame.transform.smoothscale(
                    loaded, (SCREEN_WIDTH, SCREEN_HEIGHT)
                )
            except (pygame.error, FileNotFoundError):
                surf = self._get_placeholder(SCREEN_WIDTH, SCREEN_HEIGHT)

        self._bg_cache[filename] = surf
        self._evict(self._bg_cache)
        return surf

    # -----------------------------------------------------------------
    # MOTION SPRITES (player + enemy)
    # -----------------------------------------------------------------

    def _list_motion_frames(self, folder: str) -> list[Path]:
        """Return sorted list of `N.png` frame files for a motion folder.

        Per §9.10: prefers simple numeric files (`1.png` … `N.png`) over
        `DefineSprite_*_MotionSource_*.png` subsets.

        Stage 91 — caches the file list per folder (per DEVELOPMENT_RULES §8.2)
        to avoid repeated directory scanning when a frame isn't in the sprite
        cache. Returns a list (mutable copy for backward compat with callers).
        """
        cached = self._frame_files.get(folder)
        if cached is not None:
            return list(cached)

        folder_path = EXTRACTED_DIR / folder
        if not folder_path.is_dir():
            self._frame_files[folder] = ()
            return []

        files: list[Path] = []
        for entry in folder_path.iterdir():
            if not entry.is_file() or entry.suffix.lower() != ".png":
                continue
            stem = entry.stem
            if stem.isdigit():
                files.append(entry)
        # Numeric sort by integer value of filename stem.
        files.sort(key=lambda p: int(p.stem))
        # Cache as immutable tuple.
        self._frame_files[folder] = tuple(files)
        return files

    def get_motion_frame_count(self, folder: str) -> int:
        """Return the number of available frames for a motion folder."""
        if folder in self._frame_counts:
            return self._frame_counts[folder]
        files = self._list_motion_frames(folder)
        count = len(files)
        self._frame_counts[folder] = count
        return count

    def get_motion_sprite(
        self,
        folder: str,
        frame_idx: int,
        target_w: int = BODY_SPRITE_W,
        target_h: int = BODY_SPRITE_H,
        flip: bool = False,
        preserve_aspect: bool = True,
    ) -> pygame.Surface:
        """Load + scale + flip a motion sprite frame.

        Args:
            folder: directory name under `assets/extracted/`.
            frame_idx: 0-based frame index. Wraps modulo available frames.
            target_w/target_h: target canvas size.
            flip: if True, horizontal flip.
            preserve_aspect: if True, scale with aspect ratio preservation
                (letterbox on transparent canvas). If False, stretch to fill.

        Returns:
            Scaled RGBA pygame.Surface (never None — placeholder on error).
        """
        cache_key = (folder, frame_idx, target_w, target_h, flip, preserve_aspect)
        if cache_key in self._motion_cache:
            self._motion_cache.move_to_end(cache_key)
            return self._motion_cache[cache_key]

        files = self._list_motion_frames(folder)
        if not files:
            surf = self._get_placeholder(target_w, target_h)
            self._motion_cache[cache_key] = surf
            self._evict(self._motion_cache)
            return surf

        idx = frame_idx % len(files)
        path = files[idx]

        try:
            loaded = pygame.image.load(str(path)).convert_alpha()
            src_w, src_h = loaded.get_size()

            if preserve_aspect and src_w > 0 and src_h > 0:
                scale = target_h / src_h
                if src_w * scale > target_w:
                    scale = target_w / src_w
                scaled_w = max(1, int(src_w * scale))
                scaled_h = max(1, int(src_h * scale))
                scaled = pygame.transform.smoothscale(loaded, (scaled_w, scaled_h))
                canvas = pygame.Surface((target_w, target_h), pygame.SRCALPHA)
                canvas.blit(scaled, ((target_w - scaled_w) // 2, (target_h - scaled_h) // 2))
                surf = canvas
            else:
                surf = pygame.transform.smoothscale(loaded, (target_w, target_h))

            if flip:
                surf = pygame.transform.flip(surf, True, False)
        except (pygame.error, FileNotFoundError):
            surf = self._get_placeholder(target_w, target_h)

        self._motion_cache[cache_key] = surf
        self._evict(self._motion_cache)
        return surf

    # -----------------------------------------------------------------
    # AVATAR (HUD portrait)
    # -----------------------------------------------------------------

    def get_avatar(
        self,
        filename: str,
        size: int = 64,
    ) -> pygame.Surface:
        """Load + scale a HUD avatar (GIF/PNG) to a square `size`×`size`.

        Used in the top HUD bar next to HP/MP bars.
        Returns a placeholder if file is missing (per rule 10).
        """
        cache_key = f"{filename}:{size}"
        if cache_key in self._avatar_cache:
            self._avatar_cache.move_to_end(cache_key)
            return self._avatar_cache[cache_key]

        path = AVATAR_DIR / filename
        if not path.exists():
            surf = self._get_placeholder(size, size)
        else:
            try:
                loaded = pygame.image.load(str(path)).convert_alpha()
                surf = pygame.transform.smoothscale(loaded, (size, size))
            except (pygame.error, FileNotFoundError):
                surf = self._get_placeholder(size, size)

        self._avatar_cache[cache_key] = surf
        self._evict(self._avatar_cache)
        return surf

    def get_enemy_avatar_placeholder(self, size: int = 64) -> pygame.Surface:
        """Generate a procedural samurai-themed placeholder for the enemy avatar.

        Used because no enemy avatar GIF was provided (per §13.1 Q2).
        Marked as INFERRED design choice — not a TODO.
        """
        cache_key = f"__enemy_placeholder__:{size}"
        if cache_key in self._avatar_cache:
            self._avatar_cache.move_to_end(cache_key)
            return self._avatar_cache[cache_key]

        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        # Dark red background circle (samurai armor color).
        pygame.draw.circle(surf, (80, 16, 16), (size // 2, size // 2), size // 2 - 2)
        pygame.draw.circle(surf, (180, 30, 30), (size // 2, size // 2), size // 2 - 2, 2)

        # Stylized kabuto helmet horns (gold triangles).
        cx, cy = size // 2, size // 2
        horn_w = max(4, size // 8)
        horn_h = max(8, size // 4)
        # Left horn.
        pygame.draw.polygon(
            surf,
            (234, 179, 8),
            [(cx - 6, cy - 4), (cx - 6 - horn_w, cy - horn_h), (cx - 6 - horn_w, cy - 4)],
        )
        # Right horn.
        pygame.draw.polygon(
            surf,
            (234, 179, 8),
            [(cx + 6, cy - 4), (cx + 6 + horn_w, cy - horn_h), (cx + 6 + horn_w, cy - 4)],
        )
        # White menpo mask (small rectangle for face).
        mask_w = max(8, size // 3)
        mask_h = max(10, size // 3)
        mask_rect = pygame.Rect(cx - mask_w // 2, cy - 2, mask_w, mask_h)
        pygame.draw.rect(surf, (240, 240, 240), mask_rect, border_radius=3)
        # Eyes (two dark dots).
        eye_y = cy + 2
        pygame.draw.circle(surf, (20, 20, 20), (cx - 5, eye_y), 2)
        pygame.draw.circle(surf, (20, 20, 20), (cx + 5, eye_y), 2)

        self._avatar_cache[cache_key] = surf
        self._evict(self._avatar_cache)
        return surf

    # -----------------------------------------------------------------
    # ENEMY AVATAR (Stage 10 — real samurai face portrait)
    # -----------------------------------------------------------------

    # Map mob_id → avatar filename under AVATAR_DIR.
    # Stage 46 — all 12 mobs mapped by role_id to reuse the 3 real portraits:
    #   role 10001 → userface_n10001.png (samurai)
    #   role 10002 → userface_n10002.png (samurai 2)
    #   role 10004 → userface_n10004.png (samurai 3)
    _MOB_AVATAR_FILES: dict[str, str] = {
        "mob_1": "userface_n10001.png",
        "mob_2": "userface_n10002.png",
        "mob_3": "userface_n10004.png",
        # Location 2 (L10/L15/L20)
        "mob_4": "userface_n10001.png",
        "mob_5": "userface_n10002.png",
        "mob_6": "userface_n10004.png",
        # Location 3 (L20/L25/L30)
        "mob_7": "userface_n10001.png",
        "mob_8": "userface_n10002.png",
        "mob_9": "userface_n10004.png",
        # Location 4 (L30/L35/L40)
        "mob_10": "userface_n10001.png",
        "mob_11": "userface_n10002.png",
        "mob_12": "userface_n10004.png",
        # Stage 79 — Flower mob avatar.
        "flower_1": "userface_n10074.png",
    }

    def get_enemy_avatar(self, mob_id: str, size: int = 64) -> pygame.Surface:
        """Load an enemy avatar for the given mob_id.

        Stage 10:
          * mob_1 (samurai): loads `userface_n10001.png` from AVATAR_DIR.
            This is the real samurai face portrait.
          * Mobs without a file entry: `get_enemy_avatar_placeholder(size)`
            (procedural samurai helmet drawn at the requested size).

        Stage 154 — БЕЗ РЕСЕМПЛИНГА портретов: `size` трактуется как размер
        СЛОТА, а не как принудительный размер картинки. Если портрет влезает
        в слот (82×82 в слоте 82 на 2К, 51×51 в слоте 82) — возвращается
        ОРИГИНАЛ; масштабирование выполняется ТОЛЬКО когда портрет крупнее
        слота (даунскейл, чтобы не выпирал). Раньше любой размер прогонялся
        через smoothscale — 82→34 на 720p и 82→68 на 2К давали мыло.
        Вызывающий центрирует полученную поверхность в слоте.

        LRU-cached (keyed by mob_id + slot size). Never returns None (per rule 10).
        """
        # For mobs without a real avatar file, fall back to procedural placeholder.
        filename = self._MOB_AVATAR_FILES.get(mob_id)
        if filename is None:
            return self.get_enemy_avatar_placeholder(size)

        cache_key = f"__enemy_avatar__:{mob_id}:{size}"
        if cache_key in self._avatar_cache:
            self._avatar_cache.move_to_end(cache_key)
            return self._avatar_cache[cache_key]

        path = AVATAR_DIR / filename
        if not path.exists():
            # File missing → fall back to procedural placeholder.
            surf = self.get_enemy_avatar_placeholder(size)
        else:
            try:
                loaded = pygame.image.load(str(path)).convert_alpha()
                iw, ih = loaded.get_size()
                if iw <= size and ih <= size:
                    # Stage 154 — влезает в слот: оригинал, без ресемплинга.
                    surf = loaded
                else:
                    # Крупнее слота — даунскейл с сохранением пропорций.
                    k = min(size / iw, size / ih)
                    surf = pygame.transform.smoothscale(
                        loaded, (max(1, int(iw * k)), max(1, int(ih * k)))
                    )
            except (pygame.error, FileNotFoundError):
                surf = self.get_enemy_avatar_placeholder(size)

        self._avatar_cache[cache_key] = surf
        self._evict(self._avatar_cache)
        return surf

    # -----------------------------------------------------------------
    # SKILL ICONS (Stage 10 — Crystal Blade icon in skill slots)
    # -----------------------------------------------------------------

    def get_skill_icon(self, skill_id: int, size: int = 36) -> pygame.Surface:
        """Load + scale a skill icon by skill_id.

        Stage 10 — used for the Crystal Blade skill icon in the char sheet
        skill grid (slot 0) and the MAP skills modal (slot 0).

        Filename pattern: `icon_skill{skill_id}.png` under SKILL_ICON_DIR.
        For skill_id=12006 → `icon_skill12006.png` (Crystal Blade icon).

        LRU-cached (keyed by skill_id + size). Never returns None (per rule 10).
        Fallback: procedural colored square with the skill_id text rendered
        in the center (emerald bg, white text) — explicit design choice,
        not a TODO.
        """
        cache_key = f"__skill_icon__:{skill_id}:{size}"
        if cache_key in self._skill_icon_cache:
            self._skill_icon_cache.move_to_end(cache_key)
            return self._skill_icon_cache[cache_key]

        filename = f"icon_skill{skill_id}.png"
        path = SKILL_ICON_DIR / filename
        if not path.exists():
            # Procedural fallback: emerald square with skill_id text.
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            pygame.draw.rect(surf, (16, 185, 129), surf.get_rect(), border_radius=4)
            pygame.draw.rect(surf, (255, 255, 255), surf.get_rect(), 1, border_radius=4)
            font = pygame.font.SysFont("dejavusans,arial", max(8, size // 3), bold=True)
            text_surf = font.render(str(skill_id), True, (255, 255, 255))
            text_rect = text_surf.get_rect(center=(size // 2, size // 2))
            surf.blit(text_surf, text_rect.topleft)
        else:
            try:
                loaded = pygame.image.load(str(path)).convert_alpha()
                surf = pygame.transform.smoothscale(loaded, (size, size))
            except (pygame.error, FileNotFoundError):
                # On load error → procedural placeholder.
                surf = pygame.Surface((size, size), pygame.SRCALPHA)
                pygame.draw.rect(surf, (16, 185, 129), surf.get_rect(), border_radius=4)
                font = pygame.font.SysFont("dejavusans,arial", max(8, size // 3), bold=True)
                text_surf = font.render(str(skill_id), True, (255, 255, 255))
                text_rect = text_surf.get_rect(center=(size // 2, size // 2))
                surf.blit(text_surf, text_rect.topleft)

        self._skill_icon_cache[cache_key] = surf
        self._evict(self._skill_icon_cache)
        return surf

    # -----------------------------------------------------------------
    # DEBUFF ICONS (Stage 11 — procedural icons for status effects)
    # -----------------------------------------------------------------

    # Procedural color palette for each status effect's debuff icon.
    # Stage 11 — drawn procedurally (no asset files needed). Used by
    # _render_fighter to render a small 32×32 debuff icon above any
    # fighter with an active status effect (e.g., frozen → ice crystal).
    _DEBUFF_COLORS: dict[str, tuple[int, int, int]] = {
        "frozen": (129, 212, 250),   # light blue-300
        "stun": (251, 191, 36),      # amber-400
        "paralyze": (167, 139, 250), # violet-400
        "poison": (132, 204, 22),    # lime-500
        "burn": (239, 68, 68),       # red-500
        "shield": (56, 189, 248),    # sky-400
    }

    def get_debuff_icon(self, status_name: str, size: int = 32) -> pygame.Surface:
        """Return a debuff icon for the given status effect.

        Stage 11 — procedural icons (colored circles + snowflake for frozen).
        Stage 12 — IMPROVED: for "freeze" and "extra_turn", use the REAL skill
        icon PNG (icon_skill12006.png for Crystal Blade, icon_skill15005.png
        for Lightning Step) instead of procedural shapes. This makes the debuff
        icon match the skill that caused it — visually clearer for the player.

        LRU-cached (keyed by status_name + size). Never returns None.

        For statuses without a skill icon (stun, poison, burn, paralyze),
        falls back to procedural colored circle + 1-letter label.
        """
        cache_key = f"__debuff_icon__:{status_name}:{size}"
        if cache_key in self._skill_icon_cache:
            self._skill_icon_cache.move_to_end(cache_key)
            return self._skill_icon_cache[cache_key]

        # Stage 12 — map status names to skill icon filenames.
        # "freeze" → Crystal Blade icon (12006) — the skill that causes freeze.
        # "extra_turn" → Lightning Step icon (15005) — the skill that grants extra turn.
        # Stage 13 — added 3 new status → skill icon mappings:
        # "thunder_cloud" → Thunderstorm icon (14001).
        # "poison" → Poison Dart icon (18003).
        # "shield" → Crystal Shield icon (14002).
        _STATUS_TO_SKILL_ICON: dict[str, str] = {
            "freeze": "icon_skill12006.png",
            "extra_turn": "icon_skill15005.png",
            "thunder_cloud": "icon_skill14001.png",
            "poison": "icon_skill18003.png",
            "shield": "icon_skill14002.png",
        }
        skill_icon_filename = _STATUS_TO_SKILL_ICON.get(status_name)
        if skill_icon_filename is not None:
            # Try to load the real skill icon PNG.
            icon_path = SKILL_ICON_DIR / skill_icon_filename
            if icon_path.exists():
                try:
                    loaded = pygame.image.load(str(icon_path)).convert_alpha()
                    surf = pygame.transform.smoothscale(loaded, (size, size))
                    self._skill_icon_cache[cache_key] = surf
                    self._evict(self._skill_icon_cache)
                    return surf
                except (pygame.error, FileNotFoundError):
                    pass  # fall through to procedural fallback

        # Procedural fallback (for stun, poison, burn, paralyze, or if the
        # skill icon file is missing).
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        cx = size // 2
        cy = size // 2
        radius = max(2, size // 2 - 2)
        color = self._DEBUFF_COLORS.get(status_name, (113, 113, 122))  # zinc-500 default

        if status_name in ("frozen", "freeze"):
            # Light blue circle background.
            pygame.draw.circle(surf, color, (cx, cy), radius)
            # White border.
            pygame.draw.circle(surf, (255, 255, 255), (cx, cy), radius, 1)
            # Draw a 6-pointed snowflake: 3 lines at 60° intervals.
            white = (255, 255, 255)
            arm_len = max(3, radius - 4)
            for angle_deg in (0, 60, 120):
                angle = math.radians(angle_deg)
                x2 = cx + int(arm_len * math.cos(angle))
                y2 = cy + int(arm_len * math.sin(angle))
                x1 = cx - int(arm_len * math.cos(angle))
                y1 = cy - int(arm_len * math.sin(angle))
                pygame.draw.line(surf, white, (x1, y1), (x2, y2), 1)
                # Small branch tips near each end (perpendicular).
                branch_len = max(2, arm_len // 4)
                for endpoint in ((x2, y2), (x1, y1)):
                    # Perpendicular direction.
                    px = int(branch_len * math.cos(angle + math.pi / 2))
                    py = int(branch_len * math.sin(angle + math.pi / 2))
                    pygame.draw.line(surf, white, endpoint, (endpoint[0] + px, endpoint[1] + py), 1)
                    pygame.draw.line(surf, white, endpoint, (endpoint[0] - px, endpoint[1] - py), 1)
        else:
            # Generic debuff: colored circle + 1-letter label.
            pygame.draw.circle(surf, color, (cx, cy), radius)
            pygame.draw.circle(surf, (255, 255, 255), (cx, cy), radius, 1)
            label = status_name[0].upper() if status_name else "?"
            font = pygame.font.SysFont("dejavusans,arial", max(10, size // 2), bold=True)
            label_surf = font.render(label, True, (255, 255, 255))
            label_rect = label_surf.get_rect(center=(cx, cy))
            surf.blit(label_surf, label_rect.topleft)

        self._skill_icon_cache[cache_key] = surf
        self._evict(self._skill_icon_cache)
        return surf

    # -----------------------------------------------------------------
    # FACING DETECTION (per §8.2)
    # -----------------------------------------------------------------

    def detect_sprite_facing(
        self,
        surface: pygame.Surface,
        cache_key: str = "",
    ) -> SpriteFacing:
        """Detect intrinsic facing of a side-view sprite.

        Uses alpha-mass heuristic on the upper 60% of the sprite
        (head + torso — legs are excluded as usually centered).

        For known folders, the cached intrinsic facing from `INTRINSIC_FACING`
        is used directly (alpha-mass verified Stage 3 — single source of truth).
        For unknown folders, the heuristic is computed on the supplied surface.

        Args:
            surface: source sprite (RGBA). Used only if cache_key is not cached.
            cache_key: unique key (e.g., folder name) to memoize the result.

        Returns:
            SpriteFacing.LEFT or SpriteFacing.RIGHT.
        """
        if cache_key and cache_key in self._facing_cache:
            return self._facing_cache[cache_key]

        w, h = surface.get_size()
        if w == 0 or h == 0:
            return SpriteFacing.RIGHT

        # Upper 60% of the sprite (head + torso).
        upper_h = max(1, int(h * 0.6))
        try:
            arr = pygame.surfarray.array_alpha(surface)
            # arr shape: (w, h). Take upper portion.
            upper = arr[:, :upper_h]
            mid = w // 2
            left_mass = int(upper[:mid].sum())
            right_mass = int(upper[mid:].sum())
        except (pygame.error, ValueError):
            return SpriteFacing.RIGHT

        facing = SpriteFacing.LEFT if left_mass > right_mass else SpriteFacing.RIGHT
        if cache_key:
            self._facing_cache[cache_key] = facing
        return facing

    def needs_flip_for_player(self, folder: str) -> bool:
        """Return True if the player sprite (in this folder) needs a horizontal
        flip to face RIGHT.

        HARD RULE (per config.PLAYER_MUST_FACE_RIGHT): player ALWAYS faces RIGHT
        in battle. Player is always positioned on the left side of the arena.

        Logic: flip only if intrinsic facing is LEFT (→ after flip, faces RIGHT).
        If intrinsic is already RIGHT, no flip needed.
        """
        intrinsic = self.detect_sprite_facing(pygame.Surface((1, 1)), folder)
        return intrinsic == SpriteFacing.LEFT

    def needs_flip_for_enemy(self, folder: str, mob_id: str = "") -> bool:
        """Return True if the enemy sprite (in this folder) needs a horizontal
        flip to face LEFT.

        HARD RULE: ALL enemies face LEFT in
        battle, regardless of mob_id. Player is always on the left side of the
        arena, so the enemy must look toward the player (LEFT).

        Logic: flip only if intrinsic facing is RIGHT (→ after flip, faces LEFT).
        If intrinsic is already LEFT, no flip needed.

        Note: the old §7.7 rule ("mob_1 ALWAYS flip") was based on an erroneous
        VLM Stage 1 reading (which said samurai intrinsic=RIGHT). Alpha-mass
        verification Stage 3 showed samurai intrinsic=LEFT, so no flip is needed.
        """
        intrinsic = self.detect_sprite_facing(pygame.Surface((1, 1)), folder)
        return intrinsic == SpriteFacing.RIGHT

    # -----------------------------------------------------------------
    # LRU EVICTION
    # -----------------------------------------------------------------

    def _evict(self, cache: OrderedDict) -> None:
        """Evict oldest entries when cache exceeds `_LRU_MAX`."""
        while len(cache) > _LRU_MAX:
            cache.popitem(last=False)

    # -----------------------------------------------------------------
    # Stage 91 — overlay + font cache (per DEVELOPMENT_RULES §8.1)
    # -----------------------------------------------------------------

    def get_overlay(self, alpha: int = 60) -> pygame.Surface:
        """Return a cached full-screen SRCALPHA overlay surface.

        Per DEVELOPMENT_RULES §8.1: avoids creating a new
        ``pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), SRCALPHA)`` every
        frame in render methods. The overlay is a black surface with the
        given alpha (0-255). Common values: 60, 80, 140.

        Args:
            alpha: alpha value 0-255 (default 60).

        Returns:
            A full-screen SRCALPHA surface filled with (0,0,0,alpha).
        """
        cached = self._overlay_cache.get(alpha)
        if cached is not None:
            return cached
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        surf.fill((0, 0, 0, alpha))
        self._overlay_cache[alpha] = surf
        return surf
