"""Tests for the frozen candidate_02 Phase 4 baseline."""

import unittest
from pathlib import Path
import importlib.util

import numpy as np

import yaml

from src.validation.phase4_case2 import (
    file_sha256,
    require_candidate_02_identity,
    validate_case2_baseline,
)
from src.validation.manual_reference import canonical_cam1_to_rectified, canonical_rectified_roundtrip_error


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

    def test_case2_manual_reference_and_case1_unchanged(self) -> None:
        manual = yaml.safe_load((ROOT / "phase4_case2_ruler_measurement.yaml").read_text(encoding="utf-8"))
        self.assertEqual(manual["static"]["ruler_value_mm"], 9.1)
        self.assertEqual(manual["static"]["clicked_pixel_canonical"], {"u_px": 798, "v_px": 414})
        self.assertEqual(manual["wave_case2"]["ruler_value_mm"], 9.6)
        self.assertEqual(manual["wave_case2"]["ruler_uncertainty_mm"], 1.0)
        self.assertEqual(manual["wave_case2"]["clicked_pixel_canonical"], {"u_px": 799, "v_px": 396})
        self.assertEqual(manual["wave_case2"]["pixel_uncertainty_px"], 1.0)
        self.assertTrue(manual["wave_case2"]["confirmed_by_user"])
        case1 = yaml.safe_load((ROOT / "phase4_physical_validation.yaml").read_text(encoding="utf-8"))
        self.assertEqual(case1["comparison"]["absolute_error_mm"], 5.867183268293882)
        self.assertIn("REFERENCE_CHANGE_TOO_SMALL", case1["classification"])

    def test_manual_reference_is_downstream_only(self) -> None:
        for source in Path("src/reconstruction").glob("*.py"):
            text = source.read_text(encoding="utf-8")
            self.assertNotIn("phase4_case2_ruler_measurement", text)
            self.assertNotIn("wave_case2", text)

    def test_case2_gate_failure_preserves_query_policy_and_suppresses_error(self) -> None:
        result = yaml.safe_load((ROOT / "phase4_case2_physical_validation.yaml").read_text(encoding="utf-8"))
        self.assertEqual(result["classification"], "CASE2_PIXEL_XYZ_DISTANCE_GATE_FAIL")
        self.assertEqual(result["query_policy"]["nearest_distance_gate_px"], 2.0)
        self.assertEqual(result["query_policy"]["neighborhood_radius_px"], 3.0)
        self.assertFalse(result["query_policy"]["interpolation_used"])
        self.assertGreater(result["wave_case2"]["nearest_diagnostic"]["distance_px"], 2.0)
        self.assertEqual(result["wave_case2"]["local"]["point_count_within_3px"], 0)
        self.assertEqual(result["wave_case2"]["pixel_sensitivity_3x3"]["passed_distance_gate"], 0)
        self.assertAlmostEqual(result["reference_comparison"]["ruler_delta_mm"], 0.5)
        self.assertAlmostEqual(result["reference_comparison"]["descriptive_rss_uncertainty_mm"], 2**0.5)
        self.assertIsNone(result["reference_comparison"]["stereo_delta_mm"])
        self.assertIsNone(result["reference_comparison"]["relative_error_percent"])
        self.assertFalse(result["frozen_baseline"]["wass_rerun"])
        self.assertFalse(result["boundaries"]["reconstruction_parameters_modified"])

    def test_all_case2_frozen_artifact_hashes_when_external_run_is_present(self) -> None:
        baseline = yaml.safe_load((ROOT / "phase4_validation_case2_baseline.yaml").read_text(encoding="utf-8"))
        run = Path(r"D:\stereo-wave-height-runs\HomeTank_004\phase4-case2-candidate02-20260828")
        if not run.exists():
            self.skipTest("external frozen Case 2 artifacts are not present")
        paths = {
            "height_npz_sha256": run / "reconstruction/height/000000_height_points.npz",
            "pixel_xyz_npz_sha256": run / "reconstruction/pixel_xyz/000000_pixel_xyz.npz",
            "xyz_text_sha256": run / "reconstruction/pointcloud/000000.xyz",
            "mesh_cam_xyzc_sha256": run / "reconstruction/wass_workspace/work/000000_wd/mesh_cam.xyzC",
            "canonical_cam1_png_sha256": ROOT / "phase4_case2_manual_reference/wave_case2_cam1_canonical_reference.png",
        }
        for key, path in paths.items():
            self.assertEqual(file_sha256(path), baseline["wave"]["array_hashes"][key])

    @unittest.skipUnless(importlib.util.find_spec("cv2"), "OpenCV Python binding is optional in the base test runtime")
    def test_case2_canonical_mapping_exactness(self) -> None:
        mapping = ROOT / "manual_reference/frozen_cam1_validation_mapping.yaml"
        point = np.asarray([[799.0, 396.0]])
        mapped = canonical_cam1_to_rectified(point, mapping_file=mapping, wass_auto_swap=True)
        np.testing.assert_allclose(mapped[0], [1053.399225242184, 402.45596253946093], atol=1e-9)
        error = canonical_rectified_roundtrip_error(
            point, mapping_file=mapping, image_size=(1920, 1080), wass_auto_swap=True
        )
        self.assertLess(float(error[0]), 0.001)


if __name__ == "__main__":
    unittest.main()
