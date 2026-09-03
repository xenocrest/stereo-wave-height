"""User-selected reference-frame artifacts and strict compatibility checks."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib,json
from pathlib import Path
from typing import Any
import numpy as np
import yaml
from validation.diagnostics import fit_plane_orthogonal

CANONICAL_CONVENTION="canonical_cam1_pixels__WASS_metric_camera_coordinates_m"

def stable_identity(value: Any, prefix: str) -> str:
    encoded=json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(encoded).hexdigest()[:16]}"

def file_identity(path: str|Path, prefix: str) -> str:
    candidate=Path(path).resolve()
    if not candidate.exists():return stable_identity({"path":str(candidate),"status":"NOT_PRESENT_CONFIG_PREPARATION"},prefix)
    stat=candidate.stat();return stable_identity({"path":str(candidate),"size":stat.st_size,"mtime_ns":stat.st_mtime_ns},prefix)

def video_pair_identity(left: str|Path,right: str|Path)->str:return stable_identity([file_identity(left,"video"),file_identity(right,"video")],"pair")
def roi_identity(roi:dict[str,Any])->str:return stable_identity(roi,"roi")

def canonical_calibration_identity(calibration:dict[str,Any])->str:
    """Return an ID for stereo geometry, independent of package/file names."""
    left=calibration.get("camera_left") or calibration.get("mono_cam0") or calibration.get("left") or {}
    right=calibration.get("camera_right") or calibration.get("mono_cam1") or calibration.get("right") or {}
    stereo=calibration.get("stereo") or {}
    payload={
      "K0":left.get("K"),"D0":left.get("D"),"K1":right.get("K"),"D1":right.get("D"),
      "R":stereo.get("R",stereo.get("R_right_from_left")),
      "T_m":stereo.get("T_m",stereo.get("T_right_from_left_m")),
      "image_size_wh":calibration.get("image_size_wh",[1920,1080]),
      "canonical_convention":CANONICAL_CONVENTION,
    }
    missing=[key for key in ("K0","D0","K1","D1","R","T_m") if payload[key] is None]
    if missing:raise ValueError("CALIBRATION_GEOMETRY_IDENTITY_UNAVAILABLE: "+", ".join(missing))
    return stable_identity(payload,"calgeom")

def _inside_polygon(u:np.ndarray,v:np.ndarray,points:list[list[float]])->np.ndarray:
    polygon=np.asarray(points,float);inside=np.zeros(u.shape,dtype=bool);j=len(polygon)-1
    for i in range(len(polygon)):
        xi,yi=polygon[i];xj,yj=polygon[j];cross=((yi>v)!=(yj>v))&(u<(xj-xi)*(v-yi)/(yj-yi+1e-300)+xi);inside^=cross;j=i
    return inside

def fit_reference_artifact(pixel_xyz_path:str|Path, *, reference_id:str,requested_timestamp_s:float,actual_timestamp_s:float,
        fallback_frame_offset:int,left_frame_id:str,right_frame_id:str,sync_residual_ms:float,calibration_id:str,
        calibration_package_hash:str|None,video_pair_id:str,roi:dict[str,Any],xyz_point_count:int,
        source_videos:dict[str,str],surface_distance_threshold_m:float,mapping_file:str|Path|None=None,
        allow_demo_quality_warning:bool=False)->dict[str,Any]:
    with np.load(pixel_xyz_path) as data:
        u,v,xyz=data["u_px"].copy(),data["v_px"].copy(),data["xyz_m"].copy()
    if roi.get("type")!="polygon" or len(roi.get("points",[]))<3:raise ValueError("REFERENCE_SUPPORT_INSUFFICIENT: polygon water ROI required")
    polygon=roi["points"]
    if roi.get("coordinate_system")=="canonical_cam1" and mapping_file is not None:
        from surface_completion.dense_map import canonical_to_rectified
        mapping=yaml.safe_load(Path(mapping_file).read_text(encoding="utf-8"))
        polygon=canonical_to_rectified(np.asarray(polygon,float),mapping).tolist()
    selected=_inside_polygon(u,v,polygon);points=np.asarray(xyz[selected],float)
    if len(points)<12:raise ValueError("REFERENCE_SUPPORT_INSUFFICIENT: fewer than 12 direct observations in ROI")
    extent=points.max(0)-points.min(0)
    if np.count_nonzero(extent>1e-6)<2 or np.linalg.matrix_rank(points-points.mean(0),tol=1e-9)<2:raise ValueError("REFERENCE_GEOMETRY_QA_FAILED: spatial support is degenerate")
    fit=fit_plane_orthogonal(points);normal=np.asarray(fit.normal,float);offset=float(fit.offset)
    if not np.all(np.isfinite(normal)) or not np.isfinite(offset) or not np.isfinite(fit.residual_rmse):raise ValueError("REFERENCE_PLANE_FIT_FAILED")
    rms_warning=fit.residual_rmse>surface_distance_threshold_m
    if rms_warning and not allow_demo_quality_warning:raise ValueError("REFERENCE_GEOMETRY_QA_FAILED: plane RMS exceeds existing surface threshold")
    xy=points[:,:2];span=np.maximum(xy.max(0)-xy.min(0),1e-12);normalized=(xy-xy.min(0))/span;cells={(min(2,int(v*3)),min(2,int(u*3))) for u,v in normalized};cov=np.cov(xy,rowvar=False);eigen=np.linalg.eigvalsh(cov);anisotropy=float(eigen[0]/max(eigen[-1],1e-18));weak=len(cells)<4 or anisotropy<.02
    return {"schema_version":"1.0","status":"REFERENCE_PLANE_READY","reference_id":reference_id,
      "source":"user_selected_reference_frame_WASS_final_XYZ_ROI_plane_fit","created_at":datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
      "reference_mode":"single_frame","future_reference_modes":["single_frame","multi_frame"],
      "requested_timestamp_s":requested_timestamp_s,"actual_timestamp_s":actual_timestamp_s,"fallback_frame_offset":fallback_frame_offset,
      "left_frame_id":left_frame_id,"right_frame_id":right_frame_id,"sync_residual_ms":sync_residual_ms,
      "calibration_id":calibration_id,"calibration_package_hash":calibration_package_hash,"video_pair_id":video_pair_id,
      "source_videos":source_videos,"canonical_convention":CANONICAL_CONVENTION,"roi":roi,"roi_id":roi_identity(roi),
      "plane":{"model":"aX+bY+cZ+d=0","a":float(normal[0]),"b":float(normal[1]),"c":float(normal[2]),"d":offset,"normal":normal.tolist(),"offset_m":offset},
      "unit":"m","plane_rms_m":float(fit.residual_rmse),"support_count":len(points),"xyz_point_count":xyz_point_count,
      "reference_confidence":"LOW" if rms_warning else ("MEDIUM" if weak else "HIGH"),"reference_quality_reasons":((["REFERENCE_PLANE_RMS_EXCEEDS_FORMAL_GATE"] if rms_warning else []) + (["REFERENCE_PLANE_WEAK_SPATIAL_SUPPORT"] if weak else [])),"support_spatial_occupancy_3x3":len(cells),"support_anisotropy_ratio":anisotropy,
      "spatial_extent_m":{"x":[float(points[:,0].min()),float(points[:,0].max())],"y":[float(points[:,1].min()),float(points[:,1].max())],"z":[float(points[:,2].min()),float(points[:,2].max())]},
      "height_definition":"signed orthogonal distance to user-selected reference plane"}

def save_reference_artifact(value:dict[str,Any],path:str|Path)->Path:
    destination=Path(path);destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text(yaml.safe_dump(value,sort_keys=False,allow_unicode=True),encoding="utf-8");return destination

def load_reference_artifact(path:str|Path)->dict[str,Any]:
    data=yaml.safe_load(Path(path).read_text(encoding="utf-8"));plane=data.get("plane",{});normal=np.asarray(plane.get("normal"),float);offset=plane.get("offset_m")
    if data.get("status")!="REFERENCE_PLANE_READY" or normal.shape!=(3,) or not np.all(np.isfinite(normal)) or not np.isfinite(offset) or np.linalg.norm(normal)==0:raise ValueError("REFERENCE_ARTIFACT_INCOMPATIBLE: invalid finite plane")
    return data

def validate_reference_artifact(path:str|Path, *,calibration_id:str,video_pair_id:str,roi:dict[str,Any])->dict[str,Any]:
    data=load_reference_artifact(path);mismatch=[]
    if data.get("calibration_id")!=calibration_id:mismatch.append("calibration_id")
    if data.get("video_pair_id")!=video_pair_id:mismatch.append("video_pair_id")
    if data.get("roi_id")!=roi_identity(roi):mismatch.append("roi_id")
    if data.get("canonical_convention")!=CANONICAL_CONVENTION:mismatch.append("canonical_convention")
    if mismatch:raise ValueError("REFERENCE_ARTIFACT_INCOMPATIBLE: "+", ".join(mismatch))
    return data
