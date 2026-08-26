"""On-demand single-frame backend reusing the fixed-calibration WASS pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import subprocess
import tempfile
import time
from typing import Any, Callable

import numpy as np
from PIL import Image

from input.orientation import OrientationTransform
from synchronization.affine import AffineTimeMapping
from synchronization.frame_selection import (
    SelectedTimestampPair,
    extract_frame_by_pts,
    probe_video_pts_window,
    select_timestamp_pair,
)

from .io import FrameRequest, ReconstructionConfig
from .pipeline import ReconstructionPipeline, ReconstructionRunResult


@dataclass(frozen=True)
class SynchronizationSpec:
    """Traceable video-clock model; never used in reconstruction numerics."""

    scale: float
    offset_s: float
    source: str
    confidence: str
    frame_level_established: bool
    event_count: int
    fit_residual_rmse_s: float
    fit_residual_max_abs_s: float

    def mapping(self) -> AffineTimeMapping:
        return AffineTimeMapping(
            self.scale, self.offset_s, self.event_count,
            self.fit_residual_rmse_s, self.fit_residual_max_abs_s,
        )


@dataclass(frozen=True)
class SingleFrameMeasurementRequest:
    """Vendor-neutral GUI-to-backend request for one stereo instant."""

    input_mode: str
    output_dir: Path
    calibration_source: Path
    wass_config_dir: Path
    wass_runtime_binding: Path
    ffmpeg_executable: Path
    synchronization_source: str
    left_video: Path | None = None
    right_video: Path | None = None
    left_image: Path | None = None
    right_image: Path | None = None
    target_time_s: float | None = None
    synchronization: SynchronizationSpec | None = None
    left_rotation_deg: int = 0
    right_rotation_deg: int = 0
    calibration_quality_mode: str = "require_approved"
    reference_plane_file: Path | None = None
    surface_distance_threshold_m: float = 0.01

    def __post_init__(self) -> None:
        if self.input_mode not in {"image_pair", "video_time"}:
            raise ValueError("input_mode must be image_pair or video_time")
        if not self.synchronization_source:
            raise ValueError("synchronization_source must be explicit")
        if self.left_rotation_deg not in (0, 90, 180, 270) or self.right_rotation_deg not in (0, 90, 180, 270):
            raise ValueError("canonical rotations must be 0/90/180/270")
        if not np.isfinite(self.surface_distance_threshold_m) or self.surface_distance_threshold_m <= 0:
            raise ValueError("surface_distance_threshold_m must be positive")
        if self.input_mode == "image_pair":
            if self.left_image is None or self.right_image is None:
                raise ValueError("image_pair mode requires left_image and right_image")
            if self.target_time_s is not None or self.synchronization is not None:
                raise ValueError("already synchronized image_pair must not carry a video clock model")
        else:
            if self.left_video is None or self.right_video is None or self.target_time_s is None:
                raise ValueError("video_time mode requires two videos and target_time_s")
            if self.synchronization is None:
                raise ValueError("video_time mode requires an explicit synchronization model")
            if not np.isfinite(self.target_time_s) or self.target_time_s < 0:
                raise ValueError("target_time_s must be finite and non-negative")
        for path in self.required_input_paths():
            if not path.is_file() and not path.is_dir():
                raise FileNotFoundError(path)

    def required_input_paths(self) -> tuple[Path, ...]:
        optional = (
            self.left_image, self.right_image, self.left_video, self.right_video,
            self.calibration_source, self.wass_config_dir, self.wass_runtime_binding,
            self.reference_plane_file,
        )
        return tuple(path for path in optional if path is not None)

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        for key, value in tuple(data.items()):
            if isinstance(value, Path):
                data[key] = str(value)
        return data


@dataclass(frozen=True)
class SingleFrameMeasurementResult:
    """Stable GUI-facing outcome, including blocked and failed states."""

    status: str
    requested_time_s: float | None
    left_timestamp_s: float | None
    right_timestamp_s: float | None
    pair_time_error_ms: float | None
    left_frame_id: str | None
    right_frame_id: str | None
    calibration_source: str
    xyz_point_count: int | None
    pixel_xyz_count: int | None
    reference_plane: dict[str, object] | None
    reference_plane_source: str | None
    height_statistics: dict[str, object] | None
    plane_rms_m: float | None
    wass_seconds: float | None
    qa_status: str
    physical_accuracy_status: str
    warnings: tuple[str, ...]
    output_paths: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def canonicalize_image_pair(
    left_source: str | Path,
    right_source: str | Path,
    left_destination: str | Path,
    right_destination: str | Path,
    *,
    left_rotation_deg: int,
    right_rotation_deg: int,
    orientation_source: str,
) -> tuple[Path, Path]:
    """Apply only declared orientation metadata and save grayscale PNGs."""
    outputs: list[Path] = []
    for source, destination, rotation in (
        (left_source, left_destination, left_rotation_deg),
        (right_source, right_destination, right_rotation_deg),
    ):
        with Image.open(source) as image:
            values = np.asarray(image.convert("L"))
        canonical = OrientationTransform(rotation, orientation_source).apply(values)
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(canonical).save(target)
        outputs.append(target)
    return outputs[0], outputs[1]


def _encode_lossless_single_frame(image: Path, video: Path, ffmpeg: Path) -> None:
    command = [
        str(ffmpeg), "-hide_banner", "-loglevel", "error", "-loop", "1", "-i", str(image),
        "-frames:v", "1", "-c:v", "ffv1", "-pix_fmt", "gray", "-y", str(video),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if completed.returncode != 0 or not video.is_file():
        raise RuntimeError(f"lossless single-frame staging failed: {completed.stderr.strip()}")


def _write_backend_outputs(output: Path, result: SingleFrameMeasurementResult) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "qa").mkdir(exist_ok=True)
    (output / "report").mkdir(exist_ok=True)
    payload = result.to_dict()
    (output / "single_frame_result.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    lines = [
        "# On-demand Single-frame Stereo Measurement Report", "",
        f"- Status: `{result.status}`",
        f"- QA: `{result.qa_status}`",
        f"- Physical accuracy: `{result.physical_accuracy_status}`",
        f"- Requested time: `{result.requested_time_s}` s",
        f"- Left/right actual timestamp: `{result.left_timestamp_s}` / `{result.right_timestamp_s}` s",
        f"- Pair residual: `{result.pair_time_error_ms}` ms",
        f"- XYZ / pixel–XYZ count: `{result.xyz_point_count}` / `{result.pixel_xyz_count}`",
        f"- Reference plane source: `{result.reference_plane_source}`",
        f"- Plane RMS: `{result.plane_rms_m}` m", "",
        "## Boundary", "",
        "The backend uses video/image input, OpenCV calibration, WASS output and geometric postprocessing only. "
        "Ruler data is not loaded by reconstruction and may be used only by downstream independent validation.", "",
    ]
    if result.warnings:
        lines += ["## Warnings", "", *[f"- {warning}" for warning in result.warnings], ""]
    (output / "report" / "single_frame_report.md").write_text("\n".join(lines), encoding="utf-8")


class SingleFrameMeasurementBackend:
    """Thin orchestration layer around the mature ReconstructionPipeline."""

    def __init__(self, *, pipeline_factory: Callable[[ReconstructionConfig], Any] = ReconstructionPipeline) -> None:
        self.pipeline_factory = pipeline_factory

    def _blocked_result(
        self, request: SingleFrameMeasurementRequest, selection: SelectedTimestampPair
    ) -> SingleFrameMeasurementResult:
        result = SingleFrameMeasurementResult(
            status="FRAME_LEVEL_SYNC_NOT_ESTABLISHED",
            requested_time_s=request.target_time_s,
            left_timestamp_s=selection.left.timestamp_s,
            right_timestamp_s=selection.right.timestamp_s,
            pair_time_error_ms=selection.residual_s * 1000.0,
            left_frame_id=f"pts_{selection.left.pts}",
            right_frame_id=f"pts_{selection.right.pts}",
            calibration_source=str(request.calibration_source),
            xyz_point_count=None, pixel_xyz_count=None, reference_plane=None,
            reference_plane_source=None, height_statistics=None, plane_rms_m=None,
            wass_seconds=None, qa_status=selection.quality_status,
            physical_accuracy_status="PHYSICAL_ACCURACY_NOT_ESTABLISHED",
            warnings=(
                "Frame-level synchronization quality gate failed; WASS was not run.",
                "Nearest PTS diagnostics do not authorize a stereo pair when the mapping is coarse-only.",
            ),
            output_paths={"result_json": "single_frame_result.json", "report": "report/single_frame_report.md"},
        )
        _write_backend_outputs(request.output_dir, result)
        return result

    def _reconstruction_failed_result(
        self,
        request: SingleFrameMeasurementRequest,
        selection: SelectedTimestampPair | None,
        error: Exception,
        elapsed_s: float,
    ) -> SingleFrameMeasurementResult:
        result = SingleFrameMeasurementResult(
            status="WASS_RECONSTRUCTION_FAILED",
            requested_time_s=request.target_time_s,
            left_timestamp_s=selection.left.timestamp_s if selection else None,
            right_timestamp_s=selection.right.timestamp_s if selection else None,
            pair_time_error_ms=selection.residual_s * 1000.0 if selection else 0.0,
            left_frame_id=f"pts_{selection.left.pts}" if selection else request.left_image.name,
            right_frame_id=f"pts_{selection.right.pts}" if selection else request.right_image.name,
            calibration_source=str(request.calibration_source),
            xyz_point_count=None, pixel_xyz_count=None, reference_plane=None,
            reference_plane_source=None, height_statistics=None, plane_rms_m=None,
            wass_seconds=elapsed_s, qa_status="WASS_RECONSTRUCTION_FAILED",
            physical_accuracy_status="PHYSICAL_ACCURACY_NOT_ESTABLISHED",
            warnings=(f"Fixed-calibration reconstruction terminated: {type(error).__name__}: {error}",),
            output_paths={"selected_pair": "selected_pair", "result_json": "single_frame_result.json", "report": "report/single_frame_report.md"},
        )
        _write_backend_outputs(request.output_dir, result)
        return result

    def run(self, request: SingleFrameMeasurementRequest) -> SingleFrameMeasurementResult:
        output = request.output_dir
        if output.exists() and any(output.iterdir()):
            raise FileExistsError("single-frame output directory must be absent or empty")
        output.mkdir(parents=True, exist_ok=True)
        selected = output / "selected_pair"
        left_png, right_png = selected / "left.png", selected / "right.png"
        selection: SelectedTimestampPair | None = None

        if request.input_mode == "video_time":
            assert request.left_video is not None and request.right_video is not None
            assert request.target_time_s is not None and request.synchronization is not None
            mapping = request.synchronization.mapping()
            mapped_target = float(mapping.map_left_to_right([request.target_time_s])[0])
            left_pts = probe_video_pts_window(
                request.left_video, ffmpeg_executable=request.ffmpeg_executable,
                center_time_s=request.target_time_s,
            )
            right_pts = probe_video_pts_window(
                request.right_video, ffmpeg_executable=request.ffmpeg_executable,
                center_time_s=mapped_target,
            )
            selection = select_timestamp_pair(
                left_pts, right_pts, requested_left_time_s=request.target_time_s,
                mapping=mapping, mapping_confidence=request.synchronization.confidence,
                frame_level_mapping_established=request.synchronization.frame_level_established,
            )
            if selection.quality_status in {"FRAME_LEVEL_SYNC_NOT_ESTABLISHED", "FRAME_PAIR_SYNC_FAILED"}:
                return self._blocked_result(request, selection)
            extract_frame_by_pts(
                request.left_video, left_png, ffmpeg_executable=request.ffmpeg_executable,
                frame=selection.left, rotation_deg=request.left_rotation_deg,
            )
            extract_frame_by_pts(
                request.right_video, right_png, ffmpeg_executable=request.ffmpeg_executable,
                frame=selection.right, rotation_deg=request.right_rotation_deg,
            )
        else:
            assert request.left_image is not None and request.right_image is not None
            canonicalize_image_pair(
                request.left_image, request.right_image, left_png, right_png,
                left_rotation_deg=request.left_rotation_deg,
                right_rotation_deg=request.right_rotation_deg,
                orientation_source="request_declared_image_metadata",
            )

        pair_metadata = {
            "input_mode": request.input_mode,
            "requested_time_s": request.target_time_s,
            "left_timestamp_s": selection.left.timestamp_s if selection else None,
            "right_timestamp_s": selection.right.timestamp_s if selection else None,
            "left_frame_id": f"pts_{selection.left.pts}" if selection else request.left_image.name,
            "right_frame_id": f"pts_{selection.right.pts}" if selection else request.right_image.name,
            "pair_residual_s": selection.residual_s if selection else 0.0,
            "synchronization_source": request.synchronization_source,
            "synchronization_model": asdict(request.synchronization) if request.synchronization else None,
            "orientation": {"left_rotation_deg": request.left_rotation_deg, "right_rotation_deg": request.right_rotation_deg},
        }
        (selected / "pair_metadata.json").write_text(
            json.dumps(pair_metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        with tempfile.TemporaryDirectory(prefix="single-frame-stage-", dir=str(output)) as temporary:
            stage = Path(temporary)
            left_video, right_video = stage / "left.mkv", stage / "right.mkv"
            _encode_lossless_single_frame(left_png, left_video, request.ffmpeg_executable)
            _encode_lossless_single_frame(right_png, right_video, request.ffmpeg_executable)
            pipeline_output = output / "reconstruction"
            config = ReconstructionConfig(
                source_path=output / "single_frame_request.json",
                left_video=left_video,
                right_video=right_video,
                frame_requests=(FrameRequest("000000", 0.0, 0.0, int(round((request.target_time_s or 0) * 1e9))),),
                left_rotation_deg=0,
                right_rotation_deg=0,
                calibration_file=request.calibration_source,
                calibration_quality_mode=request.calibration_quality_mode,
                wass_config_dir=request.wass_config_dir,
                wass_runtime_binding=request.wass_runtime_binding,
                ffmpeg_executable=str(request.ffmpeg_executable),
                output_directory=pipeline_output,
                surface_distance_threshold_m=request.surface_distance_threshold_m,
                run_type="wave" if request.reference_plane_file else "static",
                reference_plane_file=request.reference_plane_file,
            )
            (output / "single_frame_request.json").write_text(
                json.dumps(request.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            started = time.perf_counter()
            try:
                run: ReconstructionRunResult = self.pipeline_factory(config).run()
            except Exception as error:
                return self._reconstruction_failed_result(
                    request, selection, error, time.perf_counter() - started
                )
            wass_seconds = time.perf_counter() - started

        reconstructed = json.loads(run.result_json.read_text(encoding="utf-8"))
        frame = reconstructed["frames"][0]
        reference = reconstructed["height_reference"]
        sync_warning = selection is not None and selection.quality_status == "FRAME_PAIR_SYNC_WARNING"
        result = SingleFrameMeasurementResult(
            status="SINGLE_FRAME_PIPELINE_PASS_WITH_SYNC_WARNING" if sync_warning else "SINGLE_FRAME_PIPELINE_PASS",
            requested_time_s=request.target_time_s,
            left_timestamp_s=selection.left.timestamp_s if selection else None,
            right_timestamp_s=selection.right.timestamp_s if selection else None,
            pair_time_error_ms=(selection.residual_s * 1000.0 if selection else 0.0),
            left_frame_id=f"pts_{selection.left.pts}" if selection else request.left_image.name,
            right_frame_id=f"pts_{selection.right.pts}" if selection else request.right_image.name,
            calibration_source=str(request.calibration_source),
            xyz_point_count=int(frame["point_count"]),
            pixel_xyz_count=int(frame["pixel_xyz_correspondence_count"]),
            reference_plane={"normal": reference["normal"], "offset_m": reference["offset_m"]},
            reference_plane_source="static_reference" if request.reference_plane_file else "current_frame_fit",
            height_statistics={
                "unit": "m", "minimum": frame["height_range_m"][0], "maximum": frame["height_range_m"][1],
                "mean": frame["height_mean_m"], "rms": frame["height_rms_m"],
                "maximum_absolute": frame["height_max_absolute_m"],
            },
            plane_rms_m=float(frame["water_plane_rms_m"]),
            wass_seconds=wass_seconds,
            qa_status="HEIGHT_RESULT_AVAILABLE_NOT_PHYSICALLY_VALIDATED",
            physical_accuracy_status="PHYSICAL_ACCURACY_NOT_ESTABLISHED",
            warnings=tuple(filter(None, ["Frame pair passed with synchronization warning." if sync_warning else None])),
            output_paths={
                "selected_pair": "selected_pair", "pointcloud": "reconstruction/pointcloud",
                "height": "reconstruction/height", "pixel_xyz": "reconstruction/pixel_xyz",
                "result_json": "single_frame_result.json", "report": "report/single_frame_report.md",
            },
        )
        _write_backend_outputs(output, result)
        return result
