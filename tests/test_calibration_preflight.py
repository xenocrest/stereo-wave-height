"""Calibration preflight, diversity, pairing, quality, and GUI model tests."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

import numpy as np

from application import CalibrationPageModel
from calibration import (
    CalibrationFrameAssessment,
    CalibrationFrameSample,
    CalibrationQualityThresholds,
    CheckerboardSpec,
    DatasetReadiness,
    DiverseViewSelection,
    PreflightThresholds,
    assess_checkerboard_frame,
    classify_calibration_quality,
    extract_calibration_video_candidates,
    pair_stereo_calibration_views,
    pose_signature_distance,
    select_diverse_calibration_views,
    summarize_dataset_readiness,
    target_preflight_status,
)


CV2_AVAILABLE = importlib.util.find_spec("cv2") is not None


def assessment(frame_id: str, timestamp_ns: int, signature: tuple[float, ...], *, usable: bool = True) -> CalibrationFrameAssessment:
    return CalibrationFrameAssessment(
        frame_id, timestamp_ns, "cam0", True, 54, 54,
        np.zeros((54, 1, 2), np.float32), 0.15, 0.16, 200.0,
        30.0, signature[-1], 0.0, signature, None if usable else "rejected", (), usable,
    )


@unittest.skipUnless(CV2_AVAILABLE, "optional OpenCV calibration backend not installed")
class CheckerboardPreflightImageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import cv2
        cls.cv2 = cv2
        cls.spec = CheckerboardSpec(9, 6, 0.020)

    def checkerboard(self, *, blur: int = 0) -> np.ndarray:
        cv2 = self.cv2
        board = np.zeros((700, 1000), np.uint8)
        for row in range(7):
            for col in range(10):
                board[row * 100:(row + 1) * 100, col * 100:(col + 1) * 100] = 255 if (row + col) % 2 else 0
        source = np.float32([[0, 0], [999, 0], [999, 699], [0, 699]])
        target = np.float32([[180, 120], [1110, 170], [1050, 780], [240, 740]])
        image = self.cv2.warpPerspective(board, self.cv2.getPerspectiveTransform(source, target), (1280, 900), borderValue=127)
        return cv2.GaussianBlur(image, (blur, blur), 0) if blur else image

    def test_standard_checkerboard_detects_54_subpixel_points(self) -> None:
        item = assess_checkerboard_frame(
            self.checkerboard(), self.spec, frame_id="sharp", timestamp_ns=0,
            camera_role="cam0", thresholds=PreflightThresholds(minimum_sharpness=1.0), cv2_module=self.cv2,
        )
        self.assertTrue(item.detected)
        self.assertEqual(item.corner_count, 54)
        self.assertEqual(item.corners_subpixel_px.shape, (54, 1, 2))
        self.assertGreater(item.coverage_fraction, 0.04)
        self.assertEqual(len(item.pose_signature), 7)

    def test_blur_is_scored_and_rejected_by_configured_threshold(self) -> None:
        sharp = assess_checkerboard_frame(self.checkerboard(), self.spec, frame_id="a", timestamp_ns=0, camera_role="cam0", cv2_module=self.cv2)
        blurred = assess_checkerboard_frame(self.checkerboard(blur=31), self.spec, frame_id="b", timestamp_ns=1, camera_role="cam0", thresholds=PreflightThresholds(minimum_sharpness=sharp.sharpness_score * 0.5), cv2_module=self.cv2)
        self.assertLess(blurred.sharpness_score, sharp.sharpness_score)
        self.assertFalse(blurred.usable)
        self.assertIn("sharpness", blurred.reject_reason)

    def test_pts_candidate_extraction_downsamples_and_deduplicates(self) -> None:
        image = self.checkerboard()
        samples = [CalibrationFrameSample(f"f{i}", i * 100_000_000, "container_pts", "cam0", image) for i in range(8)]
        result = extract_calibration_video_candidates(
            samples, self.spec, minimum_interval_ns=250_000_000,
            thresholds=PreflightThresholds(minimum_sharpness=1.0), cv2_module=self.cv2,
        )
        self.assertEqual(len(result.sampled), 3)
        self.assertEqual(len(result.diverse.accepted), 1)
        self.assertEqual(result.timestamp_source, "container_pts")


class PoseDiversityTests(unittest.TestCase):
    base = (0.5, 0.5, -2.0, 0.0, 0.5, 0.0, 0.05)

    def test_same_pose_is_near_duplicate(self) -> None:
        a = assessment("a", 0, self.base); b = assessment("b", 1, (0.505, 0.5, -2.01, 0.002, 0.502, 0.0, 0.05))
        self.assertLess(pose_signature_distance(a, b), 0.12)
        selected = select_diverse_calibration_views([a, b], duplicate_distance=0.12)
        self.assertEqual(len(selected.accepted), 1); self.assertEqual(len(selected.duplicates), 1)

    def test_clearly_different_poses_are_separated(self) -> None:
        a = assessment("a", 0, self.base); b = assessment("b", 1, (0.8, 0.2, -1.2, 0.25, 0.7, 0.3, 0.4))
        selected = select_diverse_calibration_views([a, b], duplicate_distance=0.12)
        self.assertEqual(len(selected.accepted), 2)

    def test_selection_is_deterministic(self) -> None:
        items = [assessment(str(i), i, (0.1 + i * 0.04, 0.2 + i * 0.03, -2 + i * 0.1, i * 0.03, 0.5, 0.0, 0.05)) for i in range(8)]
        first = select_diverse_calibration_views(items, duplicate_distance=0.05)
        second = select_diverse_calibration_views(reversed(items), duplicate_distance=0.05)
        self.assertEqual([x.frame_id for x in first.accepted], [x.frame_id for x in second.accepted])

    def test_dataset_readiness_threshold(self) -> None:
        selected = DiverseViewSelection(tuple(assessment(str(i), i, (0.1 + (i % 4) * 0.2, 0.1 + (i % 3) * 0.25, -2.5 + i * 0.08, i * 0.02, 0.5 + i * 0.01, 0.0, 0.1)) for i in range(12)), (), (), ())
        summary = summarize_dataset_readiness(selected)
        self.assertEqual(summary.independent_pose_count, 12)
        self.assertNotEqual(summary.status, "CALIBRATION_DATASET_INSUFFICIENT")

    def test_below_twelve_is_insufficient(self) -> None:
        selected = DiverseViewSelection(tuple(assessment(str(i), i, self.base) for i in range(11)), (), (), ())
        self.assertEqual(summarize_dataset_readiness(selected).status, "CALIBRATION_DATASET_INSUFFICIENT")


class StereoPairingTests(unittest.TestCase):
    def test_pairing_uses_timestamps_not_frame_indices(self) -> None:
        signature = (0.5, 0.5, -2.0, 0.0, 0.5, 0.0, 0.05)
        left = [assessment("left_100", 1_000_000_000, signature)]
        right_item = assessment("right_9000", 1_001_000_000, signature)
        right_item = CalibrationFrameAssessment(**{**right_item.__dict__, "camera_role": "cam1"})
        pairs = pair_stereo_calibration_views(left, [right_item], maximum_delta_t_ns=2_000_000, maximum_pose_distance=0.1)
        self.assertEqual(len(pairs), 1); self.assertEqual(pairs[0].delta_t_ns, 1_000_000)

    def test_pose_geometry_mismatch_is_not_paired(self) -> None:
        left = [assessment("l", 0, (0.1, 0.1, -3.0, 0.0, 0.5, 0.0, 0.0))]
        right = [assessment("r", 0, (0.9, 0.9, -1.0, 0.4, 0.8, 0.5, 0.7))]
        self.assertEqual(pair_stereo_calibration_views(left, right, maximum_delta_t_ns=1, maximum_pose_distance=0.1), ())

    def test_gate_a_requires_bilateral_usable_pair(self) -> None:
        signature = (0.5, 0.5, -2.0, 0.0, 0.5, 0.0, 0.05)
        left = assessment("l", 0, signature); right = assessment("r", 0, signature)
        pair = pair_stereo_calibration_views([left], [right], maximum_delta_t_ns=1, maximum_pose_distance=0.1)[0]
        self.assertEqual(target_preflight_status(left, right, pair), "TARGET_PREFLIGHT_PASS")
        self.assertEqual(target_preflight_status(left, right, None), "TARGET_PREFLIGHT_FAIL")


class QualityAndGuiTests(unittest.TestCase):
    def test_quality_summary_serializes_and_passes(self) -> None:
        summary = classify_calibration_quality(
            initial_view_count=13, accepted_view_ids=[str(i) for i in range(12)], rejected_views=[("bad", "high per-view RMS")],
            mono_left_rms_px=0.4, mono_right_rms_px=0.5, stereo_rms_px=0.8,
            epipolar_rms_px=0.4, rectification_rms_px=0.5, baseline_m=0.2,
            rectification_valid=True, thresholds=CalibrationQualityThresholds(),
        )
        self.assertEqual(summary.classification, "CALIBRATION_PASS")
        json.dumps(summary.as_mapping())

    def test_high_reprojection_error_has_explicit_classification(self) -> None:
        summary = classify_calibration_quality(
            initial_view_count=12, accepted_view_ids=[str(i) for i in range(12)],
            mono_left_rms_px=2.0, mono_right_rms_px=0.5, stereo_rms_px=0.8,
            epipolar_rms_px=0.4, rectification_rms_px=0.5, baseline_m=0.2, rectification_valid=True,
        )
        self.assertEqual(summary.classification, "CALIBRATION_HIGH_REPROJECTION_ERROR")

    def test_gui_model_receives_status_without_recomputing_metrics(self) -> None:
        item = assessment("a", 0, (0.5, 0.5, -2.0, 0.0, 0.5, 0.0, 0.05))
        dataset = DatasetReadiness(12, "PASS", "PASS", "PASS", 0.8, "CALIBRATION_DATASET_READY_WITH_WARNING", ())
        model = CalibrationPageModel.from_assessments(cam0=item, cam1=item, dataset=dataset, quality=None, candidate_count=18, experiment_status="PENDING")
        self.assertIn("54/54", model.cam0_text); self.assertIn("Independent poses 12", model.dataset_text)

    def test_hometank_003_template_remains_pending(self) -> None:
        root = Path(__file__).resolve().parents[1]
        manifest = (root / "experiments/real_video/HomeTank_003/manifest_template.yaml").read_text(encoding="utf-8")
        self.assertIn("status: NOT_CAPTURED", manifest)
        self.assertIn("calibration_result_status: PENDING", manifest)


if __name__ == "__main__":
    unittest.main()
