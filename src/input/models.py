"""Canonical input data models independent of camera or video vendor."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True)
class VideoMetadata:
    """Traceable metadata reported by a configured video backend."""

    path: Path
    width_px: int
    height_px: int
    frame_count: int
    fps: float
    duration_s: float
    timestamp_source: str

    def __post_init__(self) -> None:
        if not self.path.is_file():
            raise FileNotFoundError(self.path)
        if self.width_px <= 0 or self.height_px <= 0 or self.frame_count <= 0:
            raise ValueError("video dimensions and frame_count must be positive")
        if not np.isfinite(self.fps) or self.fps <= 0:
            raise ValueError("video fps must be explicitly positive")
        expected = self.frame_count / self.fps
        if not np.isfinite(self.duration_s) or self.duration_s <= 0:
            raise ValueError("video duration must be explicitly positive")
        if not np.isclose(self.duration_s, expected, rtol=0.0, atol=max(1e-9, 1/self.fps)):
            raise ValueError("duration_s is inconsistent with frame_count/fps")
        if not self.timestamp_source or self.timestamp_source.upper() in {"UNKNOWN", "TODO"}:
            raise ValueError("timestamp_source must be explicit")


@dataclass(frozen=True)
class StereoFramePair:
    """Unified synchronized pair consumed by all downstream stages."""

    pair_id: int
    left_index: int
    right_index: int
    left_timestamp_s: float
    right_timestamp_s: float
    left_frame: Any
    right_frame: Any
    timestamp_source: str

    def __post_init__(self) -> None:
        if min(self.pair_id, self.left_index, self.right_index) < 0:
            raise ValueError("pair and frame indices must be non-negative")
        if not np.isfinite(self.left_timestamp_s) or not np.isfinite(self.right_timestamp_s):
            raise ValueError("frame timestamps must be finite seconds")
        if self.left_frame is None or self.right_frame is None:
            raise ValueError("both frame payloads are required")
        if not self.timestamp_source:
            raise ValueError("timestamp provenance is required")
