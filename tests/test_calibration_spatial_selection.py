import unittest

from calibration.spatial_selection import (
    baseline_sanity, build_bilateral_descriptor, select_spatially_diverse, spatial_grid_counts,
)


def pair(pair_id: str, x: float, y: float, sharpness: float = 100.0):
    corners = [[x + (i % 9) * 10, y + (i // 9) * 10] for i in range(54)]
    camera = {"center_x_px": x + 40, "center_y_px": y + 25, "area_fraction": .1,
              "perspective_score": .05, "sharpness": sharpness, "corners": corners}
    return {"pair_id": pair_id, "left": camera, "right": camera,
            "left_corners": corners, "right_corners": corners}


class SpatialCalibrationSelectionTests(unittest.TestCase):
    def test_descriptor_grid_and_selection_are_deterministic(self):
        descriptors = [build_bilateral_descriptor(pair(str(i), x, y), image_size_wh=(300, 300))
                       for i, (x, y) in enumerate([(5, 5), (105, 5), (205, 5), (5, 105), (105, 105), (205, 205)])]
        first = select_spatially_diverse(descriptors, count=4)
        second = select_spatially_diverse(descriptors, count=4)
        self.assertEqual([item.pair_id for item in first], [item.pair_id for item in second])
        self.assertGreaterEqual(sum(value > 0 for value in spatial_grid_counts(first)[0]), 4)

    def test_orientation_descriptor_is_continuous_across_pi_wrap(self):
        a = build_bilateral_descriptor(pair("a", 10, 10), image_size_wh=(300, 300))
        wrapped = pair("b", 10, 10)
        for camera in (wrapped["left"], wrapped["right"]):
            camera["corners"] = list(reversed(camera["corners"]))
        wrapped["left_corners"] = wrapped["left"]["corners"]
        wrapped["right_corners"] = wrapped["right"]["corners"]
        b = build_bilateral_descriptor(wrapped, image_size_wh=(300, 300))
        # Reversal changes directed board orientation by pi; sin/cos keeps the
        # representation finite and avoids the -pi/+pi scalar discontinuity.
        self.assertTrue(all(abs(value) <= 1 for value in (b.vector[3], b.vector[4], b.vector[9], b.vector[10])))

    def test_duplicates_and_validation_exclusion(self):
        items = [build_bilateral_descriptor(pair("a", 10, 10), image_size_wh=(300, 300)),
                 build_bilateral_descriptor(pair("b", 10.1, 10.1), image_size_wh=(300, 300)),
                 build_bilateral_descriptor(pair("c", 180, 180), image_size_wh=(300, 300))]
        chosen = select_spatially_diverse(items, count=1, excluded_pair_ids={"c"})
        self.assertNotEqual(chosen[0].pair_id, "c")
        with self.assertRaises(ValueError):
            select_spatially_diverse(items[:2], count=2, duplicate_distance=.035)

    def test_baseline_sanity(self):
        result = baseline_sanity(.068)
        self.assertAlmostEqual(result["absolute_difference_m"], .002)


if __name__ == "__main__":
    unittest.main()
