"""Minimum status/ray safeguards for the dense-map MVP."""

import unittest
from pathlib import Path

import numpy as np

from src.surface_completion.dense_map import (
    ESTIMATED, ESTIMATED_GLOBAL_MODEL, OBSERVED, UNSUPPORTED, estimate_global_ray_surface, estimate_ray_surface, metric_projection,
    plane_basis, plane_xy, ray_from_projection,
    rasterize_water_roi, scale_dense_height_for_png,
)
from src.surface_completion.constrained_full_domain import fit_physical_height_trend
from scipy.spatial import cKDTree


class DenseHeightMapTests(unittest.TestCase):
    def test_all_unsupported_dense_map_renders_without_index_error(self) -> None:
        rendered = scale_dense_height_for_png(np.full((3, 4), np.nan, dtype=np.float32))
        self.assertEqual(rendered.shape, (3, 4))
        self.assertTrue(np.all(rendered == 0))

    def test_polygon_roi_rasterizes_only_declared_canonical_area(self) -> None:
        canonical = np.zeros((100, 2))
        mask = rasterize_water_roi(
            {"type": "polygon", "coordinate_system": "canonical_cam1",
             "points": [[2, 2], [7, 2], [7, 7], [2, 7]]},
            width=10, height=10, observed_rectified_px=np.array([[0., 0.], [1., 0.], [0., 1.]]),
            canonical_rectified_px=canonical,
        )
        self.assertTrue(mask[4, 4]); self.assertFalse(mask[0, 0]); self.assertFalse(mask[9, 9])

    def test_committed_polygon_output_never_populates_outside_roi(self) -> None:
        path = Path("experiments/real_video/HomeTank_004/dense_height_case2_outputs/dense_height_case2.npz")
        with np.load(path) as data:
            outside = ~data["water_roi_mask"]
            self.assertTrue(np.all(data["status"][outside] == UNSUPPORTED))
            self.assertTrue(np.all(np.isnan(data["height_mm"][outside])))

    def test_status_codes_are_distinct_and_unsupported_is_zero(self) -> None:
        self.assertEqual(int(UNSUPPORTED), 0)
        self.assertEqual({int(UNSUPPORTED), int(OBSERVED), int(ESTIMATED), int(ESTIMATED_GLOBAL_MODEL)}, {0, 1, 2, 3})

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

    def test_global_surface_uses_calibrated_ray_and_physical_plane_coordinates(self) -> None:
        normal=np.array([0.,0.,1.]);basis=plane_basis(normal)
        x,y=np.meshgrid(np.linspace(-.2,.2,12),np.linspace(-.1,.1,10));xyz=np.column_stack((x.ravel(),y.ravel(),np.ones(x.size)))
        xy=plane_xy(xyz,normal,basis);height=.004+.003*xy[:,0]-.002*xy[:,1]
        coefficients,quadratic=fit_physical_height_trend(xy,height)
        projection=np.array([[100.,0.,50.,0.],[0.,100.,40.,0.],[0.,0.,1.,0.]])
        pixels=np.array([[50.,40.],[60.,45.]])
        values,valid=estimate_global_ray_surface(pixels,projection,normal,-1.,basis,coefficients,quadratic)
        self.assertTrue(np.all(valid));self.assertTrue(np.all(np.isfinite(values)))
        self.assertAlmostEqual(float(values[0]),.004,places=8)


if __name__ == "__main__":
    unittest.main()
