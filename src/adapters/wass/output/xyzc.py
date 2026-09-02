"""Decode WASS ``mesh_cam.xyzC`` using the colocated upstream MATLAB loader schema."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct

import numpy as np
import numpy.typing as npt


FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True)
class WassXyzcPointCloud:
    """Decoded camera-coordinate points in unscaled WASS baseline units."""

    points_camera: FloatArray
    source_path: Path
    source_coordinate_system: str = "wass_camera_coordinates"
    source_unit: str = "baseline_normalized"

    def __post_init__(self) -> None:
        points = np.asarray(self.points_camera, dtype=np.float64)
        if points.ndim != 2 or points.shape[1] != 3 or not np.all(np.isfinite(points)):
            raise ValueError("points_camera must be finite with shape [point,3]")
        object.__setattr__(self, "points_camera", points.copy())


def read_wass_xyzc(path: str | Path) -> WassXyzcPointCloud:
    """Read the confirmed uint32/double/uint16 compressed point-cloud layout."""
    source = Path(path)
    with source.open("rb") as stream:
        count_raw = stream.read(4)
        if len(count_raw) != 4:
            raise ValueError("xyzC header is truncated")
        point_count = struct.unpack("<I", count_raw)[0]
        limits = np.fromfile(stream, dtype="<f8", count=6)
        # PovMesh writes the matrix row-by-row.  The upstream MATLAB reader
        # uses ``fread([3,3])'``: fread first constructs a column-major matrix
        # and the trailing transpose restores the original row-major matrix.
        # NumPy reshape is already row-major, so transposing here a second time
        # corrupts the camera-frame coordinates and therefore pixel projection.
        rotation_inverse = np.fromfile(stream, dtype="<f8", count=9).reshape(3, 3)
        translation_inverse = np.fromfile(stream, dtype="<f8", count=3)
        quantized = np.fromfile(stream, dtype="<u2", count=3 * point_count)
        trailing = stream.read(1)
    if limits.size != 6 or quantized.size != 3 * point_count or trailing:
        raise ValueError("xyzC size does not match declared point count")
    if np.any(limits[:3] == 0) or not np.all(np.isfinite(limits)):
        raise ValueError("xyzC quantization limits are invalid")
    # MATLAB fread([3,n]) is column-major: reshape to [point,component].
    normalized = quantized.reshape(point_count, 3).astype(np.float64)
    normalized = normalized / limits[:3] + limits[3:6]
    points_camera = normalized @ rotation_inverse.T + translation_inverse
    return WassXyzcPointCloud(points_camera, source)


def align_wass_points_to_plane(
    point_cloud: WassXyzcPointCloud,
    plane_abcd: npt.ArrayLike,
    *,
    metres_per_baseline_unit: float,
) -> FloatArray:
    """Apply WASS MATLAB's plane alignment, explicit scale, and Z inversion."""
    plane = np.asarray(plane_abcd, dtype=np.float64)
    if plane.shape != (4,) or not np.all(np.isfinite(plane)):
        raise ValueError("plane_abcd must contain four finite coefficients")
    if not np.isfinite(metres_per_baseline_unit) or metres_per_baseline_unit <= 0:
        raise ValueError("metres_per_baseline_unit must be explicitly positive")
    a, b, c, d = plane
    denominator = a * a + b * b
    if denominator == 0:
        rotation = np.eye(3)
    else:
        q = (1.0 - c) / denominator
        rotation = np.array([
            [1.0 - a * a * q, -a * b * q, -a],
            [-a * b * q, 1.0 - b * b * q, -b],
            [a, b, c],
        ])
    translation = np.array([0.0, 0.0, d])
    aligned = (point_cloud.points_camera @ rotation.T + translation) * metres_per_baseline_unit
    aligned[:, 2] *= -1.0
    return aligned
