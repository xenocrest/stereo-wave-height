"""Configurable ideal stereo observation geometry; no matching or triangulation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from .config import NominalIntrinsics
from .virtual_camera import VirtualPinholeCamera


FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True)
class IdealStereoRig:
    """Parallel, downward-looking virtual stereo rig.

    ``baseline_m`` and ``working_distance_m`` are mandatory deployment
    variables. Camera centres are above ``Zw=0`` and optical axes point toward
    ``-Zw``. No default deployment geometry is inferred.
    """

    intrinsics: NominalIntrinsics
    baseline_m: float
    working_distance_m: float
    left: VirtualPinholeCamera
    right: VirtualPinholeCamera
    coordinate_system: str = "world_water_surface"
    unit: str = "m"

    @classmethod
    def create(
        cls,
        intrinsics: NominalIntrinsics,
        *,
        baseline_m: float,
        working_distance_m: float,
    ) -> "IdealStereoRig":
        """Create a rig from explicit positive deployment variables."""
        if not np.isfinite(baseline_m) or baseline_m <= 0:
            raise ValueError("baseline_m must be explicitly positive and finite")
        if not np.isfinite(working_distance_m) or working_distance_m <= 0:
            raise ValueError("working_distance_m must be explicitly positive and finite")

        # Xc=+Xw, Yc=-Yw, Zc=-Zw gives a proper downward-looking rotation.
        rotation = np.diag([1.0, -1.0, -1.0])
        left = VirtualPinholeCamera(
            camera_id="left",
            intrinsics=intrinsics,
            center_world_m=np.array([-baseline_m / 2.0, 0.0, working_distance_m]),
            rotation_world_to_camera=rotation,
        )
        right = VirtualPinholeCamera(
            camera_id="right",
            intrinsics=intrinsics,
            center_world_m=np.array([baseline_m / 2.0, 0.0, working_distance_m]),
            rotation_world_to_camera=rotation,
        )
        return cls(
            intrinsics=intrinsics,
            baseline_m=float(baseline_m),
            working_distance_m=float(working_distance_m),
            left=left,
            right=right,
        )

    def project(
        self,
        points_world_m: npt.ArrayLike,
        *,
        coordinate_system: str,
        unit: str,
    ) -> tuple[FloatArray, FloatArray, FloatArray, FloatArray]:
        """Return left/right pixels and depths for known 3-D world points."""
        if coordinate_system != self.coordinate_system:
            raise ValueError("stereo rig coordinate system mismatch")
        if unit != self.unit:
            raise ValueError("stereo rig unit mismatch")
        left_pixels, left_depth = self.left.project(
            points_world_m, coordinate_system=coordinate_system, unit=unit
        )
        right_pixels, right_depth = self.right.project(
            points_world_m, coordinate_system=coordinate_system, unit=unit
        )
        return left_pixels, right_pixels, left_depth, right_depth

    @property
    def left_projection_matrix(self) -> FloatArray:
        """Left nominal projection matrix ``K[R|-RC]``."""
        return self.left.projection_matrix

    @property
    def right_projection_matrix(self) -> FloatArray:
        """Right nominal projection matrix ``K[R|-RC]``."""
        return self.right.projection_matrix
