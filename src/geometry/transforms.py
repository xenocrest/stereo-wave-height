"""Declared rigid/similarity transforms without unit or axis inference."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt


FloatArray = npt.NDArray[np.float64]
AxisDirections = tuple[str, str, str]


def _known(value: str, name: str) -> str:
    normalized = value.strip()
    if not normalized or normalized.upper() in {"UNKNOWN", "TODO", "UNKNOWN/TODO"}:
        raise ValueError(f"{name} must be explicitly known")
    return normalized


def require_axis_directions(actual: AxisDirections, expected: AxisDirections) -> None:
    """Require exact, explicit axis directions; never infer or auto-flip axes."""
    if len(actual) != 3 or len(expected) != 3:
        raise ValueError("axis direction tuples must contain x, y, and z descriptions")
    actual_known = tuple(_known(value, "actual axis direction") for value in actual)
    expected_known = tuple(_known(value, "expected axis direction") for value in expected)
    if actual_known != expected_known:
        raise ValueError(f"axis directions {actual_known} do not match {expected_known}")


@dataclass(frozen=True)
class SimilarityTransform:
    """A declared transform ``target = scale * R * source + translation``.

    The caller must explicitly provide coordinate systems, units, and axis
    direction descriptions. The class validates a proper 3-D rotation and
    refuses mismatched input metadata.
    """

    scale: float
    rotation: FloatArray
    translation: FloatArray
    source_coordinate_system: str
    target_coordinate_system: str
    source_unit: str
    target_unit: str
    source_axes: AxisDirections
    target_axes: AxisDirections

    def __post_init__(self) -> None:
        rotation = np.asarray(self.rotation, dtype=np.float64)
        translation = np.asarray(self.translation, dtype=np.float64)
        if not np.isfinite(self.scale) or self.scale <= 0:
            raise ValueError("scale must be finite and positive")
        if rotation.shape != (3, 3):
            raise ValueError("rotation must have shape [3, 3]")
        if translation.shape != (3,):
            raise ValueError("translation must have shape [3]")
        if not np.all(np.isfinite(rotation)) or not np.all(np.isfinite(translation)):
            raise ValueError("rotation and translation must be finite")
        if not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-12, rtol=0.0):
            raise ValueError("rotation must be orthonormal")
        if not np.isclose(np.linalg.det(rotation), 1.0, atol=1e-12, rtol=0.0):
            raise ValueError("rotation must be right-handed with determinant +1")

        object.__setattr__(self, "rotation", rotation.copy())
        object.__setattr__(self, "translation", translation.copy())
        for field in (
            "source_coordinate_system",
            "target_coordinate_system",
            "source_unit",
            "target_unit",
        ):
            object.__setattr__(self, field, _known(getattr(self, field), field))
        tuple(_known(value, "source axis direction") for value in self.source_axes)
        tuple(_known(value, "target axis direction") for value in self.target_axes)

    def apply(
        self,
        points: npt.ArrayLike,
        *,
        coordinate_system: str,
        unit: str,
        axis_directions: AxisDirections,
    ) -> FloatArray:
        """Transform ``[..., 3]`` points after exact metadata checks."""
        if _known(coordinate_system, "coordinate_system") != self.source_coordinate_system:
            raise ValueError("source coordinate system mismatch")
        if _known(unit, "unit") != self.source_unit:
            raise ValueError("source unit mismatch")
        require_axis_directions(axis_directions, self.source_axes)

        array = np.asarray(points, dtype=np.float64)
        if array.ndim < 1 or array.shape[-1] != 3:
            raise ValueError("points must have shape [..., 3]")
        if not np.all(np.isfinite(array)):
            raise ValueError("points passed to a transform must be finite")
        return self.scale * (array @ self.rotation.T) + self.translation
