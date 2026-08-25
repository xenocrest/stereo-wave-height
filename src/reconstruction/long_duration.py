"""Capacity preflight and resumable batch planning for long WASS sequences."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class CapacityEstimate:
    """Evidence-based lower-bound estimate for one planned sequence."""

    frame_count: int
    seconds_per_frame: float
    bytes_per_frame: float
    estimated_runtime_s: float
    estimated_storage_bytes: int
    available_storage_bytes: int
    status: str


@dataclass(frozen=True)
class FrameBatch:
    """Half-open frame-index interval suitable for checkpointed execution."""

    batch_id: int
    start_index: int
    stop_index: int


def estimate_capacity(
    *,
    frame_count: int,
    measured_seconds_per_frame: float,
    measured_bytes_per_frame: float,
    available_storage_bytes: int,
    safety_factor: float = 1.0,
) -> CapacityEstimate:
    """Estimate resource demand without silently reducing frame count."""
    if not isinstance(frame_count, int) or frame_count <= 0:
        raise ValueError("frame_count must be a positive integer")
    values = (measured_seconds_per_frame, measured_bytes_per_frame, safety_factor)
    if any(not math.isfinite(value) or value <= 0 for value in values):
        raise ValueError("measured resource values and safety_factor must be positive and finite")
    if not isinstance(available_storage_bytes, int) or available_storage_bytes < 0:
        raise ValueError("available_storage_bytes must be a non-negative integer")
    runtime = frame_count * measured_seconds_per_frame * safety_factor
    storage = int(math.ceil(frame_count * measured_bytes_per_frame * safety_factor))
    status = "CAPACITY_AVAILABLE" if storage <= available_storage_bytes else "BLOCKED_INSUFFICIENT_STORAGE"
    return CapacityEstimate(
        frame_count, measured_seconds_per_frame, measured_bytes_per_frame,
        runtime, storage, available_storage_bytes, status,
    )


def plan_frame_batches(frame_count: int, *, batch_size: int) -> tuple[FrameBatch, ...]:
    """Create deterministic, gap-free, non-overlapping resumable batches."""
    if not isinstance(frame_count, int) or frame_count <= 0:
        raise ValueError("frame_count must be a positive integer")
    if not isinstance(batch_size, int) or batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")
    return tuple(
        FrameBatch(batch_id, start, min(start + batch_size, frame_count))
        for batch_id, start in enumerate(range(0, frame_count, batch_size))
    )
