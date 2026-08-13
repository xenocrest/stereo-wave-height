"""Machine-precision validation of the ideal virtual stereo geometry."""

from pathlib import Path
import unittest

import numpy as np

from src.simulation.config import load_nominal_intrinsics
from src.simulation.stereo_rig import IdealStereoRig
from src.simulation.texture import planar_random_texture
from src.validation.virtual_stereo_geometry import (
    closure_metrics,
    theoretical_pinhole_projection,
    triangulate_parallel_downward_stereo,
)


ROOT = Path(__file__).resolve().parents[1]


class VirtualStereoGeometryValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.intrinsics = load_nominal_intrinsics(ROOT / "configs/equipment/candidate_system.yaml")
        cls.rig = IdealStereoRig.create(cls.intrinsics, baseline_m=0.20, working_distance_m=2.0)

    def _project_and_triangulate(self, points: np.ndarray) -> np.ndarray:
        left, right, _, _ = self.rig.project(points, coordinate_system="world_water_surface", unit="m")
        i = self.intrinsics
        return triangulate_parallel_downward_stereo(
            left, right, fx_px=i.fx_px, fy_px=i.fy_px, cx_px=i.cx_px, cy_px=i.cy_px,
            baseline_m=self.rig.baseline_m, working_distance_m=self.rig.working_distance_m,
        )

    def test_focal_mm_to_pixels(self) -> None:
        self.assertAlmostEqual(self.intrinsics.fx_px, 8.0 / 0.00345, places=12)
        self.assertEqual(self.intrinsics.fx_px, self.intrinsics.fy_px)

    def test_principal_point_is_zero_based_image_center(self) -> None:
        self.assertEqual(self.intrinsics.cx_px, (2448 - 1) / 2)
        self.assertEqual(self.intrinsics.cy_px, (2048 - 1) / 2)

    def test_left_and_right_projection_match_independent_equations(self) -> None:
        points = np.array([[0, 0, 0], [-.4, .2, 0], [.4, -.2, 0], [0, .3, .25], [0, -.3, -.25], [-.2, .1, .5], [.2, -.1, -.5], [-.5, 0, 0], [.5, 0, 0], [.1, .2, -.8]], float)
        for camera in (self.rig.left, self.rig.right):
            actual, _ = camera.project(points, coordinate_system="world_water_surface", unit="m")
            expected, _ = theoretical_pinhole_projection(points, intrinsic_matrix=self.intrinsics.matrix, rotation_world_to_camera=camera.rotation_world_to_camera, camera_center_world_m=camera.center_world_m)
            np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-12)

    def test_disparity_at_known_depth(self) -> None:
        point = np.array([[0.0, 0.0, 0.0]])
        left, right, depth, _ = self.rig.project(point, coordinate_system="world_water_surface", unit="m")
        self.assertAlmostEqual(float(left[0, 0] - right[0, 0]), self.intrinsics.fx_px * .2 / depth[0], places=12)

    def test_disparity_decreases_monotonically_with_depth(self) -> None:
        depth = np.array([1.5, 2.0, 2.5, 3.0])
        points = np.column_stack((np.zeros(4), np.zeros(4), 2.0 - depth))
        left, right, _, _ = self.rig.project(points, coordinate_system="world_water_surface", unit="m")
        disparity = left[:, 0] - right[:, 0]
        self.assertTrue(np.all(np.diff(disparity) < 0))

    def test_multiple_depth_triangulation_closure(self) -> None:
        x, y, depth = np.meshgrid(np.linspace(-.5, .5, 7), np.linspace(-.35, .35, 5), [1.5, 2, 2.5, 3], indexing="ij")
        points = np.stack((x, y, 2.0 - depth), axis=-1)
        self.assertLess(closure_metrics(points, self._project_and_triangulate(points)).euclidean_max_m, 1e-12)

    def test_plane_surface_closure(self) -> None:
        x, y = np.meshgrid(np.linspace(-.7, .7, 71), np.linspace(-.6, .6, 61))
        points = np.stack((x, y, np.zeros_like(x)), axis=-1)
        self.assertLess(closure_metrics(points, self._project_and_triangulate(points)).euclidean_max_m, 1e-12)

    def test_sinusoidal_surface_closure(self) -> None:
        x, y = np.meshgrid(np.linspace(-.7, .7, 71), np.linspace(-.6, .6, 61))
        z = .01 * np.sin(2 * np.pi * x / .8)
        points = np.stack((x, y, z), axis=-1)
        self.assertLess(closure_metrics(points, self._project_and_triangulate(points)).euclidean_max_m, 1e-12)

    def test_shared_texture_is_one_physical_array(self) -> None:
        texture = planar_random_texture([-0.1, 0.0, 0.1], [-0.1, 0.0, 0.1], seed=5)
        self.assertEqual(texture.intensity.shape, (3, 3))
        np.testing.assert_array_equal(texture.intensity, planar_random_texture(texture.x_m, texture.y_m, seed=5).intensity)

    def test_behind_camera_projection_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "front"):
            self.rig.left.project([[0, 0, 3]], coordinate_system="world_water_surface", unit="m")

    def test_zero_disparity_triangulation_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            triangulate_parallel_downward_stereo([[1, 1]], [[1, 1]], fx_px=1, fy_px=1, cx_px=0, cy_px=0, baseline_m=.2, working_distance_m=2)


if __name__ == "__main__":
    unittest.main()
