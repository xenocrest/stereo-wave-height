"""Read-only independent audit of frozen artifacts; writes only audit evidence.

No new reconstruction, reference fit, correction, or formal-code edits.
"""
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path
import cv2
import numpy as np
from scipy.io import loadmat
from scipy.spatial import cKDTree
from netCDF4 import Dataset
from plyfile import PlyData

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / 'src')]
from app import core, coordinates
from wassgridsurface.wass_utils import load_camera_mesh, align_on_sea_plane_RT

ROOT = Path('D:/stereo-wave-height-runs/independent-quality-audit-20261001')
EVIDENCE = REPO / 'audit/evidence'
HROOT = Path('D:/stereo-wave-height-runs/fixed-coordinate-acceptance-20261001-final')
RUNS = {'HomeTank21': (HROOT/'Run_A/science', 1),
        'HomeTank22': (HROOT/'Run_B/science', 0),
        'HomeTank23': (HROOT/'Run_C/science', 0),
        'Vieira0': (Path('D:/stereo-wave-height-runs/pipeline/vieira_official/run_20260928_113344'), 0)}

def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''): h.update(b)
    return h.hexdigest()

def stats(x):
    a=np.asarray(x); a=a[np.isfinite(a)]
    return {'count':len(a), 'quantiles_0_2_50_98_100':np.percentile(a,[0,2,50,98,100]).tolist()} if a.size else {'count':0}

def dump(name, data):
    EVIDENCE.mkdir(parents=True,exist_ok=True)
    (EVIDENCE/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,default=lambda x:int(x) if isinstance(x,np.integer) else float(x) if isinstance(x,np.floating) else str(x)),encoding='utf-8')

def project(P, xyz):
    v=np.c_[np.asarray(xyz),np.ones(len(xyz))]@P.T
    return v[:,:2]/v[:,2,None]

def inspect(label, root, frame):
    ws=root/'wass/workspaces'/f'{frame:06d}_wd'
    setup=loadmat(root/'surface/config.mat')
    nc=Dataset(root/'surface/gridded.nc')
    meta=nc['meta']; w,h=int(meta.image_width),int(meta.image_height)
    P=np.linalg.inv(np.array([[2/w,0,-1,0],[0,2/h,-1,0],[0,0,1,0],[0,0,0,1]]))@np.asarray(meta['P0plane'])
    sync=json.loads((root/'sync/sync.json').read_text('utf-8'))
    rawpath=sorted((root/'sync/frames/cam0').glob('*'))[frame]
    raw=cv2.imread(str(rawpath)); undist=cv2.imread(str(ws/'undistorted/00000000.png'))
    K=np.asarray(setup['K0']); D=np.zeros(5)
    from pipeline.adapters.wass import load_matrix
    D=load_matrix(root/'wass/config/distortion_00.xml').flatten()
    ref=core.load_reference(HROOT/'reference_plane.json')[0] if label.startswith('HomeTank') else core.reference_from_run(root,0)
    result=core.load_result(root,frame,ref)
    xyz=result['xyz']; source=result['source']; valid=source!=0
    v,u=np.where(valid)
    chosen=np.random.default_rng(20261001).choice(len(v),min(1000,len(v)),replace=False)
    vs,us=v[chosen],u[chosen]; samples=xyz[vs,us]
    uv=project(P,samples)
    # OpenGL raster centers should be u+0.5,v+0.5 after logical/physical scaling.
    target=(np.c_[us,vs]+0.5)*[w/xyz.shape[1],h/xyz.shape[0]]
    cam=np.c_[samples,np.ones(len(samples))]@np.linalg.inv(setup['Cam0toGrid']).T
    uvraw=cv2.projectPoints(np.ascontiguousarray(cam[:,:3],dtype=np.float64),np.zeros(3),np.zeros(3),K,D)[0].reshape(-1,2)
    displayed=target.copy() # GUI resizes raw to mapping and only rescales hover coordinates.
    rows=[]
    for i in range(min(32,len(samples))):
        hu=core.hover(result,int(us[i]),int(vs[i]))
        rows.append({'map_uv':[int(us[i]),int(vs[i])],'grid_xyz':samples[i].tolist(),'project_undist_uv':uv[i].tolist(),'project_raw_uv':uvraw[i].tolist(),'gui_raw_uv':displayed[i].tolist(),'raw_alignment_error_px':float(np.linalg.norm(uvraw[i]-displayed[i])),'hover':hu})
    mesh=load_camera_mesh(ws/'mesh_cam.xyzC')
    aligned=align_on_sea_plane_RT(mesh,setup['Rpl'],setup['Tpl'])*float(setup['CAM_BASELINE'].item())
    fullpath=ws/'mesh_full.ply'
    full=None
    if fullpath.exists():
        vertex=PlyData.read(fullpath)['vertex'].data
        full=np.vstack([vertex[n] for n in ('x','y','z')])
    XX=np.asarray(nc['X_grid'])/1000; YY=np.asarray(nc['Y_grid'])/1000
    ZZ=np.asarray(nc['Z'][frame].filled(np.nan))/1000
    gx=np.rint((aligned[0]-XX.min())/(XX.max()-XX.min())*(XX.shape[1]-1)).astype(int)
    gy=np.rint((aligned[1]-YY.min())/(YY.max()-YY.min())*(YY.shape[0]-1)).astype(int)
    good=(gx>=0)&(gx<XX.shape[1])&(gy>=0)&(gy<XX.shape[0])
    occupancy=np.zeros(XX.shape,bool); occupancy[gy[good],gx[good]]=True
    gridvalid=np.isfinite(ZZ)
    dist=cKDTree(np.c_[aligned[0,good],aligned[1,good]]).query(np.c_[XX[gridvalid],YY[gridvalid]])[0]
    rawuv=project(np.loadtxt(ws/'P0cam.txt'),mesh.T)
    data={'root':str(root),'frame':frame,'identity':coordinates.identity(root),
          'raw_path':str(rawpath),'raw_shape':raw.shape,'undist_shape':undist.shape,'map_shape':xyz.shape,
          'meta_image_wh':[w,h], 'K0':K.tolist(),'D0':D.tolist(),'Rpl':setup['Rpl'].tolist(),'Tpl':setup['Tpl'].tolist(),
          'baseline':float(setup['CAM_BASELINE'].item()),'reference':ref.as_dict(),'timestamp':result['timestamp_s'],
          'provenance_counts':{str(i):int(np.sum(source==i)) for i in range(3)},
          'map_reprojection_error_vs_pixel_centers_px':stats(np.linalg.norm(uv-target,axis=1)),
          'gui_raw_alignment_error_px':stats(np.linalg.norm(uvraw-displayed,axis=1)),
          'cloud_filtered_count':mesh.shape[1],'cloud_preplane_count':None if full is None else full.shape[1],
          'cloud_camera_axis_ranges':[stats(row) for row in mesh],
          'aligned_axis_ranges':[stats(row) for row in aligned],
          'grid_shape':XX.shape,'grid_xy_extent':[XX.min(),XX.max(),YY.min(),YY.max()],
          'grid_valid_count':int(gridvalid.sum()),'occupied_cells':int(occupancy.sum()),
          'grid_without_direct_cell_observation_count':int(np.sum(gridvalid&~occupancy)),
          'grid_nearest_observation_distance_native':stats(dist),'grid_z':stats(ZZ),
          'mapped_z':stats(xyz[...,2][valid]),'mapped_fixed_h':stats(result['height'][valid]),
          'reference_height_minus_z':stats((result['height']-xyz[...,2])[valid]),'projection_samples':rows}
    ROOT.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(ROOT/f'{label}_analysis.npz',aligned=aligned,full=full if full is not None else np.zeros((3,0)),rawuv=rawuv,XX=XX,YY=YY,ZZ=ZZ,occupancy=occupancy)
    nc.close()
    dump(f'{label}.json',data)
    print(label,json.dumps({k:data[k] for k in ('map_reprojection_error_vs_pixel_centers_px','gui_raw_alignment_error_px','raw_shape','map_shape','cloud_filtered_count','occupied_cells','grid_valid_count','grid_z','mapped_fixed_h')},default=str))
    return data

def provenance():
    from pipeline.adapters.wass import load_matrix
    history=Path('D:/stereo-wave-height-runs/HomeTank_004/wave-reconstruction-pipeline-20260824/wass_workspace/config')
    rows={}
    for label,(root,_) in RUNS.items():
        if not label.startswith('HomeTank'):continue
        checks={}
        for name in ('intrinsics_00.xml','intrinsics_01.xml','distortion_00.xml','distortion_01.xml','ext_R.xml','ext_T.xml'):
            active=root/'wass/config'/name
            fresh=root/'calibration'/name
            checks[name]={'active_path':str(active),'historical_path':str(history/name), 'active_hash':digest(active),'historical_hash':digest(history/name),'hash_equal_to_history':digest(active)==digest(history/name),'numeric_equal_to_history':bool(np.array_equal(load_matrix(active),load_matrix(history/name))),'numeric_equal_to_calibration_dir':bool(np.array_equal(load_matrix(active),load_matrix(fresh))) if fresh.exists() else None,'active_matrix':load_matrix(active).tolist()}
        ws=sorted((root/'wass/workspaces').glob('*_wd'))
        for p in ws:
            checks[str(p)]={n:bool(np.array_equal(load_matrix(p/dst),load_matrix(root/'wass/config'/src))) for n,src,dst in [('K0','intrinsics_00.xml','intrinsics_00000000.xml'),('K1','intrinsics_01.xml','intrinsics_00000001.xml'),('R','ext_R.xml','ext_R.xml'),('T','ext_T.xml','ext_T.xml')]}
        rows[label]=checks
    dump('calibration_bundle_provenance.json',rows)

if __name__=='__main__':
    for label,(root,frame) in RUNS.items():inspect(label,root,frame)
    provenance()
