"""Read-only diagnostics for locating Case 1 height-error sources.

These functions measure existing truth, point clouds, support and grids.  They
do not filter, interpolate, smooth, or alter the formal acceptance result.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt


FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]


@dataclass(frozen=True)
class PlaneFit:
    """Orthogonal least-squares plane in an explicitly supplied coordinate system."""

    normal: FloatArray
    offset: float
    centroid: FloatArray
    residual_rmse: float
    residual_max_abs: float
    point_count: int

    @property
    def z_at_origin(self) -> float:
        """Return plane Z at X=Y=0; fail if the plane is vertical."""
        if abs(self.normal[2]) <= np.finfo(float).eps:
            raise ValueError("plane has no finite Z intercept")
        return float(-self.offset / self.normal[2])


@dataclass(frozen=True)
class SupportStatistics:
    """Raw point counts assigned to the nearest regular-grid cell."""

    counts: IntArray
    total_input_points: int
    in_grid_points: int

    @property
    def supported_cell_ratio(self) -> float:
        return float(np.count_nonzero(self.counts) / self.counts.size)


@dataclass(frozen=True)
class SpatialErrorStatistics:
    """Descriptive spatial statistics; these never replace acceptance metrics."""

    median_error: float
    absolute_percentiles: dict[int, float]
    maximum_absolute_error: float
    maximum_index: tuple[int, int, int]
    center_rmse: float
    boundary_rmse: float


def constant_truth_difference(static: npt.ArrayLike, raised: npt.ArrayLike) -> FloatArray:
    """Return raised-static truth after exact shape and finite-value checks."""
    static_array = np.asarray(static, dtype=np.float64)
    raised_array = np.asarray(raised, dtype=np.float64)
    if static_array.shape != raised_array.shape or static_array.size == 0:
        raise ValueError("truth arrays must have the same non-empty shape")
    difference = raised_array - static_array
    if not np.all(np.isfinite(difference)):
        raise ValueError("truth difference must be finite")
    return difference


def fit_plane_orthogonal(points_xyz: npt.ArrayLike) -> PlaneFit:
    """Fit ``n dot X + c = 0`` by orthogonal least squares in input units."""
    points = np.asarray(points_xyz, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 3 or points.shape[0] < 3:
        raise ValueError("points_xyz must have shape [point,3] with at least 3 points")
    if not np.all(np.isfinite(points)):
        raise ValueError("points_xyz must be finite")
    centroid = np.mean(points, axis=0)
    centered = points - centroid
    covariance = centered.T @ centered / points.shape[0]
    _, eigenvectors = np.linalg.eigh(covariance)
    normal = eigenvectors[:, 0]
    if normal[2] < 0:
        normal = -normal
    offset = -float(normal @ centroid)
    residual = points @ normal + offset
    return PlaneFit(
        normal=normal,
        offset=offset,
        centroid=centroid,
        residual_rmse=float(np.sqrt(np.mean(residual * residual))),
        residual_max_abs=float(np.max(np.abs(residual))),
        point_count=int(points.shape[0]),
    )


def _grid_edges(coordinates: npt.ArrayLike, name: str) -> FloatArray:
    values = np.asarray(coordinates, dtype=np.float64)
    if values.ndim != 1 or values.size < 2 or not np.all(np.isfinite(values)):
        raise ValueError(f"{name} must be a finite one-dimensional grid")
    differences = np.diff(values)
    if np.any(differences <= 0) or not np.allclose(differences, differences[0]):
        raise ValueError(f"{name} must be strictly increasing and regularly spaced")
    half = differences[0] / 2.0
    return np.concatenate(([values[0] - half], values + half))


def raw_point_support(points_xy: npt.ArrayLike, x: npt.ArrayLike, y: npt.ArrayLike) -> SupportStatistics:
    """Count raw points per nearest cell without estimating any surface value."""
    points = np.asarray(points_xy, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 2 or not np.all(np.isfinite(points)):
        raise ValueError("points_xy must be finite with shape [point,2]")
    x_edges = _grid_edges(x, "x")
    y_edges = _grid_edges(y, "y")
    counts, _, _ = np.histogram2d(points[:, 1], points[:, 0], bins=(y_edges, x_edges))
    counts = counts.astype(np.int64)
    return SupportStatistics(counts, int(points.shape[0]), int(np.sum(counts)))


def verify_grid_alignment(
    x_a: npt.ArrayLike, y_a: npt.ArrayLike, x_b: npt.ArrayLike, y_b: npt.ArrayLike
) -> None:
    """Require bit-for-bit equal physical grid coordinates."""
    if not np.array_equal(np.asarray(x_a), np.asarray(x_b)):
        raise ValueError("x grids differ")
    if not np.array_equal(np.asarray(y_a), np.asarray(y_b)):
        raise ValueError("y grids differ")


def spatial_error_statistics(error: npt.ArrayLike, valid_mask: npt.ArrayLike) -> SpatialErrorStatistics:
    """Describe full-domain errors and a fixed 10% outer boundary ring."""
    values = np.asarray(error, dtype=np.float64)
    valid = np.asarray(valid_mask, dtype=bool)
    if values.shape != valid.shape or values.ndim != 3:
        raise ValueError("error and valid_mask must share shape [time,y,x]")
    selected = valid & np.isfinite(values)
    if not np.any(selected):
        raise ValueError("no valid finite error values")
    absolute = np.abs(values[selected])
    flat_max = int(np.nanargmax(np.where(selected, np.abs(values), np.nan)))
    maximum_index = tuple(int(index) for index in np.unravel_index(flat_max, values.shape))
    border = max(1, int(np.ceil(0.10 * min(values.shape[1:]))))
    boundary_2d = np.ones(values.shape[1:], dtype=bool)
    boundary_2d[border:-border, border:-border] = False
    boundary = np.broadcast_to(boundary_2d, values.shape) & selected
    center = (~np.broadcast_to(boundary_2d, values.shape)) & selected
    if not np.any(center) or not np.any(boundary):
        raise ValueError("grid is too small for center/boundary diagnostics")
    return SpatialErrorStatistics(
        median_error=float(np.median(values[selected])),
        absolute_percentiles={
            percentile: float(np.percentile(absolute, percentile))
            for percentile in (50, 90, 95, 99)
        },
        maximum_absolute_error=float(absolute.max()),
        maximum_index=maximum_index,
        center_rmse=float(np.sqrt(np.mean(values[center] ** 2))),
        boundary_rmse=float(np.sqrt(np.mean(values[boundary] ** 2))),
    )
