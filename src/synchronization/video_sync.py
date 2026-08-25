"""Camera-independent light-event video synchronization diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
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
