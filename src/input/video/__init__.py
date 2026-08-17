"""Recorded stereo-video input implementation."""

from .source import OpenCVVideoBackend, StereoVideoSource, VideoBackend

__all__ = ["OpenCVVideoBackend", "StereoVideoSource", "VideoBackend"]
