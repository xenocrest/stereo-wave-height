"""Reproduce Vieira-style monocular intrinsics from a raw checkerboard video.

The numerical detector and calibration are OpenCV APIs.  This wrapper only
performs deterministic sampling, chooses spatially diverse complete-board
views without looking at reprojection error, and records full provenance.
It deliberately does not estimate stereo extrinsics; WASS autocalibration is
the authority for that stage of the Vieira workflow.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import cv2
import numpy as np


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def detect(gray: np.ndarray, pattern: tuple[int, int]) -> tuple[np.ndarray, str] | None:
    flags = cv2.CALIB_CB_NORMALIZE_IMAGE | cv2.CALIB_CB_EXHAUSTIVE | cv2.CALIB_CB_ACCURACY
    attempts = [(gray, 1.0, "SB_NATIVE")]
    half = cv2.resize(gray, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    attempts.append((half, 0.5, "SB_HALF_SCALE"))
    for candidate, scale, method in attempts:
        found, corners = cv2.findChessboardCornersSB(candidate, pattern, flags)
        if not found or corners is None or len(corners) != pattern[0] * pattern[1]:
            continue
        full = np.asarray(corners, np.float32).reshape(-1, 1, 2) / scale
        cv2.cornerSubPix(
            gray,
            full,
            (5, 5),
            (-1, -1),
            (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 40, 1e-4),
        )
        return full, method
    return None


def descriptor(corners: np.ndarray, width: int, height: int, pattern: tuple[int, int]) -> np.ndarray:
    xy = corners.reshape(-1, 2).astype(np.float64)
    lo, hi = xy.min(axis=0), xy.max(axis=0)
    area = max(float(np.prod(hi - lo)) / float(width * height), 1e-12)
    row = xy[pattern[0] - 1] - xy[0]
    col = xy[-pattern[0]] - xy[0]
    row_angle = math.atan2(float(row[1]), float(row[0]))
    row0 = np.linalg.norm(row)
    row1 = np.linalg.norm(xy[-1] - xy[-pattern[0]])
    col0 = np.linalg.norm(col)
    col1 = np.linalg.norm(xy[-1] - xy[pattern[0] - 1])
    perspective = max(abs(row0 - row1) / max(row0, row1), abs(col0 - col1) / max(col0, col1))
    return np.asarray(
        [xy[:, 0].mean() / width, xy[:, 1].mean() / height, math.log(area), math.sin(row_angle), math.cos(row_angle), perspective],
        np.float64,
    )


def select_diverse(records: list[dict[str, Any]], count: int) -> list[int]:
    if len(records) <= count:
        return list(range(len(records)))
    features = np.stack([np.asarray(record["descriptor"], np.float64) for record in records])
    lo, hi = np.min(features, axis=0), np.max(features, axis=0)
    normalized = (features - lo) / np.where(hi - lo > 1e-12, hi - lo, 1.0)
    median = np.median(normalized, axis=0)
    chosen = [int(np.argmin(np.linalg.norm(normalized - median, axis=1)))]
    remaining = set(range(len(records))) - set(chosen)
    while remaining and len(chosen) < count:
        index = max(remaining, key=lambda item: (min(float(np.linalg.norm(normalized[item] - normalized[j])) for j in chosen), -records[item]["frame_index"]))
        chosen.append(index)
        remaining.remove(index)
    return sorted(chosen, key=lambda item: records[item]["frame_index"])


def object_points(pattern: tuple[int, int], square_size_m: float) -> np.ndarray:
    points = np.zeros((pattern[0] * pattern[1], 3), np.float32)
    points[:, :2] = np.mgrid[0 : pattern[0], 0 : pattern[1]].T.reshape(-1, 2).astype(np.float32) * square_size_m
    return points


def save_matrix(path: Path, value: np.ndarray) -> None:
    storage = cv2.FileStorage(str(path), cv2.FILE_STORAGE_WRITE)
    if not storage.isOpened():
        raise RuntimeError(f"cannot open OpenCV matrix output: {path}")
    storage.write("matrix", np.asarray(value, np.float64))
    storage.release()


def run(args: argparse.Namespace) -> dict[str, Any]:
    source = Path(args.video).resolve()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "selected_frames").mkdir(exist_ok=True)
    (output / "corner_overlays").mkdir(exist_ok=True)
    pattern = (args.pattern_cols, args.pattern_rows)

    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise ValueError(f"cannot open raw calibration video: {source}")
    if hasattr(cv2, "CAP_PROP_ORIENTATION_AUTO"):
        capture.set(cv2.CAP_PROP_ORIENTATION_AUTO, 0)
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    interval = max(1, int(round(fps / args.sample_hz)))
    records: list[dict[str, Any]] = []
    sampled = 0
    index = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        if index % interval == 0:
            sampled += 1
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            found = detect(gray, pattern)
            if found is not None:
                corners, method = found
                desc = descriptor(corners, width, height, pattern)
                lo = np.floor(corners.reshape(-1, 2).min(axis=0)).astype(int)
                hi = np.ceil(corners.reshape(-1, 2).max(axis=0)).astype(int)
                roi = gray[max(0, lo[1]) : min(height, hi[1] + 1), max(0, lo[0]) : min(width, hi[0] + 1)]
                sharpness = float(cv2.Laplacian(roi, cv2.CV_64F).var()) if roi.size else 0.0
                records.append(
                    {
                        "frame_index": index,
                        "timestamp_s": index / fps,
                        "method": method,
                        "sharpness_laplacian_variance": sharpness,
                        "descriptor": desc.tolist(),
                        "corners_px": corners.reshape(-1, 2).astype(float).tolist(),
                    }
                )
        index += 1
    capture.release()
    if len(records) < args.minimum_views:
        raise RuntimeError(f"only {len(records)} complete checkerboards detected; minimum is {args.minimum_views}")

    selected_indices = select_diverse(records, args.target_views)
    selected = [records[item] for item in selected_indices]
    object_template = object_points(pattern, args.square_size_m)
    objects = [object_template.copy() for _ in selected]
    images = [np.asarray(record["corners_px"], np.float32).reshape(-1, 1, 2) for record in selected]
    rms, camera, distortion, rvecs, tvecs = cv2.calibrateCamera(objects, images, (width, height), None, None, flags=0)
    per_view = []
    for obj, image, rvec, tvec in zip(objects, images, rvecs, tvecs):
        projected, _ = cv2.projectPoints(obj, rvec, tvec, camera, distortion)
        residual = projected.reshape(-1, 2) - image.reshape(-1, 2)
        per_view.append(float(np.sqrt(np.mean(np.sum(residual * residual, axis=1)))))
    if not np.all(np.isfinite(np.concatenate([camera.reshape(-1), distortion.reshape(-1), np.asarray(per_view), [rms]]))):
        raise RuntimeError("OpenCV returned non-finite calibration output")
    if distortion.size != 5:
        raise RuntimeError(f"WASS expects OpenCV's five-parameter distortion model, got {distortion.size}")

    capture = cv2.VideoCapture(str(source))
    if hasattr(cv2, "CAP_PROP_ORIENTATION_AUTO"):
        capture.set(cv2.CAP_PROP_ORIENTATION_AUTO, 0)
    for order, record in enumerate(selected):
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(record["frame_index"]))
        ok, frame = capture.read()
        if not ok:
            raise RuntimeError(f"cannot re-read selected frame {record['frame_index']}")
        name = f"view_{order:03d}_frame_{record['frame_index']:06d}.png"
        cv2.imwrite(str(output / "selected_frames" / name), frame)
        overlay = frame.copy()
        cv2.drawChessboardCorners(overlay, pattern, np.asarray(record["corners_px"], np.float32).reshape(-1, 1, 2), True)
        cv2.imwrite(str(output / "corner_overlays" / name), overlay)
        record["selected_order"] = order
        record["per_view_rms_px"] = per_view[order]
    capture.release()

    save_matrix(output / "intrinsics.xml", camera)
    save_matrix(output / "distortion.xml", distortion.reshape(5, 1))
    result = {
        "schema_version": "1.0",
        "method": "OpenCV findChessboardCornersSB + cornerSubPix + calibrateCamera",
        "selection_rule": "complete detections sampled uniformly in time; deterministic farthest-point diversity in board center/scale/orientation/perspective; reprojection error not used for selection",
        "source_video": str(source),
        "source_sha256": sha256(source),
        "opencv_version": cv2.__version__,
        "image_size_wh": [width, height],
        "fps_reported_by_decoder": fps,
        "frame_count_reported_by_decoder": frame_count,
        "sample_hz": args.sample_hz,
        "sampled_frame_count": sampled,
        "complete_detection_count": len(records),
        "selected_view_count": len(selected),
        "pattern_inner_corners": list(pattern),
        "square_size_m": args.square_size_m,
        "rms_px": float(rms),
        "per_view_rms_px": per_view,
        "camera_matrix": camera.tolist(),
        "distortion_k1_k2_p1_p2_k3": distortion.reshape(-1).tolist(),
        "all_detections": records,
        "selected_frame_indices": [int(record["frame_index"]) for record in selected],
        "selected_frame_files": [f"selected_frames/view_{i:03d}_frame_{record['frame_index']:06d}.png" for i, record in enumerate(selected)],
        "focus_zoom_risk": "NOT_OBSERVABLE_FROM_CONTAINER_METADATA; fixed-intrinsics model assumed by Vieira/OpenCV calibration",
        "stereo_extrinsics": "NOT_ESTIMATED_HERE; delegated to WASS autocalibration",
    }
    (output / "calibration.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--pattern-cols", type=int, default=9)
    parser.add_argument("--pattern-rows", type=int, default=6)
    parser.add_argument("--square-size-m", type=float, default=0.020)
    parser.add_argument("--sample-hz", type=float, default=5.0)
    parser.add_argument("--target-views", type=int, default=50)
    parser.add_argument("--minimum-views", type=int, default=20)
    args = parser.parse_args()
    result = run(args)
    print(json.dumps({key: result[key] for key in ("source_video", "complete_detection_count", "selected_view_count", "rms_px", "camera_matrix", "distortion_k1_k2_p1_p2_k3")}, indent=2))


if __name__ == "__main__":
    main()
