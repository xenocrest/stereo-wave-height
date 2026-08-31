"""Minimal deterministic tests for the isolated global-surface experiment."""

import unittest

import numpy as np

from src.surface_completion.global_surface import fit_global_surface, global_holdout


class GlobalSurfaceCompletionTests(unittest.TestCase):
    @staticmethod
    def surface() -> tuple[np.ndarray, np.ndarray]:
        x, y = np.meshgrid(np.linspace(-1, 1, 30), np.linspace(-1, 1, 25))
        xy = np.column_stack((x.ravel(), y.ravel()))
        return xy, 0.002 * x.ravel() ** 2 - 0.001 * y.ravel() + 0.01

    def test_deterministic_finite_in_domain_prediction(self) -> None:
        xy, height = self.surface()
        first = fit_global_surface(xy, height, target_control_points=200)
        second = fit_global_surface(xy, height, target_control_points=200)
        query = np.array([[0.0, 0.0], [0.4, -0.2]])
        np.testing.assert_allclose(first.evaluate(query), second.evaluate(query), atol=1e-12)
        self.assertTrue(np.all(np.isfinite(first.evaluate(query))))

    def test_holdout_is_excluded_and_reproducible(self) -> None:
        xy, height = self.surface()
        first = global_holdout(xy, height, maximum_test_points=50, seed=7, target_control_points=200)
        second = global_holdout(xy, height, maximum_test_points=50, seed=7, target_control_points=200)
        self.assertEqual(first["holdout_indices"], second["holdout_indices"])
        self.assertEqual(len(set(first["holdout_indices"])), first["test_point_count"])
        self.assertEqual(first["coverage_percent"], 100.0)
        self.assertAlmostEqual(first["rmse_m"], second["rmse_m"])


if __name__ == "__main__":
    unittest.main()
