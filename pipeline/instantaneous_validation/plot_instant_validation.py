from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from pipeline.instantaneous_validation.load_vision import load_frame
from pipeline.instantaneous_validation.schemas import ReferencePlane


def plot_frame(run_dir: str | Path, frame_id: int, reference: ReferencePlane,
               comparisons: list[dict], output: str | Path, fallback: bool = False) -> str:
    frame = load_frame(run_dir, frame_id, reference)
    image = frame["height"] * (1000 if frame["units"] == "m" else 1)
    unit = "mm" if frame["units"] == "m" else "B (normalized)"
    fig, ax = plt.subplots(figsize=(12, 7), constrained_layout=True)
    plot = ax.imshow(np.ma.masked_invalid(image), cmap="turbo", origin="upper")
    fig.colorbar(plot, ax=ax, label=f"H ({unit})")
    for row in comparisons:
        if row.get("u") is not None:
            ax.plot(row["u"], row["v"], "wo", mec="black", ms=7)
            ax.annotate(f'{row["sensor_id"]}: vision={row["H_vision_mm"]:.2f} mm, '
                        f'truth={row["H_true_mm"]:.2f} mm, ΔH={row["DeltaH_mm"]:+.2f} mm'
                        if row.get("DeltaH_mm") is not None else f'{row["sensor_id"]}: {row["status"]}',
                        (row["u"], row["v"]), color="white", fontsize=8,
                        bbox={"facecolor": "black", "alpha": 0.65})
    ax.set_title(f'H(x,y,t_k) | frame={frame_id} | t={frame["timestamp_s"]:.6f} s'
                 + (" | EXTRINSIC_FALLBACK" if fallback else "")
                 + f"\nreference={reference.plane_id} ({reference.mode})")
    ax.set_xlabel("u (pixel)")
    ax.set_ylabel("v (pixel)")
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(target, dpi=150)
    plt.close(fig)
    return str(target)
