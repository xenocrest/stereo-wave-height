"""Read-only wall-clock and WASS internal-stage profiling utilities."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import subprocess
import time
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class CommandTiming:
    """Measured external command duration and captured output."""

    seconds: float
    return_code: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class StereoInternalTiming:
    """Substages reported by WASS's own stereo timing table."""

    data_load_seconds: float
    rectification_seconds: float
    dense_stereo_seconds: float
    triangulation_seconds: float
    zgap_seconds: float
    outlier_removal_seconds: float
    plane_fitting_seconds: float
    plane_refinement_seconds: float
    total_seconds: float


def time_command(argv: Sequence[str], *, cwd: str | Path | None = None) -> CommandTiming:
    """Run one unchanged external command and measure monotonic wall time."""
    if not argv:
        raise ValueError("argv must not be empty")
    started = time.perf_counter()
    completed = subprocess.run(
        list(argv), cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
    )
    elapsed = time.perf_counter() - started
    return CommandTiming(elapsed, completed.returncode, completed.stdout, completed.stderr)


def parse_stereo_internal_timing(log_text: str) -> StereoInternalTiming:
    """Parse the timing table emitted by the confirmed WASS runtime."""
    labels = {
        "Data load": "data_load_seconds",
        "Rectification": "rectification_seconds",
        "Dense Stereo": "dense_stereo_seconds",
        "Triangulation": "triangulation_seconds",
        "Z-gap stats": "zgap_seconds",
        "Outlier removal": "outlier_removal_seconds",
        "Plane fitting": "plane_fitting_seconds",
        "Plane refinement": "plane_refinement_seconds",
        "TOTAL": "total_seconds",
    }
    values: dict[str, float] = {}
    for label, field in labels.items():
        match = re.search(rf"\|\s*{re.escape(label)}\s*\|\s*([0-9.eE+-]+)\s*\|", log_text)
        if match is None:
            raise ValueError(f"WASS stereo timing field is missing: {label}")
        values[field] = float(match.group(1))
    return StereoInternalTiming(**values)


def aggregate_profiles(frames: list[dict[str, float]]) -> dict[str, dict[str, float]]:
    """Return count/mean/min/max for every numeric timing field."""
    if not frames:
        raise ValueError("at least one frame profile is required")
    keys = tuple(frames[0])
    if any(tuple(frame) != keys for frame in frames):
        raise ValueError("all frame profiles must have identical ordered fields")
    result: dict[str, dict[str, float]] = {}
    for key in keys:
        values = np.asarray([frame[key] for frame in frames], dtype=np.float64)
        if not np.all(np.isfinite(values)) or np.any(values < 0):
            raise ValueError("profile timings must be finite and non-negative")
        result[key] = {
            "mean": float(values.mean()), "minimum": float(values.min()), "maximum": float(values.max())
        }
    return result


def write_profile_json(path: str | Path, payload: dict[str, object]) -> Path:
    """Write a small machine-readable performance report."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return destination


def internal_timing_dict(timing: StereoInternalTiming) -> dict[str, float]:
    """Convert a frozen parsed timing to a JSON-ready mapping."""
    return asdict(timing)
