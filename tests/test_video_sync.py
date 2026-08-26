"""Tests for robust light-event synchronization analysis."""

import unittest
from unittest.mock import patch
import subprocess

import numpy as np

from src.synchronization.video_sync import (
    BrightnessEvent,
    EventPair,
    FrameBrightnessSeries,
    RefinedBrightnessEvent,
    detect_brightness_events,
    detect_frame_level_light_events,
    estimate_event_offset,
    extract_frame_brightness_pts,
    fit_frame_level_sync_model,
    pair_frame_level_events,
    synchronization_residual_statistics,
)


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

    @patch("src.synchronization.video_sync.subprocess.run")
    def test_full_pts_brightness_extraction_uses_decoded_metadata(self, run) -> None:
        run.return_value = subprocess.CompletedProcess(
            [], 0,
            "frame:0 pts:100 pts_time:1.000\nlavfi.signalstats.YAVG=10.5\n"
            "frame:1 pts:102 pts_time:1.017\nlavfi.signalstats.YAVG=12.5\n",
            "",
        )
        result = extract_frame_brightness_pts("input.mp4", ffmpeg_executable="ffmpeg")
        np.testing.assert_array_equal(result.pts, [100, 102])
        np.testing.assert_allclose(result.timestamps_s, [1.0, 1.017])
        np.testing.assert_allclose(result.brightness, [10.5, 12.5])
        self.assertNotIn("fps=", " ".join(run.call_args.args[0]))

    def test_frame_level_event_detection_and_pairing(self) -> None:
        timestamps = np.arange(80, dtype=float) * 0.01
        signal = np.r_[np.zeros(20), np.ones(30) * 20, np.zeros(30)]
        series = FrameBrightnessSeries(np.arange(80), timestamps, signal)
        events = detect_frame_level_light_events(series, minimum_change=3, minimum_separation_s=0.1)
        self.assertEqual([event.polarity for event in events], [1, -1])
        shifted = tuple(
            RefinedBrightnessEvent(event.time_s + 0.03, event.polarity, event.local_amplitude, "HIGH", event.refinement)
            for event in events
        )
        pairs = pair_frame_level_events(events, shifted, coarse_offset_s=0.03, tolerance_s=0.01)
        self.assertEqual(len(pairs), 2)

    def test_offset_and_affine_model_selection_and_residual_statistics(self) -> None:
        def event(time: float) -> RefinedBrightnessEvent:
            return RefinedBrightnessEvent(time, 1, 10, "HIGH", "LINEAR_HALF_LEVEL_CROSSING")
        offset_pairs = tuple(EventPair(event(t), event(t + 0.02 + noise)) for t, noise in [(1, 0), (2, .001), (3, -.001)])
        offset = fit_frame_level_sync_model(offset_pairs, frame_period_s=0.02)
        self.assertEqual(offset.model_type, "OFFSET_ONLY")
        affine_pairs = tuple(EventPair(event(t), event(1.002 * t + 0.01)) for t in (1, 5, 10, 20))
        affine = fit_frame_level_sync_model(affine_pairs, frame_period_s=0.02)
        self.assertEqual(affine.model_type, "AFFINE")
        self.assertAlmostEqual(affine.scale, 1.002)
        stats = synchronization_residual_statistics(np.array([-0.001, 0.0, 0.001]))
        self.assertAlmostEqual(stats["max_absolute_s"], 0.001)

    def test_static_and_wave_models_are_independent(self) -> None:
        def event(time: float, polarity: int) -> RefinedBrightnessEvent:
            return RefinedBrightnessEvent(time, polarity, 10, "HIGH", "LINEAR_HALF_LEVEL_CROSSING")
        static = tuple(EventPair(event(t, 1), event(t + .02, 1)) for t in (1, 2, 3))
        wave = tuple(EventPair(event(t, 1), event(t - .06, 1)) for t in (1, 2, 3))
        self.assertAlmostEqual(fit_frame_level_sync_model(static, frame_period_s=.02).offset_s, .02)
        self.assertAlmostEqual(fit_frame_level_sync_model(wave, frame_period_s=.02).offset_s, -.06)


if __name__ == "__main__":
    unittest.main()
