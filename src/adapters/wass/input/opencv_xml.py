"""Write the OpenCV XML matrix schema observed in the local WASS runtime."""

from __future__ import annotations

from dataclasses import dataclass
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


def write_opencv_matrix_xml(path: str | Path, matrix: npt.ArrayLike) -> Path:
    """Write a finite float64 matrix under the confirmed ``intrinsics_penne`` node."""
    values = np.asarray(matrix, dtype=np.float64)
    if values.ndim != 2 or values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("OpenCV matrix must be a non-empty finite 2-D array")
    root = ET.Element("opencv_storage")
    node = ET.SubElement(root, "intrinsics_penne", {"type_id": "opencv-matrix"})
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
