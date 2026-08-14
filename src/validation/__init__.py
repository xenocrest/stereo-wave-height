"""Validation metrics for post-WASS height products."""

from .metrics import HeightMetrics, calculate_height_metrics
from .constant_height import ConstantHeightResult, validate_constant_height_sequence
from .diagnostics import (
    PlaneFit,
    MeasurementDomainMasks,
    SpatialErrorStatistics,
    SupportStatistics,
    constant_truth_difference,
    absolute_error_percentiles,
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
from .irregular_wave import (
    RepresentativeGridPoint,
    direct_error_metrics,
    freeze_nearest_grid_points,
    uniformly_spaced_frame_ids,
)
from .scene_distance import SceneDistanceTheory, min_mean_max, scene_distance_theory
from .virtual_stereo_geometry import (
    ClosureMetrics,
    closure_metrics,
    theoretical_pinhole_projection,
    triangulate_parallel_downward_stereo,
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
    "absolute_error_percentiles",
    "fit_plane_orthogonal",
    "height_observation_support_mask",
    "measurement_domain_masks",
    "raw_point_support",
    "spatial_error_statistics",
    "verify_grid_alignment",
    "wass_zgap_percentile",
    "SinusoidalWaveEstimate",
    "estimate_sinusoidal_wave",
    "RepresentativeGridPoint",
    "direct_error_metrics",
    "freeze_nearest_grid_points",
    "uniformly_spaced_frame_ids",
    "SceneDistanceTheory",
    "min_mean_max",
    "scene_distance_theory",
    "translate_coordinate_origin_m",
    "wrap_phase_rad",
    "ClosureMetrics",
    "closure_metrics",
    "theoretical_pinhole_projection",
    "triangulate_parallel_downward_stereo",
]
