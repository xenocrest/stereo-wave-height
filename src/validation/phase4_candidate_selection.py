"""Image-only candidate preparation for a new physical-validation case.

This module accepts decoded canonical video frames and synchronization metadata.
It deliberately has no access to WASS, XYZ, reconstructed height, or ruler data.
Final candidate selection remains a manual decision.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np


@dataclass(frozen=True)
class VisualCandidate:
    """One image-domain change candidate before any reconstruction is run."""

    candidate_id: str
    sample_time_s: float
    image_change_score: float


@dataclass(frozen=True)
class CandidatePreviewMetadata:
    """Traceable frozen-frame and R0 availability metadata for a preview."""

    candidate_id: str
    requested_left_time_s: float
    actual_cam1_pts: int
    actual_cam1_time_s: float
    left_pts: int
    left_time_s: float
    right_pts: int
    right_time_s: float
    pair_residual_s: float
    sync_status: str
    preview_path: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def image_change_scores(
    frames: np.ndarray,
    timestamps_s: np.ndarray,
    *,
    reference_time_s: float,
    roi_xywh: tuple[int, int, int, int],
) -> np.ndarray:
    """Score canonical-frame appearance change after removing global offset.

    The score is mean absolute difference from the frame nearest the declared
    reference time. Per-frame median removal reduces global brightness-step
    influence. The ROI is explicit and is never inferred from ruler values.
    """
    images = np.asarray(frames)
    times = np.asarray(timestamps_s, dtype=np.float64)
    if images.ndim != 3 or images.shape[0] < 2 or times.shape != (images.shape[0],):
        raise ValueError("frames must be [time,y,x] with one timestamp per frame")
    if not np.all(np.isfinite(times)) or np.any(np.diff(times) <= 0):
        raise ValueError("candidate timestamps must be finite and strictly increasing")
    x, y, width, height = roi_xywh
    if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > images.shape[2] or y + height > images.shape[1]:
        raise ValueError("candidate ROI lies outside the decoded image")
    region = images[:, y : y + height, x : x + width].astype(np.float64)
    normalized = region - np.median(region, axis=(1, 2))[:, None, None]
    reference = normalized[int(np.argmin(np.abs(times - reference_time_s)))]
    return np.mean(np.abs(normalized - reference), axis=(1, 2))


def temporal_nonmaximum_candidates(
    timestamps_s: np.ndarray,
    scores: np.ndarray,
    *,
    count: int,
    minimum_separation_s: float,
    excluded_reference_time_s: float | None = None,
    excluded_half_window_s: float = 0.0,
) -> tuple[VisualCandidate, ...]:
    """Select high-change, time-separated candidates without naming a winner."""
    times = np.asarray(timestamps_s, dtype=np.float64)
    values = np.asarray(scores, dtype=np.float64)
    if times.ndim != 1 or values.shape != times.shape or times.size == 0:
        raise ValueError("timestamps and scores must be equal non-empty vectors")
    if count <= 0 or minimum_separation_s < 0 or excluded_half_window_s < 0:
        raise ValueError("candidate count must be positive and time windows non-negative")
    if not np.all(np.isfinite(times)) or not np.all(np.isfinite(values)):
        raise ValueError("candidate inputs must be finite")
    selected: list[int] = []
    for index in np.argsort(values)[::-1]:
        if excluded_reference_time_s is not None and abs(times[index] - excluded_reference_time_s) <= excluded_half_window_s:
            continue
        if all(abs(times[index] - times[other]) >= minimum_separation_s for other in selected):
            selected.append(int(index))
        if len(selected) == count:
            break
    selected.sort(key=lambda index: times[index])
    return tuple(
        VisualCandidate(f"candidate_{number:02d}", float(times[index]), float(values[index]))
        for number, index in enumerate(selected, start=1)
    )


def validate_candidate_case_status(status: str, candidates: tuple[CandidatePreviewMetadata, ...]) -> None:
    """Require an unresolved manual-selection state with distinct identities."""
    if status != "PHASE4_CASE2_CANDIDATE_SELECTION_REQUIRED":
        raise ValueError("Case 2 preview generation must stop at manual selection")
    if not 5 <= len(candidates) <= 8:
        raise ValueError("Case 2 requires five to eight preview candidates")
    identities = {(item.right_pts, item.right_time_s) for item in candidates}
    if len(identities) != len(candidates):
        raise ValueError("candidate frame identities must be unique")
