"""Tests for read-only single-frame height QA."""

import json
from pathlib import Path
import unittest
import yaml

import numpy as np

from src.validation.single_frame_height_qa import (
    abnormal_connected_components,
    audit_single_frame_height,
    height_distribution_statistics,
    rasterize_sparse_support,
    sparse_height_raster,
    support_edge_distances,
    tail_fraction_statistics,
)


class SingleFrameHeightQATests(unittest.TestCase):
    def test_percentiles_raw_and_robust_ranges(self) -> None:
        values = np.array([-0.1, -0.002, 0.0, 0.002, 0.1])
        result = height_distribution_statistics(values)
        self.assertEqual(result["raw_height_range_mm"], {"min": -100.0, "max": 100.0})
        self.assertGreater(result["robust_height_range_p1_p99_mm"]["low"], -100)
        self.assertLess(result["robust_height_range_p1_p99_mm"]["high"], 100)
        self.assertIn("p99.9_m", result["percentiles"])

    def test_tail_fraction_uses_explicit_center(self) -> None:
        result = tail_fraction_statistics([0.010, 0.011, 0.030], (5, 10), center_m=0.010)
        self.assertEqual(result["gt_5_mm"]["count"], 1)
        self.assertEqual(result["gt_10_mm"]["count"], 1)

    def test_unsupported_pixels_remain_nan(self) -> None:
        raster = sparse_height_raster([1, 3], [1, 1], [0.1, 0.2], (4, 5))
        self.assertTrue(np.isnan(raster[0, 0]))
        self.assertFalse(np.any(raster[np.isnan(raster)] == 0))
        self.assertEqual(np.count_nonzero(np.isfinite(raster)), 2)

    def test_support_edge_distance_and_abnormal_grouping(self) -> None:
        u = np.array([1, 2, 3, 2, 2, 8])
        v = np.array([2, 2, 2, 1, 3, 8])
        support, x, y = rasterize_sparse_support(u, v, (10, 10))
        distance = support_edge_distances(support, x, y)
        self.assertGreater(distance[1], distance[0])
        grouping = abnormal_connected_components(x, y, [1, 1, 0, 0, 0, 1], (10, 10))
        self.assertEqual(grouping.component_count, 2)
        self.assertEqual(grouping.largest_component_pixels, 2)
        self.assertEqual(grouping.singleton_component_count, 1)

    def test_coordinate_convention_preserved_and_result_serializes(self) -> None:
        result = audit_single_frame_height(
            xyz_m=np.array([[0, 0, 1], [1, 0, 1], [2, 0, 1]], float),
            u_px=[1, 2, 3], v_px=[1, 1, 1], height_m=[0, 0.001, 0.02],
            pixel_coordinate_system="wass_rectified_computational_cam0__input_left",
            image_shape=(5, 5), condition="static",
        )
        self.assertEqual(result.pixel_coordinate_system, "wass_rectified_computational_cam0__input_left")
        json.dumps(result.to_dict())

    def test_audit_module_has_no_ruler_dependency(self) -> None:
        source = Path(__file__).resolve().parents[1] / "src" / "validation" / "single_frame_height_qa.py"
        text = source.read_text(encoding="utf-8").lower()
        self.assertNotIn("ruler_validation", text)
        self.assertNotIn("ruler_reference", text)

    def test_frozen_validation_baseline_serialization(self) -> None:
        path = Path(__file__).resolve().parents[1] / "experiments" / "real_video" / "HomeTank_004" / "phase4_validation_baseline.yaml"
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.assertTrue(payload["FROZEN_FOR_INDEPENDENT_VALIDATION"])
        self.assertFalse(payload["validation_boundary"]["ruler_data_used_to_create_baseline"])
        self.assertEqual(payload["validation_boundary"]["physical_accuracy"], "PHYSICAL_ACCURACY_NOT_ESTABLISHED")


if __name__ == "__main__":
    unittest.main()
