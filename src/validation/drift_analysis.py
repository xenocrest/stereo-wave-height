"""Static-reference temporal and spatial stability diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from .wave_statistics import height_statistics


@dataclass(frozen=True)
class TemporalDrift:
    """Temporal drift of per-frame spatial mean height."""

    reference_mean: float
    signed_drift: tuple[float, ...]
    maximum_absolute: float
    rms: float
    peak_to_peak: float


def temporal_mean_drift(frame_heights: list[np.ndarray], *, reference_index: int = 0) -> TemporalDrift:
    """Compare each frame's raw spatial mean with one declared reference."""
    if not frame_heights or not 0 <= reference_index < len(frame_heights):
        raise ValueError("frame heights and a valid reference_index are required")
    means = np.asarray([height_statistics(values).mean for values in frame_heights])
    drift = means - means[reference_index]
    return TemporalDrift(
        reference_mean=float(means[reference_index]),
        signed_drift=tuple(float(value) for value in drift),
        maximum_absolute=float(np.max(np.abs(drift))),
        rms=float(math.sqrt(float(np.mean(drift**2)))),
        peak_to_peak=float(drift.max() - drift.min()),
    )


def spatial_deviation(height: np.ndarray) -> dict[str, float]:
    """Measure within-frame variation about that frame's spatial mean."""
    values = np.asarray(height, dtype=np.float64)
    if values.ndim != 1 or values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("height must be a non-empty finite one-dimensional array")
    centered = values - values.mean()
    return {
        "rms": float(np.sqrt(np.mean(centered**2))),
        "p95_absolute": float(np.percentile(np.abs(centered), 95.0)),
        "maximum_absolute": float(np.max(np.abs(centered))),
    }
