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
    rms: float
    minimum: float
    maximum: float
    peak_to_peak: float
    p95_absolute: float


def height_statistics(height: np.ndarray) -> HeightStatistics:
    """Summarize finite height observations without rejection or filtering."""
    values = np.asarray(height, dtype=np.float64)
    if values.ndim != 1 or values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("height must be a non-empty finite one-dimensional array")
    return HeightStatistics(
        count=int(values.size),
        mean=float(values.mean()),
        rms=float(math.sqrt(float(np.mean(values**2)))),
        minimum=float(values.min()),
        maximum=float(values.max()),
        peak_to_peak=float(values.max() - values.min()),
        p95_absolute=float(np.percentile(np.abs(values), 95.0)),
    )


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
