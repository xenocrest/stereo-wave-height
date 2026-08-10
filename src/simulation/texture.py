"""Deterministic simulation-only texture attached to a surface grid."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt


FloatArray = npt.NDArray[np.float64]
UInt8Array = npt.NDArray[np.uint8]


@dataclass(frozen=True)
class PlanarRandomTexture:
    """Unsigned 8-bit intensities tied to physical ``(x,y)`` samples."""

    x_m: FloatArray
    y_m: FloatArray
    intensity: UInt8Array
    seed: int
    source: str = "deterministic_planar_random_simulation"
    status: str = "SIMULATION_ASSUMPTION"

    def __post_init__(self) -> None:
        x = np.asarray(self.x_m, dtype=np.float64)
        y = np.asarray(self.y_m, dtype=np.float64)
        intensity = np.asarray(self.intensity)
        if x.ndim != 1 or y.ndim != 1 or x.size == 0 or y.size == 0:
            raise ValueError("x_m and y_m must be non-empty one-dimensional arrays")
        if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
            raise ValueError("texture coordinates must be finite")
        if intensity.shape != (y.size, x.size) or intensity.dtype != np.uint8:
            raise ValueError("intensity must be uint8 with shape [y,x]")
        object.__setattr__(self, "x_m", x.copy())
        object.__setattr__(self, "y_m", y.copy())
        object.__setattr__(self, "intensity", intensity.copy())


def planar_random_texture(
    x_m: npt.ArrayLike,
    y_m: npt.ArrayLike,
    *,
    seed: int,
    minimum: int = 16,
    maximum: int = 239,
) -> PlanarRandomTexture:
    """Create repeatable random grayscale values on physical surface samples."""
    if not isinstance(seed, (int, np.integer)):
        raise TypeError("seed must be an integer")
    if not 0 <= minimum <= maximum <= 255:
        raise ValueError("texture limits must satisfy 0 <= minimum <= maximum <= 255")
    x = np.asarray(x_m, dtype=np.float64)
    y = np.asarray(y_m, dtype=np.float64)
    if x.ndim != 1 or y.ndim != 1 or x.size == 0 or y.size == 0:
        raise ValueError("x_m and y_m must be non-empty one-dimensional arrays")
    generator = np.random.default_rng(int(seed))
    values = generator.integers(
        minimum, maximum + 1, size=(y.size, x.size), dtype=np.uint8
    )
    return PlanarRandomTexture(x, y, values, int(seed))
