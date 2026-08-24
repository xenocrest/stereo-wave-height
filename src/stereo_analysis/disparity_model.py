"""Ideal rectified-stereo disparity and depth design relations.

All public arguments carry units in their names.  This module deliberately
does not infer or convert units and does not configure a stereo matcher.
"""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class DisparityDesignResult:
    """Traceable output for one nominal distance and a physical depth range."""

    baseline_m: float
    focal_length_px: float
    nominal_distance_m: float
    expected_disparity_px: float
    depth_range_m: tuple[float, float]
    disparity_range_px: tuple[float, float]
    recommended_disparity_center_px: float


def _positive_finite(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be finite and greater than zero")
    return value


def expected_disparity(
    baseline_m: float,
    focal_length_px: float,
    distance_m: float,
) -> float:
    """Return ideal rectified disparity ``d = f B / Z`` in pixels."""
    baseline = _positive_finite("baseline_m", baseline_m)
    focal = _positive_finite("focal_length_px", focal_length_px)
    distance = _positive_finite("distance_m", distance_m)
    return focal * baseline / distance


def depth_from_disparity(
    baseline_m: float,
    focal_length_px: float,
    disparity_px: float,
) -> float:
    """Return ideal rectified depth ``Z = f B / d`` in metres."""
    baseline = _positive_finite("baseline_m", baseline_m)
    focal = _positive_finite("focal_length_px", focal_length_px)
    disparity = _positive_finite("disparity_px", disparity_px)
    return focal * baseline / disparity


def analyze_disparity_design(
    baseline_m: float,
    focal_length_px: float,
    distance_m: float,
    *,
    depth_range_m: tuple[float, float] | None = None,
) -> DisparityDesignResult:
    """Evaluate nominal disparity and the disparity interval for a depth range.

    ``depth_range_m`` is ordered ``(nearest, farthest)``.  If it is omitted,
    the nominal distance is used for both bounds.  The reported center is the
    arithmetic center of the ideal disparity interval; it is a design
    diagnostic, not an automatically selected matcher parameter.
    """
    baseline = _positive_finite("baseline_m", baseline_m)
    focal = _positive_finite("focal_length_px", focal_length_px)
    distance = _positive_finite("distance_m", distance_m)
    if depth_range_m is None:
        nearest = farthest = distance
    else:
        if len(depth_range_m) != 2:
            raise ValueError("depth_range_m must contain nearest and farthest depth")
        nearest = _positive_finite("depth_range_m[0]", depth_range_m[0])
        farthest = _positive_finite("depth_range_m[1]", depth_range_m[1])
        if nearest > farthest:
            raise ValueError("depth_range_m must be ordered nearest to farthest")
        if not nearest <= distance <= farthest:
            raise ValueError("distance_m must lie inside depth_range_m")

    nominal_disparity = focal * baseline / distance
    minimum_disparity = focal * baseline / farthest
    maximum_disparity = focal * baseline / nearest
    return DisparityDesignResult(
        baseline_m=baseline,
        focal_length_px=focal,
        nominal_distance_m=distance,
        expected_disparity_px=nominal_disparity,
        depth_range_m=(nearest, farthest),
        disparity_range_px=(minimum_disparity, maximum_disparity),
        recommended_disparity_center_px=(minimum_disparity + maximum_disparity) / 2.0,
    )
