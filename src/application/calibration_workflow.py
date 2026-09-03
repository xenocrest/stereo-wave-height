"""Video orchestration around the existing official OpenCV calibration backend."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml

from calibration import CheckerboardSpec, calibrate_stereo_official, detect_checkerboard_official
from .video_tools import extract_frame, probe_video


@dataclass(frozen=True)
class VideoCalibrationRun:
    result_path: Path
    paired_views: int


def calibrate_from_videos(
    left_video: Path,
    right_video: Path,
    ffmpeg: Path,
    output_path: Path,
    *,
    corners_x: int,
    corners_y: int,
    square_size_mm: float,
    sample_count: int = 24,
) -> VideoCalibrationRun:
    """Sample paired times, detect complete boards, and call the frozen OpenCV backend."""
    spec = CheckerboardSpec(corners_x, corners_y, square_size_mm / 1000.0)
    left_meta, right_meta = probe_video(left_video, ffmpeg), probe_video(right_video, ffmpeg)
    if (left_meta.width, left_meta.height) != (right_meta.width, right_meta.height):
        raise ValueError("左右标定视频分辨率不同，无法进行双目标定。")
    duration = min(left_meta.duration_sec, right_meta.duration_sec)
    times = np.linspace(duration * 0.05, duration * 0.95, sample_count)
    objects: list[np.ndarray] = []
    left_points: list[np.ndarray] = []
    right_points: list[np.ndarray] = []
    for timestamp in times:
        left = np.asarray(extract_frame(left_video, float(timestamp), ffmpeg).convert("L"), dtype=np.uint8)
        right = np.asarray(extract_frame(right_video, float(timestamp), ffmpeg).convert("L"), dtype=np.uint8)
        ld = detect_checkerboard_official(left, spec, allow_clahe_fallback=True)
        rd = detect_checkerboard_official(right, spec, allow_clahe_fallback=True)
        if ld is None or rd is None:
            continue
        objects.append(spec.object_points_m())
        left_points.append(ld.corners_px)
        right_points.append(rd.corners_px)
    # Four complete paired poses are sufficient for OpenCV to produce finite
    # candidate geometry for the GUI's explicitly non-production demo route.
    # Quality gates still decide whether that candidate is validated; sparse
    # capture coverage is therefore diagnostic, not an unconditional UI exit.
    if len(objects) < 4:
        raise RuntimeError(f"有效同步标定视图不足：检测到 {len(objects)} 组，至少需要 4 组才能求解演示候选。请检查棋盘参数、清晰度和左右同步画面。")
    result = calibrate_stereo_official(
        objects, left_points, right_points, (left_meta.width, left_meta.height),
        square_size_m=spec.square_size_m,
    )
    payload = {
        "schema_version": "1.0", "status": "GUI_CALIBRATION_COMPLETED_REQUIRES_QA",
        "image_size_wh": [left_meta.width, left_meta.height],
        "approved_for_wass": False, "backend": "OPENCV_OFFICIAL",
        "target": {"inner_corners": [corners_x, corners_y], "square_size_m": spec.square_size_m},
        "mono_cam0": {"model": "LEFT", "rms_px": result.mono_left.rms_px,
                      "K": result.mono_left.camera_matrix.tolist(), "D": result.mono_left.distortion.reshape(-1).tolist()},
        "mono_cam1": {"model": "RIGHT", "rms_px": result.mono_right.rms_px,
                      "K": result.mono_right.camera_matrix.tolist(), "D": result.mono_right.distortion.reshape(-1).tolist()},
        "stereo": {"rms_px": result.stereo_rms_px,
                   "R_right_from_left": result.rotation_right_from_left.tolist(),
                   "T_right_from_left_m": result.translation_right_from_left_m.reshape(-1).tolist(),
                   "baseline_m": result.baseline_m,
                   "symmetric_epipolar_rms_px": result.epipolar_rms_px,
                   "symmetric_epipolar_max_px": result.epipolar_max_px},
        "rectification": {"vertical_disparity_rms_px": result.rectification.vertical_disparity_rms_px,
                          "vertical_disparity_max_px": result.rectification.vertical_disparity_max_px},
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return VideoCalibrationRun(output_path, len(objects))
