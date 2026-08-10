"""Ideal pinhole projection with explicit world/camera coordinate metadata."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from .config import NominalIntrinsics


FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True)
class VirtualPinholeCamera:
    """A simulation-only pinhole camera with known pose and nominal intrinsics."""

    camera_id: str
    intrinsics: NominalIntrinsics
    center_world_m: FloatArray
    rotation_world_to_camera: FloatArray
    world_coordinate_system: str = "world_water_surface"
    world_unit: str = "m"

    def __post_init__(self) -> None:
        center = np.asarray(self.center_world_m, dtype=np.float64)
        rotation = np.asarray(self.rotation_world_to_camera, dtype=np.float64)
        if center.shape != (3,) or rotation.shape != (3, 3):
            raise ValueError("camera center and rotation must have shapes [3] and [3,3]")
        if not np.all(np.isfinite(center)) or not np.all(np.isfinite(rotation)):
            raise ValueError("camera pose must be finite")
        if not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-12, rtol=0.0):
            raise ValueError("camera rotation must be orthonormal")
        if not np.isclose(np.linalg.det(rotation), 1.0, atol=1e-12, rtol=0.0):
            raise ValueError("camera rotation must be a proper rotation")
        object.__setattr__(self, "center_world_m", center.copy())
        object.__setattr__(self, "rotation_world_to_camera", rotation.copy())

    @property
    def projection_matrix(self) -> FloatArray:
        """Return ``K [R | -R C]`` for world points expressed in metres."""
        translation = -self.rotation_world_to_camera @ self.center_world_m
        extrinsic = np.column_stack((self.rotation_world_to_camera, translation))
        return self.intrinsics.matrix @ extrinsic

    def project(
        self,
        points_world_m: npt.ArrayLike,
        *,
        coordinate_system: str,
        unit: str,
    ) -> tuple[FloatArray, FloatArray]:
        """Project ``[...,3]`` world points to pixels and return camera depth in m."""
        if coordinate_system != self.world_coordinate_system:
            raise ValueError("world coordinate system mismatch")
        if unit != self.world_unit:
            raise ValueError("world unit mismatch")
        points = np.asarray(points_world_m, dtype=np.float64)
        if points.ndim < 1 or points.shape[-1] != 3 or not np.all(np.isfinite(points)):
            raise ValueError("points_world_m must be finite with shape [...,3]")
        camera = (points - self.center_world_m) @ self.rotation_world_to_camera.T
        depth = camera[..., 2]
        if np.any(depth <= 0):
            raise ValueError("all projected points must lie in front of the camera")
        u = self.intrinsics.fx_px * camera[..., 0] / depth + self.intrinsics.cx_px
        v = self.intrinsics.fy_px * camera[..., 1] / depth + self.intrinsics.cy_px
        return np.stack((u, v), axis=-1), depth

    def backproject_with_depth(
        self,
        pixels: npt.ArrayLike,
        depth_m: npt.ArrayLike,
        *,
        coordinate_system: str,
        unit: str,
    ) -> FloatArray:
        """Backproject pixels using supplied true depth; this is not stereo reconstruction."""
        if coordinate_system != self.world_coordinate_system or unit != self.world_unit:
            raise ValueError("backprojection metadata mismatch")
        pixel_array = np.asarray(pixels, dtype=np.float64)
        depth = np.asarray(depth_m, dtype=np.float64)
        if pixel_array.ndim < 1 or pixel_array.shape[-1] != 2:
            raise ValueError("pixels must have shape [...,2]")
        if depth.shape != pixel_array.shape[:-1]:
            raise ValueError("depth shape must match pixel leading dimensions")
        if np.any(~np.isfinite(pixel_array)) or np.any(~np.isfinite(depth)) or np.any(depth <= 0):
            raise ValueError("pixels and positive depth must be finite")
        x_c = (pixel_array[..., 0] - self.intrinsics.cx_px) * depth / self.intrinsics.fx_px
        y_c = (pixel_array[..., 1] - self.intrinsics.cy_px) * depth / self.intrinsics.fy_px
        camera = np.stack((x_c, y_c, depth), axis=-1)
        return camera @ self.rotation_world_to_camera + self.center_world_m
