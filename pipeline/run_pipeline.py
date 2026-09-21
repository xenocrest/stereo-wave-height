from __future__ import annotations

import argparse
from datetime import datetime, timezone
import glob
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml

from pipeline.adapters import calibration, surface, sync, wass
from pipeline.common import CommandRecorder, StageFailure, require_empty, sha256, write_json
from pipeline.visualization.view_results import build as build_visualization


def load_config(path: str | Path) -> dict[str, Any]:
    source = Path(path).resolve()
    config = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("project YAML must contain a mapping")
    validate_config(config)
    config["_config_path"] = str(source)
    return config


def validate_config(config: dict[str, Any]) -> None:
    required = {"project", "source_type", "output_root", "tools", "calibration", "sync", "wass", "surface"}
    missing = sorted(required - set(config))
    if missing:
        raise ValueError(f"missing project config keys: {', '.join(missing)}")
    if config["source_type"] not in {"stereo_video", "synchronized_image_sequence"}:
        raise ValueError("source_type must be stereo_video or synchronized_image_sequence")
    if config["source_type"] == "stereo_video":
        for key in ("left_video", "right_video"):
            if key not in config["sync"]:
                raise ValueError(f"sync.{key} is required for stereo_video")
    else:
        for key in ("left_images", "right_images", "fps"):
            if key not in config["sync"]:
                raise ValueError(f"sync.{key} is required for synchronized_image_sequence")
    if float(config["surface"].get("baseline_m", 0)) <= 0:
        raise ValueError("surface.baseline_m must be positive; use 1 only for an explicitly baseline-normalized author sample")


def _run_directory(config: dict[str, Any], explicit: str | None) -> Path:
    if explicit:
        return require_empty(Path(explicit).resolve())
    timestamp = datetime.now().strftime("run_%Y%m%d_%H%M%S")
    path = Path(config["output_root"]).resolve() / str(config["project"]) / timestamp
    if not str(path).isascii():
        raise ValueError("WASS run directory must use an ASCII-only path")
    return require_empty(path)


def _input_files(config: dict[str, Any]) -> list[Path]:
    result: list[Path] = []
    cal = config["calibration"]
    for key in ("left_video", "right_video"):
        if cal.get(key):
            result.append(Path(cal[key]).resolve())
    if cal.get("config_path"):
        result.extend(path for path in Path(cal["config_path"]).resolve().iterdir() if path.is_file())
    sync_config = config["sync"]
    for key in ("left_video", "right_video"):
        if sync_config.get(key):
            result.append(Path(sync_config[key]).resolve())
    for key in ("left_images", "right_images"):
        if sync_config.get(key):
            result.extend(Path(item).resolve() for item in sorted(glob.glob(sync_config[key])))
    fallback = config["wass"].get("fallback_calibration")
    if fallback:
        result.extend(path for path in Path(fallback["path"]).resolve().iterdir() if path.is_file())
        for key in ("matcher_config", "stereo_config"):
            if fallback.get(key):
                result.append(Path(fallback[key]).resolve())
    unique = []
    seen = set()
    for path in result:
        if path not in seen:
            if not path.is_file():
                raise FileNotFoundError(path)
            seen.add(path)
            unique.append(path)
    return unique


def _tool_snapshot(tools: dict[str, Any], recorder: CommandRecorder) -> dict[str, Any]:
    snapshot = {key: str(Path(value).resolve()) for key, value in tools.items()}
    recorder.run("version_python", [tools["python"], "-c", "import cv2,numpy,scipy,yaml,plotly,importlib.metadata as m; print('OpenCV',cv2.__version__); print('numpy',numpy.__version__); print('scipy',scipy.__version__); print('PyYAML',yaml.__version__); print('plotly',plotly.__version__); print('wassgridsurface',m.version('wassgridsurface')); print('wassncplot',m.version('wassncplot'))"])
    recorder.run("version_ffmpeg", [tools["ffmpeg"], "-version"])
    recorder.run("version_wass", [Path(tools["wass_bin"]) / "wass_stereo.exe"], check=False)
    for key in ("python", "ffmpeg", "praat"):
        if key in tools and Path(tools[key]).is_file():
            snapshot[key + "_sha256"] = sha256(tools[key])
    wass_stereo = Path(tools["wass_bin"]) / "wass_stereo.exe"
    snapshot["wass_stereo_sha256"] = sha256(wass_stereo)
    for key in ("wass_source", "wass_lowcost"):
        if key in tools:
            root = Path(tools[key]).resolve()
            files = sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in {".py", ".c", ".cpp", ".h", ".hpp"})
            snapshot[key + "_source_hashes"] = {str(path): sha256(path) for path in files}
    return snapshot


def run_pipeline(config_path: str | Path, explicit_run_dir: str | None = None) -> dict[str, Any]:
    config = load_config(config_path)
    repo_root = Path(__file__).resolve().parents[1]
    run_dir = _run_directory(config, explicit_run_dir)
    logs = run_dir / "logs" / "pipeline"
    recorder = CommandRecorder(logs)
    started = time.perf_counter()
    snapshot = {key: value for key, value in config.items() if not key.startswith("_")}
    (run_dir / "config_snapshot.yaml").write_text(yaml.safe_dump(snapshot, allow_unicode=True, sort_keys=False), encoding="utf-8")
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "project": config["project"],
        "source_type": config["source_type"],
        "run_directory": str(run_dir),
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "status": "RUNNING",
        "third_party_algorithm_modifications": 0,
        "stages": {},
    }
    current_stage = "toolchain"
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True, check=True).stdout.strip()
        report["git_commit"] = commit
        report["git_dirty"] = bool(subprocess.run(["git", "status", "--porcelain"], cwd=repo_root, capture_output=True, text=True, check=True).stdout.strip())
        report["pipeline_source_hashes"] = {
            str(path.relative_to(repo_root)): sha256(path)
            for path in sorted((repo_root / "pipeline").rglob("*.py"))
        }
        report["input_hashes"] = {str(path): sha256(path) for path in _input_files(config)}
        report["toolchain"] = _tool_snapshot(config["tools"], recorder)

        current_stage = "calibration"
        report["stages"]["calibration"] = calibration.run(config["calibration"], config["tools"], run_dir, repo_root, recorder)
        current_stage = "sync"
        report["stages"]["sync"] = sync.run(config["source_type"], config["sync"], config["tools"], run_dir, repo_root, recorder)
        current_stage = "wass"
        report["stages"]["wass"] = wass.run(config["wass"], config["tools"], run_dir, recorder)
        current_stage = "surface"
        report["stages"]["surface"] = surface.run(config["surface"], config["tools"], report["stages"]["sync"], run_dir, recorder)
        current_stage = "visualization"
        report["stages"]["visualization"] = build_visualization(run_dir)
        report["status"] = config.get("pass_status", "PIPELINE_PASS")
    except Exception as error:
        failed_stage = error.stage if isinstance(error, StageFailure) else current_stage
        report["status"] = "FAILED_AT_" + failed_stage.upper()
        report["error"] = {"type": type(error).__name__, "message": str(error), "traceback": traceback.format_exc()}
    finally:
        report["elapsed_s"] = time.perf_counter() - started
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        report["commands"] = recorder.calls
        write_json(run_dir / "run_report.json", report)
        write_json(run_dir / "logs" / "commands.json", recorder.calls)
    if report["status"].startswith("FAILED_AT_"):
        raise RuntimeError(f"{report['status']}: {report['error']['type']}: {report['error']['message']}\nreport: {run_dir / 'run_report.json'}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the unmodified Vieira/WASS scientific workflow")
    parser.add_argument("config", help="project YAML")
    parser.add_argument("--run-dir", help="explicit empty ASCII output directory")
    args = parser.parse_args()
    report = run_pipeline(args.config, args.run_dir)
    print(json.dumps({"status": report["status"], "run_directory": report["run_directory"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
