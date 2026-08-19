"""Traceable camera-calibration models and checkerboard helpers."""

from .checkerboard import (
    CalibrationCameraRoles,
    CheckerboardDetection,
    CheckerboardSpec,
    StereoExtrinsics,
    detect_and_refine_checkerboard,
    stereo_baseline_m,
)

__all__ = [
    "CalibrationCameraRoles",
    "CheckerboardDetection",
    "CheckerboardSpec",
    "StereoExtrinsics",
    "detect_and_refine_checkerboard",
    "stereo_baseline_m",
]
