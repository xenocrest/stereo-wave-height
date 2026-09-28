"""Render three recorded instants per existing run without rerunning WASS."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline.instantaneous_validation.load_vision import frame_times
from pipeline.instantaneous_validation.plot_instant_validation import plot_frame
from pipeline.instantaneous_validation.schemas import ReferencePlane


def render(run_dir: str | Path, output_dir: str | Path, count: int = 3, fallback: bool = False) -> dict:
    root, target = Path(run_dir), Path(output_dir)
    times = frame_times(root)
    chosen = sorted(times)[:count]
    if len(chosen) < count:
        raise ValueError("recorded run has fewer frames than requested")
    # Existing archived grids were aligned by official WASS mean-plane machinery.
    # This zero plane is an internal display coordinate, not an independently measured physical datum.
    reference = ReferencePlane("WASS_INTERNAL_MEAN_PLANE_VISUALIZATION_ONLY", (0.0, 0.0, 1.0),
                               0.0, "internal_algorithm_plane", "official_grid")
    products = []
    for frame_id in chosen:
        path = plot_frame(root, frame_id, reference, [], target / f"instant_{frame_id:08d}.png", fallback)
        products.append({"frame_id": frame_id, "timestamp_s": times[frame_id], "image": path,
                         "reference": reference.plane_id})
    target.mkdir(parents=True, exist_ok=True)
    report = {"status": "INSTANTANEOUS_VISUALIZATION_PASS", "source_run": str(root),
              "physical_truth_validation": False, "extrinsic_fallback": fallback, "frames": products}
    (target / "render_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir")
    parser.add_argument("output_dir")
    parser.add_argument("--fallback", action="store_true")
    args = parser.parse_args()
    print(json.dumps(render(args.run_dir, args.output_dir, fallback=args.fallback), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
