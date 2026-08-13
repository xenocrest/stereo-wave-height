"""Unit tests for Case 2 wave-parameter evaluation."""

import unittest

import numpy as np

from src.validation.sinusoidal_wave import (
    estimate_sinusoidal_wave,
    translate_coordinate_origin_m,
    wrap_phase_rad,
)


class SinusoidalWaveValidationTests(unittest.TestCase):
    def test_exact_known_wave_parameters(self) -> None:
        x = np.arange(160, dtype=np.float64) * 0.01 - 0.80
        timestamps = np.arange(10, dtype=np.int64) * 200_000_000
        amplitude = 0.010
        wavelength = 0.80
        frequency = 0.50
        phase = 0.37
        time_s = timestamps.astype(np.float64) * 1e-9
        height = amplitude * np.sin(
            2 * np.pi / wavelength * x[np.newaxis, :]
            - 2 * np.pi * frequency * time_s[:, np.newaxis]
            + phase
        )
        estimate = estimate_sinusoidal_wave(height, x, timestamps)
        self.assertAlmostEqual(estimate.amplitude_m, amplitude, places=12)
        self.assertAlmostEqual(estimate.wavelength_m, wavelength, places=12)
        self.assertAlmostEqual(estimate.frequency_hz, frequency, places=12)
        self.assertAlmostEqual(wrap_phase_rad(estimate.phase_rad - phase), 0.0, places=12)

    def test_nonregular_coordinates_fail(self) -> None:
        with self.assertRaisesRegex(ValueError, "regularly spaced"):
            estimate_sinusoidal_wave(np.ones((4, 4)), [0.0, 1.0, 2.1, 3.0], np.arange(4) * 10)

    def test_zero_phase_truth_is_recovered(self) -> None:
        x = np.arange(160) * 0.01 - 0.80
        timestamps = np.arange(10, dtype=np.int64) * 200_000_000
        t = timestamps * 1e-9
        h = 0.01 * np.sin(2 * np.pi / 0.8 * x[None, :] - 2 * np.pi * 0.5 * t[:, None])
        self.assertAlmostEqual(estimate_sinusoidal_wave(h, x, timestamps).phase_rad, 0.0, places=12)

    def test_x_origin_shift_changes_phase_by_k_delta_x(self) -> None:
        x_grid = np.arange(160) * 0.01 - 0.895
        x_world = translate_coordinate_origin_m(x_grid, target_minus_source_m=0.10)
        timestamps = np.arange(10, dtype=np.int64) * 200_000_000
        t = timestamps * 1e-9
        h = 0.01 * np.sin(2 * np.pi / 0.8 * x_world[None, :] - 2 * np.pi * 0.5 * t[:, None])
        grid_phase = estimate_sinusoidal_wave(h, x_grid, timestamps).phase_rad
        world_phase = estimate_sinusoidal_wave(h, x_world, timestamps).phase_rad
        self.assertAlmostEqual(grid_phase, np.pi / 4, places=12)
        self.assertAlmostEqual(world_phase, 0.0, places=12)

    def test_t_origin_shift_changes_phase_by_minus_omega_delta_t(self) -> None:
        x = np.arange(160) * 0.01 - 0.80
        timestamps = np.arange(10, dtype=np.int64) * 200_000_000
        shifted_time = (timestamps - 250_000_000).astype(np.float64) * 1e-9
        h = 0.01 * np.sin(2 * np.pi / 0.8 * x[None, :] - 2 * np.pi * 0.5 * shifted_time[:, None])
        phase = estimate_sinusoidal_wave(h, x, timestamps).phase_rad
        self.assertAlmostEqual(phase, np.pi / 4, places=12)

    def test_phase_wrap_interval(self) -> None:
        self.assertAlmostEqual(wrap_phase_rad(2 * np.pi + 0.2), 0.2, places=12)
        self.assertAlmostEqual(wrap_phase_rad(-2 * np.pi - 0.2), -0.2, places=12)
        self.assertAlmostEqual(wrap_phase_rad(np.pi), -np.pi, places=12)


if __name__ == "__main__":
    unittest.main()
