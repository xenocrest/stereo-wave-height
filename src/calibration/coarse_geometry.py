"""Validation-only coarse stereo geometry configuration (no solver)."""

from __future__ import annotations

from dataclasses import dataclass
import math


_PROVENANCE = {"MEASURED", "USER_SPECIFIED", "ASSUMED", "DERIVED"}


@dataclass(frozen=True)
class CoarseValue:
    value: float | None
    unit: str
    provenance: str

    def __post_init__(self) -> None:
        if self.provenance not in _PROVENANCE:
            raise ValueError("unsupported coarse-geometry provenance")
        if self.value is not None and not math.isfinite(self.value):
            raise ValueError("coarse-geometry values must be finite or null")
        if not self.unit:
            raise ValueError("unit is required")


@dataclass(frozen=True)
class CoarseGeometryConfig:
    """Manual/assumed geometry for algorithm-closure validation only."""

    baseline_m: CoarseValue
    cam0_height_m: CoarseValue
    cam1_height_m: CoarseValue
    cam0_pitch_deg: CoarseValue
    cam1_pitch_deg: CoarseValue
    image_width_px: int
    image_height_px: int
    focal_px: CoarseValue | None = None
    horizontal_fov_deg: CoarseValue | None = None
    cam0_yaw_deg: CoarseValue | None = None
    cam1_yaw_deg: CoarseValue | None = None
    cam0_roll_deg: CoarseValue | None = None
    cam1_roll_deg: CoarseValue | None = None
    principal_point_status: str = "ASSUMED_IMAGE_CENTER"
    distortion_status: str = "ASSUMED_ZERO"
    mode: str = "COARSE_GEOMETRY_VALIDATION"
    metrological_validity: bool = False
    purpose: str = "ALGORITHM_CLOSURE_VALIDATION"

    def __post_init__(self) -> None:
        if self.mode != "COARSE_GEOMETRY_VALIDATION" or self.metrological_validity:
            raise ValueError("coarse mode can never be marked metrically valid")
        if self.purpose != "ALGORITHM_CLOSURE_VALIDATION":
            raise ValueError("coarse mode purpose is fixed")
        if self.image_width_px <= 0 or self.image_height_px <= 0:
            raise ValueError("positive image dimensions are required")
        if self.focal_px is None and self.horizontal_fov_deg is None:
            raise ValueError("approximate focal_px or horizontal_fov_deg is required")
        if self.baseline_m.value is not None and self.baseline_m.value <= 0:
            raise ValueError("baseline_m must be positive when supplied")
