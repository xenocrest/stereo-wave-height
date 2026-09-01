"""Read-only dense-result visualization and canonical-pixel query helpers."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import numpy as np
from PIL import Image
import yaml
from scipy.spatial import cKDTree

from surface_completion.dense_map import canonical_to_rectified

UNSUPPORTED, OBSERVED, ESTIMATED = 0, 1, 2


@dataclass(frozen=True)
class DisplayTransform:
    source_width: int; source_height: int; display_width: int; display_height: int
    offset_x: float; offset_y: float; scale: float

    @classmethod
    def fit(cls, source_width: int, source_height: int, canvas_width: int, canvas_height: int) -> "DisplayTransform":
        scale=min(canvas_width/source_width,canvas_height/source_height)
        width,height=source_width*scale,source_height*scale
        return cls(source_width,source_height,int(round(width)),int(round(height)),(canvas_width-width)/2,(canvas_height-height)/2,scale)

    def canvas_to_pixel(self,x:float,y:float) -> tuple[int,int] | None:
        u=(x-self.offset_x)/self.scale; v=(y-self.offset_y)/self.scale
        if u<0 or v<0 or u>=self.source_width or v>=self.source_height:return None
        return int(u),int(v)

    def pixel_to_canvas(self, u: float, v: float) -> tuple[float, float]:
        return self.offset_x + u * self.scale, self.offset_y + v * self.scale

    def canvas_to_full_pixel(self,x:float,y:float,crop_origin:tuple[int,int]=(0,0))->tuple[int,int]|None:
        pixel=self.canvas_to_pixel(x,y)
        return None if pixel is None else (pixel[0]+crop_origin[0],pixel[1]+crop_origin[1])

    def full_pixel_to_canvas(self,u:float,v:float,crop_origin:tuple[int,int]=(0,0))->tuple[float,float]:
        return self.pixel_to_canvas(u-crop_origin[0],v-crop_origin[1])


@dataclass(frozen=True)
class PixelQuery:
    pixel: tuple[int,int]; status: str; source: str; height_mm: float|None; xyz_m: tuple[float,float,float]|None


class DenseMeasurementView:
    def __init__(self,dense_npz:Path,pixel_xyz_npz:Path,mapping_yaml:Path) -> None:
        with np.load(dense_npz) as dense:
            self.height=dense["height_mm"].copy(); self.status=dense["status"].copy(); self.roi=dense["water_roi_mask"].copy()
        with np.load(pixel_xyz_npz) as sparse:
            self.xyz=sparse["xyz_m"].copy(); pixels=np.column_stack((sparse["u_px"],sparse["v_px"]))
        self.tree=cKDTree(pixels)
        self.mapping=yaml.safe_load(Path(mapping_yaml).read_text(encoding="utf-8"))

    def query(self,u:int,v:int) -> PixelQuery:
        if u<0 or v<0 or v>=self.status.shape[0] or u>=self.status.shape[1] or not self.roi[v,u]:
            return PixelQuery((u,v),"OUTSIDE_ROI","UNSUPPORTED",None,None)
        code=int(self.status[v,u])
        if code==UNSUPPORTED:return PixelQuery((u,v),"UNSUPPORTED","UNSUPPORTED",None,None)
        height=float(self.height[v,u])
        if code==ESTIMATED:return PixelQuery((u,v),"ESTIMATED","SURFACE_ESTIMATED",height,None)
        rectified=canonical_to_rectified(np.asarray([[u,v]],dtype=np.float64),self.mapping)[0]
        distance,index=self.tree.query(rectified,k=1)
        if distance>2.0: raise RuntimeError("OBSERVED pixel violates frozen 2 px direct-observation gate")
        xyz=tuple(float(value) for value in self.xyz[int(index)])
        return PixelQuery((u,v),"OBSERVED","DIRECT_STEREO",height,xyz)


def make_height_overlay(original:Path,dense_npz:Path,alpha:float=0.45) -> Image.Image:
    if not 0<=alpha<=1:raise ValueError("alpha must be in [0,1]")
    base=np.asarray(Image.open(original).convert("RGB"),dtype=np.float32)
    with np.load(dense_npz) as dense:
        h=dense["height_mm"].copy(); valid=dense["valid_mask"].copy() & np.isfinite(h)
    color=np.zeros_like(base); values=h[valid]
    if values.size:
        lo,hi=np.percentile(values,(2,98)); norm=np.zeros_like(h,dtype=np.float32); norm[valid]=np.clip((h[valid]-lo)/max(hi-lo,1e-9),0,1)
        color[...,0]=255*norm; color[...,1]=255*(1-np.abs(2*norm-1)); color[...,2]=255*(1-norm)
        base[valid]=(1-alpha)*base[valid]+alpha*color[valid]
    return Image.fromarray(np.clip(base,0,255).astype(np.uint8),"RGB")
