"""Timestamp mapping and frame-pairing utilities."""

from .affine import AffineTimeMapping, PairingDiagnostics, TimestampPair, fit_affine_time_mapping, pair_nearest_timestamps
from .frame_selection import SelectedTimestampPair, VideoFrameTimestamp, nearest_frame, select_timestamp_pair
from .video_sync import (
    EventPair,
    FrameBrightnessSeries,
    FrameLevelSyncModel,
    RefinedBrightnessEvent,
    detect_frame_level_light_events,
    extract_frame_brightness_pts,
    fit_frame_level_sync_model,
    pair_frame_level_events,
    synchronization_residual_statistics,
)

__all__ = [
    "AffineTimeMapping",
    "PairingDiagnostics",
    "TimestampPair",
    "fit_affine_time_mapping",
    "pair_nearest_timestamps",
    "SelectedTimestampPair",
    "VideoFrameTimestamp",
    "nearest_frame",
    "select_timestamp_pair",
    "EventPair",
    "FrameBrightnessSeries",
    "FrameLevelSyncModel",
    "RefinedBrightnessEvent",
    "detect_frame_level_light_events",
    "extract_frame_brightness_pts",
    "fit_frame_level_sync_model",
    "pair_frame_level_events",
    "synchronization_residual_statistics",
]
