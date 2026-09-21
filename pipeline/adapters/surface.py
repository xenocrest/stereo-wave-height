from __future__ import annotations

from pathlib import Path
import shutil
from typing import Any

import numpy as np
import scipy.io as sio

from pipeline.common import CommandRecorder, StageFailure, copy_file, write_json


def _grid_domain(workspaces: list[Path], baseline: float, config: dict[str, Any]) -> tuple[float, float, float, str]:
    if all(key in config for key in ("area_center_x", "area_center_y", "area_size")):
        return float(config["area_center_x"]), float(config["area_center_y"]), float(config["area_size"]), "explicit YAML configuration"
    # Official decoder and official sea-plane alignment are used only to choose
    # the rectangular plotting domain. They do not change any WASS point.
    from wassgridsurface.wass_utils import align_on_sea_plane, load_camera_mesh

    planes = np.vstack([np.loadtxt(path / "plane.txt") for path in workspaces])
    extent_plane = np.median(planes, axis=0)
    points = align_on_sea_plane(load_camera_mesh(workspaces[0] / "mesh_cam.xyzC"), extent_plane) * baseline
    lo, hi = points[:2].min(axis=1), points[:2].max(axis=1)
    center = (lo + hi) / 2
    side = float(np.max(hi - lo))
    if not np.isfinite(side) or side <= 0:
        raise ValueError("official point cloud did not provide a finite grid domain")
    return float(center[0]), float(center[1]), side, "extent of first official WASS mesh after official sea-plane alignment"


def _ply_count(path: Path) -> int | None:
    if not path.is_file():
        return None
    with path.open("rb") as stream:
        for _ in range(50):
            line = stream.readline().decode("ascii", errors="replace").strip()
            if line.startswith("element vertex "):
                return int(line.split()[-1])
            if line == "end_header":
                break
    return None


def run(
    config: dict[str, Any],
    tools: dict[str, Any],
    sync_report: dict[str, Any],
    run_dir: Path,
    recorder: CommandRecorder,
) -> dict[str, Any]:
    workspaces = sorted((run_dir / "wass" / "workspaces").glob("*_wd"))
    if not workspaces:
        raise ValueError("no WASS workspaces available for surface gridding")
    for workspace in workspaces:
        if not (workspace / "mesh_cam.xyzC").is_file() or not (workspace / "plane.txt").is_file():
            raise StageFailure("surface", f"incomplete official WASS workspace: {workspace}")

    output = run_dir / "surface"
    output.mkdir(parents=True, exist_ok=True)
    planes = np.vstack([np.loadtxt(workspace / "plane.txt") for workspace in workspaces])
    np.savetxt(run_dir / "wass" / "workspaces" / "planes.txt", planes)
    np.savetxt(output / "planes.txt", planes)
    baseline = float(config["baseline_m"])
    center_x, center_y, side, domain_source = _grid_domain(workspaces, baseline, config)
    grid_n = int(config.get("N", 256))
    (output / "gridconfig.txt").write_text(
        f"[Area]\narea_center_x={center_x}\narea_center_y={center_y}\narea_size={side}\nN={grid_n}\n",
        encoding="ascii",
    )
    python_dir = Path(tools["python"]).parent
    gridder = python_dir / "wassgridsurface.exe"
    ncplot = python_dir / "wassncplot.exe"
    fps = float(sync_report.get("fps") or sync_report.get("output_sampling_fps") or 1.0)
    recorder.run(
        "wassgridsurface_setup",
        [
            gridder, "--action", "setup", run_dir / "wass" / "workspaces", output,
            "--gridconfig", output / "gridconfig.txt", "--baseline", str(baseline),
            "--fps", str(fps), "--stereo_image_idx", "0",
        ],
    )
    recorder.run(
        "wassgridsurface_grid",
        [
            gridder, "--action", "grid", run_dir / "wass" / "workspaces", output,
            "--gridsetup", output / "config.mat", "--num_frames", str(len(workspaces)),
            "--parallel", str(config.get("parallel", 1)), "--stereo_image_idx", "0",
        ],
    )
    netcdf = output / "gridded.nc"
    if not netcdf.is_file():
        raise StageFailure("wassgridsurface", f"official NetCDF output missing: {netcdf}")

    mapping_dir = run_dir / "pixel" / "pixel_xyz"
    mapping_dir.mkdir(parents=True, exist_ok=True)
    recorder.run(
        "wassncplot",
        [
            ncplot, netcdf, mapping_dir, "-f", "0", "-l", str(len(workspaces)),
            "--savexyz", "--save-img", "--no-textoverlay", "--pxscale", "1",
        ],
    )
    overlay_dir = run_dir / "visualization" / "overlay"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    for image in mapping_dir.glob("*.png"):
        shutil.copy2(image, overlay_dir / image.name)

    height_dir = run_dir / "pixel" / "pixel_height"
    height_dir.mkdir(parents=True, exist_ok=True)
    mapping_reports = []
    units = config.get("units", "m")
    for mat_path in sorted(mapping_dir.glob("*.mat")):
        data = sio.loadmat(mat_path)
        if "px_2_3D" not in data:
            continue
        xyz = np.asarray(data["px_2_3D"], np.float64)
        valid = np.isfinite(xyz).all(axis=2)
        valid &= ~np.all(np.isclose(xyz, 0.0), axis=2)
        valid &= ~np.all(np.isclose(xyz, 1.0), axis=2)
        height = np.full(xyz.shape[:2], np.nan, np.float64)
        # wassgridsurface has already aligned the official grid with its mean
        # sea plane, therefore n=(0,0,1), d=0 and H=n^T P+d=Z.
        height[valid] = xyz[..., 2][valid]
        source = np.zeros(xyz.shape[:2], np.uint8)
        source[valid] = 2  # OFFICIAL_GRID_ESTIMATE; code 1 is reserved for direct stereo observations.
        target = height_dir / f"{mat_path.stem}.npz"
        np.savez_compressed(
            target,
            xyz=xyz,
            height=height,
            source=source,
            units=units,
            equation="H = n^T P + d; official aligned grid uses n=(0,0,1), d=0",
            source_labels=np.asarray(["NO_DATA", "DIRECT_STEREO", "OFFICIAL_GRID_ESTIMATE"]),
        )
        mapping_reports.append(
            {
                "frame": mat_path.stem,
                "mapping_mat": str(mat_path),
                "pixel_height": str(target),
                "valid_grid_estimate_pixels": int(valid.sum()),
                "direct_stereo_pixels": 0,
                "no_data_pixels": int((~valid).sum()),
                "units": units,
            }
        )
    if not mapping_reports:
        raise StageFailure("wassncplot", "official pixel-to-XYZ mapping was not generated")

    plane_record = {
        "method": "official WASS plane.txt inputs and official wassgridsurface setup mean-plane alignment",
        "raw_wass_planes": planes.tolist(),
        "grid_setup": str(output / "config.mat"),
        "height_equation": "H = n^T P + d; after official alignment n=(0,0,1), d=0, so H=Z",
        "baseline_m": baseline,
        "units": units,
        "grid_domain": {"center_x": center_x, "center_y": center_y, "size": side, "N": grid_n, "source": domain_source},
    }
    write_json(output / "plane.json", plane_record)
    point_counts = [_ply_count(workspace / "mesh.ply") for workspace in workspaces]
    report = {
        "status": "PASS",
        "gridded_netcdf": str(netcdf),
        "frame_count": len(workspaces),
        "official_ply_point_counts": point_counts,
        "mapping": mapping_reports,
        "plane": plane_record,
    }
    write_json(output / "surface_report.json", report)
    return report

