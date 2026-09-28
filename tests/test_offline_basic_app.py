import json
from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np

from app import core
from pipeline.instantaneous_validation.schemas import ReferencePlane


class OfflineAppTests(unittest.TestCase):
    def test_project_creation_and_arbitrary_paths(self):
        project = core.new_project("new_gopro", "D:/runs")
        self.assertEqual(project["project"], "new_gopro")
        self.assertEqual(project["calibration"]["left_video"], "")
        project["sync"]["left_video"] = "E:/任意相机/left.mp4"
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "project.yaml"
            core.save_project(project, path)
            self.assertEqual(core.read_project(path)["sync"]["left_video"], "E:/任意相机/left.mp4")

    def test_video_metadata_and_seek(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "test.avi"
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (32, 24))
            for index in range(5):
                writer.write(np.full((24, 32, 3), index * 20, np.uint8))
            writer.release()
            info = core.video_metadata(path)
            self.assertEqual(info["width"], 32)
            self.assertEqual(info["frame_count"], 5)
            self.assertEqual(core.read_preview(str(path), 0.2).shape, (24, 32, 3))

    def test_gui_play_pause_and_frame_seek(self):
        from PySide6.QtWidgets import QApplication
        from app.main import MainWindow
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "test.avi"
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (32, 24))
            for index in range(10):
                writer.write(np.full((24, 32, 3), index * 20, np.uint8))
            writer.release()
            window = MainWindow()
            try:
                window.wave_left.setText(str(path))
                window.wave_right.setText(str(path))
                window._load_videos()
                window.slider.setValue(200)
                self.assertEqual(window.slider.value(), 200)
                window._toggle_play()
                self.assertTrue(window.playing)
                window._tick()
                self.assertGreater(window.slider.value(), 200)
                window._toggle_play()
                self.assertFalse(window.playing)
                previous = window.slider.value()
                window._step(1)
                self.assertGreater(window.slider.value(), previous)
            finally:
                window.timer.stop()
                window.close()

    def test_switch_project_clears_previous_scientific_state(self):
        from PySide6.QtWidgets import QApplication
        from app.main import MainWindow
        app = QApplication.instance() or QApplication([])
        window = MainWindow()
        try:
            window.config = core.new_project("next_project", "D:/runs")
            window.science_run = Path("D:/old-run")
            window.sync_run = Path("D:/old-run")
            window.reference_run = Path("D:/old-run")
            window.reference_time_s = 12.0
            window.cache["old"] = Path("D:/old-run")
            window._populate()
            self.assertIsNone(window.science_run)
            self.assertIsNone(window.sync_run)
            self.assertIsNone(window.reference_run)
            self.assertIsNone(window.reference_time_s)
            self.assertFalse(window.cache)
            self.assertIn("Reconstruction: NOT_RUN", window.status.text())
        finally:
            window.close()

    def test_sync_frame_selection_and_offset(self):
        rows = {"frame_mapping": [{"left_requested_timestamp_s": n, "output_index": n} for n in range(3)]}
        self.assertEqual(core.sync_frame_at(rows, 1.1)["output_index"], 1)
        self.assertEqual(core.aligned_preview_times(20, -0.075), (20, 19.925))

    def test_reference_freeze_and_import(self):
        plane = ReferencePlane("fixed", (0.0, 0.0, 1.0), 0.01, "provided_physical_plane", "official_wass_grid_m")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "plane.json"
            core.save_reference(plane, "geometry-1", path)
            loaded, identity = core.load_reference(path)
            self.assertEqual(loaded, plane)
            self.assertEqual(identity, "geometry-1")
            self.assertEqual(json.loads(path.read_text())["reference_plane_id"], "fixed")

    def test_hover_provenance_and_no_data(self):
        result = {"xyz": np.array([[[1., 2., 3.], [2., 3., 4.], [np.nan] * 3]]),
                  "height": np.array([[0.001, 0.002, np.nan]]),
                  "source": np.array([[1, 2, 0]], np.uint8), "units": "m"}
        self.assertEqual(core.hover(result, 0, 0)["provenance"], "DIRECT_STEREO")
        self.assertEqual(core.hover(result, 1, 0)["height_mm"], 2.0)
        self.assertEqual(core.hover(result, 1, 0)["provenance"], "OFFICIAL_GRID_ESTIMATE")
        self.assertEqual(core.hover(result, 2, 0)["provenance"], "NO_DATA")
        self.assertIsNone(core.hover(result, 12, 12)["height_mm"])

    def test_cache_depends_on_reference_and_time(self):
        config = core.new_project("x", "D:/runs")
        config["_app_reference_time_s"] = 10
        first = core.cache_key(config, 11)
        self.assertEqual(first, core.cache_key(config, 11))
        config["_app_reference_time_s"] = 12
        self.assertNotEqual(first, core.cache_key(config, 11))

    def test_scientific_failure_log(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(RuntimeError, "Return code: 5"):
                core.run_external(["cmd", "/c", "exit", "5"], Path(folder) / "tool.log")
            self.assertTrue((Path(folder) / "tool.log").exists())

    def test_clean_external_environment(self):
        import os
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = "C:/bad"
        try:
            self.assertNotIn("QT_QPA_PLATFORM_PLUGIN_PATH", core.clean_environment())
        finally:
            del os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"]

    def test_vieira_result_adapter_if_available(self):
        root = Path("D:/stereo-wave-height-runs/pipeline/vieira_official/run_20260928_113344")
        if not root.is_dir():
            self.skipTest("Official sample run not installed")
        reference = core.reference_from_run(root)
        self.assertEqual(reference.coordinate_system, "official_wass_grid_B")
        result = core.load_result(root, 0, reference)
        self.assertEqual(result["units"], "B")
        self.assertTrue(np.count_nonzero(result["source"] == 2) > 0)
        valid = np.argwhere(result["source"] == 2)[0]
        item = core.hover(result, int(valid[1]), int(valid[0]))
        self.assertEqual(item["provenance"], "OFFICIAL_GRID_ESTIMATE")
        self.assertIsNone(item["height_mm"])

    def test_hometank_result_adapter_if_available(self):
        root = Path("D:/stereo-wave-height-runs/pipeline/hometank004/run_20260928_113734")
        if not root.is_dir():
            self.skipTest("HomeTank run not installed")
        reference = core.reference_from_run(root, 0)
        result = core.load_result(root, 1, reference, core.calibration_identity(root))
        self.assertEqual(result["units"], "m")
        self.assertEqual(result["frame_id"], 1)
        with self.assertRaisesRegex(ValueError, "different active K/D/R/T"):
            core.load_result(root, 1, reference, "wrong")

    def test_real_gui_views_with_existing_hometank_run_if_available(self):
        root = Path("D:/stereo-wave-height-runs/pipeline/hometank004/run_20260928_113734")
        if not root.is_dir():
            self.skipTest("HomeTank run not installed")
        from PySide6.QtWidgets import QApplication
        from app.main import MainWindow
        app = QApplication.instance() or QApplication([])
        window = MainWindow()
        try:
            window.config = core.read_project(core.ROOT / "examples" / "hometank004.yaml")
            window._populate()
            window.slider.setValue(20000)
            window._set_static_reference()
            window.slider.setValue(21000)
            config = window._gather()
            config.update(_app_target_s=21.0, _app_target_frame=2, _app_reference_frame=0)
            window.science_run = root
            window._viewing_existing_run = True
            window._pending_key = "ui-test"
            window._receive_reconstruction(config)
            self.assertIsNotNone(window.raw_rgb)
            self.assertIsNotNone(window.overlay_rgb)
            self.assertIn("WASS XYZ=", window.frame_summary.text())
            window._display_mode("cloud")
            self.assertFalse(window.point_cloud.isHidden())
            window._display_mode("overlay")
            self.assertIsNotNone(window.image_canvas.image)
            window._display_mode("raw")
            window._hover(100, 100)
            self.assertIn("NO_DATA", window.hover_label.text())
            window.show_common.setChecked(True)
            window._display_mode("raw")
            self.assertIsNotNone(window.image_canvas.border)
            window._reconstruct()  # Same frame must reuse the completed run, without WASS.
            self.assertEqual(window.science_run, root)
            self.assertIsNone(window.worker)
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()
