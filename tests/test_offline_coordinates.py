from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from app import core, coordinates


SOURCE = Path("D:/stereo-wave-height-runs/pipeline/hometank004_multiframe_acceptance/run_20260928/science")


class CoordinateTests(unittest.TestCase):
    def setUp(self):
        if not SOURCE.is_dir():
            self.skipTest("Traceable official run not installed")
        self.reference = core.reference_from_run(SOURCE, 0)

    def test_identity_uses_actual_grid_transform_not_run_path(self):
        ids = coordinates.identity(SOURCE)
        self.assertEqual(ids, coordinates.identity(SOURCE))
        self.assertEqual(self.reference.coordinate_frame_id, ids["coordinate_frame_id"])
        self.assertNotEqual(coordinates.numeric_hash({"Rpl": np.eye(3)}),
                            coordinates.numeric_hash({"Rpl": -np.eye(3)}))

    def test_mismatch_rejected_before_height_calculation(self):
        for key in ("calibration_id", "extrinsics_id", "coordinate_frame_id"):
            with self.subTest(key=key), patch("app.core.load_frame") as height_loader:
                bad = replace(self.reference, **{key: "different"})
                with self.assertRaisesRegex(ValueError, "REFERENCE_FRAME_MISMATCH"):
                    core.load_result(SOURCE, 1, bad)
                height_loader.assert_not_called()

    def test_reference_json_contains_complete_binding(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "reference_plane.json"
            core.save_reference(self.reference, self.reference.calibration_id, path, SOURCE, 0)
            data = json.loads(path.read_text())
            for key in ("reference_plane_id", "calibration_id", "extrinsics_id", "coordinate_frame_id",
                        "n", "d", "source", "frame_id", "timestamp"):
                self.assertIn(key, data)
            restored, _ = core.load_reference(path)
            self.assertEqual(restored, self.reference)

    def test_common_region_not_invented_and_three_frames_still_load(self):
        for frame_id in (1, 2, 3):
            result = core.load_result(SOURCE, frame_id, self.reference)
            self.assertEqual(result["common_stereo_region"], "COMMON_REGION_NOT_AVAILABLE")
            self.assertEqual(result["reference_status"], "MATCHED")
            self.assertGreater(np.count_nonzero(np.isfinite(result["height"])), 0)

    def test_gui_mismatch_hides_old_height(self):
        from PySide6.QtWidgets import QApplication
        from app.main import MainWindow
        app = QApplication.instance() or QApplication([])
        window = MainWindow()
        try:
            window.result = {"timestamp_s": 1.}
            with patch("app.main.QMessageBox.critical"):
                window._error("REFERENCE_FRAME_MISMATCH: extrinsics_id differs")
            self.assertIsNone(window.result)
            self.assertIn("FRAME_MISMATCH", window.frame_summary.text())
        finally:
            window.close()

    def test_real_independent_runs_gui_hover_export_if_available(self):
        from PySide6.QtWidgets import QApplication
        from app.main import MainWindow
        from app import presentation
        from pipeline.common import sha256
        app = QApplication.instance() or QApplication([])
        directory = Path("D:/stereo-wave-height-runs/fixed-coordinate-acceptance-20261001-final")
        if not (directory / "gui_project.yaml").is_file():
            self.skipTest("Independent official acceptance runs not installed")
        window = MainWindow()
        try:
            window.config = core.read_project(directory / "gui_project.yaml")
            window._populate()
            frozen = window.reference
            for letter, target in zip("ABC", (21., 22., 23.)):
                root = directory / f"Run_{letter}" / "science"
                window.slider.setValue(int(target * 1000))
                with patch.object(window, "_error", side_effect=AssertionError):
                    window._open_run_path(str(root / "run_report.json"))
                self.assertEqual(window.reference, frozen)
                self.assertEqual(window.result["coordinate_frame_id"], frozen.coordinate_frame_id)
                self.assertIn("MATCHED", window.frame_summary.text())
                for mode in ("raw", "cloud", "overlay"):
                    window._display_mode(mode)
                window._hover(1, 1)
                self.assertIn("NO_DATA", window.hover_label.text())
                valid = np.argwhere(np.isfinite(window.result["height"]))[0]
                self.assertIsNotNone(core.hover(window.result, int(valid[1]), int(valid[0]))["height_mm"])
                with tempfile.TemporaryDirectory() as folder:
                    ply = root / "reconstruction/ply" / f"{window.result['frame_id']:06d}.ply"
                    metadata = presentation.export_current_frame(folder, window.result, window.raw_rgb,
                        window.overlay_rgb, ply, frozen, (0.4, 0.4, 0.5, 0.5))
                    self.assertEqual(metadata["coordinate_frame_id"], frozen.coordinate_frame_id)
                    self.assertEqual(metadata["extrinsics_id"], frozen.extrinsics_id)
                    self.assertEqual(sha256(ply), sha256(Path(folder) / "pointcloud.ply"))
        finally:
            window.close()

    def test_empty_new_input_interfaces_no_hidden_fallback(self):
        from PySide6.QtWidgets import QApplication
        from app.main import MainWindow
        app = QApplication.instance() or QApplication([])
        window = MainWindow()
        try:
            window.config = core.new_project("new_camera", "D:/new_camera_runs")
            window._populate()
            self.assertNotIn("HomeTank", json.dumps(window._gather()))
            self.assertFalse(window._gather()["wass"]["allow_extrinsic_fallback"])
            self.assertIsNone(window.reference)
            self.assertIsNone(window.science_run)
            pair = core.ROOT / "experiments/real_video/HomeTank_005/videos"
            window.wave_left.setText(str(pair / "wave/HomeTank_005_wave_cam0_LEFT.mp4"))
            window.wave_right.setText(str(pair / "wave/HomeTank_005_wave_cam1_RIGHT.mp4"))
            window.cal_left.setText(str(pair / "calibration/HomeTank_005_calibration_cam0_LEFT.mp4"))
            window.cal_right.setText(str(pair / "calibration/HomeTank_005_calibration_cam1_RIGHT.mp4"))
            window._load_videos()
            window.sync_run = Path("D:/new_camera_runs/synchronized")
            window.slider.setValue(1000)
            window._set_static_reference()
            self.assertEqual(window.reference_time_s, 1.)
            self.assertFalse(window.reference_confirmed)
            config = window._gather()
            self.assertNotIn("fallback_calibration", config["wass"])
            self.assertNotIn("frozen_reference", config["presentation"])
            with patch.object(window, "_start_work") as dispatch, patch.object(window, "_error", side_effect=AssertionError):
                window._calibrate()
                self.assertEqual(dispatch.call_args.args[0], "calibrate")
                window.sync_run = Path("D:/new_camera_runs/synchronized")
                window.slider.setValue(2000)
                window._reconstruct()
                self.assertEqual(dispatch.call_args.args[0], "reconstruct")
                self.assertNotIn("fallback_calibration", dispatch.call_args.args[1]["wass"])
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()
