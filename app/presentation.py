"""Display/export helpers only; never alter frozen scientific results."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys

import cv2
import numpy as np
from plyfile import PlyData

from app import core


def rectangle_mask(shape: tuple[int, int], normalized: tuple[float, float, float, float] | None) -> np.ndarray:
    h, w = shape
    if normalized is None:
        return np.ones((h, w), dtype=bool)
    x0, y0, x1, y1 = normalized
    left, right = sorted((max(0, min(w, round(x0 * w))), max(0, min(w, round(x1 * w)))))
    top, bottom = sorted((max(0, min(h, round(y0 * h))), max(0, min(h, round(y1 * h)))))
    mask = np.zeros((h, w), dtype=bool)
    mask[top:bottom, left:right] = True
    return mask


def point_in_rectangle(u: int, v: int, shape: tuple[int, int], normalized: tuple | None) -> bool:
    if normalized is None:
        return True
    h, w = shape
    x0, y0, x1, y1 = normalized
    return x0 <= u / w < x1 and y0 <= v / h < y1


def save_rgb(path: Path, rgb: np.ndarray) -> None:
    encoded = cv2.imencode(".png", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))[1]
    encoded.tofile(str(path))


def export_current_frame(destination: str | Path, result: dict, raw_rgb: np.ndarray,
                         overlay_rgb: np.ndarray, ply: Path, reference, region: tuple | None) -> dict:
    """Export only already-computed official values; ROI is a presentation filter."""
    folder = Path(destination)
    folder.mkdir(parents=True, exist_ok=True)
    run = Path(result["run_dir"])
    frame_id = int(result["frame_id"])
    row = json.loads((run / "sync" / "sync.json").read_text(encoding="utf-8"))["frame_mapping"][frame_id]
    wass = json.loads((run / "wass" / "run_summary.json").read_text(encoding="utf-8"))
    source = result["source"]
    available = (source != 0) & np.isfinite(result["height"]) & np.isfinite(result["xyz"]).all(axis=2)
    selected = available & rectangle_mask(source.shape, region)
    save_rgb(folder / "current_frame.png", raw_rgb)
    save_rgb(folder / "measurement_frame.png", core.measurement_image(result))
    save_rgb(folder / "overlay.png", overlay_rgb)
    shutil.copy2(ply, folder / "pointcloud.ply")
    with (folder / "instantaneous_height.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("u", "v", "X", "Y", "Z", "H_native", "H_mm", "provenance"))
        for v, u in np.argwhere(selected):
            x, y, z = result["xyz"][v, u]
            h = float(result["height"][v, u])
            writer.writerow((int(u), int(v), float(x), float(y), float(z), h,
                             h * 1000 if result["units"] == "m" else "", core.PROVENANCE[int(source[v, u])]))
    metadata_out = {
        "frame_id": frame_id, "timestamp_s": float(result["timestamp_s"]),
        **{key: row.get(key) for key in ("requested_timestamp", "actual_left_source_pts", "actual_right_source_pts",
            "left_source_frame_index", "right_source_frame_index", "TLCC_offset", "pair_residual_s", "timestamp_basis")},
        "left_actual_timestamp_s": row.get("left_actual_timestamp_s"),
        "right_actual_timestamp_s": row.get("right_actual_timestamp_s"),
        "stereo_pair_residual_ms": row.get("stereo_pair_residual_ms"),
        "sync_offset_right_minus_left_s": json.loads((run / "sync" / "sync.json").read_text(encoding="utf-8")).get("audio_lag_right_minus_left_s"),
        "calibration_id": result["calibration_identity"],
        "extrinsics_id": result.get("extrinsics_id"),
        "coordinate_frame_id": result.get("coordinate_frame_id"),
        "reference_status": result.get("reference_status", "UNBOUND"),
        "calibration_source": "EXTRINSICS_FALLBACK" if wass["active_calibration"]["fallback"] else "EXTRINSICS_COMPUTED",
        "reference_plane_id": reference.plane_id,
        "reference_source": ("INTERNAL_STATIC_REFERENCE" if reference.mode == "designated_static_water_frame"
                             else "PROVIDED_PHYSICAL_REFERENCE"),
        "reference_mode": reference.mode,
        "reference_coordinate_system": reference.coordinate_system,
        "wass_point_count": int(len(PlyData.read(ply)["vertex"].data)),
        "mapped_pixel_count": int(np.count_nonzero(available)),
        "exported_pixel_count": int(np.count_nonzero(selected)),
        "measurement_region_source": "USER_RECTANGLE" if region is not None else "NONE",
        "measurement_region_normalized": region,
        "common_stereo_region": "COMMON_REGION_NOT_AVAILABLE",
        "height_available_region": "finite official pixel XYZ/H and nonzero provenance",
        "science_run": str(run), "units": result["units"],
        "raw_image_size_wh": [raw_rgb.shape[1], raw_rgb.shape[0]],
        "official_mapping_size_wh": [source.shape[1], source.shape[0]],
        "csv_pixel_coordinate_system": "official wassncplot pixel mapping",
        "overlay_coordinate_system": "UNDISTORTED_MEASUREMENT_VIEW: official WASS undistorted cam0, complete extent at map raster size",
        "measurement_image_size_wh": [source.shape[1], source.shape[0]],
        "raw_image_coordinate_system": "RAW_CAMERA_IMAGE; undistorted height hover disabled",
        "pointcloud_coordinate_system": "unchanged official WASS PLY; not the aligned metric grid XYZ in CSV",
        "note": "ROI affects presentation/export only; no WASS input or scientific output was modified.",
    }
    (folder / "metadata.json").write_text(json.dumps(metadata_out, ensure_ascii=False, indent=2), encoding="utf-8")
    return metadata_out


def toolchain(config: dict) -> list[dict]:
    """Read-only local checks, with bounded version probes."""
    tools = config.get("tools", {})
    def row(name: str, path: str, version: str = "unknown") -> dict:
        present = Path(path).is_file() if path else False
        return {"name": name, "path": path, "version": version, "status": "READY" if present else "NOT_READY"}
    python = tools.get("python", sys.executable)
    entries = [row("Python", python),
               {"name": "OpenCV", "path": python + " / cv2", "version": "unknown", "status": "NOT_READY"},
               row("FFmpeg", tools.get("ffmpeg", "")),
               row("Praat", tools.get("praat", "")),
               row("WASS", str(Path(tools.get("wass_bin", "")) / "wass_stereo.exe"))]
    if any(not (Path(tools.get("wass_bin", "")) / name).is_file() for name in
           ("wass_prepare.exe", "wass_match.exe", "wass_autocalibrate.exe", "wass_stereo.exe")):
        entries[4]["status"] = "NOT_READY"
    for name in ("wassgridsurface", "wassncplot"):
        entries.append({"name": name, "path": python + " / " + name,
                        "version": "unknown", "status": "NOT_READY"})
    if entries[0]["status"] == "READY":
        probe = ("import sys,json,importlib.util; from importlib import metadata; "
                 "names=['opencv-python','wassgridsurface','wassncplot']; "
                 "print(json.dumps({'python':sys.version.split()[0], "
                 "'cv2_path':getattr(importlib.util.find_spec('cv2'),'origin',None), "
                 "'versions':{n:metadata.version(n) for n in names if any(d.metadata['Name'].lower()==n for d in metadata.distributions())}}))")
        try:
            proc = subprocess.run([python, "-c", probe], capture_output=True, text=True, timeout=10,
                                  env=core.clean_environment(), check=False)
            info = json.loads(proc.stdout)
            entries[0]["version"] = info["python"]
            versions = info["versions"]
            for entry, package in ((entries[1], "opencv-python"), (entries[5], "wassgridsurface"),
                                   (entries[6], "wassncplot")):
                if package in versions:
                    entry.update(version=versions[package], status="READY")
            if info.get("cv2_path"):
                entries[1]["path"] = info["cv2_path"]
        except (OSError, ValueError, subprocess.TimeoutExpired):
            entries[0].update(version="probe failed", status="NOT_READY")
    ffmpeg = entries[2]
    if ffmpeg["status"] == "READY":
        try:
            proc = subprocess.run([ffmpeg["path"], "-version"], capture_output=True, text=True, timeout=5,
                                  env=core.clean_environment(), check=False)
            ffmpeg["version"] = proc.stdout.splitlines()[0][:120] if proc.stdout else "unknown"
        except (OSError, subprocess.TimeoutExpired):
            ffmpeg["version"] = "unavailable"
    for entry, args in ((entries[3], ["--version"]), (entries[4], ["--version"])):
        if entry["status"] != "READY":
            continue
        try:
            proc = subprocess.run([entry["path"], *args], capture_output=True, timeout=5,
                                  env=core.clean_environment(), check=False)
            first = proc.stdout.splitlines()[0] if proc.stdout else b""
            if b"\x00" in first:
                decoded = proc.stdout.decode("utf-16-le", errors="replace")
            else:
                decoded = proc.stdout.decode("utf-8", errors="replace")
            entry["version"] = decoded.splitlines()[0][:120] if decoded else "unknown"
        except (OSError, subprocess.TimeoutExpired):
            entry["version"] = "unavailable"
    return entries
