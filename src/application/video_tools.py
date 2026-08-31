"""Offline video metadata and preview helpers using the existing FFmpeg runtime."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import re
import subprocess
import threading
import time

from PIL import Image
from process_utils import hidden_process_kwargs


@dataclass(frozen=True)
class VideoMetadata:
    width: int
    height: int
    fps: float
    duration_sec: float


def probe_video(path: Path, ffmpeg: Path) -> VideoMetadata:
    completed = subprocess.run([str(ffmpeg), "-hide_banner", "-i", str(path)], capture_output=True, text=True,
                               encoding="utf-8",errors="replace",check=False,
                               **hidden_process_kwargs())
    text = completed.stderr
    duration_match = re.search(r"Duration:\s*(\d+):(\d+):([0-9.]+)", text)
    video_match = re.search(r"Video:.*?\b(\d{2,5})x(\d{2,5})\b.*?([0-9.]+) fps", text)
    if not duration_match or not video_match:
        raise RuntimeError(f"无法读取视频 metadata：{path}")
    duration = int(duration_match.group(1)) * 3600 + int(duration_match.group(2)) * 60 + float(duration_match.group(3))
    return VideoMetadata(int(video_match.group(1)), int(video_match.group(2)), float(video_match.group(3)), duration)


def extract_frame(path: Path, time_sec: float, ffmpeg: Path) -> Image.Image:
    command = [str(ffmpeg), "-hide_banner", "-loglevel", "error", "-ss", f"{max(time_sec, 0.0):.6f}",
               "-i", str(path), "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "pipe:1"]
    completed = subprocess.run(command, capture_output=True, check=False, **hidden_process_kwargs())
    if completed.returncode != 0 or not completed.stdout:
        raise RuntimeError(f"无法提取视频帧：{path}")
    image = Image.open(BytesIO(completed.stdout))
    image.load()
    return image.convert("RGB")


class LatestFrameDecoder:
    """Background real-time preview decoder retaining exactly one latest frame."""

    def __init__(self, *, display_fps: float = 30.0) -> None:
        self.display_fps=display_fps; self._lock=threading.Lock(); self._stop=threading.Event()
        self._latest: tuple[int,float,Image.Image] | None=None; self._version=0; self._generation=0
        self._thread: threading.Thread | None=None

    def start(self,path:Path,start_time_sec:float) -> None:
        self.seek(path,start_time_sec,continue_playing=True)

    def seek(self, path: Path, time_sec: float, *, continue_playing: bool) -> int:
        """Submit one latest-only OpenCV seek; paused mode publishes one frame."""
        self.stop(); self._stop.clear(); self._generation += 1; generation=self._generation
        with self._lock:self._latest=None
        self._thread=threading.Thread(
            target=self._decode,args=(Path(path),time_sec,generation,continue_playing),daemon=True
        ); self._thread.start()
        return generation

    def _decode(self,path:Path,start:float,generation:int,continuous:bool) -> None:
        import cv2
        capture=cv2.VideoCapture(str(path)); capture.set(cv2.CAP_PROP_POS_MSEC,max(start,0)*1000.0)
        interval=1.0/self.display_fps; deadline=time.perf_counter()
        try:
            while not self._stop.is_set():
                ok,frame=capture.read()
                if not ok: break
                timestamp=float(capture.get(cv2.CAP_PROP_POS_MSEC)/1000.0)
                rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
                with self._lock:
                    if generation != self._generation: break
                    self._version+=1; self._latest=(self._version,timestamp,Image.fromarray(rgb))
                if not continuous: break
                deadline+=interval; self._stop.wait(max(0.0,deadline-time.perf_counter()))
        finally: capture.release()

    def snapshot(self,after_version:int) -> tuple[int,float,Image.Image] | None:
        with self._lock:
            return self._latest if self._latest and self._latest[0]>after_version else None

    @property
    def pending_frame_count(self) -> int:
        return 0 if self._latest is None else 1

    def stop(self) -> None:
        self._generation += 1; self._stop.set()
        if self._thread and self._thread.is_alive(): self._thread.join(timeout=0.5)
        self._thread=None
