"""Ideal point-sampled grayscale imaging for synthetic stereo observations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt
from PIL import Image

from .texture import PlanarRandomTexture
from .virtual_camera import VirtualPinholeCamera


UInt8Array = npt.NDArray[np.uint8]
BoolArray = npt.NDArray[np.bool_]


@dataclass(frozen=True)
class RenderedImage:
    """One ideal grayscale view and the pixels populated by surface samples."""

    image: UInt8Array
    valid_mask: BoolArray
    projected_sample_count: int
    encoding: str = "mono8"


def render_surface(
    camera: VirtualPinholeCamera,
    points_world_m: npt.ArrayLike,
    texture: PlanarRandomTexture,
    *,
    splat_radius_px: int = 1,
    background_intensity: int = 0,
) -> RenderedImage:
    """Project textured points and resolve collisions with a nearest-depth buffer.

    The finite pixel splat is a rasterisation setting, not an optical, lighting,
    reflectance, noise, matching, or reconstruction model.
    """
    points = np.asarray(points_world_m, dtype=np.float64)
    if points.shape != (*texture.intensity.shape, 3):
        raise ValueError("points_world_m must have shape [y,x,3] matching texture")
    if not isinstance(splat_radius_px, (int, np.integer)) or splat_radius_px < 0:
        raise ValueError("splat_radius_px must be a non-negative integer")
    if not isinstance(background_intensity, (int, np.integer)) or not 0 <= background_intensity <= 255:
        raise ValueError("background_intensity must be an integer in [0,255]")

    pixels, depth = camera.project(
        points, coordinate_system="world_water_surface", unit="m"
    )
    base_u = np.rint(pixels[..., 0]).astype(np.int64).ravel()
    base_v = np.rint(pixels[..., 1]).astype(np.int64).ravel()
    depth_flat = depth.ravel()
    intensity_flat = texture.intensity.ravel()

    offsets = np.arange(-splat_radius_px, splat_radius_px + 1, dtype=np.int64)
    du, dv = np.meshgrid(offsets, offsets)
    repeat = du.size
    u = (base_u[:, None] + du.ravel()).reshape(-1)
    v = (base_v[:, None] + dv.ravel()).reshape(-1)
    z = np.repeat(depth_flat, repeat)
    values = np.repeat(intensity_flat, repeat)

    width = camera.intrinsics.equipment.width_px
    height = camera.intrinsics.equipment.height_px
    inside = (u >= 0) & (u < width) & (v >= 0) & (v < height)
    u, v, z, values = u[inside], v[inside], z[inside], values[inside]

    image = np.full((height, width), background_intensity, dtype=np.uint8)
    valid = np.zeros((height, width), dtype=bool)
    if u.size:
        flat_index = v * width + u
        order = np.lexsort((z, flat_index))
        sorted_index = flat_index[order]
        first = np.concatenate(([True], sorted_index[1:] != sorted_index[:-1]))
        selected = order[first]
        image.ravel()[flat_index[selected]] = values[selected]
        valid.ravel()[flat_index[selected]] = True

    return RenderedImage(image, valid, int(np.count_nonzero(inside)))


def save_grayscale_png(path: str | Path, image: npt.ArrayLike) -> Path:
    """Save a two-dimensional uint8 array as an 8-bit grayscale PNG."""
    array = np.asarray(image)
    if array.ndim != 2 or array.dtype != np.uint8:
        raise ValueError("PNG image must be a two-dimensional uint8 array")
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(array, mode="L").save(destination, format="PNG")
    return destination

