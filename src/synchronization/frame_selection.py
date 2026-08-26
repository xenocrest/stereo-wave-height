"""PTS-based selection and quality gating for one on-demand stereo frame pair."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import subprocess

import numpy as np

from .affine import AffineTimeMapping


@dataclass(frozen=True)
class VideoFrameTimestamp:
    """One decoded video frame identified by presentation timestamp."""

    pts: int
    timestamp_s: float


@dataclass(frozen=True)
class SelectedTimestampPair:
    """Nearest decoded PTS pair and its right-clock residual."""

    requested_left_time_s: float
    left: VideoFrameTimestamp
    mapped_right_time_s: float
    right: VideoFrameTimestamp
    residual_s: float
    frame_period_s: float
    quality_status: str


_SHOWINFO = re.compile(r"\bpts:\s*(-?\d+)\s+pts_time:([0-9.eE+-]+)")


def probe_video_pts_window(
    video: str | Path,
    *,
    ffmpeg_executable: str | Path,
    center_time_s: float,
    half_window_s: float = 0.25,
) -> tuple[VideoFrameTimestamp, ...]:
    """Read decoded presentation timestamps near a target without altering video."""
    if not np.isfinite(center_time_s) or center_time_s < 0:
        raise ValueError("center_time_s must be finite and non-negative")
    if not np.isfinite(half_window_s) or half_window_s <= 0:
        raise ValueError("half_window_s must be finite and positive")
    start = max(0.0, center_time_s - half_window_s)
    command = [
        str(ffmpeg_executable), "-hide_banner", "-loglevel", "info",
        "-ss", f"{start:.9f}", "-copyts", "-i", str(video),
        "-to", f"{start + 2 * half_window_s:.9f}", "-vf", "showinfo", "-an", "-f", "null", os.devnull,
    ]
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"video PTS probe failed: {completed.stderr.strip()}")
    frames = tuple(
        VideoFrameTimestamp(int(match.group(1)), float(match.group(2)))
        for match in _SHOWINFO.finditer(completed.stderr)
    )
    if len(frames) < 2 or any(b.timestamp_s <= a.timestamp_s for a, b in zip(frames, frames[1:])):
        raise ValueError("PTS probe did not return a strictly increasing decoded frame sequence")
    return frames


def nearest_frame(frames: tuple[VideoFrameTimestamp, ...], target_s: float) -> VideoFrameTimestamp:
    """Return nearest presentation timestamp, with the earlier frame winning ties."""
    if not frames or not np.isfinite(target_s):
        raise ValueError("frames must be non-empty and target finite")
    errors = np.asarray([abs(frame.timestamp_s - target_s) for frame in frames], dtype=float)
    minimum = float(np.min(errors))
    tied = [
        frame
        for frame, error in zip(frames, errors, strict=True)
        if np.isclose(error, minimum, rtol=0.0, atol=1e-12)
    ]
    return min(tied, key=lambda frame: frame.timestamp_s)


def select_timestamp_pair(
    left_frames: tuple[VideoFrameTimestamp, ...],
    right_frames: tuple[VideoFrameTimestamp, ...],
    *,
    requested_left_time_s: float,
    mapping: AffineTimeMapping,
    mapping_confidence: str,
    frame_level_mapping_established: bool,
) -> SelectedTimestampPair:
    """Select a nearest PTS pair and apply a frame-period-derived quality gate.

    PASS requires a validated frame-level mapping and residual no larger than
    half the smaller observed frame period.  WARNING spans half to one frame.
    An unvalidated mapping always fails, regardless of a coincidentally small
    residual.
    """
    left = nearest_frame(left_frames, requested_left_time_s)
    mapped = float(mapping.map_left_to_right([left.timestamp_s])[0])
    right = nearest_frame(right_frames, mapped)
    residual = right.timestamp_s - mapped
    left_intervals = np.diff([frame.timestamp_s for frame in left_frames])
    right_intervals = np.diff([frame.timestamp_s for frame in right_frames])
    left_intervals = left_intervals[left_intervals > 0]
    right_intervals = right_intervals[right_intervals > 0]
    if left_intervals.size == 0 or right_intervals.size == 0:
        raise ValueError("frame period cannot be estimated")
    period = float(min(np.median(left_intervals), np.median(right_intervals)))
    confidence = mapping_confidence.upper()
    if not frame_level_mapping_established or confidence not in {"HIGH", "MEDIUM"}:
        status = "FRAME_LEVEL_SYNC_NOT_ESTABLISHED"
    elif abs(residual) <= 0.5 * period:
        status = "FRAME_PAIR_SYNC_ESTABLISHED"
    elif abs(residual) <= period:
        status = "FRAME_PAIR_SYNC_WARNING"
    else:
        status = "FRAME_PAIR_SYNC_FAILED"
    return SelectedTimestampPair(
        float(requested_left_time_s), left, mapped, right, float(residual), period, status
    )


def extract_frame_by_pts(
    video: str | Path,
    destination: str | Path,
    *,
    ffmpeg_executable: str | Path,
    frame: VideoFrameTimestamp,
    rotation_deg: int,
) -> Path:
    """Decode exactly one declared PTS and canonicalize orientation."""
    rotation = rotation_deg % 360
    if rotation not in (0, 90, 180, 270):
        raise ValueError("rotation_deg must be 0/90/180/270")
    orientation = {
        0: "format=gray",
        90: "select='eq(pts\\,{pts})',transpose=1,format=gray",
        180: "select='eq(pts\\,{pts})',hflip,vflip,format=gray",
        270: "select='eq(pts\\,{pts})',transpose=2,format=gray",
    }[rotation]
    if rotation == 0:
        orientation = "select='eq(pts\\,{pts})',format=gray"
    filter_value = orientation.format(pts=frame.pts)
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    start = max(0.0, frame.timestamp_s - 0.5)
    command = [
        str(ffmpeg_executable), "-hide_banner", "-loglevel", "error",
        "-ss", f"{start:.9f}", "-copyts", "-i", str(video),
        "-vf", filter_value, "-frames:v", "1", "-vsync", "0", "-y", str(target),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if completed.returncode != 0 or not target.is_file():
        raise RuntimeError(f"exact PTS extraction failed: {completed.stderr.strip()}")
    return target
