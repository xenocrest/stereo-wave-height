"""HomeTank_002 calibration units, roles, conventions, and provenance guards."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from adapters.wass.input import REQUIRED_WASS_CONFIG_FILES, prepare_wass_workspace
from calibration import CalibrationCameraRoles, CheckerboardSpec, StereoExtrinsics, stereo_baseline_m
from input import OrientationTransform


class HomeTank002CalibrationTests(unittest.TestCase):
    def test_checkerboard_pattern_and_metric_object_points(self) -> None:
        spec = CheckerboardSpec(9, 6, 0.020)
        self.assertEqual(spec.pattern_size, (9, 6))
        self.assertEqual(spec.total_inner_corners, 54)
        self.assertEqual(spec.as_mapping()["square_size_mm"], 20.0)
        points = spec.object_points_m()
        self.assertEqual(points.shape, (54, 3))
        np.testing.assert_allclose(points[0], [0, 0, 0])
        np.testing.assert_allclose(points[8], [0.160, 0, 0])
        np.testing.assert_allclose(points[9], [0, 0.020, 0])

    def test_home_tank_002_roles_do_not_inherit_home_tank_001(self) -> None:
        roles = CalibrationCameraRoles("HomeTank_002", "cam0", "iQOO Neo5S", "cam1", "iQOO Z10 Turbo+", "HomeTank_002 manifest")
        self.assertEqual((roles.left_role, roles.left_device), ("cam0", "iQOO Neo5S"))
        self.assertEqual((roles.right_role, roles.right_device), ("cam1", "iQOO Z10 Turbo+"))

    def test_extrinsic_convention_and_baseline(self) -> None:
        extrinsics = StereoExtrinsics(np.eye(3), np.array([0.3, 0.4, 0.0]), "test calibration")
        self.assertAlmostEqual(extrinsics.baseline_m, 0.5)
        self.assertAlmostEqual(stereo_baseline_m([[0.3], [0.4], [0.0]]), 0.5)
        self.assertIn("X_right", extrinsics.as_mapping()["convention"])

    def test_orientation_is_experiment_metadata_not_device_history(self) -> None:
        home_tank_002_cam0 = OrientationTransform(180, "HomeTank_002 MP4 display matrix")
        home_tank_002_cam1 = OrientationTransform(0, "HomeTank_002 MP4 display matrix absence")
        self.assertEqual(home_tank_002_cam0.rotation_deg, 180)
        self.assertEqual(home_tank_002_cam1.rotation_deg, 0)

    def test_calibration_provenance_reaches_wass_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); dataset = root / "dataset"
            for directory in (dataset / "left", dataset / "right", dataset / "metadata"):
                directory.mkdir(parents=True, exist_ok=True)
            (dataset / "left" / "000000.png").write_bytes(b"left")
            (dataset / "right" / "000000.png").write_bytes(b"right")
            provenance = {"experiment_id": "HomeTank_002", "status": "CALIBRATION_PASS", "source": "checkerboard_9x6_0.020m"}
            payload = {
                "dataset_type": "real_stereo_video_wass_input_adapter",
                "orientation_status": "CANONICAL_ORIENTATION_APPLIED",
                "pairing_basis": "timestamp",
                "calibration_provenance": provenance,
                "frames": [{"frame_id": "000000", "timestamp_ns": 1_000_123_456, "left_image": "left/000000.png", "right_image": "right/000000.png"}],
            }
            (dataset / "metadata" / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
            config = root / "config"; config.mkdir()
            for name in REQUIRED_WASS_CONFIG_FILES:
                (config / name).write_text(name, encoding="utf-8")
            prepared = prepare_wass_workspace(dataset, root / "workspace", verified_config_dir=config)
            output = json.loads(prepared.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(output["calibration_provenance"], provenance)


if __name__ == "__main__":
    unittest.main()
