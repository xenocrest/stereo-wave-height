"""Unit tests for the post-WASS height-processing core only."""

from __future__ import annotations

import math
import unittest
from dataclasses import replace

import numpy as np

from adapters.wass.output import StandardizedGrid3D
from geometry import SimilarityTransform
from height import HeightField, calculate_height
from reference import StaticWaterReference, valid_temporal_mean
from validation import calculate_height_metrics


WORLD_AXES = ("+Xw", "+Yw", "+Zw_up")


def make_grid(
    z: np.ndarray,
    *,
    valid_mask: np.ndarray | None = None,
    coordinate_system: str = "world_water_surface",
    unit: str = "m",
) -> StandardizedGrid3D:
    """Build a small canonical simulated WASS output for tests."""
    z_array = np.asarray(z, dtype=np.float64)
    if valid_mask is None:
        mask = np.ones(z_array.shape, dtype=np.bool_)
    else:
        mask = np.asarray(valid_mask, dtype=np.bool_)
    return StandardizedGrid3D(
        x=np.arange(z_array.shape[2], dtype=np.float64),
        y=np.arange(z_array.shape[1], dtype=np.float64),
        z=z_array,
        timestamp_ns=np.arange(z_array.shape[0], dtype=np.int64) * 1_000_000,
        valid_mask=mask,
        coordinate_system=coordinate_system,
        unit=unit,
    )


class PostWassCoreTests(unittest.TestCase):
    """Verify project postprocessing without testing WASS algorithms."""

    def test_static_water_zero_test(self) -> None:
        static = make_grid(np.full((3, 2, 2), 1.25))
        reference = valid_temporal_mean(static)
        height = calculate_height(static, reference)
        np.testing.assert_array_equal(height.valid_mask, np.ones((3, 2, 2), dtype=bool))
        np.testing.assert_allclose(height.h, 0.0)

    def test_known_constant_height_test(self) -> None:
        static = make_grid(np.full((2, 2, 3), 0.8))
        dynamic = make_grid(np.full((2, 2, 3), 0.825))
        height = calculate_height(dynamic, valid_temporal_mean(static))
        np.testing.assert_allclose(height.h, 0.025)

    def test_positive_negative_height_sign_test(self) -> None:
        reference = valid_temporal_mean(make_grid(np.full((2, 1, 2), 2.0)))
        positive = calculate_height(make_grid(np.full((1, 1, 2), 2.1)), reference)
        negative = calculate_height(make_grid(np.full((1, 1, 2), 1.9)), reference)
        self.assertGreater(float(np.mean(positive.h)), 0.0)
        self.assertLess(float(np.mean(negative.h)), 0.0)

    def test_mask_nan_propagation_test(self) -> None:
        static_z = np.array([[[1.0, np.nan]], [[1.0, np.nan]]])
        static_mask = np.array([[[True, False]], [[True, False]]])
        reference = valid_temporal_mean(make_grid(static_z, valid_mask=static_mask))

        dynamic_z = np.array([[[np.nan, 1.2]], [[1.1, 1.2]]])
        dynamic_mask = np.array([[[False, True]], [[True, True]]])
        height = calculate_height(make_grid(dynamic_z, valid_mask=dynamic_mask), reference)

        expected_mask = np.array([[[False, False]], [[True, False]]])
        np.testing.assert_array_equal(height.valid_mask, expected_mask)
        self.assertTrue(np.isnan(height.h[0, 0, 0]))
        self.assertTrue(np.isnan(height.h[0, 0, 1]))
        self.assertAlmostEqual(height.h[1, 0, 0], 0.1)
        self.assertTrue(np.isnan(height.h[1, 0, 1]))

    def test_rmse_mae_test(self) -> None:
        calculated = HeightField(
            x=np.arange(4, dtype=float),
            y=np.array([0.0]),
            h=np.array([[[1.0, 2.0, np.nan, 4.0]]]),
            timestamp_ns=np.array([0], dtype=np.int64),
            valid_mask=np.array([[[True, True, False, True]]]),
            coordinate_system="world_water_surface",
            unit="m",
        )
        metrics = calculate_height_metrics(
            calculated,
            truth=np.array([[[0.0, 2.0, 3.0, 2.0]]]),
            truth_valid_mask=np.ones((1, 1, 4), dtype=bool),
            truth_unit="m",
            truth_coordinate_system="world_water_surface",
        )
        self.assertAlmostEqual(metrics.rmse, math.sqrt(5.0 / 3.0))
        self.assertAlmostEqual(metrics.mae, 1.0)
        self.assertAlmostEqual(metrics.maximum_absolute_error, 2.0)
        self.assertAlmostEqual(metrics.coverage, 0.75)
        self.assertAlmostEqual(metrics.hole_rate, 0.25)
        self.assertEqual(metrics.unit, "m")

    def test_coordinate_system_mismatch_test(self) -> None:
        reference = valid_temporal_mean(make_grid(np.ones((1, 1, 1))))
        dynamic = make_grid(np.ones((1, 1, 1)), coordinate_system="camera_left")
        with self.assertRaisesRegex(ValueError, "coordinate system mismatch"):
            calculate_height(dynamic, reference)

    def test_unit_mismatch_test(self) -> None:
        reference = valid_temporal_mean(make_grid(np.ones((1, 1, 1)), unit="m"))
        dynamic = make_grid(np.ones((1, 1, 1)), unit="mm")
        with self.assertRaisesRegex(ValueError, "unit mismatch"):
            calculate_height(dynamic, reference)

    def test_shape_mismatch_test(self) -> None:
        dynamic = make_grid(np.ones((1, 2, 2)))
        reference = StaticWaterReference(
            x=np.arange(3, dtype=float),
            y=np.arange(2, dtype=float),
            z0=np.ones((2, 3)),
            valid_mask=np.ones((2, 3), dtype=bool),
            sample_count=np.ones((2, 3), dtype=np.int64),
            coordinate_system="world_water_surface",
            unit="m",
        )
        with self.assertRaisesRegex(ValueError, "spatial shape mismatch"):
            calculate_height(dynamic, reference)

    def test_similarity_transform_test(self) -> None:
        transform = SimilarityTransform(
            scale=2.0,
            rotation=np.eye(3),
            translation=np.array([1.0, -1.0, 0.5]),
            source_coordinate_system="wass_normalized",
            target_coordinate_system="world_water_surface",
            source_unit="normalized",
            target_unit="m",
            source_axes=WORLD_AXES,
            target_axes=WORLD_AXES,
        )
        result = transform.apply(
            [[1.0, 2.0, 3.0]],
            coordinate_system="wass_normalized",
            unit="normalized",
            axis_directions=WORLD_AXES,
        )
        np.testing.assert_allclose(result, [[3.0, 3.0, 6.5]])

    def test_unknown_transform_metadata_fails_test(self) -> None:
        with self.assertRaisesRegex(ValueError, "source_unit must be explicitly known"):
            SimilarityTransform(
                scale=1.0,
                rotation=np.eye(3),
                translation=np.zeros(3),
                source_coordinate_system="wass",
                target_coordinate_system="world",
                source_unit="UNKNOWN",
                target_unit="m",
                source_axes=WORLD_AXES,
                target_axes=WORLD_AXES,
            )

    def test_all_invalid_metrics_fail_test(self) -> None:
        calculated = HeightField(
            x=np.array([0.0]),
            y=np.array([0.0]),
            h=np.array([[[np.nan]]]),
            timestamp_ns=np.array([0], dtype=np.int64),
            valid_mask=np.array([[[False]]]),
            coordinate_system="world_water_surface",
            unit="m",
        )
        with self.assertRaisesRegex(ValueError, "no valid samples"):
            calculate_height_metrics(
                calculated,
                truth=np.array([[[0.0]]]),
                truth_valid_mask=np.array([[[True]]]),
                truth_unit="m",
                truth_coordinate_system="world_water_surface",
            )


if __name__ == "__main__":
    unittest.main()
