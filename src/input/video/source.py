"""General recorded-video source producing canonical stereo frame pairs."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

import numpy as np

from ..models import StereoFramePair, VideoMetadata


class VideoBackend(Protocol):
    """Minimal backend contract; decoders remain replaceable dependencies."""

    def probe(self, path: Path) -> VideoMetadata: ...

    def read_frame(self, path: Path, frame_index: int) -> Any: ...


class OpenCVVideoBackend:
    """Optional OpenCV backend, imported only when explicitly used."""

    @staticmethod
    def _cv2():
        try:
            import cv2
        except ImportError as error:
            raise RuntimeError(
                "OpenCV video support is not installed; install a reviewed video backend "
                "before reading real files"
            ) from error
        return cv2

    def probe(self, path: Path) -> VideoMetadata:
        cv2 = self._cv2()
        source = Path(path)
        if not source.is_file():
            raise FileNotFoundError(source)
        capture = cv2.VideoCapture(str(source))
        try:
            if not capture.isOpened():
                raise ValueError(f"video backend cannot open {source}")
            width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = float(capture.get(cv2.CAP_PROP_FPS))
        finally:
            capture.release()
        if not np.isfinite(fps) or fps <= 0:
            raise ValueError("video backend did not report a known positive fps")
        return VideoMetadata(source.resolve(), width, height, count, fps, count/fps, "container_fps_index")

    def read_frame(self, path: Path, frame_index: int) -> Any:
        if frame_index < 0:
            raise IndexError("frame_index must be non-negative")
        cv2 = self._cv2()
        capture = cv2.VideoCapture(str(path))
        try:
            if not capture.isOpened():
                raise ValueError(f"video backend cannot open {path}")
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = capture.read()
        finally:
            capture.release()
        if not ok or frame is None:
            raise IndexError(f"cannot decode frame {frame_index} from {path}")
        return frame


class StereoVideoSource:
    """Two recorded files with explicit frame indices and timestamp provenance."""

    def __init__(self, left_path: str | Path, right_path: str | Path, *, backend: VideoBackend) -> None:
        self.backend = backend
        self.left = backend.probe(Path(left_path))
        self.right = backend.probe(Path(right_path))

    @staticmethod
    def _timestamp(index: int, metadata: VideoMetadata) -> float:
        if index < 0 or index >= metadata.frame_count:
            raise IndexError("frame index outside video")
        return float(index / metadata.fps)

    def frame_pair(self, pair_id: int, left_index: int, right_index: int) -> StereoFramePair:
        """Decode an explicitly selected pair without assuming synchronization."""
        left_time = self._timestamp(left_index, self.left)
        right_time = self._timestamp(right_index, self.right)
        return StereoFramePair(
            pair_id=pair_id,
            left_index=left_index,
            right_index=right_index,
            left_timestamp_s=left_time,
            right_timestamp_s=right_time,
            left_frame=self.backend.read_frame(self.left.path, left_index),
            right_frame=self.backend.read_frame(self.right.path, right_index),
            timestamp_source="per_video_container_fps_index_not_synchronized",
        )
