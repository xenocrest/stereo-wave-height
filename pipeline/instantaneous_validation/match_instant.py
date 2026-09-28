from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree


def nearest_truth(rows: list[dict], sensor_id: str, vision_time_s: float,
                  offset_ms: float, max_difference_ms: float) -> tuple[dict | None, float | None]:
    candidates = [row for row in rows if row["sensor_id"] == sensor_id and row["quality_flag"] == "GOOD"]
    if not candidates:
        return None, None
    row = min(candidates, key=lambda item: abs(item["timestamp"] + offset_ms / 1000 - vision_time_s))
    delta_ms = (row["timestamp"] + offset_ms / 1000 - vision_time_s) * 1000
    return row, delta_ms


def nearest_vision(xyz: np.ndarray, source: np.ndarray, x_mm: float, y_mm: float,
                   max_distance_mm: float) -> tuple[tuple[int, int] | None, float | None]:
    valid = (source != 0) & np.isfinite(xyz).all(axis=2)
    vv, uu = np.nonzero(valid)
    if not len(vv):
        return None, None
    xy_mm = xyz[vv, uu, :2] * 1000
    distance, index = cKDTree(xy_mm).query([x_mm, y_mm])
    return ((int(uu[index]), int(vv[index])) if distance <= max_distance_mm else None), float(distance)
