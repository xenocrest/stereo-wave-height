"""Independent physical validation of frozen single-frame reconstruction.

This module is deliberately downstream-only.  It reads frozen pixel/XYZ and
height arrays plus manual ruler observations; it never calls reconstruction,
WASS, calibration, synchronization, or reference-plane fitting.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from pathlib import Path

import numpy as np


class RulerScaleDirection(str, Enum):
    """Relationship between increasing ruler values and positive height."""

    INCREASES_WITH_POSITIVE_HEIGHT = "INCREASES_WITH_POSITIVE_HEIGHT"
    DECREASES_WITH_POSITIVE_HEIGHT = "DECREASES_WITH_POSITIVE_HEIGHT"


class PhysicalValidationStatus(str, Enum):
    """States that do not imply an unapproved accuracy pass threshold."""

    MANUAL_REFERENCE_REQUIRED = "MANUAL_REFERENCE_REQUIRED"
    VALIDATION_LOCATION_REQUIRED = "VALIDATION_LOCATION_REQUIRED"
    NO_VALID_RECONSTRUCTION_NEAR_REFERENCE = "NO_VALID_RECONSTRUCTION_NEAR_REFERENCE"
    PHYSICAL_VALIDATION_COMPLETED = "PHYSICAL_VALIDATION_COMPLETED"
    PHYSICAL_VALIDATION_COMPLETED_WITH_WARNING = "PHYSICAL_VALIDATION_COMPLETED_WITH_WARNING"
    PHYSICAL_ACCURACY_NOT_ESTABLISHED = "PHYSICAL_ACCURACY_NOT_ESTABLISHED"


@dataclass(frozen=True)
class LocalHeightReadout:
    """Observed reconstruction values around one manually selected pixel."""

    nearest_distance_px: float
    nearest_height_m: float
    local_median_height_m: float
    local_point_count: int
    neighborhood_radius_px: float
    local_spread_m: float
    support_sufficient: bool
    requested_pixel: tuple[float, float] | None = None
    nearest_pixel: tuple[float, float] | None = None
    nearest_xyz_m: tuple[float, float, float] | None = None
    local_min_height_m: float | None = None
    local_max_height_m: float | None = None
    local_mean_height_m: float | None = None
    local_std_height_m: float | None = None
    local_p5_height_m: float | None = None
    local_p95_height_m: float | None = None


@dataclass(frozen=True)
class PhysicalError:
    """Stereo-versus-ruler error without an accuracy pass/fail claim."""

    signed_error_m: float
    absolute_error_m: float
    relative_error_percent: float | None


@dataclass(frozen=True)
class FrozenObservedHeight:
    """Read-only aligned pixel and height arrays from one frozen R0 result."""

    u_px: np.ndarray
    v_px: np.ndarray
    height_m: np.ndarray
    pixel_coordinate_system: str
    xyz_m: np.ndarray | None = None


@dataclass(frozen=True)
class IndependentValidationResult:
    """Complete comparison using manual truth and frozen observations only."""

    status: PhysicalValidationStatus
    ruler_delta_height_m: float
    stereo_local_height_m: float
    static_support: LocalHeightReadout
    wave_readout: LocalHeightReadout
    error: PhysicalError


def file_sha256(path: str | Path) -> str:
    """Return an uppercase SHA-256 digest for baseline identity checks."""
    digest = sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def require_frozen_baseline(binding: dict[str, object]) -> None:
    """Reject validation against a mutable or unidentified baseline."""
    if binding.get("FROZEN_FOR_INDEPENDENT_VALIDATION") is not True:
        raise ValueError("independent validation requires a frozen baseline")
    for field in ("frozen_source_commit", "static", "wave", "sync_policy", "calibration"):
        if not binding.get(field):
            raise ValueError(f"frozen baseline is missing {field}")


def load_frozen_observed_height(
    pixel_xyz_path: str | Path,
    height_path: str | Path,
    *,
    expected_height_sha256: str,
) -> FrozenObservedHeight:
    """Load aligned frozen observations after checking the recorded height hash."""
    pixel_path = Path(pixel_xyz_path)
    frozen_height_path = Path(height_path)
    if file_sha256(frozen_height_path) != expected_height_sha256.upper():
        raise ValueError("height array does not match the frozen validation baseline")
    with np.load(pixel_path, allow_pickle=False) as pixel_data, np.load(frozen_height_path, allow_pickle=False) as height_data:
        required_pixel = {"u_px", "v_px", "xyz_m", "pixel_coordinate_system"}
        required_height = {"height_m", "water_mask"}
        if not required_pixel.issubset(pixel_data.files) or not required_height.issubset(height_data.files):
            raise ValueError("frozen observation schema is incomplete")
        u = np.asarray(pixel_data["u_px"], dtype=np.float64)
        v = np.asarray(pixel_data["v_px"], dtype=np.float64)
        xyz = np.asarray(pixel_data["xyz_m"], dtype=np.float64)
        height = np.asarray(height_data["height_m"], dtype=np.float64)
        mask = np.asarray(height_data["water_mask"], dtype=bool)
        coordinate_system = str(pixel_data["pixel_coordinate_system"])
    if u.shape != v.shape or u.shape != height.shape or mask.shape != height.shape or xyz.shape != (u.size, 3):
        raise ValueError("pixel, height and mask arrays are not aligned")
    if not np.all(mask):
        u, v, height, xyz = u[mask], v[mask], height[mask], xyz[mask]
    if u.size == 0 or not coordinate_system:
        raise ValueError("frozen observation contains no usable data or coordinate system")
    return FrozenObservedHeight(u.copy(), v.copy(), height.copy(), coordinate_system, xyz.copy())


def ruler_delta_m(
    static_value_mm: float,
    wave_value_mm: float,
    direction: RulerScaleDirection,
) -> float:
    """Convert two manual readings to positive-plane-normal water-level change."""
    values = np.asarray([static_value_mm, wave_value_mm], dtype=np.float64)
    if not np.all(np.isfinite(values)):
        raise ValueError("manual ruler values must be finite")
    raw_delta_m = float((wave_value_mm - static_value_mm) / 1000.0)
    if direction is RulerScaleDirection.INCREASES_WITH_POSITIVE_HEIGHT:
        return raw_delta_m
    if direction is RulerScaleDirection.DECREASES_WITH_POSITIVE_HEIGHT:
        return -raw_delta_m
    raise ValueError("ruler scale direction must be explicit")


def query_local_observed_height(
    u_px: np.ndarray,
    v_px: np.ndarray,
    height_m: np.ndarray,
    *,
    query_u_px: float,
    query_v_px: float,
    maximum_nearest_distance_px: float,
    neighborhood_radius_px: float,
    minimum_local_points: int,
    xyz_m: np.ndarray | None = None,
) -> LocalHeightReadout:
    """Read observed heights near a pixel without interpolation or point creation."""
    u = np.asarray(u_px, dtype=np.float64)
    v = np.asarray(v_px, dtype=np.float64)
    height = np.asarray(height_m, dtype=np.float64)
    xyz = None if xyz_m is None else np.asarray(xyz_m, dtype=np.float64)
    if u.ndim != 1 or u.shape != v.shape or u.shape != height.shape or u.size == 0:
        raise ValueError("pixel and height arrays must have equal non-empty one-dimensional shape")
    if not np.all(np.isfinite(u)) or not np.all(np.isfinite(v)) or not np.all(np.isfinite(height)):
        raise ValueError("pixel and height arrays must contain only finite observed values")
    if xyz is not None and (xyz.shape != (u.size, 3) or not np.all(np.isfinite(xyz))):
        raise ValueError("XYZ must have finite shape [point,3] aligned with pixels")
    scalars = (query_u_px, query_v_px, maximum_nearest_distance_px, neighborhood_radius_px)
    if not all(np.isfinite(value) for value in scalars):
        raise ValueError("query and distance values must be finite")
    if maximum_nearest_distance_px < 0 or neighborhood_radius_px < 0:
        raise ValueError("distance gates must be non-negative")
    if minimum_local_points <= 0:
        raise ValueError("minimum_local_points must be positive")

    distance = np.hypot(u - query_u_px, v - query_v_px)
    nearest_index = int(np.argmin(distance))
    nearest_distance = float(distance[nearest_index])
    if nearest_distance > maximum_nearest_distance_px:
        raise LookupError("NO_VALID_RECONSTRUCTION_NEAR_REFERENCE")
    local = height[distance <= neighborhood_radius_px]
    if local.size == 0:
        raise LookupError("NO_VALID_RECONSTRUCTION_NEAR_REFERENCE")
    median = float(np.median(local))
    spread = float(np.median(np.abs(local - median)))
    return LocalHeightReadout(
        nearest_distance_px=nearest_distance,
        nearest_height_m=float(height[nearest_index]),
        local_median_height_m=median,
        local_point_count=int(local.size),
        neighborhood_radius_px=float(neighborhood_radius_px),
        local_spread_m=spread,
        support_sufficient=bool(local.size >= minimum_local_points),
        requested_pixel=(float(query_u_px), float(query_v_px)),
        nearest_pixel=(float(u[nearest_index]), float(v[nearest_index])),
        nearest_xyz_m=None if xyz is None else tuple(float(value) for value in xyz[nearest_index]),
        local_min_height_m=float(np.min(local)),
        local_max_height_m=float(np.max(local)),
        local_mean_height_m=float(np.mean(local)),
        local_std_height_m=float(np.std(local)),
        local_p5_height_m=float(np.percentile(local, 5)),
        local_p95_height_m=float(np.percentile(local, 95)),
    )


def physical_error(
    stereo_local_height_m: float,
    ruler_delta_height_m: float,
    *,
    relative_error_minimum_reference_m: float,
) -> PhysicalError:
    """Calculate signed/absolute error and guard relative error near zero."""
    values = (stereo_local_height_m, ruler_delta_height_m, relative_error_minimum_reference_m)
    if not all(np.isfinite(value) for value in values):
        raise ValueError("error inputs must be finite")
    if relative_error_minimum_reference_m < 0:
        raise ValueError("relative-error reference gate must be non-negative")
    signed = float(stereo_local_height_m - ruler_delta_height_m)
    relative = None
    if abs(ruler_delta_height_m) > relative_error_minimum_reference_m:
        relative = float(100.0 * abs(signed) / abs(ruler_delta_height_m))
    return PhysicalError(signed, abs(signed), relative)


def compare_frozen_single_frames(
    static_observation: FrozenObservedHeight,
    wave_observation: FrozenObservedHeight,
    *,
    static_value_mm: float,
    wave_value_mm: float,
    direction: RulerScaleDirection,
    static_pixel: tuple[float, float],
    wave_pixel: tuple[float, float],
    maximum_nearest_distance_px: float,
    neighborhood_radius_px: float,
    minimum_local_points: int,
    relative_error_minimum_reference_m: float,
) -> IndependentValidationResult:
    """Compare the frozen local wave height with an independent ruler delta.

    Both independently selected locations are queried.  The formal stereo
    change is the Wave local median minus the Static local median; neither a
    global mean nor a ruler-derived correction enters the calculation.
    """
    if static_observation.pixel_coordinate_system != wave_observation.pixel_coordinate_system:
        raise ValueError("Static and Wave pixel coordinate systems differ")
    common = dict(
        maximum_nearest_distance_px=maximum_nearest_distance_px,
        neighborhood_radius_px=neighborhood_radius_px,
        minimum_local_points=minimum_local_points,
    )
    static_readout = query_local_observed_height(
        static_observation.u_px,
        static_observation.v_px,
        static_observation.height_m,
        query_u_px=static_pixel[0],
        query_v_px=static_pixel[1],
        xyz_m=static_observation.xyz_m,
        **common,
    )
    wave_readout = query_local_observed_height(
        wave_observation.u_px,
        wave_observation.v_px,
        wave_observation.height_m,
        query_u_px=wave_pixel[0],
        query_v_px=wave_pixel[1],
        xyz_m=wave_observation.xyz_m,
        **common,
    )
    ruler_height = ruler_delta_m(static_value_mm, wave_value_mm, direction)
    stereo_delta = wave_readout.local_median_height_m - static_readout.local_median_height_m
    error = physical_error(
        stereo_delta,
        ruler_height,
        relative_error_minimum_reference_m=relative_error_minimum_reference_m,
    )
    status = (
        PhysicalValidationStatus.PHYSICAL_VALIDATION_COMPLETED
        if static_readout.support_sufficient and wave_readout.support_sufficient
        else PhysicalValidationStatus.PHYSICAL_VALIDATION_COMPLETED_WITH_WARNING
    )
    return IndependentValidationResult(
        status=status,
        ruler_delta_height_m=ruler_height,
        stereo_local_height_m=stereo_delta,
        static_support=static_readout,
        wave_readout=wave_readout,
        error=error,
    )
