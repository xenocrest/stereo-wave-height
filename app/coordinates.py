"""Identity/compatibility metadata, not registration or scientific transforms."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.io import loadmat

from pipeline.adapters.wass import load_matrix
from pipeline.instantaneous_validation.schemas import ReferencePlane


def numeric_hash(values: dict) -> str:
    digest = hashlib.sha256()
    for key, value in sorted(values.items()):
        array = np.asarray(value, dtype="<f8")
        if not np.isfinite(array).all():
            raise ValueError("REFERENCE_FRAME_MISMATCH: nonfinite coordinate definition")
        digest.update(key.encode())
        digest.update(json.dumps(array.shape).encode())
        digest.update(array.tobytes())
    return digest.hexdigest()


def identity(run: str | Path) -> dict:
    from app.core import calibration_identity
    root = Path(run)
    config = root / "wass" / "config"
    extrinsics = numeric_hash({key: load_matrix(config / name) for key, name in
                               (("R", "ext_R.xml"), ("T", "ext_T.xml"))})
    setup = loadmat(root / "surface" / "config.mat")
    # Include the actual official alignment/scale and both camera conventions.
    keys = ("Rpl", "Tpl", "CAM_BASELINE", "Cam0toGrid", "Cam1toGrid",
            "P0cam", "P1cam", "P0plane", "P1plane", "K0", "K1")
    transform_hash = numeric_hash({key: setup[key] for key in keys})
    with np.load(next((root / "pixel" / "pixel_height").glob("*.npz")), allow_pickle=False) as data:
        units = str(data["units"])
    cal = calibration_identity(root)
    frame = hashlib.sha256(json.dumps({"calibration_id": cal, "extrinsics_id": extrinsics,
        "official_grid_transform": transform_hash, "units": units,
        "convention": "wassgridsurface_0.11_camera_mesh_to_official_grid"}, sort_keys=True).encode()).hexdigest()
    return {"calibration_id": cal, "extrinsics_id": extrinsics,
            "coordinate_frame_id": frame, "coordinate_system": f"official_wass_grid_{units}"}


@dataclass(frozen=True)
class BoundReference(ReferencePlane):
    calibration_id: str = ""
    extrinsics_id: str = ""
    coordinate_frame_id: str = ""

    def as_dict(self) -> dict:
        data = super().as_dict()
        data.update(calibration_id=self.calibration_id, extrinsics_id=self.extrinsics_id,
                    coordinate_frame_id=self.coordinate_frame_id, n=list(self.normal),
                    source=("INTERNAL_STATIC_REFERENCE" if self.mode == "designated_static_water_frame"
                            else "PROVIDED_PHYSICAL_REFERENCE"))
        return data


def bind(plane: ReferencePlane, ids: dict) -> BoundReference:
    return BoundReference(plane.plane_id, plane.normal, plane.d, plane.mode, plane.coordinate_system,
                          ids["calibration_id"], ids["extrinsics_id"], ids["coordinate_frame_id"])


def require_match(reference: ReferencePlane, ids: dict) -> None:
    for key in ("calibration_id", "extrinsics_id", "coordinate_frame_id"):
        if not getattr(reference, key, "") or getattr(reference, key) != ids[key]:
            raise ValueError(f"REFERENCE_FRAME_MISMATCH: {key} differs or is unbound")
    if reference.coordinate_system != ids["coordinate_system"]:
        raise ValueError("REFERENCE_FRAME_MISMATCH: coordinate units/convention differ")


def validate_workspace(workspace: Path, setup_path: Path) -> None:
    """Verify official camera coordinates before using a frozen grid setup."""
    setup = loadmat(setup_path)
    for key, filename in (("P0cam", "P0cam.txt"), ("P1cam", "P1cam.txt")):
        if not np.array_equal(setup[key], np.loadtxt(workspace / filename)):
            raise ValueError(f"REFERENCE_FRAME_MISMATCH: official workspace {key} changed")
    for key, filename in (("K0", "intrinsics_00000000.xml"), ("K1", "intrinsics_00000001.xml")):
        if not np.array_equal(setup[key], load_matrix(workspace / filename)):
            raise ValueError(f"REFERENCE_FRAME_MISMATCH: official workspace {key} changed")
