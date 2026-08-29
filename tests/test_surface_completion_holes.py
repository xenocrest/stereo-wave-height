"""Minimal continuous-hole completion safeguards."""

import hashlib
from pathlib import Path
import unittest

import numpy as np
from scipy.spatial import cKDTree
import yaml

from src.surface_completion.holes import evaluate_spatial_holes, hole_support_indices


class SurfaceCompletionHoleTests(unittest.TestCase):
    def test_points_inside_hole_are_excluded(self) -> None:
        x, y = np.meshgrid(np.arange(7, dtype=float), np.arange(7, dtype=float))
        xy = np.column_stack((x.ravel(), y.ravel()))
        center = np.array([3., 3.])
        support = hole_support_indices(cKDTree(xy), xy, center, hole_radius_m=1.5, support_radius_m=3)
        self.assertTrue(np.all(np.linalg.norm(xy[support] - center, axis=1) > 1.5))

    def test_fixed_seed_is_reproducible(self) -> None:
        x, y = np.meshgrid(np.linspace(0, 1, 30), np.linspace(0, 1, 30))
        xy = np.column_stack((x.ravel(), y.ravel())); height = x.ravel() + y.ravel()
        kwargs = dict(maximum_test_centers=20, seed=9, hole_radius_multipliers=(.5, 1.5, 3., 4.5))
        self.assertEqual(evaluate_spatial_holes(xy, height, **kwargs), evaluate_spatial_holes(xy, height, **kwargs))

    def test_frozen_artifacts_unchanged_when_present(self) -> None:
        result = yaml.safe_load(Path("experiments/real_video/HomeTank_004/surface_completion_hole_validation.yaml").read_text(encoding="utf-8"))
        for frame in result["config"]["frames"]:
            path = Path(frame["height_npz"])
            if path.exists():
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest().upper(), frame["sha256"])


if __name__ == "__main__":
    unittest.main()
