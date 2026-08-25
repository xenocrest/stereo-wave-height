"""Non-destructive WASS production-mode planning and result merging.

This module changes neither WASS algorithms nor calibration.  It makes ROI
capabilities, retained artifacts, and resumable batch state explicit before a
long run is authorized.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import PurePosixPath
from typing import Iterable, Mapping


class OutputMode(str, Enum):
    """Supported artifact-retention policies."""

    DIAGNOSTIC = "diagnostic"
    PRODUCTION = "production"


@dataclass(frozen=True)
class PixelRoi:
    """Explicit image ROI; it is never inferred from reconstruction quality."""

    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if min(self.x, self.y) < 0 or self.width <= 0 or self.height <= 0:
            raise ValueError("ROI origin must be non-negative and extent positive")


@dataclass(frozen=True)
class RoiCapability:
    """Confirmed effect boundary for the unmodified WASS interface."""

    pre_match_reduction_supported: bool
    stereo_mask_supported: bool
    triangulation_bbox_supported: bool
    calibration_preserving_input_crop_supported: bool


CONFIRMED_WASS_ROI_CAPABILITY = RoiCapability(
    pre_match_reduction_supported=False,
    stereo_mask_supported=True,
    triangulation_bbox_supported=True,
    calibration_preserving_input_crop_supported=False,
)


@dataclass(frozen=True)
class BatchRecord:
    """One deterministic half-open batch and its checkpoint state."""

    batch_id: int
    start_index: int
    stop_index: int
    status: str


def production_retention(relative_path: str) -> str:
    """Classify an artifact without deleting it.

    The caller must perform verified checkpointing before applying any prune
    decision.  Raw videos are outside this output policy.
    """
    path = PurePosixPath(relative_path.replace("\\", "/"))
    if path.suffix.lower() == ".mp4":
        raise ValueError("raw videos are not production output artifacts")
    if path.parts and path.parts[0] in {"height", "pixel_xyz"}:
        return "RETAIN"
    if path.parts and path.parts[0] == "pointcloud" and path.suffix.lower() == ".xyz":
        return "RETAIN"
    if path.name in {"wave_result.json", "wave_timeseries.csv", "reconstruction_result.json"}:
        return "RETAIN"
    if path.parts and path.parts[0] in {"rectified", "disparity", "dataset", "wass_workspace"}:
        return "PRUNE_AFTER_VERIFIED_CHECKPOINT"
    if path.suffix.lower() == ".ply":
        return "PRUNE_AFTER_VERIFIED_CHECKPOINT"
    return "REVIEW_REQUIRED"


def resumable_batches(
    frame_count: int,
    batch_size: int,
    *,
    frame_start: int = 0,
    frame_stop_exclusive: int | None = None,
    completed_batch_ids: Iterable[int] = (),
) -> tuple[BatchRecord, ...]:
    """Build gap-free batches and mark only explicitly completed checkpoints."""
    if not isinstance(frame_count, int) or frame_count <= 0:
        raise ValueError("frame_count must be a positive integer")
    if not isinstance(batch_size, int) or batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")
    stop = frame_count if frame_stop_exclusive is None else frame_stop_exclusive
    if (
        not isinstance(frame_start, int)
        or not isinstance(stop, int)
        or frame_start < 0
        or stop <= frame_start
        or stop > frame_count
    ):
        raise ValueError("requested frame range must be a non-empty subset of the sequence")
    completed = set(completed_batch_ids)
    count = (stop - frame_start + batch_size - 1) // batch_size
    if any(not isinstance(value, int) or value < 0 or value >= count for value in completed):
        raise ValueError("completed batch id is outside the plan")
    return tuple(
        BatchRecord(
            batch_id=batch_id,
            start_index=start,
            stop_index=min(start + batch_size, stop),
            status="COMPLETE" if batch_id in completed else "PENDING",
        )
        for batch_id, start in enumerate(range(frame_start, stop, batch_size))
    )


def merge_wave_results(results: Iterable[Mapping[str, object]]) -> dict[str, object]:
    """Merge completed batch JSON payloads without altering frame results."""
    payloads = list(results)
    if not payloads:
        raise ValueError("at least one batch result is required")
    frames: list[dict[str, object]] = []
    seen: set[str] = set()
    for payload in payloads:
        series = payload.get("height_series")
        if not isinstance(series, list):
            raise ValueError("batch result height_series must be a list")
        for item in series:
            if not isinstance(item, dict) or "frame_id" not in item or "timestamp_ns" not in item:
                raise ValueError("each height_series record needs frame_id and timestamp_ns")
            frame_id = str(item["frame_id"])
            if frame_id in seen:
                raise ValueError(f"duplicate frame_id across batches: {frame_id}")
            seen.add(frame_id)
            frames.append(dict(item))
    frames.sort(key=lambda item: (int(item["timestamp_ns"]), str(item["frame_id"])))
    return {
        "schema_version": "1.0",
        "status": "MERGED_FROM_VERIFIED_BATCH_RESULTS",
        "batch_count": len(payloads),
        "frame_count": len(frames),
        "height_series": frames,
    }
