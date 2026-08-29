"""Tests for the on-demand single-frame request, timing gate and boundaries."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import subprocess
from types import SimpleNamespace

import numpy as np
from PIL import Image

from src.reconstruction.single_frame import (
    SingleFrameMeasurementRequest,
    SingleFrameMeasurementResult,
    SingleFrameMeasurementBackend,
    DenseHeightSpec,
    SynchronizationSpec,
    canonicalize_image_pair,
)
from src.synchronization.affine import AffineTimeMapping
from src.synchronization.frame_selection import VideoFrameTimestamp, extract_frame_by_pts, nearest_frame, select_timestamp_pair
from src.synchronization.tolerance import OnDemandSyncTolerancePolicy


class SingleFrameMeasurementTests(unittest.TestCase):
    @patch("src.reconstruction.single_frame._encode_lossless_single_frame")
    def test_dense_enabled_automatically_adds_summary_and_disabled_is_compatible(self, encode) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left, right = root / "left.png", root / "right.png"
            Image.fromarray(np.zeros((10, 10), dtype=np.uint8)).save(left)
            Image.fromarray(np.zeros((10, 10), dtype=np.uint8)).save(right)
            calibration, binding, mapping = root / "cal.yaml", root / "runtime.json", root / "mapping.yaml"
            for path in (calibration, binding, mapping): path.write_text("{}\n", encoding="utf-8")
            config_dir = root / "config"; config_dir.mkdir()
            def fake_pipeline(config):
                class Pipeline:
                    def run(self):
                        config.output_directory.mkdir(parents=True)
                        payload = {"frames": [{"frame_id": "000000", "point_count": 10,
                                   "pixel_xyz_correspondence_count": 10, "height_range_m": [-.01, .01],
                                   "height_mean_m": 0., "height_rms_m": .001, "height_max_absolute_m": .01,
                                   "water_plane_rms_m": .001}],
                                   "height_reference": {"normal": [0, 0, 1], "offset_m": 0},
                                   "calibration": {"baseline_m": .1}}
                        result = config.output_directory / "reconstruction_result.json"
                        result.write_text(json.dumps(payload), encoding="utf-8")
                        return SimpleNamespace(result_json=result)
                return Pipeline()
            dense_calls = []
            def fake_dense(config):
                dense_calls.append(config)
                return {"water_roi_pixel_count": 100, "status": {
                    "observed": {"count": 40}, "estimated": {"count": 10}, "unsupported": {"count": 50}}}
            dense = DenseHeightSpec(True, mapping, {"type": "polygon", "coordinate_system": "canonical_cam1",
                                                    "points": [[1, 1], [8, 1], [8, 8], [1, 8]]})
            request = SingleFrameMeasurementRequest(
                "image_pair", root / "out", calibration, config_dir, binding, Path("ffmpeg"), "explicit",
                left_image=left, right_image=right, dense_height=dense,
            )
            result = SingleFrameMeasurementBackend(pipeline_factory=fake_pipeline, dense_map_builder=fake_dense).run(request)
            self.assertEqual(result.status, "SINGLE_FRAME_DENSE_HEIGHT_COMPLETED")
            self.assertEqual(result.dense_height["valid_height_count"], 50)
            self.assertEqual(len(dense_calls), 1)
            compatible = SingleFrameMeasurementRequest(
                "image_pair", root / "out-disabled", calibration, config_dir, binding, Path("ffmpeg"), "explicit",
                left_image=left, right_image=right,
            )
            legacy = SingleFrameMeasurementBackend(pipeline_factory=fake_pipeline, dense_map_builder=fake_dense).run(compatible)
            self.assertEqual(legacy.status, "SINGLE_FRAME_PIPELINE_PASS")
            self.assertIsNone(legacy.dense_height)
            self.assertEqual(len(dense_calls), 1)

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

    @patch("src.synchronization.frame_selection.subprocess.run")
    def test_exact_pts_filter_is_passed_without_shell_escape_corruption(self, run) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "frame.png"
            def complete(argv, **_kwargs):
                output.write_bytes(b"png")
                return subprocess.CompletedProcess(argv, 0, "", "")
            run.side_effect = complete
            extract_frame_by_pts(
                "video.mp4", output, ffmpeg_executable="ffmpeg",
                frame=VideoFrameTimestamp(901103, 10.012256), rotation_deg=180,
            )
            argv = run.call_args.args[0]
            self.assertIn("select='eq(pts,901103)',hflip,vflip,format=gray", argv)

    def test_ruler_has_no_reverse_dependency_into_reconstruction(self) -> None:
        reconstruction = Path(__file__).resolve().parents[1] / "src" / "reconstruction"
        for source in reconstruction.glob("*.py"):
            text = source.read_text(encoding="utf-8").lower()
            self.assertNotIn("import ruler", text, source)
            self.assertNotIn("from validation.ruler", text, source)

    def test_request_serializes_engineering_tolerance_without_ruler_data(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left, right, calibration, binding = [
                root / name for name in ("left.mp4", "right.mp4", "cal.yaml", "runtime.json")
            ]
            for path in (left, right, calibration, binding):
                path.write_bytes(b"test")
            wass = root / "wass"; wass.mkdir()
            request = SingleFrameMeasurementRequest(
                input_mode="video_time", output_dir=root / "out", calibration_source=calibration,
                wass_config_dir=wass, wass_runtime_binding=binding, ffmpeg_executable=Path("ffmpeg"),
                synchronization_source="events", left_video=left, right_video=right, target_time_s=1.0,
                synchronization=SynchronizationSpec(1, 0, "events", "MEDIUM", False, 3, .01, .02),
                synchronization_tolerance=OnDemandSyncTolerancePolicy(
                    "ON_DEMAND_SYNC_TOLERANCE_ESTABLISHED", 0, 1, "controlled test"
                ),
            )
            payload = json.dumps(request.to_dict()).lower()
            self.assertIn("strict_max_abs_frames", payload)
            self.assertNotIn("ruler", payload)

    @patch("src.reconstruction.single_frame.probe_video_pts_window")
    def test_quality_gate_prevents_wass_for_coarse_model(self, probe) -> None:
        probe.return_value = tuple(
            VideoFrameTimestamp(index, value) for index, value in enumerate((0.98, 1.0, 1.02))
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left, right = root / "left.mp4", root / "right.mp4"
            calibration, binding = root / "calibration.yaml", root / "runtime.json"
            for path in (left, right, calibration, binding):
                path.write_bytes(b"test")
            config = root / "wass"; config.mkdir()
            request = SingleFrameMeasurementRequest(
                input_mode="video_time", output_dir=root / "output",
                calibration_source=calibration, wass_config_dir=config,
                wass_runtime_binding=binding, ffmpeg_executable=Path("ffmpeg"),
                synchronization_source="coarse_light_events", left_video=left,
                right_video=right, target_time_s=1.0,
                synchronization=SynchronizationSpec(1.0, 0.0, "coarse", "HIGH", False, 10, .05, .1),
            )
            def forbidden_pipeline(_config):
                raise AssertionError("WASS pipeline must not be constructed")
            result = SingleFrameMeasurementBackend(pipeline_factory=forbidden_pipeline).run(request)
            self.assertEqual(result.status, "FRAME_LEVEL_SYNC_NOT_ESTABLISHED")
            self.assertIsNone(result.xyz_point_count)


if __name__ == "__main__":
    unittest.main()
