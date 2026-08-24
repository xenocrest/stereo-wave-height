"""First-order depth resolution from rectified-disparity uncertainty."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class DepthResolutionResult:
    """Magnitude of first-order depth uncertainty in SI and millimetres."""

    depth_sensitivity_m_per_px: float
    disparity_uncertainty_px: float
    depth_error_m: float
    depth_error_mm: float


def _positive_finite(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be finite and greater than zero")
    return value


def depth_resolution(
    baseline_m: float,
    focal_length_px: float,
    distance_m: float,
    disparity_uncertainty_px: float,
) -> DepthResolutionResult:
    """Return ``|Delta Z| = Z^2 |Delta d| / (f B)``.

    The relation is a local first-order error propagation model.  It is not a
    measured accuracy claim and excludes calibration, synchronization,
    matching outliers, optical distortion and surface effects.
    """
    baseline = _positive_finite("baseline_m", baseline_m)
    focal = _positive_finite("focal_length_px", focal_length_px)
    distance = _positive_finite("distance_m", distance_m)
    uncertainty = float(disparity_uncertainty_px)
    if not math.isfinite(uncertainty) or uncertainty < 0.0:
        raise ValueError("disparity_uncertainty_px must be finite and non-negative")
    sensitivity = distance**2 / (focal * baseline)
    error_m = sensitivity * uncertainty
    return DepthResolutionResult(
        depth_sensitivity_m_per_px=sensitivity,
        disparity_uncertainty_px=uncertainty,
        depth_error_m=error_m,
        depth_error_mm=error_m * 1000.0,
    )
