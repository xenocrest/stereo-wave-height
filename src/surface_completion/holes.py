"""Continuous circular-hole hold-out validation for the existing MLS model."""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
from scipy.spatial import cKDTree

from .mls import _error_summary, deterministic_holdout_indices, quadratic_mls_predict


@dataclass(frozen=True)
class HoleLevelResult:
    hole_radius_m: float
    test_point_count: int
    supported_prediction_count: int
    unsupported_count: int
    coverage_percent: float
    mae_m: float | None
    rmse_m: float | None
    median_absolute_error_m: float | None
    p95_absolute_error_m: float | None
    maximum_absolute_error_m: float | None
    unsupported_reasons: dict[str, int]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def hole_support_indices(
    tree: cKDTree,
    xy_m: np.ndarray,
    center_xy_m: np.ndarray,
    *,
    hole_radius_m: float,
    support_radius_m: float,
) -> np.ndarray:
    """Return only points outside the artificial hole and inside MLS support."""
    candidates = np.asarray(tree.query_ball_point(center_xy_m, support_radius_m), dtype=np.int64)
    if candidates.size == 0:
        return candidates
    distance = np.linalg.norm(xy_m[candidates] - center_xy_m, axis=1)
    return candidates[distance > hole_radius_m]


def evaluate_spatial_holes(
    xy_m: np.ndarray,
    height_m: np.ndarray,
    *,
    maximum_test_centers: int,
    seed: int,
    hole_radius_multipliers: tuple[float, ...],
    radius_multiplier: float = 6.0,
    sigma_multiplier: float = 3.0,
    minimum_points: int = 12,
    maximum_neighbors: int = 64,
    maximum_condition_number: float = 1e8,
) -> dict[str, object]:
    """Hide circular neighborhoods and predict their observed center heights."""
    xy = np.asarray(xy_m, dtype=np.float64)
    height = np.asarray(height_m, dtype=np.float64)
    if xy.ndim != 2 or xy.shape[1] != 2 or height.shape != (xy.shape[0],):
        raise ValueError("xy_m and height_m must align")
    if not np.all(np.isfinite(xy)) or not np.all(np.isfinite(height)):
        raise ValueError("frozen observations must be finite")
    if len(hole_radius_multipliers) != 4 or any(value <= 0 for value in hole_radius_multipliers):
        raise ValueError("exactly four positive hole scales are required")
    tree = cKDTree(xy)
    spacing = tree.query(xy, k=2)[0][:, 1]
    positive = spacing[spacing > 0]
    p50, p90, p95 = (float(value) for value in np.percentile(positive, (50, 90, 95)))
    support_radius = radius_multiplier * p90
    sigma = sigma_multiplier * p90
    # A fixed center count, independent of point count, keeps frame comparisons balanced.
    ratio = min(0.5, maximum_test_centers / xy.shape[0])
    centers = deterministic_holdout_indices(xy.shape[0], ratio, maximum_test_centers, seed)
    levels: dict[str, object] = {}
    for level_index, multiplier in enumerate(hole_radius_multipliers):
        hole_radius = multiplier * p90
        prediction = np.full(centers.size, np.nan, dtype=np.float64)
        rejected = {"UNSUPPORTED_MINIMUM_POINTS": 0, "UNSUPPORTED_ILL_CONDITIONED": 0}
        for output_index, source_index in enumerate(centers):
            support = hole_support_indices(
                tree, xy, xy[source_index], hole_radius_m=hole_radius, support_radius_m=support_radius
            )
            value, diagnostic = quadratic_mls_predict(
                xy[support], height[support], xy[source_index], support_radius_m=support_radius,
                gaussian_sigma_m=sigma, minimum_points=minimum_points,
                maximum_neighbors=maximum_neighbors, maximum_condition_number=maximum_condition_number,
            )
            prediction[output_index] = value
            if diagnostic["status"] != "SUPPORTED":
                rejected[str(diagnostic["status"])] += 1
        valid = np.isfinite(prediction)
        summary = _error_summary(prediction[valid] - height[centers][valid])
        levels[f"hole_{level_index}"] = HoleLevelResult(
            hole_radius_m=hole_radius, test_point_count=int(centers.size),
            supported_prediction_count=int(valid.sum()), unsupported_count=int((~valid).sum()),
            coverage_percent=float(100 * valid.mean()), mae_m=summary["mae_m"], rmse_m=summary["rmse_m"],
            median_absolute_error_m=summary["median_absolute_error_m"],
            p95_absolute_error_m=summary["p95_absolute_error_m"],
            maximum_absolute_error_m=summary["maximum_absolute_error_m"], unsupported_reasons=rejected,
        ).to_dict()
    return {
        "spacing_m": {"p50": p50, "p90": p90, "p95": p95},
        "rules": {"support_radius_m": support_radius, "gaussian_sigma_m": sigma,
                  "hole_radius_basis": "frame_p90_nearest_neighbor_spacing",
                  "hole_radius_multipliers": list(hole_radius_multipliers),
                  "minimum_points": minimum_points, "maximum_neighbors": maximum_neighbors,
                  "maximum_condition_number": maximum_condition_number,
                  "test_center_count": int(centers.size), "seed": seed},
        "levels": levels,
    }
