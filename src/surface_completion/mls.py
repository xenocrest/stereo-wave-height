"""Weighted local quadratic surface fitting in physical X/Y coordinates."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
from scipy.spatial import cKDTree


@dataclass(frozen=True)
class HoldoutResult:
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
    spacing_m: dict[str, float]
    rules: dict[str, float | int]
    strata: dict[str, dict[str, float | int | None]]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _design(dx: np.ndarray, dy: np.ndarray) -> np.ndarray:
    return np.column_stack((dx * dx, dx * dy, dy * dy, dx, dy, np.ones_like(dx)))


def quadratic_mls_predict(
    support_xy_m: np.ndarray,
    support_h_m: np.ndarray,
    query_xy_m: np.ndarray,
    *,
    support_radius_m: float,
    gaussian_sigma_m: float,
    minimum_points: int,
    maximum_neighbors: int,
    maximum_condition_number: float,
) -> tuple[float, dict[str, float | int | str]]:
    """Predict H at one point, or return NaN when physical support is inadequate."""
    xy = np.asarray(support_xy_m, dtype=np.float64)
    height = np.asarray(support_h_m, dtype=np.float64)
    query = np.asarray(query_xy_m, dtype=np.float64)
    if xy.ndim != 2 or xy.shape[1] != 2 or height.shape != (xy.shape[0],) or query.shape != (2,):
        raise ValueError("support/query shape mismatch")
    if min(support_radius_m, gaussian_sigma_m) <= 0 or minimum_points < 6 or maximum_neighbors < minimum_points:
        raise ValueError("invalid MLS support parameters")
    distance = np.linalg.norm(xy - query, axis=1)
    indices = np.flatnonzero(distance <= support_radius_m)
    if indices.size > maximum_neighbors:
        indices = indices[np.argsort(distance[indices])[:maximum_neighbors]]
    nearest = float(distance[indices].min()) if indices.size else float("nan")
    diagnostic: dict[str, float | int | str] = {"support_count": int(indices.size), "nearest_support_m": nearest}
    if indices.size < minimum_points:
        diagnostic["status"] = "UNSUPPORTED_MINIMUM_POINTS"
        return float("nan"), diagnostic

    local_xy = (xy[indices] - query) / support_radius_m
    matrix = _design(local_xy[:, 0], local_xy[:, 1])
    weights = np.exp(-0.5 * (distance[indices] / gaussian_sigma_m) ** 2)
    weighted_matrix = matrix * np.sqrt(weights)[:, None]
    weighted_height = height[indices] * np.sqrt(weights)
    rank = int(np.linalg.matrix_rank(weighted_matrix))
    condition = float(np.linalg.cond(weighted_matrix))
    diagnostic.update({"rank": rank, "condition_number": condition})
    if rank < 6 or not np.isfinite(condition) or condition > maximum_condition_number:
        diagnostic["status"] = "UNSUPPORTED_ILL_CONDITIONED"
        return float("nan"), diagnostic
    coefficients, *_ = np.linalg.lstsq(weighted_matrix, weighted_height, rcond=None)
    diagnostic["status"] = "SUPPORTED"
    return float(coefficients[5]), diagnostic


def deterministic_holdout_indices(point_count: int, ratio: float, maximum_count: int, seed: int) -> np.ndarray:
    """Return reproducible unique test indices without modifying source arrays."""
    if point_count < 2 or not 0 < ratio < 1 or maximum_count <= 0:
        raise ValueError("invalid hold-out request")
    count = min(maximum_count, max(1, int(np.floor(point_count * ratio))))
    return np.sort(np.random.default_rng(seed).choice(point_count, size=count, replace=False))


def _error_summary(error_m: np.ndarray) -> dict[str, float | int | None]:
    if error_m.size == 0:
        return {"count": 0, "mae_m": None, "rmse_m": None, "median_absolute_error_m": None,
                "p95_absolute_error_m": None, "maximum_absolute_error_m": None}
    absolute = np.abs(error_m)
    return {
        "count": int(error_m.size), "mae_m": float(absolute.mean()),
        "rmse_m": float(np.sqrt(np.mean(error_m**2))),
        "median_absolute_error_m": float(np.median(absolute)),
        "p95_absolute_error_m": float(np.percentile(absolute, 95)),
        "maximum_absolute_error_m": float(absolute.max()),
    }


def evaluate_holdout(
    xy_m: np.ndarray,
    height_m: np.ndarray,
    *,
    holdout_ratio: float,
    maximum_test_points: int,
    seed: int,
    radius_multiplier: float = 6.0,
    sigma_multiplier: float = 3.0,
    minimum_points: int = 12,
    maximum_neighbors: int = 64,
    maximum_condition_number: float = 1e8,
) -> HoldoutResult:
    """Evaluate local MLS after removing every test point from the support set."""
    xy = np.asarray(xy_m, dtype=np.float64)
    height = np.asarray(height_m, dtype=np.float64)
    if xy.ndim != 2 or xy.shape[1] != 2 or height.shape != (xy.shape[0],):
        raise ValueError("xy_m and height_m must align")
    if not np.all(np.isfinite(xy)) or not np.all(np.isfinite(height)):
        raise ValueError("frozen observations must be finite")
    tree = cKDTree(xy)
    spacing = tree.query(xy, k=2)[0][:, 1]
    positive = spacing[spacing > 0]
    if positive.size == 0:
        raise ValueError("physical point spacing is degenerate")
    p50, p90, p95 = (float(value) for value in np.percentile(positive, (50, 90, 95)))
    radius = radius_multiplier * p90
    sigma = sigma_multiplier * p90

    test_indices = deterministic_holdout_indices(xy.shape[0], holdout_ratio, maximum_test_points, seed)
    support_mask = np.ones(xy.shape[0], dtype=bool)
    support_mask[test_indices] = False
    support_xy, support_h = xy[support_mask], height[support_mask]
    support_tree = cKDTree(support_xy)
    nearest_support = support_tree.query(xy[test_indices], k=1)[0]

    prediction = np.full(test_indices.size, np.nan, dtype=np.float64)
    rejection_counts = {"UNSUPPORTED_MINIMUM_POINTS": 0, "UNSUPPORTED_ILL_CONDITIONED": 0}
    for output_index, source_index in enumerate(test_indices):
        nearby = support_tree.query_ball_point(xy[source_index], radius)
        if nearby:
            prediction[output_index], diagnostic = quadratic_mls_predict(
                support_xy[np.asarray(nearby, dtype=np.int64)], support_h[np.asarray(nearby, dtype=np.int64)],
                xy[source_index], support_radius_m=radius, gaussian_sigma_m=sigma,
                minimum_points=minimum_points, maximum_neighbors=maximum_neighbors,
                maximum_condition_number=maximum_condition_number,
            )
            if diagnostic["status"] != "SUPPORTED":
                rejection_counts[str(diagnostic["status"])] += 1
        else:
            rejection_counts["UNSUPPORTED_MINIMUM_POINTS"] += 1
    valid = np.isfinite(prediction)
    error = prediction[valid] - height[test_indices][valid]
    summary = _error_summary(error)
    labels = {
        "near": nearest_support <= p50,
        "medium": (nearest_support > p50) & (nearest_support <= p90),
        "sparse": nearest_support > p90,
    }
    strata: dict[str, dict[str, float | int | None]] = {}
    for name, selected in labels.items():
        usable = selected & valid
        item = _error_summary(prediction[usable] - height[test_indices][usable])
        item.update({"test_count": int(selected.sum()), "supported_count": int(usable.sum()),
                     "coverage_percent": float(100 * usable.sum() / selected.sum()) if selected.any() else None})
        strata[name] = item
    return HoldoutResult(
        test_point_count=int(test_indices.size), supported_prediction_count=int(valid.sum()),
        unsupported_count=int((~valid).sum()), coverage_percent=float(100 * valid.mean()),
        mae_m=summary["mae_m"], rmse_m=summary["rmse_m"],
        median_absolute_error_m=summary["median_absolute_error_m"],
        p95_absolute_error_m=summary["p95_absolute_error_m"],
        maximum_absolute_error_m=summary["maximum_absolute_error_m"],
        unsupported_reasons=rejection_counts,
        spacing_m={"p50": p50, "p90": p90, "p95": p95},
        rules={"support_radius_m": radius, "gaussian_sigma_m": sigma, "minimum_points": minimum_points,
               "maximum_neighbors": maximum_neighbors, "maximum_condition_number": maximum_condition_number},
        strata=strata,
    )
