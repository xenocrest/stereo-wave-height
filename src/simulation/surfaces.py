"""Analytical water-surface truth generators; no visual texture synthesis."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt


FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]


@dataclass(frozen=True)
class SurfaceTruth:
    """Analytical truth on ``[time,y,x]`` in the world water-surface frame."""

    x_m: FloatArray
    y_m: FloatArray
    timestamp_ns: IntArray
    z0_m: FloatArray
    h_true_m: FloatArray
    z_true_m: FloatArray
    model: str
    coordinate_system: str = "world_water_surface"
    unit: str = "m"

    def __post_init__(self) -> None:
        expected_spatial = (self.y_m.size, self.x_m.size)
        expected_dynamic = (self.timestamp_ns.size, *expected_spatial)
        if self.x_m.ndim != 1 or self.y_m.ndim != 1 or self.timestamp_ns.ndim != 1:
            raise ValueError("x, y, and timestamp arrays must be one-dimensional")
        if self.z0_m.shape != expected_spatial:
            raise ValueError("z0_m must have shape [y,x]")
        if self.h_true_m.shape != expected_dynamic or self.z_true_m.shape != expected_dynamic:
            raise ValueError("height and surface truth must have shape [time,y,x]")
        if self.timestamp_ns.size > 1 and np.any(np.diff(self.timestamp_ns) <= 0):
            raise ValueError("timestamp_ns must be strictly increasing")
        for array in (self.x_m, self.y_m, self.z0_m, self.h_true_m, self.z_true_m):
            if not np.all(np.isfinite(array)):
                raise ValueError("surface truth arrays must be finite")
        if not np.allclose(self.z_true_m, self.z0_m[np.newaxis, :, :] + self.h_true_m):
            raise ValueError("z_true_m must equal z0_m + h_true_m")

    def points_at(self, time_index: int) -> FloatArray:
        """Return world points ``[y,x,3]`` for one truth time index."""
        if time_index < 0 or time_index >= self.timestamp_ns.size:
            raise IndexError("surface time index out of range")
        x_grid, y_grid = np.meshgrid(self.x_m, self.y_m)
        return np.stack((x_grid, y_grid, self.z_true_m[time_index]), axis=-1)


def _inputs(
    x_m: npt.ArrayLike,
    y_m: npt.ArrayLike,
    timestamp_ns: npt.ArrayLike,
    z0_m: float | npt.ArrayLike,
) -> tuple[FloatArray, FloatArray, IntArray, FloatArray]:
    x = np.asarray(x_m, dtype=np.float64)
    y = np.asarray(y_m, dtype=np.float64)
    timestamps = np.asarray(timestamp_ns, dtype=np.int64)
    if x.ndim != 1 or y.ndim != 1 or timestamps.ndim != 1:
        raise ValueError("x_m, y_m, and timestamp_ns must be one-dimensional")
    z0_raw = np.asarray(z0_m, dtype=np.float64)
    if z0_raw.ndim == 0:
        z0 = np.full((y.size, x.size), float(z0_raw), dtype=np.float64)
    elif z0_raw.shape == (y.size, x.size):
        z0 = z0_raw.copy()
    else:
        raise ValueError("z0_m must be scalar or have shape [y,x]")
    return x, y, timestamps, z0


def _surface(
    x: FloatArray,
    y: FloatArray,
    timestamps: IntArray,
    z0: FloatArray,
    h: FloatArray,
    model: str,
) -> SurfaceTruth:
    return SurfaceTruth(x, y, timestamps, z0, h, z0[np.newaxis, :, :] + h, model)


def static_water(
    x_m: npt.ArrayLike,
    y_m: npt.ArrayLike,
    timestamp_ns: npt.ArrayLike,
    *,
    z0_m: float | npt.ArrayLike = 0.0,
) -> SurfaceTruth:
    """Generate ``H_true=0`` with metres and nanosecond timestamps."""
    x, y, timestamps, z0 = _inputs(x_m, y_m, timestamp_ns, z0_m)
    h = np.zeros((timestamps.size, y.size, x.size), dtype=np.float64)
    return _surface(x, y, timestamps, z0, h, "static_water")


def constant_height(
    x_m: npt.ArrayLike,
    y_m: npt.ArrayLike,
    timestamp_ns: npt.ArrayLike,
    *,
    delta_height_m: float,
    z0_m: float | npt.ArrayLike = 0.0,
) -> SurfaceTruth:
    """Generate a plane at explicit signed height ``delta_height_m``."""
    if not np.isfinite(delta_height_m):
        raise ValueError("delta_height_m must be finite")
    x, y, timestamps, z0 = _inputs(x_m, y_m, timestamp_ns, z0_m)
    h = np.full((timestamps.size, y.size, x.size), delta_height_m, dtype=np.float64)
    return _surface(x, y, timestamps, z0, h, "constant_height")


def sinusoidal_wave(
    x_m: npt.ArrayLike,
    y_m: npt.ArrayLike,
    timestamp_ns: npt.ArrayLike,
    *,
    amplitude_m: float,
    wave_number_rad_per_m: float,
    angular_frequency_rad_per_s: float,
    phase_rad: float = 0.0,
    z0_m: float | npt.ArrayLike = 0.0,
) -> SurfaceTruth:
    """Generate ``H=A*sin(k*x-omega*t+phase)`` without a texture model."""
    parameters = (amplitude_m, wave_number_rad_per_m, angular_frequency_rad_per_s, phase_rad)
    if not all(np.isfinite(value) for value in parameters):
        raise ValueError("all sinusoidal parameters must be finite")
    x, y, timestamps, z0 = _inputs(x_m, y_m, timestamp_ns, z0_m)
    time_s = (timestamps - timestamps[0]).astype(np.float64) * 1e-9
    phase = (
        wave_number_rad_per_m * x[np.newaxis, np.newaxis, :]
        - angular_frequency_rad_per_s * time_s[:, np.newaxis, np.newaxis]
        + phase_rad
    )
    h_x = amplitude_m * np.sin(phase)
    h = np.broadcast_to(h_x, (timestamps.size, y.size, x.size)).copy()
    return _surface(x, y, timestamps, z0, h, "sinusoidal_wave")
