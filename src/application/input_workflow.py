"""Small state model and truthful file policies for the guided input UI."""
from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

import yaml


CALIBRATION_FILE_TYPES = (("YAML 双目标定文件", "*.yaml *.yml"),)
VIDEO_FILE_TYPES = (("本地视频", "*.mp4 *.mov *.avi *.mkv *.m4v"),)
VIDEO_FORMAT_TEXT = "MP4、MOV、AVI、MKV、M4V"


@dataclass
class GuidedInputState:
    """UI-only readiness state; it never changes reconstruction parameters."""

    calibration_mode: str = "existing"
    calibration_ready: bool = False
    calibration_step_completed: bool = False
    calibration_quality_status: str = "NOT_EVALUATED"
    left_measurement_ready: bool = False
    right_measurement_ready: bool = False
    operating_mode: str = "VALIDATED_MODE"

    @property
    def measurement_ready(self) -> bool:
        return self.calibration_ready and self.left_measurement_ready and self.right_measurement_ready

    def set_mode(self, mode: str) -> None:
        if mode not in {"existing", "videos"}:
            raise ValueError("标定方式必须是 existing 或 videos")
        self.calibration_mode = mode
        self.calibration_ready = False
        self.calibration_step_completed = False

    def mark_calibration_ready(
        self,
        *,
        operating_mode: str = "VALIDATED_MODE",
        quality_status: str = "UNKNOWN",
    ) -> None:
        if operating_mode not in {"VALIDATED_MODE", "DEMO_ESTIMATION_MODE"}:
            raise ValueError("unknown calibration operating mode")
        self.calibration_ready = True
        self.calibration_step_completed = True
        self.calibration_quality_status = quality_status
        self.operating_mode = operating_mode

    def mark_calibration_failed(self) -> None:
        """Record an engineering failure that prevents a usable calibration."""
        self.calibration_ready = False
        self.calibration_step_completed = False

    def mark_measurement_video(self, side: str, ready: bool = True) -> None:
        if side == "left":
            self.left_measurement_ready = ready
        elif side == "right":
            self.right_measurement_ready = ready
        else:
            raise ValueError("相机角色必须是 left 或 right")


def validate_gui_calibration(data: dict[str, Any]) -> None:
    """Reject structurally invalid/non-finite calibration; do not apply QA gates."""
    try:
        mono0, mono1, stereo = data["mono_cam0"], data["mono_cam1"], data["stereo"]
        k0, k1 = mono0["K"], mono1["K"]
        rotation, translation = stereo["R_right_from_left"], stereo["T_right_from_left_m"]
        values = [
            *[value for row in k0 for value in row], *mono0["D"],
            *[value for row in k1 for value in row], *mono1["D"],
            *[value for row in rotation for value in row], *translation,
        ]
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("calibration is missing K0/D0/K1/D1/R/T") from error
    if any(len(matrix) != 3 or any(len(row) != 3 for row in matrix) for matrix in (k0, k1, rotation)) or len(translation) != 3:
        raise ValueError("calibration K0/K1/R must be 3x3 and T must contain three values")
    image_size = data.get("image_size_wh")
    if image_size is not None and (len(image_size) != 2 or int(image_size[0]) <= 0 or int(image_size[1]) <= 0):
        raise ValueError("calibration image size must contain two positive values")
    if not values or not all(math.isfinite(float(value)) for value in values):
        raise ValueError("calibration K/D/R/T contains NaN or Inf")

def load_calibration_selection(path: str | Path) -> tuple[dict[str, Any], Path, str]:
    """Load either a direct OpenCV calibration or an immutable package manifest."""
    selected = Path(path).resolve()
    data = yaml.safe_load(selected.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("calibration YAML root must be a mapping")
    if "mono_cam0" in data and "mono_cam1" in data and "stereo" in data:
        mode = "DEMO_ESTIMATION_MODE" if data.get("gui_operating_mode") == "DEMO_ESTIMATION_MODE" or data.get("status") == "DEMO_ONLY" else "VALIDATED_MODE"
        return data, selected, mode
    artifact = data.get("artifacts", {}).get("opencv_calibration", {})
    relative = artifact.get("path") if isinstance(artifact, dict) else None
    if not relative:
        raise ValueError("selected YAML is neither an OpenCV calibration nor a calibration package manifest")
    calibration_path = (selected.parent / str(relative)).resolve()
    if calibration_path.parent != selected.parent:
        raise ValueError("calibration package artifact must remain inside the package root")
    calibration = yaml.safe_load(calibration_path.read_text(encoding="utf-8"))
    if not isinstance(calibration, dict) or not {"mono_cam0", "mono_cam1", "stereo"} <= calibration.keys():
        raise ValueError("calibration package contains an incompatible OpenCV artifact")
    mode = "DEMO_ESTIMATION_MODE" if data.get("status") == "DEMO_ONLY" else "VALIDATED_MODE"
    calibration["package_manifest"] = str(selected)
    calibration["package_status"] = data.get("status")
    calibration["calibration_id"] = data.get("calibration_id", calibration.get("calibration_id"))
    return calibration, calibration_path, mode
