"""Tests for the camera-independent ruler validation core."""

import unittest

import numpy as np

from src.validation.ruler_validation import (
    DriftClassification,
    classify_drift_source,
    signed_plane_height,
    validate_ruler_scale,
    validate_water_height,
    validation_error_metrics,
)


class RulerValidationTests(unittest.TestCase):
    def test_metric_scale_uses_3d_euclidean_distance(self) -> None:
        result = validate_ruler_scale(np.zeros(3), np.array([0.0, 0.03, 0.04]), 0.05)
        self.assertAlmostEqual(result.reconstructed_length_m, 0.05)
        self.assertAlmostEqual(result.relative_error, 0.0)

    def test_height_uses_plane_normal_not_camera_z(self) -> None:
        height = signed_plane_height(
            np.array([2.0, 0.0, 7.0]), np.array([1.0, 0.0, 1.0]), np.array([2.0, 0.0, 0.0])
        )
        self.assertAlmostEqual(height, 1.0)
        result = validate_water_height(0.009, 0.010)
        self.assertAlmostEqual(result.signed_error_m, 0.001)

    def test_incomplete_reference_never_guesses_classification(self) -> None:
        result = classify_drift_source(
            reference_complete=False,
            ruler_position_drift_m=None,
            ruler_relative_length_change=None,
            surface_anomaly_m=None,
            position_threshold_m=0.001,
            scale_threshold=0.01,
            surface_threshold_m=0.001,
        )
        self.assertEqual(result, DriftClassification.INCOMPLETE_REFERENCE)

    def test_three_documented_failure_classes(self) -> None:
        common = dict(reference_complete=True, position_threshold_m=0.01, scale_threshold=0.02, surface_threshold_m=0.01)
        self.assertEqual(
            classify_drift_source(ruler_position_drift_m=0.02, ruler_relative_length_change=0.0, surface_anomaly_m=0.0, **common),
            DriftClassification.GLOBAL_RECONSTRUCTION_DRIFT,
        )
        self.assertEqual(
            classify_drift_source(ruler_position_drift_m=0.0, ruler_relative_length_change=0.03, surface_anomaly_m=0.0, **common),
            DriftClassification.GEOMETRIC_SCALE_ERROR,
        )
        self.assertEqual(
            classify_drift_source(ruler_position_drift_m=0.0, ruler_relative_length_change=0.0, surface_anomaly_m=0.02, **common),
            DriftClassification.SURFACE_MATCHING_INSTABILITY,
        )

    def test_unknown_or_degenerate_inputs_fail(self) -> None:
        with self.assertRaises(ValueError):
            validate_ruler_scale(np.zeros(3), np.ones(3), 0.0)
        with self.assertRaises(ValueError):
            signed_plane_height(np.zeros(3), np.zeros(3), np.zeros(3))

    def test_independent_reference_error_metrics(self) -> None:
        result = validation_error_metrics(np.array([0.0, 0.02]), np.array([0.0, 0.01]))
        self.assertEqual(result.count, 2)
        self.assertAlmostEqual(result.rmse_m, np.sqrt(0.00005))
        self.assertAlmostEqual(result.mae_m, 0.005)
        self.assertAlmostEqual(result.maximum_absolute_error_m, 0.01)
        self.assertAlmostEqual(result.mean_bias_m, 0.005)


if __name__ == "__main__":
    unittest.main()
