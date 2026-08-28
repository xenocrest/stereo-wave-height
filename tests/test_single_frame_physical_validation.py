"""Tests for the frozen-result-only Phase 4 validation layer."""

import ast
import tempfile
import unittest
from pathlib import Path

import numpy as np
import yaml

from src.validation.single_frame_physical_validation import (
    FrozenObservedHeight,
    RulerScaleDirection,
    compare_frozen_single_frames,
    file_sha256,
    physical_error,
    query_local_observed_height,
    require_frozen_baseline,
    ruler_delta_m,
)


class SingleFramePhysicalValidationTests(unittest.TestCase):
    def test_ruler_delta_respects_explicit_sign(self) -> None:
        self.assertAlmostEqual(ruler_delta_m(100.0, 110.0, RulerScaleDirection.INCREASES_WITH_POSITIVE_HEIGHT), 0.01)
        self.assertAlmostEqual(ruler_delta_m(100.0, 110.0, RulerScaleDirection.DECREASES_WITH_POSITIVE_HEIGHT), -0.01)

    def test_nearest_observed_query_and_local_median(self) -> None:
        result = query_local_observed_height(
            np.array([10.0, 11.0, 12.0]), np.array([10.0, 10.0, 10.0]), np.array([0.001, 0.003, 0.100]),
            query_u_px=10.5, query_v_px=10.0, maximum_nearest_distance_px=1.0,
            neighborhood_radius_px=1.0, minimum_local_points=2,
        )
        self.assertAlmostEqual(result.nearest_distance_px, 0.5)
        self.assertAlmostEqual(result.local_median_height_m, 0.002)
        self.assertEqual(result.local_point_count, 2)
        self.assertTrue(result.support_sufficient)

    def test_distance_gate_and_insufficient_support_are_explicit(self) -> None:
        with self.assertRaisesRegex(LookupError, "NO_VALID_RECONSTRUCTION"):
            query_local_observed_height(
                np.array([0.0]), np.array([0.0]), np.array([0.0]), query_u_px=5.0, query_v_px=5.0,
                maximum_nearest_distance_px=1.0, neighborhood_radius_px=1.0, minimum_local_points=1,
            )
        result = query_local_observed_height(
            np.array([0.0]), np.array([0.0]), np.array([0.0]), query_u_px=0.0, query_v_px=0.0,
            maximum_nearest_distance_px=1.0, neighborhood_radius_px=1.0, minimum_local_points=2,
        )
        self.assertFalse(result.support_sufficient)

    def test_absolute_and_near_zero_relative_error(self) -> None:
        result = physical_error(0.012, 0.010, relative_error_minimum_reference_m=0.0001)
        self.assertAlmostEqual(result.absolute_error_m, 0.002)
        self.assertAlmostEqual(result.relative_error_percent, 20.0)
        near_zero = physical_error(0.001, 0.0, relative_error_minimum_reference_m=0.0001)
        self.assertIsNone(near_zero.relative_error_percent)

    def test_baseline_identity_requires_freeze_and_sources(self) -> None:
        complete = {
            "FROZEN_FOR_INDEPENDENT_VALIDATION": True, "frozen_source_commit": "abc",
            "static": {}, "wave": {}, "sync_policy": {}, "calibration": {},
        }
        for field in ("static", "wave", "sync_policy", "calibration"):
            complete[field] = {"identifier": field}
        require_frozen_baseline(complete)
        complete["FROZEN_FOR_INDEPENDENT_VALIDATION"] = False
        with self.assertRaises(ValueError):
            require_frozen_baseline(complete)

    def test_file_identity_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "frozen.bin"
            path.write_bytes(b"frozen")
            self.assertEqual(file_sha256(path), "FFB304816A1090313E833215C08DAE3D209CFAD1FFD1F674F0909A2AE99E1394")

    def test_validation_module_has_no_reconstruction_or_ruler_back_dependency(self) -> None:
        validation_source = Path("src/validation/single_frame_physical_validation.py").read_text(encoding="utf-8")
        imports = [node for node in ast.walk(ast.parse(validation_source)) if isinstance(node, (ast.Import, ast.ImportFrom))]
        imported = " ".join(str(node.names) for node in imports)
        self.assertNotIn("src.reconstruction.pipeline", imported)
        for source in Path("src/reconstruction").glob("*.py"):
            self.assertNotIn("ruler_validation", source.read_text(encoding="utf-8"))

    def test_known_ruler_values_and_user_pixels_are_not_replaced_with_zero(self) -> None:
        text = Path("experiments/real_video/HomeTank_004/ruler_measurement.yaml").read_text(encoding="utf-8")
        self.assertIn("ruler_value_mm: 9.1", text)
        self.assertIn("ruler_value_mm: 9.2", text)
        self.assertIn("waterline_pixel: {u_px: 798, v_px: 414}", text)
        self.assertIn("waterline_pixel: {u_px: 800, v_px: 414}", text)
        self.assertNotIn("waterline_pixel: {u_px: 0", text)

    def test_complete_comparison_uses_wave_local_height_not_static_or_global_mean(self) -> None:
        static = FrozenObservedHeight(np.array([1.0]), np.array([1.0]), np.array([0.0]), "rectified_cam0")
        wave = FrozenObservedHeight(np.array([2.0, 2.2]), np.array([2.0, 2.0]), np.array([0.009, 0.011]), "rectified_cam0")
        result = compare_frozen_single_frames(
            static, wave, static_value_mm=100.0, wave_value_mm=110.0,
            direction=RulerScaleDirection.INCREASES_WITH_POSITIVE_HEIGHT,
            static_pixel=(1.0, 1.0), wave_pixel=(2.1, 2.0), maximum_nearest_distance_px=0.5,
            neighborhood_radius_px=0.5, minimum_local_points=1,
            relative_error_minimum_reference_m=0.001,
        )
        self.assertAlmostEqual(result.stereo_local_height_m, 0.010)
        self.assertAlmostEqual(result.error.absolute_error_m, 0.0)

    def test_comparison_subtracts_nonzero_static_local_height(self) -> None:
        static = FrozenObservedHeight(np.array([1.0]), np.array([1.0]), np.array([0.002]), "rectified_cam0")
        wave = FrozenObservedHeight(np.array([2.0]), np.array([2.0]), np.array([0.009]), "rectified_cam0")
        result = compare_frozen_single_frames(
            static, wave, static_value_mm=10.0, wave_value_mm=17.0,
            direction=RulerScaleDirection.INCREASES_WITH_POSITIVE_HEIGHT,
            static_pixel=(1.0, 1.0), wave_pixel=(2.0, 2.0), maximum_nearest_distance_px=0.1,
            neighborhood_radius_px=0.1, minimum_local_points=1,
            relative_error_minimum_reference_m=0.001,
        )
        self.assertAlmostEqual(result.stereo_local_height_m, 0.007)
        self.assertAlmostEqual(result.error.absolute_error_m, 0.0)

    def test_phase4_confirmed_inputs_and_result_are_frozen_and_not_optimized(self) -> None:
        root = Path("experiments/real_video/HomeTank_004")
        points = yaml.safe_load((root / "manual_reference/manual_reference_points.yaml").read_text(encoding="utf-8"))
        result = yaml.safe_load((root / "phase4_physical_validation.yaml").read_text(encoding="utf-8"))
        self.assertEqual(points["static"]["clicked_pixel_canonical"], {"u_px": 798, "v_px": 414})
        self.assertEqual(points["wave"]["clicked_pixel_canonical"], {"u_px": 800, "v_px": 414})
        self.assertEqual(points["static"]["pixel_uncertainty_px"], 1.0)
        self.assertTrue(points["static"]["confirmed_by_user"])
        self.assertEqual(result["query_policy"]["nearest_distance_gate_px"], 2.0)
        self.assertEqual(result["query_policy"]["neighborhood_radius_px"], 3.0)
        self.assertFalse(result["query_policy"]["selection_used_height_values"])
        self.assertEqual(result["static"]["local"]["point_count"], 126)
        self.assertEqual(result["wave"]["local"]["point_count"], 30)
        self.assertAlmostEqual(result["comparison"]["ruler_delta_mm"], 0.1)
        self.assertAlmostEqual(result["comparison"]["stereo_delta_mm"], -5.767183268293882)
        self.assertAlmostEqual(result["comparison"]["absolute_error_mm"], 5.867183268293882)
        self.assertIsNone(result["comparison"]["relative_error_percent"])
        self.assertFalse(result["boundaries"]["ruler_used_in_reconstruction"])
        self.assertFalse(result["boundaries"]["clicks_optimized_against_result"])

    def test_phase4_frozen_height_hashes_match_files(self) -> None:
        root = Path(r"D:\stereo-wave-height-runs\HomeTank_004\sync-tolerance-formal-r0-20260826")
        if not root.exists():
            self.skipTest("external frozen R0 artifacts are not present")
        expected = {
            "static": "B57113FE200ED593C95AE8BEEE7E7016CF13F595268FFD4F911EFB70B046FF9D",
            "wave": "BD99D0CD2B45C1E56753ECA3DF6DA1A7E2676944D86A829F098DBA8E83BC7E10",
        }
        for label, digest in expected.items():
            path = root / label / "reconstruction/height/000000_height_points.npz"
            self.assertEqual(file_sha256(path), digest)

    def test_coordinate_system_mismatch_is_rejected(self) -> None:
        static = FrozenObservedHeight(np.array([0.0]), np.array([0.0]), np.array([0.0]), "cam0")
        wave = FrozenObservedHeight(np.array([0.0]), np.array([0.0]), np.array([0.0]), "cam1")
        with self.assertRaises(ValueError):
            compare_frozen_single_frames(
                static, wave, static_value_mm=0.0, wave_value_mm=1.0,
                direction=RulerScaleDirection.INCREASES_WITH_POSITIVE_HEIGHT,
                static_pixel=(0.0, 0.0), wave_pixel=(0.0, 0.0), maximum_nearest_distance_px=1.0,
                neighborhood_radius_px=1.0, minimum_local_points=1,
                relative_error_minimum_reference_m=0.001,
            )


if __name__ == "__main__":
    unittest.main()
