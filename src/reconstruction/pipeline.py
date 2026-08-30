"""End-to-end fixed-calibration video-to-height orchestration using WASS."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image

from adapters.wass.input import prepare_wass_workspace
from adapters.wass.output.xyzc import read_wass_xyzc
from adapters.wass.runner import WassRunner
from adapters.wass.runtime import load_runtime_binding
from .io import (
    ReconstructionConfig,
    extract_synchronized_frames,
    load_calibration,
    load_reference_plane,
    load_reconstruction_config,
    verify_wass_calibration,
    write_ply,
    write_xyz,
)
from .height import height_from_plane
from .pixel_xyz import load_projection_matrix, project_wass_points, save_pixel_xyz
from .report import write_report, write_result_json
from .surface import extract_planar_surface


@dataclass(frozen=True)
class ReconstructionRunResult:
    """Paths and summary returned to CLI, tests and future GUI."""

    output_directory: Path
    result_json: Path
    report_markdown: Path
    status: str
    frame_count: int
    point_count: int


class ReconstructionPipeline:
    """Coordinate existing project modules; never implement stereo itself."""

    def __init__(self, config: ReconstructionConfig) -> None:
        self.config = config

    @classmethod
    def from_file(cls, path: str | Path) -> "ReconstructionPipeline":
        return cls(load_reconstruction_config(path))

    def run(self) -> ReconstructionRunResult:
        output = self.config.output_directory
        if output.exists() and any(output.iterdir()):
            raise FileExistsError("output directory must be absent or empty")
        output.mkdir(parents=True, exist_ok=True)
        calibration = load_calibration(
            self.config.calibration_file, quality_mode=self.config.calibration_quality_mode
        )
        verify_wass_calibration(self.config.wass_config_dir, calibration)
        dataset = output / "dataset"
        extract_synchronized_frames(self.config, dataset)
        workspace = output / "wass_workspace"
        prepare_wass_workspace(dataset, workspace, verified_config_dir=self.config.wass_config_dir)
        runner = WassRunner(load_runtime_binding(self.config.wass_runtime_binding))
        run = runner.run_fixed_calibration(workspace)

        frame_results: list[dict[str, object]] = []
        point_total = 0
        rectified_dir, disparity_dir = output / "rectified", output / "disparity"
        pointcloud_dir, height_dir = output / "pointcloud", output / "height"
        pixel_xyz_dir = output / "pixel_xyz"
        for directory in (rectified_dir, disparity_dir, pointcloud_dir, height_dir, pixel_xyz_dir):
            directory.mkdir(parents=True, exist_ok=True)
        manifest = json.loads((workspace / "wass_input_manifest.json").read_text(encoding="utf-8"))
        decoded: list[tuple[dict[str, object], Path, np.ndarray, object]] = []
        for frame in manifest["frames"]:
            workdir = workspace / frame["workdir"]
            cloud = read_wass_xyzc(workdir / "mesh_cam.xyzC")
            points_m = cloud.points_camera * calibration.baseline_m
            surface = extract_planar_surface(
                points_m, distance_threshold_m=self.config.surface_distance_threshold_m
            )
            decoded.append((frame, workdir, cloud, points_m, surface))
        if self.config.reference_plane_file is None:
            reference_normal = decoded[0][4].normal
            reference_offset_m = decoded[0][4].offset_m
            reference_frame_id = str(decoded[0][0]["frame_id"])
            reference_source = "first_configured_static_frame_fitted_plane"
            reference_warning = None
        else:
            reference_normal, reference_offset_m, reference_data = load_reference_plane(
                self.config.reference_plane_file
            )
            reference_frame_id = str(reference_data.get("frame_id", "UNKNOWN"))
            reference_source = str(reference_data["source"])
            reference_warning = reference_data.get("warning")

        for frame, workdir, cloud, points_m, surface in decoded:
            frame_id = frame["frame_id"]
            reference_height_m = height_from_plane(points_m, reference_normal, reference_offset_m)
            point_total += points_m.shape[0]
            write_xyz(pointcloud_dir / f"{frame_id}.xyz", points_m)
            write_ply(pointcloud_dir / f"{frame_id}.ply", points_m)
            np.savez_compressed(
                height_dir / f"{frame_id}_height_points.npz",
                x_m=points_m[:, 0], y_m=points_m[:, 1], height_m=reference_height_m,
                water_mask=surface.water_mask,
            )
            montage_path = workdir / "stereo.jpg"
            with Image.open(montage_path) as montage:
                width, height = montage.size
                if width % 2:
                    raise ValueError("WASS rectified stereo montage width must be even")
                computational_left = montage.crop((0, 0, width // 2, height))
                computational_right = montage.crop((width // 2, 0, width, height))
                log = (workdir / "wass_stereo_log.txt").read_text(encoding="utf-8",errors="replace")
                swapped = "auto-swapping left-right images" in log
                original_left = computational_right if swapped else computational_left
                original_right = computational_left if swapped else computational_right
                original_left.save(rectified_dir / f"{frame_id}_left.png")
                original_right.save(rectified_dir / f"{frame_id}_right.png")
            pixel_role = "input_right" if swapped else "input_left"
            correspondence = project_wass_points(
                cloud.points_camera,
                points_m,
                load_projection_matrix(workdir / "P0cam.txt"),
                pixel_coordinate_system=f"wass_rectified_computational_cam0__{pixel_role}",
            )
            save_pixel_xyz(pixel_xyz_dir / f"{frame_id}_pixel_xyz.npz", correspondence)
            disparity_source = workdir / "disparity_stereo_ouput.png"
            shutil.copy2(disparity_source, disparity_dir / f"{frame_id}.png")
            with Image.open(disparity_source) as disparity_image:
                disparity_visualization = np.asarray(disparity_image.convert("L"), dtype=np.float64)
            stereo_log = (workdir / "wass_stereo_log.txt").read_text(encoding="utf-8",errors="replace")
            valid_line = next(
                (line for line in stereo_log.splitlines() if " valid points found" in line), None
            )
            valid_disparity_count = int(valid_line.split()[-4]) if valid_line else None
            frame_results.append({
                "frame_id": frame_id,
                "timestamp_ns": frame["timestamp_ns"],
                "point_count": int(points_m.shape[0]),
                "xyz_range_m": {
                    axis: [float(points_m[:, index].min()), float(points_m[:, index].max())]
                    for index, axis in enumerate(("x", "y", "z"))
                },
                "plane": {"normal": surface.normal.tolist(), "offset_m": surface.offset_m},
                "water_plane_rms_m": surface.rms_m,
                "water_plane_mean_residual_m": surface.mean_m,
                "water_plane_max_absolute_residual_m": surface.max_absolute_m,
                "water_mask_ratio": float(surface.water_mask.mean()),
                "water_surface_point_count": int(np.count_nonzero(surface.water_mask)),
                "disparity_statistics": {
                    "absolute_numeric_status": "NOT_EXPORTED_BY_FROZEN_WASS_RUNTIME",
                    "valid_triangulated_count": valid_disparity_count,
                    "visualization_8bit": {
                        "minimum": float(disparity_visualization.min()),
                        "maximum": float(disparity_visualization.max()),
                        "mean": float(disparity_visualization.mean()),
                        "standard_deviation": float(disparity_visualization.std()),
                    },
                },
                "height_reference_frame_id": reference_frame_id,
                "height_range_m": [float(reference_height_m.min()), float(reference_height_m.max())],
                "height_mean_m": float(reference_height_m.mean()),
                "height_rms_m": float(np.sqrt(np.mean(reference_height_m**2))),
                "height_max_absolute_m": float(np.max(np.abs(reference_height_m))),
                "pixel_xyz_correspondence_count": int(correspondence.xyz_m.shape[0]),
                "pixel_xyz_coordinate_system": correspondence.pixel_coordinate_system,
                "pixel_xyz_method": "project mesh_cam camera coordinates with per-workdir P0cam",
                "rectification_auto_swap_restored_to_input_roles": swapped,
            })
        result = {
            "schema_version": "1.0",
            "status": (
                "WAVE_PIPELINE_COMPLETED_WITH_STATIC_WARNING"
                if self.config.run_type == "wave"
                else "COMPLETED_DIAGNOSTIC_STATIC_UNSTABLE"
            ),
            "run_type": self.config.run_type,
            "stereo_backend": "wass",
            "frame_count": run.frame_count,
            "point_count": point_total,
            "water_plane_rms": {"unit": "m", "per_frame": [frame["water_plane_rms_m"] for frame in frame_results]},
            "height_range": {
                "unit": "m",
                "minimum": min(frame["height_range_m"][0] for frame in frame_results),
                "maximum": max(frame["height_range_m"][1] for frame in frame_results),
            },
            "height_representation": "irregular_point_samples_X_Y_H_no_interpolation",
            "pixel_xyz": {
                "count": point_total,
                "storage": "pixel_xyz/<frame_id>_pixel_xyz.npz",
                "method": "project unscaled mesh_cam camera coordinates with per-workdir P0cam",
                "coordinate_system_is_recorded_per_frame": True,
                "original_unrectified_pixel_claimed": False,
            },
            "height_reference": {
                "method": "external_static_reference_plane" if self.config.reference_plane_file else "first_static_frame_fitted_plane",
                "frame_id": reference_frame_id,
                "normal": reference_normal.tolist(),
                "offset_m": reference_offset_m,
                "source": reference_source,
                "warning": reference_warning,
            },
            "input": {"left_video": str(self.config.left_video), "right_video": str(self.config.right_video)},
            "calibration": {
                "source": str(calibration.source_path), "baseline_m": calibration.baseline_m,
                "quality_mode": self.config.calibration_quality_mode,
                "approved_for_wass": calibration.approved_for_wass,
                "manual_measurement_used_for_reconstruction": False,
            },
            "processing": {
                "completed_stages": list(run.completed_stages), "autocalibrate_run": False,
                "surface_distance_threshold_m": self.config.surface_distance_threshold_m,
                "disparity_artifact": "WASS 8-bit diagnostic visualization; not lossless numeric disparity",
            },
            "frames": frame_results,
            "validation": {"pipeline_closure": "PASS", "static_stability": "FAIL_PRESERVED", "industrial_accuracy": "NOT_ESTABLISHED"},
        }
        result_json = write_result_json(output / "reconstruction_result.json", result)
        report = write_report(output / "reconstruction_report.md", result)
        return ReconstructionRunResult(output, result_json, report, str(result["status"]), run.frame_count, point_total)
