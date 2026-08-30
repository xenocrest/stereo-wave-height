"""Shared development/PyInstaller entry point, including backend command mode."""
from __future__ import annotations

import sys


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--backend-single-frame":
        from src.reconstruction.run_single_frame import main as backend_main
        sys.argv = [sys.argv[0], "--config", sys.argv[2]]
        return backend_main()
    if len(sys.argv) != 1:
        print("Usage: StereoWaveHeightDemo.exe [--backend-single-frame CONFIG]", file=sys.stderr)
        return 2
    from .main_window import StereoWaveHeightApplication
    StereoWaveHeightApplication().run()
    return 0
