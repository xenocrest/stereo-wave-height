"""Configuration and testable selection semantics for WASS plane RANSAC."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

import numpy as np


class PlaneRansacSamplingMode(str, Enum):
    """Supported WASS plane-hypothesis sampling populations."""

    FULL_IMAGE_RANDOM_SAMPLING = "FULL_IMAGE_RANDOM_SAMPLING"
    VALID_POINT_SAMPLING = "VALID_POINT_SAMPLING"


class IntegerSampler(Protocol):
    """Small protocol shared by NumPy generators and deterministic test doubles."""

    def integers(self, high: int, size: int) -> np.ndarray: ...


@dataclass(frozen=True)
class PlaneRansacSamplingPolicy:
    """Plane RANSAC sampling policy; the default preserves upstream behavior."""

    sampling_mode: PlaneRansacSamplingMode = PlaneRansacSamplingMode.FULL_IMAGE_RANDOM_SAMPLING

    def wass_config_line(self) -> str:
        """Render the verified WASS incfg key."""
        return f'PLANE_RANSAC_SAMPLING_MODE="{self.sampling_mode.value}"'

    def sample_flat_indices(self, valid_mask: np.ndarray, rng: IntegerSampler) -> np.ndarray:
        """Select three candidate pixel indices without changing inlier logic.

        The full-image mode intentionally does not repair invalid samples. The
        valid-point mode fails explicitly when fewer than three observations
        exist and otherwise selects only from the valid population.
        """
        mask = np.asarray(valid_mask)
        if mask.ndim != 2 or mask.dtype != np.bool_:
            raise ValueError("valid_mask must be a two-dimensional boolean array")
        if self.sampling_mode is PlaneRansacSamplingMode.FULL_IMAGE_RANDOM_SAMPLING:
            return np.asarray(rng.integers(mask.size, 3), dtype=np.int64)
        valid_indices = np.flatnonzero(mask)
        if valid_indices.size < 3:
            raise ValueError("VALID_POINT_SAMPLING requires at least three valid points")
        selections = np.asarray(rng.integers(valid_indices.size, 3), dtype=np.int64)
        return valid_indices[selections]
