"""Input and validation contract for the unmodified official sea-plane setup."""
import json
from pathlib import Path

import cv2
import numpy as np
from scipy.io import loadmat

from pipeline.common import sha256, write_json

COORDINATE_CONTRACT = "OFFICIAL_UNIT_PLANE_RIGID_GRID_V2"


def unit_plane(plane):
    p = np.asarray(plane, dtype=np.float64)
    if p.shape != (4,) or not np.isfinite(p).all():
        raise ValueError("PLANE_CONTRACT: requires finite [a,b,c,d]")
    length = float(np.linalg.norm(p[:3]))
    if length <= 1e-12:
        raise ValueError("PLANE_CONTRACT: zero/cancelled mean normal")
    p = p / length  # d must use the SAME divisor to preserve the plane equation.
    if p[0] ** 2 + p[1] ** 2 <= 1e-12:
        raise ValueError("PLANE_CONTRACT: official formula singular for a=b=0")
    return p


def setup_input(raw_planes):
    raw = np.asarray(raw_planes, dtype=np.float64)
    if raw.ndim != 2 or raw.shape[1] != 4 or not len(raw) or not np.isfinite(raw).all():
        raise ValueError("PLANE_CONTRACT: requires finite Nx4 WASS observations")
    mean = np.mean(raw, axis=0)
    canonical = unit_plane(mean)
    # Official CLI uses loadtxt then mean(axis=0): a single line becomes scalar.
    # These are adapter input rows, NOT additional WASS observations.
    rows = np.tile(canonical, (max(2, len(raw)), 1))
    return rows, {"coordinate_contract": COORDINATE_CONTRACT,
        "raw_wass_observation_count": len(raw), "raw_mean_plane": mean.tolist(),
        "normalization_divisor": float(np.linalg.norm(mean[:3])),
        "canonical_mean_plane": canonical.tolist(), "official_cli_input_rows": len(rows),
        "input_rows_meaning": "identical canonical mean; not independent observations"}


def rotation_metrics(setup):
    R = np.asarray(setup["Rpl"], dtype=np.float64)
    return {"orthogonality_frobenius": float(np.linalg.norm(R.T @ R - np.eye(3))),
            "determinant": float(np.linalg.det(R))}


def require_rigid(setup):
    for key in ("Rpl", "Tpl", "RTplane"):
        if not np.isfinite(setup[key]).all():
            raise ValueError("REFERENCE_FRAME_MISMATCH: nonfinite official transform")
    if np.asarray(setup['Rpl']).shape != (3, 3) or np.asarray(setup['RTplane']).shape != (4, 4):
        raise ValueError("REFERENCE_FRAME_MISMATCH: malformed official transform")
    metrics = rotation_metrics(setup)
    if metrics["orthogonality_frobenius"] > 1e-10 or abs(metrics["determinant"] - 1) > 1e-10:
        raise ValueError("REFERENCE_FRAME_MISMATCH: nonrigid legacy Rpl; regenerate setup/reference")
    R, T = setup["Rpl"], np.asarray(setup["Tpl"]).reshape(3, 1)
    inverse = np.vstack((np.hstack((R.T, -R.T @ T)), [0, 0, 0, 1]))
    if not np.allclose(setup["RTplane"], inverse, atol=1e-12, rtol=1e-12):
        raise ValueError("REFERENCE_FRAME_MISMATCH: official inverse plane transform differs")
    return metrics


def real_point_metrics(setup, workspace):
    from wassgridsurface.wass_utils import load_camera_mesh, align_on_sea_plane_RT
    points = load_camera_mesh(Path(workspace) / "mesh_cam.xyzC")
    # Deterministically spread across actual decoded WASS observations, not the grid.
    indices = np.linspace(0, points.shape[1]-1, min(1000, points.shape[1]), dtype=int)
    camera = points[:, indices]
    baseline = float(setup["CAM_BASELINE"].item())
    if not np.isfinite(baseline) or baseline <= 0:
        raise ValueError("PLANE_CONTRACT: positive finite baseline required")
    grid = align_on_sea_plane_RT(camera, setup["Rpl"], setup["Tpl"]) * baseline
    homogeneous = lambda p: np.vstack((p, np.ones(p.shape[1])))
    D = np.diag([1/baseline, 1/baseline, -1/baseline, 1])
    restored = (setup["RTplane"] @ D @ homogeneous(grid))[:3]
    errors = np.linalg.norm(restored-camera, axis=0)
    image = cv2.imread(str(Path(workspace) / "undistorted/00000000.png"))
    if image is None:
        raise ValueError("PLANE_CONTRACT: official camera image missing")
    h, w = image.shape[:2]
    to_norm = np.array([[2/w, 0, -1, 0], [0, 2/h, -1, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
    stats = lambda x: {"median": float(np.median(x)), "max": float(np.max(x))}
    output = {**rotation_metrics(setup), "actual_wass_point_count": len(indices),
              "camera_grid_camera_error_B": stats(errors), "cameras": {}}
    for i in (0, 1):
        P = setup[f"P{i}cam"] @ homogeneous(camera)
        before = P[:2] / P[2]
        plane = setup[f"P{i}plane"] @ homogeneous(grid)
        after = (plane[:2] / plane[2] + 1) * np.array([[w/2], [h/2]])
        K = np.eye(4); K[:3, :3] = setup[f"K{i}"]
        P4 = np.vstack((setup[f"P{i}cam"], [0, 0, 0, 1]))
        camera_local = np.linalg.inv(K) @ P4 @ homogeneous(camera)
        via_matrix = setup[f"Cam{i}toGrid"] @ camera_local
        forward_error = np.linalg.norm(via_matrix[:3] - grid, axis=0)
        # setup output must embody the same public formula, not just a unit R.
        expected = to_norm @ P4 @ setup["RTplane"] @ D
        output["cameras"][str(i)] = {"reprojection_px": stats(np.linalg.norm(after-before, axis=0)),
            "official_forward_matrix_vs_alignment_native": stats(forward_error),
            "projection_matrix_formula_max": float(np.max(np.abs(expected-setup[f"P{i}plane"]))) }
    return output


def certify_setup(setup_path, workspaces, input_record):
    setup_path = Path(setup_path)
    setup = loadmat(setup_path)
    require_rigid(setup)
    results = [real_point_metrics(setup, workspace) for workspace in workspaces]
    for result in results:
        if result["camera_grid_camera_error_B"]["max"] > 1e-9:
            raise ValueError("PLANE_CONTRACT: official camera/grid inverse failed")
        for camera in result["cameras"].values():
            if (camera["reprojection_px"]["max"] > 1e-7 or
                camera["official_forward_matrix_vs_alignment_native"]["max"] > 1e-9 or
                camera["projection_matrix_formula_max"] > 1e-10):
                raise ValueError("PLANE_CONTRACT: official forward/projection disagrees")
    record = {**input_record, "config_mat_sha256": sha256(setup_path), "actual_point_validation": results}
    write_json(setup_path.parent / "coordinate_contract.json", record)
    return record


def require_certified(setup_path):
    setup_path = Path(setup_path)
    marker = setup_path.parent / "coordinate_contract.json"
    if not marker.is_file():
        raise ValueError("REFERENCE_FRAME_MISMATCH: legacy coordinate contract; regenerate reference/cache")
    record = json.loads(marker.read_text(encoding="utf-8"))
    if record.get("coordinate_contract") != COORDINATE_CONTRACT or record.get("config_mat_sha256") != sha256(setup_path):
        raise ValueError("REFERENCE_FRAME_MISMATCH: missing/changed certified setup")
    require_rigid(loadmat(setup_path))
    return record
