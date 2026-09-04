"""Calibration-driven dense stereo fallback independent of WASS.

The module follows the same pinhole geometry as the project model.  It does
not fill invalid disparities and it does not estimate height without an
explicit reference plane.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np


@dataclass(frozen=True)
class DenseStereoPolicy:
    min_disparity: int = 0
    num_disparities: int = 256
    block_size: int = 7
    uniqueness_ratio: int = 10
    speckle_window_size: int = 100
    speckle_range: int = 2
    left_right_tolerance_px: float = 1.5

    def __post_init__(self) -> None:
        if self.num_disparities <= 0 or self.num_disparities % 16:
            raise ValueError("num_disparities must be a positive multiple of 16")
        if self.block_size < 3 or self.block_size % 2 == 0:
            raise ValueError("block_size must be odd and at least 3")
        if self.left_right_tolerance_px <= 0:
            raise ValueError("left_right_tolerance_px must be positive")


@dataclass(frozen=True)
class DenseStereoResult:
    disparity_px: np.ndarray
    xyz_m: np.ndarray
    valid_mask: np.ndarray
    rectified_left: np.ndarray
    rectified_right: np.ndarray
    metadata: dict[str, Any]


def _matcher(policy: DenseStereoPolicy, *, right: bool = False) -> cv2.StereoSGBM:
    minimum = -policy.min_disparity-policy.num_disparities if right else policy.min_disparity
    channels = 1
    return cv2.StereoSGBM_create(
        minDisparity=minimum, numDisparities=policy.num_disparities,
        blockSize=policy.block_size,
        P1=8*channels*policy.block_size**2, P2=32*channels*policy.block_size**2,
        disp12MaxDiff=-1, preFilterCap=31, uniquenessRatio=policy.uniqueness_ratio,
        speckleWindowSize=policy.speckle_window_size, speckleRange=policy.speckle_range,
        mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY,
    )


def left_right_consistency(left_disparity: np.ndarray, right_disparity: np.ndarray,
                           tolerance_px: float) -> np.ndarray:
    """Return pixels satisfying d_L(x)+d_R(x-d_L)=0."""
    left=np.asarray(left_disparity,float);right=np.asarray(right_disparity,float)
    if left.shape != right.shape or left.ndim != 2:
        raise ValueError("left/right disparity shapes must match and be two-dimensional")
    rows,cols=left.shape;yy,xx=np.indices(left.shape);xr=np.rint(xx-left).astype(np.int64)
    inside=(xr>=0)&(xr<cols)&np.isfinite(left)
    sampled=np.full(left.shape,np.nan);sampled[inside]=right[yy[inside],xr[inside]]
    return inside & np.isfinite(sampled) & (np.abs(left+sampled)<=float(tolerance_px))


def reconstruct_dense_stereo(
    left_image: np.ndarray, right_image: np.ndarray, *,
    K0: np.ndarray, D0: np.ndarray, K1: np.ndarray, D1: np.ndarray,
    R_right_from_left: np.ndarray, T_right_from_left_m: np.ndarray,
    policy: DenseStereoPolicy = DenseStereoPolicy(),
    rectification_alpha: float = 0.0,
) -> DenseStereoResult:
    """Rectify, match and reproject a stereo pair using calibrated geometry."""
    left=np.asarray(left_image);right=np.asarray(right_image)
    if left.shape[:2] != right.shape[:2] or left.ndim not in (2,3):
        raise ValueError("stereo images must have matching image dimensions")
    height,width=left.shape[:2];size=(width,height)
    K0=np.asarray(K0,float);K1=np.asarray(K1,float);D0=np.asarray(D0,float).reshape(-1);D1=np.asarray(D1,float).reshape(-1)
    R=np.asarray(R_right_from_left,float);T=np.asarray(T_right_from_left_m,float).reshape(3,1)
    if K0.shape!=(3,3) or K1.shape!=(3,3) or R.shape!=(3,3) or not np.all(np.isfinite(T)) or np.linalg.norm(T)<=0:
        raise ValueError("finite K0/D0/K1/D1/R/T with non-zero metric T are required")
    if not np.isfinite(rectification_alpha) or not -1 <= rectification_alpha <= 1:
        raise ValueError("rectification alpha must be finite and between -1 and 1")
    R0,R1,P0,P1,Q,roi0,roi1=cv2.stereoRectify(K0,D0,K1,D1,size,R,T,flags=cv2.CALIB_ZERO_DISPARITY,alpha=rectification_alpha)
    map0=cv2.initUndistortRectifyMap(K0,D0,R0,P0,size,cv2.CV_32FC1)
    map1=cv2.initUndistortRectifyMap(K1,D1,R1,P1,size,cv2.CV_32FC1)
    rect0=cv2.remap(left,*map0,cv2.INTER_LINEAR);rect1=cv2.remap(right,*map1,cv2.INTER_LINEAR)
    gray0=cv2.cvtColor(rect0,cv2.COLOR_BGR2GRAY) if rect0.ndim==3 else rect0
    gray1=cv2.cvtColor(rect1,cv2.COLOR_BGR2GRAY) if rect1.ndim==3 else rect1
    dl=_matcher(policy).compute(gray0,gray1).astype(np.float32)/16.0
    dr=_matcher(policy,right=True).compute(gray1,gray0).astype(np.float32)/16.0
    consistent=left_right_consistency(dl,dr,policy.left_right_tolerance_px)
    valid=consistent & (dl>policy.min_disparity) & (dl<policy.min_disparity+policy.num_disparities)
    xyz=cv2.reprojectImageTo3D(dl,Q).astype(np.float64);valid &= np.all(np.isfinite(xyz),axis=2)
    xyz[~valid]=np.nan;disparity=dl.copy();disparity[~valid]=np.nan
    return DenseStereoResult(disparity,xyz,valid,rect0,rect1,{
        "backend":"OPENCV_STEREOSGBM_CALIBRATED_FALLBACK","coordinate_system":"rectified_left_camera",
        "xyz_unit":"m","valid_count":int(valid.sum()),"valid_ratio":float(valid.mean()),
        "baseline_m":float(np.linalg.norm(T)),"rectification_roi_left":list(roi0),"rectification_roi_right":list(roi1),
        "left_right_tolerance_px":policy.left_right_tolerance_px,
        "rectification_alpha":rectification_alpha,
    })
