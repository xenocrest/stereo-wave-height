"""Tests for projection-based pixel/XYZ mapping and plane-normal height."""

import tempfile
import unittest
from pathlib import Path

import numpy as np

from src.reconstruction.height import height_from_plane
from src.reconstruction.pixel_xyz import (
    load_projection_matrix,
    project_wass_points,
    query_xyz,
    save_pixel_xyz,
)


class PixelXyzHeightTests(unittest.TestCase):
    def test_projection_preserves_metric_pairing(self) -> None:
        camera = np.array([[1.0, 2.0, 2.0], [2.0, 4.0, 2.0]])
        metric = camera * 0.2
        projection = np.array([[10.0, 0.0, 0.0, 0.0], [0.0, 10.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0]])
        result = project_wass_points(camera, metric, projection, pixel_coordinate_system="rectified_cam0")
        np.testing.assert_allclose(result.u_px, [5.0, 10.0])
        np.testing.assert_allclose(result.v_px, [10.0, 20.0])
        np.testing.assert_allclose(result.xyz_m, metric)

    def test_query_has_explicit_radius_and_no_guess(self) -> None:
        result = project_wass_points(
            np.array([[1.0, 1.0, 1.0]]), np.array([[0.1, 0.1, 0.1]]), np.eye(3, 4),
            pixel_coordinate_system="rectified_cam0",
        )
        np.testing.assert_allclose(query_xyz(result, 1.1, 1.0, maximum_distance_px=0.2), [0.1, 0.1, 0.1])
        with self.assertRaises(LookupError):
            query_xyz(result, 2.0, 2.0, maximum_distance_px=0.2)

    def test_saved_schema_and_projection_loader(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            matrix_path = root / "P.txt"
            matrix_path.write_text("1 0 0 0\n0 1 0 0\n0 0 1 0\n", encoding="utf-8")
            projection = load_projection_matrix(matrix_path)
            result = project_wass_points(
                np.array([[1.0, 1.0, 1.0]]), np.array([[0.2, 0.2, 0.2]]), projection,
                pixel_coordinate_system="rectified_cam0",
            )
            output = save_pixel_xyz(root / "map.npz", result)
            with np.load(output, allow_pickle=False) as saved:
                self.assertEqual(str(saved["pixel_coordinate_system"]), "rectified_cam0")
                np.testing.assert_allclose(saved["xyz_m"], [[0.2, 0.2, 0.2]])

    def test_height_is_signed_orthogonal_distance_not_camera_z(self) -> None:
        points = np.array([[2.0, 0.0, 100.0], [-1.0, 0.0, -50.0]])
        height = height_from_plane(points, np.array([2.0, 0.0, 0.0]), -2.0)
        np.testing.assert_allclose(height, [1.0, -2.0])

    def test_invalid_projective_or_plane_inputs_fail(self) -> None:
        with self.assertRaises(ValueError):
            project_wass_points(np.zeros((1, 3)), np.zeros((1, 3)), np.zeros((3, 4)), pixel_coordinate_system="cam0")
        with self.assertRaises(ValueError):
            height_from_plane(np.ones((1, 3)), np.zeros(3), 0.0)


if __name__ == "__main__":
    unittest.main()
