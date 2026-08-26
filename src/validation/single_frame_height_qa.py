"""Read-only QA for frozen single-frame height and pixel–XYZ outputs.

This module characterizes reconstruction results only.  It does not load a
physical reference, modify heights, fill unsupported pixels, or filter points.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import numpy.typing as npt
from scipy import ndimage


PERCENTILES = (0.1, 1, 5, 25, 50, 75, 95, 99, 99.9)


@dataclass(frozen=True)
class AbnormalGrouping:
    component_count: int
    largest_component_pixels: int
    largest_component_fraction: float
    largest_component_bbox_xywh: tuple[int, int, int, int] | None
    singleton_component_count: int


@dataclass(frozen=True)
class HeightQualityAuditResult:
    status: str
    valid_point_count: int
    pixel_coordinate_system: str
    statistics: dict[str, object]
    tail_fractions: dict[str, dict[str, float | int]]
    support: dict[str, object]
    abnormal_grouping: AbnormalGrouping
    xyz: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        return data


def _finite_vector(values: npt.ArrayLike, name: str) -> npt.NDArray[np.float64]:
    vector = np.asarray(values, dtype=np.float64)
    if vector.ndim != 1 or vector.size == 0 or not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} must be a non-empty finite vector")
    return vector


def height_distribution_statistics(height_m: npt.ArrayLike) -> dict[str, object]:
    """Return raw and robust height statistics without clipping values."""
    height = _finite_vector(height_m, "height_m")
    q = np.percentile(height, PERCENTILES)
    percentiles = {f"p{value:g}_m": float(item) for value, item in zip(PERCENTILES, q, strict=True)}
    return {
        "unit": "m",
        "minimum_m": float(height.min()),
        "maximum_m": float(height.max()),
        "mean_m": float(height.mean()),
        "standard_deviation_m": float(height.std()),
        "rms_m": float(np.sqrt(np.mean(height**2))),
        "percentiles": percentiles,
        "iqr_m": float(percentiles["p75_m"] - percentiles["p25_m"]),
        "raw_height_range_mm": {"min": float(height.min() * 1000), "max": float(height.max() * 1000)},
        "robust_height_range_p1_p99_mm": {"low": float(percentiles["p1_m"] * 1000), "high": float(percentiles["p99_m"] * 1000)},
        "robust_height_range_p5_p95_mm": {"low": float(percentiles["p5_m"] * 1000), "high": float(percentiles["p95_m"] * 1000)},
    }


def tail_fraction_statistics(
    values_m: npt.ArrayLike, thresholds_mm: tuple[float, ...], *, center_m: float = 0.0
) -> dict[str, dict[str, float | int]]:
    """Count absolute deviations from an explicit center at each threshold."""
    values = _finite_vector(values_m, "values_m")
    if not np.isfinite(center_m) or any(value <= 0 for value in thresholds_mm):
        raise ValueError("center must be finite and thresholds positive")
    result: dict[str, dict[str, float | int]] = {}
    deviation = np.abs(values - center_m)
    for threshold in thresholds_mm:
        count = int(np.count_nonzero(deviation > threshold / 1000.0))
        result[f"gt_{threshold:g}_mm"] = {"count": count, "fraction": count / values.size, "percent": 100 * count / values.size}
    return result


def rasterize_sparse_support(
    u_px: npt.ArrayLike, v_px: npt.ArrayLike, image_shape: tuple[int, int]
) -> tuple[npt.NDArray[np.bool_], npt.NDArray[np.int64], npt.NDArray[np.int64]]:
    """Rasterize observed projected pixels only; unsupported pixels remain false."""
    u = _finite_vector(u_px, "u_px")
    v = _finite_vector(v_px, "v_px")
    if u.shape != v.shape or len(image_shape) != 2 or min(image_shape) <= 0:
        raise ValueError("pixel arrays must align and image_shape must be positive")
    x, y = np.rint(u).astype(np.int64), np.rint(v).astype(np.int64)
    if np.any(x < 0) or np.any(x >= image_shape[1]) or np.any(y < 0) or np.any(y >= image_shape[0]):
        raise ValueError("projected pixel lies outside declared computational image")
    support = np.zeros(image_shape, dtype=bool)
    support[y, x] = True
    return support, x, y


def sparse_height_raster(
    u_px: npt.ArrayLike, v_px: npt.ArrayLike, height_m: npt.ArrayLike, image_shape: tuple[int, int]
) -> npt.NDArray[np.float64]:
    """Create a display raster while preserving unsupported pixels as NaN.

    Multiple 3D samples may project to one pixel. Their median is used only for
    this QA visualization; pointwise statistics retain every original sample.
    """
    height = _finite_vector(height_m, "height_m")
    support, x, y = rasterize_sparse_support(u_px, v_px, image_shape)
    if height.size != x.size:
        raise ValueError("height and pixel arrays must align")
    raster = np.full(image_shape, np.nan, dtype=np.float64)
    order = np.lexsort((x, y))
    keys = np.column_stack((y[order], x[order]))
    starts = np.r_[0, np.flatnonzero(np.any(np.diff(keys, axis=0), axis=1)) + 1]
    ends = np.r_[starts[1:], keys.shape[0]]
    for start, end in zip(starts, ends, strict=True):
        yy, xx = keys[start]
        raster[yy, xx] = float(np.median(height[order[start:end]]))
    assert np.array_equal(np.isfinite(raster), support)
    return raster


def support_edge_distances(
    support: npt.NDArray[np.bool_], x: npt.NDArray[np.int64], y: npt.NDArray[np.int64]
) -> npt.NDArray[np.float64]:
    """Distance of each observed sample to the nearest unsupported pixel."""
    if support.ndim != 2 or x.shape != y.shape:
        raise ValueError("support must be 2D and pixel indices aligned")
    distance = ndimage.distance_transform_edt(support)
    return distance[y, x].astype(np.float64)


def abnormal_connected_components(
    x: npt.NDArray[np.int64], y: npt.NDArray[np.int64], abnormal: npt.ArrayLike,
    image_shape: tuple[int, int],
) -> AbnormalGrouping:
    """Group abnormal observed pixels by 8-connected pixel adjacency."""
    flag = np.asarray(abnormal, dtype=bool)
    if flag.shape != x.shape:
        raise ValueError("abnormal mask must align with pixel samples")
    raster = np.zeros(image_shape, dtype=np.uint8)
    raster[y[flag], x[flag]] = 1
    labels, count = ndimage.label(raster, structure=np.ones((3, 3), dtype=np.uint8))
    if count == 0:
        return AbnormalGrouping(0, 0, 0.0, None, 0)
    sizes = np.bincount(labels.ravel())[1:]
    largest_index = int(np.argmax(sizes))
    boxes = ndimage.find_objects(labels)
    row_slice, column_slice = boxes[largest_index]
    bbox = (
        int(column_slice.start), int(row_slice.start),
        int(column_slice.stop - column_slice.start), int(row_slice.stop - row_slice.start),
    )
    return AbnormalGrouping(
        int(count), int(sizes.max()), float(sizes.max() / sizes.sum()), bbox,
        int(np.count_nonzero(sizes == 1)),
    )


def audit_single_frame_height(
    *,
    xyz_m: npt.ArrayLike,
    u_px: npt.ArrayLike,
    v_px: npt.ArrayLike,
    height_m: npt.ArrayLike,
    pixel_coordinate_system: str,
    image_shape: tuple[int, int],
    condition: str,
) -> HeightQualityAuditResult:
    """Characterize a frozen static or wave pointwise height result."""
    xyz = np.asarray(xyz_m, dtype=np.float64)
    height = _finite_vector(height_m, "height_m")
    if xyz.shape != (height.size, 3) or not np.all(np.isfinite(xyz)):
        raise ValueError("xyz_m must be finite N×3 and align with height")
    if not pixel_coordinate_system.startswith("wass_rectified_computational_"):
        raise ValueError("pixel coordinate convention must be explicit and computational-rectified")
    support, x, y = rasterize_sparse_support(u_px, v_px, image_shape)
    edge = support_edge_distances(support, x, y)
    center = 0.0 if condition == "static" else float(np.median(height))
    thresholds = (5, 10, 20, 30, 40, 50) if condition == "static" else (5, 10, 20, 30, 50)
    tail = tail_fraction_statistics(height, thresholds, center_m=center)
    abnormal = np.abs(height - center) > 0.010
    normal_edge = edge[~abnormal]
    abnormal_edge = edge[abnormal]
    edge_summary = {
        "definition": "distance transform on observed-pixel raster; no support filling",
        "all_median_px": float(np.median(edge)),
        "normal_median_px": float(np.median(normal_edge)) if normal_edge.size else None,
        "abnormal_median_px": float(np.median(abnormal_edge)) if abnormal_edge.size else None,
        "abnormal_p25_px": float(np.percentile(abnormal_edge, 25)) if abnormal_edge.size else None,
        "abnormal_p75_px": float(np.percentile(abnormal_edge, 75)) if abnormal_edge.size else None,
    }
    grouping = abnormal_connected_components(x, y, abnormal, image_shape)
    p1, p99 = np.percentile(height, (1, 99))
    low_grouping = abnormal_connected_components(x, y, height < p1, image_shape)
    high_grouping = abnormal_connected_components(x, y, height > p99, image_shape)
    support_bbox = [int(x.min()), int(y.min()), int(x.max() - x.min() + 1), int(y.max() - y.min() + 1)]
    ranges = {
        axis: [float(xyz[:, index].min()), float(xyz[:, index].max())]
        for index, axis in enumerate(("x", "y", "z"))
    }
    abnormal_ranges = {
        axis: ([float(xyz[abnormal, index].min()), float(xyz[abnormal, index].max())] if np.any(abnormal) else None)
        for index, axis in enumerate(("x", "y", "z"))
    }
    return HeightQualityAuditResult(
        "HEIGHT_DISTRIBUTION_CHARACTERIZED", int(height.size), pixel_coordinate_system,
        height_distribution_statistics(height), tail,
        {
            "image_shape": list(image_shape), "unique_observed_pixels": int(np.count_nonzero(support)),
            "support_bbox_xywh": support_bbox, "unsupported_pixels_are_nan": True,
            "edge_distance": edge_summary,
            "p1_below_grouping": asdict(low_grouping),
            "p99_above_grouping": asdict(high_grouping),
        }, grouping, {"all_range_m": ranges, "abnormal_gt_10mm_range_m": abnormal_ranges},
    )
