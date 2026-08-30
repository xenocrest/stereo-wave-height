"""Small state model and truthful file policies for the guided input UI."""
from __future__ import annotations

from dataclasses import dataclass


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

    @property
    def measurement_ready(self) -> bool:
        return self.calibration_ready and self.left_measurement_ready and self.right_measurement_ready

    def set_mode(self, mode: str) -> None:
        if mode not in {"existing", "videos"}:
            raise ValueError("标定方式必须是 existing 或 videos")
        self.calibration_mode = mode
        self.calibration_ready = False

    def mark_calibration_ready(self) -> None:
        self.calibration_ready = True

    def mark_measurement_video(self, side: str, ready: bool = True) -> None:
        if side == "left":
            self.left_measurement_ready = ready
        elif side == "right":
            self.right_measurement_ready = ready
        else:
            raise ValueError("相机角色必须是 left 或 right")

