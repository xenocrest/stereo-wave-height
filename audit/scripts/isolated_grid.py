"""Isolate official DCT variability with identical decoded cloud/setup."""
import sys,shutil,json
from pathlib import Path
import numpy as np
from netCDF4 import Dataset
REPO=Path(__file__).resolve().parents[2];sys.path[:0]=[str(REPO),str(REPO/'src')]
from audit.scripts.inspect_artifacts import ROOT,RUNS,dump,stats,digest
from audit.scripts.official_experiments import call,BIN
import audit.scripts.official_experiments as recorder
recorder.RECORD_NAME='isolated_grid_commands.json'
recorder.LOG_PREFIX='isolated_grid'

def setup_review():
    # The installed 0.11.4 CLI calls this action generateconfig, although its
    # README calls it generategridconfig. Retain the failed documented call.
    source=Path('D:/stereo-wave-height-runs/pipeline/hometank004_multiframe_acceptance/run_20260928/science')
    out=ROOT/'official_setup_review';out.mkdir(exist_ok=True)
    call([BIN/'wassgridsurface.exe','--action','generateconfig',source/'wass/workspaces',out])
    shutil.copy2(out/'gridconfig.txt',REPO/'audit/evidence/official_generated_gridconfig.txt')
    shutil.copy2(source/'surface/gridconfig.txt',out/'gridconfig.txt')
    call([BIN/'wassgridsurface.exe','--action','setup',source/'wass/workspaces',out,'--gridconfig',out/'gridconfig.txt','--baseline','0.07','--fps','1','--stereo_image_idx','0'])
    shutil.copy2(out/'area_grid.png',REPO/'audit/evidence/HomeTank_setup_area_grid.png')

def main():
    origin,frame=RUNS['HomeTank21'];original=origin/'wass/workspaces'/f'{frame:06d}_wd'
    records=[]
    for i in range(1,4):
        base=ROOT/f'grid_only_{i}'
        if base.exists():raise FileExistsError(base)
        ws=base/'workspaces/000000_wd';ws.mkdir(parents=True)
        for f in ['mesh_cam.xyzC','P0cam.txt','P1cam.txt','plane.txt']:
            shutil.copy2(original/f,ws/f)
        shutil.copytree(original/'undistorted',ws/'undistorted')
        surface=base/'surface';surface.mkdir();shutil.copy2(origin/'surface/config.mat',surface/'config.mat')
        call([BIN/'wassgridsurface.exe','--action','grid',base/'workspaces',surface,'--gridsetup',surface/'config.mat','--num_frames','1','--parallel','1','--stereo_image_idx','0'])
        nc=Dataset(surface/'gridded.nc');z=np.asarray(nc['Z'][0].filled(np.nan))/1000;nc.close()
        row={'run':i,'path':str(base),'cloud_hash':digest(ws/'mesh_cam.xyzC'),'setup_hash':digest(surface/'config.mat'),'grid_z':stats(z),'fixed_grid_z_m':{f'{x},{y}':float(z[y,x]) for x,y in [(32,32),(64,128),(128,128),(192,128),(224,224)]}}
        records.append(row);dump('isolated_grid_repeats.json',records);print(json.dumps(row),flush=True)
    setup_review()

if __name__=='__main__':
    if '--setup-only' in sys.argv:setup_review()
    else:main()
