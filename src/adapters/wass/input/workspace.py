"""Prepare canonical WASS inputs without changing geometry or exposing truth."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any


REQUIRED_WASS_CONFIG_FILES = (
    "intrinsics_00.xml",
    "intrinsics_01.xml",
    "distortion_00.xml",
    "distortion_01.xml",
    "matcher_config.txt",
    "stereo_config.txt",
)


@dataclass(frozen=True)
class PreparedWassWorkspace:
    """Materialized, traceable WASS input workspace."""

    root: Path
    manifest_path: Path
    calibration_dir: Path
    frame_count: int


def _inside(root: Path, relative: str, field: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as error:
        raise ValueError(f"{field} escapes dataset root") from error
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    return candidate


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prepare_wass_workspace(
    dataset_root: str | Path,
    workspace_root: str | Path,
    *,
    verified_config_dir: str | Path,
) -> PreparedWassWorkspace:
    """Map a canonical stereo manifest to WASS inputs using verified configs.

    Synthetic timestamps require exact integer-millisecond filename tokens.
    Real-video PTS retain nanoseconds in the manifest while only the filename
    token is floored to milliseconds. Ground-truth files are neither read nor
    copied.
    """
    dataset = Path(dataset_root).resolve()
    source_manifest = dataset / "metadata" / "manifest.json"
    if not source_manifest.is_file():
        raise FileNotFoundError(source_manifest)
    payload = json.loads(source_manifest.read_text(encoding="utf-8"))
    dataset_type = payload.get("dataset_type")
    supported_types = {
        "synthetic_stereo_wass_input_adapter",
        "real_stereo_video_wass_input_adapter",
    }
    if dataset_type not in supported_types:
        raise ValueError("unsupported dataset_type")
    if dataset_type == "real_stereo_video_wass_input_adapter":
        if payload.get("orientation_status") != "CANONICAL_ORIENTATION_APPLIED":
            raise ValueError("real-video frames must declare canonical orientation before WASS")
        if payload.get("pairing_basis") != "timestamp":
            raise ValueError("real-video frames must be paired by timestamp")
    frames = payload.get("frames")
    if not isinstance(frames, list) or not frames:
        raise ValueError("manifest frames must be a non-empty list")

    config_source = Path(verified_config_dir).resolve()
    missing = [name for name in REQUIRED_WASS_CONFIG_FILES if not (config_source / name).is_file()]
    if missing:
        raise FileNotFoundError(f"verified WASS config files missing: {missing}")

    root = Path(workspace_root).resolve()
    if root.exists() and any(root.iterdir()):
        raise FileExistsError("workspace_root must be absent or empty")
    cam0 = root / "input" / "cam0"
    cam1 = root / "input" / "cam1"
    config_target = root / "config"
    logs = root / "logs"
    work = root / "work"
    for directory in (cam0, cam1, config_target, logs, work):
        directory.mkdir(parents=True, exist_ok=True)

    config_records: dict[str, dict[str, str]] = {}
    for name in REQUIRED_WASS_CONFIG_FILES:
        source = config_source / name
        target = config_target / name
        shutil.copy2(source, target)
        config_records[name] = {"path": target.relative_to(root).as_posix(), "sha256": _sha256(target)}

    frame_records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_timestamps: set[int] = set()
    for index, frame in enumerate(frames):
        if not isinstance(frame, dict):
            raise ValueError("each manifest frame must be an object")
        frame_id = frame.get("frame_id")
        timestamp_ns = frame.get("timestamp_ns")
        if frame_id != f"{index:06d}" or frame_id in seen_ids:
            raise ValueError("frame_id must be unique, contiguous, and six-digit")
        if not isinstance(timestamp_ns, int) or timestamp_ns < 0 or timestamp_ns in seen_timestamps:
            raise ValueError("timestamp_ns must be a unique non-negative integer")
        if dataset_type == "synthetic_stereo_wass_input_adapter" and timestamp_ns % 1_000_000:
            raise ValueError("timestamp_ns cannot be losslessly represented as integer milliseconds")
        seen_ids.add(frame_id)
        seen_timestamps.add(timestamp_ns)
        timestamp_ms = timestamp_ns // 1_000_000
        left_source = _inside(dataset, str(frame.get("left_image", "")), "left_image")
        right_source = _inside(dataset, str(frame.get("right_image", "")), "right_image")
        left_name = f"{frame_id}_{timestamp_ms:013d}_01.png"
        right_name = f"{frame_id}_{timestamp_ms:013d}_02.png"
        left_target = cam0 / left_name
        right_target = cam1 / right_name
        shutil.copy2(left_source, left_target)
        shutil.copy2(right_source, right_target)
        frame_records.append(
            {
                "frame_id": frame_id,
                "timestamp_ns": timestamp_ns,
                "timestamp_ms_filename_token": timestamp_ms,
                "timestamp_filename_quantization": "exact" if timestamp_ns % 1_000_000 == 0 else "floor_to_millisecond_filename_only",
                "cam0": left_target.relative_to(root).as_posix(),
                "cam1": right_target.relative_to(root).as_posix(),
                "workdir": f"work/{frame_id}_wd",
                "source_sha256": {"cam0": _sha256(left_target), "cam1": _sha256(right_target)},
            }
        )

    output = {
        "schema_version": 1,
        "adapter": f"stereo-wave-height.{dataset_type}.v1",
        "source_manifest": str(source_manifest),
        "image_operation": (
            "byte_for_byte_copy_no_geometry_change"
            if dataset_type == "synthetic_stereo_wass_input_adapter"
            else "byte_for_byte_copy_of_already_canonical_frames"
        ),
        "ground_truth_exposed_to_wass": False,
        "config_status": "caller_supplied_verified_wass_v1_5",
        "calibration_provenance": payload.get("calibration_provenance"),
        "config": config_records,
        "frames": frame_records,
    }
    manifest_path = root / "wass_input_manifest.json"
    manifest_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    return PreparedWassWorkspace(root, manifest_path, config_target, len(frame_records))
