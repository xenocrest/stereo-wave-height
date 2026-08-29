"""Minimal canonical-pixel dense height map from frozen WASS observations."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from PIL import Image, ImageDraw
from scipy.spatial import ConvexHull, cKDTree

from .mls import evaluate_holdout, quadratic_mls_predict

OBSERVED, ESTIMATED, UNSUPPORTED = np.uint8(1), np.uint8(2), np.uint8(0)


def rasterize_water_roi(
    roi: dict[str, Any], *, width: int, height: int, observed_rectified_px: np.ndarray,
    canonical_rectified_px: np.ndarray,
) -> np.ndarray:
    """Rasterize an explicit canonical polygon or the safe observed hull."""
    roi_type = str(roi.get("type", "observed_convex_hull"))
    if roi_type == "observed_convex_hull":
        hull = ConvexHull(observed_rectified_px)
        return np.all(
            canonical_rectified_px @ hull.equations[:, :2].T + hull.equations[:, 2] <= 1e-7,
            axis=1,
        ).reshape(height, width)
    if roi_type != "polygon":
        raise ValueError("water ROI type must be observed_convex_hull or polygon")
    if roi.get("coordinate_system") != "canonical_cam1":
        raise ValueError("polygon water ROI must explicitly use canonical_cam1")
    points = np.asarray(roi.get("points"), dtype=np.float64)
    if points.ndim != 2 or points.shape[0] < 3 or points.shape[1] != 2 or not np.all(np.isfinite(points)):
        raise ValueError("polygon water ROI requires at least three finite [x,y] points")
    if np.any(points[:, 0] < 0) or np.any(points[:, 0] >= width) or np.any(points[:, 1] < 0) or np.any(points[:, 1] >= height):
        raise ValueError("polygon water ROI lies outside the canonical image")
    image = Image.new("1", (width, height), 0)
    ImageDraw.Draw(image).polygon([tuple(point) for point in points], fill=1)
    return np.asarray(image, dtype=bool)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _undistort_normalized(points_px: np.ndarray, k: np.ndarray, d: np.ndarray) -> np.ndarray:
    """Invert OpenCV's 5-coefficient Brown model for canonical pixels."""
    xd = (points_px[:, 0] - k[0, 2]) / k[0, 0]
    yd = (points_px[:, 1] - k[1, 2]) / k[1, 1]
    x, y = xd.copy(), yd.copy()
    k1, k2, p1, p2, k3 = d
    for _ in range(12):
        r2 = x * x + y * y
        radial = 1 + k1 * r2 + k2 * r2**2 + k3 * r2**3
        tx = 2 * p1 * x * y + p2 * (r2 + 2 * x * x)
        ty = p1 * (r2 + 2 * y * y) + 2 * p2 * x * y
        x = (xd - tx) / radial
        y = (yd - ty) / radial
    return np.column_stack((x, y))


def canonical_to_rectified(points_px: np.ndarray, mapping: dict[str, Any]) -> np.ndarray:
    """Apply the frozen canonical-cam1 to WASS-rectified mapping."""
    prepare, rectify = mapping["prepare_undistortion"], mapping["stereo_rectification"]
    k = np.asarray(prepare["K1"], dtype=np.float64)
    d = np.asarray(prepare["D1"], dtype=np.float64)
    rotation = np.asarray(rectify["R_computational_cam0"], dtype=np.float64)
    projection = np.asarray(rectify["P_computational_cam0"], dtype=np.float64)
    normalized = _undistort_normalized(np.asarray(points_px, dtype=np.float64), k, d)
    rays = np.column_stack((normalized, np.ones(normalized.shape[0]))) @ rotation.T
    homogeneous = np.column_stack((rays, np.ones(rays.shape[0]))) @ projection.T
    return homogeneous[:, :2] / homogeneous[:, 2, None]


def metric_projection(projection_unscaled: np.ndarray, scale_m_per_unit: float) -> np.ndarray:
    """Convert WASS P for unscaled camera coordinates to metric XYZ coordinates."""
    if scale_m_per_unit <= 0:
        raise ValueError("scale must be positive")
    result = np.asarray(projection_unscaled, dtype=np.float64).copy()
    result[:, 3] *= scale_m_per_unit
    return result


def ray_from_projection(pixel_uv: np.ndarray, projection_metric: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    matrix, translation = projection_metric[:, :3], projection_metric[:, 3]
    center = -np.linalg.solve(matrix, translation)
    direction = np.linalg.solve(matrix, np.asarray([pixel_uv[0], pixel_uv[1], 1.0]))
    direction /= np.linalg.norm(direction)
    return center, direction


def _ray_plane(center: np.ndarray, direction: np.ndarray, normal: np.ndarray, offset: float) -> np.ndarray:
    denominator = float(normal @ direction)
    if abs(denominator) < 1e-12:
        raise ValueError("ray is parallel to reference plane")
    return center + (-(float(normal @ center) + offset) / denominator) * direction


def plane_basis(normal: np.ndarray) -> np.ndarray:
    """Return two deterministic orthonormal physical axes spanning a plane."""
    unit = np.asarray(normal, dtype=np.float64) / np.linalg.norm(normal)
    seed = np.array([1.0, 0.0, 0.0]) if abs(unit[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    first = seed - unit * float(seed @ unit); first /= np.linalg.norm(first)
    second = np.cross(unit, first)
    return np.vstack((first, second))


def plane_xy(points: np.ndarray, normal: np.ndarray, basis: np.ndarray) -> np.ndarray:
    """Express 3-D points in metre-valued coordinates parallel to the reference plane."""
    unit = normal / np.linalg.norm(normal)
    projected = points - (points @ unit)[:, None] * unit
    return projected @ basis.T


def estimate_ray_surface(
    pixel_uv: np.ndarray, projection_metric: np.ndarray, support_xyz: np.ndarray,
    support_h: np.ndarray, support_xy: np.ndarray, support_tree: cKDTree,
    normal: np.ndarray, offset: float, basis: np.ndarray,
    seed_observation_xyz: np.ndarray,
    *, p90_spacing_m: float, maximum_gap_m: float, mls: dict[str, Any],
) -> tuple[float, dict[str, Any]]:
    """Intersect a calibrated ray with the local MLS height surface."""
    center, direction = ray_from_projection(pixel_uv, projection_metric)
    # Establish the required reference-plane intersection first, then move along
    # the same calibrated ray to the depth of the nearest *support seed*.  The
    # seed is not returned as an observation; the physical hole gate and MLS
    # still decide whether an estimate exists.
    point = _ray_plane(center, direction, normal, offset)
    seed_t = float((np.asarray(seed_observation_xyz) - center) @ direction)
    if np.isfinite(seed_t) and seed_t > 0:
        point = center + seed_t * direction
    denominator = float(normal @ direction) / float(np.linalg.norm(normal))
    if abs(denominator) < 1e-12:
        return float("nan"), {"status": "UNSUPPORTED_RAY_GEOMETRY"}
    radius = float(mls["radius_multiplier"]) * p90_spacing_m
    sigma = float(mls["sigma_multiplier"]) * p90_spacing_m
    last: dict[str, Any] = {}
    for iteration in range(20):
        query_xy = plane_xy(point[None, :], normal, basis)[0]
        nearest = float(support_tree.query(query_xy, k=1)[0])
        # The validated hole radius excludes observations *inside* 3*P90; the
        # first surviving discrete sample lies up to one P90 farther away.
        # This discretization allowance reproduces hole_2 without admitting
        # hole_3 (4.5*P90).
        inferred_gap = max(0.0, nearest - p90_spacing_m)
        if inferred_gap > maximum_gap_m:
            return float("nan"), {"status": "UNSUPPORTED_GAP", "nearest_support_m": nearest,
                                  "inferred_gap_m": inferred_gap}
        nearby = np.asarray(support_tree.query_ball_point(query_xy, radius), dtype=np.int64)
        prediction, last = quadratic_mls_predict(
            support_xy[nearby], support_h[nearby], query_xy,
            support_radius_m=radius, gaussian_sigma_m=sigma,
            minimum_points=int(mls["minimum_points"]), maximum_neighbors=int(mls["maximum_neighbors"]),
            maximum_condition_number=float(mls["maximum_condition_number"]),
        )
        if not np.isfinite(prediction):
            return prediction, last
        current_h = float((normal @ point + offset) / np.linalg.norm(normal))
        step = (prediction - current_h) / denominator
        if not np.isfinite(step) or abs(step) > 0.05:
            return float("nan"), {**last, "status": "UNSUPPORTED_NO_CONVERGENCE"}
        point = point + 0.5 * step * direction
        if abs(step) < 2e-7:
            return float(prediction), {**last, "iterations": iteration + 1, "nearest_support_m": nearest,
                                       "inferred_gap_m": inferred_gap}
    return float("nan"), {**last, "status": "UNSUPPORTED_NO_CONVERGENCE"}


def build_dense_map(config: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    frozen = config["frozen"]
    pixel_path, height_path = Path(frozen["pixel_xyz_npz"]), Path(frozen["height_npz"])
    original_hashes = {str(path): _sha256(path) for path in (pixel_path, height_path)}
    with np.load(pixel_path) as data:
        observed_uv = np.column_stack((data["u_px"], data["v_px"]))
        xyz = np.asarray(data["xyz_m"], dtype=np.float64)
        coordinate_system = str(data["pixel_coordinate_system"])
    with np.load(height_path) as data:
        height = np.asarray(data["height_m"], dtype=np.float64)
        water = np.asarray(data["water_mask"], dtype=bool)
    if xyz.shape[0] != height.size or water.shape != height.shape:
        raise ValueError("frozen pixel/height artifacts do not align")
    observed_uv, xyz, height = observed_uv[water], xyz[water], height[water]
    mapping = yaml.safe_load(Path(frozen["mapping_yaml"]).read_text(encoding="utf-8"))
    if "reference_plane" in frozen:
        plane = frozen["reference_plane"]
    else:
        plane = yaml.safe_load(Path(frozen["reference_plane_yaml"]).read_text(encoding="utf-8"))["plane"]
    normal, offset = np.asarray(plane["normal"], dtype=np.float64), float(plane["offset_m"])
    projection = metric_projection(np.loadtxt(frozen["projection_txt"]), float(frozen["calibrated_baseline_m"]))
    width, image_height = (int(v) for v in mapping["image_size_px"])
    yy, xx = np.indices((image_height, width), dtype=np.float64)
    canonical = np.column_stack((xx.ravel(), yy.ravel()))
    rectified = canonical_to_rectified(canonical, mapping)
    roi_config = config.get("water_roi", {"type": "observed_convex_hull"})
    roi = rasterize_water_roi(roi_config, width=width, height=image_height,
                              observed_rectified_px=observed_uv, canonical_rectified_px=rectified)
    roi_indices = np.flatnonzero(roi.ravel())
    basis = plane_basis(normal)
    support_xy = plane_xy(xyz, normal, basis)
    pixel_tree, physical_tree = cKDTree(observed_uv), cKDTree(support_xy)
    spacing = physical_tree.query(support_xy, k=2)[0][:, 1]
    p90 = float(np.percentile(spacing[spacing > 0], 90))
    max_gap = float(config["completion"]["maximum_gap_multiplier"]) * p90
    direct_gate = float(config["observation_gate_px"])
    dense_h = np.full(width * image_height, np.nan, dtype=np.float32)
    status = np.zeros(width * image_height, dtype=np.uint8)
    nearest_d, nearest_i = pixel_tree.query(rectified[roi_indices], k=1)
    direct = nearest_d <= direct_gate
    direct_indices = roi_indices[direct]
    dense_h[direct_indices] = height[nearest_i[direct]].astype(np.float32) * 1000
    status[direct_indices] = OBSERVED
    diagnostics: dict[int, dict[str, Any]] = {}
    rejection_reasons: dict[str, int] = {}
    rejection_nearest: list[float] = []
    missing_indices = roi_indices[~direct]
    missing_nearest = nearest_i[~direct]
    for flat_index, seed_index in zip(missing_indices, missing_nearest):
        value, diagnostic = estimate_ray_surface(
            rectified[flat_index], projection, xyz, height, support_xy, physical_tree,
            normal, offset, basis, xyz[int(seed_index)],
            p90_spacing_m=p90, maximum_gap_m=max_gap, mls=config["mls"],
        )
        if np.isfinite(value):
            dense_h[flat_index] = np.float32(value * 1000)
            status[flat_index] = ESTIMATED
        else:
            reason = str(diagnostic.get("status", "UNSUPPORTED_UNKNOWN"))
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
            if "nearest_support_m" in diagnostic:
                rejection_nearest.append(float(diagnostic["nearest_support_m"]))
        if int(flat_index) in config.get("diagnostic_flat_indices", []):
            diagnostics[int(flat_index)] = diagnostic
    dense_h = dense_h.reshape(image_height, width)
    status = status.reshape(image_height, width)
    output = Path(config["output_directory"]); output.mkdir(parents=True, exist_ok=True)
    stem = str(config.get("artifact_stem", "dense_height_case2"))
    metadata = {
        "classification": "DENSE_HEIGHT_MAP_MVP_COMPLETED", "source_frame": frozen["frame_identity"],
        "coordinate_system": coordinate_system, "output_pixel_system": "canonical_cam1",
        "reference_plane": plane, "observation_gate_px": direct_gate,
        "metric_scale_source": "frozen OpenCV calibrated baseline",
        "calibrated_baseline_m": float(frozen["calibrated_baseline_m"]),
        "p90_spacing_m": p90, "maximum_gap_m": max_gap,
        "completion_rule": "hole_2 = 3 * frame P90 nearest-neighbor spacing",
        "water_roi": roi_config,
    }
    np.savez_compressed(output / f"{stem}.npz", height_mm=dense_h, status=status,
                        valid_mask=status != UNSUPPORTED, water_roi_mask=roi,
                        metadata_json=np.asarray(json.dumps(metadata, ensure_ascii=False)))
    valid = np.isfinite(dense_h)
    lo, hi = np.percentile(dense_h[valid], (2, 98))
    scaled = np.zeros_like(dense_h, dtype=np.uint8)
    scaled[valid] = np.clip((dense_h[valid] - lo) / max(hi - lo, 1e-12) * 255, 0, 255).astype(np.uint8)
    Image.fromarray(scaled, "L").save(output / f"{stem}.png")
    status_rgb = np.zeros((image_height, width, 3), dtype=np.uint8)
    status_rgb[status == OBSERVED] = (0, 180, 255)
    status_rgb[status == ESTIMATED] = (70, 210, 80)
    status_rgb[roi & (status == UNSUPPORTED)] = (220, 50, 50)
    Image.fromarray(status_rgb, "RGB").save(output / f"{stem}_status.png")
    roi_count = int(roi.sum())
    counts = {name: int(np.count_nonzero(status[roi] == code)) for name, code in
              (("observed", OBSERVED), ("estimated", ESTIMATED), ("unsupported", UNSUPPORTED))}
    qa = evaluate_holdout(support_xy, height, holdout_ratio=0.01, maximum_test_points=50,
                          seed=20260829, radius_multiplier=float(config["mls"]["radius_multiplier"]),
                          sigma_multiplier=float(config["mls"]["sigma_multiplier"]),
                          minimum_points=int(config["mls"]["minimum_points"]),
                          maximum_neighbors=int(config["mls"]["maximum_neighbors"]),
                          maximum_condition_number=float(config["mls"]["maximum_condition_number"]))
    target_names = {int(UNSUPPORTED): "UNSUPPORTED", int(OBSERVED): "OBSERVED", int(ESTIMATED): "ESTIMATED"}
    target = None
    if config.get("case2_check_canonical_px") is not None:
        target_u, target_v = (int(v) for v in config["case2_check_canonical_px"])
        target_flat = target_v * width + target_u
        target_code = status.ravel()[target_flat] if 0 <= target_u < width and 0 <= target_v < image_height else UNSUPPORTED
        target = {"canonical_px": [target_u, target_v], "status": target_names[int(target_code)],
                  "height_mm": float(dense_h.ravel()[target_flat]) if target_code != UNSUPPORTED else None,
                  "inside_water_roi": bool(roi.ravel()[target_flat])}
    elapsed = time.perf_counter() - started
    result = {"metadata": metadata, "resolution_px": [width, image_height], "water_roi_pixel_count": roi_count,
              "status": {key: {"count": count, "percent": 100 * count / roi_count} for key, count in counts.items()},
              "valid_height_mm": {"minimum": float(dense_h[valid].min()), "maximum": float(dense_h[valid].max()),
                                  "mean": float(dense_h[valid].mean()), "median": float(np.median(dense_h[valid]))},
              "generation_seconds": elapsed, "diagnostics": diagnostics,
              "unsupported_reasons": rejection_reasons,
              "unsupported_nearest_support_m": ({"minimum": min(rejection_nearest),
                                                   "median": float(np.median(rejection_nearest)),
                                                   "maximum": max(rejection_nearest)}
                                                  if rejection_nearest else None),
              "case2_manual_point_check": target,
              "small_holdout_qa": qa.to_dict(),
              "frozen_artifacts_unchanged": all(_sha256(Path(path)) == digest for path, digest in original_hashes.items())}
    (output / f"{stem}_result.yaml").write_text(yaml.safe_dump(result, sort_keys=False), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--config", required=True)
    args = parser.parse_args()
    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    result = build_dense_map(config)
    print(yaml.safe_dump(result, sort_keys=False)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
