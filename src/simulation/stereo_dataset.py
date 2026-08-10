"""Small synthetic stereo dataset writer for the documented WASS input boundary."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import numpy as np

from .imaging import render_surface, save_grayscale_png
from .stereo_rig import IdealStereoRig
from .surfaces import SurfaceTruth
from .texture import planar_random_texture


@dataclass(frozen=True)
class GeneratedStereoDataset:
    """Paths and frame count for one generated dataset."""

    root: Path
    manifest_path: Path
    calibration_path: Path
    ground_truth_path: Path
    frame_count: int


def _camera_calibration_text(rig: IdealStereoRig) -> str:
    intrinsics = rig.intrinsics
    k = intrinsics.matrix
    return f"""# Simulation nominal calibration; not a measured camera calibration.
schema_version: 1
status: SIMULATION_NOMINAL
camera_model: {intrinsics.equipment.model}
image:
  width_px: {intrinsics.equipment.width_px}
  height_px: {intrinsics.equipment.height_px}
  encoding: mono8
candidate_equipment:
  pixel_size_um: {intrinsics.equipment.pixel_size_um}
  focal_length_mm: {intrinsics.equipment.focal_length_mm}
intrinsics_px:
  fx: {intrinsics.fx_px:.15g}
  fy: {intrinsics.fy_px:.15g}
  cx: {intrinsics.cx_px:.15g}
  cy: {intrinsics.cy_px:.15g}
K: [[{k[0, 0]:.15g}, 0, {k[0, 2]:.15g}], [0, {k[1, 1]:.15g}, {k[1, 2]:.15g}], [0, 0, 1]]
distortion:
  model: ideal_pinhole
  coefficients: [0, 0, 0, 0, 0]
  status: ideal_simulation_assumption
stereo:
  baseline_m: {rig.baseline_m:.15g}
  working_distance_m: {rig.working_distance_m:.15g}
  status: simulation_input
coordinate_system: {rig.coordinate_system}
unit: {rig.unit}
"""


def generate_stereo_dataset(
    output_root: str | Path,
    *,
    rig: IdealStereoRig,
    surface: SurfaceTruth,
    texture_seed: int,
    splat_radius_px: int = 1,
) -> GeneratedStereoDataset:
    """Generate PNG pairs, simulation calibration, truth, and a JSON manifest."""
    root = Path(output_root)
    if root.exists() and any(root.iterdir()):
        raise FileExistsError("output_root must be absent or empty; existing data is not overwritten")
    for relative in ("left", "right", "calibration", "metadata", "ground_truth"):
        (root / relative).mkdir(parents=True, exist_ok=True)
    if surface.coordinate_system != rig.coordinate_system or surface.unit != rig.unit:
        raise ValueError("surface and stereo rig metadata must match")

    texture = planar_random_texture(surface.x_m, surface.y_m, seed=texture_seed)
    frames: list[dict[str, Any]] = []
    for index, timestamp in enumerate(surface.timestamp_ns):
        points = surface.points_at(index)
        left = render_surface(rig.left, points, texture, splat_radius_px=splat_radius_px)
        right = render_surface(rig.right, points, texture, splat_radius_px=splat_radius_px)
        filename = f"{index:06d}.png"
        left_relative = Path("left") / filename
        right_relative = Path("right") / filename
        save_grayscale_png(root / left_relative, left.image)
        save_grayscale_png(root / right_relative, right.image)
        frames.append(
            {
                "frame_id": f"{index:06d}",
                "timestamp_ns": int(timestamp),
                "left_image": left_relative.as_posix(),
                "right_image": right_relative.as_posix(),
            }
        )

    ground_truth_relative = Path("ground_truth") / "height_fields.npz"
    np.savez_compressed(
        root / ground_truth_relative,
        x_m=surface.x_m,
        y_m=surface.y_m,
        timestamp_ns=surface.timestamp_ns,
        z0_m=surface.z0_m,
        h_true_m=surface.h_true_m,
        z_true_m=surface.z_true_m,
    )
    calibration_relative = Path("calibration") / "camera.yaml"
    (root / calibration_relative).write_text(_camera_calibration_text(rig), encoding="utf-8")

    intrinsics = rig.intrinsics
    manifest = {
        "schema_version": 1,
        "dataset_type": "synthetic_stereo_wass_input_adapter",
        "camera": {
            "model": intrinsics.equipment.model,
            "status": intrinsics.equipment.camera_status,
            "intrinsics_status": intrinsics.status,
            "width_px": intrinsics.equipment.width_px,
            "height_px": intrinsics.equipment.height_px,
            "pixel_size_um": intrinsics.equipment.pixel_size_um,
            "focal_length_mm": intrinsics.equipment.focal_length_mm,
            "encoding": "mono8",
            "format": "PNG",
        },
        "simulation_parameters": {
            "surface_model": surface.model,
            "baseline_m": rig.baseline_m,
            "working_distance_m": rig.working_distance_m,
            "texture_seed": int(texture_seed),
            "texture_source": texture.source,
            "splat_radius_px": splat_radius_px,
            "coordinate_system": rig.coordinate_system,
            "unit": rig.unit,
        },
        "calibration": calibration_relative.as_posix(),
        "ground_truth_reference": {
            "path": ground_truth_relative.as_posix(),
            "fields": ["x_m", "y_m", "timestamp_ns", "z0_m", "h_true_m", "z_true_m"],
            "height_unit": "m",
            "time_unit": "ns",
            "coordinate_system": surface.coordinate_system,
        },
        "frames": frames,
    }
    manifest_path = root / "metadata" / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return GeneratedStereoDataset(
        root=root,
        manifest_path=manifest_path,
        calibration_path=root / calibration_relative,
        ground_truth_path=root / ground_truth_relative,
        frame_count=len(frames),
    )

