"""Isolated official-WASSfast trial inputs from frozen HomeTank_004 geometry.

No calibration, new reconstruction, GUI change, or reference fitting. The only
geometry here maps a predeclared image polygon onto the frozen reference plane
to select the official gridder's domain. Frame decoding does not alter videos.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess

import numpy as np


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--official-setup", action="store_true")
    args = parser.parse_args()
    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    root, wd = Path(cfg["output"]), Path(cfg["frozen_workdir"])
    if args.official_setup:
        from wassgridsurface.wassgridsurface import setup
        plan = json.loads((root / "input_manifest.json").read_text())
        setup(str(wd), np.loadtxt(wd / "plane.txt"), cfg["baseline_m"],
              str(root / "grid"), plan["grid_center_m"], plan["grid_side_m"],
              plan["grid_side_m"], 256, 256, Iw=1920, Ih=1080, fps=cfg["fps"])
        return

    import cv2 as cv
    import yaml
    from wassgridsurface.wass_utils import compute_sea_plane_RT, load_camera_mesh
    root.mkdir(parents=True, exist_ok=False)
    (root / "grid").mkdir()
    calib = yaml.safe_load(Path(cfg["calibration"]).read_text(encoding="utf-8"))
    if not np.isclose(calib["stereo"]["baseline_m"], cfg["baseline_m"], rtol=1e-12):
        raise ValueError("Frozen baseline mismatch")
    plane = np.loadtxt(wd / "plane.txt")
    rotation, translation = compute_sea_plane_RT(plane)
    frozen = load_camera_mesh(wd / "mesh_cam.xyzC")
    residual = (plane[:3] @ frozen + plane[3]) * cfg["baseline_m"]
    k1 = np.asarray(calib["mono_cam1"]["K"])
    d1 = np.asarray(calib["mono_cam1"]["D"])
    # Canonical distorted pixels -> undistorted camera rays -> frozen plane.
    roi = np.asarray(cfg["candidate_roi_cam1_px"], dtype=float)
    rays = cv.undistortPoints(roi.reshape(-1,1,2), k1, d1).reshape(-1,2)
    rays = np.column_stack((rays, np.ones(len(rays))))
    distances = -plane[3] / (rays @ plane[:3])
    if not np.isfinite(distances).all() or np.any(distances <= 0):
        raise ValueError("ROI rays do not meet the frozen plane in front of camera")
    plane_points = ((rays*distances[:,None]) @ rotation.T + translation.ravel()) * cfg["baseline_m"]
    lo, hi = plane_points[:,:2].min(axis=0), plane_points[:,:2].max(axis=0)
    plan = {"status": "DIAGNOSTIC_NOT_PHYSICAL_APPROVAL", "grid_center_m": ((lo+hi)/2).tolist(),
            "grid_side_m": float(np.max(hi-lo)), "roi_plane_xy_m": plane_points[:,:2].tolist(),
            "frozen_plane": plane.tolist(), "reference_residual_rms_m": float(np.sqrt(np.mean(residual**2))),
            "reference_sha256": sha(wd/'plane.txt'), "calibration_sha256": sha(cfg['calibration']),
            "candidate_roi_cam1_px": roi.tolist(), "roi_selection": "predeclared analyst polygon NOT user confirmed",
            "frames": [], "warning": "CALIBRATION_QUALITY_FAIL and STATIC_VALIDATION_FAIL preserved; sync candidate only"}
    shutil.copytree(cfg["wass_config"], root / "config")
    shutil.copyfile(cfg["official_settings"], root / "settings.cfg")
    for condition, timing in cfg["sequences"].items():
        for side in (0,1):
            video = cfg["videos"][condition][side]
            target_dir = root / condition / "input" / f"cam{side}"
            target_dir.mkdir(parents=True)
            capture = cv.VideoCapture(video)
            if not capture.isOpened():
                raise ValueError(f"Cannot open {video}")
            capture.set(cv.CAP_PROP_ORIENTATION_AUTO, 0)
            for index in range(cfg["frame_count"]):
                target = timing["left_start_s"] + index/cfg["fps"] + (timing["right_minus_left_s"] if side else 0)
                capture.set(cv.CAP_PROP_POS_MSEC, target*1000)
                ok, image = capture.read()
                actual = capture.get(cv.CAP_PROP_POS_MSEC)/1000
                if not ok:
                    raise ValueError("Frame decode failed")
                if side == 0:
                    image = cv.rotate(image, cv.ROTATE_180)
                if image.shape[:2] != (1080,1920):
                    raise ValueError("Unexpected canonical image size")
                image = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
                path = target_dir / f"{index:06d}_{round(index/cfg['fps']*1000):013d}_{side:02d}.png"
                if not cv.imwrite(str(path), image):
                    raise IOError(path)
                plan["frames"].append({"condition":condition,"side":side,"frame":index,
                    "target_s":target,"actual_s":actual,"image":str(path),"sha256":sha(path)})
            capture.release()
    (root / "input_manifest.json").write_text(json.dumps(plan,indent=2)+"\n", encoding="utf-8")
    subprocess.run([cfg["gridder_python"], str(Path(__file__).resolve()), "--config", str(args.config.resolve()),
                    "--official-setup"], check=True)
    print(json.dumps({k:v for k,v in plan.items() if k != "frames"},indent=2))


if __name__ == "__main__":
    main()
