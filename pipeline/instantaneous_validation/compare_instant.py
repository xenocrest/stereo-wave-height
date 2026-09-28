from __future__ import annotations

import math

from pipeline.instantaneous_validation.load_vision import load_frame
from pipeline.instantaneous_validation.match_instant import nearest_truth, nearest_vision
from pipeline.instantaneous_validation.schemas import PROVENANCE, ReferencePlane


def compare_frame(run_dir, frame_id: int, reference: ReferencePlane, truth_rows: list[dict],
                  layout: dict[str, dict], sync: dict, max_time_difference_ms: float,
                  max_spatial_distance_mm: float, threshold_mm: float = 10.0) -> list[dict]:
    if max_time_difference_ms < 0 or max_spatial_distance_mm < 0 or threshold_mm <= 0:
        raise ValueError("validation gates must be nonnegative and threshold positive")
    if sync.get("method") != "provided_offset" or sync.get("offset_ms") is None:
        raise ValueError("truth sync requires a measured, explicit provided_offset")
    if not math.isfinite(float(sync["offset_ms"])):
        raise ValueError("truth sync offset must be finite")
    if not sync.get("source") or sync["source"] == "TBD_AFTER_HARDWARE_ARRIVAL":
        raise ValueError("truth sync source must document how offset was measured")
    frame = load_frame(run_dir, frame_id, reference)
    if frame["units"] != "m":
        raise ValueError("metric ground truth cannot be compared with normalized B units")
    results = []
    for sensor_id, sensor in layout.items():
        x_gt, y_gt = float(sensor["x_mm"]), float(sensor["y_mm"])
        base = {"frame_id": frame_id, "timestamp": frame["timestamp_s"], "sensor_id": sensor_id,
                "reference_plane_id": reference.plane_id, "x_gt_mm": x_gt, "y_gt_mm": y_gt,
                "t_vision": frame["timestamp_s"], "t_gt": None, "delta_t_ms": None,
                "x_vision_mm": None, "y_vision_mm": None, "spatial_distance_mm": None,
                "u": None, "v": None, "H_vision_mm": None, "H_true_mm": None,
                "DeltaH_mm": None, "abs_DeltaH_mm": None, "provenance": "NO_DATA"}
        row, delta = nearest_truth(truth_rows, sensor_id, frame["timestamp_s"],
                                   float(sync["offset_ms"]), max_time_difference_ms)
        base["delta_t_ms"] = delta
        if row is not None:
            base["t_gt"] = row["timestamp"]
        if row is None or delta is None or abs(delta) > max_time_difference_ms:
            base["status"] = "TIME_NOT_ALIGNED"
            results.append(base)
            continue
        if not math.isclose(row["x"], x_gt, abs_tol=1e-6) or not math.isclose(row["y"], y_gt, abs_tol=1e-6):
            base["status"] = "SENSOR_LAYOUT_MISMATCH"
            results.append(base)
            continue
        pixel, spatial = nearest_vision(frame["xyz"], frame["source"], x_gt, y_gt, max_spatial_distance_mm)
        base["spatial_distance_mm"] = spatial
        if pixel is None:
            base["status"] = "SPACE_NOT_ALIGNED" if spatial is not None else "NO_DATA"
            results.append(base)
            continue
        u, v = pixel
        point = frame["xyz"][v, u]
        base.update({"u": u, "v": v, "x_vision_mm": float(point[0] * 1000),
                     "y_vision_mm": float(point[1] * 1000),
                     "H_vision_mm": float(frame["height"][v, u] * 1000),
                     "provenance": PROVENANCE[int(frame["source"][v, u])]})
        if base["provenance"] == "NO_DATA":
            base["status"] = "NO_DATA"
            results.append(base)
            continue
        if isinstance(row.get("H_true_mm"), float):
            if row.get("reference_plane_id") != reference.plane_id:
                base["status"] = "REFERENCE_DATUM_MISMATCH"
                results.append(base)
                continue
            h_true = row["H_true_mm"]
        elif isinstance(row.get("Z_true_mm"), float):
            if row.get("coordinate_system") != reference.coordinate_system:
                base["status"] = "REFERENCE_DATUM_MISMATCH"
                results.append(base)
                continue
            h_true = float(reference.height([x_gt / 1000, y_gt / 1000, row["Z_true_mm"] / 1000]) * 1000)
        else:
            base["status"] = "MISSING_TRUE_HEIGHT"
            results.append(base)
            continue
        delta_h = base["H_vision_mm"] - h_true
        base.update({"H_true_mm": h_true, "DeltaH_mm": delta_h, "abs_DeltaH_mm": abs(delta_h),
                     "status": "PASS_LT_10MM" if abs(delta_h) < threshold_mm
                     and not math.isclose(abs(delta_h), threshold_mm, rel_tol=0, abs_tol=1e-9)
                     else "FAIL_GE_10MM"})
        results.append(base)
    return results
