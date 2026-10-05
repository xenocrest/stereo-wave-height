"""Presentation-layer orchestration. Scientific calculations stay in pipeline/."""
from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess

import cv2
import numpy as np
import yaml
from tools.camera_image import open_canonical_video, orientation_metadata

from pipeline.adapters.wass import load_matrix
from pipeline.instantaneous_validation.load_vision import load_frame
from pipeline.instantaneous_validation.schemas import PROVENANCE, ReferencePlane, reference_from_config
from pipeline.adapters.plane_contract import COORDINATE_CONTRACT

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "pipeline" / "config.example.yaml"


def new_project(name: str, output_root: str) -> dict:
    config = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    config["project"] = name
    config["output_root"] = output_root
    for block, keys in (("calibration", ("left_video", "right_video")), ("sync", ("left_video", "right_video"))):
        for key in keys:
            config[block][key] = ""
    config["wass"] = {}
    config["wass"]["allow_extrinsic_fallback"] = False
    return config


def save_project(config: dict, path: str | Path) -> None:
    Path(path).write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")


def read_project(path: str | Path) -> dict:
    config = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("Project YAML must contain a mapping")
    return config


def video_metadata(path: str | Path) -> dict:
    capture = open_canonical_video(path)
    try:
        if not capture.isOpened():
            raise ValueError(f"Cannot read video: {path}")
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        return {**orientation_metadata(capture), "width": int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
                "height": int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                "fps": fps, "frame_count": count,
                "duration_s": count / fps if fps > 0 else 0.0}
    finally:
        capture.release()


def read_preview(path: str, time_s: float) -> np.ndarray:
    capture = open_canonical_video(path)
    try:
        if not capture.isOpened():
            raise ValueError(f"Cannot read video: {path}")
        capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, time_s) * 1000.0)
        ok, frame = capture.read()
        if not ok:
            raise ValueError(f"Cannot decode at {time_s:.3f}s: {path}")
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    finally:
        capture.release()


def clean_environment() -> dict[str, str]:
    env = os.environ.copy()
    for key in list(env):
        if key.startswith(("_MEIPASS", "PYINSTALLER_", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH")):
            env.pop(key, None)
    env.pop("PYTHONHOME", None)
    return env


def command_for(action: str, config_path: Path, run_dir: Path, python: str) -> list[str]:
    return [python, "-m", "app.worker", action, str(config_path), str(run_dir)]


def run_external(command: list[str], log_path: Path) -> dict:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log:
        completed = subprocess.run(command, cwd=ROOT, env=clean_environment(),
                                   stdout=log, stderr=subprocess.STDOUT, check=False)
    if completed.returncode:
        raise RuntimeError(f"Tool: {command[0]}\nCommand: {subprocess.list2cmdline(command)}\n"
                           f"Workspace: {log_path.parent}\nReturn code: {completed.returncode}\nLog: {log_path}")
    return json.loads((log_path.parent / "result.json").read_text(encoding="utf-8"))


def _run_name() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def stage_paths(config: dict, stage: str) -> tuple[Path, Path]:
    root = Path(config["output_root"]).resolve() / str(config["project"]) / "gui"
    target = root / f"{stage}_{_run_name()}"
    if not str(target).isascii():
        raise ValueError("Scientific workspace path must use ASCII characters")
    target.mkdir(parents=True)
    snapshot = target / "project.yaml"
    save_project(config, snapshot)
    return snapshot, target


def calibration_matrices(run_dir: str | Path) -> dict:
    root = Path(run_dir) / "calibration"
    result = {name: load_matrix(root / filename).tolist() for name, filename in
              (("K_L", "intrinsics_00.xml"), ("D_L", "distortion_00.xml"),
               ("K_R", "intrinsics_01.xml"), ("D_R", "distortion_01.xml"))}
    for name, filename in (("R", "ext_R.xml"), ("T", "ext_T.xml")):
        path = root / filename
        if path.is_file():
            result[name] = load_matrix(path).tolist()
    report = root / "report.json"
    if report.is_file():
        info = json.loads(report.read_text(encoding="utf-8"))
        result["rms_px"] = info.get("rms_px", {
            camera: info.get(camera, {}).get("rms_px") for camera in ("left", "right")})
    if "T" in result:
        result["baseline"] = float(np.linalg.norm(result["T"]))
    return result


def calibration_identity(run_dir: str | Path) -> str:
    import hashlib
    root = Path(run_dir) / "wass" / "config"
    digest = hashlib.sha256()
    for filename in ("intrinsics_00.xml", "distortion_00.xml", "intrinsics_01.xml",
                     "distortion_01.xml", "ext_R.xml", "ext_T.xml"):
        digest.update(np.asarray(load_matrix(root / filename), dtype="<f8").tobytes())
    return digest.hexdigest()


def reference_from_run(run_dir: str | Path, frame_id: int = 0) -> ReferencePlane:
    from app.coordinates import bind, identity
    ids = identity(run_dir)  # Refuse legacy setup before fitting any candidate.
    with np.load(Path(run_dir) / "pixel" / "pixel_height" / f"{frame_id:08d}.npz", allow_pickle=False) as data:
        units = str(data["units"])
    if units not in {"m", "B"}:
        raise ValueError(f"Unknown scientific coordinate unit: {units}")
    plane = reference_from_config({"mode": "designated_static_water_frame",
                                  "coordinate_system": f"official_wass_grid_{units}",
                                  "reference_frame_id": frame_id}, run_dir)
    return bind(plane, ids, regenerate_id=True)


def save_reference(reference: ReferencePlane, calibration_id: str, path: str | Path,
                   scientific_run: str | Path | None = None, source_frame_id: int | None = None) -> None:
    data = reference.as_dict()
    data["calibration_identity"] = calibration_id
    if scientific_run is not None:
        data["scientific_run"] = str(Path(scientific_run).resolve())
    if source_frame_id is not None:
        data["source_frame_id"] = source_frame_id
        data["frame_id"] = source_frame_id
        if scientific_run is not None:
            from pipeline.instantaneous_validation.load_vision import frame_times
            data["timestamp"] = frame_times(scientific_run)[source_frame_id]
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_reference(path: str | Path) -> tuple[ReferencePlane, str]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return reference_from_metadata(data)


def reference_from_metadata(data: dict) -> tuple[ReferencePlane, str]:
    """Deserialize a frozen reference, without fitting or changing coefficients."""
    if data["mode"] not in {"designated_static_water_frame", "provided_physical_plane"}:
        raise ValueError("Unknown reference source mode")
    plane = ReferencePlane(data["reference_plane_id"], tuple(data["normal"]),
                           float(data["d"]), data["mode"], data["coordinate_system"])
    if (len(plane.normal) != 3 or not np.isfinite(plane.normal).all() or not np.isfinite(plane.d)
            or not np.isclose(np.linalg.norm(plane.normal), 1.0, atol=1e-6)):
        raise ValueError("Reference normal is not unit length")
    from app.coordinates import bind, identity, require_match
    ids = {key: data.get(key, "") for key in ("calibration_id", "extrinsics_id", "coordinate_frame_id")}
    ids["coordinate_system"] = plane.coordinate_system
    ids["coordinate_contract"] = data.get("coordinate_contract", "")
    if data.get("scientific_run") or any(ids[key] for key in ("calibration_id", "extrinsics_id", "coordinate_frame_id")):
        if ids["coordinate_contract"] != COORDINATE_CONTRACT:
            raise ValueError("REFERENCE_FRAME_MISMATCH: legacy reference; regenerate in certified coordinate frame")
    if all(ids[key] for key in ("calibration_id", "extrinsics_id", "coordinate_frame_id")):
        plane = bind(plane, ids)
        if data.get("scientific_run"):
            require_match(plane, identity(data["scientific_run"]))
    elif data.get("scientific_run"):
        raise ValueError("REFERENCE_FRAME_MISMATCH: incomplete reference binding; regenerate")
    return plane, data.get("calibration_identity", ids["calibration_id"])


def project_input_identity(config: dict) -> str:
    """Identity for GUI state invalidation, not a scientific calibration hash."""
    import hashlib
    inputs = {"coordinate_contract": COORDINATE_CONTRACT, "calibration": config["calibration"],
              "wave": [config["sync"].get(key, "") for key in ("left_video", "right_video")],
              "surface": config["surface"], "wass": config.get("wass", {})}
    return hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()


def validate_run_inputs(run_dir: Path, config: dict) -> None:
    sync = json.loads((run_dir / "sync" / "sync.json").read_text(encoding="utf-8"))
    for key in ("left_video", "right_video"):
        if key in sync and Path(sync[key]).resolve() != Path(config["sync"][key]).resolve():
            raise ValueError("Scientific run belongs to a different video pair; cannot display it on current inputs")


def load_result(run_dir: str | Path, frame_id: int, reference: ReferencePlane,
                expected_calibration_id: str = "") -> dict:
    from app.coordinates import identity, require_match
    actual_id = calibration_identity(run_dir)
    if expected_calibration_id and actual_id != expected_calibration_id:
        raise ValueError("REFERENCE_FRAME_MISMATCH: different active K/D/R/T; fixed height unavailable")
    ids = identity(run_dir)
    require_match(reference, ids)  # Reject BEFORE load_frame calls n^T P+d.
    result = load_frame(run_dir, frame_id, reference)
    if reference.coordinate_system != f"official_wass_grid_{result['units']}":
        raise ValueError("Reference coordinate system/units differ from this official grid")
    result["calibration_identity"] = actual_id
    result.update(ids, reference_status="MATCHED", common_stereo_region="COMMON_REGION_NOT_AVAILABLE")
    result["run_dir"] = str(run_dir)
    return result


def hover(result: dict, u: int, v: int) -> dict:
    xyz, source, height = result["xyz"], result["source"], result["height"]
    if not (0 <= u < xyz.shape[1] and 0 <= v < xyz.shape[0]):
        return {"u": u, "v": v, "provenance": "NO_DATA", "height_mm": None}
    provenance = PROVENANCE[int(source[v, u])]
    point = xyz[v, u]
    h = float(height[v, u])
    if provenance == "NO_DATA" or not np.isfinite(point).all() or not np.isfinite(h):
        return {"u": u, "v": v, "provenance": "NO_DATA", "height_mm": None}
    return {"u": u, "v": v, "X": float(point[0]), "Y": float(point[1]),
            "Z": float(point[2]), "height_native": h,
            "height_mm": h * 1000 if result["units"] == "m" else None,
            "provenance": provenance}


def measurement_image(result: dict, camera: int = 0) -> np.ndarray:
    """Read the actual WASS undistorted image, never substitute raw video."""
    path = (Path(result["run_dir"]) / "wass" / "workspaces" /
            f"{int(result['frame_id']):06d}_wd" / "undistorted" / f"{camera:08d}.png")
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR) if path.is_file() else None
    if image is None:
        raise ValueError(f"UNDISTORTED_MEASUREMENT_VIEW missing official camera image: {path}")
    if camera == 0:
        h, w = result["height"].shape
        if image.shape[1] * h != image.shape[0] * w:
            raise ValueError("Official measurement image and pixel map have different aspect/crop")
        # The official renderer may have a larger framebuffer (e.g. 1.25x).
        # Keep the complete image extent and present exactly the map raster.
        image = cv2.resize(image, (w, h), interpolation=cv2.INTER_LINEAR)
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def sync_frame_at(sync: dict, time_s: float) -> dict:
    mapping = sync.get("frame_mapping", [])
    if not mapping:
        raise ValueError("No synchronized frames")
    return min(mapping, key=lambda row: abs(float(row["left_requested_timestamp_s"]) - time_s))


def aligned_preview_times(time_s: float, right_minus_left_s: float) -> tuple[float, float]:
    return time_s, time_s + right_minus_left_s


def cache_key(config: dict, time_s: float) -> str:
    import hashlib
    inputs = {"coordinate_contract": COORDINATE_CONTRACT, "left": config["sync"]["left_video"], "right": config["sync"]["right_video"],
              "calibration": config["calibration"], "fallback": config["wass"].get("fallback_calibration"),
              "time_s": round(time_s, 6),
              "reference_time_s": config.get("_app_reference_time_s"),
              "reference_plane_id": config.get("_app_reference_plane_id"),
              "frozen_reference": {key: config.get("presentation", {}).get("frozen_reference", {}).get(key)
                  for key in ("reference_plane_id", "calibration_id", "extrinsics_id", "coordinate_frame_id")}}
    return hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()[:20]


def write_frame_manifest(run_dir: Path, selected_s: float, reference_id: str | None,
                         frame_id: int = 0) -> Path:
    sync = json.loads((run_dir / "sync" / "sync.json").read_text(encoding="utf-8"))
    row = sync["frame_mapping"][frame_id]
    target = run_dir / "frames" / f"{frame_id:06d}"
    inputs = target / "input"
    inputs.mkdir(parents=True, exist_ok=True)
    for camera, key in (("left", "left_file"), ("right", "right_file")):
        shutil.copy2(row[key], inputs / f"{camera}.png")
    metadata = {"frame_id": frame_id, "requested_time_s": selected_s,
                **{key: row.get(key) for key in ("requested_timestamp", "actual_left_source_pts", "actual_right_source_pts",
                    "left_source_frame_index", "right_source_frame_index", "TLCC_offset", "pair_residual_s", "timestamp_basis")},
                "left_timestamp_s": row.get("left_actual_timestamp_s"),
                "right_timestamp_s": row.get("right_actual_timestamp_s"),
                "delta_t_ms": row.get("stereo_pair_residual_ms"),
                "calibration_id": calibration_identity(run_dir),
                "reference_plane_id": reference_id,
                "scientific_backend_version": json.loads((run_dir / "run_report.json").read_text(encoding="utf-8")).get("git_commit"),
                "scientific_run": str(run_dir)}
    from app.coordinates import identity
    metadata.update(identity(run_dir))
    (target / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return target
