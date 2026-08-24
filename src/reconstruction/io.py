"""Configuration, video-frame extraction and artifact IO for reconstruction."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
from typing import Any
import xml.etree.ElementTree as ET

import numpy as np


@dataclass(frozen=True)
class FrameRequest:
    """One timestamp-associated pair requested from two videos."""

    frame_id: str
    left_timestamp_s: float
    right_timestamp_s: float
    timestamp_ns: int


@dataclass(frozen=True)
class ReconstructionConfig:
    """Resolved, vendor-neutral reconstruction configuration."""

    source_path: Path
    left_video: Path
    right_video: Path
    frame_requests: tuple[FrameRequest, ...]
    left_rotation_deg: int
    right_rotation_deg: int
    calibration_file: Path
    calibration_quality_mode: str
    wass_config_dir: Path
    wass_runtime_binding: Path
    ffmpeg_executable: str
    output_directory: Path
    surface_distance_threshold_m: float
    run_type: str
    reference_plane_file: Path | None


@dataclass(frozen=True)
class CalibrationParameters:
    """OpenCV stereo calibration with explicit metric translation."""

    k0: np.ndarray
    d0: np.ndarray
    k1: np.ndarray
    d1: np.ndarray
    r: np.ndarray
    t_m: np.ndarray
    approved_for_wass: bool
    source_path: Path

    @property
    def baseline_m(self) -> float:
        return float(np.linalg.norm(self.t_m))


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as error:
        raise RuntimeError("YAML configuration requires PyYAML") from error
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"configuration root must be a mapping: {path}")
    return data


def _resolve(base: Path, raw: str, field: str) -> Path:
    expanded = os.path.expandvars(raw)
    if "$" in expanded:
        raise ValueError(f"unresolved environment variable in {field}: {raw}")
    path = Path(expanded)
    return (path if path.is_absolute() else base / path).resolve()


def load_reconstruction_config(path: str | Path) -> ReconstructionConfig:
    """Load a YAML config and resolve paths relative to the config file."""
    source = Path(path).resolve()
    data = _load_yaml(source)
    base = source.parent
    input_data = data.get("input", {})
    calibration = data.get("calibration", {})
    processing = data.get("processing", {})
    output = data.get("output", {})
    if processing.get("stereo_backend") != "wass":
        raise ValueError("stereo_backend must be wass")
    if processing.get("fixed_calibration") is not True:
        raise ValueError("this pipeline requires fixed_calibration=true")
    if processing.get("run_autocalibrate") is not False:
        raise ValueError("fixed-calibration pipeline forbids autocalibration")
    requests: list[FrameRequest] = []
    for index, item in enumerate(input_data.get("frame_pairs", [])):
        frame_id = str(item.get("frame_id", ""))
        if frame_id != f"{index:06d}":
            raise ValueError("frame IDs must be contiguous six-digit values")
        left_s = float(item["left_timestamp_s"])
        right_s = float(item["right_timestamp_s"])
        timestamp_ns = int(item.get("timestamp_ns", round(left_s * 1_000_000_000)))
        if not np.isfinite(left_s) or not np.isfinite(right_s) or min(left_s, right_s) < 0:
            raise ValueError("frame timestamps must be finite and non-negative")
        requests.append(FrameRequest(frame_id, left_s, right_s, timestamp_ns))
    if not requests:
        raise ValueError("input.frame_pairs must not be empty")
    rotations = input_data.get("canonical_rotation_deg", {})
    threshold = float(processing.get("surface_distance_threshold_m"))
    if not np.isfinite(threshold) or threshold <= 0:
        raise ValueError("surface_distance_threshold_m must be explicitly positive")
    config = ReconstructionConfig(
        source_path=source,
        left_video=_resolve(base, str(input_data["left_video"]), "left_video"),
        right_video=_resolve(base, str(input_data["right_video"]), "right_video"),
        frame_requests=tuple(requests),
        left_rotation_deg=int(rotations.get("left", 0)),
        right_rotation_deg=int(rotations.get("right", 0)),
        calibration_file=_resolve(base, str(calibration["file"]), "calibration.file"),
        calibration_quality_mode=str(calibration.get("quality_mode", "require_approved")),
        wass_config_dir=_resolve(base, str(processing["wass_config_dir"]), "wass_config_dir"),
        wass_runtime_binding=_resolve(base, str(processing["wass_runtime_binding"]), "wass_runtime_binding"),
        ffmpeg_executable=os.path.expandvars(str(input_data["ffmpeg_executable"])),
        output_directory=_resolve(base, str(output["directory"]), "output.directory"),
        surface_distance_threshold_m=threshold,
        run_type=str(processing.get("run_type", "static")),
        reference_plane_file=(
            _resolve(base, str(processing["reference_plane_file"]), "reference_plane_file")
            if processing.get("reference_plane_file") else None
        ),
    )
    for name, candidate in (
        ("left_video", config.left_video), ("right_video", config.right_video),
        ("calibration.file", config.calibration_file), ("wass_config_dir", config.wass_config_dir),
        ("wass_runtime_binding", config.wass_runtime_binding),
    ):
        if not candidate.exists():
            raise FileNotFoundError(f"{name}: {candidate}")
    if config.left_rotation_deg not in (0, 90, 180, 270) or config.right_rotation_deg not in (0, 90, 180, 270):
        raise ValueError("canonical rotations must be 0/90/180/270 degrees")
    if config.calibration_quality_mode not in {"require_approved", "diagnostic_allow_failed_gate"}:
        raise ValueError("unsupported calibration quality_mode")
    if config.run_type not in {"static", "wave"}:
        raise ValueError("processing.run_type must be static or wave")
    if config.run_type == "wave" and config.reference_plane_file is None:
        raise ValueError("wave processing requires an explicit static reference_plane_file")
    if config.reference_plane_file is not None and not config.reference_plane_file.is_file():
        raise FileNotFoundError(f"reference_plane_file: {config.reference_plane_file}")
    return config


def load_reference_plane(path: str | Path) -> tuple[np.ndarray, float, dict[str, Any]]:
    """Load a normalized, metric static reference plane with provenance."""
    source = Path(path).resolve()
    data = _load_yaml(source)
    plane = data.get("plane", {})
    normal = np.asarray(plane.get("normal"), dtype=np.float64)
    offset = float(plane.get("offset_m"))
    if normal.shape != (3,) or not np.all(np.isfinite(normal)) or not np.isfinite(offset):
        raise ValueError("reference plane must contain finite normal[3] and offset_m")
    norm = float(np.linalg.norm(normal))
    if not np.isclose(norm, 1.0, atol=1e-8):
        raise ValueError("reference plane normal must already be normalized")
    if data.get("unit") != "m" or not data.get("source"):
        raise ValueError("reference plane requires metric unit and source provenance")
    return normal, offset, data


def load_calibration(path: str | Path, *, quality_mode: str) -> CalibrationParameters:
    """Read the project's OpenCV calibration result without changing values."""
    source = Path(path).resolve()
    data = _load_yaml(source)
    mono0, mono1, stereo = data["mono_cam0"], data["mono_cam1"], data["stereo"]
    result = CalibrationParameters(
        k0=np.asarray(mono0["K"], dtype=np.float64),
        d0=np.asarray(mono0["D"], dtype=np.float64),
        k1=np.asarray(mono1["K"], dtype=np.float64),
        d1=np.asarray(mono1["D"], dtype=np.float64),
        r=np.asarray(stereo["R_right_from_left"], dtype=np.float64),
        t_m=np.asarray(stereo["T_right_from_left_m"], dtype=np.float64),
        approved_for_wass=bool(data.get("approved_for_wass", False)),
        source_path=source,
    )
    if result.k0.shape != (3, 3) or result.k1.shape != (3, 3):
        raise ValueError("calibration K matrices must be 3x3")
    if result.d0.shape != (5,) or result.d1.shape != (5,) or result.r.shape != (3, 3) or result.t_m.shape != (3,):
        raise ValueError("calibration D/R/T shapes are invalid")
    if not all(np.all(np.isfinite(value)) for value in (result.k0, result.d0, result.k1, result.d1, result.r, result.t_m)):
        raise ValueError("calibration values must be finite")
    if quality_mode == "require_approved" and not result.approved_for_wass:
        raise ValueError("calibration quality gate has not approved WASS reconstruction")
    return result


def _read_opencv_matrix(path: Path) -> np.ndarray:
    root = ET.parse(path).getroot()
    nodes = list(root)
    if len(nodes) != 1:
        raise ValueError(f"expected one matrix in {path}")
    node = nodes[0]
    rows, cols = int(node.findtext("rows", "0")), int(node.findtext("cols", "0"))
    values = np.fromstring(node.findtext("data", ""), sep=" ", dtype=np.float64)
    if values.size != rows * cols:
        raise ValueError(f"matrix size mismatch in {path}")
    return values.reshape(rows, cols)


def verify_wass_calibration(config_dir: Path, calibration: CalibrationParameters) -> None:
    """Require WASS XML to equal the loaded OpenCV K/D/R/T numerically."""
    expected = {
        "intrinsics_00.xml": calibration.k0,
        "distortion_00.xml": calibration.d0.reshape(-1, 1),
        "intrinsics_01.xml": calibration.k1,
        "distortion_01.xml": calibration.d1.reshape(-1, 1),
        "ext_R.xml": calibration.r,
        "ext_T.xml": calibration.t_m.reshape(-1, 1),
    }
    for name, values in expected.items():
        actual = _read_opencv_matrix(config_dir / name)
        if actual.shape != values.shape or not np.allclose(actual, values, rtol=0.0, atol=1e-12):
            raise ValueError(f"WASS fixed calibration differs from OpenCV source: {name}")


def _rotation_filter(degrees: int) -> str:
    return {0: "format=gray", 90: "transpose=1,format=gray", 180: "hflip,vflip,format=gray", 270: "transpose=2,format=gray"}[degrees]


def extract_synchronized_frames(config: ReconstructionConfig, dataset_root: Path) -> Path:
    """Extract configured timestamps without assuming equal frame indices."""
    left_dir, right_dir = dataset_root / "left", dataset_root / "right"
    metadata_dir = dataset_root / "metadata"
    for directory in (left_dir, right_dir, metadata_dir):
        directory.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for request in config.frame_requests:
        paths = (left_dir / f"{request.frame_id}.png", right_dir / f"{request.frame_id}.png")
        for video, timestamp, rotation, destination in (
            (config.left_video, request.left_timestamp_s, config.left_rotation_deg, paths[0]),
            (config.right_video, request.right_timestamp_s, config.right_rotation_deg, paths[1]),
        ):
            command = [config.ffmpeg_executable, "-hide_banner", "-loglevel", "error", "-noautorotate",
                       "-ss", f"{timestamp:.9f}", "-i", str(video), "-frames:v", "1",
                       "-vf", _rotation_filter(rotation), "-update", "1", "-y", str(destination)]
            completed = subprocess.run(command, capture_output=True, text=True, check=False, shell=False)
            if completed.returncode != 0 or not destination.is_file():
                raise RuntimeError(f"video extraction failed for {destination}: {completed.stderr.strip()}")
        records.append({
            "frame_id": request.frame_id,
            "timestamp_ns": request.timestamp_ns,
            "left_timestamp_s": request.left_timestamp_s,
            "right_timestamp_s": request.right_timestamp_s,
            "left_image": paths[0].relative_to(dataset_root).as_posix(),
            "right_image": paths[1].relative_to(dataset_root).as_posix(),
        })
    manifest = {
        "dataset_type": "real_stereo_video_wass_input_adapter",
        "orientation_status": "CANONICAL_ORIENTATION_APPLIED",
        "pairing_basis": "timestamp",
        "calibration_provenance": str(config.calibration_file),
        "frames": records,
    }
    manifest_path = metadata_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def write_xyz(path: Path, points: np.ndarray) -> None:
    """Write metric XYZ as a traceable ASCII point cloud."""
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savetxt(path, np.asarray(points, dtype=np.float64), fmt="%.9f")


def write_ply(path: Path, points: np.ndarray) -> None:
    """Write metric XYZ using the minimal ASCII PLY vertex schema."""
    values = np.asarray(points, dtype=np.float64)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="ascii", newline="\n") as stream:
        stream.write("ply\nformat ascii 1.0\n")
        stream.write(f"element vertex {values.shape[0]}\n")
        stream.write("property double x\nproperty double y\nproperty double z\nend_header\n")
        np.savetxt(stream, values, fmt="%.9f")
