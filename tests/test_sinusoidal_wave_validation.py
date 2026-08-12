"""Unit tests for Case 2 wave-parameter evaluation."""

import unittest

import numpy as np

from src.validation.sinusoidal_wave import estimate_sinusoidal_wave, wrap_phase_rad


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


if __name__ == "__main__":
    unittest.main()
