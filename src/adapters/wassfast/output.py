"""Strict WASSfast 1.6.3 CNN output mapping, verified on its official example.

Upstream dimension names are misleading: X_grid varies over array columns and
Y_grid over rows. Workdir resets each batch; only recorded monotonic time is used.
Finite predictions are NOT raw observations and must never be reported as such.
"""
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from adapters.wass.output.model import StandardizedGrid3D


@dataclass(frozen=True)
class WassfastResult:
    """Metric plane-relative estimates with an optional separate observation mask."""

    grid: StandardizedGrid3D
    raw_support_mask: np.ndarray | None
    baseline_m: float
    source_workdir: np.ndarray


def read_cnn_output(source: Path, config_mat: Path) -> WassfastResult:
    """Validate upstream metadata and physical grids without resampling or fitting.

Zinput is used ONLY for its finite support mask. Its upstream units are internally
inconsistent, so its numeric heights are deliberately not exposed here. This
function does not turn an upstream CNN estimate into physical validation.
"""
    from netCDF4 import Dataset
    from scipy.io import loadmat

    config = loadmat(config_mat)
    with Dataset(source, "r") as ds:
        meta = ds.groups["meta"]
        if getattr(meta, "info", "") != "Generated with WASSFast v.1.6.3":
            raise ValueError("Unsupported/unverified upstream version")
        if getattr(meta, "wassfast_mode", "") != "CNN":
            raise ValueError("Only the verified CNN output schema is supported")
        required = {"Z": ("count", "X", "Y"), "X_grid": ("X", "Y"),
                    "Y_grid": ("X", "Y"), "time": ("count",)}
        for name, dimensions in required.items():
            if tuple(ds[name].dimensions) != dimensions:
                raise ValueError(f"Unexpected {name} dimensions")
        for name in ("Z", "X_grid", "Y_grid"):
            if getattr(ds[name], "units", "") != "millimeter":
                raise ValueError(f"Unconfirmed unit for {name}")
        if getattr(ds["time"], "units", "") != "seconds":
            raise ValueError("Unconfirmed time unit")
        if getattr(ds["scale"], "units", "") != "meter":
            raise ValueError("Unconfirmed scale unit")
        baseline = float(ds["scale"][...])
        if not np.isfinite(baseline) or baseline <= 0:
            raise ValueError("Invalid baseline")
        if not np.isclose(baseline, float(config["CAM_BASELINE"].item()), rtol=1e-12, atol=0):
            raise ValueError("Configuration baseline mismatch")
        for key in ("P0plane", "P1plane"):
            # Old official example lacks P1plane; upstream explicitly writes zero.
            expected = config.get(key, np.zeros((4, 4)))
            if not np.allclose(meta[key][:], expected, rtol=1e-10, atol=1e-12):
                raise ValueError(f"Configuration {key} mismatch")
        xg = np.ma.filled(ds["X_grid"][:], np.nan).astype(float) / 1000
        yg = np.ma.filled(ds["Y_grid"][:], np.nan).astype(float) / 1000
        x, y = xg[0, :], yg[:, 0]
        if (not np.allclose(xg, x[None, :], rtol=0, atol=1e-9)
                or not np.allclose(yg, y[:, None], rtol=0, atol=1e-9)
                or not np.all(np.diff(x) > 0) or not np.all(np.diff(y) > 0)):
            raise ValueError("Nonseparable or unexpected physical grid orientation")
        for key, actual in (("xmin", x[0]), ("xmax", x[-1]),
                            ("ymin", y[0]), ("ymax", y[-1])):
            if not np.isclose(actual, config[key].item(), rtol=1e-10, atol=1e-9):
                raise ValueError(f"Configuration grid extent mismatch: {key}")
        z = np.ma.filled(ds["Z"][:], np.nan).astype(float) / 1000
        valid = np.isfinite(z)
        z[~valid] = np.nan
        seconds = np.ma.filled(ds["time"][:], np.nan).astype(float)
        if not np.isfinite(seconds).all() or np.any(seconds < 0):
            raise ValueError("Invalid relative timestamps")
        timestamp_ns = np.rint(seconds * 1e9).astype(np.int64)
        raw = None
        if "Zinput" in ds.variables:
            observed = ds["Zinput"][:]
            if not np.ma.getmaskarray(observed).all():
                if observed.shape != z.shape:
                    raise ValueError("Zinput shape mismatch")
                raw = np.isfinite(np.ma.filled(observed, np.nan))
        workdir = np.asarray(ds["workdir"][:])
    grid = StandardizedGrid3D(x, y, z, timestamp_ns, valid,
                              "wassfast_official_config_plane_aligned", "m")
    return WassfastResult(grid, raw, baseline, workdir)
