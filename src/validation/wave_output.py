"""Stable CSV/JSON output contracts for camera-independent wave results."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
import json
from pathlib import Path

import numpy as np

from .wave_statistics import height_statistics


@dataclass(frozen=True)
class WaveFrameRecord:
    """One timestamped spatial height summary in metres."""

    frame: str
    timestamp_ns: int
    valid_points: int
    mean_H_m: float
    median_H_m: float
    rms_H_m: float
    p5_H_m: float
    p95_H_m: float
    min_H_m: float
    max_H_m: float


def build_wave_frame_record(frame: str, timestamp_ns: int, height_m: np.ndarray) -> WaveFrameRecord:
    """Build a deterministic record from raw valid ROI height samples."""
    if not frame or not isinstance(timestamp_ns, int) or timestamp_ns < 0:
        raise ValueError("frame and non-negative integer timestamp_ns are required")
    summary = height_statistics(height_m)
    return WaveFrameRecord(
        frame=frame,
        timestamp_ns=timestamp_ns,
        valid_points=summary.count,
        mean_H_m=summary.mean,
        median_H_m=summary.median,
        rms_H_m=summary.rms,
        p5_H_m=summary.p5,
        p95_H_m=summary.p95,
        min_H_m=summary.minimum,
        max_H_m=summary.maximum,
    )


def write_wave_timeseries_csv(
    path: str | Path,
    records: list[WaveFrameRecord],
    low_frequency_baseline_m: np.ndarray,
    filtered_height_m: np.ndarray,
) -> Path:
    """Write raw and analysis-only series side by side."""
    baseline = np.asarray(low_frequency_baseline_m, dtype=np.float64)
    filtered = np.asarray(filtered_height_m, dtype=np.float64)
    if not records or baseline.shape != (len(records),) or filtered.shape != baseline.shape:
        raise ValueError("records, baseline and filtered series must have equal non-empty length")
    if not np.all(np.isfinite(baseline)) or not np.all(np.isfinite(filtered)):
        raise ValueError("analysis series must be finite")
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(asdict(records[0])) + ["low_frequency_baseline_m", "filtered_H_m"]
    with destination.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for record, base, corrected in zip(records, baseline, filtered):
            writer.writerow({**asdict(record), "low_frequency_baseline_m": base, "filtered_H_m": corrected})
    return destination


def write_wave_result_json(path: str | Path, result: dict[str, object]) -> Path:
    """Write the unified non-GUI result without altering its scientific status."""
    required = {"status", "height_series", "statistics", "validation_status"}
    missing = required.difference(result)
    if missing:
        raise ValueError(f"wave result lacks required fields: {sorted(missing)}")
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return destination
