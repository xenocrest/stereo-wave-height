"""Explicit image-orientation normalization before synchronization and WASS."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt


@dataclass(frozen=True)
class OrientationTransform:
    """A declared right-angle transform from encoded to canonical pixels."""

    rotation_deg: int
    source: str
    status: str = "CONFIRMED_FROM_CONTAINER_METADATA"

    def __post_init__(self) -> None:
        normalized = self.rotation_deg % 360
        if normalized not in (0, 90, 180, 270):
            raise ValueError("rotation_deg must be a multiple of 90 degrees")
        if not self.source or self.status in ("", "UNKNOWN", "TODO"):
            raise ValueError("orientation source and status must be explicit")
        object.__setattr__(self, "rotation_deg", normalized)

    def apply(self, image: npt.ArrayLike) -> npt.NDArray[np.generic]:
        """Rotate encoded pixels counter-clockwise into canonical orientation."""
        array = np.asarray(image)
        if array.ndim not in (2, 3) or array.shape[0] == 0 or array.shape[1] == 0:
            raise ValueError("image must be a non-empty [height,width] or [height,width,channels] array")
        turns = self.rotation_deg // 90
        return np.ascontiguousarray(np.rot90(array, k=turns, axes=(0, 1)))

    def as_mapping(self) -> dict[str, object]:
        """Return provenance suitable for JSON/YAML manifests."""
        return {
            "rotation_deg_counter_clockwise": self.rotation_deg,
            "source": self.source,
            "status": self.status,
        }
