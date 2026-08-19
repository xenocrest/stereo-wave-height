"""Trial-1 guards for orientation, timing, units, and coarse provenance."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from adapters.wass.input import REQUIRED_WASS_CONFIG_FILES, prepare_wass_workspace
from geometry import CoarseIntrinsicHypothesis, CoarseStereoGeometry, baseline_mm_to_m
from input import OrientationTransform
from synchronization import fit_affine_time_mapping, pair_nearest_timestamps


class RealVideoTrialTests(unittest.TestCase):
    def _intrinsic(self) -> CoarseIntrinsicHypothesis:
        return CoarseIntrinsicHypothesis(1920, 1080, 1370.0, 1370.0, 960.0, 540.0, "70 deg assumed horizontal FOV")

    def test_cam0_180_degree_normalization(self) -> None:
        encoded = np.array([[1, 2, 3], [4, 5, 6]])
        transform = OrientationTransform(180, "MP4 display matrix")
        np.testing.assert_array_equal(transform.apply(encoded), [[6, 5, 4], [3, 2, 1]])
        self.assertEqual(transform.as_mapping()["rotation_deg_counter_clockwise"], 180)

    def test_timestamp_pairing_does_not_require_equal_indices(self) -> None:
        mapping = fit_affine_time_mapping([0.0, 10.0, 20.0], [0.07, 10.06, 20.05])
        result = pair_nearest_timestamps([1.0, 2.0], [0.05, 1.069, 2.068], mapping, tolerance_s=0.01)
        self.assertEqual([(pair.left_index, pair.right_index) for pair in result.pairs], [(0, 1), (1, 2)])

    def test_baseline_and_common_pitch_provenance(self) -> None:
        intrinsic = self._intrinsic()
        baseline = baseline_mm_to_m(650.0)
        geometry = CoarseStereoGeometry(intrinsic, intrinsic, baseline, np.eye(3), np.array([baseline, 0.0, 0.0]), 40.0)
        record = geometry.as_mapping()
        self.assertEqual(record["baseline_m"], 0.65)
        self.assertEqual(record["relative_rotation_right_from_left"], np.eye(3).tolist())
        self.assertEqual(record["common_system_pitch_deg"], 40.0)
        self.assertEqual(record["common_pitch_role"], "deployment_orientation_not_relative_stereo_rotation")
        self.assertEqual(record["intrinsic_status"], "ASSUMED_FOR_FEASIBILITY_ONLY")

    def test_real_manifest_requires_canonical_timestamp_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset = root / "dataset"
            for directory in (dataset / "left", dataset / "right", dataset / "metadata"):
                directory.mkdir(parents=True, exist_ok=True)
            (dataset / "left" / "000000.png").write_bytes(b"left")
            (dataset / "right" / "000000.png").write_bytes(b"right")
            manifest = {
                "dataset_type": "real_stereo_video_wass_input_adapter",
                "orientation_status": "CANONICAL_ORIENTATION_APPLIED",
                "pairing_basis": "timestamp",
                "frames": [{"frame_id": "000000", "timestamp_ns": 1_000_123_456, "left_image": "left/000000.png", "right_image": "right/000000.png"}],
            }
            (dataset / "metadata" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            config = root / "config"; config.mkdir()
            for name in REQUIRED_WASS_CONFIG_FILES:
                (config / name).write_text(name, encoding="utf-8")
            prepared = prepare_wass_workspace(dataset, root / "workspace", verified_config_dir=config)
            self.assertEqual(prepared.frame_count, 1)
            output = json.loads(prepared.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(output["frames"][0]["timestamp_ns"], 1_000_123_456)
            self.assertEqual(output["frames"][0]["timestamp_filename_quantization"], "floor_to_millisecond_filename_only")


if __name__ == "__main__":
    unittest.main()
