"""Read-only diagnostics for spatial support in a frozen WASS work directory.

This module deliberately does not invoke WASS or alter reconstruction data.
It reads the optional observability artifacts emitted by the existing diagnostic
runtime and produces counts used by the HomeTank_004 support audit.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct

import numpy as np
import numpy.typing as npt


@dataclass(frozen=True)
class DepthArtifact:
    depth: npt.NDArray[np.float64]
    valid: npt.NDArray[np.bool_]


def read_precluster_depth(path: str | Path) -> DepthArtifact:
    """Read the traceable ``WASSPCZ1`` depth-plus-validity artifact."""
    with Path(path).open("rb") as stream:
        header = stream.read(16)
        if header[:8] != b"WASSPCZ1":
            raise ValueError("unsupported pre-cluster depth artifact")
        width, height = struct.unpack("<II", header[8:])
        count = width * height
        depth = np.fromfile(stream, dtype="<f8", count=count)
        valid = np.fromfile(stream, dtype="u1", count=count)
    if depth.size != count or valid.size != count:
        raise ValueError("truncated pre-cluster depth artifact")
    return DepthArtifact(depth.reshape(height, width), valid.reshape(height, width).astype(bool))


def read_component_labels(path: str | Path) -> npt.NDArray[np.int32]:
    """Read the traceable ``WASSCCL1`` connected-component label artifact."""
    with Path(path).open("rb") as stream:
        header = stream.read(16)
        if header[:8] != b"WASSCCL1":
            raise ValueError("unsupported component-label artifact")
        width, height = struct.unpack("<II", header[8:])
        labels = np.fromfile(stream, dtype="<i4", count=width * height)
    if labels.size != width * height:
        raise ValueError("truncated component-label artifact")
    return labels.reshape(height, width)


def effective_disparity(depth: npt.ArrayLike, focal_px: float) -> npt.NDArray[np.float64]:
    """Return ``f/Z`` for WASS's baseline-normalized rectified camera depth."""
    values = np.asarray(depth, dtype=np.float64)
    if focal_px <= 0 or np.any(values <= 0):
        raise ValueError("focal length and valid depth must be positive")
    return focal_px / values


def support_funnel(common_count: int, disparity_count: int, component_count: int,
                   final_count: int) -> dict[str, int]:
    """Validate and return the observed support funnel without inventing stages."""
    values = [common_count, disparity_count, component_count, final_count]
    if any(value < 0 for value in values):
        raise ValueError("support counts cannot be negative")
    if not (common_count >= disparity_count >= component_count >= final_count):
        raise ValueError("support funnel must be monotonically non-increasing")
    return dict(common_fov=common_count, stereo_triangulated=disparity_count,
                largest_component=component_count, final_xyz=final_count)
