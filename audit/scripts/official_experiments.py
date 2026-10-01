"""Unmodified official executables on copied inputs, repeats and one mask A/B.

Scientific code and production configuration are never overwritten.
"""
import json,shutil,subprocess,time,sys
from pathlib import Path
import cv2,numpy as np
from scipy.io import loadmat
from netCDF4 import Dataset
from plyfile import PlyData
REPO=Path(__file__).resolve().parents[2];sys.path[:0]=[str(REPO),str(REPO/'src')]
from audit.scripts.inspect_artifacts import ROOT,RUNS,dump,digest,stats,project
from wassgridsurface.wass_utils import load_camera_mesh,align_on_sea_plane_RT
WASS=Path('D:/wass/dist/bin'); BIN=Path('D:/stereo-wave-height-runs/wassgridsurface-0.11.4-venv/Scripts')
commands=[]
RECORD_NAME='official_experiment_commands.json'
LOG_PREFIX='official_experiment'

def call(argv,cwd=None):
    start=time.time();p=subprocess.run([str(x) for x in argv],cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace')
    log=ROOT/f'{LOG_PREFIX}_{len(commands):02d}_{time.time_ns()}.log';log.write_text(p.stdout+'\n'+p.stderr,encoding='utf-8')
    commands.append({'argv':[str(x) for x in argv],'cwd':str(cwd),'returncode':p.returncode,'elapsed_s':time.time()-start,'log':str(log)})
    dump(RECORD_NAME,commands)
    if p.returncode:raise RuntimeError(f'{argv[0]} failed: {p.stderr[-500:]}')

def fresh_workspace(case,source):
    base=ROOT/'experiments'/case
    if base.exists():raise FileExistsError(base)
    ws=base/'workspaces/000000_wd';ws.mkdir(parents=True)
    shutil.copytree(source/'undistorted',ws/'undistorted')
    for name in ('intrinsics_00000000.xml','intrinsics_00000001.xml','ext_R.xml','ext_T.xml'):
        shutil.copy2(source/name,ws/name)
    return base,ws

def summarize(base,ws):
    nc=Dataset(base/'surface/gridded.nc');grid=np.asarray(nc['Z'][0].filled(np.nan))/1000
    setup=loadmat(base/'surface/config.mat');mesh=load_camera_mesh(ws/'mesh_cam.xyzC')
    a=align_on_sea_plane_RT(mesh,setup['Rpl'],setup['Tpl'])*setup['CAM_BASELINE'].item()
    rows={'case':base.name,'path':str(base),'filtered_count':mesh.shape[1],
          'preplane_count':len(PlyData.read(ws/'mesh_full.ply')['vertex'].data) if (ws/'mesh_full.ply').exists() else None,
          'plane':np.loadtxt(ws/'plane.txt').tolist(),'grid_z':stats(grid),
          'fixed_grid_positions':{f'{i},{j}':float(grid[j,i]) for i,j in [(32,32),(64,128),(128,128),(192,128),(224,224)]},
          'grid_config_hash':digest(base/'surface/config.mat'),'stereo_config_hash':digest(base/'stereo_config.txt')}
    ref=json.loads((RUNS['HomeTank21'][0]/'reference_plane.json').read_text('utf-8'))
    maps=sorted((base/'pixel').glob('*.mat'))
    if maps:
        xyz=loadmat(maps[0])['px_2_3D'];valid=np.isfinite(xyz).all(2)&~np.all(np.isclose(xyz,0),2)&~np.all(np.isclose(xyz,1),2)
        heights=xyz@np.asarray(ref['normal'])+ref['d']
        rows['mapped_count']=int(valid.sum()); rows['fixed_pixel_h']={f'{u},{v}':float(heights[v,u]) if valid[v,u] else None for u,v in [(1200,700),(1200,900),(1500,850),(1700,950)]}
    np.savez_compressed(base/'diagnostics.npz',aligned=a,grid=grid)
    nc.close();return rows

def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    origin,frame=RUNS['HomeTank21'];source=origin/'wass/workspaces'/f'{frame:06d}_wd'
    config=(origin/'wass/config/stereo_config.txt').read_text('utf-8')
    setup=origin/'surface/config.mat';records=[]
    for case in ['repeat1','repeat2','repeat3','mask_A','mask_B']:
        base,ws=fresh_workspace(case,source)
        text=config
        if case.startswith('mask_'):text+='\nRANDOM_SEED=20261001\n'
        if case=='mask_B':
            # Camera auto-swap is verified from the original log: internal left=cam1.
            # Conservative hand-drawn image-footprint masks; bottom texture/refraction
            # still cannot be distinguished from surface observations by a mask.
            polygons={0:[[420,835],[1390,835],[1660,1035],[440,1035]],1:[[120,700],[1090,700],[1360,1030],[160,1030]]}
            for cam,poly in polygons.items():
                image=cv2.imread(str(ws/'undistorted'/f'{cam:08d}.png'),0)
                mask=np.zeros_like(image);cv2.fillPoly(mask,[np.array(poly,np.int32)],255)
                cv2.imwrite(str(ws/f'water_cam{cam}.png'),mask)
                preview=cv2.cvtColor(image,cv2.COLOR_GRAY2BGR);cv2.polylines(preview,[np.array(poly,np.int32)],True,(0,255,0),3)
                cv2.imwrite(str(REPO/'audit/evidence'/f'water_mask_cam{cam}_preview.png'),preview)
            text+='\nLEFT_MASK_IMAGE=water_cam1.png\nRIGHT_MASK_IMAGE=water_cam0.png\n'
            dump('mask_definition.json',{'polygons_in_actual_undistorted_cam_coordinates':polygons,'internal_left':'cam1','internal_right':'cam0','scope':'conservative visible water footprint candidate; not segmentation or independent proof of surface correspondences','A_B_common_official_random_seed':20261001})
        (base/'stereo_config.txt').write_text(text,encoding='utf-8')
        try:
            call([WASS/'wass_stereo.exe',base/'stereo_config.txt',ws])
            (base/'surface').mkdir();shutil.copy2(setup,base/'surface/config.mat')
            call([BIN/'wassgridsurface.exe','--action','grid',base/'workspaces',base/'surface','--gridsetup',base/'surface/config.mat','--num_frames','1','--parallel','1','--stereo_image_idx','0'])
            (base/'pixel').mkdir()
            call([BIN/'wassncplot.exe',base/'surface/gridded.nc',base/'pixel','-f','0','-l','1','--savexyz','--save-img','--no-textoverlay','--pxscale','1'])
            row=summarize(base,ws);row['status']='EXECUTED'
        except Exception as e:
            row={'case':case,'status':'OFFICIAL_FAILURE','error':str(e),'path':str(base)}
        records.append(row);dump('repeat_and_mask_experiments.json',records);print(json.dumps(row),flush=True)
    defaults=ROOT/'official_defaults';defaults.mkdir()
    call([WASS/'wass_stereo.exe','--genconfig'],defaults)
    shutil.copy2(defaults/'stereo_config.txt',REPO/'audit/evidence/WASS_OFFICIAL_DEFAULT.txt')

if __name__=='__main__':main()
