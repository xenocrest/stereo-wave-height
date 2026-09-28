from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

import numpy as np
import yaml

PROVENANCE = {0: "NO_DATA", 1: "DIRECT_STEREO", 2: "OFFICIAL_GRID_ESTIMATE"}


@dataclass(frozen=True)
class ReferencePlane:
    plane_id: str
    normal: tuple[float, float, float]
    d: float
    mode: str
    coordinate_system: str

    def height(self, xyz: np.ndarray) -> np.ndarray:
        return np.asarray(xyz, dtype=float) @ np.asarray(self.normal) + self.d

    def as_dict(self) -> dict:
        return {"reference_plane_id": self.plane_id, "normal": list(self.normal), "d": self.d,
                "mode": self.mode, "coordinate_system": self.coordinate_system,
                "equation": "H = n^T P + d; n has unit length"}


def _normalize(normal: list[float], d: float) -> tuple[tuple[float, float, float], float]:
    n = np.asarray(normal, dtype=float)
    if n.shape != (3,) or not np.isfinite(n).all() or not np.isfinite(d):
        raise ValueError("reference plane coefficients must be finite n[3], d")
    norm = float(np.linalg.norm(n))
    if norm <= 0:
        raise ValueError("reference plane normal must be nonzero")
    n /= norm
    if n[2] < 0:
        n = -n
        d = -d
    return tuple(float(x) for x in n), float(d / norm)


def reference_from_config(config: dict, run_dir: str | Path) -> ReferencePlane:
    mode = config.get("mode")
    root = Path(run_dir)
    coordinate_system = config.get("coordinate_system")
    if not coordinate_system:
        raise ValueError("reference.coordinate_system is required; physical plane must be registered to official gridded XYZ")
    if mode == "provided_physical_plane":
        n, d = _normalize([config[key] for key in ("n_x", "n_y", "n_z")], float(config["d"]))
    elif mode == "designated_static_water_frame":
        frame_id = int(config["reference_frame_id"])
        path = root / "pixel" / "pixel_height" / f"{frame_id:08d}.npz"
        if not path.is_file():
            raise FileNotFoundError(path)
        with np.load(path, allow_pickle=False) as data:
            xyz, source = data["xyz"], data["source"]
            valid = (source != 0) & np.isfinite(xyz).all(axis=2)
            points = xyz[valid]
        if len(points) < 6:
            raise ValueError("designated static water frame has fewer than six usable grid points")
        step = max(1, len(points) // 100_000)
        sample = points[::step]
        if np.linalg.matrix_rank(np.column_stack((sample[:, :2], np.ones(len(sample))))) < 3:
            raise ValueError("static reference has degenerate XY geometry")
        slope_x, slope_y, intercept = np.linalg.lstsq(
            np.column_stack((sample[:, :2], np.ones(len(sample)))), sample[:, 2], rcond=None
        )[0]
        n, d = _normalize([-slope_x, -slope_y, 1.0], -intercept)
    else:
        raise ValueError("reference.mode must be provided_physical_plane or designated_static_water_frame")
    identity = hashlib.sha256(json.dumps({"mode": mode, "n": n, "d": d, "coordinate_system": coordinate_system,
                                        "reference_frame_id": config.get("reference_frame_id")}, sort_keys=True).encode()).hexdigest()[:16]
    default_id = f"INTERNAL_STATIC_REFERENCE_{identity}" if mode == "designated_static_water_frame" else f"physical_ref_{identity}"
    return ReferencePlane(config.get("reference_plane_id", default_id), n, d, mode, coordinate_system)


def read_yaml(path: str | Path) -> dict:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"YAML must contain a mapping: {path}")
    return data
