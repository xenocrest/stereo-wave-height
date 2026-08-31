"""Thin subprocess adapter around the frozen single-frame backend."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

import yaml

from .session import MeasurementRecord
from .fallback import run_bounded_fallback
from process_utils import hidden_process_kwargs
from reconstruction.io import load_calibration
from adapters.wass.input.opencv_xml import write_opencv_matrix_xml


class BackendResultError(RuntimeError):
    """A user-presentable backend integration failure."""

    def __init__(self, message: str, *, stage: str = "结果处理", retry_neighbor: bool = False) -> None:
        super().__init__(message)
        self.stage = stage
        self.retry_neighbor = retry_neighbor


def _failure_from_summary(summary: dict[str, Any], log_path: Path | None = None) -> BackendResultError:
    """Preserve the backend's first structured error instead of hiding it behind exit code 1."""
    status = str(summary.get("status", "UNKNOWN"))
    warnings = [str(value) for value in summary.get("warnings", [])]
    root = warnings[0] if warnings else f"后端状态为 {status}"
    lowered = root.lower()
    frame_local_markers = (
        "insufficient stereo", "insufficient match", "matching support",
        "geometry qa", "frame-local", "no reliable 3d", "not enough matches",
    )
    retry = status == "FRAME_RECONSTRUCTION_SUPPORT_FAILURE" or any(
        marker in lowered for marker in frame_local_markers
    )
    if "calibration" in lowered or "intrinsics" in lowered:
        stage = "固定标定准备"
    elif "ffmpeg" in lowered or "video" in lowered or "frame" in lowered and not retry:
        stage = "视频抽帧"
    elif "match" in lowered:
        stage = "双目匹配"
    elif "stereo" in lowered or "wass" in lowered:
        stage = "WASS 三维重建"
    else:
        stage = "后端处理"
    suffix = f"，详细日志：{log_path}" if log_path is not None else ""
    return BackendResultError(f"后端在【{stage}】阶段失败：{root}{suffix}", stage=stage, retry_neighbor=retry)


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
    core_only = status == "SINGLE_FRAME_RECONSTRUCTION_COMPLETED_DENSE_HEIGHT_FAILED"
    if status != "SINGLE_FRAME_DENSE_HEIGHT_COMPLETED" and not core_only:
        raise _failure_from_summary(summary)
    dense = summary.get("dense_height") or {}
    paths = dense.get("artifact_paths") or {}
    selected = output / "selected_pair" / "right.png"
    height = output / str(paths.get("height_png", "dense_height/dense_height.png"))
    status_map = output / str(paths.get("status_png", "dense_height/dense_height_status.png"))
    pointcloud = output / "reconstruction" / "pointcloud" / "000000.xyz"
    required=(selected,pointcloud) if core_only else (selected,height,status_map)
    missing = [path for path in required if not path.is_file()]
    if missing:
        raise BackendResultError("结果图缺失：" + ", ".join(str(path) for path in missing))
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
                       output_directory: Path, calibration_file: Path | None = None,
                       water_roi: dict[str, Any] | None = None) -> Path:
        data = yaml.safe_load(self.template_config.read_text(encoding="utf-8"))
        template_base = self.template_config.parent
        def absolute(value: str) -> str:
            path = Path(value)
            return str(path if path.is_absolute() else (template_base / path).resolve())
        data["input"]["left_video"] = str(Path(left_video).resolve())
        data["input"]["right_video"] = str(Path(right_video).resolve())
        data["input"]["target_time_s"] = float(target_time_sec)
        data["input"]["ffmpeg_executable"] = absolute(data["input"]["ffmpeg_executable"])
        selected_calibration = Path(calibration_file).resolve() if calibration_file else Path(absolute(data["calibration"]["source"]))
        data["calibration"]["source"] = str(selected_calibration)
        for key in ("wass_config_dir", "wass_runtime_binding", "reference_plane_file"):
            data["processing"][key] = absolute(data["processing"][key])
        if calibration_file is not None:
            source_config = Path(data["processing"]["wass_config_dir"])
            calibration = load_calibration(
                selected_calibration,
                quality_mode=str(data["calibration"].get("quality_mode", "require_approved")),
            )
            generated_config = Path(output_directory).parent / f"{Path(output_directory).name}_wass_config"
            if generated_config.exists():
                raise FileExistsError(f"generated WASS config already exists: {generated_config}")
            shutil.copytree(source_config, generated_config)
            matrices = {
                "intrinsics_00.xml": (calibration.k0, "intrinsics_penne"),
                "distortion_00.xml": (calibration.d0.reshape(-1, 1), "intrinsics_penne"),
                "intrinsics_01.xml": (calibration.k1, "intrinsics_penne"),
                "distortion_01.xml": (calibration.d1.reshape(-1, 1), "intrinsics_penne"),
                "ext_R.xml": (calibration.r, "ext_R"),
                "ext_T.xml": (calibration.t_m.reshape(-1, 1), "ext_T"),
            }
            for name, (matrix, node_name) in matrices.items():
                write_opencv_matrix_xml(generated_config / name, matrix, node_name=node_name)
            (generated_config / "selected_calibration_source.txt").write_text(
                str(selected_calibration) + "\n", encoding="utf-8"
            )
            data["processing"]["wass_config_dir"] = str(generated_config)
        if data.get("dense_height", {}).get("mapping_file"):
            data["dense_height"]["mapping_file"] = absolute(data["dense_height"]["mapping_file"])
        if water_roi is not None:
            data["dense_height"]["water_roi"] = water_roi
        data["output"]["directory"] = str(Path(output_directory).resolve())
        config = Path(output_directory).parent / f"{Path(output_directory).name}_request.yaml"
        config.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
        return config

    def run(self, left_video: Path, right_video: Path, target_time_sec: float,
            output_directory: Path, log_path: Path, calibration_file: Path | None = None,
            water_roi: dict[str, Any] | None = None) -> MeasurementRecord:
        try:
            config = self.prepare_config(left_video, right_video, target_time_sec, output_directory, calibration_file, water_roi)
        except Exception as error:
            raise BackendResultError(
                f"后端在【请求配置】阶段失败：{type(error).__name__}: {error}，详细日志：{log_path}",
                stage="请求配置",
            ) from error
        environment = os.environ.copy()
        extra = os.pathsep.join((str(self.repository / "src"), str(self.repository)))
        environment["PYTHONPATH"] = extra + (os.pathsep + environment["PYTHONPATH"] if environment.get("PYTHONPATH") else "")
        command = backend_command(config)
        with Path(log_path).open("a", encoding="utf-8") as stream:
            stream.write("backend command: " + subprocess.list2cmdline(command) + "\n")
            completed = subprocess.run(command, cwd=self.repository, env=environment, capture_output=True,
                                       text=False, check=False,
                                       **hidden_process_kwargs(enabled=bool(getattr(sys,"frozen",False))))
            backend_output = (completed.stdout or b"") + (completed.stderr or b"")
            decoded = backend_output.decode("utf-8", errors="replace")
            stream.write(decoded)
        if completed.returncode != 0:
            unified = Path(output_directory) / "single_frame_result.json"
            if unified.is_file():
                try:
                    summary = json.loads(unified.read_text(encoding="utf-8"))
                    if summary.get("status") == "SINGLE_FRAME_RECONSTRUCTION_COMPLETED_DENSE_HEIGHT_FAILED":
                        return parse_backend_result(output_directory)
                    raise _failure_from_summary(summary, Path(log_path))
                except json.JSONDecodeError:
                    pass
            tail = " | ".join(line.strip() for line in decoded.splitlines()[-4:] if line.strip())
            root = tail or "后端未生成结构化错误结果"
            raise BackendResultError(
                f"后端在【进程启动/运行时】阶段失败：{root}（退出码 {completed.returncode}），详细日志：{log_path}",
                stage="进程启动/运行时",
            )
        return parse_backend_result(output_directory)

    def run_with_fallback(self, left_video: Path, right_video: Path, target_time_sec: float,
                          output_directory: Path, log_path: Path, calibration_file: Path,
                          *, frame_period_sec: float, water_roi: dict[str, Any] | None = None) -> MeasurementRecord:
        """Try the target then at most four neighboring whole-pair target times."""
        def attempt(candidate_time: float, offset: int) -> MeasurementRecord:
            folder=Path(output_directory)/f"attempt_{offset:+d}"
            return self.run(left_video,right_video,candidate_time,folder,log_path,calibration_file,water_roi)
        result=run_bounded_fallback(
            target_time_sec,
            frame_period_sec,
            attempt,
            should_retry=lambda error: isinstance(error, BackendResultError) and error.retry_neighbor,
        )
        record=result.value; summary=dict(record.summary_metadata)
        summary.update({
            "requested_target_time_sec":target_time_sec,
            "actual_measurement_time_sec":result.actual_time_sec,
            "fallback_used":result.frame_offset!=0,
            "fallback_frame_offset":result.frame_offset,
            "fallback_time_offset_ms":(result.actual_time_sec-target_time_sec)*1000.0,
            "fallback_reason":"; ".join(result.failures) if result.failures else None,
        })
        record.unified_result_path.write_text(json.dumps(summary,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
        return MeasurementRecord(**{**record.__dict__,"target_time_sec":target_time_sec,"summary_metadata":summary})


def backend_command(config: Path, *, executable: Path | None = None, frozen: bool | None = None) -> list[str]:
    """Build the child command for development Python or the packaged executable."""
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    program = str((executable or Path(sys.executable)).resolve())
    return [program, "--backend-single-frame", str(Path(config).resolve())] if is_frozen else [
        program, "-m", "src.reconstruction.run_single_frame", "--config", str(Path(config).resolve())
    ]
