"""Case 1 static-reference separation and common-grid tests."""

from __future__ import annotations

from dataclasses import replace
import unittest

import numpy as np

from adapters.wass.output import StandardizedGrid3D
from validation import validate_constant_height_sequence


def _grid(z: np.ndarray) -> StandardizedGrid3D:
    return StandardizedGrid3D(
        x=np.array([0.0, 1.0]),
        y=np.array([0.0]),
        z=z,
        timestamp_ns=np.arange(z.shape[0], dtype=np.int64),
        valid_mask=np.ones(z.shape, dtype=bool),
        coordinate_system="common_test_grid",
        unit="m",
    )


class Case1ConstantHeightTests(unittest.TestCase):
    def test_static_frames_only_are_used_for_z0(self) -> None:
        grid = _grid(np.array([[[2.0, 2.0]], [[2.0, 2.0]], [[2.01, 2.01]]]))
        result = validate_constant_height_sequence(
            grid, static_frame_indices=[0, 1], dynamic_frame_indices=[2], true_height=0.01
        )
        self.assertAlmostEqual(result.mean_recovered_height, 0.01)

    def test_known_constant_offset_and_sign_are_recovered(self) -> None:
        grid = _grid(np.array([[[0.0, 0.0]], [[0.02, 0.02]]]))
        result = validate_constant_height_sequence(
            grid, static_frame_indices=[0], dynamic_frame_indices=[1], true_height=0.02
        )
        self.assertGreater(result.mean_recovered_height, 0.0)
        self.assertAlmostEqual(result.signed_bias, 0.0)
        self.assertAlmostEqual(result.rmse, 0.0)

    def test_overlapping_static_and_dynamic_frames_fail(self) -> None:
        grid = _grid(np.array([[[0.0, 0.0]], [[0.01, 0.01]]]))
        with self.assertRaises(ValueError):
            validate_constant_height_sequence(
                grid, static_frame_indices=[0, 1], dynamic_frame_indices=[1], true_height=0.01
            )

    def test_incompatible_grid_is_rejected_by_model(self) -> None:
        grid = _grid(np.array([[[0.0, 0.0]], [[0.01, 0.01]]]))
        with self.assertRaises(ValueError):
            replace(grid, x=np.array([0.0, 1.0, 2.0]))

    def test_unknown_coordinate_system_is_rejected(self) -> None:
        grid = _grid(np.array([[[0.0, 0.0]], [[0.01, 0.01]]]))
        with self.assertRaises(ValueError):
            replace(grid, coordinate_system="UNKNOWN")

    def test_frame_indices_must_be_ordered_and_in_range(self) -> None:
        grid = _grid(np.array([[[0.0, 0.0]], [[0.01, 0.01]]]))
        with self.assertRaises(ValueError):
            validate_constant_height_sequence(
                grid, static_frame_indices=[0], dynamic_frame_indices=[1, 1], true_height=0.01
            )


if __name__ == "__main__":
    unittest.main()
