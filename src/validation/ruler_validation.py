"""Independent ruler-based checks for metric stereo reconstruction.

The functions consume explicit physical references and reconstructed points.
They never alter calibration, WASS output, or scale data to match the ruler.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np


class DriftClassification(str, Enum):
    """Evidence-based source classification for reconstruction drift."""

    GLOBAL_RECONSTRUCTION_DRIFT = "GLOBAL_RECONSTRUCTION_DRIFT"
    SURFACE_MATCHING_INSTABILITY = "SURFACE_MATCHING_INSTABILITY"
    GEOMETRIC_SCALE_ERROR = "GEOMETRIC_SCALE_ERROR"
    INCOMPLETE_REFERENCE = "RULER_VALIDATION_INCOMPLETE_MANUAL_REFERENCE_REQUIRED"


@dataclass(frozen=True)
class ScaleValidation:
    """Comparison between a declared ruler interval and its 3-D reconstruction."""

    real_length_m: float
    reconstructed_length_m: float
    relative_error: float


@dataclass(frozen=True)
class HeightValidation:
    """Physical ruler height versus signed reconstructed plane-normal height."""

    ruler_height_m: float
    reconstructed_height_m: float
    signed_error_m: float


@dataclass(frozen=True)
class ValidationErrorMetrics:
    """Independent reconstructed-versus-physical reference errors in metres."""

    count: int
    rmse_m: float
    mae_m: float
    maximum_absolute_error_m: float


def _finite_vector(value: np.ndarray, name: str) -> np.ndarray:
    vector = np.asarray(value, dtype=np.float64)
    if vector.shape != (3,) or not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} must be a finite 3-vector in metres")
    return vector


def validate_ruler_scale(
    endpoint_a_m: np.ndarray,
    endpoint_b_m: np.ndarray,
    real_length_m: float,
) -> ScaleValidation:
    """Compare Euclidean 3-D endpoint distance with an explicit real interval."""
    first = _finite_vector(endpoint_a_m, "endpoint_a_m")
    second = _finite_vector(endpoint_b_m, "endpoint_b_m")
    if not np.isfinite(real_length_m) or real_length_m <= 0:
        raise ValueError("real_length_m must be explicitly known and positive")
    reconstructed = float(np.linalg.norm(second - first))
    if reconstructed == 0:
        raise ValueError("reconstructed ruler endpoints must be distinct")
    return ScaleValidation(
        real_length_m=float(real_length_m),
        reconstructed_length_m=reconstructed,
        relative_error=float((reconstructed - real_length_m) / real_length_m),
    )


def signed_plane_height(
    point_m: np.ndarray,
    reference_point_m: np.ndarray,
    plane_normal: np.ndarray,
) -> float:
    """Return signed metric height along an explicit plane normal.

    This implements ``h = n dot (P-P0) / ||n||`` and deliberately does not use
    camera Z as water height.
    """
    point = _finite_vector(point_m, "point_m")
    reference = _finite_vector(reference_point_m, "reference_point_m")
    normal = _finite_vector(plane_normal, "plane_normal")
    norm = float(np.linalg.norm(normal))
    if norm == 0:
        raise ValueError("plane_normal must be non-zero")
    return float(np.dot(normal, point - reference) / norm)


def validate_water_height(ruler_height_m: float, reconstructed_height_m: float) -> HeightValidation:
    """Compare two independently supplied signed heights in metres."""
    if not np.isfinite(ruler_height_m) or not np.isfinite(reconstructed_height_m):
        raise ValueError("both heights must be finite metric values")
    return HeightValidation(
        ruler_height_m=float(ruler_height_m),
        reconstructed_height_m=float(reconstructed_height_m),
        signed_error_m=float(reconstructed_height_m - ruler_height_m),
    )


def validation_error_metrics(reconstructed_height_m: np.ndarray, real_height_m: np.ndarray) -> ValidationErrorMetrics:
    """Evaluate algorithm output against separately supplied manual truth."""
    reconstructed = np.asarray(reconstructed_height_m, dtype=np.float64)
    real = np.asarray(real_height_m, dtype=np.float64)
    if reconstructed.ndim != 1 or reconstructed.shape != real.shape or reconstructed.size == 0:
        raise ValueError("reconstructed and real height arrays must have equal non-empty shape")
    if not np.all(np.isfinite(reconstructed)) or not np.all(np.isfinite(real)):
        raise ValueError("height arrays must be finite")
    error = reconstructed - real
    return ValidationErrorMetrics(
        count=int(error.size),
        rmse_m=float(np.sqrt(np.mean(error**2))),
        mae_m=float(np.mean(np.abs(error))),
        maximum_absolute_error_m=float(np.max(np.abs(error))),
    )


def classify_drift_source(
    *,
    reference_complete: bool,
    ruler_position_drift_m: float | None,
    ruler_relative_length_change: float | None,
    surface_anomaly_m: float | None,
    position_threshold_m: float,
    scale_threshold: float,
    surface_threshold_m: float,
) -> DriftClassification:
    """Classify drift using caller-declared, pre-established thresholds."""
    thresholds = (position_threshold_m, scale_threshold, surface_threshold_m)
    if any(not np.isfinite(value) or value < 0 for value in thresholds):
        raise ValueError("classification thresholds must be finite and non-negative")
    if not reference_complete:
        return DriftClassification.INCOMPLETE_REFERENCE
    measurements = (ruler_position_drift_m, ruler_relative_length_change, surface_anomaly_m)
    if any(value is None or not np.isfinite(value) or value < 0 for value in measurements):
        raise ValueError("complete reference classification requires non-negative measurements")
    assert ruler_position_drift_m is not None
    assert ruler_relative_length_change is not None
    assert surface_anomaly_m is not None
    if ruler_relative_length_change > scale_threshold:
        return DriftClassification.GEOMETRIC_SCALE_ERROR
    if ruler_position_drift_m > position_threshold_m:
        return DriftClassification.GLOBAL_RECONSTRUCTION_DRIFT
    if surface_anomaly_m > surface_threshold_m:
        return DriftClassification.SURFACE_MATCHING_INSTABILITY
    raise ValueError("measurements do not establish one of the defined failure classes")
