"""Theory helpers for the controlled stereo-baseline validation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class BaselineTheory:
    """Pinhole geometry for one baseline at a frozen scene distance."""

    baseline_m: float
    nominal_disparity_px: float
    min_disparity_px: float
    max_disparity_px: float
    sensitivity_m_per_px: float
    minimum_common_horizontal_fov_m: float
    nominal_triangulation_angle_deg: float
    disparity_range_pass: bool
    common_fov_pass: bool
    triangulation_angle_pass: bool


def baseline_theory(
    baseline_m: float,
    *,
    distance_m: float,
    amplitude_m: float,
    focal_px: float,
    image_width_px: int,
    minimum_disparity_px: float,
    maximum_disparity_px: float,
    required_common_width_m: float,
    minimum_triangulation_angle_deg: float,
) -> BaselineTheory:
    """Evaluate disparity, overlap, sensitivity, and central ray angle."""
    values = (
        baseline_m, distance_m, amplitude_m, focal_px, minimum_disparity_px,
        maximum_disparity_px, required_common_width_m,
        minimum_triangulation_angle_deg,
    )
    if not all(np.isfinite(value) for value in values):
        raise ValueError("baseline-theory inputs must be finite")
    if baseline_m <= 0 or distance_m <= amplitude_m or amplitude_m < 0 or focal_px <= 0:
        raise ValueError("physical lengths must be positive and distance exceed amplitude")
    if image_width_px <= 0 or minimum_disparity_px >= maximum_disparity_px:
        raise ValueError("image width and disparity bounds are invalid")
    nearest = distance_m - amplitude_m
    farthest = distance_m + amplitude_m
    focal_baseline = focal_px * baseline_m
    nominal = focal_baseline / distance_m
    minimum = focal_baseline / farthest
    maximum = focal_baseline / nearest
    common = image_width_px * nearest / focal_px - baseline_m
    angle_deg = float(np.degrees(2.0 * np.arctan(baseline_m / (2.0 * distance_m))))
    return BaselineTheory(
        float(baseline_m), float(nominal), float(minimum), float(maximum),
        float(distance_m**2 / focal_baseline), float(common), angle_deg,
        bool(minimum >= minimum_disparity_px and maximum <= maximum_disparity_px),
        bool(common >= required_common_width_m),
        bool(angle_deg >= minimum_triangulation_angle_deg),
    )
