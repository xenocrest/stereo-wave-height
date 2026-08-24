"""Array-level diagnostics for static stereo frame consistency.

The functions are independent of camera brand and WASS configuration.  They
measure supplied image, mask, disparity and depth arrays without modifying or
repairing those arrays.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


@dataclass(frozen=True)
class DistributionSummary:
    """Finite scalar distribution summary in the caller's declared unit."""

    count: int
    minimum: float
    maximum: float
    mean: float
    median: float
    p5: float
    p95: float


@dataclass(frozen=True)
class DepthDriftSummary:
    """Signed and magnitude depth drift over an explicit common mask."""

    count: int
    mean: float
    rms: float
    p95_absolute: float


@dataclass(frozen=True)
class PlaneGeometry:
    """Normalized implicit plane corresponding to ``z = a*x + b*y + c``."""

    normal_xyz: tuple[float, float, float]
    offset: float
    tilt_deg: float


def _finite_values(values: np.ndarray, name: str) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if array.size == 0 or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be non-empty and finite")
    return array


def normalized_histogram(image: np.ndarray, *, bins: int = 16) -> np.ndarray:
    """Return a normalized grayscale histogram over the fixed range [0, 256)."""
    array = np.asarray(image)
    if array.ndim != 2 or array.size == 0:
        raise ValueError("image must be a non-empty two-dimensional grayscale array")
    if not np.issubdtype(array.dtype, np.number) or not np.all(np.isfinite(array)):
        raise ValueError("image values must be numeric and finite")
    if np.any(array < 0) or np.any(array > 255):
        raise ValueError("grayscale image values must be within [0, 255]")
    if not isinstance(bins, int) or bins <= 0:
        raise ValueError("bins must be a positive integer")
    counts, _ = np.histogram(array, bins=bins, range=(0.0, 256.0))
    return counts.astype(np.float64) / float(array.size)


def histogram_total_variation(first: np.ndarray, second: np.ndarray) -> float:
    """Return total-variation distance between two normalized histograms."""
    left = _finite_values(first, "first histogram")
    right = _finite_values(second, "second histogram")
    if left.shape != right.shape or left.ndim != 1:
        raise ValueError("histograms must be one-dimensional with identical shape")
    if np.any(left < 0) or np.any(right < 0):
        raise ValueError("histogram entries must be non-negative")
    if not np.isclose(left.sum(), 1.0) or not np.isclose(right.sum(), 1.0):
        raise ValueError("histograms must each sum to one")
    return float(0.5 * np.abs(left - right).sum())


def mask_overlap(first: np.ndarray, second: np.ndarray) -> float:
    """Return intersection-over-union for two explicit boolean support masks."""
    left = np.asarray(first)
    right = np.asarray(second)
    if left.dtype != np.bool_ or right.dtype != np.bool_:
        raise ValueError("support masks must have boolean dtype")
    if left.shape != right.shape or left.size == 0:
        raise ValueError("support masks must be non-empty and have identical shape")
    union = np.count_nonzero(left | right)
    if union == 0:
        raise ValueError("support-mask union is empty")
    return float(np.count_nonzero(left & right) / union)


def distribution_summary(values: np.ndarray) -> DistributionSummary:
    """Summarize a supplied disparity or other scalar distribution."""
    array = _finite_values(values, "values").ravel()
    return DistributionSummary(
        count=int(array.size),
        minimum=float(array.min()),
        maximum=float(array.max()),
        mean=float(array.mean()),
        median=float(np.median(array)),
        p5=float(np.percentile(array, 5.0)),
        p95=float(np.percentile(array, 95.0)),
    )


def depth_drift(
    current_depth: np.ndarray,
    reference_depth: np.ndarray,
    common_mask: np.ndarray,
) -> DepthDriftSummary:
    """Summarize ``current-reference`` only on a declared common valid domain."""
    current = np.asarray(current_depth, dtype=np.float64)
    reference = np.asarray(reference_depth, dtype=np.float64)
    mask = np.asarray(common_mask)
    if current.shape != reference.shape or current.shape != mask.shape or current.size == 0:
        raise ValueError("depth arrays and common mask must have the same non-empty shape")
    if mask.dtype != np.bool_:
        raise ValueError("common_mask must have boolean dtype")
    differences = current[mask] - reference[mask]
    differences = _finite_values(differences, "masked depth differences")
    return DepthDriftSummary(
        count=int(differences.size),
        mean=float(differences.mean()),
        rms=float(np.sqrt(np.mean(np.square(differences)))),
        p95_absolute=float(np.percentile(np.abs(differences), 95.0)),
    )


def plane_geometry(a: float, b: float, c: float) -> PlaneGeometry:
    """Convert ``z=a*x+b*y+c`` to a normalized implicit plane.

    The returned form is ``normal_xyz dot [x,y,z] + offset = 0`` and its
    normal is oriented toward positive z.
    """
    coefficients = _finite_values(np.asarray([a, b, c]), "plane coefficients")
    normal = np.asarray([-coefficients[0], -coefficients[1], 1.0])
    norm = float(np.linalg.norm(normal))
    normal /= norm
    offset = -float(coefficients[2]) / norm
    tilt = math.degrees(math.acos(float(np.clip(normal[2], -1.0, 1.0))))
    return PlaneGeometry(tuple(float(value) for value in normal), offset, tilt)
