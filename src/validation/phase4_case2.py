"""Guards for freezing the user-selected Phase 4 Case 2 reconstruction.

The helpers validate identity and provenance only.  They do not invoke WASS,
read ruler values, select candidates, or alter reconstruction arrays.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping


CASE2_CANDIDATE_ID = "candidate_02"
CASE2_RIGHT_FRAME_ID = "pts_2646070"
CASE2_LEFT_FRAME_ID = "pts_2651866"


def file_sha256(path: str | Path) -> str:
    """Return an uppercase SHA-256 digest for a frozen artifact."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


def require_candidate_02_identity(
    candidate: Mapping[str, Any], pair: Mapping[str, Any]
) -> None:
    """Reject any reconstruction pair that is not the selected candidate_02."""
    expected = {
        "id": CASE2_CANDIDATE_ID,
        "requested_left_time_s": 29.4654055,
        "actual_cam1_pts": 2646070,
        "actual_cam1_time_s": 29.400778,
        "cam1_frame_identity": CASE2_RIGHT_FRAME_ID,
        "sync_status": "SYNC_ACCEPTED_FOR_ON_DEMAND_MEASUREMENT",
    }
    for key, value in expected.items():
        if candidate.get(key) != value:
            raise ValueError(f"CASE2_CANDIDATE_IDENTITY_MISMATCH: {key}")
    if candidate.get("canonical_rotation_deg") != 0:
        raise ValueError("CASE2_CANDIDATE_IDENTITY_MISMATCH: canonical orientation")
    if pair.get("left_frame_id") != CASE2_LEFT_FRAME_ID or pair.get("right_frame_id") != CASE2_RIGHT_FRAME_ID:
        raise ValueError("CASE2_CANDIDATE_IDENTITY_MISMATCH: R0 frame identity")
    if abs(float(pair.get("requested_time_s")) - 29.4654055) > 1e-9:
        raise ValueError("CASE2_CANDIDATE_IDENTITY_MISMATCH: requested time")
    if abs(float(pair.get("pair_residual_s")) - 0.0010055) > 1e-9:
        raise ValueError("CASE2_CANDIDATE_IDENTITY_MISMATCH: pair residual")


def validate_case2_baseline(document: Mapping[str, Any]) -> None:
    """Validate the frozen boundary before downstream manual validation."""
    if document.get("case_id") != "phase4_case2":
        raise ValueError("Case 2 baseline has the wrong case identity")
    if not document.get("frozen_for_independent_validation"):
        raise ValueError("Case 2 baseline is not frozen")
    static = document.get("static", {})
    if not static.get("reuse_existing_frozen_static"):
        raise ValueError("Case 2 must reuse the existing frozen Static")
    wave = document.get("wave", {})
    if wave.get("selected_candidate") != CASE2_CANDIDATE_ID:
        raise ValueError("Case 2 baseline must bind candidate_02 only")
    if wave.get("reference_plane", {}).get("source") != "static_reference_plane.yaml":
        raise ValueError("Case 2 Wave must use the frozen Static reference plane")
    if document.get("manual_reference_used_in_reconstruction") is not False:
        raise ValueError("manual reference must remain outside reconstruction")
