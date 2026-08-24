"""Tests for general wave-height and drift diagnostics."""

import tempfile
import unittest
from pathlib import Path

import numpy as np

from src.validation.drift_analysis import spatial_deviation, temporal_mean_drift
from src.validation.wave_height import (
    HeightSamples,
    common_observed_roi,
    drift_correct_spatial_mean,
    load_height_samples,
    roi_mask,
)
from src.validation.wave_statistics import height_statistics, significant_wave_height


class WaveHeightValidationTests(unittest.TestCase):
    def test_common_roi_uses_physical_intersection(self) -> None:
        valid = np.ones(3, dtype=bool)
        first = HeightSamples(np.array([0.0, 1.0, 2.0]), np.array([0.0, 1.0, 2.0]), np.zeros(3), valid)
        second = HeightSamples(np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0, 3.0]), np.zeros(3), valid)
        roi = common_observed_roi([first, second])
        self.assertEqual((roi.x_min_m, roi.x_max_m, roi.y_min_m, roi.y_max_m), (1.0, 2.0, 1.0, 2.0))
        self.assertEqual(int(np.count_nonzero(roi_mask(first, roi))), 2)

    def test_drift_correction_preserves_raw_and_removes_mean(self) -> None:
        raw = np.array([1.0, 2.0, 3.0])
        corrected = drift_correct_spatial_mean(raw)
        np.testing.assert_array_equal(raw, [1.0, 2.0, 3.0])
        self.assertAlmostEqual(float(corrected.mean()), 0.0)

    def test_statistics_and_temporal_drift(self) -> None:
        stats = height_statistics(np.array([-1.0, 1.0]))
        self.assertEqual(stats.rms, 1.0)
        self.assertEqual(stats.peak_to_peak, 2.0)
        drift = temporal_mean_drift([np.array([0.0, 0.0]), np.array([2.0, 2.0])])
        self.assertEqual(drift.signed_drift, (0.0, 2.0))
        self.assertAlmostEqual(drift.rms, np.sqrt(2.0))

    def test_spatial_deviation_and_significant_height_boundary(self) -> None:
        result = spatial_deviation(np.array([1.0, 2.0, 3.0]))
        self.assertAlmostEqual(result["rms"], np.sqrt(2.0 / 3.0))
        self.assertIsNone(significant_wave_height(np.array([1.0, 2.0])))
        self.assertEqual(significant_wave_height(np.array([1.0, 2.0, 3.0])), 3.0)

    def test_npz_schema_is_strict(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "height.npz"
            np.savez(path, x_m=[0.0], y_m=[0.0], height_m=[0.1], water_mask=[True])
            self.assertEqual(load_height_samples(path).height_m[0], 0.1)
            bad = Path(temporary) / "bad.npz"
            np.savez(bad, x_m=[0.0])
            with self.assertRaises(ValueError):
                load_height_samples(bad)


if __name__ == "__main__":
    unittest.main()
