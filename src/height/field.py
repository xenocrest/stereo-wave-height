"""Calculate ``H(time,y,x) = Z(time,y,x) - Z0(y,x)`` explicitly."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from adapters.wass.output import StandardizedGrid3D
from reference import StaticWaterReference


FloatArray = npt.NDArray[np.float64]
BoolArray = npt.NDArray[np.bool_]
IntArray = npt.NDArray[np.int64]


@dataclass(frozen=True)
class HeightField:
    """Relative height on a canonical ``[time, y, x]`` grid."""

    x: FloatArray
    y: FloatArray
    h: FloatArray
    timestamp_ns: IntArray
    valid_mask: BoolArray
    coordinate_system: str
    unit: str

    def __post_init__(self) -> None:
        expected_shape = (self.timestamp_ns.size, self.y.size, self.x.size)
        if self.h.shape != expected_shape or self.valid_mask.shape != expected_shape:
            raise ValueError("h and valid_mask must have shape [time, y, x]")
        if np.any(self.valid_mask & ~np.isfinite(self.h)):
            raise ValueError("valid height cells must be finite")
        if np.any(~self.valid_mask & ~np.isnan(self.h)):
            raise ValueError("invalid height cells must be NaN")


def calculate_height(
    dynamic: StandardizedGrid3D,
    reference: StaticWaterReference,
) -> HeightField:
    """Subtract a compatible static reference and propagate masks/NaNs.

    Grid coordinates, unit, coordinate-system identifier, and spatial shape
    must match exactly. The function performs no resampling or unit conversion.
    """
    if dynamic.coordinate_system != reference.coordinate_system:
        raise ValueError("coordinate system mismatch between Z and Z0")
    if dynamic.unit != reference.unit:
        raise ValueError("unit mismatch between Z and Z0")
    if dynamic.z.shape[1:] != reference.z0.shape:
        raise ValueError("spatial shape mismatch between Z and Z0")
    if not np.array_equal(dynamic.x, reference.x) or not np.array_equal(dynamic.y, reference.y):
        raise ValueError("grid coordinates differ between Z and Z0")

    valid = dynamic.valid_mask & reference.valid_mask[np.newaxis, :, :]
    h = np.full(dynamic.z.shape, np.nan, dtype=np.float64)
    difference = dynamic.z - reference.z0[np.newaxis, :, :]
    h[valid] = difference[valid]
    return HeightField(
        x=dynamic.x.copy(),
        y=dynamic.y.copy(),
        h=h,
        timestamp_ns=dynamic.timestamp_ns.copy(),
        valid_mask=valid,
        coordinate_system=dynamic.coordinate_system,
        unit=dynamic.unit,
    )
