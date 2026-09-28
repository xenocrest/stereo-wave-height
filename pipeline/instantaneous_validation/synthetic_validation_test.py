"""Complete synthetic validation dry run using an existing official WASS result."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
import yaml

from pipeline.run_pipeline import load_config
from pipeline.instantaneous_validation.load_vision import frame_times
from pipeline.instantaneous_validation.run_validation import run as run_validation


def run(config_path: str | Path) -> dict:
    settings = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    if settings.get("synthetic_only") is not True:
        raise ValueError("dry run must explicitly declare synthetic_only: true")
    source = Path(settings["source_run"])
    output = Path(settings["output_dir"])
    output.mkdir(parents=True, exist_ok=True)
    saved = load_config(source / "config_snapshot.yaml")
    pipeline_report = json.loads((source / "run_report.json").read_text(encoding="utf-8"))
    if pipeline_report["status"] != settings["expected_pipeline_status"]:
        raise ValueError("source run has not passed the expected official pipeline")
    frame_id = int(settings["frame_id"])
    timestamp = frame_times(source)[frame_id]
    with np.load(source / "pixel" / "pixel_height" / f"{frame_id:08d}.npz", allow_pickle=False) as data:
        xyz, source_code, units = data["xyz"], data["source"], str(data["units"])
    if units != "m":
        raise ValueError("dry-run sensor heights require a metric WASS run")
    valid = np.argwhere((source_code == 2) & np.isfinite(xyz).all(axis=2))
    if len(valid) < 3:
        raise ValueError("source run has insufficient official grid estimates")
    picks = valid[[len(valid) // 4, len(valid) // 2, 3 * len(valid) // 4]]
    reference_id = "SYNTHETIC_TEST_PLANE_NOT_PHYSICAL"
    layout = {"coordinate_system": "official_grid_m", "sensors": []}
    truth = []
    for index, (v, u) in enumerate(picks):
        x, y, z = (float(value) for value in xyz[v, u])
        sensor_id = f"Synthetic_{chr(65 + index)}"
        layout["sensors"].append({"id": sensor_id, "x_mm": x * 1000, "y_mm": y * 1000,
                                  "z_datum_mm": 0, "origin": "synthetic program test; coordinates selected from frozen WASS grid"})
        expected_delta = [4.2, -12.0, 0.0][index]
        truth.append({"timestamp": timestamp - 0.002, "sensor_id": sensor_id,
                      "x": x * 1000, "y": y * 1000, "H_true_mm": z * 1000 - expected_delta,
                      "quality_flag": "GOOD", "reference_plane_id": reference_id})
    layout_path, truth_path, sync_path = (output / name for name in ("sensor_layout.yaml", "ground_truth.csv", "truth_sync.yaml"))
    layout_path.write_text(yaml.safe_dump(layout, allow_unicode=True, sort_keys=False), encoding="utf-8")
    with truth_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(truth[0]))
        writer.writeheader()
        writer.writerows(truth)
    sync_path.write_text(yaml.safe_dump({"truth_sync": {"method": "provided_offset", "offset_ms": 2.0,
                                                         "source": "synthetic known offset for software test",
                                                         "confidence": "synthetic_exact"}}, sort_keys=False), encoding="utf-8")
    config = {"reference": {"mode": "provided_physical_plane", "coordinate_system": "official_grid_m",
                             "reference_plane_id": reference_id, "n_x": 0.0, "n_y": 0.0, "n_z": 1.0, "d": 0.0},
              "truth": {"data_file": str(truth_path), "sensor_layout": str(layout_path), "sync_file": str(sync_path)},
              "validation": {"max_time_difference_ms": 5.0, "max_spatial_distance_mm": 2.0},
              "frame_ids": [frame_id], "export_stride": int(settings["export_stride"]),
              "extrinsic_fallback": True}
    (output / "experiment.yaml").write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
    result = run_validation(config, source, output / "validation", synthetic=True)
    rows = json.loads((output / "validation" / "instantaneous_validation_report.json").read_text(encoding="utf-8"))["frames"][str(frame_id)]
    expected = ["PASS_LT_10MM", "FAIL_GE_10MM", "PASS_LT_10MM"]
    if [row["status"] for row in rows] != expected:
        raise AssertionError(f"synthetic validation produced unexpected statuses: {rows}")
    result["status"] = "PRE_HARDWARE_DRY_RUN_PASS"
    result["source_pipeline_status"] = pipeline_report["status"]
    result["synthetic_only"] = True
    result["source_pipeline_config_validated"] = saved["project"]
    (output / "dry_run_report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", nargs="?", default=str(Path(__file__).resolve().parents[2] / "examples" / "pre_hardware_dry_run" / "config.yaml"))
    args = parser.parse_args()
    print(json.dumps(run(args.config), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
