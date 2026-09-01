"""Auditable, deterministic adaptation decisions without hidden tuning."""
from __future__ import annotations
from typing import Any
import math

def geometry_disparity_expectation(*,focal_px:float,baseline_m:float,depth_min_m:float|None,depth_max_m:float|None)->dict[str,Any]:
    if not math.isfinite(focal_px) or not math.isfinite(baseline_m) or focal_px<=0 or baseline_m<=0:raise ValueError("positive finite focal and baseline required")
    if depth_min_m is None or depth_max_m is None:return {"status":"DEPTH_PRIOR_UNAVAILABLE","minimum_disparity_px":None,"maximum_disparity_px":None,"source":"explicit_geometry_without_depth_prior"}
    if not 0<depth_min_m<=depth_max_m:raise ValueError("depth range must satisfy 0 < min <= max")
    return {"status":"GEOMETRY_INFORMED","minimum_disparity_px":focal_px*baseline_m/depth_max_m,"maximum_disparity_px":focal_px*baseline_m/depth_min_m,"source":"d=fB/Z"}

def choose_adaptation(scene:dict[str,Any],*,disparity:dict[str,Any]|None=None)->dict[str,Any]:
    reasons=list(scene.get("quality_reasons",[]));profile="CURRENT_FROZEN_MATCHER";photometric="NONE"
    if "PHOTOMETRIC_RISK" in reasons:profile="HIGH_PHOTOMETRIC_MISMATCH_EXPERIMENTAL";photometric="CLAHE_OR_MEAN_STD_AB_REQUIRED"
    elif "TEXTURE_LIMITED" in reasons:profile="LOW_TEXTURE_EXPERIMENTAL"
    elif "SPECULAR_OR_CLIPPING_RISK" in reasons:profile="HIGH_GLARE_EXPERIMENTAL"
    return {"schema_version":"1.0","scene_diagnostics":scene,"selected_calibration_model":"SPLIT_MONO_FIXED_INTRINSIC_STEREO_WHEN_AVAILABLE",
            "selected_sync_policy":"NORMALIZED_RESIDUAL_WITH_EXISTING_EXACT_WARNING_REJECT","selected_matcher_profile":profile,
            "matcher_profile_status":"EXPERIMENTAL_NOT_PROMOTED" if profile!="CURRENT_FROZEN_MATCHER" else "READY_TO_INTEGRATE",
            "photometric_preprocessing":photometric,"photometric_preprocessing_applied":False,
            "disparity_range":disparity or {"status":"UNCHANGED_CURRENT_CONFIG"},"component_filtering_strategy":"LARGEST_COMPONENT_CURRENT_DEFAULT__MULTI_COMPONENT_DIAGNOSTIC_ONLY",
            "completion_strategy":"LOCAL_SUPPORT_GATED_3XP90_DEFAULT_VALIDATED_PER_SCENE","warnings":reasons}
