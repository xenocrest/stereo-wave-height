from pathlib import Path
import unittest


class HomeTank004InputInspectionTests(unittest.TestCase):
    def test_input_remains_registered_and_failed_calibration_is_not_approved(self):
        root = Path(__file__).resolve().parents[1] / "experiments" / "real_video" / "HomeTank_004"
        expected = {
            "manifest.yaml", "measured_geometry.yaml", "calibration_result.yaml",
            "fallback_geometry.yaml", "result_summary.md", "videos",
            "video_metadata_summary.yaml", "input_inspection.md",
            "calibration_detection_summary.yaml", "calibration_metrics.json",
            "calibration_report.md", "coarse_geometry_candidates.yaml",
            "coarse_geometry_reassessment.md", "calibration_validation.yaml",
            "calibration_validation.md", "calibration_parameter_usage.yaml",
            "static_trial_plan.yaml", "static_trial_full_calibration.yaml",
            "static_trial_full_calibration.md", "fixed_calibration_rectification_audit.md",
            "rectification_policy.yaml", "rectification_policy_result.md",
            "fixed_calibration_rectification_policy_audit.md",
            "rectification_policy_compatibility.yaml",
            "rectification_policy_compatibility_report.md",
        }
        self.assertEqual({path.name for path in root.iterdir()}, expected)
        self.assertIn("CALIBRATION_QUALITY_FAIL", (root / "manifest.yaml").read_text(encoding="utf-8"))
        self.assertIn("strict_calibration_failed: true", (root / "calibration_result.yaml").read_text(encoding="utf-8"))
        self.assertIn("approved_for_wass: false", (root / "calibration_result.yaml").read_text(encoding="utf-8"))
        for condition in ("calibration", "static", "wave"):
            directory = root / "videos" / condition
            self.assertTrue(directory.is_dir())
            self.assertTrue((directory / ".gitkeep").is_file())

    def test_corrected_geometry_and_coarse_candidates_preserve_strict_failure(self):
        root = Path(__file__).resolve().parents[1] / "experiments" / "real_video" / "HomeTank_004"
        measured = (root / "measured_geometry.yaml").read_text(encoding="utf-8")
        for required in (
            "previous manual geometry values contained a decimal-place / factor-of-10 transcription error",
            "baseline_m: 0.700", "value: 0.070", "value: 0.190", "value: 0.170",
        ):
            self.assertIn(required, measured)

        result = (root / "calibration_result.yaml").read_text(encoding="utf-8")
        self.assertIn("status: CALIBRATION_QUALITY_FAIL", result)
        self.assertIn("approved_for_wass: false", result)
        self.assertIn("absolute_difference_m: 0.00131528841525623", result)
        self.assertIn("relative_difference_percent_of_measured: 1.8789834503660428", result)

        candidates = (root / "coarse_geometry_candidates.yaml").read_text(encoding="utf-8")
        self.assertIn("metrological_validity: false", candidates)
        self.assertIn("workflow_principle: MATURE_CALIBRATION_FIRST", candidates)
        self.assertIn("id: FULL_CALIBRATION", candidates)
        self.assertIn("id: CALIBRATION_ZERO_DISTORTION", candidates)
        self.assertIn("id: SPECIFICATION_INTRINSIC_REFERENCE", candidates)
        self.assertNotIn("T_hybrid", candidates)
        self.assertNotIn("T_magnitude: USER_SPECIFIED", candidates)

        usage = (root / "calibration_parameter_usage.yaml").read_text(encoding="utf-8")
        self.assertIn("usage: PHYSICAL_SANITY_CHECK_ONLY", usage)
        self.assertIn("may_override_calibration: false", usage)
        plan = (root / "static_trial_plan.yaml").read_text(encoding="utf-8")
        self.assertIn("status: CANDIDATE_A_COMPLETED_INVALID", plan)
        self.assertIn("wave_data_allowed: false", plan)
        self.assertIn("run_wass_autocalibrate: false", plan)

    def test_full_calibration_static_trial_schema_and_failure_are_explicit(self):
        root = Path(__file__).resolve().parents[1] / "experiments" / "real_video" / "HomeTank_004"
        result = (root / "static_trial_full_calibration.yaml").read_text(encoding="utf-8")
        for required in (
            "candidate: FULL_CALIBRATION",
            "T: OPENCV_STEREO_CALIBRATION_RESULT_UNCHANGED",
            "manual_baseline_used_for_reconstruction: false",
            "status: NOT_RUN_PROHIBITED",
            "primary_error: epipole lies inside the image plane",
            "xyz_point_count: 0",
            "static_trial_result: STATIC_GEOMETRY_INVALID",
            "strict_calibration_status_preserved: CALIBRATION_QUALITY_FAIL",
            "approved_for_wass: false",
            "wave_run: false",
            "candidate_b_run: false",
            "candidate_c_run: false",
        ):
            self.assertIn(required, result)

    def test_fixed_calibration_convention_audit_preserves_failure(self):
        root = Path(__file__).resolve().parents[1] / "experiments" / "real_video" / "HomeTank_004"
        audit = (root / "fixed_calibration_rectification_audit.md").read_text(encoding="utf-8")
        for required in (
            "X_second = R * X_first + T",
            "X_cam1 = ext_R * X_cam0 + ext_T",
            "R/T_DIRECTION_CONVERSION_REQUIRED = false",
            "LEFT_RIGHT_INPUT_ERROR = false",
            "TRANSLATION_UNIT_ERROR = false",
            "CALIBRATION_QUALITY_FAIL",
            "approved_for_wass=false",
            "FAILED_AT_WASS_RECTIFICATION",
        ):
            self.assertIn(required, audit)

    def test_policy_compatibility_result_is_fail_fast_not_fabricated(self):
        root = Path(__file__).resolve().parents[1] / "experiments" / "real_video" / "HomeTank_004"
        result = (root / "rectification_policy_compatibility.yaml").read_text(encoding="utf-8")
        for required in (
            "candidate: FULL_CALIBRATION",
            "candidate_parameters_changed: false",
            "policy_interface: NOT_RUNTIME_CONFIGURABLE",
            "test: A0", "test: A1", "test: A2", "test: A3",
            "rectification_policy_compatible: false",
            "BLOCKED_BY_PRODUCTION_WASS_POLICY_INTERFACE",
            "static_reconstruction_run: false",
            "approved_for_wass: false",
        ):
            self.assertIn(required, result)

    def test_rectification_policy_audit_schema_preserves_candidate_a(self):
        root = Path(__file__).resolve().parents[1] / "experiments" / "real_video" / "HomeTank_004"
        audit = (root / "fixed_calibration_rectification_policy_audit.md").read_text(encoding="utf-8")
        for required in (
            "validPixROI1 = [0, 0, 1920, 1079]",
            "validPixROI2 = [0, 0, 1920, 1080]",
            "(4277.6657, 134.7423) px",
            "(3786.6227, 28.8087) px",
            "EPIPOLE_INSIDE_IMAGE=false",
            "RECTIFICATION_POLICY_ROI_INCOMPATIBILITY",
            "CALIBRATION_QUALITY_FAIL",
            "approved_for_wass=false",
            "No adapter modification",
        ):
            self.assertIn(required, audit)


if __name__ == "__main__":
    unittest.main()
