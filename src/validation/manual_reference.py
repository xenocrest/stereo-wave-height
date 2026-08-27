"""Manual reference-point metadata for downstream physical validation only."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

import yaml


VALIDATION_COORDINATE_SYSTEM = "wass_rectified_computational_cam0__input_right"


@dataclass(frozen=True)
class FrozenReferenceFrame:
    """Identity of one exported image tied to a frozen reconstruction result."""

    label: str
    target_time_s: float
    cam1_frame_id: str
    cam1_pts_s: float
    canonical_rotation_deg: int
    image_sha256: str
    width_px: int
    height_px: int
    coordinate_system: str


def file_sha256(path: str | Path) -> str:
    """Hash an exported reference without modifying it."""
    digest = sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def require_direct_validation_coordinates(
    *, source_coordinate_system: str, target_coordinate_system: str, source_size: tuple[int, int], target_size: tuple[int, int]
) -> None:
    """Allow direct clicks only for identical coordinate systems and sizes.

    This deliberately rejects resolution scaling, homographies and raw/canonical
    pixels that lack a verified mapping to the frozen pixel–XYZ coordinates.
    """
    if source_coordinate_system != target_coordinate_system:
        raise ValueError("CAM1_VALIDATION_PIXEL_MAPPING_NOT_AVAILABLE")
    if source_size != target_size:
        raise ValueError("unverified resolution scaling is forbidden")


def serialize_confirmed_point(
    points_file: str | Path,
    *,
    label: str,
    u_px: int,
    v_px: int,
    image_width_px: int,
    image_height_px: int,
) -> None:
    """Persist one user-confirmed click while preserving uncertainty as manual input."""
    if label not in {"static", "wave"}:
        raise ValueError("label must be static or wave")
    if not (0 <= u_px < image_width_px and 0 <= v_px < image_height_px):
        raise ValueError("clicked pixel lies outside the reference image")
    path = Path(points_file)
    document: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    record = document[label]
    require_direct_validation_coordinates(
        source_coordinate_system=str(record["source_coordinate_system"]),
        target_coordinate_system=str(document["frozen_pixel_xyz_coordinate_system"]),
        source_size=(int(record["image_width_px"]), int(record["image_height_px"])),
        target_size=(image_width_px, image_height_px),
    )
    record["clicked_pixel"] = {"u_px": int(u_px), "v_px": int(v_px)}
    record["confirmed_by_user"] = True
    # pixel_uncertainty_px is intentionally untouched: only the user may set it.
    path.write_text(yaml.safe_dump(document, sort_keys=False, allow_unicode=True), encoding="utf-8")

