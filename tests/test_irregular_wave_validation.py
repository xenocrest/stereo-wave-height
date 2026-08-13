"""Truth, coordinate, sampling and metric tests for deterministic IRR-1."""

import json
from pathlib import Path
import unittest

import numpy as np

from src.simulation.irregular_surface import WaveComponent, component_height_m, multicomponent_wave
from src.validation.irregular_wave import direct_error_metrics, freeze_nearest_grid_points, uniformly_spaced_frame_ids


class IrregularWaveValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.components = (
            WaveComponent(.015, .8, .5, 0),
            WaveComponent(.008, .5, .8, np.pi/3),
            WaveComponent(.005, 1.2, .3, -np.pi/4),
        )

    def test_formula_component_sum_and_temporal_sign(self) -> None:
        x = np.array([-.2, .1]); t = np.array([0., .4])
        manual = sum(c.amplitude_m*np.sin(2*np.pi*x[None,:]/c.wavelength_m-2*np.pi*c.frequency_hz*t[:,None]+c.phase_rad) for c in self.components)
        individual = sum(component_height_m(c, x[None,:], t[:,None]) for c in self.components)
        np.testing.assert_allclose(individual, manual, atol=1e-15)
        surface = multicomponent_wave(x, [-.1, .1], (t*1e9).astype(np.int64), components=self.components)
        np.testing.assert_allclose(surface.h_true_m[:,0,:], manual, atol=1e-15)

    def test_derived_k_omega_and_round_trip(self) -> None:
        for component in self.components:
            self.assertEqual(component.wave_number_rad_per_m, 2*np.pi/component.wavelength_m)
            self.assertEqual(component.angular_frequency_rad_per_s, 2*np.pi*component.frequency_hz)
            encoded = json.loads(json.dumps(component.to_dict()))
            self.assertEqual(WaveComponent.from_dict(encoded), component)

    def test_representative_nearest_sampling_and_alignment(self) -> None:
        points = freeze_nearest_grid_points({'P':(.105,.01)}, [-.005,.005], [0.,.02], world_minus_grid_x_m=.1)
        self.assertAlmostEqual(points[0].sampled_x_world_m, .105)
        self.assertAlmostEqual(points[0].sampled_y_world_m, 0.)
        with self.assertRaises(ValueError):
            freeze_nearest_grid_points({'P':(0.,0.)}, [0.,1.], [0.,1.], world_minus_grid_x_m=float('nan'))

    def test_direct_metrics(self) -> None:
        result = direct_error_metrics([-1., 1., 3.], [True, True, False])
        self.assertEqual(result['bias_m'], 0.)
        self.assertEqual(result['rmse_m'], 1.)
        self.assertEqual(result['mae_m'], 1.)
        self.assertEqual(result['max_abs_error_m'], 1.)

    def test_frozen_config_contains_required_values(self) -> None:
        text = (Path(__file__).parents[1]/'configs'/'simulation'/'irregular_wave_multicomponent.yaml').read_text(encoding='utf-8')
        for token in ('dynamic_frame_count: 50', 'world_minus_grid_x_m: 0.10', 'sampling_rule: nearest_grid_node', 'zgap_percentile: 99.5'):
            self.assertIn(token, text)

    def test_uniform_subset_is_exact_deterministic_unique_and_full_span(self) -> None:
        first = uniformly_spaced_frame_ids(2, 51, 10)
        second = uniformly_spaced_frame_ids(2, 51, 10)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 10)
        self.assertEqual(len(set(first)), 10)
        self.assertEqual(first[0], "000002")
        self.assertEqual(first[-1], "000051")
        self.assertNotIn("000000", first)
        self.assertNotIn("000001", first)


if __name__ == '__main__':
    unittest.main()
