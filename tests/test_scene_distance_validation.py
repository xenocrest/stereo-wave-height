"""Controlled scene-distance theory and contract tests."""

from pathlib import Path
import unittest

from src.validation import freeze_nearest_grid_points
from src.validation.scene_distance import min_mean_max, scene_distance_theory


class SceneDistanceValidationTests(unittest.TestCase):
    def theory(self, distance: float):
        return scene_distance_theory(distance, amplitude_m=.03, focal_px=2318.840579710145,
            baseline_m=.2, image_width_px=2448, minimum_disparity_px=160,
            maximum_disparity_px=320, required_common_width_m=1.59)

    def test_disparity_decreases_and_sensitivity_increases_quadratically(self) -> None:
        near,far=self.theory(1.75),self.theory(2.5)
        self.assertGreater(near.nominal_disparity_px,far.nominal_disparity_px)
        self.assertAlmostEqual(far.sensitivity_m_per_px/near.sensitivity_m_per_px,(2.5/1.75)**2)

    def test_full_wave_disparity_bounds(self) -> None:
        result=self.theory(2.5)
        self.assertLess(result.min_disparity_px,result.nominal_disparity_px)
        self.assertGreater(result.max_disparity_px,result.nominal_disparity_px)
        self.assertTrue(result.disparity_range_pass)

    def test_rejected_candidate_reasons(self) -> None:
        self.assertFalse(self.theory(1.5).common_fov_pass)
        self.assertFalse(self.theory(3.0).disparity_range_pass)

    def test_fixed_world_points_and_explicit_alignment(self) -> None:
        requested={'P1':(.005,-.005),'P2':(-.595,-.005)}
        a=freeze_nearest_grid_points(requested,[-.095,-.085],[-.005,.005],world_minus_grid_x_m=.1)
        b=freeze_nearest_grid_points(requested,[-.095,-.085],[-.005,.005],world_minus_grid_x_m=.1)
        self.assertEqual(a,b)
        with self.assertRaises(ValueError):
            freeze_nearest_grid_points(requested,[0,1],[0,1],world_minus_grid_x_m=float('nan'))

    def test_aggregation_and_frozen_config(self) -> None:
        self.assertEqual(min_mean_max([1,2,3]),{'min':1.,'mean':2.,'max':3.})
        text=(Path(__file__).parents[1]/'configs'/'simulation'/'scene_distance_validation.yaml').read_text(encoding='utf-8')
        for token in ('D1: 1.75','D0: 2.00','D2: 2.50','rule: all_dynamic_only','world_minus_grid_x_m: 0.10'):
            self.assertIn(token,text)


if __name__=='__main__': unittest.main()
