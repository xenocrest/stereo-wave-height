from __future__ import annotations

import csv
import json
from pathlib import Path

from pipeline.instantaneous_validation.plot_instant_validation import plot_frame
from pipeline.instantaneous_validation.schemas import ReferencePlane


def write_report(run_dir: str | Path, reference: ReferencePlane, frames: dict[int, list[dict]],
                 output_dir: str | Path, fallback: bool = False, synthetic: bool = False) -> dict:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    columns = ["frame_id", "timestamp", "sensor_id", "H_vision_mm", "H_true_mm", "DeltaH_mm",
               "abs_DeltaH_mm", "delta_t_ms", "spatial_distance_mm", "provenance", "status",
               "t_vision", "t_gt", "x_vision_mm", "y_vision_mm", "x_gt_mm", "y_gt_mm",
               "u", "v", "reference_plane_id"]
    with (root / "instantaneous_validation_table.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for rows in frames.values():
            writer.writerows(rows)
    lines = ["# 瞬时高度逐点验证", "", f"Reference: `{reference.plane_id}`", "",
             "SYNTHETIC DATA — PROGRAM LOGIC ONLY; NO PHYSICAL ACCURACY CLAIM." if synthetic
             else "Independent sensor comparison; each row represents one time and one measured position.", ""]
    for frame_id, rows in sorted(frames.items()):
        image = plot_frame(run_dir, frame_id, reference, rows, root / f"frame_{frame_id:08d}.png", fallback)
        timestamp = rows[0]["timestamp"] if rows else None
        lines += [f"## Frame ID: {frame_id}; Timestamp: {timestamp} s", "", f"![Instantaneous height]({Path(image).name})", "",
                  "| Sensor | Hvision (mm) | Htrue (mm) | ΔH (mm) | abs(ΔH) (mm) | Δt (ms) | distance (mm) | provenance | Result |",
                  "|---|---:|---:|---:|---:|---:|---:|---|---|"]
        for row in rows:
            values = [row.get(key) for key in ("sensor_id", "H_vision_mm", "H_true_mm", "DeltaH_mm",
                                               "abs_DeltaH_mm", "delta_t_ms", "spatial_distance_mm", "provenance", "status")]
            lines.append("| " + " | ".join("—" if item is None else f"{item:.3f}" if isinstance(item, float) else str(item)
                                           for item in values) + " |")
        lines.append("")
    (root / "instantaneous_validation_report.md").write_text("\n".join(lines), encoding="utf-8")
    eligible = any(row.get("status") in {"PASS_LT_10MM", "FAIL_GE_10MM"}
                   for rows in frames.values() for row in rows)
    status = ("SYNTHETIC_VALIDATION_FRAMEWORK_PASS" if synthetic and eligible else
              "INSTANTANEOUS_VALIDATION_RECORDED" if eligible else
              "INSTANTANEOUS_VALIDATION_NO_ALIGNED_COMPARISON")
    payload = {"status": status,
               "synthetic": synthetic, "reference": reference.as_dict(), "frames": frames,
               "report": str(root / "instantaneous_validation_report.md")}
    (root / "instantaneous_validation_report.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
