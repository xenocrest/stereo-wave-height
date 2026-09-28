from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from pipeline.instantaneous_validation.schemas import PROVENANCE, ReferencePlane


def frame_times(run_dir: str | Path) -> dict[int, float]:
    sync = json.loads((Path(run_dir) / "sync" / "sync.json").read_text(encoding="utf-8"))
    if sync.get("status") == "PROVIDED":
        return {int(row["index"]): float(row["time_s"]) for row in sync["frames"]}
    return {int(row["output_index"]): float(row["left_requested_timestamp_s"])
            for row in sync["frame_mapping"]}


def load_frame(run_dir: str | Path, frame_id: int, reference: ReferencePlane) -> dict:
    root = Path(run_dir)
    with np.load(root / "pixel" / "pixel_height" / f"{frame_id:08d}.npz", allow_pickle=False) as data:
        units = str(data["units"])
        xyz, source = data["xyz"].copy(), data["source"].copy()
    if units not in {"m", "B"}:
        raise ValueError(f"unsupported official coordinate unit: {units}")
    if not np.isin(source, list(PROVENANCE)).all():
        raise ValueError("unknown pixel provenance code")
    height = reference.height(xyz)
    height[(source == 0) | ~np.isfinite(xyz).all(axis=2)] = np.nan
    times = frame_times(root)
    if frame_id not in times:
        raise ValueError(f"frame {frame_id} has no recorded timestamp")
    return {"frame_id": frame_id, "timestamp_s": times[frame_id], "xyz": xyz, "height": height,
            "source": source, "units": units, "reference_plane_id": reference.plane_id}


def export_csv(run_dir: str | Path, frame_ids: list[int], reference: ReferencePlane,
               output: str | Path, stride: int = 1) -> dict:
    if stride < 1:
        raise ValueError("stride must be >= 1")
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with target.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["frame_id", "timestamp", "u", "v", "X", "Y", "Z", "H_mm", "provenance", "reference_plane_id"])
        for frame_id in frame_ids:
            frame = load_frame(run_dir, frame_id, reference)
            if frame["units"] != "m":
                raise ValueError("H_mm cannot be exported from baseline-normalized B units")
            xyz, height, source = frame["xyz"], frame["height"], frame["source"]
            for v in range(0, height.shape[0], stride):
                for u in range(0, height.shape[1], stride):
                    p = xyz[v, u]
                    h = height[v, u]
                    writer.writerow([frame_id, f'{frame["timestamp_s"]:.9f}', u, v,
                                     *[f"{float(x):.9f}" if np.isfinite(x) else "" for x in p],
                                     f"{float(h)*1000:.6f}" if np.isfinite(h) else "",
                                     PROVENANCE[int(source[v, u])], reference.plane_id])
                    count += 1
    return {"csv": str(target), "rows": count, "stride": stride, "frame_ids": frame_ids,
            "scope": "sampled pixels" if stride > 1 else "all pixels"}
