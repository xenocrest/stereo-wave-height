"""Ocean-compatible WASS observation-to-completion boundary.

No tank depth, bottom texture, ruler, refraction or device-specific inputs.
Only confirmed same-frame water-surface observations may anchor completion.
"""
from dataclasses import dataclass
import numpy as np
from .dense_height_solver import DenseHeightPolicy, DenseHeightSolution, solve_dense_height


@dataclass(frozen=True)
class OceanSurfacePolicy:
    """Caller-declared coverage gate, not an empirically proven accuracy limit."""
    minimum_observed_ratio: float
    completion: DenseHeightPolicy = DenseHeightPolicy(anchor_mode="hard")

    def __post_init__(self):
        if not np.isfinite(self.minimum_observed_ratio) or not 0<self.minimum_observed_ratio<=1:
            raise ValueError("an explicit observed coverage ratio in (0,1] is required")
        if self.completion.anchor_mode!="hard":
            raise ValueError("ocean completion requires hard observation anchors")


def complete_water_surface(height_m, observed_mask, water_roi, common_fov, x_m, y_m,
                           *, observation_subject: str, policy: OceanSurfacePolicy) -> DenseHeightSolution:
    """Complete exactly water ROI intersect common FOV; never resize to fit ROI.

    x/y are calibrated metric water-plane coordinates for these exact pixels.
    Input heights already refer to one independent, common static reference.
    Surface identity is a required upstream assertion, NOT an automatic detector.
    Full finite coverage is a model output, not full observed coverage or accuracy.
    """
    if observation_subject!="WATER_SURFACE":
        raise ValueError("WATER_SURFACE_OBSERVATIONS_REQUIRED_NOT_BOTTOM_OR_UNKNOWN")
    arrays=[np.asarray(a) for a in (height_m,observed_mask,water_roi,common_fov,x_m,y_m)]
    if len({a.shape for a in arrays})!=1 or arrays[0].ndim!=2:
        raise ValueError("pixel-aligned fields must have the same 2D shape")
    h,obs,water,common,x,y=arrays
    domain=water.astype(bool)&common.astype(bool)
    if not domain.any():raise ValueError("EMPTY_COMMON_WATER_DOMAIN")
    anchors=obs.astype(bool)&domain&np.isfinite(h)
    ratio=float(anchors.sum()/domain.sum())
    if ratio<policy.minimum_observed_ratio:
        raise ValueError(f"RAW_WATER_SUPPORT_BELOW_GATE: {ratio:.6f} < {policy.minimum_observed_ratio:.6f}")
    result=solve_dense_height(h,anchors,domain,x,y,policy=policy.completion)
    result.metadata.update(observation_subject=observation_subject,minimum_observed_ratio=policy.minimum_observed_ratio,
                           filled_coverage_is_accuracy=False,trend_validation_status="NOT_EVALUATED",
                           requires_shared_independent_reference=True)
    return result
