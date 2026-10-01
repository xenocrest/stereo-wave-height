"""Capture the three real Qt result views from one completed scientific run."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from PySide6.QtWidgets import QApplication

from app import core
from app.main import MainWindow


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("project")
    parser.add_argument("run_report")
    parser.add_argument("output")
    parser.add_argument("--reference-time", type=float, required=True)
    parser.add_argument("--target-time", type=float, required=True)
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)
    window = MainWindow()
    window.config = core.read_project(args.project)
    window._populate()
    window.resize(1408, 864)
    window.show()
    window.slider.setValue(int(args.reference_time * 1000))
    window._set_static_reference()
    window.slider.setValue(int(args.target_time * 1000))
    window.tabs.setCurrentIndex(1)
    window._open_run_path(args.run_report)
    app.processEvents()
    if window.result is None:
        raise RuntimeError("GUI did not load the official result")
    window._confirm_reference()
    for mode in ("raw", "cloud", "overlay"):
        window._display_mode(mode)
        app.processEvents()
        if not window.grab().save(str(out / f"{mode}.png")):
            raise RuntimeError(f"Failed to save {mode} screenshot")
    window.close()


if __name__ == "__main__":
    main()
