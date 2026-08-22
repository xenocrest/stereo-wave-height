import unittest

import numpy as np

from adapters.wass.plane_sampling import (
    PlaneRansacSamplingMode,
    PlaneRansacSamplingPolicy,
)


class FixedSampler:
    def __init__(self, values):
        self.values = np.asarray(values, dtype=np.int64)

    def integers(self, high, size):
        if size != 3 or np.any(self.values >= high):
            raise AssertionError("invalid deterministic sampler request")
        return self.values.copy()


class WassPlaneSamplingTests(unittest.TestCase):
    def test_valid_point_mode_samples_only_valid_xyz_locations(self):
        mask = np.array([[False, True, False], [True, False, True]], dtype=bool)
        policy = PlaneRansacSamplingPolicy(PlaneRansacSamplingMode.VALID_POINT_SAMPLING)
        selected = policy.sample_flat_indices(mask, FixedSampler([0, 1, 2]))
        self.assertEqual(selected.tolist(), [1, 3, 5])
        self.assertTrue(np.all(mask.ravel()[selected]))

    def test_default_fallback_preserves_full_image_random_sampling(self):
        mask = np.array([[False, True], [False, False]], dtype=bool)
        policy = PlaneRansacSamplingPolicy()
        selected = policy.sample_flat_indices(mask, FixedSampler([0, 2, 3]))
        self.assertEqual(selected.tolist(), [0, 2, 3])
        self.assertFalse(np.any(mask.ravel()[selected]))
        self.assertEqual(
            policy.wass_config_line(),
            'PLANE_RANSAC_SAMPLING_MODE="FULL_IMAGE_RANDOM_SAMPLING"',
        )

    def test_valid_point_mode_rejects_insufficient_population(self):
        policy = PlaneRansacSamplingPolicy(PlaneRansacSamplingMode.VALID_POINT_SAMPLING)
        with self.assertRaisesRegex(ValueError, "at least three"):
            policy.sample_flat_indices(np.array([[True, False]], dtype=bool), FixedSampler([0, 0, 0]))


if __name__ == "__main__":
    unittest.main()
