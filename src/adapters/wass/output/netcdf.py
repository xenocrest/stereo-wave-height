"""Strict parser for explicitly mapped wassgridsurface NetCDF output."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt

from .model import StandardizedGrid3D, _require_known_label


WASSGRIDSURFACE_0_11_4_COORDINATE_SYSTEM = "wass_plane_aligned_grid"


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


class WassGridSurface0114Parser:
    """Parse the schema verified from ``wassgridsurface==0.11.4``.

    The release labels both spatial dimensions as ``(X, Y)`` although the
    first array index varies with physical y and the second with physical x.
    The coordinate fields are verified before mapping to ``[time, y, x]``.

    The 0.11.4 DCT path creates but does not populate ``maskZ``. The caller
    must explicitly select its version-specific finite-Z validity policy.
    """

    format_id = "wassgridsurface.netcdf.0.11.4"
    _VALIDITY_POLICY = "finite_z_for_dct_0_11_4"

    def __init__(
        self,
        *,
        timestamp_ns: npt.ArrayLike,
        expected_baseline_m: float,
        coordinate_system: str = WASSGRIDSURFACE_0_11_4_COORDINATE_SYSTEM,
        validity_policy: str,
    ) -> None:
        self.timestamp_ns = np.asarray(timestamp_ns, dtype=np.int64)
        if self.timestamp_ns.ndim != 1:
            raise ValueError("timestamp_ns must be one-dimensional")
        if self.timestamp_ns.size > 1 and np.any(np.diff(self.timestamp_ns) <= 0):
            raise ValueError("timestamp_ns must be strictly increasing")
        if not np.isfinite(expected_baseline_m) or expected_baseline_m <= 0:
            raise ValueError("expected_baseline_m must be explicitly positive")
        if validity_policy != self._VALIDITY_POLICY:
            raise ValueError("unsupported or unknown wassgridsurface validity policy")
        self.expected_baseline_m = float(expected_baseline_m)
        self.coordinate_system = _require_known_label(coordinate_system, "coordinate_system")
        self.validity_policy = validity_policy

    @staticmethod
    def _require_units(variable: object, expected: str, name: str) -> None:
        actual = getattr(variable, "units", None)
        if actual != expected:
            raise ValueError(f"{name} units must be {expected!r}, got {actual!r}")

    def parse(self, source: Path) -> StandardizedGrid3D:
        """Return the verified 0.11.4 product in metres and ``[time,y,x]``."""
        try:
            from netCDF4 import Dataset
        except ImportError as error:
            raise RuntimeError("netCDF4 is required to parse WASS gridded.nc") from error

        path = Path(source)
        if not path.is_file():
            raise FileNotFoundError(path)
        with Dataset(path, "r") as dataset:
            if dataset.file_format != "NETCDF4":
                raise ValueError("wassgridsurface 0.11.4 output must be NETCDF4")
            if not {"count", "X", "Y"}.issubset(dataset.dimensions):
                raise ValueError("required 0.11.4 NetCDF dimensions are missing")
            required = {"scale", "time", "workdir", "X_grid", "Y_grid", "Z", "maskZ"}
            if not required.issubset(dataset.variables):
                raise ValueError("required 0.11.4 NetCDF variables are missing")
            if "meta" not in dataset.groups:
                raise ValueError("required 0.11.4 meta group is missing")

            meta = dataset.groups["meta"]
            if getattr(meta, "info", None) != "Generated with WASS gridder v.0.11.4":
                raise ValueError("NetCDF generator version is not confirmed as 0.11.4")
            if getattr(meta, "generator", None) != "WASS":
                raise ValueError("NetCDF generator is not confirmed as WASS")

            scale_var = dataset.variables["scale"]
            time_var = dataset.variables["time"]
            x_var = dataset.variables["X_grid"]
            y_var = dataset.variables["Y_grid"]
            z_var = dataset.variables["Z"]
            mask_var = dataset.variables["maskZ"]
            if z_var.dimensions != ("count", "X", "Y"):
                raise ValueError("unexpected 0.11.4 Z dimension order")
            if x_var.dimensions != ("X", "Y") or y_var.dimensions != ("X", "Y"):
                raise ValueError("unexpected 0.11.4 coordinate dimensions")
            if mask_var.dimensions != ("X", "Y"):
                raise ValueError("unexpected 0.11.4 maskZ dimensions")
            self._require_units(scale_var, "meter", "scale")
            self._require_units(time_var, "seconds", "time")
            self._require_units(x_var, "millimeter", "X_grid")
            self._require_units(y_var, "millimeter", "Y_grid")
            self._require_units(z_var, "millimeter", "Z")

            stored_baseline = float(np.asarray(scale_var[:]).item())
            meta_baseline = float(getattr(meta, "baseline"))
            if not np.isclose(stored_baseline, self.expected_baseline_m, rtol=0.0, atol=1e-12):
                raise ValueError("NetCDF scale differs from the explicit expected baseline")
            if not np.isclose(meta_baseline, stored_baseline, rtol=0.0, atol=1e-12):
                raise ValueError("NetCDF meta baseline differs from scale")

            time_s = np.asarray(time_var[:], dtype=np.float64)
            if time_s.shape != self.timestamp_ns.shape:
                raise ValueError("NetCDF frame count differs from manifest timestamps")
            expected_time_s = (self.timestamp_ns - self.timestamp_ns[0]).astype(np.float64) * 1e-9
            if not np.allclose(time_s, expected_time_s, rtol=0.0, atol=1e-6):
                raise ValueError("NetCDF time differs from manifest-relative time")

            x_grid_mm = np.asarray(x_var[:], dtype=np.float64)
            y_grid_mm = np.asarray(y_var[:], dtype=np.float64)
            if x_grid_mm.shape != y_grid_mm.shape or x_grid_mm.ndim != 2:
                raise ValueError("X_grid and Y_grid must be same-shape two-dimensional fields")
            x_mm = x_grid_mm[0, :]
            y_mm = y_grid_mm[:, 0]
            if not np.allclose(x_grid_mm, x_mm[np.newaxis, :], rtol=0.0, atol=1e-9):
                raise ValueError("X_grid is not separable along the physical x axis")
            if not np.allclose(y_grid_mm, y_mm[:, np.newaxis], rtol=0.0, atol=1e-9):
                raise ValueError("Y_grid is not separable along the physical y axis")
            if np.any(np.diff(x_mm) <= 0) or np.any(np.diff(y_mm) <= 0):
                raise ValueError("physical x and y coordinates must increase")

            z_stored = np.ma.asarray(z_var[:])
            if np.any(np.ma.getmaskarray(z_stored)):
                raise ValueError("0.11.4 DCT Z contains unexpected NetCDF masked cells")
            z_m = np.asarray(z_stored, dtype=np.float64) * 1e-3
            if z_m.shape != (self.timestamp_ns.size, y_mm.size, x_mm.size):
                raise ValueError("Z shape is inconsistent with verified physical axes")

            mask_stored = np.ma.asarray(mask_var[:])
            if not np.all(np.ma.getmaskarray(mask_stored)):
                raise ValueError("finite-Z DCT policy requires the confirmed unwritten maskZ field")
            valid = np.isfinite(z_m)
            z_m[~valid] = np.nan

        return StandardizedGrid3D(
            x=x_mm * 1e-3,
            y=y_mm * 1e-3,
            z=z_m,
            timestamp_ns=self.timestamp_ns,
            valid_mask=valid,
            coordinate_system=self.coordinate_system,
            unit="m",
        )
