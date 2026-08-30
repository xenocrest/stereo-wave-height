"""Thin subprocess adapter around the frozen single-frame backend."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

import yaml

from .session import MeasurementRecord


class BackendResultError(RuntimeError):
    """A user-presentable backend integration failure."""


def parse_backend_result(output_directory: Path, *, display_name: str | None = None) -> MeasurementRecord:
    output = Path(output_directory)
    unified = output / "single_frame_result.json"
    if not unified.is_file():
        raise BackendResultError(f"统一结果文件不存在：{unified}")
    try:
        summary: dict[str, Any] = json.loads(unified.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        raise BackendResultError(f"无法读取统一结果：{error}") from error
    status = str(summary.get("status", "UNKNOWN"))
    if status != "SINGLE_FRAME_DENSE_HEIGHT_COMPLETED":
        raise BackendResultError(f"单帧解算未完成：{status}")
    dense = summary.get("dense_height") or {}
    paths = dense.get("artifact_paths") or {}
    selected = output / "selected_pair" / "right.png"
    height = output / str(paths.get("height_png", "dense_height/dense_height.png"))
    status_map = output / str(paths.get("status_png", "dense_height/dense_height_status.png"))
    missing = [path for path in (selected, height, status_map) if not path.is_file()]
    if missing:
        raise BackendResultError("结果图缺失：" + ", ".join(str(path) for path in missing))
    pointcloud = output / "reconstruction" / "pointcloud" / "000000.xyz"
    target = float(summary["requested_time_s"])
    return MeasurementRecord(
        target_time_sec=target,
        display_name=display_name or f"{target:.3f}s",
        output_directory=output,
        unified_result_path=unified,
        selected_frame_path=selected,
        dense_height_path=height,
        status_map_path=status_map,
        point_cloud_path=pointcloud if pointcloud.is_file() else None,
        created_time=datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        summary_metadata=summary,
        dense_npz_path=output / str(paths.get("npz", "dense_height/dense_height.npz")),
        pixel_xyz_path=output / "reconstruction" / "pixel_xyz" / "000000_pixel_xyz.npz",
        point_cloud_ply_path=output / "reconstruction" / "pointcloud" / "000000.ply",
        report_path=output / "report" / "single_frame_report.md",
        overlay_path=output / "dense_height" / "height_overlay.png",
    )


class FrozenBackendRunner:
    """Create a request config, invoke the official CLI, and parse its output."""

    def __init__(self, repository: Path, template_config: Path) -> None:
        self.repository = Path(repository).resolve()
        self.template_config = Path(template_config).resolve()

    def prepare_config(self, left_video: Path, right_video: Path, target_time_sec: float,
                       output_directory: Path, calibration_file: Path | None = None) -> Path:
        data = yaml.safe_load(self.template_config.read_text(encoding="utf-8"))
        template_base = self.template_config.parent
        def absolute(value: str) -> str:
            path = Path(value)
            return str(path if path.is_absolute() else (template_base / path).resolve())
        data["input"]["left_video"] = str(Path(left_video).resolve())
        data["input"]["right_video"] = str(Path(right_video).resolve())
        data["input"]["target_time_s"] = float(target_time_sec)
        data["input"]["ffmpeg_executable"] = absolute(data["input"]["ffmpeg_executable"])
        data["calibration"]["source"] = str(Path(calibration_file).resolve()) if calibration_file else absolute(data["calibration"]["source"])
        for key in ("wass_config_dir", "wass_runtime_binding", "reference_plane_file"):
            data["processing"][key] = absolute(data["processing"][key])
        if data.get("dense_height", {}).get("mapping_file"):
            data["dense_height"]["mapping_file"] = absolute(data["dense_height"]["mapping_file"])
        data["output"]["directory"] = str(Path(output_directory).resolve())
        config = Path(output_directory).parent / f"{Path(output_directory).name}_request.yaml"
        config.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
        return config

    def run(self, left_video: Path, right_video: Path, target_time_sec: float,
            output_directory: Path, log_path: Path, calibration_file: Path | None = None) -> MeasurementRecord:
        config = self.prepare_config(left_video, right_video, target_time_sec, output_directory, calibration_file)
        environment = os.environ.copy()
        extra = os.pathsep.join((str(self.repository / "src"), str(self.repository)))
        environment["PYTHONPATH"] = extra + (os.pathsep + environment["PYTHONPATH"] if environment.get("PYTHONPATH") else "")
        command = backend_command(config)
        with Path(log_path).open("a", encoding="utf-8") as stream:
            stream.write("backend command: " + subprocess.list2cmdline(command) + "\n")
            completed = subprocess.run(command, cwd=self.repository, env=environment, stdout=stream,
                                       stderr=subprocess.STDOUT, text=True, check=False)
        if completed.returncode != 0:
            raise BackendResultError(f"后端执行失败（退出码 {completed.returncode}），详情见 {log_path}")
        return parse_backend_result(output_directory)


def backend_command(config: Path, *, executable: Path | None = None, frozen: bool | None = None) -> list[str]:
    """Build the child command for development Python or the packaged executable."""
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    program = str((executable or Path(sys.executable)).resolve())
    return [program, "--backend-single-frame", str(Path(config).resolve())] if is_frozen else [
        program, "-m", "src.reconstruction.run_single_frame", "--config", str(Path(config).resolve())
    ]
