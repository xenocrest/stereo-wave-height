"""CLI for one video/image request through reconstruction and dense height."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from synchronization.tolerance import OnDemandSyncTolerancePolicy

from .single_frame import DenseHeightSpec, SingleFrameMeasurementBackend, SingleFrameMeasurementRequest, SynchronizationSpec


def _path(base: Path, value: str | None) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    return path if path.is_absolute() else (base / path).resolve()


def load_request(path: str | Path) -> SingleFrameMeasurementRequest:
    source = Path(path).resolve(); base = source.parent
    data = yaml.safe_load(source.read_text(encoding="utf-8"))
    inputs, processing, output = data["input"], data["processing"], data["output"]
    sync_data = data.get("synchronization")
    synchronization = None if sync_data is None else SynchronizationSpec(
        float(sync_data["a"]), float(sync_data["b_s"]), str(sync_data["source"]),
        str(sync_data["confidence"]), bool(sync_data["frame_level_established"]),
        int(sync_data["event_count"]), float(sync_data["fit_residual_rmse_s"]),
        float(sync_data["fit_residual_max_abs_s"]),
    )
    tolerance_data = data.get("on_demand_sync_tolerance")
    tolerance = None if tolerance_data is None else OnDemandSyncTolerancePolicy(
        str(tolerance_data["status"]), int(tolerance_data["strict_max_abs_frames"]),
        int(tolerance_data["warning_max_abs_frames"]), str(tolerance_data["evidence_source"]),
    )
    dense_data = data.get("dense_height", {"enabled": False})
    completion = dense_data.get("surface_completion", {})
    dense = DenseHeightSpec(
        enabled=bool(dense_data.get("enabled", False)), mapping_file=_path(base, dense_data.get("mapping_file")),
        water_roi=dense_data.get("water_roi"), observation_gate_px=float(dense_data.get("observation_gate_px", 2.0)),
        method=str(completion.get("method", "mls_quadratic")),
        max_gap_spacing_multiplier=float(completion.get("max_gap_spacing_multiplier", 3.0)),
        common_fov_file=_path(base,dense_data.get("common_fov_file")),
    )
    rotations = inputs.get("canonical_rotation_deg", {})
    return SingleFrameMeasurementRequest(
        input_mode=str(data["input_mode"]), output_dir=_path(base, output["directory"]),
        calibration_source=_path(base, data["calibration"]["source"]),
        wass_config_dir=_path(base, processing["wass_config_dir"]),
        wass_runtime_binding=_path(base, processing["wass_runtime_binding"]),
        ffmpeg_executable=_path(base, inputs["ffmpeg_executable"]),
        synchronization_source=str(data["synchronization_source"]),
        left_video=_path(base, inputs.get("left_video")), right_video=_path(base, inputs.get("right_video")),
        left_image=_path(base, inputs.get("left_image")), right_image=_path(base, inputs.get("right_image")),
        target_time_s=inputs.get("target_time_s"), synchronization=synchronization,
        left_rotation_deg=int(rotations.get("left", 0)), right_rotation_deg=int(rotations.get("right", 0)),
        calibration_quality_mode=str(data["calibration"].get("quality_mode", "require_approved")),
        reference_plane_file=_path(base, processing.get("reference_plane_file")),
        surface_distance_threshold_m=float(processing.get("surface_distance_threshold_m", 0.01)),
        synchronization_tolerance=tolerance, dense_height=dense,
        solve_mode=str(data.get("solve_mode","legacy")),
        reference_artifact_file=_path(base,processing.get("reference_artifact_file")),
        calibration_id=data.get("calibration",{}).get("calibration_id"),
        calibration_package_hash=data.get("calibration",{}).get("package_hash"),
        video_pair_id=data.get("input",{}).get("video_pair_id"),
    )


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--config", required=True)
    request = load_request(parser.parse_args().config)
    result = SingleFrameMeasurementBackend().run(request)
    print(result.status)
    return 0 if result.status not in {"WASS_RECONSTRUCTION_FAILED", "SINGLE_FRAME_RECONSTRUCTION_COMPLETED_DENSE_HEIGHT_FAILED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
