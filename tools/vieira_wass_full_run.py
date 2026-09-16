"""Orchestrate an isolated official WASS prepare/match/autocalibrate/stereo run.

No WASS algorithm is reimplemented.  Every numerical stage is delegated to
the unmodified official executables; this wrapper creates fresh directories,
captures logs/timings, and summarizes their outputs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import time

import cv2
import numpy as np


def command(command_line: list[str], log: Path) -> dict[str, object]:
    started = time.perf_counter()
    completed = subprocess.run(command_line, text=True, capture_output=True, encoding="utf-8", errors="replace")
    elapsed = time.perf_counter() - started
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(
        "COMMAND: " + subprocess.list2cmdline(command_line) + "\n"
        + f"RETURN_CODE: {completed.returncode}\nELAPSED_S: {elapsed:.6f}\n\nSTDOUT\n{completed.stdout}\n\nSTDERR\n{completed.stderr}\n",
        encoding="utf-8",
    )
    return {"return_code": completed.returncode, "elapsed_s": elapsed, "log": str(log)}


def load_matrix(path: Path) -> np.ndarray:
    storage = cv2.FileStorage(str(path), cv2.FILE_STORAGE_READ)
    if not storage.isOpened():
        raise RuntimeError(f"cannot open OpenCV XML matrix: {path}")
    value = storage.getFirstTopLevelNode().mat()
    storage.release()
    if value is None or not np.all(np.isfinite(value)):
        raise RuntimeError(f"invalid matrix: {path}")
    return value


def run(args: argparse.Namespace) -> dict[str, object]:
    sync = Path(args.sync).resolve()
    output = Path(args.output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"refusing to reuse non-empty WASS run directory: {output}")
    config, workspaces, logs = output / "config", output / "workspaces", output / "logs"
    config.mkdir(parents=True)
    workspaces.mkdir()
    logs.mkdir()

    shutil.copy2(Path(args.cam0_intrinsics), config / "intrinsics_00.xml")
    shutil.copy2(Path(args.cam0_distortion), config / "distortion_00.xml")
    shutil.copy2(Path(args.cam1_intrinsics), config / "intrinsics_01.xml")
    shutil.copy2(Path(args.cam1_distortion), config / "distortion_01.xml")
    shutil.copy2(Path(args.matcher_config), config / "matcher_config.txt")
    shutil.copy2(Path(args.stereo_config), config / "stereo_config.txt")

    left = sorted((sync / "cam0").glob("*.png"))
    right = sorted((sync / "cam1").glob("*.png"))
    if not left or len(left) != len(right) or [item.name for item in left] != [item.name for item in right]:
        raise ValueError("fresh synchronized cam0/cam1 PNG sets are empty or unequal")

    prepare_exe = str(Path(args.wass_bin) / "wass_prepare.exe")
    match_exe = str(Path(args.wass_bin) / "wass_match.exe")
    autocal_exe = str(Path(args.wass_bin) / "wass_autocalibrate.exe")
    stereo_exe = str(Path(args.wass_bin) / "wass_stereo.exe")
    stages: dict[str, object] = {"prepare": [], "match": [], "stereo": []}
    workspace_paths = []
    for index, (left_image, right_image) in enumerate(zip(left, right)):
        workspace = workspaces / f"{index:06d}_wd"
        workspace_paths.append(workspace)
        result = command(
            [prepare_exe, "--workdir", str(workspace), "--calibdir", str(config), "--c0", str(left_image), "--c1", str(right_image)],
            logs / f"prepare_{index:06d}.log",
        )
        result.update({"index": index, "workspace": str(workspace)})
        stages["prepare"].append(result)
        if result["return_code"] != 0:
            raise RuntimeError(f"WASS prepare failed for frame {index}; see {result['log']}")

    for index, workspace in enumerate(workspace_paths):
        result = command([match_exe, str(config / "matcher_config.txt"), str(workspace)], logs / f"match_{index:06d}.log")
        result.update({"index": index, "workspace": str(workspace)})
        stages["match"].append(result)

    matched = [workspace for workspace, result in zip(workspace_paths, stages["match"]) if result["return_code"] == 0 and (workspace / "matcher_stats.csv").exists() and (workspace / "matches.txt").exists()]
    if not matched:
        raise RuntimeError("no WASS match workspace succeeded")
    workspaces_file = output / "workspaces.txt"
    workspaces_file.write_text("\n".join(str(path) for path in matched) + "\n", encoding="utf-8")
    autocal = command([autocal_exe, str(workspaces_file)], logs / "autocalibrate.log")
    stages["autocalibrate"] = autocal
    if autocal["return_code"] != 0:
        raise RuntimeError(f"WASS autocalibrate failed; see {autocal['log']}")

    rotation = load_matrix(matched[0] / "ext_R.xml")
    translation = load_matrix(matched[0] / "ext_T.xml").reshape(3)
    for index, workspace in enumerate(workspace_paths):
        if not (workspace / "ext_R.xml").exists() or not (workspace / "ext_T.xml").exists():
            continue
        result = command([stereo_exe, str(config / "stereo_config.txt"), str(workspace)], logs / f"stereo_{index:06d}.log")
        result.update({"index": index, "workspace": str(workspace)})
        stages["stereo"].append(result)

    frames = []
    for index, workspace in enumerate(workspace_paths):
        mesh = workspace / "mesh_cam.xyzC"
        plane = workspace / "plane.txt"
        frames.append(
            {
                "index": index,
                "workspace": str(workspace),
                "match_succeeded": workspace in matched,
                "mesh_exists": mesh.exists(),
                "mesh_bytes": mesh.stat().st_size if mesh.exists() else 0,
                "plane_exists": plane.exists(),
                "plane_text": plane.read_text(encoding="utf-8", errors="replace").strip() if plane.exists() else None,
            }
        )
    summary = {
        "schema_version": "1.0",
        "status": "COMPLETE" if any(frame["mesh_exists"] for frame in frames) else "BLOCKED_AT_OFFICIAL_STEREO",
        "pipeline": "official WASS prepare -> match -> autocalibrate -> stereo",
        "source_sync_directory": str(sync),
        "workspace_count": len(workspace_paths),
        "successful_match_count": len(matched),
        "autocalibration_rotation_right_from_left": rotation.tolist(),
        "autocalibration_translation_unit_baseline": translation.tolist(),
        "autocalibration_translation_norm": float(np.linalg.norm(translation)),
        "metric_baseline_m_for_later_official_gridding": args.baseline_m,
        "stages": stages,
        "frames": frames,
        "historical_workspace_or_extrinsics_reused": False,
    }
    (output / "run_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sync", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--cam0-intrinsics", required=True)
    parser.add_argument("--cam0-distortion", required=True)
    parser.add_argument("--cam1-intrinsics", required=True)
    parser.add_argument("--cam1-distortion", required=True)
    parser.add_argument("--wass-bin", required=True)
    parser.add_argument("--matcher-config", required=True)
    parser.add_argument("--stereo-config", required=True)
    parser.add_argument("--baseline-m", type=float, required=True)
    args = parser.parse_args()
    summary = run(args)
    print(json.dumps({key: summary[key] for key in ("workspace_count", "successful_match_count", "autocalibration_translation_norm")}, indent=2))


if __name__ == "__main__":
    main()
