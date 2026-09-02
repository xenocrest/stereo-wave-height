"""Shared development/PyInstaller entry point, including backend command mode."""
from __future__ import annotations

import sys
import traceback
from pathlib import Path


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--backend-single-frame":
        config=Path(sys.argv[2]).resolve()
        try:
            from src.reconstruction.run_single_frame import main as backend_main
            sys.argv = [sys.argv[0], "--config", str(config)]
            return backend_main()
        except Exception:
            # A windowed PyInstaller process has no console.  Preserve the
            # actual backend exception beside its request instead of leaving
            # the GUI with an opaque exit code or an invisible error dialog.
            config.with_suffix(".backend_crash.log").write_text(traceback.format_exc(),encoding="utf-8")
            return 1
    if len(sys.argv) != 1:
        print("Usage: StereoWaveHeightDemo.exe [--backend-single-frame CONFIG]", file=sys.stderr)
        return 2
    from .main_window import StereoWaveHeightApplication
    StereoWaveHeightApplication().run()
    return 0
