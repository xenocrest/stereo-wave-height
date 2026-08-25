"""Traceable correspondence between WASS rectified pixels and metric XYZ.

WASS final point clouds do not store source pixel indices.  The mapping is
recovered geometrically with the per-workdir WASS projection matrix, never by
point order assumptions, ruler data, or a parallel stereo implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class PixelXyzCorrespondence:
    """One projected rectified pixel coordinate per metric 3-D point."""

    u_px: np.ndarray
    v_px: np.ndarray
    xyz_m: np.ndarray
    pixel_coordinate_system: str

    def __post_init__(self) -> None:
        u = np.asarray(self.u_px, dtype=np.float64)
        v = np.asarray(self.v_px, dtype=np.float64)
        xyz = np.asarray(self.xyz_m, dtype=np.float64)
        if u.ndim != 1 or u.shape != v.shape or xyz.shape != (u.size, 3) or u.size == 0:
            raise ValueError("u, v and xyz must contain the same non-empty point count")
        if not np.all(np.isfinite(u)) or not np.all(np.isfinite(v)) or not np.all(np.isfinite(xyz)):
            raise ValueError("pixel and XYZ coordinates must be finite")
        if not self.pixel_coordinate_system:
            raise ValueError("pixel_coordinate_system must be explicit")
        object.__setattr__(self, "u_px", u.copy())
        object.__setattr__(self, "v_px", v.copy())
        object.__setattr__(self, "xyz_m", xyz.copy())


def load_projection_matrix(path: str | Path) -> np.ndarray:
    """Load a finite WASS 3x4 camera projection matrix."""
    matrix = np.asarray(np.loadtxt(Path(path)), dtype=np.float64)
    if matrix.shape != (3, 4) or not np.all(np.isfinite(matrix)):
        raise ValueError("WASS projection matrix must be finite with shape [3,4]")
    return matrix


def project_wass_points(
    points_camera_unscaled: np.ndarray,
    points_xyz_m: np.ndarray,
    projection_3x4: np.ndarray,
    *,
    pixel_coordinate_system: str,
) -> PixelXyzCorrespondence:
    """Project unscaled WASS camera points and pair them with metric XYZ.

    The projective translation in ``P`` shares WASS's original camera unit;
    therefore projection uses the unscaled points.  ``points_xyz_m`` supplies
    the corresponding metric result and must retain the same point ordering.
    """
    camera = np.asarray(points_camera_unscaled, dtype=np.float64)
    metric = np.asarray(points_xyz_m, dtype=np.float64)
    projection = np.asarray(projection_3x4, dtype=np.float64)
    if camera.ndim != 2 or camera.shape[1] != 3 or metric.shape != camera.shape:
        raise ValueError("unscaled and metric points must have shape [point,3]")
    if projection.shape != (3, 4) or not np.all(np.isfinite(projection)):
        raise ValueError("projection_3x4 must be finite with shape [3,4]")
    homogeneous = np.column_stack((camera, np.ones(camera.shape[0]))) @ projection.T
    denominator = homogeneous[:, 2]
    if np.any(~np.isfinite(homogeneous)) or np.any(np.abs(denominator) <= np.finfo(float).eps):
        raise ValueError("projection produced a point at infinity or non-finite value")
    return PixelXyzCorrespondence(
        homogeneous[:, 0] / denominator,
        homogeneous[:, 1] / denominator,
        metric,
        pixel_coordinate_system,
    )


def query_xyz(
    correspondence: PixelXyzCorrespondence,
    u_px: float,
    v_px: float,
    *,
    maximum_distance_px: float,
) -> np.ndarray:
    """Return nearest observed XYZ within an explicit pixel-radius gate."""
    if not np.isfinite(u_px) or not np.isfinite(v_px):
        raise ValueError("query pixel must be finite")
    if not np.isfinite(maximum_distance_px) or maximum_distance_px < 0:
        raise ValueError("maximum_distance_px must be finite and non-negative")
    squared = (correspondence.u_px - u_px) ** 2 + (correspondence.v_px - v_px) ** 2
    index = int(np.argmin(squared))
    if squared[index] > maximum_distance_px**2:
        raise LookupError("no reconstructed observation lies within the requested pixel radius")
    return correspondence.xyz_m[index].copy()


def save_pixel_xyz(path: str | Path, correspondence: PixelXyzCorrespondence) -> Path:
    """Save a compact mapping without rounding pixel or metric coordinates."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        destination,
        u_px=correspondence.u_px,
        v_px=correspondence.v_px,
        xyz_m=correspondence.xyz_m,
        pixel_coordinate_system=np.asarray(correspondence.pixel_coordinate_system),
    )
    return destination
