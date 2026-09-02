"""Small state model and truthful file policies for the guided input UI."""
from __future__ import annotations

from dataclasses import dataclass
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

    def mark_calibration_ready(self, *, operating_mode: str = "VALIDATED_MODE") -> None:
        if operating_mode not in {"VALIDATED_MODE", "DEMO_ESTIMATION_MODE"}:
            raise ValueError("unknown calibration operating mode")
        self.calibration_ready = True
        self.operating_mode = operating_mode

    def mark_calibration_failed(self) -> None:
        """Expose QA failure without allowing measurement to start."""
        self.calibration_ready = False

    def mark_measurement_video(self, side: str, ready: bool = True) -> None:
        if side == "left":
            self.left_measurement_ready = ready
        elif side == "right":
            self.right_measurement_ready = ready
        else:
            raise ValueError("相机角色必须是 left 或 right")


def load_calibration_selection(path: str | Path) -> tuple[dict[str, Any], Path, str]:
    """Load either a direct OpenCV calibration or an immutable package manifest."""
    selected = Path(path).resolve()
    data = yaml.safe_load(selected.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("calibration YAML root must be a mapping")
    if "mono_cam0" in data and "mono_cam1" in data and "stereo" in data:
        mode = "DEMO_ESTIMATION_MODE" if data.get("status") == "DEMO_ONLY" else "VALIDATED_MODE"
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
