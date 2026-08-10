"""In-memory WASS-input-facing metadata; this module writes no images or video."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

import numpy as np
import numpy.typing as npt

from .stereo_rig import IdealStereoRig


FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]


@dataclass(frozen=True)
class SyntheticFrameRecord:
    """One planned synchronized synthetic stereo frame pair."""

    frame_id: str
    timestamp_ns: int
    left_image: PurePosixPath
    right_image: PurePosixPath
    time_reference: str = "simulation_epoch"
    sync_offset_ns: int = 0
    pair_status: str = "planned_not_materialized"


@dataclass(frozen=True)
class SyntheticCameraMetadata:
    """Candidate-device-derived camera metadata for a virtual view."""

    camera_id: str
    model: str
    width_px: int
    height_px: int
    pixel_size_um: float
    focal_length_mm: float
    equipment_status: str
    intrinsic_status: str
    coordinate_system: str


@dataclass(frozen=True)
class SyntheticCalibration:
    """Simulation-nominal calibration; never a real calibrated result."""

    intrinsic_left: FloatArray
    intrinsic_right: FloatArray
    distortion_left: FloatArray
    distortion_right: FloatArray
    projection_left: FloatArray
    projection_right: FloatArray
    relative_rotation_right_from_left: FloatArray
    relative_translation_right_from_left_m: FloatArray
    baseline_m: float
    working_distance_m: float
    status: str = "SIMULATION_NOMINAL"


@dataclass(frozen=True)
class SyntheticDatasetManifest:
    """Planned dataset contract corresponding to future WASS input files."""

    frames: tuple[SyntheticFrameRecord, ...]
    cameras: tuple[SyntheticCameraMetadata, SyntheticCameraMetadata]
    calibration: SyntheticCalibration
    source_type: str = "simulation"
    image_format: str = "grayscale_png"
    materialized: bool = False


def build_synthetic_manifest(
    rig: IdealStereoRig,
    timestamp_ns: npt.ArrayLike,
) -> SyntheticDatasetManifest:
    """Build metadata and planned paths without rendering or writing images."""
    timestamps = np.asarray(timestamp_ns, dtype=np.int64)
    if timestamps.ndim != 1 or timestamps.size == 0:
        raise ValueError("timestamp_ns must be a non-empty one-dimensional array")
    if timestamps.size > 1 and np.any(np.diff(timestamps) <= 0):
        raise ValueError("timestamp_ns must be strictly increasing")

    frames = tuple(
        SyntheticFrameRecord(
            frame_id=f"{index:06d}",
            timestamp_ns=int(timestamp),
            left_image=PurePosixPath(f"left/{index:06d}.png"),
            right_image=PurePosixPath(f"right/{index:06d}.png"),
        )
        for index, timestamp in enumerate(timestamps)
    )
    equipment = rig.intrinsics.equipment
    cameras = tuple(
        SyntheticCameraMetadata(
            camera_id=camera_id,
            model=equipment.model,
            width_px=equipment.width_px,
            height_px=equipment.height_px,
            pixel_size_um=equipment.pixel_size_um,
            focal_length_mm=equipment.focal_length_mm,
            equipment_status=equipment.camera_status,
            intrinsic_status=rig.intrinsics.status,
            coordinate_system=f"virtual_camera_{camera_id}",
        )
        for camera_id in ("left", "right")
    )
    calibration = SyntheticCalibration(
        intrinsic_left=rig.intrinsics.matrix,
        intrinsic_right=rig.intrinsics.matrix,
        distortion_left=rig.intrinsics.distortion.copy(),
        distortion_right=rig.intrinsics.distortion.copy(),
        projection_left=rig.left_projection_matrix,
        projection_right=rig.right_projection_matrix,
        relative_rotation_right_from_left=np.eye(3, dtype=np.float64),
        relative_translation_right_from_left_m=np.array([-rig.baseline_m, 0.0, 0.0]),
        baseline_m=rig.baseline_m,
        working_distance_m=rig.working_distance_m,
    )
    return SyntheticDatasetManifest(
        frames=frames,
        cameras=(cameras[0], cameras[1]),
        calibration=calibration,
    )
