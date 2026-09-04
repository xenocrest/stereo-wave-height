"""Optional official RAFT correspondence estimator for SAME-TIME stereo images.

This is not RAFT-Stereo and is not temporal wave interpolation. Learned flow
is a candidate pixel correspondence only; calibrated epipolar/LR/depth gates
remain compulsory. No learned metric depth, ruler input or height correction.
"""
from pathlib import Path
import numpy as np


def horizontal_disparity(flow_xy: np.ndarray, vertical_tolerance_px: float) -> np.ndarray:
    """Convert (u_other-u_this,v_other-v_this) to signed stereo disparity."""
    flow=np.asarray(flow_xy,float)
    if flow.ndim!=3 or flow.shape[0]!=2 or not np.isfinite(vertical_tolerance_px) or vertical_tolerance_px<=0:
        raise ValueError('flow must have shape [2,height,width] and a positive vertical gate')
    valid=np.all(np.isfinite(flow),axis=0)&(abs(flow[1])<=vertical_tolerance_px)
    return np.where(valid,-flow[0],np.nan).astype(np.float32)


class TorchvisionRaftCorrespondence:
    """Lazy optional dependency; official fixed checkpoint, no online training."""
    name='TORCHVISION_RAFT_SAME_TIME_STEREO_ESTIMATE'

    def __init__(self, checkpoint: Path, *, device: str='cpu', iterations: int=20,
                 vertical_tolerance_px: float=1.5, horizontal_crop_offset_px: int=0):
        import torch
        from torchvision.models.optical_flow import raft_large
        if iterations<1:raise ValueError('positive iteration count required')
        self.torch=torch;self.device=device;self.iterations=iterations;self.vertical_tolerance_px=vertical_tolerance_px
        if horizontal_crop_offset_px<0:raise ValueError('crop offset must be nonnegative')
        self.horizontal_crop_offset_px=horizontal_crop_offset_px
        self.model=raft_large(weights=None,progress=False).eval()
        self.model.load_state_dict(torch.load(str(checkpoint),map_location='cpu',weights_only=True),strict=True)
        self.model.to(device)

    def _flow(self,a: np.ndarray,b: np.ndarray) -> np.ndarray:
        torch=self.torch
        def tensor(im):
            if im.ndim==2:im=np.repeat(im[:,:,None],3,axis=2)
            return torch.from_numpy(np.ascontiguousarray(im[:,:,::-1])).permute(2,0,1)[None].float().to(self.device)/127.5-1
        height,width=a.shape[:2];pa=(-height)%8;pb=(-width)%8
        x,y=[torch.nn.functional.pad(tensor(im),(0,pb,0,pa),mode='replicate') for im in [a,b]]
        with torch.inference_mode():
            flow=self.model(x,y,num_flow_updates=self.iterations)[-1]
        return flow[0,:,:height,:width].cpu().numpy()

    def compute(self,left_bgr: np.ndarray,right_bgr: np.ndarray) -> tuple[np.ndarray,np.ndarray]:
        offset=self.horizontal_crop_offset_px;width=left_bgr.shape[1]
        if offset>=width-128:raise ValueError('crop leaves insufficient model input width')
        left=left_bgr[:,offset:];right=right_bgr[:,:width-offset]
        forward=self._flow(left,right);backward=self._flow(right,left)
        self.last_forward_flow=np.full((2,*left_bgr.shape[:2]),np.nan,np.float32)
        self.last_backward_flow=np.full((2,*right_bgr.shape[:2]),np.nan,np.float32)
        self.last_forward_flow[:,:,offset:]=forward;self.last_forward_flow[0,:,offset:]-=offset
        self.last_backward_flow[:,:,:width-offset]=backward;self.last_backward_flow[0,:,:width-offset]+=offset
        dl=horizontal_disparity(forward,self.vertical_tolerance_px)+offset
        dr=horizontal_disparity(backward,self.vertical_tolerance_px)-offset
        out_left=np.full(left_bgr.shape[:2],np.nan,np.float32);out_right=out_left.copy()
        out_left[:,offset:]=dl;out_right[:,:width-offset]=dr
        return out_left,out_right
