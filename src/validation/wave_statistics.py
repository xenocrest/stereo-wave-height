"""General statistics for reconstructed water-height observations."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


@dataclass(frozen=True)
class HeightStatistics:
    """Scalar height statistics in the same unit as the input."""

    count: int
    mean: float
    median: float
    rms: float
    minimum: float
    maximum: float
    peak_to_peak: float
    p5: float
    p95: float
    p95_absolute: float


def height_statistics(height: np.ndarray) -> HeightStatistics:
    """Summarize finite height observations without rejection or filtering."""
    values = np.asarray(height, dtype=np.float64)
    if values.ndim != 1 or values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("height must be a non-empty finite one-dimensional array")
    return HeightStatistics(
        count=int(values.size),
        mean=float(values.mean()),
        median=float(np.median(values)),
        rms=float(math.sqrt(float(np.mean(values**2)))),
        minimum=float(values.min()),
        maximum=float(values.max()),
        peak_to_peak=float(values.max() - values.min()),
        p5=float(np.percentile(values, 5.0)),
        p95=float(np.percentile(values, 95.0)),
        p95_absolute=float(np.percentile(np.abs(values), 95.0)),
    )


def moving_average_baseline(series: np.ndarray, *, window_frames: int) -> np.ndarray:
    """Return a centered low-frequency moving mean with truncated edges.

    The caller must configure an odd window of at least three frames.  This is
    an analysis transform and never mutates the raw time series.
    """
    values = np.asarray(series, dtype=np.float64)
    if values.ndim != 1 or values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("series must be a non-empty finite one-dimensional array")
    if not isinstance(window_frames, int) or window_frames < 3 or window_frames % 2 == 0:
        raise ValueError("window_frames must be an odd integer of at least three")
    if window_frames > values.size:
        raise ValueError("window_frames cannot exceed the series length")
    radius = window_frames // 2
    return np.asarray([
        values[max(0, index - radius):min(values.size, index + radius + 1)].mean()
        for index in range(values.size)
    ])


def remove_low_frequency_drift(series: np.ndarray, *, window_frames: int) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(baseline, raw-baseline)`` without overwriting raw values."""
    values = np.asarray(series, dtype=np.float64)
    baseline = moving_average_baseline(values, window_frames=window_frames)
    return baseline, values - baseline


def significant_wave_height(wave_heights: np.ndarray, *, minimum_waves: int = 3) -> float | None:
    """Return mean of the highest one-third individual wave heights.

    ``wave_heights`` must already contain independently identified complete
    crest-to-trough wave heights.  This function deliberately does not infer
    waves from a short or irregularly sampled record.
    """
    values = np.asarray(wave_heights, dtype=np.float64)
    if values.ndim != 1 or not np.all(np.isfinite(values)) or np.any(values < 0):
        raise ValueError("wave_heights must be a finite non-negative one-dimensional array")
    if values.size < minimum_waves:
        return None
    count = max(1, int(math.ceil(values.size / 3.0)))
    return float(np.sort(values)[-count:].mean())
