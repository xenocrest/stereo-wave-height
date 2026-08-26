"""Timestamp mapping and frame-pairing utilities."""

from .affine import AffineTimeMapping, PairingDiagnostics, TimestampPair, fit_affine_time_mapping, pair_nearest_timestamps
from .frame_selection import SelectedTimestampPair, VideoFrameTimestamp, nearest_frame, select_timestamp_pair

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
]
