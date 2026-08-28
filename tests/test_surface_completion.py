"""Minimal safeguards for physical-XY spatial surface completion."""

import unittest
from pathlib import Path
import hashlib

import numpy as np
import yaml

from src.surface_completion.mls import deterministic_holdout_indices, evaluate_holdout, quadratic_mls_predict


class SurfaceCompletionTests(unittest.TestCase):
    def test_quadratic_surface_recovery(self) -> None:
        x, y = np.meshgrid(np.linspace(-1, 1, 9), np.linspace(-1, 1, 9))
        xy = np.column_stack((x.ravel(), y.ravel()))
        h = 0.2*x.ravel()**2 + 0.1*x.ravel()*y.ravel() - 0.05*y.ravel()**2 + 0.3*x.ravel() - 0.1*y.ravel() + 2
        value, diagnostic = quadratic_mls_predict(
            xy, h, np.array([0.1, -0.2]), support_radius_m=2, gaussian_sigma_m=1,
            minimum_points=12, maximum_neighbors=64, maximum_condition_number=1e8,
        )
        self.assertEqual(diagnostic["status"], "SUPPORTED")
        self.assertAlmostEqual(value, 2.2*0 + (0.2*0.01 + 0.1*-0.02 - 0.05*0.04 + 0.03 + 0.02 + 2), places=10)

    def test_support_shortage_returns_nan(self) -> None:
        value, diagnostic = quadratic_mls_predict(
            np.array([[0., 0.], [1., 0.]]), np.array([0., 1.]), np.array([0., 0.]),
            support_radius_m=2, gaussian_sigma_m=1, minimum_points=6,
            maximum_neighbors=6, maximum_condition_number=1e8,
        )
        self.assertTrue(np.isnan(value))
        self.assertEqual(diagnostic["status"], "UNSUPPORTED_MINIMUM_POINTS")

    def test_holdout_is_reproducible_and_excludes_test_points(self) -> None:
        first = deterministic_holdout_indices(100, 0.1, 20, 7)
        second = deterministic_holdout_indices(100, 0.1, 20, 7)
        np.testing.assert_array_equal(first, second)
        support = np.ones(100, dtype=bool); support[first] = False
        self.assertFalse(np.any(support[first]))

    def test_evaluation_reproducible(self) -> None:
        x, y = np.meshgrid(np.linspace(0, 1, 20), np.linspace(0, 1, 20))
        xy = np.column_stack((x.ravel(), y.ravel())); h = x.ravel() + y.ravel()
        kwargs = dict(holdout_ratio=.1, maximum_test_points=30, seed=12, radius_multiplier=6,
                      sigma_multiplier=3, minimum_points=12, maximum_neighbors=64,
                      maximum_condition_number=1e8)
        self.assertEqual(evaluate_holdout(xy, h, **kwargs).to_dict(), evaluate_holdout(xy, h, **kwargs).to_dict())

    def test_repository_result_preserves_frozen_hashes(self) -> None:
        result = yaml.safe_load(Path("experiments/real_video/HomeTank_004/surface_completion_holdout_validation.yaml").read_text(encoding="utf-8"))
        self.assertEqual(result["classification"], "SPATIAL_SURFACE_COMPLETION_PROMISING")
        for frame in result["config"]["frames"]:
            path = Path(frame["height_npz"])
            if path.exists():
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest().upper(), frame["sha256"])
        for source in Path("src/reconstruction").glob("*.py"):
            self.assertNotIn("surface_completion", source.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
