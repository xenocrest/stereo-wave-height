"""Tests for image-only Phase 4 Case 2 candidate preparation."""

import ast
import unittest
from pathlib import Path

import numpy as np
import yaml

from src.validation.phase4_candidate_selection import (
    CandidatePreviewMetadata,
    image_change_scores,
    temporal_nonmaximum_candidates,
    validate_candidate_case_status,
)
from src.validation.single_frame_physical_validation import file_sha256


class Phase4CandidateSelectionTests(unittest.TestCase):
    def test_candidate_time_extraction_and_temporal_nms(self) -> None:
        times = np.array([0.0, 0.5, 1.0, 1.5, 2.0])
        scores = np.array([0.0, 9.0, 8.0, 7.0, 10.0])
        selected = temporal_nonmaximum_candidates(times, scores, count=2, minimum_separation_s=1.0)
        self.assertEqual([item.sample_time_s for item in selected], [0.5, 2.0])

    def test_image_scores_use_declared_reference_and_roi(self) -> None:
        frames = np.zeros((3, 4, 5), dtype=np.uint8)
        frames[1, 1:3, 1:4] = np.array([[0, 20, 40], [0, 20, 40]])
        scores = image_change_scores(frames, np.array([0.0, 1.0, 2.0]), reference_time_s=0.0, roi_xywh=(1, 1, 3, 2))
        self.assertEqual(scores[0], 0.0)
        self.assertGreater(scores[1], scores[0])

    def test_candidate_metadata_and_manual_stop_status(self) -> None:
        candidates = tuple(
            CandidatePreviewMetadata(
                f"candidate_{i:02d}", float(i), i, float(i), i, float(i), i, float(i),
                0.0, "SYNC_ACCEPTED_FOR_ON_DEMAND_MEASUREMENT", f"candidate_{i:02d}.png",
            ) for i in range(1, 6)
        )
        validate_candidate_case_status("PHASE4_CASE2_CANDIDATE_SELECTION_REQUIRED", candidates)
        self.assertEqual(candidates[0].to_dict()["actual_cam1_pts"], 1)

    def test_repository_case2_has_canonical_identity_and_case1_is_preserved(self) -> None:
        root = Path("experiments/real_video/HomeTank_004")
        case2 = yaml.safe_load((root / "phase4_case2_candidates.yaml").read_text(encoding="utf-8"))
        case1 = yaml.safe_load((root / "phase4_physical_validation.yaml").read_text(encoding="utf-8"))
        self.assertEqual(case2["status"], "PHASE4_CASE2_CANDIDATE_SELECTION_REQUIRED")
        self.assertEqual(len(case2["candidates"]), 6)
        self.assertTrue(all(item["canonical_rotation_deg"] == 0 for item in case2["candidates"]))
        self.assertTrue(all(item["sync_status"] == "SYNC_ACCEPTED_FOR_ON_DEMAND_MEASUREMENT" for item in case2["candidates"]))
        for item in case2["candidates"]:
            self.assertEqual(item["cam1_frame_identity"], f"pts_{item['actual_cam1_pts']}")
            self.assertEqual(file_sha256(root / item["preview"]), item["preview_sha256"])
        self.assertEqual(case1["comparison"]["absolute_error_mm"], 5.867183268293882)
        self.assertIn("REFERENCE_CHANGE_TOO_SMALL", case1["classification"])

    def test_candidate_selection_has_no_reconstruction_or_ruler_dependency(self) -> None:
        source = Path("src/validation/phase4_candidate_selection.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = " ".join(str(node.names) for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)))
        self.assertNotIn("reconstruction", imports)
        self.assertNotIn("ruler", imports.lower())
        self.assertNotIn("height_m", source)
        self.assertNotIn("xyz_m", source)


if __name__ == "__main__":
    unittest.main()
