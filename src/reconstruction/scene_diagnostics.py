"""Deterministic image/scene diagnostics for real-world stereo inputs."""
from __future__ import annotations

from typing import Any
import numpy as np
import numpy.typing as npt


def _cv2():
    try:import cv2
    except ImportError as error:raise RuntimeError("OpenCV is required for scene diagnostics") from error
    return cv2


def _gray(image:npt.ArrayLike)->npt.NDArray[np.uint8]:
    cv2=_cv2();value=np.asarray(image)
    if value.ndim==2:gray=value
    elif value.ndim==3 and value.shape[2] in (3,4):gray=cv2.cvtColor(value,cv2.COLOR_BGR2GRAY if value.shape[2]==3 else cv2.COLOR_BGRA2GRAY)
    else:raise ValueError("image must be gray, BGR or BGRA")
    if gray.dtype!=np.uint8:raise ValueError("diagnostics require uint8 image data")
    return gray


def _mask(shape:tuple[int,int],roi:dict[str,Any]|None)->npt.NDArray[np.bool_]:
    cv2=_cv2();mask=np.ones(shape,np.uint8)
    if roi is not None:
        if roi.get("type")!="polygon" or len(roi.get("points",[]))<3:raise ValueError("ROI must be a polygon")
        mask[:]=0;cv2.fillPoly(mask,[np.asarray(roi["points"],np.int32)],1)
    return mask.astype(bool)


def _one(gray:npt.NDArray[np.uint8],valid:npt.NDArray[np.bool_])->dict[str,Any]:
    cv2=_cv2();pixels=gray[valid]
    if not pixels.size:raise ValueError("diagnostic ROI has no pixels")
    gx=cv2.Sobel(gray,cv2.CV_32F,1,0,ksize=3);gy=cv2.Sobel(gray,cv2.CV_32F,0,1,ksize=3);energy=np.sqrt(gx*gx+gy*gy);lap=cv2.Laplacian(gray,cv2.CV_32F)
    grid=[];h,w=gray.shape
    for row in range(3):
        for col in range(3):
            cell=energy[row*h//3:(row+1)*h//3,col*w//3:(col+1)*w//3];cellmask=valid[row*h//3:(row+1)*h//3,col*w//3:(col+1)*w//3];grid.append(float(np.mean(cell[cellmask])) if np.any(cellmask) else None)
    return {"brightness_mean":float(np.mean(pixels)),"brightness_std":float(np.std(pixels)),"contrast_p95_p5":float(np.percentile(pixels,95)-np.percentile(pixels,5)),
            "bright_clipping_ratio":float(np.mean(pixels>=250)),"dark_clipping_ratio":float(np.mean(pixels<=5)),"specular_highlight_proxy_ratio":float(np.mean((gray>=245)&valid&(energy>np.percentile(energy[valid],75)))),
            "gradient_texture_energy":float(np.mean(energy[valid])),"local_texture_energy_3x3":grid,"blur_laplacian_variance":float(np.var(lap[valid])),"low_texture_ratio":float(np.mean(energy[valid]<5.0))}


def diagnose_stereo_scene(left:npt.ArrayLike,right:npt.ArrayLike,*,roi:dict[str,Any]|None=None,common_fov_mask:npt.ArrayLike|None=None,
        previous_left:npt.ArrayLike|None=None,frame_period_s:float|None=None,sync_residual_s:float|None=None,rolling_shutter:bool|None=None)->dict[str,Any]:
    """Return metrics and risk labels; no preprocessing or matcher change occurs."""
    cv2=_cv2();l=_gray(left);r=_gray(right)
    if l.shape!=r.shape:raise ValueError("left/right diagnostic image sizes differ")
    roi_mask=_mask(l.shape,roi);common=np.ones(l.shape,bool) if common_fov_mask is None else np.asarray(common_fov_mask,bool)
    if common.shape!=l.shape:raise ValueError("common-FOV mask shape mismatch")
    lm=_one(l,roi_mask&common);rm=_one(r,roi_mask&common);reasons=[]
    exposure=abs(lm["brightness_mean"]-rm["brightness_mean"]);contrast=abs(lm["brightness_std"]-rm["brightness_std"]);sharp=abs(lm["blur_laplacian_variance"]-rm["blur_laplacian_variance"])
    if max(lm["low_texture_ratio"],rm["low_texture_ratio"])>.65:reasons.append("TEXTURE_LIMITED")
    if exposure>20 or contrast>15:reasons.append("PHOTOMETRIC_RISK")
    if max(lm["bright_clipping_ratio"],rm["bright_clipping_ratio"])>.05 or max(lm["specular_highlight_proxy_ratio"],rm["specular_highlight_proxy_ratio"])>.03:reasons.append("SPECULAR_OR_CLIPPING_RISK")
    if min(lm["blur_laplacian_variance"],rm["blur_laplacian_variance"])<20:reasons.append("BLUR_RISK")
    motion=None
    if previous_left is not None:
        prev=_gray(previous_left)
        if prev.shape!=l.shape:raise ValueError("previous frame shape mismatch")
        flow=cv2.calcOpticalFlowFarneback(prev,l,None,.5,2,15,2,5,1.1,0);motion=float(np.median(np.linalg.norm(flow,axis=2)[roi_mask]));
        if motion>2:reasons.append("CAMERA_RIG_MOTION_RISK")
    normalized_sync=None
    if sync_residual_s is not None and frame_period_s:
        normalized_sync=abs(sync_residual_s)/frame_period_s
        if normalized_sync>.5:reasons.append("SYNC_UNRELIABLE")
    rs_status="ROLLING_SHUTTER_RISK" if rolling_shutter is True and (motion or 0)>1 else "ROLLING_SHUTTER_METADATA_UNKNOWN" if rolling_shutter is None else "NO_ROLLING_SHUTTER_RISK_DETECTED"
    if rs_status=="ROLLING_SHUTTER_RISK":reasons.append(rs_status)
    status="VALID" if not reasons else "VALID_WITH_WARNING"
    return {"schema_version":"1.0","image_size":{"width":l.shape[1],"height":l.shape[0]},"left":lm,"right":rm,
            "left_right_difference":{"brightness_mean":exposure,"contrast_std":contrast,"sharpness_laplacian_variance":sharp},
            "common_fov_ratio":float(np.mean(common)),"roi_valid_common_fov_ratio":float(np.sum(roi_mask&common)/max(1,np.sum(roi_mask))),
            "temporal_motion_median_px":motion,"sync_residual_over_frame_period":normalized_sync,"rolling_shutter_status":rs_status,
            "quality_status":status,"quality_reasons":sorted(set(reasons))}
