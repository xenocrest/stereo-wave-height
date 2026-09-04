"""Calibration-driven dense stereo fallback independent of WASS.

The module follows the same pinhole geometry as the project model.  It does
not fill invalid disparities and it does not estimate height without an
explicit reference plane.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import cv2
import numpy as np


class DisparityBackend(Protocol):
    """Optional same-time stereo matcher; outputs dL>0, dR<0 in input pixels."""
    name: str

    def compute(self, left_bgr: np.ndarray, right_bgr: np.ndarray) -> tuple[np.ndarray,np.ndarray]: ...


@dataclass(frozen=True)
class DenseStereoPolicy:
    min_disparity: int = 0
    num_disparities: int = 256
    block_size: int = 7
    uniqueness_ratio: int = 10
    speckle_window_size: int = 100
    speckle_range: int = 2
    left_right_tolerance_px: float = 1.5
    pad_search_canvas: bool = False

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
    minimum = -policy.min_disparity-policy.num_disparities+1 if right else policy.min_disparity
    channels = 1
    return cv2.StereoSGBM_create(
        minDisparity=minimum, numDisparities=policy.num_disparities,
        blockSize=policy.block_size,
        P1=8*channels*policy.block_size**2, P2=32*channels*policy.block_size**2,
        disp12MaxDiff=-1, preFilterCap=31, uniquenessRatio=policy.uniqueness_ratio,
        speckleWindowSize=policy.speckle_window_size, speckleRange=policy.speckle_range,
        mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY,
    )


def compute_bidirectional_disparities(gray0: np.ndarray, gray1: np.ndarray,
                                      policy: DenseStereoPolicy) -> tuple[np.ndarray,np.ndarray]:
    """Match on an optional padded canvas, returning ORIGINAL pixel indexing.

    Equal horizontal padding in both views preserves d=u_left-u_right and Q.
    It avoids SGBM's unconditional whole-search-width border exclusion. Padding
    is not image evidence: downstream remap/support and LR gates remain required.
    """
    if gray0.shape!=gray1.shape or gray0.ndim!=2:
        raise ValueError('matching requires equal grayscale image shapes')
    pad=max(abs(policy.min_disparity),abs(policy.min_disparity+policy.num_disparities-1))+policy.block_size if policy.pad_search_canvas else 0
    images=[cv2.copyMakeBorder(g,0,0,pad,pad,cv2.BORDER_CONSTANT,value=0) if pad else g for g in [gray0,gray1]]
    dl=_matcher(policy).compute(images[0],images[1]).astype(np.float32)/16.0
    dr=_matcher(policy,right=True).compute(images[1],images[0]).astype(np.float32)/16.0
    if pad:dl=dl[:,pad:pad+gray0.shape[1]];dr=dr[:,pad:pad+gray0.shape[1]]
    return dl,dr


def left_right_consistency(left_disparity: np.ndarray, right_disparity: np.ndarray,
                           tolerance_px: float) -> np.ndarray:
    """Return pixels satisfying d_L(x)+d_R(x-d_L)=0."""
    left=np.asarray(left_disparity,float);right=np.asarray(right_disparity,float)
    if left.shape != right.shape or left.ndim != 2:
        raise ValueError("left/right disparity shapes must match and be two-dimensional")
    rows,cols=left.shape;yy,xx=np.indices(left.shape)
    xr=np.rint(xx-np.where(np.isfinite(left),left,0)).astype(np.int64)
    inside=(xr>=0)&(xr<cols)&np.isfinite(left)
    sampled=np.full(left.shape,np.nan);sampled[inside]=right[yy[inside],xr[inside]]
    return inside & np.isfinite(sampled) & (np.abs(left+sampled)<=float(tolerance_px))


def disparity_observation_mask(left: np.ndarray, right: np.ndarray,
                               source_left: np.ndarray, source_right: np.ndarray,
                               policy: DenseStereoPolicy) -> tuple[np.ndarray, dict[str, int]]:
    """Reject invalid, censored search-endpoint and unobserved remap matches.

    Values at either search endpoint have no evidence that the optimum lies
    within the search interval. This gate reports missing observations; it
    does not change, interpolate or repair any disparity value.
    """
    left=np.asarray(left,float);right=np.asarray(right,float)
    if left.ndim != 2 or any(np.shape(a)!=left.shape for a in (right,source_left,source_right)):
        raise ValueError("disparities and source support masks must share a 2D shape")
    low=policy.min_disparity;high=low+policy.num_disparities-1
    left_ok=np.isfinite(left)&(left>low)&(left<high)
    right_ok=np.isfinite(right)&(right>-high)&(right<-low)
    clean_right=np.where(right_ok&np.asarray(source_right,bool),right,np.nan)
    consistent=left_right_consistency(left,clean_right,policy.left_right_tolerance_px)
    valid=left_ok&np.asarray(source_left,bool)&consistent
    return valid,{
        "left_search_endpoint_count":int(np.sum(np.isfinite(left)&((left==low)|(left==high)))),
        "left_interior_search_count":int(left_ok.sum()),
        "left_source_support_count":int(np.count_nonzero(source_left)),
        "right_source_support_count":int(np.count_nonzero(source_right)),
        "bidirectional_observation_count":int(valid.sum()),
    }


def _remap_support(maps: tuple[np.ndarray, np.ndarray], width: int, height: int,
                   block_size: int) -> np.ndarray:
    """Require the bilinear source footprint and matching block to be observed."""
    x,y=maps
    valid=np.isfinite(x)&np.isfinite(y)&(x>=0)&(x<width-1)&(y>=0)&(y<height-1)
    return cv2.erode(valid.astype(np.uint8),np.ones((block_size,block_size),np.uint8),
                     borderType=cv2.BORDER_CONSTANT,borderValue=0).astype(bool)


def reconstruct_dense_stereo(
    left_image: np.ndarray, right_image: np.ndarray, *,
    K0: np.ndarray, D0: np.ndarray, K1: np.ndarray, D1: np.ndarray,
    R_right_from_left: np.ndarray, T_right_from_left_m: np.ndarray,
    policy: DenseStereoPolicy = DenseStereoPolicy(),
    rectification_alpha: float = 0.0,
    disparity_backend: DisparityBackend | None = None,
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
    if disparity_backend is None:
        dl,dr=compute_bidirectional_disparities(gray0,gray1,policy)
    else:
        dl,dr=disparity_backend.compute(rect0,rect1)
        dl=np.asarray(dl,np.float32);dr=np.asarray(dr,np.float32)
        if dl.shape!=(height,width) or dr.shape!=(height,width):
            raise ValueError('backend disparity shape must match original rectified images')
    valid,counts=disparity_observation_mask(dl,dr,
        _remap_support(map0,width,height,policy.block_size),
        _remap_support(map1,width,height,policy.block_size),policy)
    xyz=cv2.reprojectImageTo3D(dl,Q).astype(np.float64)
    physical=np.all(np.isfinite(xyz),axis=2)&(xyz[:,:,2]>0)
    counts['nonpositive_or_nonfinite_depth_rejected']=int(np.sum(valid&~physical))
    valid &= physical
    xyz[~valid]=np.nan;disparity=dl.copy();disparity[~valid]=np.nan
    return DenseStereoResult(disparity,xyz,valid,rect0,rect1,{
        "backend":"OPENCV_STEREOSGBM_CALIBRATED_FALLBACK" if disparity_backend is None else disparity_backend.name,"coordinate_system":"rectified_left_camera",
        "xyz_unit":"m","valid_count":int(valid.sum()),"valid_ratio":float(valid.mean()),
        "baseline_m":float(np.linalg.norm(T)),"rectification_roi_left":list(roi0),"rectification_roi_right":list(roi1),
        "left_right_tolerance_px":policy.left_right_tolerance_px,
        "rectification_alpha":rectification_alpha,
        "observation_gates":counts,
        "search_endpoint_policy":"REJECT_CENSORED_MATCHES_NO_FILL" if disparity_backend is None else "PIXEL_RANGE_AND_LR_GATES_NO_FILL",
        "pad_search_canvas":policy.pad_search_canvas if disparity_backend is None else False,
        "observation_kind":"CLASSICAL_STEREO_CANDIDATE" if disparity_backend is None else "LEARNED_CORRESPONDENCE_CANDIDATE",
    })
