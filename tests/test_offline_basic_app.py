import json
from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np

from app import core, presentation
from pipeline.instantaneous_validation.schemas import ReferencePlane


class OfflineAppTests(unittest.TestCase):
    def test_measurement_region_display_only(self):
        mask = presentation.rectangle_mask((10, 20), (0.25, 0.2, 0.75, 0.8))
        self.assertEqual(int(mask.sum()), 60)
        self.assertTrue(presentation.point_in_rectangle(5, 2, (10, 20), (0.25, 0.2, 0.75, 0.8)))
        self.assertFalse(presentation.point_in_rectangle(0, 0, (10, 20), (0.25, 0.2, 0.75, 0.8)))

    def test_fallback_requires_explicit_allow_and_path(self):
        from PySide6.QtWidgets import QApplication
        from app.main import MainWindow
        app = QApplication.instance() or QApplication([])
        window = MainWindow()
        try:
            window.config = core.new_project("new", "D:/runs")
            window.config["wass"]["fallback_calibration"] = {"path": "D:/known-calibration"}
            window._populate()
            with self.assertRaisesRegex(ValueError, "allow_extrinsic_fallback"):
                window._gather()
            window.config["wass"]["allow_extrinsic_fallback"] = True
            self.assertEqual(window._gather()["wass"]["fallback_calibration"]["path"], "D:/known-calibration")
        finally:
            window.close()

    def test_export_has_only_existing_values_and_provenance(self):
        from plyfile import PlyData, PlyElement
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "run"
            (root / "sync").mkdir(parents=True)
            (root / "wass").mkdir()
            undistorted = root / "wass/workspaces/000000_wd/undistorted"
            undistorted.mkdir(parents=True)
            presentation.save_rgb(undistorted / "00000000.png", np.zeros((1, 2, 3), np.uint8))
            ply = root / "pointcloud.ply"
            verts = np.array([(1., 2., 3.)], dtype=[("x", "f4"), ("y", "f4"), ("z", "f4")])
            PlyData([PlyElement.describe(verts, "vertex")], text=True).write(ply)
            (root / "sync" / "sync.json").write_text(json.dumps({"frame_mapping": [{
                "left_actual_timestamp_s": 1., "right_actual_timestamp_s": 0.99,
                "stereo_pair_residual_ms": -10.}], "audio_lag_right_minus_left_s": -0.01}))
            (root / "wass" / "run_summary.json").write_text(json.dumps({
                "active_calibration": {"fallback": False}}))
            result = {"run_dir": str(root), "frame_id": 0, "timestamp_s": 1.,
                      "calibration_identity": "c", "units": "m",
                      "xyz": np.array([[[1., 2., 3.], [4., 5., 6.]]]),
                      "height": np.array([[0.001, 0.002]]),
                      "source": np.array([[2, 0]], np.uint8)}
            plane = ReferencePlane("r", (0., 0., 1.), 0., "designated_static_water_frame", "official_wass_grid_m")
            out = Path(folder) / "out"
            meta = presentation.export_current_frame(out, result, np.zeros((1, 2, 3), np.uint8),
                                                     np.zeros((1, 2, 3), np.uint8), ply, plane, None)
            self.assertEqual(meta["mapped_pixel_count"], 1)
            self.assertEqual(meta["exported_pixel_count"], 1)
            self.assertEqual(len((out / "instantaneous_height.csv").read_text().splitlines()), 2)
            self.assertEqual(meta["measurement_region_source"], "NONE")

    def test_project_creation_and_arbitrary_paths(self):
        project = core.new_project("new_gopro", "D:/runs")
        self.assertEqual(project["project"], "new_gopro")
        self.assertEqual(project["calibration"]["left_video"], "")
        project["sync"]["left_video"] = "E:/任意相机/left.mp4"
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "project.yaml"
            core.save_project(project, path)
            self.assertEqual(core.read_project(path)["sync"]["left_video"], "E:/任意相机/left.mp4")
        self.assertFalse(project["wass"]["allow_extrinsic_fallback"])
        self.assertNotIn("HomeTank", json.dumps(project))

    def test_input_change_clears_reference_and_old_results(self):
        from PySide6.QtWidgets import QApplication
        from app.main import MainWindow
        app = QApplication.instance() or QApplication([])
        window = MainWindow()
        try:
            window.config = core.new_project("new", "D:/runs")
            window._populate()
            window.result = {"timestamp_s": 1.0}
            window.reference_confirmed = True
            window.wave_left.setText("E:/new/left.mp4")
            window._inputs_changed()
            self.assertIsNone(window.result)
            self.assertFalse(window.reference_confirmed)
            self.assertIsNone(window.sync_run)
            self.assertIsNone(window.image_canvas.image)
        finally:
            window.close()

    def test_frozen_reference_persists_across_project_reload_if_available(self):
        root = Path("D:/stereo-wave-height-runs/pipeline/hometank004_multiframe_acceptance/run_20260928/science")
        if not root.is_dir():
            self.skipTest("Multiframe run not installed")
        from PySide6.QtWidgets import QApplication
        from app.main import MainWindow
        app = QApplication.instance() or QApplication([])
        window = MainWindow()
        with tempfile.TemporaryDirectory() as folder:
            try:
                window.config = core.read_project(core.ROOT / "examples/hometank004.yaml")
                window._populate()
                window.project_path = Path(folder) / "project.yaml"
                window.reference = core.reference_from_run(root, 0)
                window.reference_identity = core.calibration_identity(root)
                window.reference_run = root
                window.reference_time_s = 20.0
                window._confirm_reference()
                frozen = window.reference
                window.config = core.read_project(window.project_path)
                window._populate()
                self.assertTrue(window.reference_confirmed)
                self.assertEqual(window.reference, frozen)
                self.assertEqual(window.reference_run, root)
                window.config["sync"]["left_video"] = "different.mp4"
                with self.assertRaisesRegex(ValueError, "different project inputs"):
                    window._restore_reference(window.config["presentation"]["frozen_reference"])
            finally:
                window.close()

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

    def test_seek_hides_previous_frame_height(self):
        from PySide6.QtWidgets import QApplication
        from app.main import MainWindow
        app = QApplication.instance() or QApplication([])
        window = MainWindow()
        try:
            window.result = {"timestamp_s": 1.0}
            window.slider.setRange(0, 3000)
            window.slider.setValue(2000)
            self.assertIsNone(window.result)
            self.assertIn("STALE", window.frame_summary.text())
            self.assertIn("Reconstruction: STALE", window.status.text())
        finally:
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

    def test_real_other_video_properties_input_only_if_available(self):
        from PySide6.QtWidgets import QApplication
        from app.main import MainWindow
        app = QApplication.instance() or QApplication([])
        root = core.ROOT / "experiments" / "real_video"
        pairs = [
            (root / "HomeTank_005/videos/wave/HomeTank_005_wave_cam0_LEFT.mp4",
             root / "HomeTank_005/videos/wave/HomeTank_005_wave_cam1_RIGHT.mp4"),
            (root / "HomeTank_006/videos/wave/HomeTank_006_wave_cam0_LEFT.mp4",
             root / "HomeTank_006/videos/wave/HomeTank_006_wave_cam1_RIGHT.mp4"),
        ]
        if any(not left.is_file() or not right.is_file() for left, right in pairs):
            self.skipTest("Other HomeTank input videos not installed")
        window = MainWindow()
        try:
            for left, right in pairs:
                window.wave_left.setText(str(left))
                window.wave_right.setText(str(right))
                window._load_videos()
                info = core.video_metadata(left)
                self.assertEqual(window.frame_rate, info["fps"])
                self.assertEqual(window.preview_left.shape[1], info["width"])
                window.slider.setValue(1000)
                self.assertEqual(window.slider.value(), 1000)
                self.assertIsNotNone(window.preview_right)
                window._toggle_play()
                self.assertTrue(window.playing)
                window._toggle_play()
                self.assertFalse(window.playing)
        finally:
            window.timer.stop()
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
            window._confirm_reference()
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
            self.assertIsNone(window.image_canvas.border)
            window._display_mode("measurement")
            self.assertIsNotNone(window.image_canvas.border)
            window._reconstruct()  # Same frame must reuse the completed run, without WASS.
            self.assertEqual(window.science_run, root)
            self.assertIsNone(window.worker)
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()
