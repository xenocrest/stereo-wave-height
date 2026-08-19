"""Presentation-only model for the desktop Calibration page."""

from __future__ import annotations

from dataclasses import dataclass

from calibration import CalibrationFrameAssessment, CalibrationQualitySummary, DatasetReadiness


@dataclass(frozen=True)
class CalibrationPageModel:
    target_text: str
    cam0_text: str
    cam1_text: str
    dataset_text: str
    result_text: str
    experiment_status: str

    @classmethod
    def pending(cls) -> "CalibrationPageModel":
        return cls(
            "Target: 9 x 6 inner corners / 20 mm squares",
            "CAM0: no preflight result",
            "CAM1: no preflight result",
            "Dataset: Candidates 0 / Independent poses 0 / NOT READY",
            "Calibration result: not available",
            "PENDING / NOT_CAPTURED",
        )

    @classmethod
    def from_assessments(
        cls,
        *,
        cam0: CalibrationFrameAssessment | None,
        cam1: CalibrationFrameAssessment | None,
        dataset: DatasetReadiness | None,
        quality: CalibrationQualitySummary | None,
        candidate_count: int,
        experiment_status: str,
    ) -> "CalibrationPageModel":
        def camera_text(role: str, item: CalibrationFrameAssessment | None) -> str:
            if item is None: return f"{role}: no preflight result"
            state = "PASS" if item.usable else "FAIL"
            return (
                f"{role}: Detected corners {item.corner_count}/{item.expected_corner_count} | "
                f"Sharpness {item.sharpness_score:.1f} | Coverage {item.coverage_fraction:.3f} | {state}"
            )
        dataset_text = "Dataset: not assessed"
        if dataset is not None:
            dataset_text = (
                f"Dataset: Candidates {candidate_count} | Independent poses {dataset.independent_pose_count} | "
                f"Position {dataset.position_coverage} | Orientation {dataset.orientation_diversity} | {dataset.status}"
            )
        result_text = "Calibration result: not available"
        if quality is not None:
            result_text = (
                f"Calibration: Mono L {quality.mono_left_rms_px} px | Mono R {quality.mono_right_rms_px} px | "
                f"Stereo {quality.stereo_rms_px} px | Epipolar {quality.epipolar_rms_px} px | "
                f"Baseline {quality.baseline_m} m | {quality.classification}"
            )
        return cls(
            "Target: 9 x 6 inner corners / 20 mm squares",
            camera_text("CAM0", cam0), camera_text("CAM1", cam1),
            dataset_text, result_text, experiment_status,
        )
