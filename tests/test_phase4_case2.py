"""Tests for the frozen candidate_02 Phase 4 baseline."""

import unittest
from pathlib import Path

import yaml

from src.validation.phase4_case2 import (
    file_sha256,
    require_candidate_02_identity,
    validate_case2_baseline,
)


ROOT = Path("experiments/real_video/HomeTank_004")


class Phase4Case2Tests(unittest.TestCase):
    def test_candidate_02_identity_binding_and_replacement_rejected(self) -> None:
        candidates = yaml.safe_load((ROOT / "phase4_case2_candidates.yaml").read_text(encoding="utf-8"))
        candidate = next(item for item in candidates["candidates"] if item["id"] == "candidate_02")
        pair = {
            "requested_time_s": 29.4654055,
            "left_frame_id": "pts_2651866",
            "right_frame_id": "pts_2646070",
            "pair_residual_s": 0.0010055,
        }
        require_candidate_02_identity(candidate, pair)
        wrong = dict(candidate, id="candidate_03")
        with self.assertRaisesRegex(ValueError, "CASE2_CANDIDATE_IDENTITY_MISMATCH"):
            require_candidate_02_identity(wrong, pair)

    def test_repository_baseline_reuses_static_and_freezes_hashes(self) -> None:
        baseline = yaml.safe_load((ROOT / "phase4_validation_case2_baseline.yaml").read_text(encoding="utf-8"))
        validate_case2_baseline(baseline)
        self.assertEqual(
            baseline["static"]["height_array_sha256"],
            yaml.safe_load((ROOT / "phase4_validation_baseline.yaml").read_text(encoding="utf-8"))["static"]["height_array_sha256"],
        )
        reference = ROOT / "phase4_case2_manual_reference" / "wave_case2_cam1_canonical_reference.png"
        self.assertEqual(file_sha256(reference), baseline["wave"]["array_hashes"]["canonical_cam1_png_sha256"])
        self.assertNotEqual(
            baseline["wave"]["array_hashes"]["canonical_cam1_png_sha256"],
            yaml.safe_load((ROOT / "phase4_case2_candidates.yaml").read_text(encoding="utf-8"))["candidates"][1]["preview_sha256"],
        )

    def test_case2_manual_reference_is_null_and_case1_unchanged(self) -> None:
        manual = yaml.safe_load((ROOT / "phase4_case2_ruler_measurement.yaml").read_text(encoding="utf-8"))
        self.assertEqual(manual["static"]["ruler_value_mm"], 9.1)
        self.assertEqual(manual["static"]["clicked_pixel_canonical"], {"u_px": 798, "v_px": 414})
        self.assertIsNone(manual["wave_case2"]["ruler_value_mm"])
        self.assertIsNone(manual["wave_case2"]["ruler_uncertainty_mm"])
        self.assertIsNone(manual["wave_case2"]["clicked_pixel_canonical"])
        self.assertIsNone(manual["wave_case2"]["pixel_uncertainty_px"])
        self.assertFalse(manual["wave_case2"]["confirmed_by_user"])
        case1 = yaml.safe_load((ROOT / "phase4_physical_validation.yaml").read_text(encoding="utf-8"))
        self.assertEqual(case1["comparison"]["absolute_error_mm"], 5.867183268293882)
        self.assertIn("REFERENCE_CHANGE_TOO_SMALL", case1["classification"])

    def test_manual_reference_is_downstream_only(self) -> None:
        for source in Path("src/reconstruction").glob("*.py"):
            text = source.read_text(encoding="utf-8")
            self.assertNotIn("phase4_case2_ruler_measurement", text)
            self.assertNotIn("wave_case2", text)


if __name__ == "__main__":
    unittest.main()
