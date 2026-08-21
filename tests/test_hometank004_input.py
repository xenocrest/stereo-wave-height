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
            "calibration_report.md",
        }
        self.assertEqual({path.name for path in root.iterdir()}, expected)
        self.assertIn("CALIBRATION_QUALITY_FAIL", (root / "manifest.yaml").read_text(encoding="utf-8"))
        self.assertIn("strict_calibration_failed: true", (root / "calibration_result.yaml").read_text(encoding="utf-8"))
        self.assertIn("approved_for_wass: false", (root / "calibration_result.yaml").read_text(encoding="utf-8"))
        for condition in ("calibration", "static", "wave"):
            directory = root / "videos" / condition
            self.assertTrue(directory.is_dir())
            self.assertTrue((directory / ".gitkeep").is_file())


if __name__ == "__main__":
    unittest.main()
