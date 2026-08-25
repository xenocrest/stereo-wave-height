"""Tests for robust light-event synchronization analysis."""

import unittest

import numpy as np

from src.synchronization.video_sync import BrightnessEvent, detect_brightness_events, estimate_event_offset


class VideoSyncTests(unittest.TestCase):
    def test_brightness_steps_are_detected_with_polarity(self) -> None:
        time = np.arange(20, dtype=float) * 0.1
        signal = np.r_[np.zeros(5), np.ones(8) * 20, np.zeros(7)]
        events = detect_brightness_events(time, signal, minimum_change=5.0, minimum_separation_s=0.2)
        self.assertEqual(len(events), 2)
        self.assertGreater(events[0].signed_change, 0)
        self.assertLess(events[1].signed_change, 0)

    def test_right_minus_left_offset_is_recovered(self) -> None:
        left = tuple(BrightnessEvent(t, sign) for t, sign in [(1.0, 10), (3.0, -10), (5.0, 10)])
        right = tuple(BrightnessEvent(t, sign) for t, sign in [(1.2, 9), (3.2, -9), (5.2, 9)])
        result = estimate_event_offset(left, right, match_tolerance_s=0.05)
        self.assertEqual(result.status, "SYNC_ESTABLISHED_BY_LIGHT_EVENTS")
        self.assertEqual(result.confidence, "HIGH")
        self.assertAlmostEqual(result.estimated_offset_s, 0.2)

    def test_single_or_inconsistent_event_does_not_establish_sync(self) -> None:
        result = estimate_event_offset((BrightnessEvent(1.0, 10),), (BrightnessEvent(1.1, 10),))
        self.assertEqual(result.status, "SYNC_NOT_ESTABLISHED")
        self.assertIsNone(result.estimated_offset_s)


if __name__ == "__main__":
    unittest.main()
