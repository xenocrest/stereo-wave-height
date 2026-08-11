"""Tests for the schema-confirmed wassgridsurface 0.11.4 NetCDF adapter."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import numpy as np

from adapters.wass.output.netcdf import WassGridSurface0114Parser


class WassGridSurface0114Tests(unittest.TestCase):
    """Exercise only the confirmed 0.11.4 schema, not WASS reconstruction."""

    def _write_fixture(self, path: Path, *, z_units: str = "millimeter") -> None:
        try:
            from netCDF4 import Dataset
        except ImportError as error:  # pragma: no cover
            self.skipTest(f"netCDF4 unavailable: {error}")
        with Dataset(path, "w", format="NETCDF4") as dataset:
            dataset.createDimension("X", 2)
            dataset.createDimension("Y", 2)
            dataset.createDimension("count", None)
            meta = dataset.createGroup("meta")
            meta.info = "Generated with WASS gridder v.0.11.4"
            meta.generator = "WASS"
            meta.baseline = 0.2
            scale = dataset.createVariable("scale", "f8")
            scale.units = "meter"
            scale[:] = 0.2
            time = dataset.createVariable("time", "f4", ("count",))
            time.units = "seconds"
            time[:] = [0.0, 0.2]
            dataset.createVariable("workdir", "u8", ("count",))[:] = [0, 1]
            x_grid = dataset.createVariable("X_grid", "f8", ("X", "Y"))
            x_grid.units = "millimeter"
            x_grid[:] = np.array([[-5.0, 5.0], [-5.0, 5.0]], dtype=np.float64)
            y_grid = dataset.createVariable("Y_grid", "f8", ("X", "Y"))
            y_grid.units = "millimeter"
            y_grid[:] = np.array([[-5.0, -5.0], [5.0, 5.0]], dtype=np.float64)
            z = dataset.createVariable("Z", "f4", ("count", "X", "Y"))
            z.units = z_units
            z[:] = np.array(
                [[[1.0, 2.0], [3.0, 4.0]], [[2.0, 3.0], [4.0, 5.0]]],
                dtype=np.float32,
            )
            dataset.createVariable("maskZ", "f4", ("X", "Y"))

    def _parser(self) -> WassGridSurface0114Parser:
        return WassGridSurface0114Parser(
            timestamp_ns=[0, 200_000_000],
            expected_baseline_m=0.2,
            validity_policy="finite_z_for_dct_0_11_4",
        )

    def test_confirmed_schema_maps_to_time_y_x_metres(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            source = Path(directory) / "gridded.nc"
            self._write_fixture(source)
            result = self._parser().parse(source)
        np.testing.assert_allclose(result.x, [-0.005, 0.005])
        np.testing.assert_allclose(result.y, [-0.005, 0.005])
        np.testing.assert_allclose(result.z[0], [[0.001, 0.002], [0.003, 0.004]])
        self.assertEqual(result.z.shape, (2, 2, 2))
        self.assertTrue(np.all(result.valid_mask))

    def test_unknown_validity_policy_fails(self) -> None:
        with self.assertRaises(ValueError):
            WassGridSurface0114Parser(
                timestamp_ns=[0], expected_baseline_m=0.2, validity_policy="UNKNOWN"
            )

    def test_unconfirmed_units_fail(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            source = Path(directory) / "gridded.nc"
            self._write_fixture(source, z_units="UNKNOWN")
            with self.assertRaises(ValueError):
                self._parser().parse(source)

    def test_baseline_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            source = Path(directory) / "gridded.nc"
            self._write_fixture(source)
            parser = WassGridSurface0114Parser(
                timestamp_ns=[0, 200_000_000],
                expected_baseline_m=0.3,
                validity_policy="finite_z_for_dct_0_11_4",
            )
            with self.assertRaises(ValueError):
                parser.parse(source)


if __name__ == "__main__":
    unittest.main()
