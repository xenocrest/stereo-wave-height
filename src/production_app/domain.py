from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


@dataclass
class CalibrationResult:
    directory: str
    identity: str
    provenance: dict


@dataclass
class SyncResult:
    right_minus_left_s: float
    provenance: dict


@dataclass
class ReferenceSurface:
    setup: str
    identity: str
    provenance: dict


@dataclass
class FrameResult:
    identity: str
    directory: str
    left_time_s: float
    right_time_s: float
    files: dict
    provenance: dict


@dataclass
class Project:
    name: str
    directory: str
    videos: dict = field(default_factory=dict)
    calibration: dict = field(default_factory=dict)
    sync: dict = field(default_factory=dict)
    reference: dict = field(default_factory=dict)
    frames: dict = field(default_factory=dict)
    toolchain: dict = field(default_factory=dict)
    workflow: dict = field(default_factory=dict)
    workspace_directory: str = ''
    schema: int = 1
    created: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def record(self):
        return asdict(self)
