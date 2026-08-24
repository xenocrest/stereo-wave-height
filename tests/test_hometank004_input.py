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
            "static_pointcloud_diagnosis.md",
            "plane_ransac_config.yaml", "plane_ransac_result.yaml",
            "plane_ransac_sampling_update.md",
            "static_validation_summary.yaml", "static_validation_summary.md",
            "static_frame_geometry_diagnostic.md",
            "static_frame_consistency_diagnostic.yaml",
            "static_frame_consistency_diagnostic.md",
            "wass_disparity_range_audit.md",
            "wass_sgbm_matching_parameter_audit.md",
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

    def test_static_pointcloud_diagnosis_preserves_frozen_status(self):
        root = Path(__file__).resolve().parents[1] / "experiments" / "real_video" / "HomeTank_004"
        report = (root / "static_pointcloud_diagnosis.md").read_text(encoding="utf-8")
        for required in (
            "PLANE_PRESENT_BUT_RANSAC_TOO_STRICT",
            "RANSAC_VALID_TRIPLET_SAMPLING_INSUFFICIENT",
            "167,581",
            "2.2490 mm",
            "80.9620%",
            "approved_for_wass=false",
            "Wave remains prohibited",
        ):
            self.assertIn(required, report)

    def test_valid_point_ransac_result_preserves_calibration_failure(self):
        root = Path(__file__).resolve().parents[1] / "experiments" / "real_video" / "HomeTank_004"
        config = (root / "plane_ransac_config.yaml").read_text(encoding="utf-8")
        result = (root / "plane_ransac_result.yaml").read_text(encoding="utf-8")
        report = (root / "plane_ransac_sampling_update.md").read_text(encoding="utf-8")
        self.assertIn("sampling_mode: VALID_POINT_SAMPLING", config)
        self.assertIn("iterations: 400", config)
        self.assertIn("distance_threshold: 1.0", config)
        self.assertIn("minimum_best_inliers: 33286", result)
        self.assertIn("maximum_plane_rms_m: 0.0022490853", result)
        self.assertIn("water_plane_status: STATIC_WATER_PLANE_DETECTED", result)
        self.assertIn("approved_for_wass: false", result)
        self.assertIn("No wave result was generated", report)

    def test_static_validation_summary_freezes_unstable_baseline(self):
        root = Path(__file__).resolve().parents[1] / "experiments" / "real_video" / "HomeTank_004"
        summary = (root / "static_validation_summary.yaml").read_text(encoding="utf-8")
        report = (root / "static_validation_summary.md").read_text(encoding="utf-8")
        self.assertIn("status: STATIC_VALIDATION_FAIL", summary)
        self.assertIn("conclusion: STATIC_BASELINE_UNSTABLE", summary)
        self.assertEqual(summary.count("frame_id:"), 3)
        self.assertIn("scale_validation:\n  status: FAIL", summary)
        self.assertIn("approved_for_wass: false", summary)
        self.assertIn("authorized: false", summary)
        self.assertIn("No WASS stage was rerun", report)
        self.assertIn("processing remains unauthorized", report)

    def test_static_frame_geometry_diagnostic_preserves_failure_gate(self):
        root = Path(__file__).resolve().parents[1] / "experiments" / "real_video" / "HomeTank_004"
        report = (root / "static_frame_geometry_diagnostic.md").read_text(encoding="utf-8")
        self.assertIn("DIFFERENT_VISIBLE_RECONSTRUCTED_REGION", report)
        self.assertIn("No frame-dependent WASS calibration", report)
        self.assertIn("216,874 | 585.2716", report)
        self.assertIn("133,968 | 488.8168", report)
        self.assertIn("141,950 | 478.1076", report)
        self.assertIn("STATIC_VALIDATION_FAIL", report)
        self.assertIn("approved_for_wass=false", report)
        self.assertIn("Wave remains prohibited", report)

    def test_static_frame_consistency_diagnostic_is_read_only_and_general(self):
        root = Path(__file__).resolve().parents[1] / "experiments" / "real_video" / "HomeTank_004"
        result = (root / "static_frame_consistency_diagnostic.yaml").read_text(encoding="utf-8")
        report = (root / "static_frame_consistency_diagnostic.md").read_text(encoding="utf-8")
        for required in (
            "classification: MIXED_IMAGE_VARIATION_AND_MATCHING_INSTABILITY",
            "wass_configuration: UNCHANGED",
            "autocalibration_run: false",
            "wave_run: false",
            "numeric_histogram_status: NOT_AVAILABLE_FROM_FROZEN_RUNTIME",
            "final: MIXED",
            "static_validation: STATIC_VALIDATION_FAIL",
            "approved_for_wass: false",
        ):
            self.assertIn(required, result)
        self.assertIn("不针对手机设备优化", report)
        self.assertIn("18.8618%", report)
        self.assertIn("`MIXED`", report)
        self.assertIn("wave 仍禁止", report)

    def test_disparity_range_audit_rejects_blind_range_expansion(self):
        root = Path(__file__).resolve().parents[1] / "experiments" / "real_video" / "HomeTank_004"
        report = (root / "wass_disparity_range_audit.md").read_text(encoding="utf-8")
        self.assertIn("OpenCV `StereoSGBM`", report)
        self.assertIn("`P1=2*13^2=338`", report)
        self.assertIn("`P2=64*13^2=10816`", report)
        self.assertIn("classification **A: the disparity-search upper bound**", report)
        self.assertIn("| 1280 | 000000 | 92,829", report)
        self.assertIn("| 2560 | 000002 | 81,078", report)
        self.assertIn("OTHER_MATCHING_INSTABILITY", report)
        self.assertIn("approved_for_wass=false", report)
        self.assertIn("Wave remains prohibited", report)

    def test_sgbm_parameter_audit_keeps_static_failure(self):
        root = Path(__file__).resolve().parents[1] / "experiments" / "real_video" / "HomeTank_004"
        report = (root / "wass_sgbm_matching_parameter_audit.md").read_text(encoding="utf-8")
        self.assertIn("uniqueness `1, 5, 10, 15`", report)
        self.assertIn("block size `7, 11, 15, 21`", report)
        self.assertIn("`uniqueness=15, block=15`", report)
        self.assertIn("22.975 mm", report)
        self.assertIn("2.801 deg", report)
        self.assertIn("no validated formal parameter change", report)
        self.assertIn("STATIC_VALIDATION_FAIL", report)
        self.assertIn("approved_for_wass=false", report)
        self.assertIn("Wave remains prohibited", report)


if __name__ == "__main__":
    unittest.main()
