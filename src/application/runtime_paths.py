"""Resolve development and frozen-distribution paths without relying on cwd."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sys


@dataclass(frozen=True)
class RuntimePaths:
    application_root: Path
    experiment: Path
    ffmpeg: Path
    session_root: Path
    frozen: bool


def resolve_runtime_paths(repository: Path | None = None, *, executable: Path | None = None,
                          frozen: bool | None = None) -> RuntimePaths:
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    if is_frozen:
        root = (executable or Path(sys.executable)).resolve().parent
        experiment = root / "resources" / "HomeTank_004"
        ffmpeg = root / "runtime" / "ffmpeg" / "ffmpeg.exe"
    else:
        root = (repository or Path(__file__).resolve().parents[2]).resolve()
        experiment = root / "experiments" / "real_video" / "HomeTank_004"
        ffmpeg = Path(os.environ.get("STEREO_WAVE_HEIGHT_FFMPEG", "D:/FormatFactory/ffmpeg.exe"))
    local = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
    session_root = Path(os.environ.get("STEREO_WAVE_HEIGHT_GUI_SESSIONS", str(local / "StereoWaveHeightDemo" / "gui_sessions")))
    return RuntimePaths(root, experiment, ffmpeg.resolve(), session_root.resolve(), is_frozen)
