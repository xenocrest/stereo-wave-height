"""Task adapter: new official WASS workspaces with a frozen official grid setup.

No calibration, matching, alignment, interpolation or height algorithms live here.
"""
from pathlib import Path
import json
import shutil
import subprocess
import traceback

import numpy as np
from scipy.io import loadmat

from app import core, coordinates
from pipeline.adapters import sync, wass
from pipeline.common import CommandRecorder, require_empty, sha256, write_json


def run(config: dict, directory: Path) -> dict:
    root = require_empty(directory.resolve())
    recorder = CommandRecorder(root / "logs" / "pipeline")
    report = {"run_directory": str(root), "status": "RUNNING", "stages": {},
              "third_party_algorithm_modifications": 0,
              "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=core.ROOT,
                  capture_output=True, text=True, check=True).stdout.strip()}
    stage = "reference"
    try:
        binding = config["presentation"]["frozen_reference"]
        reference, _ = core.reference_from_metadata(binding)
        origin = Path(binding["scientific_run"])
        core.validate_run_inputs(origin, config)
        ids = coordinates.identity(origin)
        coordinates.require_match(reference, ids)
        if ids["coordinate_system"] != f"official_wass_grid_{config['surface'].get('units', 'm')}":
            raise ValueError("REFERENCE_FRAME_MISMATCH: output coordinate units changed")
        origin_setup = origin / "surface" / "config.mat"
        setup = loadmat(origin_setup)
        if float(config["surface"]["baseline_m"]) != float(setup["CAM_BASELINE"].item()):
            raise ValueError("REFERENCE_FRAME_MISMATCH: metric baseline changed")
        original_summary = json.loads((origin / "wass" / "run_summary.json").read_text(encoding="utf-8"))
        active = original_summary["active_calibration"]
        if active["fallback"] and not config["wass"].get("allow_extrinsic_fallback", False):
            raise ValueError("Frozen EXTRINSICS_FALLBACK requires explicit allow_extrinsic_fallback")
        for folder in ("calibration", "wass/config", "surface", "pixel/pixel_xyz", "pixel/pixel_height",
                       "reconstruction/xyz", "reconstruction/ply"):
            (root / folder).mkdir(parents=True, exist_ok=True)
        for path in (origin / "wass" / "config").iterdir():
            if path.is_file():
                shutil.copy2(path, root / "wass" / "config" / path.name)
                shutil.copy2(path, root / "calibration" / path.name)
        if (origin / "calibration" / "report.json").is_file():
            shutil.copy2(origin / "calibration" / "report.json", root / "calibration" / "report.json")
        shutil.copy2(origin_setup, root / "surface" / "config.mat")
        shutil.copy2(origin / "surface" / "coordinate_contract.json", root / "surface" / "coordinate_contract.json")
        write_json(root / "reference_plane.json", binding)
        core.save_project(config, root / "config_snapshot.yaml")
        stage = "sync"
        sync_report = sync.run(config["source_type"], config["sync"], config["tools"], root, core.ROOT, recorder)
        report["stages"]["sync"] = sync_report
        stage = "wass"
        workspaces = wass._prepare(wass._pairs(root / "sync"), root / "wass" / "workspaces",
                                   root / "wass" / "config", Path(config["tools"]["wass_bin"]),
                                   recorder, "fixed")
        for index, workspace in enumerate(workspaces):
            recorder.run(f"stereo_{index:06d}", [Path(config["tools"]["wass_bin"]) / "wass_stereo.exe",
                                                root / "wass" / "config" / "stereo_config.txt", workspace])
            coordinates.validate_workspace(workspace, root / "surface" / "config.mat")
            for source, target in (("mesh_cam.xyzC", f"xyz/{index:06d}.xyzC"),
                                   ("mesh.ply", f"ply/{index:06d}.ply")):
                shutil.copy2(workspace / source, root / "reconstruction" / target)
        summary = {"status": "FROZEN_EXTRINSICS_REUSED", "active_calibration": active,
                   "frozen_source_run": str(origin), "frame_count": len(workspaces),
                   "note": "No new autocalibration; exact confirmed calibration/pose reused for official prepare/stereo."}
        write_json(root / "wass" / "run_summary.json", summary)
        report["stages"]["wass"] = summary
        stage = "surface"
        binaries = Path(config["tools"]["python"]).parent
        recorder.run("wassgridsurface_grid", [binaries / "wassgridsurface.exe", "--action", "grid",
            root / "wass" / "workspaces", root / "surface", "--gridsetup", root / "surface" / "config.mat",
            "--num_frames", str(len(workspaces)), "--parallel", str(config["surface"].get("parallel", 1)),
            "--stereo_image_idx", "0"])
        mapping = root / "pixel" / "pixel_xyz"
        recorder.run("wassncplot", [binaries / "wassncplot.exe", root / "surface" / "gridded.nc", mapping,
            "-f", "0", "-l", str(len(workspaces)), "--savexyz", "--save-img", "--no-textoverlay", "--pxscale", "1"])
        # Output-format adapter: identical validity/provenance convention to the
        # frozen pipeline. Only read official px_2_3D; do not alter any XYZ.
        mapped = []
        for path in sorted(mapping.glob("*.mat")):
            xyz = np.asarray(loadmat(path)["px_2_3D"], np.float64)
            valid = np.isfinite(xyz).all(axis=2)
            valid &= ~np.all(np.isclose(xyz, 0.), axis=2) & ~np.all(np.isclose(xyz, 1.), axis=2)
            source = np.where(valid, 2, 0).astype(np.uint8)
            np.savez_compressed(root / "pixel" / "pixel_height" / f"{path.stem}.npz",
                xyz=xyz, height=np.where(valid, xyz[..., 2], np.nan), source=source,
                units=config["surface"].get("units", "m"))
            mapped.append({"frame": path.stem, "valid_grid_estimate_pixels": int(valid.sum())})
        if len(mapped) != len(workspaces):
            raise ValueError("Official mapping frame count differs from reconstructed workspaces")
        coordinates.require_match(reference, coordinates.identity(root))
        write_json(root / "coordinate_frame.json", {**ids, "frozen_source_run": str(origin),
            "grid_setup_sha256": sha256(root / "surface" / "config.mat"), "mapping": mapped})
        write_json(root / "run_report.json", report)
        for index in range(len(workspaces)):
            requested = float(sync_report["frame_mapping"][index]["left_requested_timestamp_s"])
            core.write_frame_manifest(root, requested, reference.plane_id, index)
        report["stages"]["surface"] = {"mapping": mapped, "grid_setup_source": str(origin_setup)}
        report.update(status="FIXED_COORDINATE_FRAME_PASS", **ids)
    except Exception as error:
        report.update(status=f"FAILED_AT_{stage.upper()}", error={"type": type(error).__name__,
                       "message": str(error), "traceback": traceback.format_exc()})
        raise
    finally:
        write_json(root / "run_report.json", report)
    return report
