"""Estimate one travelling sinusoid from a regular x-t height section."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt


@dataclass(frozen=True)
class SinusoidalWaveEstimate:
    """Estimated SI wave parameters and wrapped phase in radians."""

    amplitude_m: float
    wavelength_m: float
    frequency_hz: float
    phase_rad: float


def wrap_phase_rad(value: float) -> float:
    """Wrap an angle in radians to ``[-pi, pi)``."""
    return float((value + np.pi) % (2.0 * np.pi) - np.pi)


def estimate_sinusoidal_wave(
    height_tx_m: npt.ArrayLike,
    x_m: npt.ArrayLike,
    timestamp_ns: npt.ArrayLike,
) -> SinusoidalWaveEstimate:
    """Estimate ``A*sin(k*x-omega*t+phi)`` from a complete regular grid.

    ``height_tx_m`` is ``[time,x]`` in metres, ``x_m`` is in metres, and
    ``timestamp_ns`` is in nanoseconds. The dominant positive spatial and
    negative temporal Fourier bin defines wavelength and frequency. Amplitude
    and phase are then obtained by least squares at that bin.
    """
    h = np.asarray(height_tx_m, dtype=np.float64)
    x = np.asarray(x_m, dtype=np.float64)
    timestamps = np.asarray(timestamp_ns, dtype=np.int64)
    if h.ndim != 2 or h.shape != (timestamps.size, x.size) or min(h.shape) < 3:
        raise ValueError("height_tx_m must have shape [time,x] with at least 3 samples per axis")
    if not np.all(np.isfinite(h)) or not np.all(np.isfinite(x)):
        raise ValueError("wave estimation requires complete finite data")
    dx = np.diff(x)
    dt_s = np.diff(timestamps).astype(np.float64) * 1e-9
    if np.any(dx <= 0) or np.any(dt_s <= 0):
        raise ValueError("coordinates and timestamps must strictly increase")
    if not np.allclose(dx, dx[0], rtol=0.0, atol=1e-12):
        raise ValueError("x_m must be regularly spaced")
    if not np.allclose(dt_s, dt_s[0], rtol=0.0, atol=1e-12):
        raise ValueError("timestamp_ns must be regularly spaced")

    centered = h - np.mean(h)
    spectrum = np.fft.fft2(centered)
    spatial = np.fft.fftfreq(x.size, d=float(dx[0]))
    temporal = np.fft.fftfreq(timestamps.size, d=float(dt_s[0]))
    candidates = (spatial[np.newaxis, :] > 0) & (temporal[:, np.newaxis] < 0)
    if not np.any(candidates):
        raise ValueError("sampling does not provide travelling-wave Fourier bins")
    magnitude = np.where(candidates, np.abs(spectrum), -np.inf)
    time_index, x_index = np.unravel_index(int(np.argmax(magnitude)), magnitude.shape)
    spatial_frequency = float(spatial[x_index])
    frequency_hz = float(-temporal[time_index])
    k = 2.0 * np.pi * spatial_frequency
    omega = 2.0 * np.pi * frequency_hz
    time_s = (timestamps - timestamps[0]).astype(np.float64) * 1e-9
    theta = k * x[np.newaxis, :] - omega * time_s[:, np.newaxis]
    design = np.column_stack((np.sin(theta).ravel(), np.cos(theta).ravel(), np.ones(h.size)))
    coefficients, _, _, _ = np.linalg.lstsq(design, h.ravel(), rcond=None)
    sine_coefficient, cosine_coefficient = coefficients[:2]
    amplitude = float(np.hypot(sine_coefficient, cosine_coefficient))
    phase = wrap_phase_rad(float(np.arctan2(cosine_coefficient, sine_coefficient)))
    return SinusoidalWaveEstimate(amplitude, 1.0 / spatial_frequency, frequency_hz, phase)
