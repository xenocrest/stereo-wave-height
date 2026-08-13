"""Validation metrics for post-WASS height products."""

from .metrics import HeightMetrics, calculate_height_metrics
from .constant_height import ConstantHeightResult, validate_constant_height_sequence
from .diagnostics import (
    PlaneFit,
    MeasurementDomainMasks,
    SpatialErrorStatistics,
    SupportStatistics,
    constant_truth_difference,
    fit_plane_orthogonal,
    height_observation_support_mask,
    measurement_domain_masks,
    raw_point_support,
    spatial_error_statistics,
    verify_grid_alignment,
    wass_zgap_percentile,
)
from .sinusoidal_wave import (
    SinusoidalWaveEstimate,
    estimate_sinusoidal_wave,
    translate_coordinate_origin_m,
    wrap_phase_rad,
)

__all__ = [
    "ConstantHeightResult",
    "HeightMetrics",
    "calculate_height_metrics",
    "validate_constant_height_sequence",
    "PlaneFit",
    "MeasurementDomainMasks",
    "SpatialErrorStatistics",
    "SupportStatistics",
    "constant_truth_difference",
    "fit_plane_orthogonal",
    "height_observation_support_mask",
    "measurement_domain_masks",
    "raw_point_support",
    "spatial_error_statistics",
    "verify_grid_alignment",
    "wass_zgap_percentile",
    "SinusoidalWaveEstimate",
    "estimate_sinusoidal_wave",
    "translate_coordinate_origin_m",
    "wrap_phase_rad",
]
