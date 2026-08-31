"""Persistent-on-disk GUI session and measurement record models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MeasurementRecord:
    target_time_sec: float
    display_name: str
    output_directory: Path
    unified_result_path: Path
    selected_frame_path: Path
    dense_height_path: Path
    status_map_path: Path
    point_cloud_path: Path | None
    created_time: str
    summary_metadata: dict[str, Any] = field(default_factory=dict)
    dense_npz_path: Path | None = None
    pixel_xyz_path: Path | None = None
    point_cloud_ply_path: Path | None = None
    report_path: Path | None = None
    overlay_path: Path | None = None

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("output_directory", "unified_result_path", "selected_frame_path",
                    "dense_height_path", "status_map_path", "point_cloud_path", "dense_npz_path",
                    "pixel_xyz_path", "point_cloud_ply_path", "report_path", "overlay_path"):
            if data[key] is not None:
                data[key] = str(data[key])
        return data

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "MeasurementRecord":
        converted = dict(data)
        for key in ("output_directory", "unified_result_path", "selected_frame_path",
                    "dense_height_path", "status_map_path"):
            converted[key] = Path(converted[key])
        for key in ("point_cloud_path", "dense_npz_path", "pixel_xyz_path", "point_cloud_ply_path", "report_path", "overlay_path"):
            converted[key] = Path(converted[key]) if converted.get(key) else None
        return cls(**converted)


class MeasurementSession:
    """Own measurement folders without writing generated data into the repository."""

    def __init__(self, root: Path, session_id: str | None = None) -> None:
        self.root = Path(root).resolve()
        self.session_id = session_id or datetime.now().strftime("%Y%m%d-%H%M%S")
        self.directory = self.root / self.session_id
        self.directory.mkdir(parents=True, exist_ok=True)
        self.records: list[MeasurementRecord] = []
        self.log_path = self.directory / "session.log"
        self.index_path = self.directory / "measurements.json"
        if self.index_path.exists():
            content = json.loads(self.index_path.read_text(encoding="utf-8"))
            self.records = [MeasurementRecord.from_json(item) for item in content]

    def unique_name(self, target_time_sec: float) -> str:
        base = f"{target_time_sec:.3f}s"
        names = {record.display_name for record in self.records}
        if base not in names:
            return base
        suffix = 2
        while f"{base}_{suffix:02d}" in names:
            suffix += 1
        return f"{base}_{suffix:02d}"

    def allocate(self, target_time_sec: float) -> tuple[str, Path]:
        name = self.unique_name(target_time_sec)
        directory = self.directory / f"measurement_{name}"
        directory.mkdir(parents=True, exist_ok=False)
        return name, directory

    def add(self, record: MeasurementRecord) -> None:
        if any(item.display_name == record.display_name for item in self.records):
            raise ValueError(f"measurement name already exists: {record.display_name}")
        self.records.append(record)
        self.index_path.write_text(json.dumps([item.to_json() for item in self.records], indent=2, ensure_ascii=False), encoding="utf-8")

    def log(self, message: str) -> None:
        stamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        with self.log_path.open("a", encoding="utf-8") as stream:
            stream.write(f"{stamp} {message}\n")
