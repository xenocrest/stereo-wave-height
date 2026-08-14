"""Controlled baseline-theory and frozen-contract tests."""

from pathlib import Path
import unittest

from src.validation import baseline_theory, freeze_nearest_grid_points, min_mean_max


class BaselineValidationTests(unittest.TestCase):
    def theory(self, baseline: float):
        return baseline_theory(
            baseline, distance_m=2.0, amplitude_m=.03,
            focal_px=2318.840579710145, image_width_px=2448,
            minimum_disparity_px=160, maximum_disparity_px=320,
            required_common_width_m=1.59, minimum_triangulation_angle_deg=3,
        )

    def test_disparity_is_linear_and_sensitivity_inverse_in_baseline(self) -> None:
        small, large = self.theory(.15), self.theory(.25)
        self.assertAlmostEqual(large.nominal_disparity_px / small.nominal_disparity_px, .25/.15)
        self.assertAlmostEqual(large.sensitivity_m_per_px / small.sensitivity_m_per_px, .15/.25)

    def test_full_wave_bounds_and_candidate_contract(self) -> None:
        for baseline in (.15, .20, .25):
            theory = self.theory(baseline)
            self.assertTrue(theory.disparity_range_pass)
            self.assertTrue(theory.common_fov_pass)
            self.assertTrue(theory.triangulation_angle_pass)

    def test_outer_candidates_explain_frozen_selection(self) -> None:
        self.assertFalse(self.theory(.10).disparity_range_pass)
        self.assertFalse(self.theory(.30).disparity_range_pass)

    def test_shared_world_points_and_explicit_alignment(self) -> None:
        requested = {'P1':(.005,-.005), 'P2':(-.595,-.005)}
        frozen = freeze_nearest_grid_points(
            requested, [-.095,-.085], [-.005,.005], world_minus_grid_x_m=.1,
        )
        self.assertEqual(frozen[0].sampled_x_world_m, .0050000000000000044)
        with self.assertRaises(ValueError):
            freeze_nearest_grid_points(requested, [0,1], [0,1], world_minus_grid_x_m=float('nan'))

    def test_metrics_aggregation_and_frozen_config(self) -> None:
        self.assertEqual(min_mean_max([1,2,3]), {'min':1., 'mean':2., 'max':3.})
        text = (Path(__file__).parents[1] / 'configs/simulation/baseline_validation.yaml').read_text(encoding='utf-8')
        for token in ('B1: 0.15', 'B0: 0.20', 'B2: 0.25', 'rule: all_dynamic_only', 'world_minus_grid_x_m = baseline_m / 2'):
            self.assertIn(token, text)


if __name__ == '__main__':
    unittest.main()
