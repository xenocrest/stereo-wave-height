"""Theory and aggregation helpers for controlled scene-distance validation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class SceneDistanceTheory:
    """Explicit SI geometry for one nominal plane and symmetric wave amplitude."""

    distance_m: float
    nominal_disparity_px: float
    min_disparity_px: float
    max_disparity_px: float
    sensitivity_m_per_px: float
    minimum_common_horizontal_fov_m: float
    disparity_range_pass: bool
    common_fov_pass: bool


def scene_distance_theory(
    distance_m: float,
    *,
    amplitude_m: float,
    focal_px: float,
    baseline_m: float,
    image_width_px: int,
    minimum_disparity_px: float,
    maximum_disparity_px: float,
    required_common_width_m: float,
) -> SceneDistanceTheory:
    """Evaluate frozen parallel-stereo disparity, sensitivity and overlap."""
    values = (distance_m, amplitude_m, focal_px, baseline_m, minimum_disparity_px,
              maximum_disparity_px, required_common_width_m)
    if not all(np.isfinite(value) for value in values):
        raise ValueError("scene-distance inputs must be finite")
    if distance_m <= amplitude_m or amplitude_m < 0 or focal_px <= 0 or baseline_m <= 0:
        raise ValueError("distance/focal/baseline must be positive and distance exceed amplitude")
    if image_width_px <= 0 or minimum_disparity_px >= maximum_disparity_px:
        raise ValueError("image width and disparity bounds are invalid")
    nearest = distance_m - amplitude_m
    farthest = distance_m + amplitude_m
    product = focal_px * baseline_m
    nominal = product / distance_m
    minimum = product / farthest
    maximum = product / nearest
    common = image_width_px * nearest / focal_px - baseline_m
    return SceneDistanceTheory(
        float(distance_m), float(nominal), float(minimum), float(maximum),
        float(distance_m**2/product), float(common),
        bool(minimum >= minimum_disparity_px and maximum <= maximum_disparity_px),
        bool(common >= required_common_width_m),
    )


def min_mean_max(values: list[float] | tuple[float, ...]) -> dict[str, float]:
    """Aggregate a non-empty finite sequence without changing its values."""
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or array.size == 0 or not np.all(np.isfinite(array)):
        raise ValueError("values must be a non-empty finite sequence")
    return {"min": float(array.min()), "mean": float(array.mean()), "max": float(array.max())}
