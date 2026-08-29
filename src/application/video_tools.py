"""Offline video metadata and preview helpers using the existing FFmpeg runtime."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import re
import subprocess

from PIL import Image


@dataclass(frozen=True)
class VideoMetadata:
    width: int
    height: int
    fps: float
    duration_sec: float


def probe_video(path: Path, ffmpeg: Path) -> VideoMetadata:
    completed = subprocess.run([str(ffmpeg), "-hide_banner", "-i", str(path)], capture_output=True, text=True, check=False)
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
    completed = subprocess.run(command, capture_output=True, check=False)
    if completed.returncode != 0 or not completed.stdout:
        raise RuntimeError(f"无法提取视频帧：{path}")
    image = Image.open(BytesIO(completed.stdout))
    image.load()
    return image.convert("RGB")
