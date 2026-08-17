"""Affine shared-event synchronization and pairing tests."""

import unittest

import numpy as np

from synchronization import fit_affine_time_mapping, pair_nearest_timestamps


class SynchronizationTests(unittest.TestCase):
    def test_pure_offset(self) -> None:
        mapping = fit_affine_time_mapping([0, 5, 10], [.12, 5.12, 10.12])
        self.assertAlmostEqual(mapping.scale, 1.0, places=12)
        self.assertAlmostEqual(mapping.offset_s, .12, places=12)
        self.assertLess(mapping.residual_rmse_s, 1e-12)

    def test_offset_and_clock_drift(self) -> None:
        left = np.array([0, 3, 7, 12], dtype=float)
        right = 1.0004 * left - .08
        mapping = fit_affine_time_mapping(left, right)
        self.assertAlmostEqual(mapping.scale, 1.0004, places=12)
        self.assertAlmostEqual(mapping.offset_s, -.08, places=12)

    def test_nearest_frame_pairing(self) -> None:
        mapping = fit_affine_time_mapping([0, 1], [.02, 1.02])
        result = pair_nearest_timestamps([0, .04, .08], [.019, .061, .101], mapping, tolerance_s=.003)
        self.assertEqual([(p.left_index, p.right_index) for p in result.pairs], [(0, 0), (1, 1), (2, 2)])
        self.assertEqual(result.rejected_left_indices, ())

    def test_tolerance_rejection(self) -> None:
        mapping = fit_affine_time_mapping([0, 1], [0, 1])
        result = pair_nearest_timestamps([0, .04], [0, .10], mapping, tolerance_s=.01)
        self.assertEqual([(p.left_index, p.right_index) for p in result.pairs], [(0, 0)])
        self.assertEqual(result.rejected_left_indices, (1,))


if __name__ == "__main__":
    unittest.main()
