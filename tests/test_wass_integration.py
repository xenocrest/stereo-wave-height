"""Unit tests for the WASS boundary; WASS binaries are never invoked here."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from adapters.wass.input import REQUIRED_WASS_CONFIG_FILES, prepare_wass_workspace
from adapters.wass.output.netcdf import VerifiedNetcdfMapping
from adapters.wass.runner import WassExecutables, WassRunner, WassStageError


class WassIntegrationTests(unittest.TestCase):
    def _dataset(self, root: Path) -> Path:
        dataset = root / "dataset"
        (dataset / "left").mkdir(parents=True)
        (dataset / "right").mkdir()
        (dataset / "metadata").mkdir()
        (dataset / "ground_truth").mkdir()
        (dataset / "left" / "000000.png").write_bytes(b"left-image")
        (dataset / "right" / "000000.png").write_bytes(b"right-image")
        (dataset / "ground_truth" / "height_fields.npz").write_bytes(b"must-not-be-copied")
        manifest = {
            "dataset_type": "synthetic_stereo_wass_input_adapter",
            "ground_truth_reference": {"path": "ground_truth/height_fields.npz"},
            "frames": [{
                "frame_id": "000000",
                "timestamp_ns": 1_000_000_000,
                "left_image": "left/000000.png",
                "right_image": "right/000000.png",
            }],
        }
        (dataset / "metadata" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return dataset

    def _config(self, root: Path) -> Path:
        config = root / "verified-config"
        config.mkdir()
        for name in REQUIRED_WASS_CONFIG_FILES:
            (config / name).write_text(f"verified test fixture: {name}\n", encoding="utf-8")
        return config

    def test_input_adapter_path_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepared = prepare_wass_workspace(
                self._dataset(root), root / "workspace", verified_config_dir=self._config(root)
            )
            manifest = json.loads(prepared.manifest_path.read_text(encoding="utf-8"))
            frame = manifest["frames"][0]
            self.assertEqual(frame["cam0"], "input/cam0/000000_0000000001000_01.png")
            self.assertEqual(frame["cam1"], "input/cam1/000000_0000000001000_02.png")
            self.assertFalse(manifest["ground_truth_exposed_to_wass"])
            self.assertFalse((prepared.root / "ground_truth").exists())

    def test_manifest_frame_pairing_rejects_missing_image(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset = self._dataset(root)
            (dataset / "right" / "000000.png").unlink()
            with self.assertRaises(FileNotFoundError):
                prepare_wass_workspace(dataset, root / "workspace", verified_config_dir=self._config(root))

    def test_runner_failure_handling_and_logs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepared = prepare_wass_workspace(
                self._dataset(root), root / "workspace", verified_config_dir=self._config(root)
            )
            binaries = root / "bin"
            binaries.mkdir()
            paths = []
            for name in ("prepare", "match", "autocalibrate", "stereo"):
                path = binaries / name
                path.write_text("test fixture", encoding="utf-8")
                paths.append(path)
            runner = WassRunner(WassExecutables(*paths))
            failed = subprocess.CompletedProcess([], 23, stdout="out", stderr="failure")
            with patch("adapters.wass.runner.subprocess.run", return_value=failed):
                with self.assertRaisesRegex(WassStageError, "prepare.*000000.*23"):
                    runner.run(prepared.root)
            self.assertEqual((prepared.root / "logs" / "prepare_000000.stderr.log").read_text(), "failure")
            commands = (prepared.root / "logs" / "commands.jsonl").read_text(encoding="utf-8")
            self.assertIn('"stage": "prepare"', commands)

    def test_parser_metadata_validation(self) -> None:
        mapping = VerifiedNetcdfMapping(
            z_variable="Z", mask_variable="maskZ", x_variable="X_grid", y_variable="Y_grid",
            z_dimensions=("count", "X", "Y"), time_dimension="count", x_dimension="X",
            y_dimension="Y", source_unit="mm", output_unit="m",
            source_coordinate_system="wass_grid", output_coordinate_system="wass_grid",
            scale_to_output=0.001, mask_true_means_valid=True,
        )
        self.assertEqual(mapping.z_dimensions, ("count", "X", "Y"))
        self.assertEqual(mapping.scale_to_output, 0.001)

    def test_unknown_unit_failure(self) -> None:
        with self.assertRaisesRegex(ValueError, "source_unit"):
            VerifiedNetcdfMapping(
                "Z", "maskZ", "X", "Y", ("t", "x", "y"), "t", "x", "y",
                "UNKNOWN", "m", "wass_grid", "wass_grid", 0.001, True,
            )

    def test_unknown_coordinate_system_failure(self) -> None:
        with self.assertRaisesRegex(ValueError, "source_coordinate_system"):
            VerifiedNetcdfMapping(
                "Z", "maskZ", "X", "Y", ("t", "x", "y"), "t", "x", "y",
                "mm", "m", "UNKNOWN/TODO", "wass_grid", 0.001, True,
            )


if __name__ == "__main__":
    unittest.main()
