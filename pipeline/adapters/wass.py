from __future__ import annotations

from pathlib import Path
import shutil
from typing import Any

import cv2
import numpy as np

from pipeline.common import CommandRecorder, StageFailure, copy_file, sha256, write_json


CALIBRATION_FILES = (
    "intrinsics_00.xml",
    "distortion_00.xml",
    "intrinsics_01.xml",
    "distortion_01.xml",
    "ext_R.xml",
    "ext_T.xml",
)


def load_matrix(path: Path) -> np.ndarray:
    storage = cv2.FileStorage(str(path), cv2.FILE_STORAGE_READ)
    if not storage.isOpened():
        raise ValueError(f"cannot open OpenCV XML: {path}")
    value = storage.getFirstTopLevelNode().mat()
    storage.release()
    if value is None or not np.all(np.isfinite(value)):
        raise ValueError(f"invalid OpenCV XML matrix: {path}")
    return value


def _pairs(sync_dir: Path) -> list[tuple[Path, Path]]:
    left = sorted(path for path in (sync_dir / "frames" / "cam0").iterdir() if path.is_file())
    right = sorted(path for path in (sync_dir / "frames" / "cam1").iterdir() if path.is_file())
    if not left or len(left) != len(right):
        raise ValueError("synchronized left/right frame sets are empty or unequal")
    return list(zip(left, right))


def _prepare(
    pairs: list[tuple[Path, Path]],
    workspaces: Path,
    config: Path,
    wass_bin: Path,
    recorder: CommandRecorder,
    prefix: str,
) -> list[Path]:
    result = []
    workspaces.mkdir(parents=True, exist_ok=True)
    for index, (left, right) in enumerate(pairs):
        workspace = workspaces / f"{index:06d}_wd"
        recorder.run(
            f"{prefix}_prepare_{index:06d}",
            [wass_bin / "wass_prepare.exe", "--workdir", workspace, "--calibdir", config, "--c0", left, "--c1", right],
        )
        result.append(workspace)
    return result


def _copy_config(source: Path, target: Path, include_extrinsics: bool) -> None:
    names = ["intrinsics_00.xml", "distortion_00.xml", "intrinsics_01.xml", "distortion_01.xml", "matcher_config.txt", "stereo_config.txt"]
    if include_extrinsics:
        names.extend(["ext_R.xml", "ext_T.xml"])
    target.mkdir(parents=True, exist_ok=True)
    for name in names:
        copy_file(source / name, target / name)


def _ensure_ply(stereo_config: Path) -> None:
    text = stereo_config.read_text(encoding="utf-8", errors="replace")
    if not any(line.strip().lower() == "save_as_ply=true" for line in text.splitlines()):
        with stereo_config.open("a", encoding="ascii") as stream:
            stream.write("\n# Pipeline requests an official PLY output; reconstruction logic is unchanged.\nSAVE_AS_PLY=true\n")


def run(
    config: dict[str, Any],
    tools: dict[str, Any],
    run_dir: Path,
    recorder: CommandRecorder,
) -> dict[str, Any]:
    output = run_dir / "wass"
    output.mkdir(parents=True, exist_ok=True)
    active_config = output / "config"
    calibration = run_dir / "calibration"
    _copy_config(calibration, active_config, include_extrinsics=False)
    pairs = _pairs(run_dir / "sync")
    wass_bin = Path(tools["wass_bin"])

    # Always perform the official prepare -> match -> autocalibrate attempt.
    auto_workspaces = _prepare(pairs, output / "autocalibration_workspaces", active_config, wass_bin, recorder, "autocal")
    for index, workspace in enumerate(auto_workspaces):
        recorder.run(
            f"match_{index:06d}",
            [wass_bin / "wass_match.exe", active_config / "matcher_config.txt", workspace],
        )
        if not (workspace / "matches.txt").is_file():
            raise StageFailure("match", f"official match output missing: {workspace / 'matches.txt'}")
    listing = output / "autocalibration_workspaces.txt"
    listing.write_text("\n".join(str(path) for path in auto_workspaces) + "\n", encoding="utf-8")
    recorder.run("autocalibrate", [wass_bin / "wass_autocalibrate.exe", listing])
    for name in ("ext_R.xml", "ext_T.xml"):
        if not (auto_workspaces[0] / name).is_file():
            raise StageFailure("autocalibrate", f"official autocalibration output missing: {name}")

    attempted = calibration / "attempted_autocalibration"
    attempted.mkdir(exist_ok=True)
    for name in ("ext_R.xml", "ext_T.xml"):
        copy_file(auto_workspaces[0] / name, attempted / name)
    attempted_r = load_matrix(attempted / "ext_R.xml")
    attempted_t = load_matrix(attempted / "ext_T.xml").reshape(3)

    fallback = config.get("fallback_calibration")
    fallback_used = bool(fallback and fallback.get("mode") == "after_autocalibration_attempt")
    if fallback_used:
        fallback_source = Path(fallback["path"]).resolve()
        # The complete six-file calibration is switched as one traceable bundle.
        # New K/D are never combined with historical R/T.
        shutil.rmtree(active_config)
        _copy_config(fallback_source, active_config, include_extrinsics=True)
        fallback_hashes = {name: sha256(fallback_source / name) for name in CALIBRATION_FILES}
        for name in CALIBRATION_FILES:
            copy_file(active_config / name, calibration / name)
        if fallback.get("matcher_config"):
            copy_file(fallback["matcher_config"], active_config / "matcher_config.txt")
        if fallback.get("stereo_config"):
            copy_file(fallback["stereo_config"], active_config / "stereo_config.txt")
        _ensure_ply(active_config / "stereo_config.txt")
        status = "HOMETANK_PIPELINE_PASS_WITH_EXTRINSIC_FALLBACK"
    else:
        for name in ("ext_R.xml", "ext_T.xml"):
            copy_file(auto_workspaces[0] / name, active_config / name)
            copy_file(auto_workspaces[0] / name, calibration / name)
        _ensure_ply(active_config / "stereo_config.txt")
        fallback_source, fallback_hashes = None, None
        status = "AUTOCALIBRATION_COMPUTED"

    # Re-prepare the final workspaces with the exact complete calibration bundle
    # that will be used by official dense stereo.
    final_workspaces = _prepare(pairs, output / "workspaces", active_config, wass_bin, recorder, "final")
    reconstructed = []
    for index, workspace in enumerate(final_workspaces):
        recorder.run(
            f"stereo_{index:06d}",
            [wass_bin / "wass_stereo.exe", active_config / "stereo_config.txt", workspace],
        )
        mesh = workspace / "mesh_cam.xyzC"
        plane = workspace / "plane.txt"
        if not mesh.is_file() or not plane.is_file():
            raise StageFailure("stereo", f"official stereo output missing in {workspace}")
        reconstructed.append(workspace)

    reconstruction = run_dir / "reconstruction"
    for subdir in ("xyz", "ply", "mesh"):
        (reconstruction / subdir).mkdir(parents=True, exist_ok=True)
    frame_records = []
    for index, workspace in enumerate(reconstructed):
        xyz = workspace / "mesh_cam.xyzC"
        ply = workspace / "mesh.ply"
        copy_file(xyz, reconstruction / "xyz" / f"{index:06d}.xyzC")
        if ply.is_file():
            copy_file(ply, reconstruction / "ply" / f"{index:06d}.ply")
        for optional in ("plane.txt", "stereo.jpg", "disparity_final_scaled.png"):
            if (workspace / optional).is_file():
                copy_file(workspace / optional, reconstruction / "mesh" / f"{index:06d}_{optional}")
        frame_records.append(
            {
                "index": index,
                "workspace": str(workspace),
                "xyz": str(xyz),
                "xyz_bytes": xyz.stat().st_size,
                "ply": str(ply) if ply.is_file() else None,
                "plane": str(workspace / "plane.txt"),
            }
        )

    active_r = load_matrix(active_config / "ext_R.xml")
    active_t = load_matrix(active_config / "ext_T.xml").reshape(3)
    report = {
        "status": status,
        "pipeline": "official WASS prepare -> match -> autocalibrate -> prepare -> stereo",
        "frame_count": len(frame_records),
        "successful_match_count": len(auto_workspaces),
        "successful_stereo_count": len(frame_records),
        "autocalibration_attempt": {
            "R": attempted_r.tolist(),
            "T": attempted_t.tolist(),
            "translation_norm": float(np.linalg.norm(attempted_t)),
            "workspaces": [str(path) for path in auto_workspaces],
        },
        "active_calibration": {
            "R": active_r.tolist(),
            "T": active_t.tolist(),
            "translation_norm": float(np.linalg.norm(active_t)),
            "fallback": fallback_used,
            "fallback_source": str(fallback_source) if fallback_source else None,
            "fallback_hashes": fallback_hashes,
            "fallback_matcher_config": fallback.get("matcher_config") if fallback_used else None,
            "fallback_stereo_config": fallback.get("stereo_config") if fallback_used else None,
            "note": "complete K/D/R/T bundle used; no new-intrinsics/historical-extrinsics mixing" if fallback_used else "official autocalibration output",
        },
        "frames": frame_records,
    }
    write_json(output / "run_summary.json", report)
    return report
