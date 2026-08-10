"""Masked error and coverage metrics with explicit metadata checks."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from height import HeightField


BoolArray = npt.NDArray[np.bool_]


@dataclass(frozen=True)
class HeightMetrics:
    """Scalar validation results; error values use ``unit``."""

    rmse: float
    mae: float
    maximum_absolute_error: float
    coverage: float
    hole_rate: float
    valid_count: int
    eligible_count: int
    unit: str


def calculate_height_metrics(
    calculated: HeightField,
    truth: npt.ArrayLike,
    truth_valid_mask: npt.ArrayLike,
    *,
    truth_unit: str,
    truth_coordinate_system: str,
    eligible_mask: npt.ArrayLike | None = None,
) -> HeightMetrics:
    """Calculate RMSE, MAE, max error, coverage, and hole rate.

    Metrics use only cells valid in both calculated and truth masks. An empty
    eligible region or a fully invalid comparison raises ``ValueError``. NaN
    under a true mask also raises instead of being silently discarded.
    """
    truth_array = np.asarray(truth, dtype=np.float64)
    truth_mask = np.asarray(truth_valid_mask, dtype=np.bool_)
    if truth_array.shape != calculated.h.shape or truth_mask.shape != calculated.h.shape:
        raise ValueError("truth, truth_valid_mask, and calculated height shapes must match")
    if truth_unit != calculated.unit:
        raise ValueError("truth and calculated height units do not match")
    if truth_coordinate_system != calculated.coordinate_system:
        raise ValueError("truth and calculated coordinate systems do not match")
    if np.any(truth_mask & ~np.isfinite(truth_array)):
        raise ValueError("truth values marked valid must be finite")

    if eligible_mask is None:
        eligible = np.ones(calculated.h.shape, dtype=np.bool_)
    else:
        eligible = np.asarray(eligible_mask, dtype=np.bool_)
        if eligible.shape != calculated.h.shape:
            raise ValueError("eligible_mask shape must match calculated height")

    eligible_count = int(np.count_nonzero(eligible))
    if eligible_count == 0:
        raise ValueError("eligible region is empty")
    valid = eligible & calculated.valid_mask & truth_mask
    valid_count = int(np.count_nonzero(valid))
    if valid_count == 0:
        raise ValueError("comparison contains no valid samples")

    error = calculated.h[valid] - truth_array[valid]
    absolute_error = np.abs(error)
    coverage = valid_count / eligible_count
    return HeightMetrics(
        rmse=float(np.sqrt(np.mean(np.square(error)))),
        mae=float(np.mean(absolute_error)),
        maximum_absolute_error=float(np.max(absolute_error)),
        coverage=coverage,
        hole_rate=1.0 - coverage,
        valid_count=valid_count,
        eligible_count=eligible_count,
        unit=calculated.unit,
    )
