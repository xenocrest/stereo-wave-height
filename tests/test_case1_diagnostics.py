import numpy as np
import pytest

from src.validation.diagnostics import (
    constant_truth_difference,
    fit_plane_orthogonal,
    height_observation_support_mask,
    measurement_domain_masks,
    raw_point_support,
    spatial_error_statistics,
    verify_grid_alignment,
    wass_zgap_percentile,
)


def test_constant_truth_exactness() -> None:
    static = np.zeros((3, 4))
    difference = constant_truth_difference(static, static + 0.010)
    assert np.array_equal(difference, np.full((3, 4), 0.010))


def test_plane_distance_sign() -> None:
    x, y = np.meshgrid(np.linspace(-1, 1, 5), np.linspace(-1, 1, 6))
    static = np.column_stack((x.ravel(), y.ravel(), np.zeros(x.size)))
    raised = static.copy()
    raised[:, 2] += 0.010
    static_fit = fit_plane_orthogonal(static)
    raised_fit = fit_plane_orthogonal(raised)
    assert raised_fit.z_at_origin - static_fit.z_at_origin == pytest.approx(0.010)


def test_support_density_accounting() -> None:
    x = np.array([0.0, 1.0])
    y = np.array([0.0, 1.0])
    points = np.array([[0.0, 0.0], [0.1, 0.1], [1.0, 1.0], [4.0, 4.0]])
    result = raw_point_support(points, x, y)
    assert result.total_input_points == 4
    assert result.in_grid_points == 3
    assert result.counts.tolist() == [[2, 0], [0, 1]]
    assert result.supported_cell_ratio == pytest.approx(0.5)
    assert result.observation_mask.tolist() == [[True, False], [False, True]]


def test_height_support_requires_dynamic_and_static_observation() -> None:
    static = np.array([[[True, False], [False, True]], [[False, True], [False, True]]])
    dynamic = np.array([[[True, True], [True, False]]])
    mask = height_observation_support_mask(dynamic, static)
    assert mask.tolist() == [[[True, True], [False, False]]]


def test_grid_finite_does_not_imply_raw_observation() -> None:
    dynamic = np.array([[[True, False]]])
    static = np.array([[[True, True]]])
    finite = np.ones((1, 1, 2), dtype=bool)
    quality = np.ones_like(finite)
    masks = measurement_domain_masks(dynamic, static, finite, quality)
    assert masks.reconstructed_by_gridder.tolist() == [[[True, True]]]
    assert masks.raw_observed.tolist() == [[[True, False]]]
    assert masks.validation_eligible.tolist() == [[[True, False]]]


def test_eligible_domain_requires_coordinate_quality() -> None:
    support = np.ones((1, 1, 2), dtype=bool)
    quality = np.array([[[True, False]]])
    masks = measurement_domain_masks(support, support, support, quality)
    assert masks.validation_eligible.tolist() == [[[True, False]]]


def test_wass_zgap_percentile_uses_sorted_floor_index() -> None:
    gaps = np.arange(1.0, 101.0)
    # floor(0.99 * 100) == 99, matching the source's zero-based index.
    assert wass_zgap_percentile(gaps, 99.0) == 100.0


def test_spatial_error_percentiles() -> None:
    error = np.arange(100, dtype=float).reshape(1, 10, 10) / 1000.0
    result = spatial_error_statistics(error, np.ones_like(error, dtype=bool))
    assert result.absolute_percentiles[50] == pytest.approx(0.0495)
    assert result.absolute_percentiles[90] == pytest.approx(0.0891)
    assert result.maximum_index == (0, 9, 9)


def test_grid_alignment_verification() -> None:
    x = np.array([0.0, 0.1])
    y = np.array([-0.1, 0.0])
    verify_grid_alignment(x, y, x.copy(), y.copy())
    with pytest.raises(ValueError, match="x grids differ"):
        verify_grid_alignment(x, y, x + 0.01, y)
