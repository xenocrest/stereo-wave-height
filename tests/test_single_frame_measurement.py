"""Tests for the on-demand single-frame request, timing gate and boundaries."""

import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

from src.reconstruction.single_frame import (
    SingleFrameMeasurementRequest,
    SingleFrameMeasurementResult,
    SynchronizationSpec,
    canonicalize_image_pair,
)
from src.synchronization.affine import AffineTimeMapping
from src.synchronization.frame_selection import VideoFrameTimestamp, nearest_frame, select_timestamp_pair


class SingleFrameMeasurementTests(unittest.TestCase):
    def test_affine_target_mapping_and_nearest_pts_pair_residual(self) -> None:
        mapping = AffineTimeMapping(1.0001, 0.02, 4, 0.001, 0.002)
        left = tuple(VideoFrameTimestamp(index, value) for index, value in enumerate((0.98, 1.0, 1.02)))
        right = tuple(VideoFrameTimestamp(index + 10, value) for index, value in enumerate((1.02, 1.04, 1.06)))
        pair = select_timestamp_pair(
            left, right, requested_left_time_s=1.001, mapping=mapping,
            mapping_confidence="HIGH", frame_level_mapping_established=True,
        )
        self.assertEqual(pair.left.timestamp_s, 1.0)
        self.assertAlmostEqual(pair.mapped_right_time_s, 1.0201)
        self.assertAlmostEqual(pair.residual_s, -0.0001)
        self.assertEqual(pair.quality_status, "FRAME_PAIR_SYNC_ESTABLISHED")

    def test_coarse_mapping_fails_even_when_nearest_pts_residual_is_zero(self) -> None:
        frames = tuple(VideoFrameTimestamp(index, value) for index, value in enumerate((0.98, 1.0, 1.02)))
        pair = select_timestamp_pair(
            frames, frames, requested_left_time_s=1.0,
            mapping=AffineTimeMapping(1.0, 0.0, 10, 0.05, 0.1),
            mapping_confidence="HIGH", frame_level_mapping_established=False,
        )
        self.assertEqual(pair.residual_s, 0.0)
        self.assertEqual(pair.quality_status, "FRAME_LEVEL_SYNC_NOT_ESTABLISHED")

    def test_nearest_frame_uses_pts_not_frame_number_and_breaks_ties_earlier(self) -> None:
        frames = (VideoFrameTimestamp(900, 1.0), VideoFrameTimestamp(2, 1.2))
        self.assertEqual(nearest_frame(frames, 1.1).pts, 900)

    def test_orientation_canonicalization_is_declared_not_camera_specific(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            values = np.array([[1, 2, 3], [4, 5, 6]], dtype=np.uint8)
            for name in ("left.png", "right.png"):
                Image.fromarray(values).save(root / name)
            canonicalize_image_pair(
                root / "left.png", root / "right.png", root / "out_left.png", root / "out_right.png",
                left_rotation_deg=180, right_rotation_deg=0, orientation_source="test_metadata",
            )
            np.testing.assert_array_equal(np.asarray(Image.open(root / "out_left.png")), np.array([[6, 5, 4], [3, 2, 1]]))
            np.testing.assert_array_equal(np.asarray(Image.open(root / "out_right.png")), values)

    def test_request_and_result_are_json_serializable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left, right = root / "left.png", root / "right.png"
            Image.fromarray(np.zeros((2, 2), dtype=np.uint8)).save(left)
            Image.fromarray(np.zeros((2, 2), dtype=np.uint8)).save(right)
            calibration, binding = root / "calibration.yaml", root / "runtime.json"
            calibration.write_text("status: test\n", encoding="utf-8")
            binding.write_text("{}\n", encoding="utf-8")
            config = root / "wass_config"; config.mkdir()
            request = SingleFrameMeasurementRequest(
                input_mode="image_pair", output_dir=root / "output",
                calibration_source=calibration, wass_config_dir=config,
                wass_runtime_binding=binding, ffmpeg_executable=Path("ffmpeg"),
                synchronization_source="explicit_synchronized_image_pair",
                left_image=left, right_image=right,
            )
            json.dumps(request.to_dict())
            result = SingleFrameMeasurementResult(
                "SINGLE_FRAME_PIPELINE_PASS", None, None, None, 0.0, "left", "right",
                str(calibration), 10, 10, {"normal": [0, 0, 1], "offset_m": 0},
                "current_frame_fit", {"unit": "m"}, 0.001, 25.0,
                "HEIGHT_RESULT_AVAILABLE_NOT_PHYSICALLY_VALIDATED",
                "PHYSICAL_ACCURACY_NOT_ESTABLISHED", (), {"result_json": "single_frame_result.json"},
            )
            json.dumps(result.to_dict())

    def test_ruler_has_no_reverse_dependency_into_reconstruction(self) -> None:
        reconstruction = Path(__file__).resolve().parents[1] / "src" / "reconstruction"
        for source in reconstruction.glob("*.py"):
            text = source.read_text(encoding="utf-8").lower()
            self.assertNotIn("import ruler", text, source)
            self.assertNotIn("from validation.ruler", text, source)


if __name__ == "__main__":
    unittest.main()
