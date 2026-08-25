"""Tests for non-destructive long-duration WASS capacity planning."""

import unittest

from src.reconstruction.long_duration import estimate_capacity, plan_frame_batches


class LongDurationTests(unittest.TestCase):
    def test_capacity_block_does_not_reduce_requested_frames(self) -> None:
        result = estimate_capacity(
            frame_count=100, measured_seconds_per_frame=2.0,
            measured_bytes_per_frame=10.0, available_storage_bytes=999,
        )
        self.assertEqual(result.frame_count, 100)
        self.assertEqual(result.estimated_runtime_s, 200.0)
        self.assertEqual(result.estimated_storage_bytes, 1000)
        self.assertEqual(result.status, "BLOCKED_INSUFFICIENT_STORAGE")

    def test_batches_are_gap_free_and_resumable(self) -> None:
        batches = plan_frame_batches(10, batch_size=4)
        self.assertEqual([(item.start_index, item.stop_index) for item in batches], [(0, 4), (4, 8), (8, 10)])
        covered = [index for item in batches for index in range(item.start_index, item.stop_index)]
        self.assertEqual(covered, list(range(10)))

    def test_invalid_capacity_inputs_fail(self) -> None:
        with self.assertRaises(ValueError):
            estimate_capacity(frame_count=0, measured_seconds_per_frame=1, measured_bytes_per_frame=1, available_storage_bytes=1)
        with self.assertRaises(ValueError):
            plan_frame_batches(10, batch_size=0)


if __name__ == "__main__":
    unittest.main()
