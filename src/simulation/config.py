"""Load simulation-nominal camera parameters from candidate equipment YAML.

The project intentionally has no general YAML dependency. This module uses a
strict indentation/path extractor for the scalar fields required from the
current project-owned schema. Unsupported or missing values fail explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt


FloatArray = npt.NDArray[np.float64]


def _parse_scalar(value: str) -> Any:
    stripped = value.strip()
    if stripped == "null":
        return None
    if stripped in {"true", "false"}:
        return stripped == "true"
    if (stripped.startswith('"') and stripped.endswith('"')) or (
        stripped.startswith("'") and stripped.endswith("'")
    ):
        return stripped[1:-1]
    try:
        return int(stripped)
    except ValueError:
        try:
            return float(stripped)
        except ValueError:
            return stripped


def _extract_scalar_paths(path: Path) -> dict[tuple[str, ...], Any]:
    """Extract scalar mapping paths from the repository's simple YAML schema."""
    if not path.is_file():
        raise FileNotFoundError(path)
    result: dict[tuple[str, ...], Any] = {}
    parents: list[tuple[int, str]] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if "\t" in raw_line:
            raise ValueError(f"tabs are not allowed in equipment YAML (line {line_number})")
        stripped = raw_line.strip()
        if stripped.startswith("-"):
            continue  # Lists are outside the scalar camera fields used here.
        if ":" not in stripped:
            raise ValueError(f"unsupported YAML line {line_number}: {stripped!r}")
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        key, value = stripped.split(":", 1)
        while parents and parents[-1][0] >= indent:
            parents.pop()
        current_path = tuple(item[1] for item in parents) + (key.strip(),)
        if value.strip():
            if current_path in result:
                raise ValueError(f"duplicate YAML field {'.'.join(current_path)}")
            result[current_path] = _parse_scalar(value)
        else:
            parents.append((indent, key.strip()))
    return result


def _required(values: dict[tuple[str, ...], Any], *path: str) -> Any:
    key = tuple(path)
    if key not in values or values[key] is None:
        raise ValueError(f"required equipment field {'.'.join(path)} is missing or UNKNOWN")
    return values[key]


@dataclass(frozen=True)
class CandidateCameraParameters:
    """Candidate physical parameters read from the equipment registry."""

    model: str
    width_px: int
    height_px: int
    pixel_size_um: float
    focal_length_mm: float
    camera_status: str
    lens_status: str
    source_path: Path

    def __post_init__(self) -> None:
        if self.width_px <= 0 or self.height_px <= 0:
            raise ValueError("candidate resolution must be positive")
        if self.pixel_size_um <= 0 or self.focal_length_mm <= 0:
            raise ValueError("candidate pixel size and focal length must be positive")
        if self.camera_status != "candidate" or self.lens_status != "candidate":
            raise ValueError("this simulation loader requires explicitly candidate equipment status")


@dataclass(frozen=True)
class NominalIntrinsics:
    """Ideal pinhole intrinsics for simulation, never a calibrated result."""

    equipment: CandidateCameraParameters
    fx_px: float
    fy_px: float
    cx_px: float
    cy_px: float
    distortion: FloatArray
    status: str = "SIMULATION_NOMINAL"
    principal_point_status: str = "simulation_assumption"
    distortion_status: str = "ideal_simulation_assumption"

    @property
    def matrix(self) -> FloatArray:
        """Return the 3x3 simulation-nominal intrinsic matrix."""
        return np.array(
            [[self.fx_px, 0.0, self.cx_px], [0.0, self.fy_px, self.cy_px], [0.0, 0.0, 1.0]],
            dtype=np.float64,
        )


def load_nominal_intrinsics(equipment_yaml: str | Path) -> NominalIntrinsics:
    """Read candidate equipment YAML and derive ideal nominal intrinsics."""
    path = Path(equipment_yaml)
    values = _extract_scalar_paths(path)
    equipment = CandidateCameraParameters(
        model=str(_required(values, "camera", "model")),
        width_px=int(_required(values, "camera", "resolution", "width_px")),
        height_px=int(_required(values, "camera", "resolution", "height_px")),
        pixel_size_um=float(_required(values, "camera", "pixel_size", "value_um")),
        focal_length_mm=float(_required(values, "lens", "focal_length_mm")),
        camera_status=str(_required(values, "camera", "status")),
        lens_status=str(_required(values, "lens", "status")),
        source_path=path.resolve(),
    )
    pixel_size_mm = equipment.pixel_size_um * 1e-3
    focal_px = equipment.focal_length_mm / pixel_size_mm
    return NominalIntrinsics(
        equipment=equipment,
        fx_px=focal_px,
        fy_px=focal_px,
        cx_px=(equipment.width_px - 1) / 2.0,
        cy_px=(equipment.height_px - 1) / 2.0,
        distortion=np.zeros(5, dtype=np.float64),
    )
