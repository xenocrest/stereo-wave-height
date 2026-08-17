"""Affine clock mapping from shared events and tolerance-gated frame pairing."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt


@dataclass(frozen=True)
class AffineTimeMapping:
    """Map left time to right time with ``t_R = a*t_L + b`` in seconds."""

    scale: float
    offset_s: float
    event_count: int
    residual_rmse_s: float
    residual_max_abs_s: float

    def __post_init__(self) -> None:
        values = (self.scale, self.offset_s, self.residual_rmse_s, self.residual_max_abs_s)
        if not all(np.isfinite(value) for value in values) or self.scale <= 0:
            raise ValueError("affine mapping values must be finite and scale positive")
        if self.event_count < 2 or self.residual_rmse_s < 0 or self.residual_max_abs_s < 0:
            raise ValueError("affine mapping requires at least two events and non-negative residuals")

    def map_left_to_right(self, timestamp_s: npt.ArrayLike) -> npt.NDArray[np.float64]:
        values = np.asarray(timestamp_s, dtype=np.float64)
        if not np.all(np.isfinite(values)):
            raise ValueError("timestamps must be finite")
        return self.scale * values + self.offset_s


@dataclass(frozen=True)
class TimestampPair:
    """One tolerance-accepted nearest timestamp association."""

    left_index: int
    right_index: int
    left_timestamp_s: float
    mapped_right_timestamp_s: float
    right_timestamp_s: float
    residual_s: float


@dataclass(frozen=True)
class PairingDiagnostics:
    """Complete pairing outcome including rejected left frames."""

    pairs: tuple[TimestampPair, ...]
    rejected_left_indices: tuple[int, ...]
    tolerance_s: float
    residual_rmse_s: float
    residual_max_abs_s: float


def _timestamps(values: npt.ArrayLike, name: str, *, minimum_size: int = 1) -> npt.NDArray[np.float64]:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or array.size < minimum_size or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be a finite one-dimensional sequence")
    if array.size > 1 and np.any(np.diff(array) <= 0):
        raise ValueError(f"{name} must be strictly increasing")
    return array


def fit_affine_time_mapping(left_event_s: npt.ArrayLike, right_event_s: npt.ArrayLike) -> AffineTimeMapping:
    """Least-squares fit from at least two corresponding shared flash events."""
    left = _timestamps(left_event_s, "left_event_s", minimum_size=2)
    right = _timestamps(right_event_s, "right_event_s", minimum_size=2)
    if left.shape != right.shape:
        raise ValueError("left and right event arrays must have equal length")
    design = np.column_stack((left, np.ones(left.size)))
    (scale, offset), _, rank, _ = np.linalg.lstsq(design, right, rcond=None)
    if rank != 2 or not np.isfinite(scale) or scale <= 0 or not np.isfinite(offset):
        raise ValueError("flash events do not define a valid positive affine clock mapping")
    residual = scale * left + offset - right
    return AffineTimeMapping(
        float(scale), float(offset), int(left.size),
        float(np.sqrt(np.mean(residual**2))), float(np.max(np.abs(residual))),
    )


def pair_nearest_timestamps(
    left_timestamp_s: npt.ArrayLike,
    right_timestamp_s: npt.ArrayLike,
    mapping: AffineTimeMapping,
    *,
    tolerance_s: float,
) -> PairingDiagnostics:
    """Pair each left frame to its nearest right timestamp within tolerance.

    Right-frame reuse is forbidden; a reused nearest candidate is rejected
    rather than silently reassigned to a farther frame.
    """
    left = _timestamps(left_timestamp_s, "left_timestamp_s")
    right = _timestamps(right_timestamp_s, "right_timestamp_s")
    if not np.isfinite(tolerance_s) or tolerance_s < 0:
        raise ValueError("tolerance_s must be finite and non-negative")
    mapped = mapping.map_left_to_right(left)
    used: set[int] = set()
    pairs: list[TimestampPair] = []
    rejected: list[int] = []
    for left_index, target in enumerate(mapped):
        insertion = int(np.searchsorted(right, target))
        candidates = [index for index in (insertion - 1, insertion) if 0 <= index < right.size]
        right_index = min(candidates, key=lambda index: (abs(right[index] - target), index))
        residual = float(right[right_index] - target)
        if abs(residual) > tolerance_s or right_index in used:
            rejected.append(left_index)
            continue
        used.add(right_index)
        pairs.append(TimestampPair(left_index, right_index, float(left[left_index]), float(target), float(right[right_index]), residual))
    residuals = np.array([pair.residual_s for pair in pairs], dtype=np.float64)
    rmse = float(np.sqrt(np.mean(residuals**2))) if residuals.size else float("nan")
    maximum = float(np.max(np.abs(residuals))) if residuals.size else float("nan")
    return PairingDiagnostics(tuple(pairs), tuple(rejected), float(tolerance_s), rmse, maximum)
