"""Case 1 validation with explicit static/dynamic frame separation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from adapters.wass.output import StandardizedGrid3D
from height import calculate_height
from reference import valid_temporal_mean


@dataclass(frozen=True)
class ConstantHeightResult:
    """Metrics for a known constant offset; error values use ``unit``."""

    true_height: float
    mean_recovered_height: float
    signed_bias: float
    rmse: float
    mae: float
    maximum_absolute_error: float
    standard_deviation: float
    coverage: float
    hole_rate: float
    valid_count: int
    eligible_count: int
    unit: str


def _select_frames(grid: StandardizedGrid3D, indices: Sequence[int]) -> StandardizedGrid3D:
    selected = np.asarray(indices, dtype=np.int64)
    if selected.ndim != 1 or selected.size == 0:
        raise ValueError("frame indices must be a non-empty one-dimensional sequence")
    if np.any(selected < 0) or np.any(selected >= grid.timestamp_ns.size):
        raise IndexError("frame index is outside the standardized grid")
    if np.unique(selected).size != selected.size or np.any(np.diff(selected) <= 0):
        raise ValueError("frame indices must be unique and strictly increasing")
    return StandardizedGrid3D(
        x=grid.x,
        y=grid.y,
        z=grid.z[selected],
        timestamp_ns=grid.timestamp_ns[selected],
        valid_mask=grid.valid_mask[selected],
        coordinate_system=grid.coordinate_system,
        unit=grid.unit,
    )


def validate_constant_height_sequence(
    grid: StandardizedGrid3D,
    *,
    static_frame_indices: Sequence[int],
    dynamic_frame_indices: Sequence[int],
    true_height: float,
) -> ConstantHeightResult:
    """Evaluate Case 1 while using only declared static frames for ``Z0``.

    Both subsets come from one standardized WASS/gridder product, which makes
    their x/y coordinates, coordinate-system label, unit, scale, and transform
    common by construction. Static and dynamic index sets must be disjoint.
    No resampling, filtering, interpolation, or coordinate correction occurs.
    """
    if not np.isfinite(true_height) or true_height == 0:
        raise ValueError("true_height must be an explicit finite non-zero value")
    static_set = set(int(value) for value in static_frame_indices)
    dynamic_set = set(int(value) for value in dynamic_frame_indices)
    if static_set & dynamic_set:
        raise ValueError("static and dynamic frame sets must be disjoint")
    static = _select_frames(grid, static_frame_indices)
    dynamic = _select_frames(grid, dynamic_frame_indices)
    reference = valid_temporal_mean(static)
    calculated = calculate_height(dynamic, reference)

    eligible_count = calculated.h.size
    valid_count = int(np.count_nonzero(calculated.valid_mask))
    if valid_count == 0:
        raise ValueError("constant-height comparison contains no valid samples")
    recovered = calculated.h[calculated.valid_mask]
    error = recovered - true_height
    absolute_error = np.abs(error)
    coverage = valid_count / eligible_count
    return ConstantHeightResult(
        true_height=float(true_height),
        mean_recovered_height=float(np.mean(recovered)),
        signed_bias=float(np.mean(error)),
        rmse=float(np.sqrt(np.mean(np.square(error)))),
        mae=float(np.mean(absolute_error)),
        maximum_absolute_error=float(np.max(absolute_error)),
        standard_deviation=float(np.std(recovered)),
        coverage=coverage,
        hole_rate=1.0 - coverage,
        valid_count=valid_count,
        eligible_count=eligible_count,
        unit=calculated.unit,
    )
