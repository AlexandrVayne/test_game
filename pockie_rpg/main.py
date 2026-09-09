"""Entry point for Pockie RPG.

Usage:
    python -m pockie_rpg.main            # pygame UI (default)
    python -m pockie_rpg.main --ui pygame  # explicit pygame
    python -m pockie_rpg.main --ui console # legacy console (not implemented)

Headless test:
    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m pockie_rpg.main
"""
from __future__ import annotations

import argparse
import os
import sys


def _make_windows_dpi_aware() -> None:
    """Stage 158 — объявить процесс DPI-aware (Windows, ДО pygame.init).

    При системном масштабе 125% НЕ-DPI-aware процесс видит ВИРТУАЛИЗИРОВАННЫЙ
    рабочий стол (2560×1440 → 2048×1152): get_desktop_sizes() врёт, окно
    создаётся логическим, а ОС растягивает его до физических пикселей —
    мыло на весь экран + нативный Hi-DPI-путь 2К не включается. DPI-aware
   (manifest-level) даёт процессу ФИЗИЧЕСКИЕ 2560×1440 — pygame рисует
    1:1, без системного ресемплинга. Не-Windows / вызов не удался — молча
    пропускаем (поведение как раньше).
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        # Per-Monitor v2 (Win10 1703+); откат на системный (Win 8.1+) и
        # legacy SetProcessDPIReport (Vista+).
        try:
            # PROCESS_PER_MONITOR_DPI_AWARE = 2.
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4.
            ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pockie-rpg",
        description="Pockie RPG — local 2D autobattler (pygame-ce).",
    )
    parser.add_argument(
        "--ui",
        choices=["pygame", "console"],
        default="pygame",
        help="UI backend (default: pygame).",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run in headless mode (no display/audio — for CI/testing).",
    )
    return parser.parse_args()


def main() -> int:
    """Main entry point. Returns exit code."""
    args = _parse_args()

    if args.headless:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

    if args.ui == "console":
        print("Console UI not implemented in Stage 2. Use --ui pygame (default).")
        return 1

    # Stage 158 — ДО создания окна: без этого Windows 125% отдаёт pygame
    # виртуализированные 2048×1152 вместо физических 2560×1440.
    _make_windows_dpi_aware()

    # Import pygame UI lazily — avoids pygame init when --ui=console.
    from pockie_rpg.ui.pygame_ui import PygameUI

    try:
        ui = PygameUI()
        ui.run()
    except KeyboardInterrupt:
        # Ctrl+C в терминале — штатный выход без traceback
        # (сам ui.run() тоже страхуется и сбрасывает pending-сейв).
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
