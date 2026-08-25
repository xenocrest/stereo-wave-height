"""Height-sample loading and explicit common-ROI selection.

This module operates after WASS reconstruction.  It does not interpolate,
filter, alter calibration, or infer correspondence between irregular clouds.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class HeightSamples:
    """Irregular metric water-height observations for one timestamp."""

    x_m: np.ndarray
    y_m: np.ndarray
    height_m: np.ndarray
    valid_mask: np.ndarray


@dataclass(frozen=True)
class PhysicalRoi:
    """Closed axis-aligned ROI in the reconstruction coordinate system."""

    x_min_m: float
    x_max_m: float
    y_min_m: float
    y_max_m: float


def physical_roi_from_xywh(*, x_m: float, y_m: float, width_m: float, height_m: float) -> PhysicalRoi:
    """Build a metric analysis ROI from origin and positive extent."""
    values = np.asarray([x_m, y_m, width_m, height_m], dtype=np.float64)
    if not np.all(np.isfinite(values)) or width_m <= 0 or height_m <= 0:
        raise ValueError("physical ROI origin must be finite and extents must be positive")
    return PhysicalRoi(float(x_m), float(x_m + width_m), float(y_m), float(y_m + height_m))


def load_height_samples(path: str | Path) -> HeightSamples:
    """Load one pipeline NPZ without modifying or filling its observations."""
    with np.load(Path(path), allow_pickle=False) as data:
        required = {"x_m", "y_m", "height_m", "water_mask"}
        missing = required.difference(data.files)
        if missing:
            raise ValueError(f"height sample file lacks fields: {sorted(missing)}")
        x = np.asarray(data["x_m"], dtype=np.float64)
        y = np.asarray(data["y_m"], dtype=np.float64)
        height = np.asarray(data["height_m"], dtype=np.float64)
        mask = np.asarray(data["water_mask"])
    if x.ndim != 1 or x.shape != y.shape or x.shape != height.shape or x.shape != mask.shape:
        raise ValueError("height samples must be equally shaped one-dimensional arrays")
    if mask.dtype != np.bool_:
        raise ValueError("water_mask must have boolean dtype")
    finite = np.isfinite(x) & np.isfinite(y) & np.isfinite(height)
    valid = mask & finite
    if not np.any(valid):
        raise ValueError("height sample file has no finite valid water observations")
    return HeightSamples(x, y, height, valid)


def common_observed_roi(frames: list[HeightSamples]) -> PhysicalRoi:
    """Return intersection of per-frame valid XY bounding boxes.

    This is a physical coordinate-domain intersection, not point
    correspondence and not an interpolated common grid.
    """
    if not frames:
        raise ValueError("at least one frame is required")
    x_min = max(float(frame.x_m[frame.valid_mask].min()) for frame in frames)
    x_max = min(float(frame.x_m[frame.valid_mask].max()) for frame in frames)
    y_min = max(float(frame.y_m[frame.valid_mask].min()) for frame in frames)
    y_max = min(float(frame.y_m[frame.valid_mask].max()) for frame in frames)
    if x_min >= x_max or y_min >= y_max:
        raise ValueError("frames have no non-empty common physical XY bounding-box ROI")
    return PhysicalRoi(x_min, x_max, y_min, y_max)


def roi_mask(frame: HeightSamples, roi: PhysicalRoi) -> np.ndarray:
    """Select raw valid observations whose coordinates lie in ``roi``."""
    mask = (
        frame.valid_mask
        & (frame.x_m >= roi.x_min_m)
        & (frame.x_m <= roi.x_max_m)
        & (frame.y_m >= roi.y_min_m)
        & (frame.y_m <= roi.y_max_m)
    )
    if not np.any(mask):
        raise ValueError("frame has no raw observations inside the requested ROI")
    return mask


def drift_correct_spatial_mean(height_m: np.ndarray) -> np.ndarray:
    """Return an analysis-only copy with its spatial mean removed."""
    values = np.asarray(height_m, dtype=np.float64)
    if values.ndim != 1 or values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("height_m must be a non-empty finite one-dimensional array")
    return values - float(values.mean())
