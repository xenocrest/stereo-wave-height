"""Camera-independent light-event video synchronization diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import subprocess

import numpy as np


@dataclass(frozen=True)
class BrightnessEvent:
    """One robust brightness transition in a sampled video signal."""

    time_s: float
    signed_change: float


@dataclass(frozen=True)
class SynchronizationResult:
    """Estimated right-minus-left offset from matched light events."""

    status: str
    estimated_offset_s: float | None
    confidence: str
    matched_events: int
    residual_rms_s: float | None


@dataclass(frozen=True)
class FrameBrightnessSeries:
    """Full decoded-frame PTS and mean luma; timestamps are never synthesized."""

    pts: np.ndarray
    timestamps_s: np.ndarray
    brightness: np.ndarray


@dataclass(frozen=True)
class RefinedBrightnessEvent:
    """A frame-level light edge, optionally interpolated between adjacent PTS."""

    time_s: float
    polarity: int
    local_amplitude: float
    confidence: str
    refinement: str


@dataclass(frozen=True)
class EventPair:
    """One polarity-consistent, order-preserving left/right light-event pair."""

    left: RefinedBrightnessEvent
    right: RefinedBrightnessEvent


@dataclass(frozen=True)
class FrameLevelSyncModel:
    """Selected event-time model and evidence-based frame-level classification."""

    scale: float
    offset_s: float
    model_type: str
    matched_events: int
    residual_statistics: dict[str, float]
    frame_period_s: float
    classification: str
    selection_reason: str


_FRAME_LINE = re.compile(r"frame:\s*\d+\s+pts:\s*(-?\d+)\s+pts_time:([0-9.eE+-]+)")
_YAVG_LINE = re.compile(r"lavfi\.signalstats\.YAVG=([0-9.eE+-]+)")


def extract_frame_brightness_pts(
    video: str | Path,
    *,
    ffmpeg_executable: str | Path,
    width: int = 64,
    height: int = 36,
) -> FrameBrightnessSeries:
    """Decode every frame read-only and return actual PTS with mean luma.

    FFmpeg's ``signalstats`` produces one YAVG value for every decoded frame.
    No nominal-FPS time axis is constructed.
    """
    if width <= 0 or height <= 0:
        raise ValueError("image dimensions must be positive")
    command = [
        str(ffmpeg_executable), "-hide_banner", "-loglevel", "error", "-noautorotate",
        "-i", str(video), "-vf",
        f"scale={width}:{height},signalstats,metadata=print:file=-",
        "-an", "-f", "null", os.devnull,
    ]
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip())
    frame_rows = _FRAME_LINE.findall(completed.stdout)
    luma_rows = _YAVG_LINE.findall(completed.stdout)
    if len(frame_rows) < 2 or len(frame_rows) != len(luma_rows):
        raise ValueError("FFmpeg did not return aligned per-frame PTS and YAVG metadata")
    pts = np.asarray([int(row[0]) for row in frame_rows], dtype=np.int64)
    timestamps = np.asarray([float(row[1]) for row in frame_rows], dtype=np.float64)
    brightness = np.asarray([float(value) for value in luma_rows], dtype=np.float64)
    if np.any(np.diff(timestamps) <= 0) or not np.all(np.isfinite(brightness)):
        raise ValueError("decoded frame timestamps must increase and brightness must be finite")
    return FrameBrightnessSeries(pts, timestamps, brightness)


def detect_frame_level_light_events(
    series: FrameBrightnessSeries,
    *,
    smoothing_frames: int = 3,
    sigma_multiplier: float = 8.0,
    minimum_change: float = 2.0,
    minimum_separation_s: float = 0.25,
) -> tuple[RefinedBrightnessEvent, ...]:
    """Detect robust light edges and interpolate their half-level crossing.

    The centered three-frame mean is deliberately short relative to the local
    frame period.  Interpolation is used only across a non-zero, monotonic edge.
    """
    if smoothing_frames < 1 or smoothing_frames % 2 == 0:
        raise ValueError("smoothing_frames must be a positive odd integer")
    times = np.asarray(series.timestamps_s, dtype=np.float64)
    signal = np.asarray(series.brightness, dtype=np.float64)
    if times.ndim != 1 or signal.shape != times.shape or times.size < smoothing_frames + 2:
        raise ValueError("frame brightness series is too short or malformed")
    kernel = np.ones(smoothing_frames, dtype=np.float64) / smoothing_frames
    smooth = np.convolve(signal, kernel, mode="same")
    radius = smoothing_frames // 2
    difference = np.diff(smooth)
    usable = difference[radius : difference.size - radius]
    center = float(np.median(usable))
    mad = float(np.median(np.abs(usable - center)))
    threshold = max(float(minimum_change), sigma_multiplier * 1.4826 * mad)
    candidates = np.flatnonzero(np.abs(difference - center) >= threshold)
    selected: list[int] = []
    for index in candidates:
        if index < radius or index + 1 >= times.size - radius:
            continue
        if selected and times[index] - times[selected[-1]] < minimum_separation_s:
            if abs(difference[index] - center) > abs(difference[selected[-1]] - center):
                selected[-1] = int(index)
        else:
            selected.append(int(index))
    events: list[RefinedBrightnessEvent] = []
    for index in selected:
        low, high = float(smooth[index]), float(smooth[index + 1])
        delta = high - low
        crossing = (low + high) / 2.0
        if delta != 0 and min(low, high) <= crossing <= max(low, high):
            fraction = (crossing - low) / delta
            event_time = float(times[index] + fraction * (times[index + 1] - times[index]))
            refinement = "LINEAR_HALF_LEVEL_CROSSING"
        else:
            event_time = float(times[index + 1])
            refinement = "NO_SUBFRAME_REFINEMENT"
        strength = abs(delta) / threshold if threshold > 0 else float("inf")
        confidence = "HIGH" if strength >= 2.0 else "MEDIUM"
        events.append(RefinedBrightnessEvent(event_time, 1 if delta > 0 else -1, float(delta), confidence, refinement))
    return tuple(events)


def pair_frame_level_events(
    left: tuple[RefinedBrightnessEvent, ...],
    right: tuple[RefinedBrightnessEvent, ...],
    *,
    coarse_offset_s: float,
    tolerance_s: float,
) -> tuple[EventPair, ...]:
    """Pair same-polarity events monotonically around a coarse offset."""
    if not np.isfinite(coarse_offset_s) or not np.isfinite(tolerance_s) or tolerance_s <= 0:
        raise ValueError("coarse offset must be finite and tolerance positive")
    used: set[int] = set()
    pairs: list[EventPair] = []
    previous_right = -1
    for left_event in left:
        choices = [
            (abs(right_event.time_s - left_event.time_s - coarse_offset_s), index, right_event)
            for index, right_event in enumerate(right)
            if index not in used and index > previous_right and right_event.polarity == left_event.polarity
        ]
        if not choices:
            continue
        error, index, right_event = min(choices, key=lambda item: (item[0], item[1]))
        if error <= tolerance_s:
            used.add(index)
            previous_right = index
            pairs.append(EventPair(left_event, right_event))
    return tuple(pairs)


def synchronization_residual_statistics(residual_s: np.ndarray) -> dict[str, float]:
    """Return traceable residual statistics in seconds."""
    residual = np.asarray(residual_s, dtype=np.float64)
    if residual.ndim != 1 or residual.size == 0 or not np.all(np.isfinite(residual)):
        raise ValueError("residual_s must be a non-empty finite vector")
    absolute = np.abs(residual)
    return {
        "rms_s": float(np.sqrt(np.mean(residual**2))),
        "median_absolute_s": float(np.median(absolute)),
        "p95_absolute_s": float(np.percentile(absolute, 95)),
        "max_absolute_s": float(np.max(absolute)),
    }


def fit_frame_level_sync_model(
    pairs: tuple[EventPair, ...],
    *,
    frame_period_s: float,
    minimum_affine_improvement: float = 0.20,
) -> FrameLevelSyncModel:
    """Compare offset-only and affine models and classify their evidence.

    An affine clock is selected only with at least three event pairs and at
    least 20% RMS improvement.  Frame-level establishment requires at least
    three pairs and P95 residual no greater than half an observed frame;
    half-to-one-frame evidence is a warning and does not authorize WASS.
    """
    if len(pairs) < 2:
        raise ValueError("at least two matched events are required")
    if not np.isfinite(frame_period_s) or frame_period_s <= 0:
        raise ValueError("frame_period_s must be finite and positive")
    if not 0 < minimum_affine_improvement < 1:
        raise ValueError("minimum_affine_improvement must lie in (0,1)")
    left = np.asarray([pair.left.time_s for pair in pairs], dtype=np.float64)
    right = np.asarray([pair.right.time_s for pair in pairs], dtype=np.float64)
    offset = float(np.median(right - left))
    offset_residual = right - (left + offset)
    offset_stats = synchronization_residual_statistics(offset_residual)
    scale = 1.0
    selected_offset = offset
    model_type = "OFFSET_ONLY"
    stats = offset_stats
    reason = "Affine drift requires at least three pairs and material RMS improvement."
    if len(pairs) >= 3:
        design = np.column_stack((left, np.ones(left.size)))
        (candidate_scale, candidate_offset), _, rank, _ = np.linalg.lstsq(design, right, rcond=None)
        candidate_residual = right - (candidate_scale * left + candidate_offset)
        candidate_stats = synchronization_residual_statistics(candidate_residual)
        improvement = 1.0 - candidate_stats["rms_s"] / offset_stats["rms_s"] if offset_stats["rms_s"] > 0 else 0.0
        if rank == 2 and candidate_scale > 0 and improvement >= minimum_affine_improvement:
            scale = float(candidate_scale)
            selected_offset = float(candidate_offset)
            model_type = "AFFINE"
            stats = candidate_stats
            reason = f"Affine RMS improvement {improvement:.3f} meets the {minimum_affine_improvement:.3f} rule."
        else:
            reason = f"Affine RMS improvement {improvement:.3f} is below the {minimum_affine_improvement:.3f} rule."
    if len(pairs) >= 3 and stats["p95_absolute_s"] <= 0.5 * frame_period_s and stats["max_absolute_s"] <= frame_period_s:
        classification = "FRAME_LEVEL_SYNC_ESTABLISHED"
    elif len(pairs) >= 3 and stats["p95_absolute_s"] <= frame_period_s and stats["max_absolute_s"] <= frame_period_s:
        classification = "FRAME_LEVEL_SYNC_WARNING"
    else:
        classification = "FRAME_LEVEL_SYNC_NOT_ESTABLISHED"
    return FrameLevelSyncModel(
        scale, selected_offset, model_type, len(pairs), stats,
        float(frame_period_s), classification, reason,
    )


def extract_brightness_series(
    video: str | Path,
    *,
    ffmpeg_executable: str | Path,
    sample_rate_hz: float = 10.0,
    width: int = 64,
    height: int = 36,
) -> tuple[np.ndarray, np.ndarray]:
    """Decode a low-resolution grayscale mean-intensity signal read-only."""
    if not np.isfinite(sample_rate_hz) or sample_rate_hz <= 0 or width <= 0 or height <= 0:
        raise ValueError("sample rate and image dimensions must be positive")
    command = [
        str(ffmpeg_executable), "-hide_banner", "-loglevel", "error", "-noautorotate", "-i", str(video),
        "-vf", f"fps={sample_rate_hz},scale={width}:{height},format=gray", "-f", "rawvideo", "-pix_fmt", "gray", "-",
    ]
    completed = subprocess.run(command, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.decode("utf-8", errors="replace"))
    frame_bytes = width * height
    if len(completed.stdout) == 0 or len(completed.stdout) % frame_bytes:
        raise ValueError("decoded brightness stream has an incomplete frame")
    frames = np.frombuffer(completed.stdout, dtype=np.uint8).reshape(-1, frame_bytes)
    brightness = frames.mean(axis=1, dtype=np.float64)
    timestamps = np.arange(brightness.size, dtype=np.float64) / sample_rate_hz
    return timestamps, brightness


def detect_brightness_events(
    timestamps_s: np.ndarray,
    brightness: np.ndarray,
    *,
    sigma_multiplier: float = 6.0,
    minimum_change: float = 3.0,
    minimum_separation_s: float = 0.5,
) -> tuple[BrightnessEvent, ...]:
    """Detect clustered robust derivative outliers without altering timestamps."""
    time_values = np.asarray(timestamps_s, dtype=np.float64)
    signal = np.asarray(brightness, dtype=np.float64)
    if time_values.ndim != 1 or signal.shape != time_values.shape or signal.size < 2:
        raise ValueError("timestamps and brightness must have equal one-dimensional shape")
    if not np.all(np.isfinite(time_values)) or not np.all(np.isfinite(signal)) or np.any(np.diff(time_values) <= 0):
        raise ValueError("timestamps must increase and all values must be finite")
    if sigma_multiplier <= 0 or minimum_change < 0 or minimum_separation_s < 0:
        raise ValueError("event thresholds must be non-negative and sigma_multiplier positive")
    difference = np.diff(signal)
    median = float(np.median(difference))
    mad = float(np.median(np.abs(difference - median)))
    robust_sigma = 1.4826 * mad
    threshold = max(float(minimum_change), sigma_multiplier * robust_sigma)
    candidates = np.flatnonzero(np.abs(difference - median) >= threshold)
    events: list[BrightnessEvent] = []
    for index in candidates:
        event = BrightnessEvent(float(time_values[index + 1]), float(difference[index]))
        if events and event.time_s - events[-1].time_s < minimum_separation_s:
            if abs(event.signed_change) > abs(events[-1].signed_change):
                events[-1] = event
        else:
            events.append(event)
    return tuple(events)


def estimate_event_offset(
    left_events: tuple[BrightnessEvent, ...],
    right_events: tuple[BrightnessEvent, ...],
    *,
    maximum_offset_s: float = 5.0,
    match_tolerance_s: float = 0.25,
) -> SynchronizationResult:
    """Estimate offset only when at least two same-polarity events agree."""
    if maximum_offset_s <= 0 or match_tolerance_s <= 0:
        raise ValueError("offset and tolerance must be positive")
    candidates = [
        right.time_s - left.time_s
        for left in left_events for right in right_events
        if np.sign(left.signed_change) == np.sign(right.signed_change)
        and abs(right.time_s - left.time_s) <= maximum_offset_s
    ]
    best: tuple[int, float, float, list[float]] | None = None
    for candidate in candidates:
        residuals: list[float] = []
        used: set[int] = set()
        for left in left_events:
            choices = [
                (abs((right.time_s - left.time_s) - candidate), index, right.time_s - left.time_s)
                for index, right in enumerate(right_events)
                if index not in used and np.sign(left.signed_change) == np.sign(right.signed_change)
            ]
            if choices:
                error, index, difference = min(choices)
                if error <= match_tolerance_s:
                    used.add(index); residuals.append(difference)
        if residuals:
            offset = float(np.median(residuals))
            rms = float(np.sqrt(np.mean((np.asarray(residuals) - offset) ** 2)))
            score = (len(residuals), -rms, -abs(offset), residuals)
            if best is None or score[:3] > best[:3]:
                best = score
    if best is None or best[0] < 2:
        return SynchronizationResult("SYNC_NOT_ESTABLISHED", None, "LOW", 0 if best is None else best[0], None)
    residuals = np.asarray(best[3])
    offset = float(np.median(residuals))
    rms = float(np.sqrt(np.mean((residuals - offset) ** 2)))
    confidence = "HIGH" if residuals.size >= 3 and rms <= match_tolerance_s / 2 else "MEDIUM"
    return SynchronizationResult("SYNC_ESTABLISHED_BY_LIGHT_EVENTS", offset, confidence, int(residuals.size), rms)
