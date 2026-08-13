"""Pre-registered point sampling and direct irregular-wave error metrics."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt


@dataclass(frozen=True)
class RepresentativeGridPoint:
    """A world point mapped to one frozen nearest official grid node."""

    point_id: str
    requested_x_world_m: float
    requested_y_world_m: float
    x_index: int
    y_index: int
    sampled_x_world_m: float
    sampled_y_world_m: float


def freeze_nearest_grid_points(
    requested_world_xy_m: dict[str, tuple[float, float]],
    x_grid_m: npt.ArrayLike,
    y_grid_m: npt.ArrayLike,
    *,
    world_minus_grid_x_m: float,
) -> tuple[RepresentativeGridPoint, ...]:
    """Map preselected world points by nearest node; never infer the origin."""
    x_grid = np.asarray(x_grid_m, dtype=np.float64)
    y_grid = np.asarray(y_grid_m, dtype=np.float64)
    if x_grid.ndim != 1 or y_grid.ndim != 1 or not requested_world_xy_m:
        raise ValueError("grids must be one-dimensional and requested points non-empty")
    if not np.isfinite(world_minus_grid_x_m):
        raise ValueError("world_minus_grid_x_m must be explicit and finite")
    x_world = x_grid + world_minus_grid_x_m
    frozen = []
    for point_id, (requested_x, requested_y) in requested_world_xy_m.items():
        if not np.isfinite(requested_x) or not np.isfinite(requested_y):
            raise ValueError("requested world coordinates must be finite")
        xi = int(np.argmin(np.abs(x_world - requested_x)))
        yi = int(np.argmin(np.abs(y_grid - requested_y)))
        frozen.append(RepresentativeGridPoint(
            point_id, float(requested_x), float(requested_y), xi, yi,
            float(x_world[xi]), float(y_grid[yi]),
        ))
    return tuple(frozen)


def direct_error_metrics(error: npt.ArrayLike, valid_mask: npt.ArrayLike) -> dict[str, float]:
    """Compute direct signed errors without fitting, filtering, or interpolation."""
    values = np.asarray(error, dtype=np.float64)
    valid = np.asarray(valid_mask, dtype=bool)
    if values.shape != valid.shape or values.size == 0:
        raise ValueError("error and valid mask must have the same non-empty shape")
    selected = valid & np.isfinite(values)
    if not np.any(selected):
        raise ValueError("no valid finite errors")
    sample = values[selected]
    absolute = np.abs(sample)
    return {
        "bias_m": float(np.mean(sample)),
        "rmse_m": float(np.sqrt(np.mean(sample * sample))),
        "mae_m": float(np.mean(absolute)),
        "max_abs_error_m": float(np.max(absolute)),
        **{f"p{p}_abs_error_m": float(np.percentile(absolute, p)) for p in (50, 90, 95, 99)},
    }
