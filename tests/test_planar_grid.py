"""Synthetic projective tests for the general non-polarity planar-grid detector."""

from __future__ import annotations

import importlib.util
import unittest

import numpy as np

from calibration import CheckerboardSpec, PlanarGridHint, orient_quad


CV2_AVAILABLE = importlib.util.find_spec("cv2") is not None


@unittest.skipUnless(CV2_AVAILABLE, "optional OpenCV calibration backend not installed")
class PlanarGridRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import cv2
        from calibration import recover_planar_grid
        cls.cv2 = cv2
        cls.recover = staticmethod(recover_planar_grid)

    def _image(self, quad: np.ndarray, *, incomplete: bool = False) -> tuple[np.ndarray, PlanarGridHint]:
        cv2 = self.cv2
        canonical = np.full((700, 1000), 238, dtype=np.uint8)
        for x in range(0, 1001, 100):
            if x < 1000: cv2.line(canonical, (x, 0), (x, 699), 25, 3)
        for y in range(0, 701, 100):
            if y < 700 and not (incomplete and y == 300): cv2.line(canonical, (0, y), (999, y), 25, 3)
        source = np.float32([[0, 0], [999, 0], [999, 699], [0, 699]])
        h = cv2.getPerspectiveTransform(source, quad.astype(np.float32))
        image = cv2.warpPerspective(canonical, h, (1280, 900), borderValue=128)
        hint = PlanarGridHint(tuple(quad[0]), tuple(quad[1]), tuple(quad[2]), tuple(quad[3]))
        return image, hint

    def test_perspective_grid_recovers_ordered_9_by_6(self) -> None:
        quad = np.float32([[160, 100], [1120, 170], [1040, 800], [220, 740]])
        image, hint = self._image(quad)
        result = self.recover(image, expected_cols=9, expected_rows=6, hint=hint, cv2_module=self.cv2)
        self.assertTrue(result.detected, result.diagnostics.rejection_reason)
        self.assertEqual(result.ordered_points_px.shape, (54, 2))
        self.assertEqual(result.diagnostics.final_lattice_shape, (6, 9))
        # Row-major ordering follows the explicit physical +X and +Y hint.
        self.assertGreater(result.ordered_points_px[8, 0], result.ordered_points_px[0, 0])
        self.assertGreater(result.ordered_points_px[9, 1], result.ordered_points_px[0, 1])

    def test_incomplete_grid_is_rejected(self) -> None:
        quad = np.float32([[160, 100], [1120, 170], [1040, 800], [220, 740]])
        image, hint = self._image(quad, incomplete=True)
        result = self.recover(image, expected_cols=9, expected_rows=6, hint=hint, cv2_module=self.cv2)
        self.assertFalse(result.detected)

    def test_out_of_image_intersections_are_rejected_without_opencv_error(self) -> None:
        image = np.full((300, 400), 255, dtype=np.uint8)
        hint = PlanarGridHint((-100.0, -100.0), (300.0, -100.0), (300.0, 200.0), (-100.0, 200.0))
        result = self.recover(
            image,
            expected_cols=9,
            expected_rows=6,
            hint=hint,
            cv2_module=self.cv2,
            minimum_line_support=0.0,
        )
        self.assertFalse(result.detected)
        self.assertEqual(result.diagnostics.rejection_reason, "one or more expected intersections are outside the image")


class PlanarGridOrderingTests(unittest.TestCase):
    def test_orientation_permutation_is_resolved_by_anchor_and_axis(self) -> None:
        quad = np.asarray([[10, 10], [110, 20], [100, 80], [20, 70]], dtype=float)
        permuted = quad[[2, 0, 3, 1]]
        hint = orient_quad(permuted, anchor_index=1, x_axis_neighbour_index=3)
        np.testing.assert_allclose(hint.as_quad(), quad)

    def test_spacing_provenance_and_object_mapping_remain_metric(self) -> None:
        spec = CheckerboardSpec(9, 6, 0.020)
        points = spec.object_points_m()
        self.assertEqual(points.shape[0], 54)
        np.testing.assert_allclose(points[8], [0.160, 0.0, 0.0])
        np.testing.assert_allclose(points[-1], [0.160, 0.100, 0.0])


if __name__ == "__main__":
    unittest.main()
