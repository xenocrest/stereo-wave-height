"""Geometry-only tests for the candidate-based virtual stereo system."""

from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np

from simulation import (
    IdealStereoRig,
    build_synthetic_manifest,
    constant_height,
    load_nominal_intrinsics,
    sinusoidal_wave,
    static_water,
)


EQUIPMENT_CONFIG = Path("configs/equipment/candidate_system.yaml")


class VirtualStereoTests(unittest.TestCase):
    """Validate observation geometry without matching or triangulation."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.intrinsics = load_nominal_intrinsics(EQUIPMENT_CONFIG)
        # These are explicit unit-test variables, not selected deployment values.
        cls.rig = IdealStereoRig.create(
            cls.intrinsics,
            baseline_m=0.20,
            working_distance_m=2.00,
        )

    def test_candidate_config_to_nominal_intrinsics(self) -> None:
        self.assertEqual(self.intrinsics.equipment.model, "MER2-503-36U3C")
        self.assertEqual((self.intrinsics.equipment.width_px, self.intrinsics.equipment.height_px), (2448, 2048))
        self.assertAlmostEqual(self.intrinsics.fx_px, 8.0 / 0.00345)
        self.assertEqual(self.intrinsics.status, "SIMULATION_NOMINAL")
        self.assertEqual(self.intrinsics.principal_point_status, "simulation_assumption")
        np.testing.assert_array_equal(self.intrinsics.distortion, np.zeros(5))

    def test_projection_backprojection_consistency(self) -> None:
        point = np.array([[0.12, -0.08, 0.03]])
        pixels, depth = self.rig.left.project(
            point,
            coordinate_system="world_water_surface",
            unit="m",
        )
        reconstructed = self.rig.left.backproject_with_depth(
            pixels,
            depth,
            coordinate_system="world_water_surface",
            unit="m",
        )
        np.testing.assert_allclose(reconstructed, point, atol=1e-12, rtol=0.0)

    def test_disparity_depth_consistency(self) -> None:
        point = np.array([[0.0, 0.0, 0.0]])
        left, right, left_depth, right_depth = self.rig.project(
            point,
            coordinate_system="world_water_surface",
            unit="m",
        )
        disparity = left[0, 0] - right[0, 0]
        expected = self.intrinsics.fx_px * self.rig.baseline_m / self.rig.working_distance_m
        self.assertAlmostEqual(disparity, expected)
        self.assertAlmostEqual(self.intrinsics.fx_px * self.rig.baseline_m / disparity, left_depth[0])
        self.assertAlmostEqual(left_depth[0], right_depth[0])

    def test_coordinate_directions(self) -> None:
        origin = np.array([[0.0, 0.0, 0.0]])
        plus_x = np.array([[0.1, 0.0, 0.0]])
        plus_y = np.array([[0.0, 0.1, 0.0]])
        plus_z = np.array([[0.0, 0.0, 0.1]])

        uv0, _, _, _ = self.rig.project(origin, coordinate_system="world_water_surface", unit="m")
        uvx, _, _, _ = self.rig.project(plus_x, coordinate_system="world_water_surface", unit="m")
        uvy, _, _, _ = self.rig.project(plus_y, coordinate_system="world_water_surface", unit="m")
        left_z, right_z, depth_z, _ = self.rig.project(
            plus_z, coordinate_system="world_water_surface", unit="m"
        )

        self.assertGreater(uvx[0, 0], uv0[0, 0])  # +Xw maps toward +u.
        self.assertLess(uvy[0, 1], uv0[0, 1])  # +Yw maps toward -v by declared rotation.
        self.assertLess(depth_z[0], self.rig.working_distance_m)  # +Zw is closer to downward camera.
        disparity_z = left_z[0, 0] - right_z[0, 0]
        disparity_zero = uv0[0, 0] - self.rig.project(
            origin, coordinate_system="world_water_surface", unit="m"
        )[1][0, 0]
        self.assertGreater(disparity_z, disparity_zero)

    def test_unit_consistency_rejects_millimetres(self) -> None:
        with self.assertRaisesRegex(ValueError, "unit mismatch"):
            self.rig.project(
                [[0.0, 0.0, 0.0]],
                coordinate_system="world_water_surface",
                unit="mm",
            )

    def test_deployment_variables_are_mandatory_positive(self) -> None:
        with self.assertRaisesRegex(ValueError, "baseline_m"):
            IdealStereoRig.create(self.intrinsics, baseline_m=0.0, working_distance_m=2.0)
        with self.assertRaisesRegex(ValueError, "working_distance_m"):
            IdealStereoRig.create(self.intrinsics, baseline_m=0.2, working_distance_m=-1.0)

    def test_surface_truth_models(self) -> None:
        x = np.array([0.0, 0.5])
        y = np.array([-0.1, 0.1])
        timestamps = np.array([0, 500_000_000], dtype=np.int64)

        still = static_water(x, y, timestamps, z0_m=0.02)
        np.testing.assert_allclose(still.h_true_m, 0.0)
        np.testing.assert_allclose(still.z_true_m, 0.02)

        raised = constant_height(x, y, timestamps, delta_height_m=0.03, z0_m=0.02)
        np.testing.assert_allclose(raised.h_true_m, 0.03)
        np.testing.assert_allclose(raised.z_true_m, 0.05)

        wave = sinusoidal_wave(
            x,
            y,
            timestamps,
            amplitude_m=0.04,
            wave_number_rad_per_m=np.pi,
            angular_frequency_rad_per_s=np.pi,
        )
        self.assertAlmostEqual(wave.h_true_m[0, 0, 0], 0.0)
        self.assertAlmostEqual(wave.h_true_m[0, 0, 1], 0.04)
        self.assertEqual(wave.points_at(0).shape, (2, 2, 3))

    def test_wass_input_manifest_is_metadata_only(self) -> None:
        manifest = build_synthetic_manifest(self.rig, [0, 1_000_000])
        self.assertFalse(manifest.materialized)
        self.assertEqual(manifest.source_type, "simulation")
        self.assertEqual(manifest.frames[0].frame_id, "000000")
        self.assertEqual(str(manifest.frames[0].left_image), "left/000000.png")
        self.assertEqual(manifest.calibration.status, "SIMULATION_NOMINAL")
        self.assertEqual(manifest.cameras[0].equipment_status, "candidate")
        np.testing.assert_allclose(
            manifest.calibration.relative_translation_right_from_left_m,
            [-self.rig.baseline_m, 0.0, 0.0],
        )


if __name__ == "__main__":
    unittest.main()
