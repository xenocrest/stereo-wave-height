"""Split mono/stereo calibration and observable real-world calibration QA.

Mono intrinsics use every complete observation from that camera.  Stereo
extrinsics use only synchronized bilateral observations and keep those
intrinsics fixed.  No reconstruction result or physical reference enters the
estimation.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Sequence

import numpy as np
import numpy.typing as npt

from .opencv_backend import (
    MonoCalibrationResult, RectificationResult, StereoCalibrationResult,
    _common_roi, _cv2, _validate_views, calibrate_monocular_official,
)


def deterministic_group_folds(group_ids: Sequence[str], *, maximum_folds: int = 5) -> tuple[tuple[int, ...], ...]:
    """Build deterministic validation folds without near-pose leakage."""
    if maximum_folds < 2:
        raise ValueError("maximum_folds must be at least two")
    unique = sorted(set(map(str, group_ids)))
    if len(unique) < 2:
        raise ValueError("at least two independent pose groups are required")
    buckets: list[list[int]] = [[] for _ in range(min(maximum_folds, len(unique)))]
    assignment = {value: index % len(buckets) for index, value in enumerate(unique)}
    for index, value in enumerate(group_ids):
        buckets[assignment[str(value)]].append(index)
    return tuple(tuple(bucket) for bucket in buckets if bucket)


@dataclass(frozen=True)
class SplitCalibrationProvenance:
    left_mono_ids: tuple[str, ...]
    right_mono_ids: tuple[str, ...]
    stereo_pair_ids: tuple[str, ...]
    heldout_pair_ids: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.left_mono_ids or not self.right_mono_ids or not self.stereo_pair_ids:
            raise ValueError("split calibration requires LEFT mono, RIGHT mono and bilateral stereo observations")
        if set(self.stereo_pair_ids) & set(self.heldout_pair_ids):
            raise ValueError("held-out stereo observations must be disjoint")


def _vertical_statistics(values: Sequence[float]) -> dict[str, float | None]:
    array=np.asarray(values,dtype=np.float64)
    if not array.size:return {"median_px":None,"rms_px":None,"p95_px":None,"max_px":None}
    return {"median_px":float(np.median(array)),"rms_px":float(np.sqrt(np.mean(array**2))),
            "p95_px":float(np.percentile(array,95)),"max_px":float(np.max(array))}


def rectification_residuals(left:Sequence[npt.ArrayLike],right:Sequence[npt.ArrayLike],*,
        k0:npt.ArrayLike,d0:npt.ArrayLike,k1:npt.ArrayLike,d1:npt.ArrayLike,
        r:npt.ArrayLike,t:npt.ArrayLike,image_size_wh:tuple[int,int],cv2_module:Any|None=None)->dict[str,Any]:
    """Held-out rectification errors with normalized 3x3 spatial diagnostics."""
    cv2=_cv2(cv2_module);k0=np.asarray(k0,float);d0=np.asarray(d0,float);k1=np.asarray(k1,float);d1=np.asarray(d1,float)
    r1,r2,p1,p2,_,_,_=cv2.stereoRectify(k0,d0,k1,d1,image_size_wh,np.asarray(r,float),np.asarray(t,float),flags=cv2.CALIB_ZERO_DISPARITY,alpha=0)
    errors=[];cells=[[] for _ in range(9)];width,height=image_size_wh
    for lp,rp in zip(left,right):
        lr=cv2.undistortPoints(np.asarray(lp,np.float32).reshape(-1,1,2),k0,d0,R=r1,P=p1).reshape(-1,2)
        rr=cv2.undistortPoints(np.asarray(rp,np.float32).reshape(-1,1,2),k1,d1,R=r2,P=p2).reshape(-1,2)
        delta=np.abs(lr[:,1]-rr[:,1]);errors.extend(delta.tolist())
        for point,value in zip(lr,delta):
            col=min(2,max(0,int(point[0]*3/max(1,width))));row=min(2,max(0,int(point[1]*3/max(1,height))));cells[row*3+col].append(float(value))
    return {**_vertical_statistics(errors),"normalized_rms":(_vertical_statistics(errors)["rms_px"] or 0)/max(image_size_wh),
            "spatial_3x3":[_vertical_statistics(cell) for cell in cells]}


def calibrate_split_official(*,mono_object_points_left:Sequence[npt.ArrayLike],mono_image_points_left:Sequence[npt.ArrayLike],
        mono_object_points_right:Sequence[npt.ArrayLike],mono_image_points_right:Sequence[npt.ArrayLike],
        stereo_object_points:Sequence[npt.ArrayLike],stereo_image_points_left:Sequence[npt.ArrayLike],
        stereo_image_points_right:Sequence[npt.ArrayLike],image_size_wh:tuple[int,int],square_size_m:float,
        provenance:SplitCalibrationProvenance,cv2_module:Any|None=None)->StereoCalibrationResult:
    """Independent mono calibration followed by fixed-intrinsic stereoCalibrate."""
    provenance.validate();cv2=_cv2(cv2_module)
    if len(provenance.left_mono_ids)!=len(mono_object_points_left) or len(provenance.right_mono_ids)!=len(mono_object_points_right) or len(provenance.stereo_pair_ids)!=len(stereo_object_points):raise ValueError("provenance counts must match calibration observations")
    mono_left=calibrate_monocular_official(mono_object_points_left,mono_image_points_left,image_size_wh,cv2_module=cv2)
    mono_right=calibrate_monocular_official(mono_object_points_right,mono_image_points_right,image_size_wh,cv2_module=cv2)
    objects,left=_validate_views(stereo_object_points,stereo_image_points_left,image_size_wh);_,right=_validate_views(stereo_object_points,stereo_image_points_right,image_size_wh)
    result=cv2.stereoCalibrate(objects,left,right,mono_left.camera_matrix.copy(),mono_left.distortion.copy(),mono_right.camera_matrix.copy(),mono_right.distortion.copy(),image_size_wh,flags=cv2.CALIB_FIX_INTRINSIC,criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_MAX_ITER,100,1e-5))
    rms,k0,d0,k1,d1,rotation,translation,essential,fundamental=result
    if not np.array_equal(k0,mono_left.camera_matrix) or not np.array_equal(k1,mono_right.camera_matrix) or not np.array_equal(d0,mono_left.distortion) or not np.array_equal(d1,mono_right.distortion):raise RuntimeError("CALIB_FIX_INTRINSIC did not preserve mono K/D")
    epi=[]
    for lp,rp in zip(left,right):
        lu=cv2.undistortPoints(lp,k0,d0,P=k0);ru=cv2.undistortPoints(rp,k1,d1,P=k1)
        lines_r=cv2.computeCorrespondEpilines(lu,1,fundamental).reshape(-1,3);lines_l=cv2.computeCorrespondEpilines(ru,2,fundamental).reshape(-1,3);lxy=lu.reshape(-1,2);rxy=ru.reshape(-1,2)
        dl=np.abs(np.sum(lines_l[:,:2]*lxy,axis=1)+lines_l[:,2])/np.linalg.norm(lines_l[:,:2],axis=1);dr=np.abs(np.sum(lines_r[:,:2]*rxy,axis=1)+lines_r[:,2])/np.linalg.norm(lines_r[:,:2],axis=1);epi.extend(((dl+dr)*.5).tolist())
    r1,r2,p1,p2,q,roi1,roi2=cv2.stereoRectify(k0,d0,k1,d1,image_size_wh,rotation,translation,flags=cv2.CALIB_ZERO_DISPARITY,alpha=0)
    residual=rectification_residuals(left,right,k0=k0,d0=d0,k1=k1,d1=d1,r=rotation,t=translation,image_size_wh=image_size_wh,cv2_module=cv2);epi=np.asarray(epi,float)
    rect=RectificationResult(r1,r2,p1,p2,q,tuple(map(int,roi1)),tuple(map(int,roi2)),_common_roi(tuple(map(int,roi1)),tuple(map(int,roi2)),),float(residual["rms_px"]),float(residual["max_px"]))
    return StereoCalibrationResult(MonoCalibrationResult(mono_left.rms_px,k0,d0,mono_left.per_view_rms_px),MonoCalibrationResult(mono_right.rms_px,k1,d1,mono_right.per_view_rms_px),float(rms),rotation,np.asarray(translation).reshape(3,1),essential,fundamental,float(np.sqrt(np.mean(epi**2))),float(np.max(epi)),rect,image_size_wh,square_size_m,backend="OPENCV_OFFICIAL_SPLIT_MONO_FIX_INTRINSIC")


def parameter_plausibility(result:StereoCalibrationResult)->dict[str,Any]:
    """Deterministic observability proxies; thresholds are review flags, not corrections."""
    k0,k1=result.mono_left.camera_matrix,result.mono_right.camera_matrix;d0=result.mono_left.distortion.reshape(-1);d1=result.mono_right.distortion.reshape(-1);w,h=result.image_size_wh
    focal_ratio=max(k0[0,0],k0[1,1],k1[0,0],k1[1,1])/min(k0[0,0],k0[1,1],k1[0,0],k1[1,1]);principal=[k0[0,2]/w,k0[1,2]/h,k1[0,2]/w,k1[1,2]/h]
    flags=[]
    if focal_ratio>1.5:flags.append("FOCAL_RATIO_IMPLAUSIBLE")
    if any(v<-.1 or v>1.1 for v in principal):flags.append("PRINCIPAL_POINT_IMPLAUSIBLE")
    if max(np.max(np.abs(d0)),np.max(np.abs(d1)))>5:flags.append("DISTORTION_MAGNITUDE_UNSTABLE")
    if len(d0)>4 and abs(d0[4])>2 or len(d1)>4 and abs(d1[4])>2:flags.append("HIGH_ORDER_DISTORTION_WEAKLY_CONSTRAINED")
    if not math.isfinite(result.baseline_m) or result.baseline_m<=0:flags.append("BASELINE_INVALID")
    return {"status":"CALIBRATION_PARAMETER_STABLE_PROXY" if not flags else "CALIBRATION_PARAMETER_UNSTABLE","flags":flags,"focal_ratio":float(focal_ratio),"principal_point_normalized":list(map(float,principal)),"max_abs_distortion":float(max(np.max(np.abs(d0)),np.max(np.abs(d1))))}


def select_distortion_complexity(candidates:Sequence[dict[str,Any]],*,heldout_tolerance_px:float=0.05)->dict[str,Any]:
    """Choose the lowest stable OpenCV model within held-out tolerance of best.

    Candidate estimation remains outside this selector.  Each record must carry
    complexity, held-out RMS and stability, preventing training-RMS selection.
    """
    if not candidates:raise ValueError("distortion model candidates required")
    valid=[item for item in candidates if item.get("parameter_stability")!="CALIBRATION_PARAMETER_UNSTABLE" and np.isfinite(item.get("heldout_rectification_rms_px",np.nan))]
    if not valid:return {"status":"CALIBRATION_PARAMETER_UNSTABLE","selected_model":None,"reason":"no stable held-out candidate"}
    best=min(float(x["heldout_rectification_rms_px"]) for x in valid);eligible=[x for x in valid if float(x["heldout_rectification_rms_px"])<=best+heldout_tolerance_px];selected=min(eligible,key=lambda x:(int(x["complexity"]),str(x["model"])))
    return {"status":"DISTORTION_MODEL_SELECTED_BY_HELDOUT_STABILITY","selected_model":selected["model"],"reason":"lowest complexity within held-out tolerance","best_heldout_rms_px":best}


def classify_rectification_health(metrics:dict[str,Any],*,matcher_vertical_tolerance_px:float,image_height_px:int)->dict[str,Any]:
    if matcher_vertical_tolerance_px<=0 or image_height_px<=0:raise ValueError("positive matcher tolerance and image height required")
    rms=metrics.get("rms_px");p95=metrics.get("p95_px");maximum=metrics.get("max_px")
    if any(value is None or not np.isfinite(value) for value in (rms,p95,maximum)):status="RECTIFICATION_FAIL"
    elif p95<=.5*matcher_vertical_tolerance_px:status="RECTIFICATION_PASS"
    elif p95<=matcher_vertical_tolerance_px:status="RECTIFICATION_WARNING"
    else:status="RECTIFICATION_FAIL"
    return {"status":status,"pixel_metrics":{"rms":rms,"p95":p95,"max":maximum},"normalized":{"rms_over_height":None if rms is None else rms/image_height_px,"p95_over_height":None if p95 is None else p95/image_height_px},"threshold_source":"explicit matcher vertical tolerance plus image scale"}


def parameter_stability(samples:Sequence[StereoCalibrationResult],*,focal_relative_limit:float=0.03,principal_normalized_limit:float=0.03,baseline_relative_limit:float=0.05)->dict[str,Any]:
    """Summarize deterministic resampling drift without claiming covariance."""
    if len(samples)<2: return {"status":"DATA_LIMITED","sample_count":len(samples)}
    fx=np.asarray([[s.mono_left.camera_matrix[0,0],s.mono_right.camera_matrix[0,0]] for s in samples]);pp=np.asarray([[s.mono_left.camera_matrix[0,2]/s.image_size_wh[0],s.mono_left.camera_matrix[1,2]/s.image_size_wh[1],s.mono_right.camera_matrix[0,2]/s.image_size_wh[0],s.mono_right.camera_matrix[1,2]/s.image_size_wh[1]] for s in samples]);base=np.asarray([s.baseline_m for s in samples])
    focal=float(np.max(np.ptp(fx,axis=0)/np.maximum(np.mean(fx,axis=0),1e-12)));principal=float(np.max(np.ptp(pp,axis=0)));baseline=float(np.ptp(base)/max(float(np.mean(base)),1e-12));unstable=focal>focal_relative_limit or principal>principal_normalized_limit or baseline>baseline_relative_limit
    return {"status":"CALIBRATION_PARAMETER_UNSTABLE" if unstable else "CALIBRATION_PARAMETER_STABLE_PROXY","sample_count":len(samples),"focal_max_relative_range":focal,"principal_max_normalized_range":principal,"baseline_relative_range":baseline}
