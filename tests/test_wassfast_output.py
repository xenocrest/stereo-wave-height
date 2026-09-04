"""Small schema tests; no upstream model training or reconstruction."""
import numpy as np
import pytest
from scipy.io import savemat
from netCDF4 import Dataset

from adapters.wassfast.output import read_cnn_output


def fixture_files(tmp_path):
    nc, mat = tmp_path / "output.nc", tmp_path / "config.mat"
    savemat(mat, {"CAM_BASELINE": 0.2, "P0plane": np.eye(4), "P1plane": np.eye(4),
                  "xmin": 1., "xmax": 3., "ymin": 4., "ymax": 5.})
    with Dataset(nc, "w") as ds:
        for name, size in (("count", 2), ("X", 2), ("Y", 3), ("V4", 4)):
            ds.createDimension(name, size)
        meta = ds.createGroup("meta")
        meta.info = "Generated with WASSFast v.1.6.3"
        meta.wassfast_mode = "CNN"
        for key in ("P0plane", "P1plane"):
            meta.createVariable(key, "f8", ("V4", "V4"))[:] = np.eye(4)
        for key, dims, unit, data in (
            ("Z", ("count", "X", "Y"), "millimeter", np.ones((2,2,3))*10),
            ("X_grid", ("X", "Y"), "millimeter", [[1000,2000,3000]]*2),
            ("Y_grid", ("X", "Y"), "millimeter", [[4000]*3,[5000]*3]),
            ("time", ("count",), "seconds", [0,0.1]),
            ("workdir", ("count",), "workdir", [0,0]),
            ("scale", (), "meter", 0.2)):
            v = ds.createVariable(key, "f8", dims)
            v.units = unit
            v[:] = data
        ds.createVariable("Zinput", "f4", ("count", "X", "Y"))
    return nc, mat


def test_physical_grid_not_dimension_names_and_support_unknown(tmp_path):
    nc, mat = fixture_files(tmp_path)
    r = read_cnn_output(nc, mat)
    assert r.grid.z.shape == (2,2,3)
    np.testing.assert_allclose(r.grid.z, .01)
    np.testing.assert_allclose(r.grid.x, [1,2,3])
    assert r.raw_support_mask is None
    assert r.grid.timestamp_ns.tolist() == [0,100000000]


def test_unknown_units_fail(tmp_path):
    nc, mat = fixture_files(tmp_path)
    with Dataset(nc, "a") as ds:
        ds["Z"].units = "UNKNOWN"
    with pytest.raises(ValueError, match="unit"):
        read_cnn_output(nc, mat)


def test_transposed_physical_axes_fail(tmp_path):
    nc, mat = fixture_files(tmp_path)
    with Dataset(nc, "a") as ds:
        ds["X_grid"][:] = [[1000]*3, [2000]*3]
    with pytest.raises(ValueError, match="grid orientation"):
        read_cnn_output(nc, mat)
