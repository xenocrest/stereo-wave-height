"""Shared layered quality vocabulary and deterministic precedence."""
from __future__ import annotations
from typing import Iterable
import numpy as np

QUALITY_STATUSES=("VALID","VALID_WITH_WARNING","INSUFFICIENT_SUPPORT","GEOMETRY_UNRELIABLE","CALIBRATION_UNRELIABLE","SYNC_UNRELIABLE","REFERENCE_UNRELIABLE","PHOTOMETRIC_RISK","TEXTURE_LIMITED","UNSUPPORTED")
_PRIORITY={name:index for index,name in enumerate(QUALITY_STATUSES)}

def resolve_quality(reasons:Iterable[str],*,geometry_valid:bool=True,support_valid:bool=True)->dict[str,object]:
    unique=sorted(set(str(value) for value in reasons))
    if not geometry_valid:status="GEOMETRY_UNRELIABLE"
    elif not support_valid:status="INSUFFICIENT_SUPPORT"
    elif "CALIBRATION_UNRELIABLE" in unique:status="CALIBRATION_UNRELIABLE"
    elif "SYNC_UNRELIABLE" in unique:status="SYNC_UNRELIABLE"
    elif "REFERENCE_UNRELIABLE" in unique:status="REFERENCE_UNRELIABLE"
    elif "TEXTURE_LIMITED" in unique:status="TEXTURE_LIMITED"
    elif "PHOTOMETRIC_RISK" in unique:status="PHOTOMETRIC_RISK"
    else:status="VALID" if not unique else "VALID_WITH_WARNING"
    return {"quality_status":status,"quality_reasons":unique}

def height_confidence(*,point_source:str,matching_reliable:bool,reference_confidence:str)->str:
    if point_source=="UNSUPPORTED":return "UNSUPPORTED"
    if point_source=="ESTIMATED_GLOBAL":return "LOW"
    if not matching_reliable or reference_confidence=="LOW":return "LOW"
    if point_source.startswith("ESTIMATED") or reference_confidence=="MEDIUM":return "MEDIUM"
    return "HIGH"

def component_diagnostics(labels:np.ndarray,xyz:np.ndarray|None=None)->list[dict[str,object]]:
    """Describe every observed component without changing retention policy."""
    values=np.asarray(labels);records=[]
    if values.ndim!=2:raise ValueError("component labels must be a 2-D image")
    for label in sorted(int(v) for v in np.unique(values) if int(v)>0):
        yy,xx=np.where(values==label);item={"label":label,"count":len(xx),"image_extent_px":{"x":[int(xx.min()),int(xx.max())],"y":[int(yy.min()),int(yy.max())]}}
        if xyz is not None:
            points=np.asarray(xyz)[values==label];valid=np.all(np.isfinite(points),axis=1);points=points[valid]
            item["xyz_extent_m"]={axis:[float(points[:,i].min()),float(points[:,i].max())] for i,axis in enumerate("xyz")} if len(points) else None
        records.append(item)
    return records
