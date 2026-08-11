"""Validation metrics for post-WASS height products."""

from .metrics import HeightMetrics, calculate_height_metrics
from .constant_height import ConstantHeightResult, validate_constant_height_sequence
from .diagnostics import (
    PlaneFit,
    SpatialErrorStatistics,
    SupportStatistics,
    constant_truth_difference,
    fit_plane_orthogonal,
    height_observation_support_mask,
    raw_point_support,
    spatial_error_statistics,
    verify_grid_alignment,
)

__all__ = [
    "ConstantHeightResult",
    "HeightMetrics",
    "calculate_height_metrics",
    "validate_constant_height_sequence",
    "PlaneFit",
    "SpatialErrorStatistics",
    "SupportStatistics",
    "constant_truth_difference",
    "fit_plane_orthogonal",
    "height_observation_support_mask",
    "raw_point_support",
    "spatial_error_statistics",
    "verify_grid_alignment",
]
