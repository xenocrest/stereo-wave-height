import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from pipeline.adapters import sync
from pipeline.common import CommandRecorder, sha256
from pipeline.run_pipeline import load_config, validate_config


class VieiraWassPipelineTests(unittest.TestCase):
    def test_checked_in_configs_validate(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(load_config(root / "examples" / "vieira_official.yaml")["source_type"], "synchronized_image_sequence")
        self.assertEqual(load_config(root / "examples" / "hometank004.yaml")["source_type"], "stereo_video")

    def test_missing_input_contract_is_rejected(self):
        config = {
            "project": "x", "source_type": "stereo_video", "output_root": "D:/runs",
            "tools": {}, "calibration": {}, "sync": {"left_video": "left.mp4"},
            "wass": {}, "surface": {"baseline_m": 1},
        }
        with self.assertRaisesRegex(ValueError, "sync.right_video"):
            validate_config(config)

    def test_provided_sequence_is_copied_losslessly_without_mp4(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left, right, run = root / "input0", root / "input1", root / "run"
            left.mkdir(); right.mkdir(); run.mkdir()
            image = np.arange(8 * 12, dtype=np.uint8).reshape(8, 12)
            for index in range(2):
                for folder in (left, right):
                    encoded = cv2.imencode(".tif", image + index)[1]
                    encoded.tofile(folder / f"{index:06d}.tif")
            report = sync.run(
                "synchronized_image_sequence",
                {"left_images": str(left / "*.tif"), "right_images": str(right / "*.tif"), "fps": 12},
                {}, run, Path.cwd(), CommandRecorder(run / "logs"),
            )
            self.assertEqual(report["status"], "PROVIDED")
            self.assertEqual(report["frame_count"], 2)
            self.assertFalse(list(run.rglob("*.mp4")))
            self.assertEqual(sha256(left / "000000.tif"), sha256(run / "sync" / "frames" / "cam0" / "000000.tif"))

    def test_nonpositive_baseline_is_rejected(self):
        config = {
            "project": "x", "source_type": "synchronized_image_sequence", "output_root": "D:/runs",
            "tools": {}, "calibration": {},
            "sync": {"left_images": "a/*", "right_images": "b/*", "fps": 1},
            "wass": {}, "surface": {"baseline_m": 0},
        }
        with self.assertRaisesRegex(ValueError, "baseline_m"):
            validate_config(config)


if __name__ == "__main__":
    unittest.main()

