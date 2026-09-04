"""Map official output to existing project height code without model changes."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from adapters.wassfast.output import read_cnn_output
from reconstruction.height import height_from_plane


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    result = read_cnn_output(args.input, args.config)
    g = result.grid
    xx, yy = np.meshgrid(g.x, g.y)
    heights = np.full_like(g.z, np.nan)
    frames = []
    for index, z in enumerate(g.z):
        good = g.valid_mask[index]
        points = np.column_stack((xx[good], yy[good], z[good]))
        h = height_from_plane(points, np.array([0., 0., 1.]), 0.)
        heights[index, good] = h
        frames.append({"output_index": index, "timestamp_ns": int(g.timestamp_ns[index]),
                       "finite_estimate_fraction": float(good.mean()),
                       "raw_support_fraction": (float(result.raw_support_mask[index].mean())
                                                if result.raw_support_mask is not None else None),
                       "height_min_m": float(h.min()), "height_max_m": float(h.max()),
                       "height_mean_m": float(h.mean()), "height_rms_m": float(np.sqrt(np.mean(h*h)))})
    np.savez_compressed(args.output / "height_estimates.npz", x_m=g.x, y_m=g.y,
                        height_m=heights, timestamp_ns=g.timestamp_ns,
                        finite_estimate_mask=g.valid_mask,
                        **({"raw_support_mask": result.raw_support_mask}
                           if result.raw_support_mask is not None else {}))
    report = {"status": "OFFICIAL_SAMPLE_TO_PROJECT_HEIGHT_PASS_NOT_ACCURACY_VALIDATED",
              "source": str(args.input), "source_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
              "config_sha256": hashlib.sha256(args.config.read_bytes()).hexdigest(),
              "coordinate_system": g.coordinate_system, "unit": g.unit,
              "height_reference": "official config plane, normal=[0,0,1], offset=0 in plane coordinates; NOT camera Z",
              "frame_count": len(frames), "grid_shape_yx": list(g.z.shape[1:]),
              "grid_extent_m": [float(g.x[0]), float(g.x[-1]), float(g.y[0]), float(g.y[-1])],
              "baseline_m": result.baseline_m, "finite_estimate_fraction": float(g.valid_mask.mean()),
              "raw_support_fraction": (float(result.raw_support_mask.mean()) if result.raw_support_mask is not None else None),
              "source_workdir_is_unique": len(np.unique(result.source_workdir)) == len(result.source_workdir),
              "timestamp_policy": "retain upstream relative time; upstream example overrides source filename timing with 15 Hz",
              "physical_accuracy": "NOT_VALIDATED_NO_INDEPENDENT_REFERENCE",
              "HomeTank_006_status": "NOT_RUN_WITH_THIS_MODEL",
              "frames": frames}
    (args.output / "result.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
    extent = report["grid_extent_m"]
    raw = result.raw_support_mask[0] if result.raw_support_mask is not None else np.zeros_like(g.z[0])
    axes[0].imshow(raw, origin="lower", extent=extent, cmap="gray", vmin=0, vmax=1)
    axes[0].set_title("Official sparse observation support")
    im = axes[1].imshow(heights[0], origin="lower", extent=extent, cmap="coolwarm")
    axes[1].set_title("Official CNN estimated height (not ground truth)")
    fig.colorbar(im, ax=axes[1], label="Height above official plane (m)")
    for ax in axes:
        ax.set_xlabel("Plane X (m)")
        ax.set_ylabel("Plane Y (m)")
    fig.savefig(args.output / "support_and_estimate.png", dpi=130)
    plt.close(fig)
    print(json.dumps({k:v for k,v in report.items() if k != "frames"}, indent=2))


if __name__ == "__main__":
    main()
