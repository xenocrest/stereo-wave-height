"""Tests for the general stereo-system engineering design models."""

import math
import unittest

from src.stereo_analysis import (
    analyze_disparity_design,
    depth_from_disparity,
    depth_resolution,
    expected_disparity,
)


class StereoAnalysisTests(unittest.TestCase):
    def test_disparity_depth_round_trip(self) -> None:
        disparity = expected_disparity(0.25, 3000.0, 2.0)
        self.assertAlmostEqual(disparity, 375.0)
        self.assertAlmostEqual(depth_from_disparity(0.25, 3000.0, disparity), 2.0)

    def test_depth_range_maps_to_reversed_disparity_bounds(self) -> None:
        result = analyze_disparity_design(
            0.25, 3000.0, 2.0, depth_range_m=(1.5, 2.5)
        )
        self.assertEqual(result.depth_range_m, (1.5, 2.5))
        self.assertEqual(result.disparity_range_px, (300.0, 500.0))
        self.assertEqual(result.recommended_disparity_center_px, 400.0)

    def test_single_distance_has_degenerate_design_range(self) -> None:
        result = analyze_disparity_design(0.0686847, 3255.98, 0.4)
        self.assertAlmostEqual(result.expected_disparity_px, 559.090023765)
        self.assertEqual(result.depth_range_m, (0.4, 0.4))
        self.assertAlmostEqual(
            result.recommended_disparity_center_px, result.expected_disparity_px
        )

    def test_industrial_example_depth_resolution(self) -> None:
        result = depth_resolution(0.25, 3000.0, 2.0, 0.1)
        self.assertAlmostEqual(result.depth_sensitivity_m_per_px, 4.0 / 750.0)
        self.assertAlmostEqual(result.depth_error_m, 0.0005333333333333334)
        self.assertAlmostEqual(result.depth_error_mm, 0.5333333333333333)

    def test_zero_disparity_uncertainty_is_explicitly_supported(self) -> None:
        self.assertEqual(depth_resolution(0.25, 3000.0, 2.0, 0.0).depth_error_m, 0.0)

    def test_invalid_or_unknown_units_are_not_silently_corrected(self) -> None:
        invalid = (0.0, -1.0, math.inf, math.nan)
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    expected_disparity(value, 3000.0, 2.0)
        with self.assertRaises(ValueError):
            analyze_disparity_design(0.25, 3000.0, 2.0, depth_range_m=(2.5, 1.5))
        with self.assertRaises(ValueError):
            depth_resolution(0.25, 3000.0, 2.0, -0.1)


if __name__ == "__main__":
    unittest.main()
