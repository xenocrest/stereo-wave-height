"""Stable JSON and Markdown output for reconstruction consumers and future GUI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_result_json(path: Path, result: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def write_report(path: Path, result: dict[str, Any]) -> Path:
    """Render the uniform result summary without embedding large artifacts."""
    calibration = result["calibration"]
    lines = [
        "# Stereo Reconstruction Report", "",
        "## 1. Input", "",
        f"- Left video: `{result['input']['left_video']}`",
        f"- Right video: `{result['input']['right_video']}`",
        f"- Timestamp-paired frames: {result['frame_count']}", "",
        "## 2. Calibration", "",
        f"- Source: `{calibration['source']}`",
        f"- Parameters: OpenCV `K0/D0/K1/D1/R/T`, unchanged",
        f"- Baseline from calibrated T: {calibration['baseline_m']:.9f} m",
        f"- Quality mode: `{calibration['quality_mode']}`",
        f"- Original approved_for_wass: `{str(calibration['approved_for_wass']).lower()}`", "",
        "## 3. Processing", "",
        "- Backend: external WASS fixed-calibration path",
        "- Stages: prepare → match → restore fixed R/T → stereo",
        "- Autocalibration: not run",
        f"- Status: `{result['status']}`", "",
        "## 4. Point cloud and surface", "",
        "| Frame | Points | Plane RMS (mm) | Water-mask ratio | Height min/max (mm) |",
        "|---|---:|---:|---:|---:|",
    ]
    for frame in result["frames"]:
        lines.append(
            f"| {frame['frame_id']} | {frame['point_count']:,} | "
            f"{frame['water_plane_rms_m']*1000:.4f} | {frame['water_mask_ratio']:.6f} | "
            f"{frame['height_range_m'][0]*1000:.3f} / {frame['height_range_m'][1]*1000:.3f} |"
        )
    lines += ["", "## 5. Result boundary", "",
              "Heights are signed distances of WASS XYZ samples to the first configured static frame's fitted reference plane. "
              "They form an irregular pointwise height field `(X,Y,H)`, not an interpolated regular grid. "
              "No stereo, gridding, smoothing, or filtering algorithm is implemented here.", "",
              "This run verifies pipeline closure only. It does not establish industrial accuracy or override any calibration/static validation gate.", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
