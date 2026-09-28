from __future__ import annotations

import argparse
import json
from pathlib import Path
import webbrowser

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import plotly.graph_objects as go
from plyfile import PlyData
import yaml

from pipeline.instantaneous_validation.load_vision import frame_times
from pipeline.instantaneous_validation.schemas import reference_from_config


def _first_pair(run_dir: Path) -> tuple[Path, Path]:
    left = sorted((run_dir / "sync" / "frames" / "cam0").glob("*"))
    right = sorted((run_dir / "sync" / "frames" / "cam1").glob("*"))
    if not left or not right:
        raise FileNotFoundError("synchronized frame pair not found")
    return left[0], right[0]


def _sync_preview(run_dir: Path) -> str:
    left_path, right_path = _first_pair(run_dir)
    left, right = cv2.imread(str(left_path)), cv2.imread(str(right_path))
    if left is None or right is None:
        raise ValueError("cannot read synchronized preview pair")
    height = min(left.shape[0], right.shape[0], 720)
    def resize(image: np.ndarray) -> np.ndarray:
        width = round(image.shape[1] * height / image.shape[0])
        return cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)
    canvas = np.hstack([resize(left), resize(right)])
    target = run_dir / "visualization" / "synchronized_pair.png"
    cv2.imwrite(str(target), canvas)
    return str(target)


def _height_products(run_dir: Path) -> tuple[str, str]:
    npz_path = sorted((run_dir / "pixel" / "pixel_height").glob("*.npz"))[0]
    with np.load(npz_path, allow_pickle=False) as data:
        xyz = data["xyz"]
        height = data["height"] if "height" in data.files else xyz[..., 2]
        source = data["source"]
        units = str(data["units"])
    frame_id = int(npz_path.stem)
    timestamp_s = frame_times(run_dir)[frame_id]
    snapshot = yaml.safe_load((run_dir / "config_snapshot.yaml").read_text(encoding="utf-8"))
    if snapshot.get("reference"):
        reference = reference_from_config(snapshot["reference"], run_dir)
        height = reference.height(xyz)
        height[(source == 0) | ~np.isfinite(xyz).all(axis=2)] = np.nan
        reference_label = reference.plane_id
    else:
        reference_label = "WASS_INTERNAL_MEAN_PLANE_ALIGNMENT; not a measured fixed physical plane"
    display_unit = "mm" if units == "m" else "B (normalized)"
    display_height = height * (1000 if units == "m" else 1)
    output = run_dir / "visualization" / "height_map"
    output.mkdir(parents=True, exist_ok=True)
    png = output / f"{npz_path.stem}.png"
    figure, axis = plt.subplots(figsize=(12, 7), constrained_layout=True)
    image = axis.imshow(display_height, cmap="turbo")
    axis.set_title(f"H(x,y,t_k) | frame={frame_id} | t={timestamp_s:.6f} s\n{reference_label}")
    axis.set_xlabel("u (pixel)")
    axis.set_ylabel("v (pixel)")
    figure.colorbar(image, ax=axis, label=f"H ({display_unit})")
    figure.savefig(png, dpi=160)
    plt.close(figure)

    stride = max(1, int(np.ceil(max(height.shape) / 900)))
    h = display_height[::stride, ::stride]
    p = xyz[::stride, ::stride]
    s = source[::stride, ::stride]
    vv, uu = np.mgrid[0 : height.shape[0] : stride, 0 : height.shape[1] : stride]
    label = np.where(s == 2, "OFFICIAL_GRID_ESTIMATE", np.where(s == 1, "DIRECT_STEREO", "NO_DATA"))
    custom = np.empty(h.shape + (8,), dtype=object)
    for index, values in enumerate((uu, vv, p[..., 0], p[..., 1], p[..., 2], h, label,
                                    np.full(h.shape, timestamp_s))):
        custom[..., index] = values
    plot = go.Figure(
        go.Heatmap(
            z=h,
            customdata=custom,
            colorscale="Turbo",
            colorbar={"title": f"H ({display_unit})"},
            hovertemplate=(
                "pixel=(%{customdata[0]}, %{customdata[1]})<br>"
                "X=%{customdata[2]:.6g}<br>Y=%{customdata[3]:.6g}<br>"
                "Z=%{customdata[4]:.6g}<br>H=%{customdata[5]:.6g} " + display_unit + "<br>"
                "timestamp=%{customdata[7]:.6f} s<br>source=%{customdata[6]}<extra></extra>"
            ),
        )
    )
    validation_path = run_dir / "validation" / "instantaneous_validation_report.json"
    if validation_path.is_file():
        recorded = json.loads(validation_path.read_text(encoding="utf-8"))
        rows = recorded.get("frames", {}).get(str(frame_id), [])
        placed = [row for row in rows if row.get("u") is not None]
        if placed:
            plot.add_trace(go.Scatter(
                x=[row["u"] / stride for row in placed],
                y=[row["v"] / stride for row in placed],
                mode="markers", name="Independent sensors",
                marker={"size": 10, "color": "white", "line": {"color": "black", "width": 2}},
                text=[f'{row["sensor_id"]}<br>H_true={row.get("H_true_mm")} mm<br>ΔH={row.get("DeltaH_mm")} mm<br>{row["status"]}'
                      for row in placed],
                hovertemplate="%{text}<extra></extra>",
            ))
    plot.update_layout(title=f"H(x,y,t_k) | frame={frame_id} | t={timestamp_s:.6f} s | {reference_label}",
                       xaxis_title="u", yaxis_title="v", yaxis_autorange="reversed")
    html = run_dir / "visualization" / "interactive_height.html"
    plot.write_html(html, include_plotlyjs=True, full_html=True)
    return str(png), str(html)


def _pointcloud(run_dir: Path) -> str | None:
    files = sorted((run_dir / "reconstruction" / "ply").glob("*.ply"))
    if not files:
        return None
    vertex = PlyData.read(files[0])["vertex"].data
    xyz = np.column_stack([vertex[name] for name in ("x", "y", "z")])
    step = max(1, int(np.ceil(len(xyz) / 50_000)))
    shown = xyz[::step]
    plot = go.Figure(
        go.Scatter3d(
            x=shown[:, 0], y=shown[:, 1], z=shown[:, 2], mode="markers",
            marker={"size": 1.5, "color": shown[:, 2], "colorscale": "Turbo"},
            hovertemplate="X=%{x:.6g}<br>Y=%{y:.6g}<br>Z=%{z:.6g}<extra></extra>",
        )
    )
    plot.update_layout(title=f"Official WASS point cloud ({len(xyz):,} points; display sample {len(shown):,})")
    target = run_dir / "visualization" / "pointcloud_preview.html"
    plot.write_html(target, include_plotlyjs=True, full_html=True)
    return str(target)


def build(run_dir: str | Path) -> dict[str, str | None]:
    root = Path(run_dir).resolve()
    outputs = {
        "synchronized_pair": _sync_preview(root),
        "height_map": None,
        "interactive_height": None,
        "pointcloud_preview": None,
    }
    outputs["height_map"], outputs["interactive_height"] = _height_products(root)
    outputs["pointcloud_preview"] = _pointcloud(root)
    (root / "visualization" / "visualization_report.json").write_text(
        json.dumps(outputs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="View unmodified official pipeline outputs")
    parser.add_argument("run_dir")
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()
    outputs = build(args.run_dir)
    print(json.dumps(outputs, ensure_ascii=False, indent=2))
    if not args.no_open and outputs["interactive_height"]:
        webbrowser.open(Path(outputs["interactive_height"]).as_uri())


if __name__ == "__main__":
    main()

