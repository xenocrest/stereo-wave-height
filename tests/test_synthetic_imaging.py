"""Tests for ideal synthetic imaging; WASS itself is deliberately not invoked."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

from src.simulation.config import load_nominal_intrinsics
from src.simulation.imaging import render_surface
from src.simulation.stereo_dataset import generate_stereo_dataset
from src.simulation.stereo_rig import IdealStereoRig
from src.simulation.surfaces import constant_height, sinusoidal_wave, static_water
from src.simulation.texture import planar_random_texture


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG = PROJECT_ROOT / "configs" / "equipment" / "candidate_system.yaml"


class SyntheticImagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.intrinsics = load_nominal_intrinsics(CONFIG)
        cls.rig = IdealStereoRig.create(
            cls.intrinsics, baseline_m=0.20, working_distance_m=2.0
        )
        cls.x_m = np.linspace(-0.30, 0.30, 61)
        cls.y_m = np.linspace(-0.25, 0.25, 51)
        cls.timestamps = np.array([1_000_000_000], dtype=np.int64)

    def test_projected_points_are_inside_image(self) -> None:
        surface = static_water(self.x_m, self.y_m, self.timestamps)
        left, right, _, _ = self.rig.project(
            surface.points_at(0), coordinate_system=surface.coordinate_system, unit=surface.unit
        )
        for pixels in (left, right):
            self.assertTrue(np.all((pixels[..., 0] >= 0) & (pixels[..., 0] < self.intrinsics.equipment.width_px)))
            self.assertTrue(np.all((pixels[..., 1] >= 0) & (pixels[..., 1] < self.intrinsics.equipment.height_px)))

    def test_disparity_depth_relation(self) -> None:
        point = np.array([[0.0, 0.0, 0.0]])
        left, right, depth_left, _ = self.rig.project(
            point, coordinate_system="world_water_surface", unit="m"
        )
        disparity = left[0, 0] - right[0, 0]
        expected = self.intrinsics.fx_px * self.rig.baseline_m / depth_left[0]
        self.assertAlmostEqual(disparity, expected, places=12)

    def test_static_water_truth_is_zero(self) -> None:
        surface = static_water(self.x_m, self.y_m, self.timestamps)
        np.testing.assert_array_equal(surface.h_true_m, 0.0)

    def test_constant_height_truth_is_preserved(self) -> None:
        surface = constant_height(
            self.x_m, self.y_m, self.timestamps, delta_height_m=-0.012
        )
        np.testing.assert_allclose(surface.h_true_m, -0.012)
        np.testing.assert_allclose(surface.z_true_m - surface.z0_m, surface.h_true_m)

    def test_left_and_right_image_dimensions(self) -> None:
        surface = static_water(self.x_m, self.y_m, self.timestamps)
        texture = planar_random_texture(self.x_m, self.y_m, seed=7)
        left = render_surface(self.rig.left, surface.points_at(0), texture)
        right = render_surface(self.rig.right, surface.points_at(0), texture)
        expected = (self.intrinsics.equipment.height_px, self.intrinsics.equipment.width_px)
        self.assertEqual(left.image.shape, expected)
        self.assertEqual(right.image.shape, expected)
        self.assertEqual(left.image.dtype, np.uint8)
        self.assertGreater(left.valid_mask.sum(), 0)

    def test_manifest_and_dataset_are_complete(self) -> None:
        surface = sinusoidal_wave(
            self.x_m,
            self.y_m,
            self.timestamps,
            amplitude_m=0.01,
            wave_number_rad_per_m=4.0,
            angular_frequency_rad_per_s=2.0,
        )
        with tempfile.TemporaryDirectory() as temporary:
            generated = generate_stereo_dataset(
                Path(temporary) / "simulation_dataset",
                rig=self.rig,
                surface=surface,
                texture_seed=19,
            )
            manifest = json.loads(generated.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(generated.frame_count, 1)
            self.assertEqual(manifest["frames"][0]["frame_id"], "000000")
            self.assertIn("timestamp_ns", manifest["frames"][0])
            self.assertIn("camera", manifest)
            self.assertIn("simulation_parameters", manifest)
            self.assertIn("ground_truth_reference", manifest)
            self.assertTrue(generated.calibration_path.is_file())
            self.assertTrue(generated.ground_truth_path.is_file())
            for side in ("left", "right"):
                image_path = generated.root / manifest["frames"][0][f"{side}_image"]
                with Image.open(image_path) as image:
                    self.assertEqual(image.mode, "L")
                    self.assertEqual(image.size, (2448, 2048))
            with np.load(generated.ground_truth_path) as truth:
                np.testing.assert_allclose(truth["h_true_m"], surface.h_true_m)

    def test_random_texture_is_reproducible(self) -> None:
        first = planar_random_texture(self.x_m, self.y_m, seed=123)
        second = planar_random_texture(self.x_m, self.y_m, seed=123)
        different = planar_random_texture(self.x_m, self.y_m, seed=124)
        np.testing.assert_array_equal(first.intensity, second.intensity)
        self.assertFalse(np.array_equal(first.intensity, different.intensity))


if __name__ == "__main__":
    unittest.main()


