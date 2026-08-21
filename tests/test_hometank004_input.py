from pathlib import Path
import ast
import re
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
            "coarse_geometry_reassessment.md",
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
        self.assertRegex(candidates, r"(?s)id: SPEC_COARSE.*?coarse_fixed_calibration_exportable: false")
        self.assertRegex(candidates, r"(?s)id: FAILED_CALIB_COARSE.*?coarse_fixed_calibration_exportable: true")
        match = re.search(r"T_right_from_left_m: (\[[^\n]+\])", candidates)
        self.assertIsNotNone(match)
        hybrid_t = ast.literal_eval(match.group(1))
        self.assertAlmostEqual(sum(value * value for value in hybrid_t) ** 0.5, 0.070)


if __name__ == "__main__":
    unittest.main()
