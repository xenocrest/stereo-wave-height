import json
import os
from pathlib import Path
import tempfile
import unittest

import numpy as np

from adapters.wass.input.opencv_xml import (
    inspect_opencv_matrix_schema,
    write_wass_coarse_fixed_calibration,
    write_wass_fixed_calibration,
)
from calibration import (
    CheckerboardSpec,
    CoarseGeometryConfig,
    CoarseValue,
    calibrate_stereo_official,
    detect_checkerboard_official,
    load_calibration_result_json,
    save_calibration_result_json,
)


class CoarseFixedCalibrationExportTests(unittest.TestCase):
    def test_explicit_non_metric_coarse_export_without_autocalibrate(self):
        k = np.array([[1329.0, 0, 960.0], [0, 1329.0, 540.0], [0, 0, 1.0]])
        kwargs = dict(
            intrinsic_00=k, intrinsic_01=k, distortion_00=np.zeros(5),
            distortion_01=np.zeros(5), rotation_01=np.eye(3),
            translation_01_m=np.array([-0.070, 0, 0]),
            metrological_validity=False,
            purpose="ALGORITHM_CLOSURE_VALIDATION_ONLY", source="coarse unit test",
        )
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            with self.assertRaisesRegex(ValueError, "explicitly allowed"):
                write_wass_coarse_fixed_calibration(
                    directory, coarse_fixed_calibration_allowed=False, **kwargs,
                )
            files = write_wass_coarse_fixed_calibration(
                directory, coarse_fixed_calibration_allowed=True, **kwargs,
            )
            self.assertEqual(len(files), 7)
            meta = json.loads((Path(directory) / "fixed_calibration_provenance.json").read_text())
            self.assertFalse(meta["approved_for_wass"])
            self.assertFalse(meta["metrological_validity"])
            self.assertTrue(meta["coarse_fixed_calibration_allowed"])
            self.assertFalse(meta["autocalibrate_required"])


class OpenCvCalibrationBackendTests(unittest.TestCase):
    def setUp(self):
        try:
            import cv2
        except ImportError:
            self.skipTest("OpenCV is not installed in the unit-test interpreter")
        self.cv2 = cv2
        self.spec = CheckerboardSpec(9, 6, 0.020)

    def _synthetic_correspondences(self):
        cv2 = self.cv2
        obj = self.spec.object_points_m()
        k0 = np.array([[820.0, 0, 320.0], [0, 815.0, 240.0], [0, 0, 1.0]])
        k1 = np.array([[825.0, 0, 318.0], [0, 818.0, 242.0], [0, 0, 1.0]])
        r01, _ = cv2.Rodrigues(np.array([0.004, -0.009, 0.003]))
        t01 = np.array([[-0.120], [0.001], [0.002]])
        objects, left, right = [], [], []
        for index in range(15):
            rvec = np.array([0.05 * np.sin(index), 0.12 * np.cos(index / 2), 0.03 * np.sin(index / 3)])
            r0, _ = cv2.Rodrigues(rvec)
            t0 = np.array([[-0.10 + 0.015 * index], [-0.06 + 0.008 * index], [0.85 + 0.025 * index]])
            r1 = r01 @ r0
            t1 = r01 @ t0 + t01
            rvec1, _ = cv2.Rodrigues(r1)
            lp, _ = cv2.projectPoints(obj, rvec, t0, k0, np.zeros(5))
            rp, _ = cv2.projectPoints(obj, rvec1, t1, k1, np.zeros(5))
            objects.append(obj.copy()); left.append(lp); right.append(rp)
        return objects, left, right, r01, t01

    def test_object_point_9x6_row_major_ordering_and_scale(self):
        points = self.spec.object_points_m()
        self.assertEqual(points.shape, (54, 3))
        np.testing.assert_allclose(points[0], [0, 0, 0])
        np.testing.assert_allclose(points[8], [0.16, 0, 0])
        np.testing.assert_allclose(points[9], [0, 0.02, 0])

    def test_synthetic_stereo_order_convention_baseline_rectification_and_serialization(self):
        objects, left, right, expected_r, expected_t = self._synthetic_correspondences()
        result = calibrate_stereo_official(objects, left, right, (640, 480), square_size_m=0.020)
        self.assertTrue(np.isfinite(result.stereo_rms_px))
        self.assertLess(result.stereo_rms_px, 1e-3)
        np.testing.assert_allclose(result.rotation_right_from_left, expected_r, atol=2e-4)
        np.testing.assert_allclose(result.translation_right_from_left_m, expected_t, atol=2e-4)
        self.assertAlmostEqual(result.baseline_m, float(np.linalg.norm(expected_t)), places=4)
        self.assertEqual(result.rectification.projection_left.shape, (3, 4))
        self.assertEqual(result.rectification.projection_right.shape, (3, 4))
        self.assertLess(result.rectification.vertical_disparity_rms_px, 1e-3)
        # OpenCV FileStorage on Windows does not reliably open non-ASCII paths;
        # keep the WASS-schema integration fixture under the ASCII repository.
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            path = save_calibration_result_json(result, Path(directory) / "result.json")
            loaded = load_calibration_result_json(path)
            self.assertEqual(loaded["convention"], "X_right = R_right_from_left @ X_left + T_right_from_left_m")
            self.assertEqual(loaded["image_size_wh"], [640, 480])

    def test_left_right_swap_changes_translation_direction(self):
        objects, left, right, _, _ = self._synthetic_correspondences()
        forward = calibrate_stereo_official(objects, left, right, (640, 480), square_size_m=0.020)
        reverse = calibrate_stereo_official(objects, right, left, (640, 480), square_size_m=0.020)
        expected_reverse_t = -reverse.rotation_right_from_left @ forward.translation_right_from_left_m
        np.testing.assert_allclose(reverse.translation_right_from_left_m, expected_reverse_t, atol=5e-4)

    def test_canonical_180_rotation_round_trip(self):
        image = np.arange(60, dtype=np.uint8).reshape(6, 10)
        canonical = self.cv2.rotate(self.cv2.rotate(image, self.cv2.ROTATE_180), self.cv2.ROTATE_180)
        np.testing.assert_array_equal(canonical, image)
        point = np.array([[[2.0, 1.0]]], dtype=np.float32)
        width, height = image.shape[1], image.shape[0]
        rotated = np.array([[[width - 1 - point[0, 0, 0], height - 1 - point[0, 0, 1]]]], dtype=np.float32)
        restored = np.array([[[width - 1 - rotated[0, 0, 0], height - 1 - rotated[0, 0, 1]]]], dtype=np.float32)
        np.testing.assert_array_equal(restored, point)

    def test_wass_fixed_converter_structure_and_gate(self):
        objects, left, right, _, _ = self._synthetic_correspondences()
        result = calibrate_stereo_official(objects, left, right, (640, 480), square_size_m=0.020)
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            with self.assertRaisesRegex(ValueError, "quality gate"):
                write_wass_fixed_calibration(
                    directory, intrinsic_00=result.mono_left.camera_matrix,
                    intrinsic_01=result.mono_right.camera_matrix,
                    distortion_00=result.mono_left.distortion.reshape(-1)[:5],
                    distortion_01=result.mono_right.distortion.reshape(-1)[:5],
                    rotation_01=result.rotation_right_from_left,
                    translation_01_m=result.translation_right_from_left_m,
                    approved_for_wass=False, source="test",
                )
            files = write_wass_fixed_calibration(
                directory, intrinsic_00=result.mono_left.camera_matrix,
                intrinsic_01=result.mono_right.camera_matrix,
                distortion_00=result.mono_left.distortion.reshape(-1)[:5],
                distortion_01=result.mono_right.distortion.reshape(-1)[:5],
                rotation_01=result.rotation_right_from_left,
                translation_01_m=result.translation_right_from_left_m,
                approved_for_wass=True, source="synthetic numerical test",
            )
            self.assertEqual(len(files), 7)
            self.assertEqual(inspect_opencv_matrix_schema(Path(directory) / "ext_R.xml").node_name, "ext_R")
            self.assertEqual(inspect_opencv_matrix_schema(Path(directory) / "ext_T.xml").node_name, "ext_T")
            storage = self.cv2.FileStorage(str(Path(directory) / "ext_R.xml"), self.cv2.FILE_STORAGE_READ)
            np.testing.assert_allclose(storage.getNode("ext_R").mat(), result.rotation_right_from_left)
            storage.release()
            meta = json.loads((Path(directory) / "fixed_calibration_provenance.json").read_text())
            self.assertFalse(meta["autocalibrate_required"])
            self.assertEqual(meta["translation_input_unit"], "m")

    def test_coarse_geometry_validation_is_never_metric(self):
        cfg = CoarseGeometryConfig(
            CoarseValue(0.20, "m", "MEASURED"), CoarseValue(None, "m", "USER_SPECIFIED"),
            CoarseValue(None, "m", "USER_SPECIFIED"), CoarseValue(40, "deg", "USER_SPECIFIED"),
            CoarseValue(40, "deg", "USER_SPECIFIED"), 1920, 1080,
            horizontal_fov_deg=CoarseValue(70, "deg", "ASSUMED"),
        )
        self.assertFalse(cfg.metrological_validity)
        self.assertEqual(cfg.purpose, "ALGORITHM_CLOSURE_VALIDATION")
        with self.assertRaises(ValueError):
            CoarseGeometryConfig(
                cfg.baseline_m, cfg.cam0_height_m, cfg.cam1_height_m,
                cfg.cam0_pitch_deg, cfg.cam1_pitch_deg, 1920, 1080,
                horizontal_fov_deg=cfg.horizontal_fov_deg, metrological_validity=True,
            )

    def test_official_opencv_public_stereo_images_golden_path(self):
        fixture = os.environ.get("OPENCV_GOLDEN_DATA_DIR")
        if not fixture:
            self.skipTest("set OPENCV_GOLDEN_DATA_DIR for the official OpenCV image integration gate")
        root = Path(fixture)
        objects, left, right = [], [], []
        for left_path in sorted(root.glob("left*.jpg")):
            right_path = root / left_path.name.replace("left", "right", 1)
            if not right_path.is_file():
                continue
            limage = self.cv2.imread(str(left_path), self.cv2.IMREAD_GRAYSCALE)
            rimage = self.cv2.imread(str(right_path), self.cv2.IMREAD_GRAYSCALE)
            ld = detect_checkerboard_official(limage, self.spec, cv2_module=self.cv2)
            rd = detect_checkerboard_official(rimage, self.spec, cv2_module=self.cv2)
            if ld is not None and rd is not None:
                objects.append(self.spec.object_points_m())
                left.append(ld.corners_px); right.append(rd.corners_px)
        self.assertGreaterEqual(len(objects), 8)
        result = calibrate_stereo_official(objects, left, right, (640, 480), square_size_m=0.020)
        self.assertTrue(np.isfinite(result.stereo_rms_px))
        self.assertTrue(np.isfinite(result.epipolar_rms_px))
        self.assertGreater(result.baseline_m, 0)
        self.assertGreater(result.rectification.common_valid_roi[2], 0)
        self.assertGreater(result.rectification.common_valid_roi[3], 0)

if __name__ == "__main__":
    unittest.main()
