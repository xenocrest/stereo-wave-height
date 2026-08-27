"""Tests for frozen cam1 manual-reference identity and serialization."""

import tempfile
import unittest
from pathlib import Path

import yaml

from src.validation.manual_reference import (
    VALIDATION_COORDINATE_SYSTEM,
    file_sha256,
    require_direct_validation_coordinates,
    serialize_confirmed_point,
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
        self.assertIsNone(data["static"]["clicked_pixel"]["u_px"])
        self.assertIsNone(data["wave"]["pixel_uncertainty_px"])
        self.assertFalse(data["static"]["confirmed_by_user"])
        root = path.parent
        for label in ("static", "wave"):
            record = data[label]
            self.assertEqual(file_sha256(root / record["reference_image"]), record["reference_image_sha256"])
            self.assertEqual(file_sha256(root / record["canonical_reference_image"]), record["canonical_image_sha256"])

    def test_point_serialization_changes_only_selected_record(self) -> None:
        source = Path("experiments/real_video/HomeTank_004/manual_reference/manual_reference_points.yaml")
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "points.yaml"
            target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            serialize_confirmed_point(target, label="static", u_px=123, v_px=456, image_width_px=1920, image_height_px=1080)
            data = yaml.safe_load(target.read_text(encoding="utf-8"))
            self.assertEqual(data["static"]["clicked_pixel"], {"u_px": 123, "v_px": 456})
            self.assertTrue(data["static"]["confirmed_by_user"])
            self.assertIsNone(data["static"]["pixel_uncertainty_px"])
            self.assertFalse(data["wave"]["confirmed_by_user"])

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
