"""Write the OpenCV XML matrix schema observed in the local WASS runtime."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
import numpy.typing as npt


@dataclass(frozen=True)
class OpenCvMatrixSchema:
    """Observed structural metadata for one OpenCV XML matrix."""

    root_tag: str
    node_name: str
    rows: int
    cols: int
    data_type: str


def write_opencv_matrix_xml(
    path: str | Path, matrix: npt.ArrayLike, *, node_name: str = "intrinsics_penne"
) -> Path:
    """Write a finite float64 matrix under an explicit OpenCV node name."""
    values = np.asarray(matrix, dtype=np.float64)
    if values.ndim != 2 or values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("OpenCV matrix must be a non-empty finite 2-D array")
    root = ET.Element("opencv_storage")
    if not node_name or not node_name.replace("_", "").isalnum():
        raise ValueError("node_name must be a non-empty XML-safe identifier")
    node = ET.SubElement(root, node_name, {"type_id": "opencv-matrix"})
    ET.SubElement(node, "rows").text = str(values.shape[0])
    ET.SubElement(node, "cols").text = str(values.shape[1])
    ET.SubElement(node, "dt").text = "d"
    ET.SubElement(node, "data").text = "\n    " + " ".join(f"{value:.17g}" for value in values.ravel()) + "\n  "
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(destination, encoding="utf-8", xml_declaration=True)
    return destination


def write_wass_calibration_xml(
    output_dir: str | Path,
    *,
    intrinsic_00: npt.ArrayLike,
    intrinsic_01: npt.ArrayLike,
    distortion_00: npt.ArrayLike,
    distortion_01: npt.ArrayLike,
) -> tuple[Path, ...]:
    """Write the four WASS calibration XML files without estimating calibration."""
    directory = Path(output_dir)
    matrices = (
        ("intrinsics_00.xml", np.asarray(intrinsic_00, dtype=np.float64)),
        ("intrinsics_01.xml", np.asarray(intrinsic_01, dtype=np.float64)),
        ("distortion_00.xml", np.asarray(distortion_00, dtype=np.float64).reshape(-1, 1)),
        ("distortion_01.xml", np.asarray(distortion_01, dtype=np.float64).reshape(-1, 1)),
    )
    if matrices[0][1].shape != (3, 3) or matrices[1][1].shape != (3, 3):
        raise ValueError("intrinsic matrices must have shape [3,3]")
    if matrices[2][1].shape != (5, 1) or matrices[3][1].shape != (5, 1):
        raise ValueError("distortion vectors must have five coefficients")
    return tuple(write_opencv_matrix_xml(directory / name, matrix) for name, matrix in matrices)


def write_wass_fixed_calibration(
    output_dir: str | Path,
    *,
    intrinsic_00: npt.ArrayLike,
    intrinsic_01: npt.ArrayLike,
    distortion_00: npt.ArrayLike,
    distortion_01: npt.ArrayLike,
    rotation_01: npt.ArrayLike,
    translation_01_m: npt.ArrayLike,
    approved_for_wass: bool,
    source: str,
) -> tuple[Path, ...]:
    """Export a quality-approved OpenCV fixed calibration for WASS 1.11.

    R/T use ``X_cam1 = R_01 X_cam0 + T_01``. WASS reads this direction but
    normalizes the translation norm to one internally; the metric baseline is
    therefore retained in the sidecar for the established scale stage.
    """
    if not approved_for_wass:
        raise ValueError("quality gate must approve calibration before WASS export")
    if not source:
        raise ValueError("calibration source is required")
    rotation = np.asarray(rotation_01, dtype=np.float64)
    translation = np.asarray(translation_01_m, dtype=np.float64).reshape(-1, 1)
    if rotation.shape != (3, 3) or translation.shape != (3, 1):
        raise ValueError("WASS fixed extrinsics require R[3,3] and T[3,1]")
    if not np.all(np.isfinite(rotation)) or not np.all(np.isfinite(translation)):
        raise ValueError("WASS fixed extrinsics must be finite")
    baseline = float(np.linalg.norm(translation))
    if baseline <= 0 or not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-8):
        raise ValueError("WASS fixed extrinsics require a valid rotation and positive baseline")
    directory = Path(output_dir)
    files = list(write_wass_calibration_xml(
        directory, intrinsic_00=intrinsic_00, intrinsic_01=intrinsic_01,
        distortion_00=distortion_00, distortion_01=distortion_01,
    ))
    files.append(write_opencv_matrix_xml(directory / "ext_R.xml", rotation, node_name="ext_R"))
    files.append(write_opencv_matrix_xml(directory / "ext_T.xml", translation, node_name="ext_T"))
    metadata = directory / "fixed_calibration_provenance.json"
    metadata.write_text(json.dumps({
        "schema_version": "1.0",
        "approved_for_wass": True,
        "source": source,
        "camera_roles": {"cam0": "left", "cam1": "right"},
        "extrinsic_convention": "X_cam1 = R_01 @ X_cam0 + T_01_m",
        "translation_input_unit": "m",
        "baseline_m": baseline,
        "wass_internal_scale_behavior": "T direction retained; norm rescaled to 1.0 by wass_stereo 1.11",
        "metric_scale_requirement": "use established WASS physical scale recovery; ext_T alone does not guarantee metric xyzC",
        "autocalibrate_required": False,
    }, indent=2) + "\n", encoding="utf-8")
    files.append(metadata)
    return tuple(files)


def write_wass_coarse_fixed_calibration(
    output_dir: str | Path,
    *,
    intrinsic_00: npt.ArrayLike,
    intrinsic_01: npt.ArrayLike,
    distortion_00: npt.ArrayLike,
    distortion_01: npt.ArrayLike,
    rotation_01: npt.ArrayLike,
    translation_01_m: npt.ArrayLike,
    coarse_fixed_calibration_allowed: bool,
    metrological_validity: bool,
    purpose: str,
    source: str,
) -> tuple[Path, ...]:
    """Export an explicit non-metrological fixed calibration for closure tests.

    This is intentionally separate from :func:`write_wass_fixed_calibration`:
    a coarse candidate remains unapproved for metrology and may only be used
    for ``ALGORITHM_CLOSURE_VALIDATION_ONLY`` without autocalibration.
    """
    if not coarse_fixed_calibration_allowed:
        raise ValueError("coarse fixed-calibration export must be explicitly allowed")
    if metrological_validity:
        raise ValueError("coarse fixed calibration can never be metrically valid")
    if purpose != "ALGORITHM_CLOSURE_VALIDATION_ONLY":
        raise ValueError("coarse fixed calibration purpose must be ALGORITHM_CLOSURE_VALIDATION_ONLY")
    if not source:
        raise ValueError("coarse calibration source is required")

    rotation = np.asarray(rotation_01, dtype=np.float64)
    translation = np.asarray(translation_01_m, dtype=np.float64).reshape(-1, 1)
    if rotation.shape != (3, 3) or translation.shape != (3, 1):
        raise ValueError("WASS fixed extrinsics require R[3,3] and T[3,1]")
    if not np.all(np.isfinite(rotation)) or not np.all(np.isfinite(translation)):
        raise ValueError("WASS fixed extrinsics must be finite")
    baseline = float(np.linalg.norm(translation))
    if baseline <= 0 or not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-8):
        raise ValueError("WASS fixed extrinsics require a valid rotation and positive baseline")

    directory = Path(output_dir)
    files = list(write_wass_calibration_xml(
        directory, intrinsic_00=intrinsic_00, intrinsic_01=intrinsic_01,
        distortion_00=distortion_00, distortion_01=distortion_01,
    ))
    files.append(write_opencv_matrix_xml(directory / "ext_R.xml", rotation, node_name="ext_R"))
    files.append(write_opencv_matrix_xml(directory / "ext_T.xml", translation, node_name="ext_T"))
    metadata = directory / "fixed_calibration_provenance.json"
    metadata.write_text(json.dumps({
        "schema_version": "1.0",
        "approved_for_wass": False,
        "coarse_fixed_calibration_allowed": True,
        "metrological_validity": False,
        "purpose": purpose,
        "source": source,
        "camera_roles": {"cam0": "left", "cam1": "right"},
        "extrinsic_convention": "X_cam1 = R_01 @ X_cam0 + T_01_m",
        "translation_input_unit": "m",
        "baseline_m": baseline,
        "wass_internal_scale_behavior": "T direction retained; norm rescaled to 1.0 by wass_stereo 1.11",
        "metric_scale_requirement": "coarse closure only; this export is not a metric calibration approval",
        "autocalibrate_required": False,
    }, indent=2) + "\n", encoding="utf-8")
    files.append(metadata)
    return tuple(files)


def inspect_opencv_matrix_schema(path: str | Path) -> OpenCvMatrixSchema:
    """Read structural fields for comparison; numeric calibration is not interpreted."""
    root = ET.parse(path).getroot()
    children = list(root)
    if len(children) != 1:
        raise ValueError("expected exactly one OpenCV matrix node")
    node = children[0]
    if node.attrib.get("type_id") != "opencv-matrix":
        raise ValueError("matrix type_id must be opencv-matrix")
    return OpenCvMatrixSchema(
        root_tag=root.tag,
        node_name=node.tag,
        rows=int(node.findtext("rows", "-1")),
        cols=int(node.findtext("cols", "-1")),
        data_type=node.findtext("dt", ""),
    )
