"""Water-plane extraction and pointwise height calculation after WASS."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from validation.diagnostics import fit_plane_orthogonal


@dataclass(frozen=True)
class SurfaceResult:
    """Plane, residuals and explicitly thresholded water-point support."""

    normal: np.ndarray
    offset_m: float
    residual_m: np.ndarray
    water_mask: np.ndarray
    rms_m: float
    mean_m: float
    max_absolute_m: float


def extract_planar_surface(points_xyz_m: np.ndarray, *, distance_threshold_m: float) -> SurfaceResult:
    """Fit one orthogonal plane and classify points by an explicit distance gate."""
    points = np.asarray(points_xyz_m, dtype=np.float64)
    fit = fit_plane_orthogonal(points)
    residual = points @ fit.normal + fit.offset
    mask = np.abs(residual) <= distance_threshold_m
    return SurfaceResult(
        normal=fit.normal.copy(), offset_m=fit.offset, residual_m=residual,
        water_mask=mask, rms_m=fit.residual_rmse,
        mean_m=float(residual.mean()), max_absolute_m=fit.residual_max_abs,
    )
