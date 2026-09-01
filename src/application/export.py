"""Transactional export for selected GUI measurements."""
from __future__ import annotations

from datetime import datetime,timezone
import json
from pathlib import Path
import shutil
from typing import Iterable

from .session import MeasurementRecord,MeasurementSession

ARTIFACTS=(
    ("selected_frame_path","selected_frame.png"),("overlay_path","height_overlay.png"),
    ("dense_height_path","height_map.png"),("status_map_path","status_map.png"),
    ("point_cloud_ply_path","point_cloud.ply"),("point_cloud_path","point_cloud.xyz"),
    ("dense_npz_path","dense_height.npz"),("pixel_xyz_path","pixel_xyz.npz"),
    ("unified_result_path","result.json"),("report_path","report.md"),
    ("reference_artifact_path","reference.yaml"),
)


def export_session(session:MeasurementSession,destination:Path,records:Iterable[MeasurementRecord]|None=None,
                   *,camera_models:dict[str,str]|None=None,calibration_reference:str|None=None) -> Path:
    chosen=list(session.records if records is None else records)
    destination=Path(destination).resolve(); session_dir=session.directory.resolve()
    if destination==session_dir or session_dir in destination.parents:raise ValueError("export destination cannot be inside the temporary session")
    final=destination/f"session_{session.session_id}"; staging=destination/f".session_{session.session_id}_staging"
    if final.exists() or staging.exists():raise FileExistsError(f"export destination already exists: {final}")
    staging.mkdir(parents=True)
    manifest={"session_id":session.session_id,"created_at":datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
              "camera_models":camera_models or {"left":"UNKNOWN","right":"UNKNOWN"},
              "calibration_reference":calibration_reference or "UNKNOWN","reference":{"status":"REFERENCE_PLANE_READY" if session.active_reference_path else "LEGACY_REFERENCE_UNSPECIFIED","active_path":str(session.active_reference_path) if session.active_reference_path else None,"history":session.references},"measurement_count":len(chosen),"measurements":[]}
    try:
        for record in chosen:
            folder=staging/f"measurement_{record.display_name}"; folder.mkdir(); copied=[]
            for attribute,name in ARTIFACTS:
                source=getattr(record,attribute,None)
                if source is not None and Path(source).is_file():shutil.copy2(source,folder/name); copied.append(name)
            reference=record.summary_metadata.get("reference_metadata") or {"status":"LEGACY_REFERENCE_UNSPECIFIED"}
            item={"display_name":record.display_name,"target_time_sec":record.target_time_sec,"classification":record.summary_metadata.get("status"),"height_summary":record.summary_metadata.get("height_statistics"),"reference":{"reference_id":record.summary_metadata.get("reference_id"),"reference_timestamp_s":reference.get("actual_timestamp_s"),"plane":reference.get("plane"),"calibration_id":reference.get("calibration_id"),"height_definition":reference.get("height_definition")},"artifacts":copied}
            (folder/"measurement_manifest.json").write_text(json.dumps(item,indent=2,ensure_ascii=False),encoding="utf-8"); manifest["measurements"].append(item)
        (staging/"session_manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding="utf-8"); staging.rename(final)
    except Exception:
        shutil.rmtree(staging,ignore_errors=True); raise
    return final


def delete_session(session:MeasurementSession) -> None:
    root=session.root.resolve(); target=session.directory.resolve()
    if target.parent!=root:raise ValueError("refusing to delete outside GUI session root")
    shutil.rmtree(target)
