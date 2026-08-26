"""Tests for evidence-derived on-demand synchronization tolerance."""

import json
import unittest

from src.synchronization.affine import AffineTimeMapping
from src.synchronization.frame_selection import VideoFrameTimestamp
from src.synchronization.tolerance import (
    OnDemandSyncTolerancePolicy,
    generate_frame_offset_candidates,
    select_formal_candidate,
)


class SyncToleranceTests(unittest.TestCase):
    def test_candidate_generation_uses_actual_pts_residual_and_period(self) -> None:
        frames = tuple(
            VideoFrameTimestamp(index, timestamp)
            for index, timestamp in enumerate((0.96, 0.977, 0.994, 1.012, 1.029, 1.047, 1.064))
        )
        candidates = generate_frame_offset_candidates(
            frames, actual_left_time_s=1.0,
            mapping=AffineTimeMapping(1.0, 0.01, 3, 0.001, 0.002),
            offsets=(-2, -1, 0, 1, 2),
        )
        self.assertEqual([item.offset_frames for item in candidates], [-2, -1, 0, 1, 2])
        self.assertEqual(select_formal_candidate(candidates).frame.timestamp_s, 1.012)
        self.assertAlmostEqual(select_formal_candidate(candidates).residual_s, 0.002)
        self.assertAlmostEqual(select_formal_candidate(candidates).local_frame_period_s, 0.017)
        self.assertAlmostEqual(select_formal_candidate(candidates).normalized_residual, 0.002 / 0.017)

    def test_policy_serialization_and_three_way_gate(self) -> None:
        policy = OnDemandSyncTolerancePolicy(
            "ON_DEMAND_SYNC_TOLERANCE_ESTABLISHED", 0, 1, "controlled evidence"
        )
        self.assertEqual(policy.classify(0), "ACCEPTED")
        self.assertEqual(policy.classify(-1), "WARNING")
        self.assertEqual(policy.classify(2), "REJECTED")
        self.assertEqual(json.loads(json.dumps(policy.to_dict()))["strict_max_abs_frames"], 0)

    def test_formal_selection_cannot_choose_best_reconstruction(self) -> None:
        frames = tuple(VideoFrameTimestamp(index, 1.0 + index * 0.01) for index in range(7))
        candidates = generate_frame_offset_candidates(
            frames, actual_left_time_s=1.03,
            mapping=AffineTimeMapping(1.0, 0.0, 3, 0.0, 0.0),
        )
        fake_quality = {candidate.offset_frames: 999 if candidate.offset_frames == 2 else 1 for candidate in candidates}
        self.assertEqual(max(fake_quality, key=fake_quality.get), 2)
        self.assertEqual(select_formal_candidate(candidates).offset_frames, 0)

    def test_unestablished_policy_always_rejects(self) -> None:
        policy = OnDemandSyncTolerancePolicy(
            "ON_DEMAND_SYNC_TOLERANCE_NOT_ESTABLISHED", None, None, "insufficient evidence"
        )
        self.assertEqual(policy.classify(0), "REJECTED")


if __name__ == "__main__":
    unittest.main()
