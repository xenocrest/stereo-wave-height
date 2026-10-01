"""Actual WASS XYZ projection, config differences, support attribution and manifests."""
import sys,json,re,shutil
from pathlib import Path
import cv2,numpy as np
from scipy.io import loadmat
from scipy.spatial import Delaunay
from plyfile import PlyData
REPO=Path(__file__).resolve().parents[2];sys.path[:0]=[str(REPO),str(REPO/'src')]
from audit.scripts.inspect_artifacts import ROOT,RUNS,dump,digest,stats,project,EVIDENCE
from wassgridsurface.wass_utils import load_camera_mesh,align_on_sea_plane_RT
from app import core

def parameter_lines(path):
    vals={}
    for line in Path(path).read_text('utf-8',errors='replace').splitlines():
        m=re.match(r'^\s*([^#\s=]+)\s*=\s*(.*?)\s*$',line)
        if m:vals[m[1]]=m[2]
    return vals

def defaults(path):
    return {m.group(1):m.group(2) for m in re.finditer(r'^\s*#?([^#\s=]+)\s*=\s*(.*?)\s*$',Path(path).read_text('utf-8'),re.M)}

def main():
    cfg=defaults(EVIDENCE/'WASS_OFFICIAL_DEFAULT.txt')
    hc=RUNS['HomeTank21'][0]/'wass/config/stereo_config.txt';vc=RUNS['Vieira0'][0]/'wass/config/stereo_config.txt'
    h,v=parameter_lines(hc),parameter_lines(vc)
    dump('config_comparison.json',{'sources':{'WASS_OFFICIAL_DEFAULT':str(EVIDENCE/'WASS_OFFICIAL_DEFAULT.txt'),'CURRENT_HOMETANK_CONFIG':str(hc),'VIEIRA_PUBLIC_CONFIG':str(vc)},'effective_values':{k:{'default':cfg.get(k),'hometank':h.get(k,cfg.get(k)),'vieira':v.get(k,cfg.get(k))} for k in sorted(set(cfg)|set(h)|set(v))},'hometank_overrides':h,'vieira_overrides':v})
    for source,label in [(hc,'CURRENT_HOMETANK_CONFIG'),(vc,'VIEIRA_PUBLIC_CONFIG')]:
        text=source.read_text('utf-8')
        (EVIDENCE/(label+'.txt')).write_text('\n'.join(line.rstrip() for line in text.splitlines()).rstrip()+'\n',encoding='utf-8')
    details={};flow=[]
    for label,(root,frame) in RUNS.items():
        ws=root/'wass/workspaces'/f'{frame:06d}_wd';s=loadmat(root/'surface/config.mat')
        mesh=load_camera_mesh(ws/'mesh_cam.xyzC');a=align_on_sea_plane_RT(mesh,s['Rpl'],s['Tpl'])*s['CAM_BASELINE'].item()
        w,h=int(s['Iw'].item()) if 'Iw' in s else 1920,int(s['Ih'].item()) if 'Ih' in s else 1080
        norm=np.array([[2/w,0,-1,0],[0,2/h,-1,0],[0,0,1,0],[0,0,0,1]])
        P=np.linalg.inv(norm)@s['P0plane']
        rawuv=project(np.loadtxt(ws/'P0cam.txt'),mesh.T);griduv=project(P,a.T)
        with np.load(root/'pixel/pixel_height'/f'{frame:08d}.npz') as n:
            xyz=n['xyz'];source=n['source'];mh,mw=xyz.shape[:2]
        sampleids=np.random.default_rng(31).choice(mesh.shape[1],32,False);samples=[]
        for idx in sampleids:
            u,v=rawuv[idx];mu,mv=int(u*mw/w),int(v*mh/h)
            mapped=None
            if 0<=mu<mw and 0<=mv<mh and source[mv,mu]!=0:mapped=xyz[mv,mu].tolist()
            samples.append({'WASS_point_id':int(idx),'WASS_XYZ_B':mesh[:,idx].tolist(),'official_aligned_XYZ':a[:,idx].tolist(),'undistorted_projection_from_raw_WASS':rawuv[idx].tolist(),'projection_from_official_aligned_point':griduv[idx].tolist(),'queried_mapping_uv':[mu,mv],'pixel_xyz_grid_estimate':mapped,'xyz_difference_native':None if mapped is None else float(np.linalg.norm(a[:,idx]-mapped))})
        occupied=np.load(ROOT/f'{label}_analysis.npz');XX,YY,ZZ=occupied['XX'],occupied['YY'],occupied['ZZ']
        inside=Delaunay(a[:2].T).find_simplex(np.c_[XX.ravel(),YY.ravel()])>=0
        row={'actual_WASS_point_projection_samples':samples,'official_alignment_forward_projection_error_px':stats(np.linalg.norm(rawuv-griduv,axis=1)),
             'grid_cells_outside_cloud_XY_convex_hull':int((~inside).sum()),'grid_outside_hull_finite_count':int(np.sum((~inside)&np.isfinite(ZZ.ravel())))}
        if label.startswith('HomeTank'):
            mask0=np.zeros((1080,1920),np.uint8)
            cv2.fillPoly(mask0,[np.array([[1180,220],[1440,220],[1390,810],[1120,810]],np.int32)],1)
            cv2.rectangle(mask0,(620,320),(1080,500),1,-1)
            xy=np.rint(rawuv).astype(int);ok=(xy[:,0]>=0)&(xy[:,0]<1920)&(xy[:,1]>=0)&(xy[:,1]<1080)
            hits=np.zeros(len(xy),bool);hits[ok]=mask0[xy[ok,1],xy[ok,0]]>0
            row['points_projected_into_explicit_ruler_and_upper_backwall_polygons']=int(hits.sum())
            row['nonwater_annotation_scope']='conservative lower bound, two hand-annotated polygons only; no automatic segmentation'
            polygon=np.zeros((1080,1920),np.uint8);cv2.fillPoly(polygon,[np.array([[420,835],[1390,835],[1660,1035],[440,1035]],np.int32)],1)
            water=np.zeros(len(xy),bool);water[ok]=polygon[xy[ok,1],xy[ok,0]]>0
            row['filtered_points_in_conservative_foreground_water_mask_cam0']=int(water.sum())
        details[label]=row
        listing=[('raw_cam0',Path(json.loads((EVIDENCE/f'{label}.json').read_text('utf-8'))['raw_path'])),('undistorted_cam0',ws/'undistorted/00000000.png'),('undistorted_cam1',ws/'undistorted/00000001.png'),('rectified_preview',ws/'stereo.jpg'),('disparity_preview',ws/'disparity_stereo_ouput.png'),('disparity_filtered_preview',ws/'disparity_final_scaled.png'),('cloud_after_zgap_before_plane',ws/'mesh_full.ply'),('filtered_cloud',ws/'mesh_cam.xyzC'),('filtered_ply',ws/'mesh.ply'),('plane',ws/'plane.txt'),('setup',root/'surface/config.mat'),('grid',root/'surface/gridded.nc'),('pixel_xyz',root/'pixel/pixel_xyz'/f'{frame:08d}.mat'),('pixel_npz',root/'pixel/pixel_height'/f'{frame:08d}.npz')]
        for stage,path in listing:
            item={'dataset':label,'frame_id':frame,'stage':stage,'path':str(path),'exists':path.exists()}
            if path.exists():
                item.update(bytes=path.stat().st_size,sha256=digest(path))
                if path.suffix in ['.jpg','.png']:item['shape']=cv2.imread(str(path)).shape
                elif path.suffix=='.ply':item['points']=len(PlyData.read(path)['vertex'].data)
            flow.append(item)
    dump('actual_XYZ_projection_and_support.json',details);dump('artifact_manifest.json',flow)
    print(json.dumps({k:{q:v for q,v in r.items() if q!='actual_WASS_point_projection_samples'} for k,r in details.items()},default=str))

if __name__=='__main__':main()
