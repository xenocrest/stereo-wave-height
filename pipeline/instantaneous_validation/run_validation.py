from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline.instantaneous_validation.compare_instant import compare_frame
from pipeline.instantaneous_validation.generate_report import write_report
from pipeline.instantaneous_validation.load_ground_truth import load_layout, load_truth
from pipeline.instantaneous_validation.load_vision import export_csv, frame_times
from pipeline.instantaneous_validation.schemas import read_yaml, reference_from_config


def run(config: dict, run_dir: str | Path, output_dir: str | Path, synthetic: bool = False) -> dict:
    root = Path(run_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    reference = reference_from_config(config["reference"], root)
    (out / "fixed_reference_plane.json").write_text(json.dumps(reference.as_dict(), indent=2), encoding="utf-8")
    frame_ids = [int(i) for i in config.get("frame_ids", frame_times(root).keys())]
    csv_info = None
    if config.get("export_vision_csv", True):
        csv_info = export_csv(root, frame_ids, reference, out / "instantaneous_height.csv",
                              int(config.get("export_stride", 1)))
        (out / "instantaneous_height_manifest.json").write_text(json.dumps(csv_info, indent=2), encoding="utf-8")
    truth = config.get("truth")
    if not truth:
        frames = {frame_id: [] for frame_id in frame_ids}
        report = write_report(root, reference, frames, out, synthetic=synthetic,
                              fallback=config.get("extrinsic_fallback", False))
        return {"reference": reference.as_dict(), "csv": csv_info, "report": report["report"]}
    rows = load_truth(truth["data_file"])
    layout_meta = read_yaml(truth["sensor_layout"])
    if layout_meta.get("coordinate_system") != reference.coordinate_system:
        raise ValueError("sensor layout coordinate_system does not match fixed reference plane")
    layout = load_layout(truth["sensor_layout"])
    sync = read_yaml(truth["sync_file"])["truth_sync"]
    validation = config["validation"]
    frames = {frame_id: compare_frame(root, frame_id, reference, rows, layout, sync,
                                     float(validation["max_time_difference_ms"]),
                                     float(validation["max_spatial_distance_mm"])) for frame_id in frame_ids}
    report = write_report(root, reference, frames, out, synthetic=synthetic,
                          fallback=config.get("extrinsic_fallback", False))
    return {"reference": reference.as_dict(), "csv": csv_info, "report": report["report"],
            "status": report["status"]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate instantaneous official WASS output against independent sensor samples")
    parser.add_argument("config")
    parser.add_argument("run_dir")
    parser.add_argument("output_dir")
    args = parser.parse_args()
    result = run(read_yaml(args.config), args.run_dir, args.output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
