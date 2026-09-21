from __future__ import annotations

import json
from pathlib import Path
import shutil
from typing import Any

from pipeline.common import CommandRecorder, copy_file, sha256, write_json


REQUIRED_INTRINSICS = (
    "intrinsics_00.xml",
    "distortion_00.xml",
    "intrinsics_01.xml",
    "distortion_01.xml",
)


def _copy_pipeline_configs(source: Path, target: Path) -> None:
    for name in ("matcher_config.txt", "stereo_config.txt"):
        copy_file(source / name, target / name)


def _generate_pipeline_configs(target: Path, tools: dict[str, Any], recorder: CommandRecorder) -> None:
    wass_bin = Path(tools["wass_bin"])
    recorder.run("generate_matcher_config", [wass_bin / "wass_match.exe", "--genconfig"], cwd=target)
    recorder.run("generate_stereo_config", [wass_bin / "wass_stereo.exe", "--genconfig"], cwd=target)


def run(
    config: dict[str, Any],
    tools: dict[str, Any],
    run_dir: Path,
    repo_root: Path,
    recorder: CommandRecorder,
) -> dict[str, Any]:
    output = run_dir / "calibration"
    output.mkdir(parents=True, exist_ok=True)
    status = config.get("status", "compute")
    report: dict[str, Any] = {"status": status.upper()}

    if status == "provided":
        source = Path(config["config_path"]).resolve()
        for name in REQUIRED_INTRINSICS:
            copy_file(source / name, output / name)
        _copy_pipeline_configs(source, output)
        report.update(
            method="provided official calibration files",
            source=str(source),
            image_size_wh=config.get("image_size_wh"),
            provided_hashes={name: sha256(source / name) for name in REQUIRED_INTRINSICS},
        )
    elif status == "compute":
        left_dir, right_dir = output / "left", output / "right"
        board = config["checkerboard"]
        common = [
            "--pattern-cols", str(board["columns"]),
            "--pattern-rows", str(board["rows"]),
            "--square-size-m", str(board["square_size_m"]),
            "--sample-hz", str(config.get("sample_hz", 5.0)),
            "--target-views", str(config.get("target_views", 50)),
            "--minimum-views", str(config.get("minimum_views", 20)),
        ]
        script = repo_root / "tools" / "vieira_intrinsics_from_raw.py"
        python = tools["python"]
        recorder.run(
            "opencv_calibration_left",
            [python, script, "--video", config["left_video"], "--output", left_dir, *common],
            cwd=repo_root,
        )
        recorder.run(
            "opencv_calibration_right",
            [python, script, "--video", config["right_video"], "--output", right_dir, *common],
            cwd=repo_root,
        )
        left_report = json.loads((left_dir / "calibration.json").read_text(encoding="utf-8"))
        right_report = json.loads((right_dir / "calibration.json").read_text(encoding="utf-8"))
        if left_report["image_size_wh"] != right_report["image_size_wh"]:
            raise ValueError("left/right calibration image sizes differ")
        copy_file(left_dir / "intrinsics.xml", output / "intrinsics_00.xml")
        copy_file(left_dir / "distortion.xml", output / "distortion_00.xml")
        copy_file(right_dir / "intrinsics.xml", output / "intrinsics_01.xml")
        copy_file(right_dir / "distortion.xml", output / "distortion_01.xml")
        # Human-readable aliases requested by the pipeline output contract.
        shutil.copy2(output / "intrinsics_00.xml", output / "K_left.xml")
        shutil.copy2(output / "distortion_00.xml", output / "D_left.xml")
        shutil.copy2(output / "intrinsics_01.xml", output / "K_right.xml")
        shutil.copy2(output / "distortion_01.xml", output / "D_right.xml")
        if config.get("pipeline_config_path"):
            _copy_pipeline_configs(Path(config["pipeline_config_path"]), output)
        else:
            _generate_pipeline_configs(output, tools, recorder)
        report.update(
            method="OpenCV findChessboardCornersSB/cornerSubPix/calibrateCamera",
            left=left_report,
            right=right_report,
            image_size_wh=left_report["image_size_wh"],
            rms_px={"left": left_report["rms_px"], "right": right_report["rms_px"]},
        )
    else:
        raise ValueError(f"unsupported calibration.status: {status}")

    report["active_intrinsics_hashes"] = {name: sha256(output / name) for name in REQUIRED_INTRINSICS}
    write_json(output / "report.json", report)
    return report

