"""Validate a future controlled WASS OLD/NEW calibration-only A/B plan."""
from __future__ import annotations
from typing import Any

LOCKED_FIELDS=("stereo_videos","target_time_s","selected_frames","sync_model","sync_residual_ms","rectification_policy","matcher_config","stereo_config","post_filter","water_roi")

def validate_ab_plan(plan: dict[str, Any]) -> None:
    if plan.get("gate_required") != "CALIBRATION_READY_FOR_WASS_AB": raise ValueError("calibration gate is required")
    if plan.get("max_new_wass_runs") != 1: raise ValueError("exactly one future NEW WASS run is permitted")
    old,new=plan["old"],plan["new"]
    for field in LOCKED_FIELDS:
        if old.get(field) != new.get(field): raise ValueError(f"A/B variable is not locked: {field}")
    if old.get("calibration") == new.get("calibration"): raise ValueError("calibration must be the sole changed input")
    if old.get("execution") != "FROZEN_EXISTING_RESULT" or new.get("execution") != "FUTURE_SINGLE_RUN": raise ValueError("invalid execution policy")
