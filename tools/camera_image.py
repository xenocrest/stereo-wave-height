"""One image-orientation convention for calibration, preview and WASS inputs."""
from pathlib import Path
import cv2

CANONICAL_CAMERA_IMAGE_ORIENTATION = "CONTAINER_DISPLAY_ORIENTATION_APPLIED_ONCE_V1"


def open_canonical_video(path: str | Path):
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        capture.release()
        raise ValueError(f"Cannot read video: {path}")
    if not hasattr(cv2, 'CAP_PROP_ORIENTATION_AUTO') or not capture.set(cv2.CAP_PROP_ORIENTATION_AUTO, 1):
        capture.release()
        raise ValueError("Decoder cannot explicitly honor CANONICAL_CAMERA_IMAGE_ORIENTATION")
    return capture


def orientation_metadata(capture) -> dict:
    return {"canonical_camera_image_orientation": CANONICAL_CAMERA_IMAGE_ORIENTATION,
            "source_orientation_metadata_deg": float(capture.get(cv2.CAP_PROP_ORIENTATION_META)),
            "opencv_orientation_auto": bool(capture.get(cv2.CAP_PROP_ORIENTATION_AUTO)),
            "orientation_application": "container display rotation applied once by decoder before calibration/preview; FFmpeg autorotate before WASS extraction"}


def ffmpeg_orientation_args() -> list[str]:
    return ["-autorotate"]
