"""Independent ideal-geometry checks for the simulation stereo rig."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt


FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True)
class ClosureMetrics:
    """Cartesian and Euclidean reconstruction errors, all in metres."""

    x_rmse_m: float
    y_rmse_m: float
    z_rmse_m: float
    euclidean_mean_m: float
    euclidean_rmse_m: float
    euclidean_max_m: float
    point_count: int


def theoretical_pinhole_projection(
    points_world_m: npt.ArrayLike,
    *,
    intrinsic_matrix: npt.ArrayLike,
    rotation_world_to_camera: npt.ArrayLike,
    camera_center_world_m: npt.ArrayLike,
) -> tuple[FloatArray, FloatArray]:
    """Project world points by ``Pc=R(Pw-C)`` and ideal pinhole equations."""
    points = np.asarray(points_world_m, dtype=np.float64)
    k = np.asarray(intrinsic_matrix, dtype=np.float64)
    rotation = np.asarray(rotation_world_to_camera, dtype=np.float64)
    center = np.asarray(camera_center_world_m, dtype=np.float64)
    if points.ndim < 1 or points.shape[-1] != 3 or not np.all(np.isfinite(points)):
        raise ValueError("points_world_m must be finite with shape [...,3]")
    if k.shape != (3, 3) or rotation.shape != (3, 3) or center.shape != (3,):
        raise ValueError("K, R, and C must have shapes [3,3], [3,3], and [3]")
    camera = (rotation @ (points - center).reshape(-1, 3).T).T.reshape(points.shape)
    depth = camera[..., 2]
    if np.any(depth <= 0):
        raise ValueError("all points must be in front of the camera")
    homogeneous = (k @ camera.reshape(-1, 3).T).T.reshape(points.shape)
    pixels = homogeneous[..., :2] / homogeneous[..., 2, np.newaxis]
    return pixels, depth


def triangulate_parallel_downward_stereo(
    left_pixels: npt.ArrayLike,
    right_pixels: npt.ArrayLike,
    *,
    fx_px: float,
    fy_px: float,
    cx_px: float,
    cy_px: float,
    baseline_m: float,
    working_distance_m: float,
) -> FloatArray:
    """Triangulate the project's parallel downward-looking ideal stereo pair.

    This validation implementation uses disparity algebra rather than the
    production camera projection or backprojection methods. Inputs are pixels;
    output is ``[...,Xw,Yw,Zw]`` in metres.
    """
    left = np.asarray(left_pixels, dtype=np.float64)
    right = np.asarray(right_pixels, dtype=np.float64)
    scalars = np.asarray(
        [fx_px, fy_px, cx_px, cy_px, baseline_m, working_distance_m], dtype=np.float64
    )
    if left.shape != right.shape or left.ndim < 1 or left.shape[-1] != 2:
        raise ValueError("left and right pixels must have matching shape [...,2]")
    if not np.all(np.isfinite(left)) or not np.all(np.isfinite(right)) or not np.all(np.isfinite(scalars)):
        raise ValueError("pixels and parameters must be finite")
    if fx_px <= 0 or fy_px <= 0 or baseline_m <= 0 or working_distance_m <= 0:
        raise ValueError("focal lengths, baseline, and working distance must be positive")
    disparity = left[..., 0] - right[..., 0]
    if np.any(disparity <= 0):
        raise ValueError("parallel stereo disparity must be positive")
    depth = fx_px * baseline_m / disparity
    x_world = (left[..., 0] - cx_px) * depth / fx_px - baseline_m / 2.0
    y_world = -(left[..., 1] - cy_px) * depth / fy_px
    z_world = working_distance_m - depth
    return np.stack((x_world, y_world, z_world), axis=-1)


def closure_metrics(expected_world_m: npt.ArrayLike, calculated_world_m: npt.ArrayLike) -> ClosureMetrics:
    """Summarize pointwise Cartesian closure in metres."""
    expected = np.asarray(expected_world_m, dtype=np.float64)
    calculated = np.asarray(calculated_world_m, dtype=np.float64)
    if expected.shape != calculated.shape or expected.ndim < 2 or expected.shape[-1] != 3:
        raise ValueError("point arrays must have identical shape [...,3]")
    if not np.all(np.isfinite(expected)) or not np.all(np.isfinite(calculated)):
        raise ValueError("point arrays must be finite")
    error = (calculated - expected).reshape(-1, 3)
    distance = np.linalg.norm(error, axis=1)
    return ClosureMetrics(
        x_rmse_m=float(np.sqrt(np.mean(error[:, 0] ** 2))),
        y_rmse_m=float(np.sqrt(np.mean(error[:, 1] ** 2))),
        z_rmse_m=float(np.sqrt(np.mean(error[:, 2] ** 2))),
        euclidean_mean_m=float(np.mean(distance)),
        euclidean_rmse_m=float(np.sqrt(np.mean(distance ** 2))),
        euclidean_max_m=float(np.max(distance)),
        point_count=int(error.shape[0]),
    )
