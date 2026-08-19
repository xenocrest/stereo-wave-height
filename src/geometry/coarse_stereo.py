"""Strict provenance model for an uncalibrated stereo feasibility hypothesis."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
import numpy.typing as npt


APPROXIMATE_STATUS = "APPROXIMATE_UNCALIBRATED"
INTRINSIC_STATUS = "ASSUMED_FOR_FEASIBILITY_ONLY"


def baseline_mm_to_m(value_mm: float) -> float:
    """Convert a finite positive manual baseline from millimetres to metres."""
    if not math.isfinite(value_mm) or value_mm <= 0:
        raise ValueError("baseline_mm must be finite and positive")
    return value_mm / 1000.0


@dataclass(frozen=True)
class CoarseIntrinsicHypothesis:
    """Pinhole K whose values are assumptions, never calibration results."""

    width_px: int
    height_px: int
    fx_px: float
    fy_px: float
    cx_px: float
    cy_px: float
    focal_source: str
    status: str = INTRINSIC_STATUS
    distortion: tuple[float, float, float, float, float] = (0.0, 0.0, 0.0, 0.0, 0.0)

    def __post_init__(self) -> None:
        values = (self.fx_px, self.fy_px, self.cx_px, self.cy_px, *self.distortion)
        if self.width_px <= 0 or self.height_px <= 0 or not all(math.isfinite(v) for v in values):
            raise ValueError("coarse intrinsic values must be finite with positive image dimensions")
        if self.fx_px <= 0 or self.fy_px <= 0:
            raise ValueError("coarse focal lengths must be positive")
        if self.status != INTRINSIC_STATUS or not self.focal_source:
            raise ValueError("coarse K must retain feasibility-only provenance")

    @property
    def matrix(self) -> npt.NDArray[np.float64]:
        return np.array(
            [[self.fx_px, 0.0, self.cx_px], [0.0, self.fy_px, self.cy_px], [0.0, 0.0, 1.0]],
            dtype=np.float64,
        )


@dataclass(frozen=True)
class CoarseStereoGeometry:
    """Relative stereo hypothesis kept separate from common deployment pitch."""

    left: CoarseIntrinsicHypothesis
    right: CoarseIntrinsicHypothesis
    baseline_m: float
    relative_rotation_right_from_left: npt.NDArray[np.float64]
    translation_right_from_left_m: npt.NDArray[np.float64]
    common_pitch_deg: float
    status: str = APPROXIMATE_STATUS

    def __post_init__(self) -> None:
        rotation = np.asarray(self.relative_rotation_right_from_left, dtype=np.float64)
        translation = np.asarray(self.translation_right_from_left_m, dtype=np.float64)
        if self.status != APPROXIMATE_STATUS:
            raise ValueError("coarse geometry status must remain APPROXIMATE_UNCALIBRATED")
        if not math.isfinite(self.baseline_m) or self.baseline_m <= 0:
            raise ValueError("baseline_m must be finite and positive")
        if rotation.shape != (3, 3) or not np.allclose(rotation, np.eye(3), atol=0.0, rtol=0.0):
            raise ValueError("Trial-1 relative rotation must be the explicit parallel-placement identity assumption")
        if translation.shape != (3,) or not np.allclose(translation, [self.baseline_m, 0.0, 0.0]):
            raise ValueError("translation must preserve the manual baseline as [B,0,0] m")
        if not math.isfinite(self.common_pitch_deg):
            raise ValueError("common_pitch_deg must be finite")
        object.__setattr__(self, "relative_rotation_right_from_left", rotation.copy())
        object.__setattr__(self, "translation_right_from_left_m", translation.copy())

    def as_mapping(self) -> dict[str, object]:
        """Serialize with common pitch outside relative stereo rotation."""
        return {
            "status": self.status,
            "baseline_m": self.baseline_m,
            "relative_rotation_right_from_left": self.relative_rotation_right_from_left.tolist(),
            "translation_right_from_left_m": self.translation_right_from_left_m.tolist(),
            "common_system_pitch_deg": self.common_pitch_deg,
            "common_pitch_role": "deployment_orientation_not_relative_stereo_rotation",
            "intrinsic_status": self.left.status,
        }
