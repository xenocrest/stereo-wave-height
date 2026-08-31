"""Deterministic smooth global surface fitted only from observed WASS X/Y/H."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
from scipy.interpolate import RBFInterpolator


@dataclass(frozen=True)
class GlobalFitDiagnostics:
    raw_count: int
    finite_count: int
    filtered_count: int
    excluded_count: int
    excluded_percent: float
    control_count: int
    robust_median_m: float
    robust_mad_m: float
    noise_scale_m: float
    smoothing_s: float

    def to_dict(self) -> dict[str, int | float]:
        return asdict(self)


class GlobalWaterSurface:
    """A thin-plate smoothing RBF H=F(X,Y), evaluated in physical metres."""

    def __init__(self, interpolator: RBFInterpolator, diagnostics: GlobalFitDiagnostics,
                 origin_xy: np.ndarray, scale_xy: np.ndarray,
                 height_origin: float, height_scale: float) -> None:
        self._interpolator = interpolator
        self.diagnostics = diagnostics
        self.origin_xy = np.asarray(origin_xy, dtype=np.float64)
        self.scale_xy = np.asarray(scale_xy, dtype=np.float64)
        self.height_origin = float(height_origin)
        self.height_scale = float(height_scale)

    def evaluate(self, xy_m: np.ndarray) -> np.ndarray:
        xy = np.asarray(xy_m, dtype=np.float64)
        if xy.ndim != 2 or xy.shape[1] != 2:
            raise ValueError("global surface queries must have shape (N,2)")
        normalized = (xy - self.origin_xy) / self.scale_xy
        return self.height_origin + self.height_scale * np.asarray(self._interpolator(normalized)).reshape(-1)


def _robust_finite_points(
    xy_m: np.ndarray, height_m: np.ndarray, *, mad_multiplier: float,
) -> tuple[np.ndarray, np.ndarray, dict[str, float | int]]:
    xy = np.asarray(xy_m, dtype=np.float64)
    height = np.asarray(height_m, dtype=np.float64)
    if xy.ndim != 2 or xy.shape[1] != 2 or height.shape != (xy.shape[0],):
        raise ValueError("global surface X/Y/H shape mismatch")
    finite = np.all(np.isfinite(xy), axis=1) & np.isfinite(height)
    finite_h = height[finite]
    if finite_h.size < 16:
        raise ValueError("global surface requires at least 16 finite observed points")
    median = float(np.median(finite_h))
    mad = float(np.median(np.abs(finite_h - median)))
    # A zero MAD means the observed surface is exactly constant; keep all finite data.
    keep_h = np.ones(finite_h.size, dtype=bool) if mad == 0 else np.abs(finite_h - median) <= mad_multiplier * mad
    indices = np.flatnonzero(finite)[keep_h]
    if indices.size < 16:
        raise ValueError("robust global surface filter retained too few observed points")
    return xy[indices], height[indices], {
        "raw_count": int(height.size), "finite_count": int(finite_h.size),
        "median_m": median, "mad_m": mad, "filtered_count": int(indices.size),
    }


def _spatial_bin_controls(
    xy_m: np.ndarray, height_m: np.ndarray, *, target_count: int,
) -> tuple[np.ndarray, np.ndarray, float]:
    if target_count < 16:
        raise ValueError("global control target must be at least 16")
    extent = np.ptp(xy_m, axis=0)
    if np.any(extent <= 0):
        raise ValueError("global surface observations do not span two physical axes")
    aspect = extent[0] / extent[1]
    nx = max(4, int(round(np.sqrt(target_count * aspect))))
    ny = max(4, int(np.ceil(target_count / nx)))
    normalized = (xy_m - xy_m.min(axis=0)) / extent
    ix = np.minimum((normalized[:, 0] * nx).astype(np.int64), nx - 1)
    iy = np.minimum((normalized[:, 1] * ny).astype(np.int64), ny - 1)
    cell = iy * nx + ix
    order = np.argsort(cell, kind="stable")
    sorted_cell = cell[order]
    starts = np.r_[0, np.flatnonzero(np.diff(sorted_cell)) + 1]
    ends = np.r_[starts[1:], order.size]
    controls_xy = np.empty((starts.size, 2), dtype=np.float64)
    controls_h = np.empty(starts.size, dtype=np.float64)
    residuals: list[np.ndarray] = []
    for out_index, (start, end) in enumerate(zip(starts, ends)):
        members = order[start:end]
        controls_xy[out_index] = np.median(xy_m[members], axis=0)
        controls_h[out_index] = np.median(height_m[members])
        residuals.append(np.abs(height_m[members] - controls_h[out_index]))
    local_mad = float(np.median(np.concatenate(residuals)))
    return controls_xy, controls_h, local_mad


def fit_global_surface(
    xy_m: np.ndarray,
    height_m: np.ndarray,
    *,
    target_control_points: int = 2500,
    mad_multiplier: float = 8.0,
    minimum_noise_scale_m: float = 1e-3,
) -> GlobalWaterSurface:
    """Fit one deterministic robust thin-plate RBF from observed WASS points."""
    filtered_xy, filtered_h, robust = _robust_finite_points(
        xy_m, height_m, mad_multiplier=mad_multiplier,
    )
    controls_xy, controls_h, local_mad = _spatial_bin_controls(
        filtered_xy, filtered_h, target_count=target_control_points,
    )
    if controls_h.size < 16:
        raise ValueError("spatial binning produced too few global controls")
    # 1.4826*MAD estimates the standard deviation of local WASS scatter.  The
    # 1 mm lower bound comes from the committed frozen local hold-out RMSE
    # (0.43--1.06 mm), preventing an unjustified near-interpolating spline.
    noise_scale = max(1.4826 * local_mad, minimum_noise_scale_m)
    origin_xy = filtered_xy.min(axis=0); scale_xy = np.ptp(filtered_xy, axis=0)
    height_origin = float(np.median(controls_h))
    height_scale = max(float(1.4826 * np.median(np.abs(controls_h - height_origin))), noise_scale)
    normalized_xy = (controls_xy - origin_xy) / scale_xy
    normalized_h = (controls_h - height_origin) / height_scale
    smoothing = float((noise_scale / height_scale) ** 2)
    interpolator = RBFInterpolator(
        normalized_xy, normalized_h, kernel="thin_plate_spline",
        smoothing=smoothing, neighbors=min(32, controls_h.size), degree=1,
    )
    excluded = int(robust["finite_count"]) - int(robust["filtered_count"])
    diagnostics = GlobalFitDiagnostics(
        raw_count=int(robust["raw_count"]), finite_count=int(robust["finite_count"]),
        filtered_count=int(robust["filtered_count"]), excluded_count=excluded,
        excluded_percent=100.0 * excluded / int(robust["finite_count"]),
        control_count=int(controls_h.size), robust_median_m=float(robust["median_m"]),
        robust_mad_m=float(robust["mad_m"]), noise_scale_m=noise_scale,
        smoothing_s=smoothing,
    )
    return GlobalWaterSurface(interpolator, diagnostics, origin_xy, scale_xy, height_origin, height_scale)


def global_holdout(
    xy_m: np.ndarray,
    height_m: np.ndarray,
    *,
    maximum_test_points: int = 500,
    seed: int = 20260831,
    target_control_points: int = 2500,
) -> dict[str, object]:
    """Deterministically exclude observed truth and evaluate the global model."""
    xy = np.asarray(xy_m, dtype=np.float64)
    height = np.asarray(height_m, dtype=np.float64)
    finite = np.all(np.isfinite(xy), axis=1) & np.isfinite(height)
    indices = np.flatnonzero(finite)
    rng = np.random.default_rng(seed)
    held = np.sort(rng.choice(indices, size=min(maximum_test_points, indices.size // 10), replace=False))
    training = finite.copy(); training[held] = False
    model = fit_global_surface(xy[training], height[training], target_control_points=target_control_points)
    predicted = model.evaluate(xy[held])
    valid = np.isfinite(predicted)
    error = predicted[valid] - height[held][valid]
    absolute = np.abs(error)
    metrics = {
        "test_point_count": int(held.size), "supported_prediction_count": int(valid.sum()),
        "coverage_percent": 100.0 * float(valid.mean()),
        "mae_m": float(np.mean(absolute)), "rmse_m": float(np.sqrt(np.mean(error * error))),
        "median_absolute_error_m": float(np.median(absolute)),
        "p95_absolute_error_m": float(np.percentile(absolute, 95)),
        "maximum_absolute_error_m": float(np.max(absolute)),
    } if np.any(valid) else {
        "test_point_count": int(held.size), "supported_prediction_count": 0,
        "coverage_percent": 0.0, "mae_m": None, "rmse_m": None,
        "median_absolute_error_m": None, "p95_absolute_error_m": None,
        "maximum_absolute_error_m": None,
    }
    return {**metrics, "seed": seed, "fit": model.diagnostics.to_dict(),
            "holdout_indices": held.tolist()}
