"""Authoritative stereo common-FOV geometry and ROI validation.

The mask is derived only from calibration/rectification geometry.  GUI image
content is never inspected and cropped GUI pixels are never sent to WASS.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import yaml

CANONICAL_CONVENTION = "canonical_cam1"


class CommonFovError(ValueError):
    """Structured common-FOV geometry failure."""


@dataclass(frozen=True)
class CommonFov:
    safe_mask: np.ndarray
    rectified_common_mask: np.ndarray
    bbox: tuple[int, int, int, int]
    metadata: dict[str, Any]

    @property
    def identity(self) -> str:
        return str(self.metadata["common_fov_id"])


def _calibration_id(data: dict[str, Any]) -> str:
    stable = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "cal_" + hashlib.sha256(stable.encode("utf-8")).hexdigest()[:16]


def _image_size(data: dict[str, Any]) -> tuple[int, int]:
    for value in (data.get("image_size"), data.get("image_size_wh"), data.get("dataset", {}).get("image_size_wh")):
        if isinstance(value, (list, tuple)) and len(value) == 2:
            return int(value[0]), int(value[1])
    rect = data.get("rectification", {})
    rois = [rect.get("roi0"), rect.get("roi1"), rect.get("common_roi")]
    valid = [r for r in rois if isinstance(r, (list, tuple)) and len(r) == 4]
    if valid:
        return max(int(r[0]) + int(r[2]) for r in valid), max(int(r[1]) + int(r[3]) for r in valid)
    raise CommonFovError("COMMON_FOV_CALIBRATION_SIZE_UNKNOWN")


def _matrix(data: dict[str, Any], camera: int, name: str) -> np.ndarray:
    node = data[f"mono_cam{camera}"]
    return np.asarray(node[name], dtype=np.float64)


def compute_common_fov(calibration: dict[str, Any], image_size: tuple[int, int], *, safety_margin_px: int = 0) -> CommonFov:
    """Compute rectified intersection and its selectable canonical-cam1 mask."""
    expected = _image_size(calibration)
    width, height = map(int, image_size)
    if (width, height) != expected:
        raise CommonFovError(f"COMMON_FOV_CALIBRATION_SIZE_MISMATCH: calibration={expected}, video={(width, height)}")
    if safety_margin_px not in (0, 1, 2):
        raise CommonFovError("common-FOV safety margin must be 0, 1, or 2 pixels")
    k0, d0 = _matrix(calibration, 0, "K"), _matrix(calibration, 0, "D")
    k1, d1 = _matrix(calibration, 1, "K"), _matrix(calibration, 1, "D")
    stereo, rect = calibration["stereo"], calibration.get("rectification", {})
    r = np.asarray(stereo["R_right_from_left"], dtype=np.float64)
    t = np.asarray(stereo["T_right_from_left_m"], dtype=np.float64).reshape(3,1)
    alpha = float(rect.get("alpha", 1.0))
    flags = cv2.CALIB_ZERO_DISPARITY if str(rect.get("flags", "")).upper() == "CALIB_ZERO_DISPARITY" else 0
    r0, r1, p0, p1, _q, _roi0, _roi1 = cv2.stereoRectify(k0, d0, k1, d1, (width, height), r, t, flags=flags, alpha=alpha)
    maps = []
    for k, d, rr, pp in ((k0, d0, r0, p0), (k1, d1, r1, p1)):
        mx, my = cv2.initUndistortRectifyMap(k, d, rr, pp, (width, height), cv2.CV_32FC1)
        maps.append((mx, my, np.isfinite(mx) & np.isfinite(my) & (mx >= 0) & (my >= 0) & (mx < width - 1) & (my < height - 1)))
    rect_common = maps[0][2] & maps[1][2]
    # Canonical cam1 -> rectified cam1, then sample the authoritative rectified intersection.
    yy, xx = np.indices((height, width), dtype=np.float32)
    source = np.column_stack((xx.ravel(), yy.ravel())).reshape(-1, 1, 2)
    target = cv2.undistortPoints(source, k1, d1, R=r1, P=p1).reshape(-1, 2)
    tx, ty = np.rint(target[:, 0]).astype(np.int64), np.rint(target[:, 1]).astype(np.int64)
    inside = (tx >= 0) & (ty >= 0) & (tx < width) & (ty < height)
    canonical = np.zeros(width * height, dtype=bool)
    canonical[inside] = rect_common[ty[inside], tx[inside]]
    canonical = canonical.reshape(height, width)
    if safety_margin_px:
        kernel = np.ones((2 * safety_margin_px + 1,) * 2, np.uint8)
        canonical = cv2.erode(canonical.astype(np.uint8), kernel, iterations=1).astype(bool)
    ys, xs = np.nonzero(canonical)
    if not xs.size:
        raise CommonFovError("NO_VALID_STEREO_COMMON_FOV")
    bbox = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
    cal_id = str(calibration.get("calibration_id") or _calibration_id(calibration))
    digest = hashlib.sha256(canonical.tobytes() + cal_id.encode() + f"{width}x{height}:{safety_margin_px}".encode()).hexdigest()
    metadata = {
        "schema_version": "1.0", "status": "AUTO_STEREO_COMMON_FOV_READY",
        "common_fov_id": "fov_" + digest[:16], "calibration_id": cal_id,
        "image_size": [width, height], "bbox": list(bbox), "crop_origin": [bbox[0], bbox[1]],
        "pixel_count": int(canonical.sum()), "coverage_ratio": float(canonical.mean()),
        "left_valid_count": int(maps[0][2].sum()), "right_valid_count": int(maps[1][2].sum()),
        "rectified_common_pixel_count": int(rect_common.sum()), "safety_margin_px": safety_margin_px,
        "coordinate_convention": CANONICAL_CONVENTION,
        "rectification": {"alpha": alpha, "zero_disparity": bool(flags & cv2.CALIB_ZERO_DISPARITY)},
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    }
    return CommonFov(canonical, rect_common, bbox, metadata)


def save_common_fov(value: CommonFov, directory: Path) -> tuple[Path, Path]:
    directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
    mask_path, metadata_path = directory / "common_fov_mask.npz", directory / "common_fov.yaml"
    np.savez_compressed(mask_path, safe_common_mask=value.safe_mask, rectified_common_mask=value.rectified_common_mask)
    data = dict(value.metadata); data["mask_artifact"] = mask_path.name
    metadata_path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return mask_path, metadata_path


def save_canonical_cam1_wass_mapping(calibration: dict[str, Any], destination: Path) -> Path:
    """Save the exact canonical-cam1 -> WASS computational-cam0 mapping.

    The fixed HomeTank geometry makes WASS swap the input cameras.  Its
    computational cam0 is therefore input RIGHT/cam1.  WASS receives images
    already undistorted by prepare and rectifies with zero distortion.
    """
    width, height = _image_size(calibration)
    k0, d0 = _matrix(calibration, 0, "K"), _matrix(calibration, 0, "D")
    k1, d1 = _matrix(calibration, 1, "K"), _matrix(calibration, 1, "D")
    stereo, policy = calibration["stereo"], calibration.get("rectification", {})
    r = np.asarray(stereo["R_right_from_left"], dtype=np.float64)
    t = np.asarray(stereo["T_right_from_left_m"], dtype=np.float64).reshape(3, 1)
    swapped_r, swapped_t = r.T, -r.T @ t
    alpha = float(policy.get("alpha", 1.0))
    flags = cv2.CALIB_ZERO_DISPARITY if str(policy.get("flags", "")).upper() == "CALIB_ZERO_DISPARITY" else 0
    rr, _r_other, pp, _p_other, _q, _roi0, _roi1 = cv2.stereoRectify(
        k1, np.zeros_like(d1), k0, np.zeros_like(d0), (width, height), swapped_r, swapped_t,
        flags=flags, alpha=alpha,
    )
    payload = {
        "schema_version": 1,
        "status": "GENERATED_FROM_SELECTED_FIXED_CALIBRATION",
        "coordinate_mapping": "canonical_cam1_to_wass_rectified_computational_cam0",
        "wass_role_mapping": {"computational_cam0": "input_right_cam1", "auto_swap_required": True},
        "image_size_px": [width, height],
        "prepare_undistortion": {"K1": k1.tolist(), "D1": d1.reshape(-1).tolist()},
        "stereo_rectification": {
            "input_distortion": "zero_after_prepare", "policy": {"alpha": alpha, "zero_disparity": bool(flags)},
            "R_computational_cam0": rr.tolist(), "P_computational_cam0": pp.tolist(),
        },
    }
    destination = Path(destination); destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return destination


def load_common_fov(metadata_path: Path) -> CommonFov:
    path = Path(metadata_path); data = yaml.safe_load(path.read_text(encoding="utf-8"))
    with np.load(path.parent / data["mask_artifact"]) as payload:
        safe, rectified = payload["safe_common_mask"].copy(), payload["rectified_common_mask"].copy()
    if list(safe.shape[::-1]) != list(data["image_size"]):
        raise CommonFovError("COMMON_FOV_ARTIFACT_SIZE_MISMATCH")
    return CommonFov(safe.astype(bool), rectified.astype(bool), tuple(data["bbox"]), data)


def validate_roi(roi: dict[str, Any], common: CommonFov) -> None:
    if roi.get("common_fov_id") not in (None,common.identity):
        raise CommonFovError("ROI_COMMON_FOV_ID_MISMATCH")
    if roi.get("coordinate_system") != CANONICAL_CONVENTION or roi.get("type") != "polygon":
        raise CommonFovError("ROI_COMMON_FOV_COORDINATE_MISMATCH")
    points = np.asarray(roi.get("points"), dtype=np.int64)
    if points.shape != (4, 2):
        raise CommonFovError("ROI_COMMON_FOV_SCHEMA_INVALID")
    x0, y0 = points.min(axis=0); x1, y1 = points.max(axis=0)
    h, w = common.safe_mask.shape
    if x0 < 0 or y0 < 0 or x1 > w or y1 > h or x1 <= x0 or y1 <= y0:
        raise CommonFovError("ROI_OUTSIDE_STEREO_COMMON_FOV")
    # Half-open rectangular ROI: every selected pixel, not merely corners, must be valid.
    if not bool(common.safe_mask[y0:y1, x0:x1].all()):
        raise CommonFovError("ROI_OUTSIDE_STEREO_COMMON_FOV")


def crop_to_full(pixel: tuple[int, int], bbox: tuple[int, int, int, int]) -> tuple[int, int]:
    return int(pixel[0] + bbox[0]), int(pixel[1] + bbox[1])


def full_to_crop(pixel: tuple[int, int], bbox: tuple[int, int, int, int]) -> tuple[int, int]:
    return int(pixel[0] - bbox[0]), int(pixel[1] - bbox[1])
