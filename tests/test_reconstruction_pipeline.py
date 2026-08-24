"""Unit tests for the generic reconstruction orchestration contracts."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from adapters.wass.input import prepare_wass_workspace
from reconstruction.io import load_calibration, load_reference_plane, verify_wass_calibration
from reconstruction.surface import extract_planar_surface


class ReconstructionPipelineTests(unittest.TestCase):
    def test_surface_height_is_signed_point_to_plane_distance(self) -> None:
        x, y = np.meshgrid(np.linspace(-1, 1, 5), np.linspace(-1, 1, 5))
        z = 0.2 * x - 0.1 * y + 2.0
        points = np.column_stack((x.ravel(), y.ravel(), z.ravel()))
        result = extract_planar_surface(points, distance_threshold_m=0.001)
        self.assertLess(result.rms_m, 1e-12)
        self.assertTrue(np.all(result.water_mask))
        self.assertLess(np.max(np.abs(result.residual_m)), 1e-12)

    def test_failed_quality_gate_requires_explicit_diagnostic_mode(self) -> None:
        source = Path(__file__).parents[1] / "experiments" / "real_video" / "HomeTank_004" / "calibration_result.yaml"
        with self.assertRaisesRegex(ValueError, "quality gate"):
            load_calibration(source, quality_mode="require_approved")
        result = load_calibration(source, quality_mode="diagnostic_allow_failed_gate")
        self.assertFalse(result.approved_for_wass)
        self.assertAlmostEqual(result.baseline_m, 0.06868471158474378)

    def test_wass_calibration_comparison_rejects_changed_parameter(self) -> None:
        source = Path(__file__).parents[1] / "experiments" / "real_video" / "HomeTank_004" / "calibration_result.yaml"
        calibration = load_calibration(source, quality_mode="diagnostic_allow_failed_gate")
        config = Path(r"D:\stereo-wave-height-runs\HomeTank_004\static-full-calibration-valid-point-ransac-20260822\config")
        if not config.is_dir():
            self.skipTest("machine-local HomeTank fixed calibration is unavailable")
        verify_wass_calibration(config, calibration)

    def test_workspace_copies_fixed_extrinsics_as_a_pair(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset = root / "dataset"
            for directory in (dataset / "left", dataset / "right", dataset / "metadata"):
                directory.mkdir(parents=True, exist_ok=True)
            (dataset / "left" / "000000.png").write_bytes(b"left")
            (dataset / "right" / "000000.png").write_bytes(b"right")
            (dataset / "metadata" / "manifest.json").write_text(json.dumps({
                "dataset_type": "real_stereo_video_wass_input_adapter",
                "orientation_status": "CANONICAL_ORIENTATION_APPLIED",
                "pairing_basis": "timestamp",
                "frames": [{"frame_id": "000000", "timestamp_ns": 1, "left_image": "left/000000.png", "right_image": "right/000000.png"}],
            }), encoding="utf-8")
            config = root / "config"; config.mkdir()
            for name in ("intrinsics_00.xml", "intrinsics_01.xml", "distortion_00.xml", "distortion_01.xml", "matcher_config.txt", "stereo_config.txt", "ext_R.xml", "ext_T.xml"):
                (config / name).write_text(name, encoding="utf-8")
            prepared = prepare_wass_workspace(dataset, root / "workspace", verified_config_dir=config)
            manifest = json.loads(prepared.manifest_path.read_text(encoding="utf-8"))
            self.assertTrue(manifest["fixed_calibration_available"])
            self.assertTrue((prepared.calibration_dir / "ext_R.xml").is_file())
            self.assertTrue((prepared.calibration_dir / "ext_T.xml").is_file())

    def test_static_reference_plane_is_normalized_and_traceable(self) -> None:
        source = Path(__file__).parents[1] / "experiments" / "real_video" / "HomeTank_004" / "static_reference_plane.yaml"
        normal, offset, metadata = load_reference_plane(source)
        self.assertAlmostEqual(float(np.linalg.norm(normal)), 1.0)
        self.assertAlmostEqual(offset, -0.22467304473232508)
        self.assertEqual(metadata["status"], "STATIC_REFERENCE_WITH_WARNING")
        self.assertIn("STATIC_VALIDATION_FAIL", metadata["warning"])


if __name__ == "__main__":
    unittest.main()
