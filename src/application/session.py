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
    reference_artifact_path: Path | None = None

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("output_directory", "unified_result_path", "selected_frame_path",
                    "dense_height_path", "status_map_path", "point_cloud_path", "dense_npz_path",
                    "pixel_xyz_path", "point_cloud_ply_path", "report_path", "overlay_path","reference_artifact_path"):
            if data[key] is not None:
                data[key] = str(data[key])
        return data

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "MeasurementRecord":
        converted = dict(data)
        for key in ("output_directory", "unified_result_path", "selected_frame_path",
                    "dense_height_path", "status_map_path"):
            converted[key] = Path(converted[key])
        for key in ("point_cloud_path", "dense_npz_path", "pixel_xyz_path", "point_cloud_ply_path", "report_path", "overlay_path","reference_artifact_path"):
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
        self.reference_index_path=self.directory/"references.json"
        self.references: list[dict[str,Any]]=[];self.active_reference_path: Path|None=None
        self.common_fov:dict[str,Any]|None=None
        self.common_fov_path:Path|None=None
        if self.index_path.exists():
            content = json.loads(self.index_path.read_text(encoding="utf-8"))
            self.records = [MeasurementRecord.from_json(item) for item in content]
        if self.reference_index_path.exists():
            content=json.loads(self.reference_index_path.read_text(encoding="utf-8"));self.references=list(content.get("history",[]));active=content.get("active_path");self.active_reference_path=Path(active) if active else None

    def set_active_reference(self,path:Path,metadata:dict[str,Any])->None:
        entry={"reference_id":metadata["reference_id"],"path":str(Path(path).resolve()),"status":"REFERENCE_PLANE_READY","created_at":metadata["created_at"]};self.references.append(entry);self.active_reference_path=Path(path).resolve();self._write_reference_index()

    def set_common_fov(self,metadata:dict[str,Any],metadata_path:Path)->None:
        self.common_fov=dict(metadata);self.common_fov_path=Path(metadata_path).resolve()

    def invalidate_reference(self,reason:str)->None:
        if self.active_reference_path is not None:self.references.append({"reference_id":None,"path":str(self.active_reference_path),"status":"STALE","reason":reason})
        self.active_reference_path=None;self._write_reference_index()

    def _write_reference_index(self)->None:
        self.reference_index_path.write_text(json.dumps({"status":"REFERENCE_PLANE_READY" if self.active_reference_path else "REFERENCE_NOT_SET_OR_STALE","active_path":str(self.active_reference_path) if self.active_reference_path else None,"history":self.references},indent=2,ensure_ascii=False),encoding="utf-8")

    def unique_name(self, target_time_sec: float) -> str:
        base = f"{target_time_sec:.3f}s"
        names = {record.display_name for record in self.records}
        names.update(path.name.removeprefix("measurement_") for path in self.directory.glob("measurement_*") if path.is_dir())
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
