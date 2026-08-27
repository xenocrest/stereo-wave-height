"""Tests for frozen cam1 manual-reference identity and serialization."""

import tempfile
import unittest
from pathlib import Path
import importlib.util

import numpy as np
import yaml

from src.validation.manual_reference import (
    VALIDATION_COORDINATE_SYSTEM,
    canonical_cam1_to_rectified,
    canonical_rectified_roundtrip_error,
    file_sha256,
    require_direct_validation_coordinates,
    serialize_confirmed_point,
    validate_frozen_frame_identity,
)


class ManualReferencePickerTests(unittest.TestCase):
    def test_repository_template_preserves_frozen_identity_and_unknown_point(self) -> None:
        path = Path("experiments/real_video/HomeTank_004/manual_reference/manual_reference_points.yaml")
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.assertEqual(data["camera"], "cam1")
        self.assertEqual(data["frozen_pixel_xyz_coordinate_system"], VALIDATION_COORDINATE_SYSTEM)
        self.assertEqual(data["static"]["source_frame_id"], "pts_900024")
        self.assertEqual(data["wave"]["source_frame_id"], "pts_1794048")
        self.assertEqual(data["static"]["canonical_rotation_deg"], 0)
        self.assertIsNone(data["static"]["clicked_pixel_canonical"]["u_px"])
        self.assertIsNone(data["static"]["mapped_pixel_rectified"]["u_px"])
        self.assertIsNone(data["wave"]["pixel_uncertainty_px"])
        self.assertFalse(data["static"]["confirmed_by_user"])
        self.assertEqual(data["static"]["raw_to_canonical_transform"], "identity")
        self.assertEqual(data["static"]["raw_reference_image"], data["static"]["canonical_reference_image"])
        root = path.parent
        for label in ("static", "wave"):
            record = data[label]
            self.assertEqual(file_sha256(root / record["rectified_reference_image"]), record["rectified_image_sha256"])
            self.assertEqual(file_sha256(root / record["canonical_reference_image"]), record["canonical_image_sha256"])

    def test_frozen_frame_identity_cross_check_and_mismatch(self) -> None:
        record = {"source_frame_id": "pts_900024", "source_pts_s": 10.000267, "target_time_s": 10.012256}
        result = {"right_frame_id": "pts_900024", "right_timestamp_s": 10.000267, "requested_time_s": 10.012256}
        pair = result.copy()
        validate_frozen_frame_identity(record, result, pair)
        pair["right_frame_id"] = "pts_900025"
        with self.assertRaisesRegex(ValueError, "FROZEN_FRAME_IDENTITY_MISMATCH"):
            validate_frozen_frame_identity(record, result, pair)

    @unittest.skipUnless(importlib.util.find_spec("cv2"), "OpenCV Python binding is optional in the base test runtime")
    def test_point_serialization_changes_only_selected_record(self) -> None:
        source = Path("experiments/real_video/HomeTank_004/manual_reference/manual_reference_points.yaml")
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "points.yaml"
            document = yaml.safe_load(source.read_text(encoding="utf-8"))
            document["mapping"]["frozen_mapping_file"] = str(
                Path("experiments/real_video/HomeTank_004/manual_reference/frozen_cam1_validation_mapping.yaml").resolve()
            )
            target.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
            serialize_confirmed_point(
                target, label="static", u_px=800, v_px=420, image_width_px=1920,
                image_height_px=1080, coordinate_system="canonical_cam1",
            )
            data = yaml.safe_load(target.read_text(encoding="utf-8"))
            self.assertEqual(data["static"]["clicked_pixel_canonical"], {"u_px": 800, "v_px": 420})
            self.assertAlmostEqual(data["static"]["mapped_pixel_rectified"]["u_px"], 1047.85534870, places=5)
            self.assertTrue(data["static"]["confirmed_by_user"])
            self.assertIsNone(data["static"]["pixel_uncertainty_px"])
            self.assertFalse(data["wave"]["confirmed_by_user"])

    @unittest.skipUnless(importlib.util.find_spec("cv2"), "OpenCV Python binding is optional in the base test runtime")
    def test_opencv_cam1_mapping_and_roundtrip(self) -> None:
        mapping = Path("experiments/real_video/HomeTank_004/manual_reference/frozen_cam1_validation_mapping.yaml")
        point = np.asarray([[800.0, 420.0]])
        mapped = canonical_cam1_to_rectified(point, mapping_file=mapping, wass_auto_swap=True)
        np.testing.assert_allclose(mapped[0], [1047.85534870, 456.46813727], atol=1e-6)
        error = canonical_rectified_roundtrip_error(
            point, mapping_file=mapping, image_size=(1920, 1080), wass_auto_swap=True
        )
        self.assertLess(float(error[0]), 0.001)

    def test_unverified_raw_mapping_and_resolution_scaling_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "MAPPING_NOT_AVAILABLE"):
            require_direct_validation_coordinates(
                source_coordinate_system="canonical_cam1", target_coordinate_system=VALIDATION_COORDINATE_SYSTEM,
                source_size=(1920, 1080), target_size=(1920, 1080),
            )
        with self.assertRaisesRegex(ValueError, "resolution scaling"):
            require_direct_validation_coordinates(
                source_coordinate_system=VALIDATION_COORDINATE_SYSTEM, target_coordinate_system=VALIDATION_COORDINATE_SYSTEM,
                source_size=(960, 540), target_size=(1920, 1080),
            )

    def test_ruler_values_remain_outside_reconstruction(self) -> None:
        for source in Path("src/reconstruction").glob("*.py"):
            text = source.read_text(encoding="utf-8")
            self.assertNotIn("ruler_measurement", text)
            self.assertNotIn("manual_reference_points", text)


if __name__ == "__main__":
    unittest.main()
