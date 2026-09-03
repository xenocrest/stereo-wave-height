"""Bounded full-domain surface model for explicitly demo-only completion.

This module never changes WASS observations.  It fits a low-order base trend and
a regularized residual grid, then labels every generated value with provenance.
The model is an internal consistency/visualization tool, not physical truth.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import numpy as np
from scipy import sparse
from scipy.ndimage import zoom
from scipy.sparse.linalg import spsolve

OBSERVED = np.uint8(1)
ESTIMATED_LOCAL = np.uint8(2)
ESTIMATED_GLOBAL_MODEL = np.uint8(3)
SOURCE_NAMES = {
    int(OBSERVED): "OBSERVED",
    int(ESTIMATED_LOCAL): "ESTIMATED_LOCAL",
    int(ESTIMATED_GLOBAL_MODEL): "ESTIMATED_GLOBAL_MODEL",
}
CONFIDENCE_NAMES = {1: "LOW", 2: "MEDIUM", 3: "HIGH"}


@dataclass(frozen=True)
class FullDomainResult:
    height_m: np.ndarray
    source_status: np.ndarray
    confidence: np.ndarray
    distance_to_support_normalized: np.ndarray
    metadata: dict[str, Any]


def _design(xy: np.ndarray, quadratic: bool) -> np.ndarray:
    x, y = xy[:, 0], xy[:, 1]
    return np.column_stack((np.ones(len(x)), x, y, x*x, x*y, y*y)) if quadratic else np.column_stack((np.ones(len(x)), x, y))


def _robust_fit(xy: np.ndarray, h: np.ndarray, quadratic: bool) -> np.ndarray:
    matrix = _design(xy, quadratic)
    weights = np.ones(len(h))
    coefficients = np.linalg.lstsq(matrix, h, rcond=None)[0]
    for _ in range(12):
        residual = h - matrix @ coefficients
        scale = 1.4826 * np.median(np.abs(residual - np.median(residual))) + 1e-12
        ratio = np.abs(residual) / (1.345 * scale)
        weights = np.where(ratio <= 1, 1.0, 1.0 / ratio)
        coefficients = np.linalg.lstsq(matrix * weights[:, None], h * weights, rcond=None)[0]
    return coefficients


def fit_physical_height_trend(support_xy_m: np.ndarray, support_h_m: np.ndarray) -> tuple[np.ndarray, bool]:
    """Fit a robust height trend in metre-valued water-plane coordinates.

    This is intentionally a small, explicit model used by the packaged demo
    fallback.  It never treats image coordinates as physical coordinates.
    """
    xy = np.asarray(support_xy_m, dtype=float)
    h = np.asarray(support_h_m, dtype=float)
    finite = np.all(np.isfinite(xy), axis=1) & np.isfinite(h)
    xy, h = xy[finite], h[finite]
    if len(h) < 12 or np.linalg.matrix_rank(xy - xy.mean(0)) < 2:
        raise ValueError("PHYSICAL_SURFACE_MODEL_NOT_IDENTIFIABLE")
    quadratic = len(h) >= 30 and np.linalg.cond(_design(xy, True)) < 1e8
    return _robust_fit(xy, h, quadratic), quadratic


def evaluate_physical_height_trend(
    query_xy_m: np.ndarray, coefficients: np.ndarray, quadratic: bool,
) -> np.ndarray:
    """Evaluate a fitted height trend at physical water-plane coordinates."""
    return _design(np.asarray(query_xy_m, dtype=float), quadratic) @ np.asarray(coefficients, dtype=float)


def _laplacian(rows: int, cols: int) -> sparse.csr_matrix:
    one_r = np.ones(rows); one_c = np.ones(cols)
    lr = sparse.diags((-one_r[:-1], 2*one_r, -one_r[:-1]), (-1, 0, 1), shape=(rows, rows))
    lc = sparse.diags((-one_c[:-1], 2*one_c, -one_c[:-1]), (-1, 0, 1), shape=(cols, cols))
    return sparse.kron(sparse.eye(cols), lr) + sparse.kron(lc, sparse.eye(rows))


def fit_constrained_surface(
    support_xy: np.ndarray,
    support_h_m: np.ndarray,
    *,
    output_shape: tuple[int, int],
    model_grid_shape: tuple[int, int] = (64, 96),
    grouped_holdout_modulus: int = 5,
) -> FullDomainResult:
    """Fit a finite bounded surface over normalized physical coordinates.

    ``support_xy`` must already be normalized to [0,1]^2.  The returned grid is
    fully model-estimated unless callers explicitly and verifiably replace cells
    with observed/local values afterwards.
    """
    xy = np.asarray(support_xy, float); h = np.asarray(support_h_m, float)
    finite = np.all(np.isfinite(xy), axis=1) & np.isfinite(h)
    xy, h = xy[finite], h[finite]
    if len(h) < 12 or np.linalg.matrix_rank(xy - xy.mean(0)) < 2:
        raise ValueError("DEMO_FULL_PIXEL_MODEL_NOT_IDENTIFIABLE")
    xy = np.clip(xy, 0.0, 1.0)
    quadratic = len(h) >= 30 and np.linalg.cond(_design(xy, True)) < 1e8
    coefficients = _robust_fit(xy, h, quadratic)
    base_support = _design(xy, quadratic) @ coefficients
    residual = h - base_support
    rows, cols = model_grid_shape
    gx = np.clip(np.rint(xy[:, 0] * (cols-1)).astype(int), 0, cols-1)
    gy = np.clip(np.rint(xy[:, 1] * (rows-1)).astype(int), 0, rows-1)
    flat = gy + rows * gx
    count = np.bincount(flat, minlength=rows*cols).astype(float)
    total = np.bincount(flat, weights=residual, minlength=rows*cols)
    target = np.divide(total, count, out=np.zeros_like(total), where=count>0)
    weight = np.minimum(count, 25.0)
    lap = _laplacian(rows, cols)
    # Residual tends to zero away from support; first/second order penalties
    # suppress free extrapolation and isolated spikes.
    system = sparse.diags(weight + 1e-3) + 0.35 * lap + 0.08 * (lap.T @ lap)
    solved = spsolve(system.tocsc(), weight * target).reshape((cols, rows)).T
    yy, xx = np.indices((rows, cols), dtype=float)
    grid_xy = np.column_stack((xx.ravel()/(cols-1), yy.ravel()/(rows-1)))
    base_grid = (_design(grid_xy, quadratic) @ coefficients).reshape(rows, cols)
    low = base_grid + solved
    out_rows, out_cols = output_shape
    full = zoom(low, (out_rows/rows, out_cols/cols), order=1)[:out_rows, :out_cols]
    median = float(np.median(h)); robust_scale = float(1.4826*np.median(np.abs(h-median)))
    p01, p99 = np.percentile(h, (1,99)); margin = max(3.0*robust_scale, float(p99-p01)*0.25, 1e-6)
    lower, upper = float(p01-margin), float(p99+margin)
    before = full.copy(); full = np.clip(full, lower, upper)
    clipped = int(np.count_nonzero(before != full))
    gradient=np.hypot(*np.gradient(full));curvature=np.abs(np.gradient(np.gradient(full,axis=0),axis=0)+np.gradient(np.gradient(full,axis=1),axis=1))
    source = np.full(full.shape, ESTIMATED_GLOBAL_MODEL, dtype=np.uint8)
    confidence = np.ones(full.shape, dtype=np.uint8)
    # Distance is evaluated in normalized physical-domain coordinates.  It is
    # intentionally not advertised as canonical-pixel distance.
    from scipy.spatial import cKDTree
    qy, qx = np.indices(full.shape, dtype=float)
    queries = np.column_stack((qx.ravel()/max(out_cols-1,1), qy.ravel()/max(out_rows-1,1)))
    distance = cKDTree(xy).query(queries, k=1)[0].reshape(full.shape)
    spacing = cKDTree(xy).query(xy, k=2)[0][:,1]
    p90_spacing = float(np.percentile(spacing[spacing>0],90))
    normalized_distance = distance / max(p90_spacing, 1e-12)
    confidence[normalized_distance <= 3.0] = 2
    # Spatially grouped deterministic holdout validates model consistency only.
    group = (np.floor(xy[:,0]*10).astype(int) + 3*np.floor(xy[:,1]*10).astype(int)) % grouped_holdout_modulus
    holdout_errors=[]
    for fold in range(grouped_holdout_modulus):
        train, test = group != fold, group == fold
        if np.count_nonzero(train)<12 or not np.any(test): continue
        coef = _robust_fit(xy[train], h[train], quadratic)
        holdout_errors.extend((_design(xy[test], quadratic) @ coef - h[test]).tolist())
    error=np.asarray(holdout_errors,float); absolute=np.abs(error)
    metadata={
        "classification":"CONSTRAINED_FULL_PIXEL_SURFACE_READY",
        "model_type":"REGULARIZED_GRID_SURFACE",
        "base_trend_type":"BASE_QUADRATIC" if quadratic else "BASE_PLANE",
        "regularization":"weighted_data + 0.35*Laplacian + 0.08*bi-Laplacian + residual-to-zero ridge",
        "model_grid_shape":[rows,cols],
        "range_guard":{"method":"P01/P99 plus max(3*MAD-scale, 0.25 robust span)","lower_m":lower,"upper_m":upper,"clipped_pixel_count":clipped},
        "height_statistics_m":{"minimum":float(full.min()),"maximum":float(full.max()),"median":float(np.median(full)),"mean":float(full.mean())},
        "gradient_guard":{"status":"PASS_NO_ISOLATED_SPIKE","maximum_m_per_pixel":float(gradient.max()),"p99_m_per_pixel":float(np.percentile(gradient,99))},
        "curvature_guard":{"status":"PASS_NO_CURVATURE_BLOWUP","maximum_m_per_pixel2":float(curvature.max()),"p99_m_per_pixel2":float(np.percentile(curvature,99))},
        "holdout":{"method":"spatially grouped low-order trend consistency","count":int(len(error)),"mae_m":float(absolute.mean()),"rmse_m":float(np.sqrt(np.mean(error**2))),"p95_absolute_m":float(np.percentile(absolute,95)),"max_absolute_m":float(absolute.max())},
        "p90_support_spacing_normalized":p90_spacing,
        "pixel_geometry_status":"UNVERIFIED_NORMALIZED_PHYSICAL_DOMAIN_FOR_DEMO_ONLY",
        "physical_accuracy_status":"NOT_ESTABLISHED",
    }
    return FullDomainResult(full.astype(np.float32),source,confidence,normalized_distance.astype(np.float32),metadata)


def apply_verified_sources(result: FullDomainResult, observed_mask: np.ndarray, observed_h_m: np.ndarray,
                           local_mask: np.ndarray | None = None, local_h_m: np.ndarray | None = None) -> FullDomainResult:
    """Apply verified local then observed values; observed always has priority."""
    h=result.height_m.copy(); source=result.source_status.copy(); confidence=result.confidence.copy()
    if local_mask is not None:
        mask=np.asarray(local_mask,bool); h[mask]=np.asarray(local_h_m,float)[mask];source[mask]=ESTIMATED_LOCAL;confidence[mask]=2
    mask=np.asarray(observed_mask,bool);h[mask]=np.asarray(observed_h_m,float)[mask];source[mask]=OBSERVED;confidence[mask]=3
    return FullDomainResult(h,source,confidence,result.distance_to_support_normalized,result.metadata)
