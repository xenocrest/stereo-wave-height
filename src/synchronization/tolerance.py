"""Controlled frame-offset candidates and evidence-derived on-demand sync policy."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from .affine import AffineTimeMapping
from .frame_selection import VideoFrameTimestamp, nearest_frame


@dataclass(frozen=True)
class FrameOffsetCandidate:
    """One right-frame candidate around the model-predicted nearest PTS."""

    offset_frames: int
    frame: VideoFrameTimestamp
    predicted_right_time_s: float
    residual_s: float
    local_frame_period_s: float
    normalized_residual: float


@dataclass(frozen=True)
class OnDemandSyncTolerancePolicy:
    """Serializable policy established only after controlled reconstruction tests."""

    status: str
    strict_max_abs_frames: int | None
    warning_max_abs_frames: int | None
    evidence_source: str

    def __post_init__(self) -> None:
        if self.status not in {"ON_DEMAND_SYNC_TOLERANCE_ESTABLISHED", "ON_DEMAND_SYNC_TOLERANCE_NOT_ESTABLISHED"}:
            raise ValueError("unknown tolerance policy status")
        if self.status.endswith("NOT_ESTABLISHED"):
            if self.strict_max_abs_frames is not None or self.warning_max_abs_frames is not None:
                raise ValueError("unestablished policy cannot carry acceptance limits")
        else:
            if self.strict_max_abs_frames is None or self.warning_max_abs_frames is None:
                raise ValueError("established policy requires strict and warning limits")
            if not 0 <= self.strict_max_abs_frames <= self.warning_max_abs_frames:
                raise ValueError("tolerance limits must be ordered non-negative integers")
        if not self.evidence_source:
            raise ValueError("evidence_source must be explicit")

    def classify(self, offset_frames: int) -> str:
        if self.status == "ON_DEMAND_SYNC_TOLERANCE_NOT_ESTABLISHED":
            return "REJECTED"
        assert self.strict_max_abs_frames is not None and self.warning_max_abs_frames is not None
        magnitude = abs(int(offset_frames))
        if magnitude <= self.strict_max_abs_frames:
            return "ACCEPTED"
        if magnitude <= self.warning_max_abs_frames:
            return "WARNING"
        return "REJECTED"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def generate_frame_offset_candidates(
    right_frames: tuple[VideoFrameTimestamp, ...],
    *,
    actual_left_time_s: float,
    mapping: AffineTimeMapping,
    offsets: tuple[int, ...] = (-3, -2, -1, 0, 1, 2, 3),
    local_radius: int = 5,
) -> tuple[FrameOffsetCandidate, ...]:
    """Generate fixed-index candidates around R0 using actual decoded PTS."""
    if len(right_frames) < 2 or len(set(offsets)) != len(offsets):
        raise ValueError("right frames must contain at least two frames and offsets must be unique")
    predicted = float(mapping.map_left_to_right([actual_left_time_s])[0])
    base = nearest_frame(right_frames, predicted)
    base_index = right_frames.index(base)
    indices = [base_index + offset for offset in offsets]
    if any(index < 0 or index >= len(right_frames) for index in indices):
        raise IndexError("a requested frame-offset candidate is unavailable")
    lo = max(0, base_index - local_radius)
    hi = min(len(right_frames), base_index + local_radius + 1)
    intervals = np.diff([frame.timestamp_s for frame in right_frames[lo:hi]])
    intervals = intervals[intervals > 0]
    if intervals.size == 0:
        raise ValueError("local frame period cannot be estimated")
    period = float(np.median(intervals))
    return tuple(
        FrameOffsetCandidate(
            int(offset), right_frames[index], predicted,
            float(right_frames[index].timestamp_s - predicted), period,
            float(abs(right_frames[index].timestamp_s - predicted) / period),
        )
        for offset, index in zip(offsets, indices, strict=True)
    )


def select_formal_candidate(candidates: tuple[FrameOffsetCandidate, ...]) -> FrameOffsetCandidate:
    """Return R0 only; reconstruction outcomes must never select a better-looking frame."""
    zero = [candidate for candidate in candidates if candidate.offset_frames == 0]
    if len(zero) != 1:
        raise ValueError("candidate set must contain exactly one R0")
    return zero[0]
