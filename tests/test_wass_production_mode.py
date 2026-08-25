"""Tests for production-mode planning without running or modifying WASS."""

import unittest

from src.performance.production_mode import (
    CONFIRMED_WASS_ROI_CAPABILITY,
    PixelRoi,
    merge_wave_results,
    production_retention,
    resumable_batches,
)


class WassProductionModeTests(unittest.TestCase):
    def test_roi_is_explicit_and_match_reduction_is_not_claimed(self) -> None:
        self.assertEqual(PixelRoi(10, 20, 100, 50).width, 100)
        self.assertFalse(CONFIRMED_WASS_ROI_CAPABILITY.pre_match_reduction_supported)
        with self.assertRaises(ValueError):
            PixelRoi(-1, 0, 10, 10)

    def test_production_retention_keeps_measurement_and_marks_diagnostics(self) -> None:
        self.assertEqual(production_retention("height/000001_height_points.npz"), "RETAIN")
        self.assertEqual(production_retention("pixel_xyz/000001_pixel_xyz.npz"), "RETAIN")
        self.assertEqual(production_retention("pointcloud/000001.xyz"), "RETAIN")
        self.assertEqual(production_retention("pointcloud/000001.ply"), "PRUNE_AFTER_VERIFIED_CHECKPOINT")
        self.assertEqual(production_retention("wass_workspace/work/000001_wd/stereo.jpg"), "PRUNE_AFTER_VERIFIED_CHECKPOINT")
        with self.assertRaises(ValueError):
            production_retention("videos/wave.mp4")

    def test_batches_resume_without_gaps(self) -> None:
        batches = resumable_batches(1001, 500, completed_batch_ids=(0,))
        self.assertEqual([(item.start_index, item.stop_index) for item in batches], [(0, 500), (500, 1000), (1000, 1001)])
        self.assertEqual([item.status for item in batches], ["COMPLETE", "PENDING", "PENDING"])
        subset = resumable_batches(2000, 500, frame_start=500, frame_stop_exclusive=1501)
        self.assertEqual([(item.start_index, item.stop_index) for item in subset], [(500, 1000), (1000, 1500), (1500, 1501)])

    def test_batch_results_merge_by_timestamp_and_reject_duplicates(self) -> None:
        first = {"height_series": [{"frame_id": "000001", "timestamp_ns": 20, "mean_H": 1.0}]}
        second = {"height_series": [{"frame_id": "000000", "timestamp_ns": 10, "mean_H": 2.0}]}
        merged = merge_wave_results((first, second))
        self.assertEqual([item["frame_id"] for item in merged["height_series"]], ["000000", "000001"])
        with self.assertRaises(ValueError):
            merge_wave_results((first, first))


if __name__ == "__main__":
    unittest.main()
