"""Projective line-grid recovery for non-polarity planar calibration targets."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import numpy as np
import numpy.typing as npt


@dataclass(frozen=True)
class PlanarGridHint:
    """Four physical outer-grid corners defining point identity and orientation.

    ``anchor_px`` is physical object origin. ``x_axis_end_px`` and
    ``y_axis_end_px`` define increasing object X and Y. ``opposite_px`` is the
    remaining outer corner. This explicit convention prevents symmetric grids
    from silently reversing point IDs between cameras.
    """

    anchor_px: tuple[float, float]
    x_axis_end_px: tuple[float, float]
    opposite_px: tuple[float, float]
    y_axis_end_px: tuple[float, float]
    source: str = "MANUAL_SEMIAUTOMATIC_ORIENTATION_HINT"

    def as_quad(self) -> npt.NDArray[np.float32]:
        quad = np.asarray(
            [self.anchor_px, self.x_axis_end_px, self.opposite_px, self.y_axis_end_px],
            dtype=np.float32,
        )
        if quad.shape != (4, 2) or not np.all(np.isfinite(quad)):
            raise ValueError("grid hint corners must be four finite 2-D points")
        signed_area = 0.5 * np.sum(quad[:, 0] * np.roll(quad[:, 1], -1) - quad[:, 1] * np.roll(quad[:, 0], -1))
        if abs(float(signed_area)) < 1.0:
            raise ValueError("grid hint quadrilateral is degenerate")
        return quad


@dataclass(frozen=True)
class PlanarGridDiagnostics:
    """Evidence for accepting or rejecting a recovered lattice."""

    mode: str
    usable_x_lines: int
    usable_y_lines: int
    candidate_intersections: int
    final_lattice_shape: tuple[int, int]
    confidence: float
    x_line_support: tuple[float, ...]
    y_line_support: tuple[float, ...]
    rejection_reason: str | None


@dataclass(frozen=True)
class PlanarGridRecovery:
    """Ordered row-major internal intersections and their line families."""

    detected: bool
    ordered_points_px: npt.NDArray[np.float32] | None
    raw_points_px: npt.NDArray[np.float32] | None
    x_family_lines_px: npt.NDArray[np.float32]
    y_family_lines_px: npt.NDArray[np.float32]
    diagnostics: PlanarGridDiagnostics


def _cv2(module: Any | None) -> Any:
    if module is not None:
        return module
    try:
        import cv2
    except ImportError as error:
        raise RuntimeError("OpenCV is required for planar-grid recovery") from error
    return cv2


def _validate_gray(grayscale: npt.ArrayLike) -> npt.NDArray[np.uint8]:
    image = np.asarray(grayscale)
    if image.ndim != 2 or image.dtype != np.uint8 or image.size == 0:
        raise ValueError("grayscale must be a non-empty uint8 [height,width] image")
    return image


def _select_profile_peaks(
    profile: npt.NDArray[np.float64],
    *,
    internal_count: int,
    physical_cell_count: int,
    search_fraction: float,
) -> tuple[np.ndarray, tuple[float, ...]]:
    length = profile.size
    spacing = length / physical_cell_count
    baseline = float(np.median(profile)) + 1e-9
    positions: list[float] = []
    supports: list[float] = []
    radius = max(3, int(round(spacing * search_fraction)))
    for index in range(1, internal_count + 1):
        centre = index * spacing
        lo = max(1, int(round(centre)) - radius)
        hi = min(length - 1, int(round(centre)) + radius + 1)
        if hi <= lo:
            raise ValueError("rectified search window is empty")
        local = profile[lo:hi]
        peak = lo + int(np.argmax(local))
        positions.append(float(peak))
        supports.append(float(profile[peak] / baseline))
    return np.asarray(positions, dtype=np.float32), tuple(supports)


def _transform_points(cv2: Any, points: npt.NDArray[np.float32], matrix: npt.NDArray[np.float64]) -> npt.NDArray[np.float32]:
    return cv2.perspectiveTransform(points.reshape(-1, 1, 2), matrix).reshape(-1, 2).astype(np.float32)


def recover_planar_grid(
    grayscale: npt.ArrayLike,
    *,
    expected_cols: int,
    expected_rows: int,
    hint: PlanarGridHint,
    cv2_module: Any | None = None,
    cell_px: int = 100,
    minimum_line_support: float = 1.35,
) -> PlanarGridRecovery:
    """Recover a projective line grid from an explicitly oriented outer quad.

    The target contains ``expected_cols + 1`` physical cells horizontally and
    ``expected_rows + 1`` vertically, so excluding the outer boundary leaves
    exactly ``expected_cols * expected_rows`` internal intersections. Peaks are
    searched near projectively rectified lattice positions and rejected when
    line-gradient support is weak; points are never synthesized after failure.
    """
    cv2 = _cv2(cv2_module)
    image = _validate_gray(grayscale)
    if expected_cols < 2 or expected_rows < 2 or cell_px < 20:
        raise ValueError("grid dimensions and cell_px are invalid")
    quad = hint.as_quad()
    cells_x = expected_cols + 1
    cells_y = expected_rows + 1
    width = cells_x * cell_px
    height = cells_y * cell_px
    destination = np.asarray([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype=np.float32)
    homography = cv2.getPerspectiveTransform(quad, destination)
    inverse = np.linalg.inv(homography)
    rectified = cv2.warpPerspective(image, homography, (width, height), flags=cv2.INTER_LINEAR)
    normalized = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(rectified)
    gradient_x = np.abs(cv2.Sobel(normalized, cv2.CV_32F, 1, 0, ksize=3))
    gradient_y = np.abs(cv2.Sobel(normalized, cv2.CV_32F, 0, 1, ksize=3))
    margin_x = max(3, cell_px // 8)
    margin_y = max(3, cell_px // 8)
    x_profile = np.mean(gradient_x[margin_y : height - margin_y], axis=0).astype(np.float64)
    y_profile = np.mean(gradient_y[:, margin_x : width - margin_x], axis=1).astype(np.float64)
    x_positions, x_support = _select_profile_peaks(
        x_profile, internal_count=expected_cols, physical_cell_count=cells_x, search_fraction=0.30
    )
    y_positions, y_support = _select_profile_peaks(
        y_profile, internal_count=expected_rows, physical_cell_count=cells_y, search_fraction=0.30
    )
    support_ok = min((*x_support, *y_support)) >= minimum_line_support
    x_lines_rect = np.asarray([[[x, 0], [x, height - 1]] for x in x_positions], dtype=np.float32)
    y_lines_rect = np.asarray([[[0, y], [width - 1, y]] for y in y_positions], dtype=np.float32)
    x_lines = _transform_points(cv2, x_lines_rect.reshape(-1, 2), inverse).reshape(-1, 2, 2)
    y_lines = _transform_points(cv2, y_lines_rect.reshape(-1, 2), inverse).reshape(-1, 2, 2)
    rectified_points = np.asarray([(x, y) for y in y_positions for x in x_positions], dtype=np.float32)
    raw_points = _transform_points(cv2, rectified_points, inverse)
    if not support_ok:
        diagnostics = PlanarGridDiagnostics(
            "SEMIAUTOMATIC_ORIENTED_QUAD", expected_cols, expected_rows,
            int(raw_points.shape[0]), (expected_rows, expected_cols),
            float(min((*x_support, *y_support)) / minimum_line_support), x_support, y_support,
            "insufficient line-gradient support",
        )
        return PlanarGridRecovery(False, None, raw_points, x_lines, y_lines, diagnostics)
    image_height, image_width = image.shape
    refinement_margin = 8.0
    inside = (
        (raw_points[:, 0] >= refinement_margin)
        & (raw_points[:, 0] < image_width - refinement_margin)
        & (raw_points[:, 1] >= refinement_margin)
        & (raw_points[:, 1] < image_height - refinement_margin)
    )
    if not bool(np.all(inside)):
        diagnostics = PlanarGridDiagnostics(
            "SEMIAUTOMATIC_ORIENTED_QUAD", expected_cols, expected_rows,
            int(raw_points.shape[0]), (expected_rows, expected_cols), 0.0,
            x_support, y_support, "one or more expected intersections are outside the image",
        )
        return PlanarGridRecovery(False, None, raw_points, x_lines, y_lines, diagnostics)
    refined = raw_points.reshape(-1, 1, 2).copy()
    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 50, 1e-4)
    cv2.cornerSubPix(image, refined, (7, 7), (-1, -1), criteria)
    refined = refined.reshape(-1, 2)
    displacement = np.linalg.norm(refined - raw_points, axis=1)
    max_allowed = max(8.0, cell_px * 0.18)
    if float(np.max(displacement)) > max_allowed:
        diagnostics = PlanarGridDiagnostics(
            "SEMIAUTOMATIC_ORIENTED_QUAD", expected_cols, expected_rows,
            int(raw_points.shape[0]), (expected_rows, expected_cols), 0.0,
            x_support, y_support, "subpixel refinement escaped the expected intersection neighbourhood",
        )
        return PlanarGridRecovery(False, None, raw_points, x_lines, y_lines, diagnostics)
    confidence = min(1.0, min((*x_support, *y_support)) / (minimum_line_support * 2.0))
    diagnostics = PlanarGridDiagnostics(
        "SEMIAUTOMATIC_ORIENTED_QUAD", expected_cols, expected_rows,
        int(refined.shape[0]), (expected_rows, expected_cols), float(confidence),
        x_support, y_support, None,
    )
    return PlanarGridRecovery(True, refined.astype(np.float32), raw_points, x_lines, y_lines, diagnostics)


def orient_quad(
    unordered_quad_px: npt.ArrayLike,
    *,
    anchor_index: int,
    x_axis_neighbour_index: int,
) -> PlanarGridHint:
    """Resolve a cyclic quad using an explicit physical anchor and +X neighbour."""
    quad = np.asarray(unordered_quad_px, dtype=np.float64)
    if quad.shape != (4, 2) or not np.all(np.isfinite(quad)):
        raise ValueError("unordered_quad_px must have shape [4,2]")
    if anchor_index not in range(4) or x_axis_neighbour_index not in range(4) or anchor_index == x_axis_neighbour_index:
        raise ValueError("anchor and x-axis neighbour indices must be distinct quad vertices")
    anchor = quad[anchor_index]
    distances = np.linalg.norm(quad - anchor, axis=1)
    neighbours = [index for index in np.argsort(distances)[1:3]]
    if x_axis_neighbour_index not in neighbours:
        raise ValueError("x_axis_neighbour_index must be adjacent to anchor")
    y_index = neighbours[0] if neighbours[1] == x_axis_neighbour_index else neighbours[1]
    opposite_index = next(index for index in range(4) if index not in (anchor_index, x_axis_neighbour_index, y_index))
    return PlanarGridHint(tuple(anchor), tuple(quad[x_axis_neighbour_index]), tuple(quad[opposite_index]), tuple(quad[y_index]))
