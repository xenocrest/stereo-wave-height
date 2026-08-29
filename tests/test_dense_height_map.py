"""Minimum status/ray safeguards for the dense-map MVP."""

import unittest

import numpy as np

from src.surface_completion.dense_map import (
    ESTIMATED, OBSERVED, UNSUPPORTED, estimate_ray_surface, metric_projection,
    plane_basis, plane_xy, ray_from_projection,
)
from scipy.spatial import cKDTree


class DenseHeightMapTests(unittest.TestCase):
    def test_status_codes_are_distinct_and_unsupported_is_zero(self) -> None:
        self.assertEqual(int(UNSUPPORTED), 0)
        self.assertEqual({int(UNSUPPORTED), int(OBSERVED), int(ESTIMATED)}, {0, 1, 2})

    def test_metric_projection_preserves_projected_pixel(self) -> None:
        projection = np.array([[2., 0., 0., 1.], [0., 2., 0., 0.], [0., 0., 1., 0.]])
        scale = 0.25
        metric = metric_projection(projection, scale)
        point_unscaled = np.array([1., 2., 4., 1.])
        point_metric = np.array([.25, .5, 1., 1.])
        a, b = projection @ point_unscaled, metric @ point_metric
        np.testing.assert_allclose(a[:2] / a[2], b[:2] / b[2])

    def test_projection_ray_reprojects_query(self) -> None:
        projection = np.array([[100., 0., 50., 0.], [0., 100., 40., 0.], [0., 0., 1., 0.]])
        center, direction = ray_from_projection(np.array([60., 45.]), projection)
        point = center + direction * 2
        image = projection @ np.r_[point, 1.]
        np.testing.assert_allclose(image[:2] / image[2], [60., 45.])

    def test_supported_and_unsupported_ray_surface_queries(self) -> None:
        x, y = np.meshgrid(np.linspace(-.01, .01, 31), np.linspace(-.01, .01, 31))
        xyz = np.column_stack((x.ravel(), y.ravel(), np.ones(x.size)))
        height = np.zeros(x.size); normal = np.array([0., 0., 1.]); basis = plane_basis(normal)
        xy = plane_xy(xyz, normal, basis); tree = cKDTree(xy)
        projection = np.array([[100., 0., 0., 0.], [0., 100., 0., 0.], [0., 0., 1., 0.]])
        policy = dict(radius_multiplier=6., sigma_multiplier=3., minimum_points=12,
                      maximum_neighbors=64, maximum_condition_number=1e8)
        value, info = estimate_ray_surface(np.array([0., 0.]), projection, xyz, height, xy, tree,
                                           normal, -1., basis, xyz[x.size // 2],
                                           p90_spacing_m=.001, maximum_gap_m=.003, mls=policy)
        self.assertTrue(np.isfinite(value)); self.assertEqual(info["status"], "SUPPORTED")
        value, _ = estimate_ray_surface(np.array([50., 50.]), projection, xyz, height, xy, tree,
                                        normal, -1., basis, xyz[-1], p90_spacing_m=.001,
                                        maximum_gap_m=.003, mls=policy)
        self.assertTrue(np.isnan(value))


if __name__ == "__main__":
    unittest.main()
