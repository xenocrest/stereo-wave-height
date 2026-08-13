"""Deterministic multi-component travelling-wave surface truth."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

import numpy as np
import numpy.typing as npt

from .surfaces import SurfaceTruth, _inputs, _surface


@dataclass(frozen=True)
class WaveComponent:
    """One SI component ``A*sin(2*pi*x/lambda-2*pi*f*t+phase)``."""

    amplitude_m: float
    wavelength_m: float
    frequency_hz: float
    phase_rad: float

    def __post_init__(self) -> None:
        values = (self.amplitude_m, self.wavelength_m, self.frequency_hz, self.phase_rad)
        if not all(np.isfinite(value) for value in values):
            raise ValueError("wave component values must be finite")
        if self.amplitude_m < 0 or self.wavelength_m <= 0 or self.frequency_hz <= 0:
            raise ValueError("amplitude must be nonnegative; wavelength and frequency must be positive")

    @property
    def wave_number_rad_per_m(self) -> float:
        return float(2.0 * np.pi / self.wavelength_m)

    @property
    def angular_frequency_rad_per_s(self) -> float:
        return float(2.0 * np.pi * self.frequency_hz)

    def to_dict(self) -> dict[str, float]:
        """Serialize without derived-value rounding or unit conversion."""
        return asdict(self)

    @classmethod
    def from_dict(cls, values: dict[str, float]) -> "WaveComponent":
        """Deserialize an explicitly keyed SI component."""
        expected = {"amplitude_m", "wavelength_m", "frequency_hz", "phase_rad"}
        if set(values) != expected:
            raise ValueError("component fields must match the explicit schema")
        return cls(**values)


def component_height_m(
    component: WaveComponent, x_m: npt.ArrayLike, time_s: npt.ArrayLike
) -> npt.NDArray[np.float64]:
    """Evaluate one component on the broadcast x/time arrays in SI units."""
    x = np.asarray(x_m, dtype=np.float64)
    time = np.asarray(time_s, dtype=np.float64)
    return component.amplitude_m * np.sin(
        component.wave_number_rad_per_m * x
        - component.angular_frequency_rad_per_s * time
        + component.phase_rad
    )


def multicomponent_wave(
    x_m: npt.ArrayLike,
    y_m: npt.ArrayLike,
    timestamp_ns: npt.ArrayLike,
    *,
    components: Iterable[WaveComponent],
    z0_m: float | npt.ArrayLike = 0.0,
) -> SurfaceTruth:
    """Generate a deterministic sum on ``[time,y,x]``; no stochastic terms."""
    frozen = tuple(components)
    if len(frozen) < 2:
        raise ValueError("multicomponent wave requires at least two components")
    x, y, timestamps, z0 = _inputs(x_m, y_m, timestamp_ns, z0_m)
    time_s = (timestamps - timestamps[0]).astype(np.float64) * 1e-9
    h_tx = sum(
        (component_height_m(c, x[np.newaxis, :], time_s[:, np.newaxis]) for c in frozen),
        start=np.zeros((timestamps.size, x.size), dtype=np.float64),
    )
    h = np.broadcast_to(h_tx[:, np.newaxis, :], (timestamps.size, y.size, x.size)).copy()
    return _surface(x, y, timestamps, z0, h, "deterministic_multicomponent_wave")
