"""Minimal static-water reference using an explicit valid temporal mean."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from adapters.wass.output import StandardizedGrid3D


FloatArray = npt.NDArray[np.float64]
BoolArray = npt.NDArray[np.bool_]
IntArray = npt.NDArray[np.int64]


@dataclass(frozen=True)
class StaticWaterReference:
    """Static reference ``Z0[y, x]`` with grid and provenance metadata."""

    x: FloatArray
    y: FloatArray
    z0: FloatArray
    valid_mask: BoolArray
    sample_count: IntArray
    coordinate_system: str
    unit: str
    method: str = "valid_temporal_mean"

    def __post_init__(self) -> None:
        expected_shape = (self.y.size, self.x.size)
        if self.z0.shape != expected_shape:
            raise ValueError("z0 must have shape [y, x]")
        if self.valid_mask.shape != expected_shape or self.sample_count.shape != expected_shape:
            raise ValueError("reference masks and counts must have shape [y, x]")
        if self.method != "valid_temporal_mean":
            raise ValueError("only valid_temporal_mean is supported")
        if np.any(self.valid_mask & ~np.isfinite(self.z0)):
            raise ValueError("valid z0 cells must be finite")
        if np.any(~self.valid_mask & ~np.isnan(self.z0)):
            raise ValueError("invalid z0 cells must be NaN")
        if np.any(self.valid_mask & (self.sample_count <= 0)):
            raise ValueError("valid z0 cells require at least one sample")


def valid_temporal_mean(static: StandardizedGrid3D) -> StaticWaterReference:
    """Compute ``Z0[y, x]`` as the mean of explicitly valid time samples.

    No smoothing, fitting, interpolation, filtering, or hole filling occurs.
    Cells without any valid sample remain NaN and invalid.
    """
    count = np.sum(static.valid_mask, axis=0, dtype=np.int64)
    total = np.sum(np.where(static.valid_mask, static.z, 0.0), axis=0)
    valid = count > 0
    z0 = np.full(count.shape, np.nan, dtype=np.float64)
    np.divide(total, count, out=z0, where=valid)
    return StaticWaterReference(
        x=static.x.copy(),
        y=static.y.copy(),
        z0=z0,
        valid_mask=valid,
        sample_count=count,
        coordinate_system=static.coordinate_system,
        unit=static.unit,
    )
