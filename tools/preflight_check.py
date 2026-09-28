"""Read-only input and tool checks before an official pipeline run."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys

import cv2
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.run_pipeline import validate_config


def _video(path: str | None) -> dict:
    if not path or not Path(path).is_file():
        return {"status": "NOT_READY", "path": path, "reason": "file missing"}
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        return {"status": "NOT_READY", "path": path, "reason": "video cannot be opened"}
    record = {"status": "READY", "path": path, "width": int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
              "height": int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)), "fps": capture.get(cv2.CAP_PROP_FPS),
              "frames": int(capture.get(cv2.CAP_PROP_FRAME_COUNT))}
    capture.release()
    record["duration_s"] = record["frames"] / record["fps"] if record["fps"] > 0 else None
    if not record["width"] or not record["height"] or not record["fps"] or not record["frames"]:
        record.update(status="NOT_READY", reason="invalid video metadata")
    return record


def _audio(ffmpeg: str | None, video: str | None) -> dict:
    if not ffmpeg or not video or not Path(ffmpeg).is_file() or not Path(video).is_file():
        return {"status": "NOT_READY", "reason": "FFmpeg or video missing"}
    command = [ffmpeg, "-hide_banner", "-i", video]
    result = subprocess.run(command, capture_output=True, text=True, errors="replace", timeout=20)
    exists = "Audio:" in (result.stderr + result.stdout)
    return {"status": "READY" if exists else "NOT_READY", "audio_track": exists, "path": video}


def check(config_path: str | Path) -> dict:
    source = Path(config_path)
    config = yaml.safe_load(source.read_text(encoding="utf-8"))
    items = {}
    try:
        validate_config(config)
        items["pipeline_yaml"] = {"status": "READY"}
    except Exception as exc:
        items["pipeline_yaml"] = {"status": "NOT_READY", "reason": str(exc)}
    tools = config.get("tools", {})
    for key in ("python", "ffmpeg", "praat", "wass_source", "wass_lowcost"):
        path = tools.get(key)
        items[f"tool_{key}"] = {"status": "READY" if path and Path(path).exists() else "NOT_READY", "path": path}
    for key in ("wass_prepare", "wass_match", "wass_autocalibrate", "wass_stereo"):
        path = Path(tools.get("wass_bin", "")) / f"{key}.exe"
        items[key] = {"status": "READY" if path.is_file() else "NOT_READY", "path": str(path)}
    python = Path(tools.get("python", ""))
    for key in ("wassgridsurface", "wassncplot"):
        path = python.parent / f"{key}.exe"
        items[key] = {"status": "READY" if path.is_file() else "NOT_READY", "path": str(path)}
    if python.is_file():
        command = [str(python), "-c", "import cv2; print(cv2.__version__)"]
        version = subprocess.run(command, capture_output=True, text=True, timeout=20)
        items["python_opencv"] = {"status": "READY" if version.returncode == 0 else "NOT_READY",
                                   "version": version.stdout.strip(), "error": version.stderr.strip()[:500]}
    else:
        items["python_opencv"] = {"status": "NOT_READY"}
    if config.get("source_type") == "stereo_video":
        for group, keys in (("calibration", ("left_video", "right_video")),
                            ("sync", ("left_video", "right_video"))):
            for key in keys:
                name = f"{group}_{key}"
                path = config.get(group, {}).get(key)
                items[name] = _video(path)
                if group == "sync":
                    items[name + "_audio"] = _audio(tools.get("ffmpeg"), path)
        for side in ("left", "right"):
            calibration_video = items[f"calibration_{side}_video"]
            measurement_video = items[f"sync_{side}_video"]
            compatible = (calibration_video["status"] == measurement_video["status"] == "READY"
                          and (calibration_video["width"], calibration_video["height"])
                          == (measurement_video["width"], measurement_video["height"]))
            items[f"camera_mode_{side}"] = {"status": "READY" if compatible else "NOT_READY",
                                             "reason": "calibration and wave resolutions must match; lens/zoom/focus must also be checked manually"}
    board = config.get("calibration", {}).get("checkerboard", {})
    for key in ("rows", "columns", "square_size_m"):
        value = board.get(key)
        items[f"checkerboard_{key}"] = {"status": "READY" if isinstance(value, (int, float)) and value > 0 else "NOT_READY",
                                        "value": value}
    baseline = config.get("surface", {}).get("baseline_m")
    nominal = config.get("camera", {}).get("nominal_baseline_mm")
    items["baseline"] = {"status": "READY" if isinstance(baseline, (int, float)) and baseline > 0
                         and isinstance(nominal, (int, float)) and nominal > 0
                         and abs(baseline * 1000 - nominal) < 1e-6 else "NOT_READY",
                         "surface_m": baseline, "nominal_mm": nominal}
    truth = config.get("truth", {})
    for key in ("data_file", "sensor_layout", "sync_file"):
        path = truth.get(key)
        items[f"truth_{key}"] = {"status": "READY" if path and Path(path).is_file() else "NOT_READY", "path": path}
    if items["truth_data_file"]["status"] == "READY":
        try:
            with Path(truth["data_file"]).open(encoding="utf-8-sig", newline="") as stream:
                header = set(csv.DictReader(stream).fieldnames or [])
            expected = {"timestamp", "sensor_id", "x", "y", "quality_flag"}
            valid = expected.issubset(header) and ("H_true_mm" in header and "reference_plane_id" in header
                                                     or "Z_true_mm" in header and "coordinate_system" in header)
            items["truth_csv_schema"] = {"status": "READY" if valid else "NOT_READY", "columns": sorted(header)}
        except Exception as exc:
            items["truth_csv_schema"] = {"status": "NOT_READY", "reason": str(exc)}
    else:
        items["truth_csv_schema"] = {"status": "NOT_READY", "reason": "truth CSV missing"}
    if items["truth_sensor_layout"]["status"] == "READY":
        try:
            layout = yaml.safe_load(Path(truth["sensor_layout"]).read_text(encoding="utf-8"))
            sensors = layout["sensors"]
            valid = layout.get("coordinate_system") == config.get("reference", {}).get("coordinate_system") and bool(sensors) and all(sensor.get("id") and all(
                isinstance(sensor.get(key), (float, int)) for key in ("x_mm", "y_mm")) for sensor in sensors)
            items["truth_layout_schema"] = {"status": "READY" if valid else "NOT_READY", "sensor_count": len(sensors)}
        except Exception as exc:
            items["truth_layout_schema"] = {"status": "NOT_READY", "reason": str(exc)}
    else:
        items["truth_layout_schema"] = {"status": "NOT_READY", "reason": "sensor layout missing"}
    if items["truth_sync_file"]["status"] == "READY":
        try:
            recorded = yaml.safe_load(Path(truth["sync_file"]).read_text(encoding="utf-8"))["truth_sync"]
            valid = (recorded.get("method") == "provided_offset"
                     and isinstance(recorded.get("offset_ms"), (float, int))
                     and bool(recorded.get("source"))
                     and recorded.get("source") != "TBD_AFTER_HARDWARE_ARRIVAL")
            items["truth_sync_schema"] = {"status": "READY" if valid else "NOT_READY", "method": recorded.get("method")}
        except Exception as exc:
            items["truth_sync_schema"] = {"status": "NOT_READY", "reason": str(exc)}
    else:
        items["truth_sync_schema"] = {"status": "NOT_READY", "reason": "truth sync missing"}
    ref = config.get("reference", {})
    mode = ref.get("mode")
    ready = bool(ref.get("coordinate_system")) and (mode == "designated_static_water_frame" and isinstance(ref.get("reference_frame_id"), int)
             or mode == "provided_physical_plane" and all(isinstance(ref.get(k), (float, int)) for k in ("n_x", "n_y", "n_z", "d")))
    if ready and mode == "provided_physical_plane":
        ready = sum(float(ref[key]) ** 2 for key in ("n_x", "n_y", "n_z")) > 0
    items["reference"] = {"status": "READY" if ready else "NOT_READY", "mode": mode}
    gates = config.get("validation", {})
    gate_valid = all(isinstance(gates.get(key), (float, int)) and gates[key] >= 0
                     for key in ("max_time_difference_ms", "max_spatial_distance_mm", "max_stereo_time_difference_ms"))
    items["validation_gates"] = {"status": "READY" if gate_valid else "NOT_READY", "values": gates}
    output_root = Path(config.get("output_root") or config.get("output", {}).get("run_root") or "")
    parent = output_root if output_root.is_dir() else output_root.parent
    free = shutil.disk_usage(parent).free if parent.is_dir() else 0
    items["output_disk"] = {"status": "READY" if free > 1_000_000_000 else "NOT_READY",
                            "path": str(output_root)}
    return {"status": "READY_FOR_PIPELINE" if all(item["status"] == "READY" for item in items.values()) else "NOT_READY",
            "checks": items}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config")
    args = parser.parse_args()
    result = check(args.config)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["status"] == "READY_FOR_PIPELINE" else 2)


if __name__ == "__main__":
    main()
