import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import sys
import subprocess

import numpy as np
import yaml

from tools.preflight_check import _video, check as preflight_check
from tools.vieira_tlcc_sync import extract_frame
from pipeline.instantaneous_validation.compare_instant import compare_frame
from pipeline.instantaneous_validation.load_ground_truth import load_truth
from pipeline.instantaneous_validation.load_vision import export_csv, load_frame
from pipeline.instantaneous_validation.load_vision import frame_times
from pipeline.instantaneous_validation.schemas import ReferencePlane, reference_from_config, read_yaml
from pipeline.instantaneous_validation.run_validation import run as run_validation
from pipeline.visualization.view_results import _height_products


class InstantaneousValidationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "sync").mkdir()
        (self.root / "pixel" / "pixel_height").mkdir(parents=True)
        (self.root / "sync" / "sync.json").write_text(json.dumps({"status": "PROVIDED", "frames": [
            {"index": 0, "time_s": 12.5}, {"index": 1, "time_s": 12.6}]}), encoding="utf-8")
        vv, uu = np.mgrid[:6, :6]
        xyz = np.stack([uu * 0.01, vv * 0.01, 0.03 + uu * 0.001], axis=-1)
        source = np.full((6, 6), 2, np.uint8)
        source[5, 5] = 0
        np.savez_compressed(self.root / "pixel" / "pixel_height" / "00000000.npz",
                            xyz=xyz, source=source, units="m")
        np.savez_compressed(self.root / "pixel" / "pixel_height" / "00000001.npz",
                            xyz=xyz, source=source, units="m")
        self.reference = ReferencePlane("physical_1", (0, 0, 1), -0.01,
                                        "provided_physical_plane", "official_grid_m")
        self.layout = {"A": {"id": "A", "x_mm": 20.0, "y_mm": 30.0}}
        self.sync = {"method": "provided_offset", "offset_ms": 2.0, "source": "measured event"}

    def truth(self, true_height: float = 17.8, time: float = 12.498, x: float = 20, y: float = 30):
        return [{"timestamp": time, "sensor_id": "A", "x": x, "y": y,
                 "H_true_mm": true_height, "quality_flag": "GOOD", "reference_plane_id": "physical_1"}]

    def compare(self, rows=None, spatial=2.0, temporal=5.0):
        return compare_frame(self.root, 0, self.reference, rows or self.truth(), self.layout,
                             self.sync, temporal, spatial)[0]

    def test_fixed_plane_height_and_timestamp(self):
        result = load_frame(self.root, 0, self.reference)
        self.assertAlmostEqual(result["height"][3, 2] * 1000, 22.0)
        self.assertEqual(result["timestamp_s"], 12.5)
        self.assertTrue(np.isnan(result["height"][5, 5]))
        self.assertEqual(result["reference_plane_id"], "physical_1")
        self.assertEqual(result["timestamp_basis"], "PROVIDED_SEQUENCE_NOMINAL_TIME")

    def test_actual_decoded_timestamp_metadata(self):
        (self.root / "sync" / "sync.json").write_text(json.dumps({"status": "COMPUTED", "frame_mapping": [
            {"output_index": 0, "left_requested_timestamp_s": 12.5,
             "left_actual_timestamp_s": 12.5089, "right_actual_timestamp_s": 12.507,
             "stereo_pair_residual_ms": -1.9}]}), encoding="utf-8")
        self.assertAlmostEqual(frame_times(self.root)[0], 12.5089)
        self.assertEqual(load_frame(self.root, 0, self.reference)["timestamp_basis"], "ACTUAL_DECODED_PTS")

    def test_ffmpeg_extraction_records_selected_frame_pts(self):
        output = self.root / "selected.png"
        output.write_bytes(b"png-test")
        completed = subprocess.CompletedProcess([], 0, "", "[Parsed_showinfo_0] n: 0 pts: 801 pts_time:0.0089 duration: 1500")
        with mock.patch("tools.vieira_tlcc_sync.run_checked", return_value=completed):
            self.assertAlmostEqual(extract_frame(self.root / "ffmpeg.exe", self.root / "video.mp4", 20.0, output), 20.0089)

    def test_provided_plane_normalization(self):
        plane = reference_from_config({"mode": "provided_physical_plane", "coordinate_system": "official_grid_m",
                                       "n_x": 0, "n_y": 0, "n_z": 2, "d": -0.02}, self.root)
        self.assertEqual(plane.normal, (0, 0, 1))
        self.assertAlmostEqual(plane.d, -0.01)

    def test_designated_static_frame_is_one_fixed_plane(self):
        plane = reference_from_config({"mode": "designated_static_water_frame", "coordinate_system": "official_grid_m",
                                       "reference_frame_id": 0}, self.root)
        self.assertEqual(plane.mode, "designated_static_water_frame")
        self.assertAlmostEqual(float(plane.height([0.02, 0.03, 0.032])), 0, places=8)
        self.assertEqual(load_frame(self.root, 1, plane)["reference_plane_id"], plane.plane_id)

    def test_time_gate_preserves_actual_time(self):
        result = self.compare(self.truth(time=12.48))
        self.assertEqual(result["status"], "TIME_NOT_ALIGNED")
        self.assertEqual(result["t_gt"], 12.48)
        self.assertAlmostEqual(result["delta_t_ms"], -18.0)
        self.assertIsNone(result["DeltaH_mm"])

    def test_space_gate(self):
        result = self.compare(spatial=0.001)
        self.assertEqual(result["status"], "PASS_LT_10MM")  # exact recorded XY
        self.layout["A"]["x_mm"] = 20.5
        rows = self.truth(x=20.5)
        result = self.compare(rows, spatial=0.1)
        self.assertEqual(result["status"], "SPACE_NOT_ALIGNED")
        self.assertAlmostEqual(result["spatial_distance_mm"], 0.5)

    def test_delta_and_strict_ten_mm_gate(self):
        passed = self.compare(self.truth(true_height=17.8))
        self.assertEqual(passed["status"], "PASS_LT_10MM")
        self.assertAlmostEqual(passed["DeltaH_mm"], 4.2)
        failed = self.compare(self.truth(true_height=34.0))
        self.assertEqual(failed["status"], "FAIL_GE_10MM")
        self.assertAlmostEqual(failed["DeltaH_mm"], -12.0)
        boundary = self.compare(self.truth(true_height=12.0))
        self.assertEqual(boundary["status"], "FAIL_GE_10MM")

    def test_provenance_and_no_data(self):
        self.assertEqual(self.compare()["provenance"], "OFFICIAL_GRID_ESTIMATE")
        path = self.root / "pixel" / "pixel_height" / "00000000.npz"
        with np.load(path, allow_pickle=False) as data:
            xyz = data["xyz"]
            source = data["source"].copy()
        source[3, 2] = 1
        np.savez_compressed(path, xyz=xyz, source=source, units="m")
        self.assertEqual(self.compare()["provenance"], "DIRECT_STEREO")
        np.savez_compressed(path, xyz=xyz, source=np.zeros_like(source), units="m")
        self.assertEqual(self.compare()["status"], "NO_DATA")

    def test_reference_datum_mismatch(self):
        rows = self.truth()
        rows[0]["reference_plane_id"] = "other"
        self.assertEqual(self.compare(rows)["status"], "REFERENCE_DATUM_MISMATCH")

    def test_csv_schema_and_full_pixel_scope(self):
        report = export_csv(self.root, [0], self.reference, self.root / "instantaneous_height.csv")
        self.assertEqual(report["rows"], 36)
        with (self.root / "instantaneous_height.csv").open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(rows[20]["provenance"], "OFFICIAL_GRID_ESTIMATE")
        self.assertEqual(rows[-1]["provenance"], "NO_DATA")
        self.assertEqual(rows[-1]["H_mm"], "")

    def test_truth_schema_and_template(self):
        truth_path = self.root / "truth.csv"
        truth_path.write_text("timestamp,sensor_id,x,y,H_true_mm,quality_flag,reference_plane_id\n"
                              "12.498,A,20,30,17.8,GOOD,physical_1\n", encoding="utf-8")
        self.assertEqual(load_truth(truth_path)[0]["H_true_mm"], 17.8)
        template = read_yaml(Path(__file__).resolve().parents[1] / "examples" / "gopro_experiment_template.yaml")
        self.assertEqual(template["sync"]["method"], "wass_lowcost_tlcc")
        self.assertIn("truth", template)
        self.assertIn("max_stereo_time_difference_ms", template["validation"])

    def test_physical_comparison_rejects_nominal_requested_timestamp(self):
        config = {"reference": {"mode": "provided_physical_plane", "coordinate_system": "official_grid_m",
                                "reference_plane_id": "physical_1", "n_x": 0, "n_y": 0, "n_z": 1, "d": -0.01},
                  "truth": {"data_file": "truth.csv"},
                  "validation": {"max_stereo_time_difference_ms": 5}}
        with self.assertRaisesRegex(ValueError, "VISION_TIMESTAMP_UNVERIFIED"):
            run_validation(config, self.root, self.root / "validation")

    def test_preflight_missing_video(self):
        self.assertEqual(_video(str(self.root / "not-recorded.mp4"))["status"], "NOT_READY")

    def test_preflight_ready_contract_with_complete_mocked_capture(self):
        tools_dir = self.root / "tools"
        tools_dir.mkdir()
        for name in ("ffmpeg.exe", "praat.exe"):
            (tools_dir / name).touch()
        for name in ("wass_prepare", "wass_match", "wass_autocalibrate", "wass_stereo"):
            (tools_dir / f"{name}.exe").touch()
        (tools_dir / "wass_source").mkdir()
        (tools_dir / "wass_lowcost").mkdir()
        truth = self.root / "ground_truth.csv"
        truth.write_text("timestamp,sensor_id,x,y,H_true_mm,quality_flag,reference_plane_id\n"
                         "12.5,A,20,30,22,GOOD,physical_1\n", encoding="utf-8")
        layout = self.root / "sensor_layout.yaml"
        layout.write_text("coordinate_system: official_grid_m\nsensors:\n  - id: A\n    x_mm: 20\n    y_mm: 30\n", encoding="utf-8")
        clock = self.root / "truth_sync.yaml"
        clock.write_text("truth_sync:\n  method: provided_offset\n  offset_ms: 2\n  source: measured event\n", encoding="utf-8")
        config = {"project": "test", "source_type": "stereo_video", "output_root": str(self.root),
                  "tools": {"python": sys.executable, "ffmpeg": str(tools_dir / "ffmpeg.exe"),
                            "praat": str(tools_dir / "praat.exe"), "wass_bin": str(tools_dir),
                            "wass_source": str(tools_dir / "wass_source"),
                            "wass_lowcost": str(tools_dir / "wass_lowcost")},
                  "calibration": {"left_video": "left_cal.mp4", "right_video": "right_cal.mp4",
                                  "checkerboard": {"rows": 6, "columns": 9, "square_size_m": 0.02}},
                  "sync": {"left_video": "left_wave.mp4", "right_video": "right_wave.mp4",
                           "method": "wass_lowcost_tlcc"}, "wass": {},
                  "surface": {"baseline_m": 0.16, "units": "m"},
                  "camera": {"nominal_baseline_mm": 160},
                  "reference": {"mode": "provided_physical_plane", "coordinate_system": "official_grid_m",
                                "n_x": 0, "n_y": 0, "n_z": 1, "d": 0},
                  "truth": {"data_file": str(truth), "sensor_layout": str(layout), "sync_file": str(clock)},
                  "validation": {"max_time_difference_ms": 5, "max_spatial_distance_mm": 2,
                                 "max_stereo_time_difference_ms": 5}}
        config_path = self.root / "experiment.yaml"
        config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
        original_is_file = Path.is_file
        def is_file(path):
            if path.name in {"wassgridsurface.exe", "wassncplot.exe"}:
                return True
            return original_is_file(path)
        video_record = {"status": "READY", "width": 1920, "height": 1080, "fps": 30.0, "frames": 300}
        with mock.patch("tools.preflight_check._video", return_value=video_record), \
             mock.patch("tools.preflight_check._audio", return_value={"status": "READY", "audio_track": True}), \
             mock.patch.object(Path, "is_file", is_file):
            self.assertEqual(preflight_check(config_path)["status"], "READY_FOR_PIPELINE")

    def test_instantaneous_hover_contains_frame_time_and_reference(self):
        (self.root / "config_snapshot.yaml").write_text(
            "pass_status: HOMETANK_PIPELINE_PASS_WITH_EXTRINSIC_FALLBACK\n"
            "reference:\n  mode: provided_physical_plane\n  coordinate_system: official_grid_m\n"
            "  reference_plane_id: physical_1\n  n_x: 0\n  n_y: 0\n  n_z: 1\n  d: -0.01\n",
            encoding="utf-8",
        )
        png, html = _height_products(self.root)
        self.assertTrue(Path(png).is_file())
        rendered = Path(html).read_text(encoding="utf-8")
        self.assertIn("frame=0", rendered)
        self.assertIn("12.500000", rendered)
        self.assertIn("physical_1", rendered)
        self.assertIn("EXTRINSIC_FALLBACK", rendered)


if __name__ == "__main__":
    unittest.main()
