"""Tests for reusable static-frame consistency diagnostics."""

import unittest

import numpy as np

from src.validation.static_consistency import (
    depth_drift,
    distribution_summary,
    histogram_total_variation,
    mask_overlap,
    normalized_histogram,
    plane_geometry,
)


class StaticConsistencyTests(unittest.TestCase):
    def test_histogram_and_total_variation(self) -> None:
        dark = np.zeros((2, 2), dtype=np.uint8)
        bright = np.full((2, 2), 255, dtype=np.uint8)
        first = normalized_histogram(dark, bins=16)
        second = normalized_histogram(bright, bins=16)
        self.assertAlmostEqual(float(first.sum()), 1.0)
        self.assertEqual(histogram_total_variation(first, first), 0.0)
        self.assertEqual(histogram_total_variation(first, second), 1.0)

    def test_mask_overlap_uses_intersection_over_union(self) -> None:
        first = np.asarray([[True, True], [False, False]])
        second = np.asarray([[True, False], [True, False]])
        self.assertAlmostEqual(mask_overlap(first, second), 1.0 / 3.0)

    def test_distribution_contains_requested_quantiles(self) -> None:
        result = distribution_summary(np.arange(1.0, 101.0))
        self.assertEqual(result.count, 100)
        self.assertEqual(result.minimum, 1.0)
        self.assertEqual(result.maximum, 100.0)
        self.assertEqual(result.median, 50.5)
        self.assertAlmostEqual(result.p5, 5.95)
        self.assertAlmostEqual(result.p95, 95.05)

    def test_depth_drift_uses_only_common_mask(self) -> None:
        reference = np.asarray([[1.0, 10.0], [2.0, 20.0]])
        current = np.asarray([[1.1, -99.0], [1.8, -99.0]])
        mask = np.asarray([[True, False], [True, False]])
        result = depth_drift(current, reference, mask)
        self.assertEqual(result.count, 2)
        self.assertAlmostEqual(result.mean, -0.05)
        self.assertAlmostEqual(result.rms, np.sqrt(0.025))
        self.assertAlmostEqual(result.p95_absolute, 0.195)

    def test_plane_geometry_has_positive_z_normal(self) -> None:
        result = plane_geometry(0.0, 0.0, 2.0)
        self.assertEqual(result.normal_xyz, (0.0, 0.0, 1.0))
        self.assertEqual(result.offset, -2.0)
        self.assertEqual(result.tilt_deg, 0.0)

    def test_unknown_or_incompatible_domains_fail_explicitly(self) -> None:
        with self.assertRaises(ValueError):
            mask_overlap(np.zeros((2, 2), dtype=bool), np.zeros((2, 2), dtype=bool))
        with self.assertRaises(ValueError):
            depth_drift(np.ones((2, 2)), np.ones((2, 3)), np.ones((2, 2), dtype=bool))
        with self.assertRaises(ValueError):
            normalized_histogram(np.asarray([[300.0]]))


if __name__ == "__main__":
    unittest.main()
