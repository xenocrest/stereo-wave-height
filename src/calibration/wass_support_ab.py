"""Read-only support comparison for one controlled OLD/NEW WASS A/B result."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from typing import Any
import numpy as np
import yaml

LOCKED=("stereo_videos","target_time_s","left_frame_id","right_frame_id","sync_model","sync_residual_ms","matcher_config_hash","stereo_config_hash","post_filter","water_roi","rectification_policy")

def validate_single_variable(old:dict[str,Any],new:dict[str,Any])->None:
    changed=[key for key in LOCKED if old.get(key)!=new.get(key)]
    if changed:raise ValueError("AB_INVALID_MULTIPLE_VARIABLES_CHANGED: "+", ".join(changed))
    if old.get("calibration_id")==new.get("calibration_id"):return

def spatial_occupancy(uv:np.ndarray,roi:tuple[float,float,float,float],grid_size:int=10)->dict[str,Any]:
    points=np.asarray(uv,float).reshape(-1,2);x,y,w,h=roi
    if w<=0 or h<=0 or grid_size<=0:raise ValueError("positive ROI/grid required")
    inside=points[(points[:,0]>=x)&(points[:,0]<x+w)&(points[:,1]>=y)&(points[:,1]<y+h)]
    cells=set((min(grid_size-1,int((px-x)/w*grid_size)),min(grid_size-1,int((py-y)/h*grid_size))) for px,py in inside)
    return {"grid_size":grid_size,"occupied_cells":len(cells),"total_cells":grid_size**2,"coverage_percent":100*len(cells)/(grid_size**2)}

def recommendation(old:dict[str,Any],new:dict[str,Any])->dict[str,str]:
    if not new.get("reconstruction_success",False):return {"classification":"WASS_AB_GEOMETRY_REGRESSION","recommendation":"KEEP_OLD"}
    old_rms=float(old["geometry_qa"]["plane_rms_m"]);new_rms=float(new["geometry_qa"]["plane_rms_m"])
    if not new["geometry_qa"].get("finite",False) or new_rms>max(old_rms*1.25,old_rms+.001):return {"classification":"WASS_AB_GEOMETRY_REGRESSION","recommendation":"KEEP_OLD"}
    count_gain=new["water_roi_direct_observed_count"]>old["water_roi_direct_observed_count"]
    spatial_gain=new["support_grid_occupied_cells"]>old["support_grid_occupied_cells"]
    if count_gain and spatial_gain:return {"classification":"WASS_AB_SUPPORT_IMPROVED","recommendation":"PROMOTE"}
    if not count_gain and not spatial_gain:return {"classification":"WASS_AB_NO_MATERIAL_IMPROVEMENT","recommendation":"KEEP_OLD"}
    return {"classification":"WASS_AB_MIXED_SUPPORT_CHANGE","recommendation":"REVIEW"}

def evaluate(old:dict[str,Any],new:dict[str,Any],old_uv:np.ndarray,new_uv:np.ndarray)->dict[str,Any]:
    validate_single_variable(old,new);roi=tuple(old["water_roi"]);oo=spatial_occupancy(old_uv,roi);no=spatial_occupancy(new_uv,roi)
    def enrich(meta,uv,occupancy):
        points=np.asarray(uv,float).reshape(-1,2);x,y,w,h=roi;inside=(points[:,0]>=x)&(points[:,0]<x+w)&(points[:,1]>=y)&(points[:,1]<y+h);bbox=None if not len(points) else [float(points[:,0].min()),float(points[:,1].min()),float(points[:,0].max()),float(points[:,1].max())]
        return {**meta,"pixel_xyz_observed_count":len(points),"water_roi_direct_observed_count":int(inside.sum()),"water_roi_observed_percent":100*int(inside.sum())/(w*h),"support_bounding_box_px":bbox,"support_grid_occupied_cells":occupancy["occupied_cells"],"support_grid_coverage_percent":occupancy["coverage_percent"]}
    old=enrich(old,old_uv,oo);new=enrich(new,new_uv,no)
    return {"single_variable_validated":True,"old":old,"new":new,"decision":recommendation(old,new)}

def save_support_maps(old_uv:np.ndarray,new_uv:np.ndarray,roi:tuple[float,float,float,float],output:Path)->None:
    import matplotlib.pyplot as plt
    x,y,w,h=roi
    for name,points,color in (("old_support_map",old_uv,"tab:blue"),("new_support_map",new_uv,"tab:orange")):
        fig,ax=plt.subplots(figsize=(6,4));ax.scatter(points[:,0],points[:,1],s=1,c=color);ax.add_patch(plt.Rectangle((x,y),w,h,fill=False,color="red"));ax.invert_yaxis();ax.set_aspect("equal");fig.savefig(output/f"{name}.png",dpi=140,bbox_inches="tight");plt.close(fig)
    fig,ax=plt.subplots(figsize=(6,4));ax.scatter(old_uv[:,0],old_uv[:,1],s=1,label="OLD",alpha=.5);ax.scatter(new_uv[:,0],new_uv[:,1],s=1,label="NEW",alpha=.5);ax.add_patch(plt.Rectangle((x,y),w,h,fill=False,color="red"));ax.invert_yaxis();ax.legend();ax.set_aspect("equal");fig.savefig(output/"old_vs_new_support_overlay.png",dpi=140,bbox_inches="tight");plt.close(fig)

def main()->None:
    p=argparse.ArgumentParser();p.add_argument("--old-metadata",required=True);p.add_argument("--new-metadata",required=True);p.add_argument("--old-uv",required=True);p.add_argument("--new-uv",required=True);p.add_argument("--output",required=True);a=p.parse_args();load=lambda x:yaml.safe_load(Path(x).read_text(encoding="utf-8")) if Path(x).suffix in {".yaml",".yml"} else json.loads(Path(x).read_text(encoding="utf-8"));
    def uv(path):
        data=np.load(path)
        if isinstance(data,np.lib.npyio.NpzFile):return np.column_stack((data["u_px"],data["v_px"]))
        return np.asarray(data)
    old,new=load(a.old_metadata),load(a.new_metadata);old_uv,new_uv=uv(a.old_uv),uv(a.new_uv);result=evaluate(old,new,old_uv,new_uv);out=Path(a.output);out.mkdir(parents=True,exist_ok=True);(out/"wass_support_ab.yaml").write_text(yaml.safe_dump(result,sort_keys=False),encoding="utf-8");save_support_maps(old_uv,new_uv,tuple(old["water_roi"]),out)
if __name__=="__main__":main()
