"""Adapter entry point for already-standardized simulated WASS output.

This factory does not simulate WASS and does not parse raw WASS files. It is
only a strict boundary for artificial canonical arrays used by unit tests.
"""

from __future__ import annotations

import numpy.typing as npt

from .model import StandardizedGrid3D


def from_standardized_simulation(
    *,
    x: npt.ArrayLike,
    y: npt.ArrayLike,
    z: npt.ArrayLike,
    timestamp_ns: npt.ArrayLike,
    valid_mask: npt.ArrayLike,
    coordinate_system: str,
    unit: str,
) -> StandardizedGrid3D:
    """Validate and wrap a standardized simulated post-WASS result."""
    return StandardizedGrid3D(
        x=x,
        y=y,
        z=z,
        timestamp_ns=timestamp_ns,
        valid_mask=valid_mask,
        coordinate_system=coordinate_system,
        unit=unit,
    )
