"""Strict parser for explicitly mapped wassgridsurface NetCDF output."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt

from .model import StandardizedGrid3D, _require_known_label


@dataclass(frozen=True)
class VerifiedNetcdfMapping:
    """Run-specific mapping proven from ``ncdump -h`` and scale validation."""

    z_variable: str
    mask_variable: str
    x_variable: str
    y_variable: str
    z_dimensions: tuple[str, str, str]
    time_dimension: str
    x_dimension: str
    y_dimension: str
    source_unit: str
    output_unit: str
    source_coordinate_system: str
    output_coordinate_system: str
    scale_to_output: float
    mask_true_means_valid: bool

    def __post_init__(self) -> None:
        for field in ("z_variable", "mask_variable", "x_variable", "y_variable",
                      "time_dimension", "x_dimension", "y_dimension", "source_unit",
                      "output_unit", "source_coordinate_system", "output_coordinate_system"):
            _require_known_label(str(getattr(self, field)), field)
        if len(set(self.z_dimensions)) != 3 or set(self.z_dimensions) != {
            self.time_dimension, self.x_dimension, self.y_dimension
        }:
            raise ValueError("z_dimensions must explicitly map time, x, and y exactly once")
        if self.source_coordinate_system != self.output_coordinate_system:
            raise ValueError("coordinate-system conversion requires a separate explicit transform")
        if not isinstance(self.mask_true_means_valid, bool):
            raise TypeError("mask_true_means_valid must be explicitly boolean")
        if not np.isfinite(self.scale_to_output) or self.scale_to_output <= 0:
            raise ValueError("scale_to_output must be explicitly positive and finite")


class WassGriddedNetcdfParser:
    """Parse ``gridded.nc`` only with caller-verified field and metadata mapping."""

    format_id = "wassgridsurface.explicit-netcdf-mapping.v1"

    def __init__(self, mapping: VerifiedNetcdfMapping, timestamp_ns: npt.ArrayLike) -> None:
        self.mapping = mapping
        self.timestamp_ns = np.asarray(timestamp_ns, dtype=np.int64)
        if self.timestamp_ns.ndim != 1:
            raise ValueError("timestamp_ns must be one-dimensional")

    def parse(self, source: Path) -> StandardizedGrid3D:
        """Read the configured variables; never infer fields, axes, units, or scale."""
        try:
            from netCDF4 import Dataset
        except ImportError as error:
            raise RuntimeError("netCDF4 is required to parse WASS gridded.nc") from error
        path = Path(source)
        if not path.is_file():
            raise FileNotFoundError(path)
        mapping = self.mapping
        with Dataset(path, "r") as dataset:
            required = (mapping.z_variable, mapping.mask_variable, mapping.x_variable, mapping.y_variable)
            missing = [name for name in required if name not in dataset.variables]
            if missing:
                raise ValueError(f"configured NetCDF variables missing: {missing}")
            z_variable = dataset.variables[mapping.z_variable]
            mask_variable = dataset.variables[mapping.mask_variable]
            if tuple(z_variable.dimensions) != mapping.z_dimensions:
                raise ValueError("NetCDF Z dimension order differs from verified mapping")
            if tuple(mask_variable.dimensions) != mapping.z_dimensions:
                raise ValueError("NetCDF mask dimension order differs from verified mapping")
            z_raw = np.asarray(z_variable[:], dtype=np.float64)
            mask_raw = np.asarray(mask_variable[:], dtype=bool)
            order = tuple(mapping.z_dimensions.index(name) for name in (
                mapping.time_dimension, mapping.y_dimension, mapping.x_dimension
            ))
            z = np.transpose(z_raw, order) * mapping.scale_to_output
            declared_mask = np.transpose(mask_raw, order)
            valid = (declared_mask if mapping.mask_true_means_valid else ~declared_mask) & np.isfinite(z)
            z[~valid] = np.nan
            x = np.asarray(dataset.variables[mapping.x_variable][:], dtype=np.float64)
            y = np.asarray(dataset.variables[mapping.y_variable][:], dtype=np.float64)
        if x.ndim != 1 or y.ndim != 1:
            raise ValueError("configured X and Y variables must be one-dimensional")
        x = x * mapping.scale_to_output
        y = y * mapping.scale_to_output
        if z.shape[0] != self.timestamp_ns.size:
            raise ValueError("NetCDF frame count does not match supplied manifest timestamps")
        return StandardizedGrid3D(
            x=x, y=y, z=z, timestamp_ns=self.timestamp_ns, valid_mask=valid,
            coordinate_system=mapping.output_coordinate_system, unit=mapping.output_unit,
        )
