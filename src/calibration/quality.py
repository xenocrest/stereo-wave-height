"""Traceable calibration-result quality gates and serializable summaries."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable


@dataclass(frozen=True)
class CalibrationQualityThresholds:
    """Project-configured review thresholds, not universal scientific limits."""

    maximum_mono_rms_px: float = 1.0
    maximum_stereo_rms_px: float = 1.5
    maximum_epipolar_rms_px: float = 1.0
    maximum_rectification_rms_px: float = 1.0
    minimum_views: int = 12


@dataclass(frozen=True)
class CalibrationQualitySummary:
    initial_view_count: int
    accepted_view_count: int
    rejected_views: tuple[tuple[str, str], ...]
    mono_left_rms_px: float | None
    mono_right_rms_px: float | None
    stereo_rms_px: float | None
    epipolar_rms_px: float | None
    rectification_rms_px: float | None
    baseline_m: float | None
    rectification_valid: bool
    classification: str

    def as_mapping(self) -> dict[str, object]:
        return {
            "initial_view_count": self.initial_view_count,
            "accepted_view_count": self.accepted_view_count,
            "rejected_views": [{"view_id": view, "reason": reason} for view, reason in self.rejected_views],
            "mono_left_rms_px": self.mono_left_rms_px,
            "mono_right_rms_px": self.mono_right_rms_px,
            "stereo_rms_px": self.stereo_rms_px,
            "epipolar_rms_px": self.epipolar_rms_px,
            "rectification_rms_px": self.rectification_rms_px,
            "baseline_m": self.baseline_m,
            "rectification_valid": self.rectification_valid,
            "classification": self.classification,
        }


def classify_calibration_quality(
    *,
    initial_view_count: int,
    accepted_view_ids: Iterable[str],
    rejected_views: Iterable[tuple[str, str]] = (),
    mono_left_rms_px: float | None,
    mono_right_rms_px: float | None,
    stereo_rms_px: float | None,
    epipolar_rms_px: float | None,
    rectification_rms_px: float | None,
    baseline_m: float | None,
    rectification_valid: bool,
    thresholds: CalibrationQualityThresholds = CalibrationQualityThresholds(),
) -> CalibrationQualitySummary:
    """Apply one explicit quality gate; this function never removes views."""
    accepted = tuple(accepted_view_ids); rejected = tuple(rejected_views)
    if len(accepted) < thresholds.minimum_views:
        classification = "CALIBRATION_DATASET_INSUFFICIENT"
    elif any(value is None or not math.isfinite(value) for value in (mono_left_rms_px, mono_right_rms_px, stereo_rms_px, epipolar_rms_px, rectification_rms_px, baseline_m)):
        classification = "CALIBRATION_RESULT_INCOMPLETE"
    elif mono_left_rms_px > thresholds.maximum_mono_rms_px or mono_right_rms_px > thresholds.maximum_mono_rms_px or stereo_rms_px > thresholds.maximum_stereo_rms_px:
        classification = "CALIBRATION_HIGH_REPROJECTION_ERROR"
    elif epipolar_rms_px > thresholds.maximum_epipolar_rms_px:
        classification = "CALIBRATION_POOR_EPIPOLAR_GEOMETRY"
    elif not rectification_valid or rectification_rms_px > thresholds.maximum_rectification_rms_px:
        classification = "CALIBRATION_RECTIFICATION_FAIL"
    elif baseline_m <= 0:
        classification = "CALIBRATION_INVALID_BASELINE"
    else:
        classification = "CALIBRATION_PASS"
    return CalibrationQualitySummary(
        initial_view_count, len(accepted), rejected, mono_left_rms_px,
        mono_right_rms_px, stereo_rms_px, epipolar_rms_px,
        rectification_rms_px, baseline_m, rectification_valid, classification,
    )
