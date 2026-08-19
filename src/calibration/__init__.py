"""Traceable camera-calibration models and checkerboard helpers."""

from .checkerboard import (
    CalibrationCameraRoles,
    CheckerboardDetection,
    CheckerboardSpec,
    StereoExtrinsics,
    detect_and_refine_checkerboard,
    stereo_baseline_m,
)
from .planar_grid import PlanarGridDiagnostics, PlanarGridHint, PlanarGridRecovery, orient_quad, recover_planar_grid
from .preflight import (
    CalibrationFrameAssessment,
    CalibrationFrameSample,
    CalibrationCandidateExtraction,
    DatasetReadiness,
    DiverseViewSelection,
    PreflightThresholds,
    StereoCalibrationPair,
    assess_checkerboard_frame,
    extract_calibration_video_candidates,
    pair_stereo_calibration_views,
    pose_signature_distance,
    select_diverse_calibration_views,
    summarize_dataset_readiness,
    target_preflight_status,
)
from .quality import CalibrationQualitySummary, CalibrationQualityThresholds, classify_calibration_quality

__all__ = [
    "CalibrationCameraRoles",
    "CheckerboardDetection",
    "CheckerboardSpec",
    "StereoExtrinsics",
    "PlanarGridDiagnostics",
    "PlanarGridHint",
    "PlanarGridRecovery",
    "CalibrationFrameAssessment",
    "CalibrationFrameSample",
    "CalibrationCandidateExtraction",
    "DatasetReadiness",
    "DiverseViewSelection",
    "PreflightThresholds",
    "StereoCalibrationPair",
    "CalibrationQualitySummary",
    "CalibrationQualityThresholds",
    "assess_checkerboard_frame",
    "extract_calibration_video_candidates",
    "pair_stereo_calibration_views",
    "pose_signature_distance",
    "select_diverse_calibration_views",
    "summarize_dataset_readiness",
    "target_preflight_status",
    "classify_calibration_quality",
    "detect_and_refine_checkerboard",
    "stereo_baseline_m",
    "orient_quad",
    "recover_planar_grid",
]
