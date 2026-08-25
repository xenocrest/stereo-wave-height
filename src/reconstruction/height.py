"""Metric point-to-reference-plane water height computation."""

from __future__ import annotations

import numpy as np


def height_from_plane(
    points_xyz_m: np.ndarray,
    plane_normal: np.ndarray,
    plane_offset_m: float,
) -> np.ndarray:
    """Return signed orthogonal heights for ``n dot P + D = 0``.

    The result is ``(n dot P + D) / ||n||`` in metres.  It is not camera Z.
    """
    points = np.asarray(points_xyz_m, dtype=np.float64)
    normal = np.asarray(plane_normal, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 3 or points.shape[0] == 0:
        raise ValueError("points_xyz_m must have non-empty shape [point,3]")
    if normal.shape != (3,) or not np.all(np.isfinite(normal)):
        raise ValueError("plane_normal must be a finite 3-vector")
    if not np.all(np.isfinite(points)) or not np.isfinite(plane_offset_m):
        raise ValueError("points and plane offset must be finite")
    norm = float(np.linalg.norm(normal))
    if norm == 0:
        raise ValueError("plane_normal must be non-zero")
    return (points @ normal + float(plane_offset_m)) / norm
