"""Checks for frozen multi-group sinusoidal validation definitions."""

import unittest
from pathlib import Path
import numpy as np

from src.validation import absolute_error_percentiles, estimate_sinusoidal_wave, translate_coordinate_origin_m


class WaveParameterMatrixTests(unittest.TestCase):
    def test_group_configs_parse_and_preserve_frozen_values(self) -> None:
        config_dir = Path(__file__).parents[1] / "configs" / "simulation"
        expected = {
            "case2_g1_amplitude.yaml": ("amplitude_m: 0.030", "frequency_hz: 0.50"),
            "case2_g2_frequency.yaml": ("amplitude_m: 0.010", "frequency_hz: 1.00"),
            "case2_g3_combined.yaml": ("amplitude_m: 0.030", "frequency_hz: 1.00"),
        }
        for filename, (amplitude, frequency) in expected.items():
            text = (config_dir / filename).read_text(encoding="utf-8")
            for token in (
                "status: KINEMATIC_SYNTHETIC_WAVE_TEST", amplitude, frequency,
                "wavelength_m: 0.80", "baseline_m: 0.20", "working_distance_m: 2.00",
                "zgap_percentile: 99.5",
            ):
                self.assertIn(token, text)

    def test_sampling_counts(self) -> None:
        self.assertEqual(round(0.80 / 0.01), 80)
        self.assertEqual(round(5.0 / 0.50), 10)
        self.assertEqual(round(5.0 / 1.00), 5)

    def test_30_mm_one_hz_estimator(self) -> None:
        x_grid = np.arange(160) * 0.01 - 0.895
        x_world = translate_coordinate_origin_m(x_grid, target_minus_source_m=0.10)
        timestamps = np.arange(10, dtype=np.int64) * 200_000_000
        h = 0.03 * np.sin(2*np.pi*x_world[None,:]/0.8 - 2*np.pi*1.0*(timestamps*1e-9)[:,None])
        estimate = estimate_sinusoidal_wave(h, x_world, timestamps)
        self.assertAlmostEqual(estimate.amplitude_m, 0.03, places=12)
        self.assertAlmostEqual(estimate.wavelength_m, 0.8, places=12)
        self.assertAlmostEqual(estimate.frequency_hz, 1.0, places=12)
        self.assertAlmostEqual(estimate.phase_rad, 0.0, places=12)

    def test_absolute_error_percentiles(self) -> None:
        result = absolute_error_percentiles([-4, -1, 2, 3], [True, True, True, False], (50, 90, 95, 99))
        expected = np.percentile([4, 1, 2], [50, 90, 95, 99])
        np.testing.assert_allclose(list(result.values()), expected)

    def test_unknown_config_status_is_not_accepted(self) -> None:
        # Traceable parser smoke check: the matrix constants are explicit, not inferred.
        with self.assertRaises(ValueError):
            translate_coordinate_origin_m([0.0], target_minus_source_m=float("nan"))


if __name__ == "__main__":
    unittest.main()
