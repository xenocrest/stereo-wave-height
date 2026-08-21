"""Thin OpenCV calibration backend for the project calibration main line.

All numerical estimation in this module is delegated to public OpenCV APIs.
Project-owned code validates conventions, records provenance, and computes
diagnostics without changing the OpenCV solution.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import numpy.typing as npt

from .checkerboard import CheckerboardSpec, stereo_baseline_m


def _cv2(module: Any | None = None) -> Any:
    if module is not None:
        return module
    try:
        import cv2
    except ImportError as error:
        raise RuntimeError("OpenCV is required for calibration") from error
    return cv2


@dataclass(frozen=True)
class OpenCvCheckerboardDetection:
    """Complete checkerboard detection in canonical full-resolution pixels."""

    corners_px: npt.NDArray[np.float32]
    method: str
    source_scale: float


@dataclass(frozen=True)
class MonoCalibrationResult:
    """One OpenCV pinhole-camera calibration result."""

    rms_px: float
    camera_matrix: npt.NDArray[np.float64]
    distortion: npt.NDArray[np.float64]
    per_view_rms_px: tuple[float, ...]


@dataclass(frozen=True)
class RectificationResult:
    """OpenCV stereoRectify outputs and corner-based vertical diagnostics."""

    rotation_left: npt.NDArray[np.float64]
    rotation_right: npt.NDArray[np.float64]
    projection_left: npt.NDArray[np.float64]
    projection_right: npt.NDArray[np.float64]
    disparity_to_depth: npt.NDArray[np.float64]
    valid_roi_left: tuple[int, int, int, int]
    valid_roi_right: tuple[int, int, int, int]
    common_valid_roi: tuple[int, int, int, int]
    vertical_disparity_rms_px: float
    vertical_disparity_max_px: float


@dataclass(frozen=True)
class StereoCalibrationResult:
    """Metric OpenCV stereo result; right camera is relative to left camera."""

    mono_left: MonoCalibrationResult
    mono_right: MonoCalibrationResult
    stereo_rms_px: float
    rotation_right_from_left: npt.NDArray[np.float64]
    translation_right_from_left_m: npt.NDArray[np.float64]
    essential_matrix: npt.NDArray[np.float64]
    fundamental_matrix: npt.NDArray[np.float64]
    epipolar_rms_px: float
    epipolar_max_px: float
    rectification: RectificationResult
    image_size_wh: tuple[int, int]
    square_size_m: float
    backend: str = "OPENCV_OFFICIAL"

    @property
    def baseline_m(self) -> float:
        return stereo_baseline_m(self.translation_right_from_left_m)

    def as_mapping(self) -> dict[str, object]:
        mono = lambda item: {
            "rms_px": item.rms_px,
            "camera_matrix": item.camera_matrix.tolist(),
            "distortion": item.distortion.reshape(-1).tolist(),
            "per_view_rms_px": list(item.per_view_rms_px),
        }
        rect = self.rectification
        return {
            "schema_version": "1.0",
            "backend": self.backend,
            "convention": "X_right = R_right_from_left @ X_left + T_right_from_left_m",
            "object_point_unit": "m",
            "image_point_unit": "pixel",
            "image_size_wh": list(self.image_size_wh),
            "square_size_m": self.square_size_m,
            "mono_left": mono(self.mono_left),
            "mono_right": mono(self.mono_right),
            "stereo_rms_px": self.stereo_rms_px,
            "rotation_right_from_left": self.rotation_right_from_left.tolist(),
            "translation_right_from_left_m": self.translation_right_from_left_m.reshape(3).tolist(),
            "baseline_m": self.baseline_m,
            "essential_matrix": self.essential_matrix.tolist(),
            "fundamental_matrix": self.fundamental_matrix.tolist(),
            "epipolar_rms_px": self.epipolar_rms_px,
            "epipolar_max_px": self.epipolar_max_px,
            "rectification": {
                "rotation_left": rect.rotation_left.tolist(),
                "rotation_right": rect.rotation_right.tolist(),
                "projection_left": rect.projection_left.tolist(),
                "projection_right": rect.projection_right.tolist(),
                "disparity_to_depth": rect.disparity_to_depth.tolist(),
                "valid_roi_left": list(rect.valid_roi_left),
                "valid_roi_right": list(rect.valid_roi_right),
                "common_valid_roi": list(rect.common_valid_roi),
                "vertical_disparity_rms_px": rect.vertical_disparity_rms_px,
                "vertical_disparity_max_px": rect.vertical_disparity_max_px,
            },
        }


def detect_checkerboard_official(
    grayscale: npt.ArrayLike,
    spec: CheckerboardSpec,
    *,
    allow_clahe_fallback: bool = False,
    cv2_module: Any | None = None,
) -> OpenCvCheckerboardDetection | None:
    """Run the frozen SB strategy: native, one 0.5x retry, optional CLAHE.

    Returned points are always refined against and expressed in the original
    canonical image. No pattern-size or parameter sweep is performed.
    """
    cv2 = _cv2(cv2_module)
    image = np.asarray(grayscale)
    if image.ndim != 2 or image.dtype != np.uint8 or image.size == 0:
        raise ValueError("grayscale must be a non-empty uint8 [height,width] image")
    flags = cv2.CALIB_CB_NORMALIZE_IMAGE | cv2.CALIB_CB_EXHAUSTIVE | cv2.CALIB_CB_ACCURACY
    attempts: list[tuple[str, npt.NDArray[np.uint8], float]] = [("SB_NATIVE", image, 1.0)]
    half = cv2.resize(image, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    attempts.append(("SB_HALF_SCALE", half, 0.5))
    if allow_clahe_fallback:
        attempts.append(("SB_CLAHE_NATIVE", cv2.createCLAHE(2.0, (8, 8)).apply(image), 1.0))
    for method, candidate, scale in attempts:
        found, corners = cv2.findChessboardCornersSB(candidate, spec.pattern_size, flags)
        if not found or corners is None or len(corners) != spec.total_inner_corners:
            continue
        full = np.asarray(corners, dtype=np.float32).reshape(-1, 1, 2) / scale
        cv2.cornerSubPix(
            image, full, (5, 5), (-1, -1),
            (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 40, 1e-4),
        )
        return OpenCvCheckerboardDetection(full.copy(), method, scale)
    return None


def _validate_views(
    object_points: Sequence[npt.ArrayLike], image_points: Sequence[npt.ArrayLike], image_size_wh: tuple[int, int]
) -> tuple[list[npt.NDArray[np.float32]], list[npt.NDArray[np.float32]]]:
    if len(object_points) != len(image_points) or len(object_points) < 2:
        raise ValueError("at least two equally paired calibration views are required")
    width, height = image_size_wh
    if width <= 0 or height <= 0:
        raise ValueError("image_size_wh must be positive and ordered (width,height)")
    objects = [np.asarray(p, dtype=np.float32).reshape(-1, 3) for p in object_points]
    images = [np.asarray(p, dtype=np.float32).reshape(-1, 1, 2) for p in image_points]
    if any(len(a) != len(b) or len(a) < 4 for a, b in zip(objects, images)):
        raise ValueError("each object/image view must contain the same four-or-more points")
    if any(not np.all(np.isfinite(p)) for p in (*objects, *images)):
        raise ValueError("calibration points must be finite")
    return objects, images


def calibrate_monocular_official(
    object_points: Sequence[npt.ArrayLike], image_points: Sequence[npt.ArrayLike], image_size_wh: tuple[int, int],
    *, cv2_module: Any | None = None,
) -> MonoCalibrationResult:
    """Call OpenCV calibrateCamera with its standard five-coefficient model."""
    cv2 = _cv2(cv2_module)
    objects, images = _validate_views(object_points, image_points, image_size_wh)
    rms, camera, distortion, rvecs, tvecs = cv2.calibrateCamera(objects, images, image_size_wh, None, None, flags=0)
    errors: list[float] = []
    for obj, img, rvec, tvec in zip(objects, images, rvecs, tvecs):
        projected, _ = cv2.projectPoints(obj, rvec, tvec, camera, distortion)
        residual = projected.reshape(-1, 2) - img.reshape(-1, 2)
        errors.append(float(np.sqrt(np.mean(np.sum(residual * residual, axis=1)))))
    values = (rms, *camera.reshape(-1), *distortion.reshape(-1), *errors)
    if not all(math.isfinite(float(value)) for value in values):
        raise RuntimeError("OpenCV monocular calibration returned non-finite output")
    return MonoCalibrationResult(float(rms), camera.astype(np.float64), distortion.astype(np.float64), tuple(errors))


def _common_roi(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[0] + a[2], b[0] + b[2]), min(a[1] + a[3], b[1] + b[3])
    return x0, y0, max(0, x1 - x0), max(0, y1 - y0)


def calibrate_stereo_official(
    object_points: Sequence[npt.ArrayLike],
    left_image_points: Sequence[npt.ArrayLike],
    right_image_points: Sequence[npt.ArrayLike],
    image_size_wh: tuple[int, int],
    *,
    square_size_m: float,
    cv2_module: Any | None = None,
) -> StereoCalibrationResult:
    """Mono calibrate, fixed-intrinsic stereoCalibrate, then stereoRectify."""
    cv2 = _cv2(cv2_module)
    objects, left = _validate_views(object_points, left_image_points, image_size_wh)
    _, right = _validate_views(object_points, right_image_points, image_size_wh)
    if not math.isfinite(square_size_m) or square_size_m <= 0:
        raise ValueError("square_size_m must be finite and positive")
    mono_left = calibrate_monocular_official(objects, left, image_size_wh, cv2_module=cv2)
    mono_right = calibrate_monocular_official(objects, right, image_size_wh, cv2_module=cv2)
    result = cv2.stereoCalibrate(
        objects, left, right,
        mono_left.camera_matrix.copy(), mono_left.distortion.copy(),
        mono_right.camera_matrix.copy(), mono_right.distortion.copy(),
        image_size_wh, flags=cv2.CALIB_FIX_INTRINSIC,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 100, 1e-5),
    )
    rms, k0, d0, k1, d1, rotation, translation, essential, fundamental = result
    epipolar: list[float] = []
    rectified_vertical: list[float] = []
    r1, r2, p1, p2, q, roi1, roi2 = cv2.stereoRectify(
        k0, d0, k1, d1, image_size_wh, rotation, translation,
        flags=cv2.CALIB_ZERO_DISPARITY, alpha=0,
    )
    for lp, rp in zip(left, right):
        lu = cv2.undistortPoints(lp, k0, d0, P=k0)
        ru = cv2.undistortPoints(rp, k1, d1, P=k1)
        lines_r = cv2.computeCorrespondEpilines(lu, 1, fundamental).reshape(-1, 3)
        lines_l = cv2.computeCorrespondEpilines(ru, 2, fundamental).reshape(-1, 3)
        lxy, rxy = lu.reshape(-1, 2), ru.reshape(-1, 2)
        dl = np.abs(np.sum(lines_l[:, :2] * lxy, axis=1) + lines_l[:, 2]) / np.linalg.norm(lines_l[:, :2], axis=1)
        dr = np.abs(np.sum(lines_r[:, :2] * rxy, axis=1) + lines_r[:, 2]) / np.linalg.norm(lines_r[:, :2], axis=1)
        epipolar.extend(((dl + dr) * 0.5).tolist())
        lr = cv2.undistortPoints(lp, k0, d0, R=r1, P=p1).reshape(-1, 2)
        rr = cv2.undistortPoints(rp, k1, d1, R=r2, P=p2).reshape(-1, 2)
        rectified_vertical.extend(np.abs(lr[:, 1] - rr[:, 1]).tolist())
    epi = np.asarray(epipolar, dtype=np.float64)
    vertical = np.asarray(rectified_vertical, dtype=np.float64)
    all_outputs = (rms, *rotation.reshape(-1), *translation.reshape(-1), *essential.reshape(-1), *fundamental.reshape(-1), *epi, *vertical)
    if not all(math.isfinite(float(value)) for value in all_outputs):
        raise RuntimeError("OpenCV stereo calibration returned non-finite output")
    rectification = RectificationResult(
        r1, r2, p1, p2, q, tuple(map(int, roi1)), tuple(map(int, roi2)),
        _common_roi(tuple(map(int, roi1)), tuple(map(int, roi2))),
        float(np.sqrt(np.mean(vertical * vertical))), float(np.max(vertical)),
    )
    return StereoCalibrationResult(
        MonoCalibrationResult(mono_left.rms_px, k0, d0, mono_left.per_view_rms_px),
        MonoCalibrationResult(mono_right.rms_px, k1, d1, mono_right.per_view_rms_px),
        float(rms), rotation, translation.reshape(3, 1), essential, fundamental,
        float(np.sqrt(np.mean(epi * epi))), float(np.max(epi)), rectification,
        image_size_wh, square_size_m,
    )


def save_calibration_result_json(result: StereoCalibrationResult, path: str | Path) -> Path:
    """Serialize the complete, convention-labelled result as UTF-8 JSON."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result.as_mapping(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return destination


def load_calibration_result_json(path: str | Path) -> dict[str, object]:
    """Load and minimally validate a serialized official-backend result."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("backend") != "OPENCV_OFFICIAL" or payload.get("object_point_unit") != "m":
        raise ValueError("not an approved OpenCV official-backend metric schema")
    return payload
