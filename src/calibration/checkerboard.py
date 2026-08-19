"""Checkerboard calibration primitives with explicit units and conventions."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import numpy as np
import numpy.typing as npt


@dataclass(frozen=True)
class CheckerboardSpec:
    """Inner-corner pattern and physical square size in metres."""

    inner_corners_cols: int
    inner_corners_rows: int
    square_size_m: float

    def __post_init__(self) -> None:
        if self.inner_corners_cols < 2 or self.inner_corners_rows < 2:
            raise ValueError("checkerboard must contain at least 2x2 inner corners")
        if not math.isfinite(self.square_size_m) or self.square_size_m <= 0:
            raise ValueError("square_size_m must be finite and positive")

    @property
    def pattern_size(self) -> tuple[int, int]:
        """OpenCV order: (columns, rows) of inner corners."""
        return self.inner_corners_cols, self.inner_corners_rows

    @property
    def total_inner_corners(self) -> int:
        return self.inner_corners_cols * self.inner_corners_rows

    def object_points_m(self) -> npt.NDArray[np.float32]:
        """Planar row-major points ``(column*square,row*square,0)`` in metres."""
        points = np.zeros((self.total_inner_corners, 3), dtype=np.float32)
        grid = np.mgrid[0 : self.inner_corners_cols, 0 : self.inner_corners_rows].T.reshape(-1, 2)
        points[:, :2] = grid.astype(np.float32) * self.square_size_m
        return points

    def as_mapping(self) -> dict[str, object]:
        return {
            "pattern_size": [self.inner_corners_cols, self.inner_corners_rows],
            "total_inner_corners": self.total_inner_corners,
            "square_size_m": self.square_size_m,
            "square_size_mm": self.square_size_m * 1000.0,
            "pattern_definition": "inner_corners_not_square_count",
        }


@dataclass(frozen=True)
class CalibrationCameraRoles:
    """Experiment-local camera roles; never inferred from a previous trial."""

    experiment_id: str
    left_role: str
    left_device: str
    right_role: str
    right_device: str
    source: str

    def __post_init__(self) -> None:
        values = (self.experiment_id, self.left_role, self.left_device, self.right_role, self.right_device, self.source)
        if any(not value for value in values):
            raise ValueError("camera-role provenance fields must be non-empty")
        if self.left_role == self.right_role or self.left_device == self.right_device:
            raise ValueError("left and right roles/devices must be distinct")


@dataclass(frozen=True)
class CheckerboardDetection:
    """Raw and explicitly subpixel-refined image corners."""

    raw_corners_px: npt.NDArray[np.float32]
    refined_corners_px: npt.NDArray[np.float32]


def detect_and_refine_checkerboard(
    grayscale: npt.ArrayLike,
    spec: CheckerboardSpec,
    *,
    cv2_module: Any | None = None,
) -> CheckerboardDetection | None:
    """Detect a complete checkerboard and run explicit subpixel refinement.

    OpenCV is imported lazily so unit-only consumers do not require a video or
    calibration backend. No partial-grid fallback or custom line-grid solver is
    used when standard checkerboard detection fails.
    """
    cv2 = cv2_module
    if cv2 is None:
        try:
            import cv2 as cv2_imported
        except ImportError as error:
            raise RuntimeError("OpenCV is required for checkerboard detection") from error
        cv2 = cv2_imported
    image = np.asarray(grayscale)
    if image.ndim != 2 or image.dtype != np.uint8 or image.size == 0:
        raise ValueError("grayscale must be a non-empty uint8 [height,width] image")
    flags = cv2.CALIB_CB_NORMALIZE_IMAGE | cv2.CALIB_CB_EXHAUSTIVE | cv2.CALIB_CB_ACCURACY
    found, corners = cv2.findChessboardCornersSB(image, spec.pattern_size, flags)
    if not found or corners is None or corners.shape[0] != spec.total_inner_corners:
        return None
    raw = np.asarray(corners, dtype=np.float32).reshape(-1, 1, 2).copy()
    refined = raw.copy()
    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 40, 1e-4)
    cv2.cornerSubPix(image, refined, (5, 5), (-1, -1), criteria)
    return CheckerboardDetection(raw, refined)


def stereo_baseline_m(translation_right_from_left_m: npt.ArrayLike) -> float:
    """Return ``||T||`` for a finite metric left-to-right translation."""
    translation = np.asarray(translation_right_from_left_m, dtype=np.float64)
    if translation.shape not in ((3,), (3, 1)) or not np.all(np.isfinite(translation)):
        raise ValueError("translation must contain three finite metric components")
    baseline = float(np.linalg.norm(translation.reshape(3)))
    if baseline <= 0:
        raise ValueError("stereo baseline must be positive")
    return baseline


@dataclass(frozen=True)
class StereoExtrinsics:
    """OpenCV convention ``X_right = R_right_from_left X_left + T`` in metres."""

    rotation_right_from_left: npt.NDArray[np.float64]
    translation_right_from_left_m: npt.NDArray[np.float64]
    source: str
    status: str = "CALIBRATED"

    def __post_init__(self) -> None:
        rotation = np.asarray(self.rotation_right_from_left, dtype=np.float64)
        translation = np.asarray(self.translation_right_from_left_m, dtype=np.float64).reshape(-1)
        if rotation.shape != (3, 3) or translation.shape != (3,):
            raise ValueError("stereo R/T must have shapes [3,3] and [3]")
        if not np.all(np.isfinite(rotation)) or not np.all(np.isfinite(translation)):
            raise ValueError("stereo R/T must be finite")
        if not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-8, rtol=0.0):
            raise ValueError("stereo rotation must be orthonormal")
        if not np.isclose(np.linalg.det(rotation), 1.0, atol=1e-8, rtol=0.0):
            raise ValueError("stereo rotation must be right-handed")
        if not self.source or self.status in ("", "UNKNOWN", "TODO"):
            raise ValueError("stereo calibration provenance must be explicit")
        object.__setattr__(self, "rotation_right_from_left", rotation.copy())
        object.__setattr__(self, "translation_right_from_left_m", translation.copy())

    @property
    def baseline_m(self) -> float:
        return stereo_baseline_m(self.translation_right_from_left_m)

    def as_mapping(self) -> dict[str, object]:
        return {
            "convention": "X_right = R_right_from_left * X_left + T_right_from_left_m",
            "rotation_right_from_left": self.rotation_right_from_left.tolist(),
            "translation_right_from_left_m": self.translation_right_from_left_m.tolist(),
            "baseline_m": self.baseline_m,
            "source": self.source,
            "status": self.status,
        }
