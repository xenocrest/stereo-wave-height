"""Deterministic, image-only spatial selection for stereo calibration poses.

The selector consumes existing checkerboard detections.  It never reads a
reconstruction result and does not modify OpenCV's calibration algorithms.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Iterable, Sequence

import numpy as np
import numpy.typing as npt


@dataclass(frozen=True)
class BilateralPoseDescriptor:
    pair_id: str
    vector: tuple[float, ...]
    grid_cells: tuple[int, int]
    minimum_area_fraction: float
    minimum_sharpness: float
    minimum_edge_margin_px: float


def _camera_descriptor(camera: dict[str, Any], width: int, height: int) -> tuple[float, ...]:
    corners = np.asarray(camera["corners"], dtype=np.float64).reshape(-1, 2)
    row = corners[8] - corners[0]
    angle = math.atan2(float(row[1]), float(row[0]))
    return (
        float(camera["center_x_px"]) / width,
        float(camera["center_y_px"]) / height,
        math.log(max(float(camera["area_fraction"]), 1e-12)),
        math.sin(angle),
        math.cos(angle),
        float(camera["perspective_score"]),
    )


def build_bilateral_descriptor(pair: dict[str, Any], *, image_size_wh: tuple[int, int]) -> BilateralPoseDescriptor:
    """Build the reproducible descriptor from one complete bilateral detection."""
    width, height = image_size_wh
    left, right = pair["left"], pair["right"]
    if width <= 0 or height <= 0 or len(pair["left_corners"]) != 54 or len(pair["right_corners"]) != 54:
        raise ValueError("complete 9x6 bilateral corners and positive image dimensions are required")
    lc = np.asarray(pair["left_corners"], dtype=np.float64)
    rc = np.asarray(pair["right_corners"], dtype=np.float64)
    margin = min(float(lc[:, 0].min()), float(lc[:, 1].min()), width - 1 - float(lc[:, 0].max()),
                 height - 1 - float(lc[:, 1].max()), float(rc[:, 0].min()), float(rc[:, 1].min()),
                 width - 1 - float(rc[:, 0].max()), height - 1 - float(rc[:, 1].max()))
    vector = _camera_descriptor(left, width, height) + _camera_descriptor(right, width, height)
    cells = (
        min(8, int(vector[1] * 3) * 3 + int(vector[0] * 3)),
        min(8, int(vector[7] * 3) * 3 + int(vector[6] * 3)),
    )
    return BilateralPoseDescriptor(
        str(pair["pair_id"]), vector, cells,
        min(float(left["area_fraction"]), float(right["area_fraction"])),
        min(float(left["sharpness"]), float(right["sharpness"])), margin,
    )


def descriptor_distance(a: BilateralPoseDescriptor, b: BilateralPoseDescriptor) -> float:
    """Weighted Euclidean distance across both cameras' image-only descriptors."""
    av, bv = np.asarray(a.vector), np.asarray(b.vector)
    weights = np.asarray([1, 1, .25, .5, .5, .5] * 2, dtype=np.float64)
    return float(np.linalg.norm((av - bv) * weights))


def spatial_grid_counts(items: Iterable[BilateralPoseDescriptor]) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Return 3x3 center occupancy for left and right cameras."""
    left = [0] * 9; right = [0] * 9
    for item in items:
        left[item.grid_cells[0]] += 1; right[item.grid_cells[1]] += 1
    return tuple(left), tuple(right)


def select_spatially_diverse(
    items: Sequence[BilateralPoseDescriptor], *, count: int,
    excluded_pair_ids: Iterable[str] = (), duplicate_distance: float = 0.035,
) -> tuple[BilateralPoseDescriptor, ...]:
    """Greedy coverage then farthest-point selection with deterministic ties."""
    excluded = set(excluded_pair_ids)
    pool = sorted((item for item in items if item.pair_id not in excluded), key=lambda item: item.pair_id)
    if count <= 0 or count > len(pool) or duplicate_distance <= 0:
        raise ValueError("invalid selection count or duplicate distance")
    selected: list[BilateralPoseDescriptor] = []
    used_left: set[int] = set(); used_right: set[int] = set()
    while pool and len(selected) < count:
        def score(item: BilateralPoseDescriptor) -> tuple[float, float, str]:
            new_cells = int(item.grid_cells[0] not in used_left) + int(item.grid_cells[1] not in used_right)
            distance = min((descriptor_distance(item, chosen) for chosen in selected), default=1.0)
            quality = math.log1p(item.minimum_sharpness) + item.minimum_area_fraction
            return 4.0 * new_cells + min(distance, 2.0), quality, item.pair_id
        candidate = max(pool, key=score)
        pool.remove(candidate)
        if selected and min(descriptor_distance(candidate, chosen) for chosen in selected) < duplicate_distance:
            continue
        selected.append(candidate); used_left.add(candidate.grid_cells[0]); used_right.add(candidate.grid_cells[1])
    if len(selected) != count:
        raise ValueError("not enough non-duplicate poses for requested selection")
    return tuple(selected)


def baseline_sanity(baseline_m: float, reference_m: float = 0.070) -> dict[str, float]:
    """Return a comparison only; this never rescales calibration translation."""
    if not math.isfinite(baseline_m) or baseline_m <= 0 or reference_m <= 0:
        raise ValueError("baselines must be finite and positive")
    difference = baseline_m - reference_m
    return {"difference_m": difference, "absolute_difference_m": abs(difference),
            "relative_difference_percent": 100.0 * abs(difference) / reference_m}
