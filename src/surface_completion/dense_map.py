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
from .constrained_full_domain import (
    evaluate_physical_height_trend,
    fit_constrained_surface,
    fit_physical_height_trend,
)

OBSERVED, ESTIMATED, UNSUPPORTED, ESTIMATED_GLOBAL_MODEL = np.uint8(1), np.uint8(2), np.uint8(0), np.uint8(3)


def scale_dense_height_for_png(dense_h: np.ndarray) -> np.ndarray:
    """Render finite heights; all-unsupported is a valid black diagnostic image."""
    values = np.asarray(dense_h, dtype=np.float32)
    valid = np.isfinite(values)
    scaled = np.zeros_like(values, dtype=np.uint8)
    if np.any(valid):
        lo, hi = np.percentile(values[valid], (2, 98))
        scaled[valid] = np.clip(
            (values[valid] - lo) / max(hi - lo, 1e-12) * 255, 0, 255
        ).astype(np.uint8)
    return scaled


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


def estimate_global_ray_surface(
    rectified_pixels: np.ndarray,
    projection_metric: np.ndarray,
    normal: np.ndarray,
    offset: float,
    basis: np.ndarray,
    coefficients: np.ndarray,
    quadratic: bool,
) -> tuple[np.ndarray, np.ndarray]:
    """Evaluate a small-height surface on calibrated reference-plane rays.

    The fitted equation is ``signed_plane_distance = q(X_plane, Y_plane)``.
    Each ray is intersected with the base water plane and the height trend is
    evaluated at that physical footprint.  This is the standard first-order
    small-height approximation (surface displacement is small relative to
    camera distance). Returned values are estimates, never observations.
    """
    pixels = np.asarray(rectified_pixels, dtype=float)
    matrix, translation = projection_metric[:, :3], projection_metric[:, 3]
    center = -np.linalg.solve(matrix, translation)
    homogeneous = np.column_stack((pixels, np.ones(len(pixels))))
    directions = np.linalg.solve(matrix, homogeneous.T).T
    directions /= np.linalg.norm(directions, axis=1)[:, None]
    unit = np.asarray(normal, float) / np.linalg.norm(normal)
    denominator = directions @ unit
    valid = np.abs(denominator) > 1e-10
    plane_parameter = np.divide(
        -(float(center @ normal) + float(offset)), directions @ normal,
        out=np.zeros(len(directions)), where=valid,
    )
    points = center + plane_parameter[:, None] * directions
    values = evaluate_physical_height_trend(plane_xy(points, normal, basis), coefficients, quadratic)
    valid &= np.isfinite(values)
    return values, valid


def build_dense_map(config: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    ocean_mode=config.get("completion_strategy")=="ocean_observation_anchored"
    if ocean_mode and (config.get("water_roi") or {}).get("type")!="polygon":
        raise ValueError("EXPLICIT_WATER_ROI_REQUIRED: select water ROI before reconstruction; observed hull is not a measurement domain")
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
    requested_roi_pixels=int(roi.sum())
    if ocean_mode:
        with np.load(frozen["common_fov_npz"]) as common_data:
            common_mask=np.asarray(common_data["safe_common_mask"],bool)
        if common_mask.shape!=roi.shape:raise ValueError("COMMON_FOV_PIXEL_SHAPE_MISMATCH")
        roi = roi & common_mask
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
    global_mode = config.get("completion_strategy") == "global_physical_ray_surface"
    for flat_index, seed_index in (() if global_mode or ocean_mode else zip(missing_indices, missing_nearest)):
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
    if ocean_mode:
        from reconstruction.ocean_surface import OceanSurfacePolicy, complete_water_surface
        from reconstruction.dense_height_solver import DenseHeightPolicy
        policy_config=config["ocean_policy"]
        matrix,translation=projection[:,:3],projection[:,3]
        center=-np.linalg.solve(matrix,translation)
        rays=np.linalg.solve(matrix,np.column_stack((rectified,np.ones(len(rectified)))).T).T
        denominator=rays@normal
        with np.errstate(divide='ignore',invalid='ignore'):
            distance=-(center@normal+offset)/denominator
        points=center+distance[:,None]*rays
        points[~np.isfinite(distance)|(distance<=0)]=np.nan
        xy=plane_xy(points,normal,basis)
        solution=complete_water_surface(dense_h/1000,status==OBSERVED,roi,common_mask,
            xy[:,0].reshape(roi.shape),xy[:,1].reshape(roi.shape),
            observation_subject=config["observation_subject"],
            policy=OceanSurfacePolicy(float(policy_config["minimum_observed_ratio"]),
                DenseHeightPolicy(anchor_mode="hard",**policy_config.get("regularization",{}))))
        dense_h=solution.height_m.astype(np.float32)*1000
        status=solution.source_status
    elif global_mode:
        missing = roi & (status == UNSUPPORTED)
        missing_flat = np.flatnonzero(missing.ravel())
        if len(missing_flat):
            query_rectified = rectified[missing_flat]
            coefficients, quadratic = fit_physical_height_trend(support_xy, height)
            values, solved = estimate_global_ray_surface(
                query_rectified, projection, normal, offset, basis,
                coefficients, quadratic,
            )
            median = float(np.median(height)); scale = float(1.4826*np.median(np.abs(height-median)))
            p01,p99=np.percentile(height,(1,99)); margin=max(3.0*scale,float(p99-p01)*0.25,1e-6)
            values=np.clip(values,float(p01-margin),float(p99+margin))
            solved_flat = missing_flat[solved]
            dense_h.ravel()[solved_flat] = values[solved].astype(np.float32) * 1000.0
            status.ravel()[solved_flat] = ESTIMATED_GLOBAL_MODEL
    elif bool(config.get("demo_global_completion", False)):
        # Presentation-only last-resort fill.  Direct observations and local
        # estimates always retain priority and provenance.
        lo, hi = support_xy.min(axis=0), support_xy.max(axis=0)
        span = np.maximum(hi - lo, 1e-12)
        normalized = (support_xy - lo) / span
        global_result = fit_constrained_surface(normalized, height, output_shape=(image_height, width))
        missing = roi & (status == UNSUPPORTED)
        dense_h[missing] = global_result.height_m[missing] * 1000.0
        status[missing] = ESTIMATED_GLOBAL_MODEL
    output = Path(config["output_directory"]); output.mkdir(parents=True, exist_ok=True)
    stem = str(config.get("artifact_stem", "dense_height_case2"))
    metadata = {
        "classification": "DENSE_HEIGHT_MAP_MVP_COMPLETED", "source_frame": frozen["frame_identity"],
        "coordinate_system": coordinate_system, "output_pixel_system": "canonical_cam1",
        "reference_plane": plane, "observation_gate_px": direct_gate,
        "metric_scale_source": "frozen OpenCV calibrated baseline",
        "calibrated_baseline_m": float(frozen["calibrated_baseline_m"]),
        "p90_spacing_m": p90, "maximum_gap_m": max_gap,
        "completion_rule": ("hard-anchor metric graph variational completion; no independent accuracy established" if ocean_mode
                            else f"scene-local maximum gap = {float(config['completion']['maximum_gap_multiplier']):g} * frame P90 nearest-neighbor spacing"),
        "status_semantics": {"OBSERVED":"direct WASS observation","ESTIMATED":("observation-anchored variational estimate" if ocean_mode else "ESTIMATED_LOCAL within support gate"),"ESTIMATED_GLOBAL_MODEL":"demo-only bounded global model","UNSUPPORTED":"no result"},
        "extrapolation_policy":(
            "hard observed anchors; metric variational estimates within anchored common-water components; accuracy unverified"
            if ocean_mode else "bounded robust global trend; values outside direct support remain ESTIMATED_GLOBAL_MODEL"
            if global_mode else "reject outside scene-local support distance/topology gate"
        ),
        "water_roi": roi_config,
        "measurement_domain": ({
            "selection":"explicit canonical polygon fixed before reconstruction",
            "requested_roi_pixel_count":requested_roi_pixels,
            "excluded_non_common_pixel_count":requested_roi_pixels-int(roi.sum()),
            "evaluation_pixel_count":int(roi.sum()),
            "coverage_denominator":"explicit water ROI intersect calibration safe_common_mask",
            "shrunk_to_observation_support":False,
            "raw_observation_ratio":float(np.count_nonzero(status==OBSERVED)/roi.sum()),
            "finite_model_ratio":float(np.count_nonzero(roi&np.isfinite(dense_h))/roi.sum()),
        } if ocean_mode else None),
        "ocean_completion":solution.metadata if ocean_mode else None,
        "global_completion_geometry": (
            "calibrated camera ray to base-plane footprint, then robust height trend in metre-valued water-plane coordinates (first-order small-height model)"
            if global_mode else None
        ),
    }
    np.savez_compressed(output / f"{stem}.npz", height_mm=dense_h, status=status,
                        valid_mask=status != UNSUPPORTED, water_roi_mask=roi,
                        metadata_json=np.asarray(json.dumps(metadata, ensure_ascii=False)))
    valid = np.isfinite(dense_h)
    scaled = scale_dense_height_for_png(dense_h)
    Image.fromarray(scaled, "L").save(output / f"{stem}.png")
    status_rgb = np.zeros((image_height, width, 3), dtype=np.uint8)
    status_rgb[status == OBSERVED] = (0, 180, 255)
    status_rgb[status == ESTIMATED] = (70, 210, 80)
    status_rgb[status == ESTIMATED_GLOBAL_MODEL] = (80, 170, 220)
    status_rgb[roi & (status == UNSUPPORTED)] = (220, 50, 50)
    Image.fromarray(status_rgb, "RGB").save(output / f"{stem}_status.png")
    roi_count = int(roi.sum())
    counts = {name: int(np.count_nonzero(status[roi] == code)) for name, code in
              (("observed", OBSERVED), ("estimated", ESTIMATED), ("estimated_global_model", ESTIMATED_GLOBAL_MODEL), ("unsupported", UNSUPPORTED))}
    qa = evaluate_holdout(support_xy, height, holdout_ratio=0.01, maximum_test_points=50,
                          seed=20260829, radius_multiplier=float(config["mls"]["radius_multiplier"]),
                          sigma_multiplier=float(config["mls"]["sigma_multiplier"]),
                          minimum_points=int(config["mls"]["minimum_points"]),
                          maximum_neighbors=int(config["mls"]["maximum_neighbors"]),
                          maximum_condition_number=float(config["mls"]["maximum_condition_number"]))
    target_names = {int(UNSUPPORTED): "UNSUPPORTED", int(OBSERVED): "OBSERVED", int(ESTIMATED): "ESTIMATED_LOCAL", int(ESTIMATED_GLOBAL_MODEL): "ESTIMATED_GLOBAL_MODEL"}
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
              "valid_height_mm": ({"minimum": float(dense_h[valid].min()), "maximum": float(dense_h[valid].max()),
                                   "mean": float(dense_h[valid].mean()), "median": float(np.median(dense_h[valid]))}
                                  if np.any(valid) else None),
              "generation_seconds": elapsed, "diagnostics": diagnostics,
              "unsupported_reasons": rejection_reasons,
              "unsupported_nearest_support_m": ({"minimum": min(rejection_nearest),
                                                   "median": float(np.median(rejection_nearest)),
                                                   "maximum": max(rejection_nearest)}
                                                  if rejection_nearest else None),
              "case2_manual_point_check": target,
              "small_holdout_qa": ({"status":"NOT_EVALUATED_FOR_VARIATIONAL_MODEL"} if ocean_mode else qa.to_dict()),
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
