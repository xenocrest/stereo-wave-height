import csv
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from tools.preflight_check import _video
from pipeline.instantaneous_validation.compare_instant import compare_frame
from pipeline.instantaneous_validation.load_ground_truth import load_truth
from pipeline.instantaneous_validation.load_vision import export_csv, load_frame
from pipeline.instantaneous_validation.schemas import ReferencePlane, reference_from_config, read_yaml
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

    def test_preflight_missing_video(self):
        self.assertEqual(_video(str(self.root / "not-recorded.mp4"))["status"], "NOT_READY")

    def test_instantaneous_hover_contains_frame_time_and_reference(self):
        (self.root / "config_snapshot.yaml").write_text(
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


if __name__ == "__main__":
    unittest.main()
