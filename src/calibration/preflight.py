"""Checkerboard preflight, pose diversity, and stereo candidate pairing."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Iterable

import numpy as np
import numpy.typing as npt

from .checkerboard import CheckerboardSpec, detect_and_refine_checkerboard


@dataclass(frozen=True)
class PreflightThresholds:
    """Project heuristics; configurable and not universal calibration standards."""

    minimum_sharpness: float = 80.0
    minimum_coverage_fraction: float = 0.04
    maximum_coverage_fraction: float = 0.80
    minimum_edge_margin_px: float = 12.0
    maximum_perspective_score: float = 0.80
    duplicate_signature_distance: float = 0.12
    minimum_independent_poses: int = 12
    preferred_independent_poses: int = 20

    def __post_init__(self) -> None:
        numeric = (
            self.minimum_sharpness,
            self.minimum_coverage_fraction,
            self.maximum_coverage_fraction,
            self.minimum_edge_margin_px,
            self.maximum_perspective_score,
            self.duplicate_signature_distance,
        )
        if not all(math.isfinite(value) and value >= 0 for value in numeric):
            raise ValueError("preflight thresholds must be finite and non-negative")
        if not 0 < self.minimum_coverage_fraction < self.maximum_coverage_fraction <= 1:
            raise ValueError("coverage thresholds must satisfy 0 < minimum < maximum <= 1")
        if self.minimum_independent_poses < 3 or self.preferred_independent_poses < self.minimum_independent_poses:
            raise ValueError("pose-count thresholds are inconsistent")


@dataclass(frozen=True)
class CalibrationFrameAssessment:
    """Single canonical frame assessment shared by CLI and GUI consumers."""

    frame_id: str
    timestamp_ns: int
    camera_role: str
    detected: bool
    corner_count: int
    expected_corner_count: int
    corners_subpixel_px: npt.NDArray[np.float32] | None
    coverage_fraction: float
    bbox_fraction: float
    sharpness_score: float
    edge_margin_px: float
    perspective_score: float
    saturation_fraction: float
    pose_signature: tuple[float, ...] | None
    reject_reason: str | None
    warnings: tuple[str, ...]
    usable: bool

    def as_mapping(self, *, include_corners: bool = False) -> dict[str, object]:
        result: dict[str, object] = {
            "frame_id": self.frame_id,
            "timestamp_ns": self.timestamp_ns,
            "camera_role": self.camera_role,
            "detected": self.detected,
            "corner_count": self.corner_count,
            "expected_corner_count": self.expected_corner_count,
            "coverage_fraction": self.coverage_fraction,
            "bbox_fraction": self.bbox_fraction,
            "sharpness_score": self.sharpness_score,
            "edge_margin_px": self.edge_margin_px,
            "perspective_score": self.perspective_score,
            "saturation_fraction": self.saturation_fraction,
            "pose_signature": list(self.pose_signature) if self.pose_signature is not None else None,
            "reject_reason": self.reject_reason,
            "warnings": list(self.warnings),
            "usable": self.usable,
        }
        if include_corners:
            result["corners_subpixel_px"] = (
                self.corners_subpixel_px.reshape(-1, 2).tolist()
                if self.corners_subpixel_px is not None else None
            )
        return result


@dataclass(frozen=True)
class DiverseViewSelection:
    accepted: tuple[CalibrationFrameAssessment, ...]
    duplicates: tuple[CalibrationFrameAssessment, ...]
    rejected: tuple[CalibrationFrameAssessment, ...]
    duplicate_groups: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class DatasetReadiness:
    independent_pose_count: int
    position_coverage: str
    scale_diversity: str
    orientation_diversity: str
    overall_diversity_score: float
    status: str
    warnings: tuple[str, ...]

    def as_mapping(self) -> dict[str, object]:
        return {
            "independent_pose_count": self.independent_pose_count,
            "position_coverage": self.position_coverage,
            "scale_diversity": self.scale_diversity,
            "orientation_diversity": self.orientation_diversity,
            "overall_diversity_score": self.overall_diversity_score,
            "status": self.status,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class StereoCalibrationPair:
    left: CalibrationFrameAssessment
    right: CalibrationFrameAssessment
    delta_t_ns: int
    pose_distance: float
    usable: bool
    reject_reason: str | None


@dataclass(frozen=True)
class CalibrationFrameSample:
    """Canonical grayscale sample carrying decoder-provided timestamp evidence."""

    frame_id: str
    timestamp_ns: int
    timestamp_source: str
    camera_role: str
    grayscale: npt.NDArray[np.uint8]

    def __post_init__(self) -> None:
        image = np.asarray(self.grayscale)
        if self.timestamp_ns < 0 or not self.timestamp_source or self.timestamp_source.upper() in {"UNKNOWN", "TODO"}:
            raise ValueError("a non-negative timestamp and explicit timestamp source are required")
        if image.ndim != 2 or image.dtype != np.uint8:
            raise ValueError("sample grayscale must be uint8 [height,width]")


@dataclass(frozen=True)
class CalibrationCandidateExtraction:
    sampled: tuple[CalibrationFrameAssessment, ...]
    diverse: DiverseViewSelection
    timestamp_source: str


def extract_calibration_video_candidates(
    samples: Iterable[CalibrationFrameSample],
    spec: CheckerboardSpec,
    *,
    minimum_interval_ns: int,
    thresholds: PreflightThresholds = PreflightThresholds(),
    cv2_module: Any | None = None,
) -> CalibrationCandidateExtraction:
    """Assess PTS-bearing samples and keep the sharpest representative per pose.

    Decoding is deliberately backend-independent. Callers must supply canonical
    frames with real decoder/container timestamps; equal frame indices are not
    accepted as timestamp evidence by this interface.
    """
    ordered = sorted(samples, key=lambda item: (item.timestamp_ns, item.frame_id))
    if minimum_interval_ns <= 0:
        raise ValueError("minimum_interval_ns must be positive")
    kept: list[CalibrationFrameSample] = []
    last = -minimum_interval_ns
    for sample in ordered:
        if sample.timestamp_ns - last >= minimum_interval_ns:
            kept.append(sample); last = sample.timestamp_ns
    assessments = tuple(
        assess_checkerboard_frame(
            sample.grayscale, spec, frame_id=sample.frame_id,
            timestamp_ns=sample.timestamp_ns, camera_role=sample.camera_role,
            thresholds=thresholds, cv2_module=cv2_module,
        ) for sample in kept
    )
    diverse = select_diverse_calibration_views(
        assessments, duplicate_distance=thresholds.duplicate_signature_distance
    )
    sources = {sample.timestamp_source for sample in kept}
    source = next(iter(sources)) if len(sources) == 1 else "multiple_explicit_timestamp_sources"
    return CalibrationCandidateExtraction(assessments, diverse, source)


def target_preflight_status(
    cam0: CalibrationFrameAssessment,
    cam1: CalibrationFrameAssessment,
    stereo_pair: StereoCalibrationPair | None,
) -> str:
    """Gate A: both complete usable views and one geometry/time-consistent pair."""
    return "TARGET_PREFLIGHT_PASS" if cam0.usable and cam1.usable and stereo_pair is not None and stereo_pair.usable else "TARGET_PREFLIGHT_FAIL"


def _cv2(module: Any | None) -> Any:
    if module is not None:
        return module
    try:
        import cv2
    except ImportError as error:
        raise RuntimeError("OpenCV is required for calibration preflight") from error
    return cv2


def _pose_geometry(points: npt.NDArray[np.float32], width: int, height: int, cv2: Any) -> tuple[float, float, float, float, float, tuple[float, ...]]:
    xy = points.reshape(-1, 2).astype(np.float64)
    hull = cv2.convexHull(xy.astype(np.float32))
    area_fraction = float(cv2.contourArea(hull) / (width * height))
    minimum = xy.min(axis=0); maximum = xy.max(axis=0)
    bbox_fraction = float(np.prod(maximum - minimum) / (width * height))
    edge_margin = float(min(minimum[0], minimum[1], width - 1 - maximum[0], height - 1 - maximum[1]))
    tl, tr, bl, br = xy[0], xy[8], xy[-9], xy[-1]
    top = np.linalg.norm(tr - tl); bottom = np.linalg.norm(br - bl)
    left = np.linalg.norm(bl - tl); right = np.linalg.norm(br - tr)
    perspective = float(max(abs(top - bottom) / max(top, bottom), abs(left - right) / max(left, right)))
    row_vector = tr - tl; col_vector = bl - tl
    row_angle = math.atan2(row_vector[1], row_vector[0]) / math.pi
    col_angle = math.atan2(col_vector[1], col_vector[0]) / math.pi
    cosine = float(np.dot(row_vector, col_vector) / (np.linalg.norm(row_vector) * np.linalg.norm(col_vector)))
    centre = xy.mean(axis=0)
    signature = (
        float(centre[0] / width), float(centre[1] / height),
        float(math.log(max(area_fraction, 1e-12))), row_angle, col_angle,
        cosine, perspective,
    )
    return area_fraction, bbox_fraction, edge_margin, perspective, cosine, signature


def assess_checkerboard_frame(
    grayscale: npt.ArrayLike,
    spec: CheckerboardSpec,
    *,
    frame_id: str,
    timestamp_ns: int,
    camera_role: str,
    thresholds: PreflightThresholds = PreflightThresholds(),
    cv2_module: Any | None = None,
) -> CalibrationFrameAssessment:
    """Assess one already canonical-orientation frame against Gate A."""
    cv2 = _cv2(cv2_module)
    image = np.asarray(grayscale)
    if image.ndim != 2 or image.dtype != np.uint8 or image.size == 0:
        raise ValueError("grayscale must be a non-empty uint8 image")
    sharpness = float(cv2.Laplacian(image, cv2.CV_64F).var())
    saturation = float(np.mean((image <= 2) | (image >= 253)))
    detection = detect_and_refine_checkerboard(image, spec, cv2_module=cv2)
    if detection is None:
        return CalibrationFrameAssessment(
            frame_id, timestamp_ns, camera_role, False, 0, spec.total_inner_corners,
            None, 0.0, 0.0, sharpness, 0.0, 1.0, saturation, None,
            "complete checkerboard not detected", (), False,
        )
    height, width = image.shape
    points = detection.refined_corners_px
    coverage, bbox, margin, perspective, _, signature = _pose_geometry(points, width, height, cv2)
    failures: list[str] = []
    warnings: list[str] = []
    if sharpness < thresholds.minimum_sharpness: failures.append("sharpness below configured minimum")
    if coverage < thresholds.minimum_coverage_fraction: failures.append("board coverage below configured minimum")
    if coverage > thresholds.maximum_coverage_fraction: failures.append("board coverage above configured maximum")
    if margin < thresholds.minimum_edge_margin_px: failures.append("board too close to or outside image edge")
    if perspective > thresholds.maximum_perspective_score: failures.append("perspective exceeds configured maximum")
    if saturation > 0.20: warnings.append("more than 20% of pixels are near saturation")
    return CalibrationFrameAssessment(
        frame_id, timestamp_ns, camera_role, True, points.shape[0], spec.total_inner_corners,
        points.copy(), coverage, bbox, sharpness, margin, perspective, saturation,
        signature, "; ".join(failures) if failures else None, tuple(warnings), not failures,
    )


def pose_signature_distance(left: CalibrationFrameAssessment, right: CalibrationFrameAssessment) -> float:
    """Weighted Euclidean distance between image-only pose signatures."""
    if left.pose_signature is None or right.pose_signature is None:
        raise ValueError("pose signatures are required")
    a = np.asarray(left.pose_signature); b = np.asarray(right.pose_signature)
    weights = np.asarray([1.0, 1.0, 0.25, 0.5, 0.5, 0.5, 0.5])
    return float(np.linalg.norm((a - b) * weights))


def select_diverse_calibration_views(
    assessments: Iterable[CalibrationFrameAssessment],
    *,
    duplicate_distance: float,
    maximum_views: int | None = None,
) -> DiverseViewSelection:
    """Deterministic greedy farthest-point selection; time spacing is ignored."""
    items = tuple(assessments)
    usable = [item for item in items if item.usable and item.pose_signature is not None]
    rejected = tuple(item for item in items if not item.usable or item.pose_signature is None)
    if duplicate_distance <= 0:
        raise ValueError("duplicate_distance must be positive")
    if not usable:
        return DiverseViewSelection((), (), rejected, ())
    usable.sort(key=lambda item: (-item.sharpness_score, item.timestamp_ns, item.frame_id))
    accepted = [usable.pop(0)]; duplicates: list[CalibrationFrameAssessment] = []
    groups: list[list[str]] = [[accepted[0].frame_id]]
    while usable and (maximum_views is None or len(accepted) < maximum_views):
        distances = [min(pose_signature_distance(item, chosen) for chosen in accepted) for item in usable]
        index = max(range(len(usable)), key=lambda i: (distances[i], -usable[i].timestamp_ns, usable[i].frame_id))
        candidate = usable.pop(index)
        if distances[index] < duplicate_distance:
            duplicates.append(candidate)
            nearest = min(range(len(accepted)), key=lambda i: pose_signature_distance(candidate, accepted[i]))
            groups[nearest].append(candidate.frame_id)
        else:
            accepted.append(candidate); groups.append([candidate.frame_id])
    for item in usable:
        duplicates.append(item)
        nearest = min(range(len(accepted)), key=lambda i: pose_signature_distance(item, accepted[i]))
        groups[nearest].append(item.frame_id)
    return DiverseViewSelection(tuple(accepted), tuple(duplicates), rejected, tuple(tuple(group) for group in groups))


def summarize_dataset_readiness(
    selected: DiverseViewSelection,
    thresholds: PreflightThresholds = PreflightThresholds(),
) -> DatasetReadiness:
    """Summarize continuous pose coverage before calibration is attempted."""
    n = len(selected.accepted)
    if not n:
        return DatasetReadiness(0, "FAIL", "FAIL", "FAIL", 0.0, "CALIBRATION_DATASET_INSUFFICIENT", ("no usable independent poses",))
    signatures = np.asarray([item.pose_signature for item in selected.accepted], dtype=float)
    x_span = float(np.ptp(signatures[:, 0])); y_span = float(np.ptp(signatures[:, 1]))
    scale_span = float(np.ptp(signatures[:, 2])); angle_span = float(max(np.ptp(signatures[:, 3]), np.ptp(signatures[:, 4])))
    position = "PASS" if x_span >= 0.25 and y_span >= 0.20 else "WARN"
    scale = "PASS" if scale_span >= 0.45 else "WARN"
    orientation = "PASS" if angle_span >= 0.15 else "WARN"
    count_score = min(1.0, n / thresholds.preferred_independent_poses)
    diversity = float(np.mean([min(1.0, x_span / 0.25), min(1.0, y_span / 0.20), min(1.0, scale_span / 0.45), min(1.0, angle_span / 0.15), count_score]))
    warnings: list[str] = []
    if n < thresholds.minimum_independent_poses:
        status = "CALIBRATION_DATASET_INSUFFICIENT"; warnings.append("below minimum independent-pose threshold")
    elif n < thresholds.preferred_independent_poses or "WARN" in (position, scale, orientation):
        status = "CALIBRATION_DATASET_READY_WITH_WARNING"; warnings.append("below preferred count or diversity coverage")
    else:
        status = "CALIBRATION_DATASET_READY"
    return DatasetReadiness(n, position, scale, orientation, diversity, status, tuple(warnings))


def pair_stereo_calibration_views(
    left: Iterable[CalibrationFrameAssessment],
    right: Iterable[CalibrationFrameAssessment],
    *,
    maximum_delta_t_ns: int,
    maximum_pose_distance: float,
) -> tuple[StereoCalibrationPair, ...]:
    """One-to-one timestamp/geometry pairing without assuming equal frame indices."""
    candidates: list[tuple[int, float, str, str, CalibrationFrameAssessment, CalibrationFrameAssessment]] = []
    for a in left:
        if not a.usable: continue
        for b in right:
            if not b.usable: continue
            dt = abs(a.timestamp_ns - b.timestamp_ns)
            distance = pose_signature_distance(a, b)
            candidates.append((dt, distance, a.frame_id, b.frame_id, a, b))
    candidates.sort(key=lambda item: item[:4])
    used_left: set[str] = set(); used_right: set[str] = set(); result: list[StereoCalibrationPair] = []
    for dt, distance, _, _, a, b in candidates:
        if a.frame_id in used_left or b.frame_id in used_right: continue
        usable = dt <= maximum_delta_t_ns and distance <= maximum_pose_distance
        if not usable: continue
        result.append(StereoCalibrationPair(a, b, dt, distance, True, None))
        used_left.add(a.frame_id); used_right.add(b.frame_id)
    return tuple(result)
