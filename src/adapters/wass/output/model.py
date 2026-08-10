"""Canonical gridded 3-D results produced after a WASS output adapter.

This module deliberately does not parse any unconfirmed WASS field. Future
version-specific parsers must produce :class:`StandardizedGrid3D` instances.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt


FloatArray = npt.NDArray[np.float64]
BoolArray = npt.NDArray[np.bool_]
IntArray = npt.NDArray[np.int64]


def _require_known_label(value: str, field_name: str) -> str:
    """Return a stripped explicit label or fail for UNKNOWN/empty values."""
    normalized = value.strip()
    if not normalized or normalized.upper() in {"UNKNOWN", "TODO", "UNKNOWN/TODO"}:
        raise ValueError(f"{field_name} must be explicitly known, got {value!r}")
    return normalized


@dataclass(frozen=True)
class StandardizedGrid3D:
    """Standardized WASS-adapter result on a ``[time, y, x]`` grid.

    Parameters use project interface units, not guessed WASS source units.
    Invalid cells must be NaN and have ``valid_mask=False``. Valid cells must
    be finite. ``coordinate_system`` and ``unit`` are mandatory provenance.
    """

    x: FloatArray
    y: FloatArray
    z: FloatArray
    timestamp_ns: IntArray
    valid_mask: BoolArray
    coordinate_system: str
    unit: str

    def __post_init__(self) -> None:
        x = np.asarray(self.x, dtype=np.float64)
        y = np.asarray(self.y, dtype=np.float64)
        z = np.asarray(self.z, dtype=np.float64)
        timestamp_ns = np.asarray(self.timestamp_ns, dtype=np.int64)
        valid_mask = np.asarray(self.valid_mask, dtype=np.bool_)

        if x.ndim != 1 or y.ndim != 1:
            raise ValueError("x and y must be one-dimensional coordinate arrays")
        if z.ndim != 3:
            raise ValueError("z must have shape [time, y, x]")
        expected_shape = (timestamp_ns.size, y.size, x.size)
        if z.shape != expected_shape:
            raise ValueError(f"z shape {z.shape} does not match {expected_shape}")
        if valid_mask.shape != z.shape:
            raise ValueError("valid_mask must have the same shape as z")
        if timestamp_ns.ndim != 1:
            raise ValueError("timestamp_ns must be one-dimensional")
        if timestamp_ns.size > 1 and np.any(np.diff(timestamp_ns) <= 0):
            raise ValueError("timestamp_ns must be strictly increasing")
        if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
            raise ValueError("x and y coordinates must be finite")
        if np.any(valid_mask & ~np.isfinite(z)):
            raise ValueError("valid z cells must be finite")
        if np.any(~valid_mask & ~np.isnan(z)):
            raise ValueError("invalid z cells must be NaN")

        object.__setattr__(self, "x", x.copy())
        object.__setattr__(self, "y", y.copy())
        object.__setattr__(self, "z", z.copy())
        object.__setattr__(self, "timestamp_ns", timestamp_ns.copy())
        object.__setattr__(self, "valid_mask", valid_mask.copy())
        object.__setattr__(
            self, "coordinate_system", _require_known_label(self.coordinate_system, "coordinate_system")
        )
        object.__setattr__(self, "unit", _require_known_label(self.unit, "unit"))
