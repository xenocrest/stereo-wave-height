import numpy as np
import pytest

from src.validation.diagnostics import (
    constant_truth_difference,
    fit_plane_orthogonal,
    raw_point_support,
    spatial_error_statistics,
    verify_grid_alignment,
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
