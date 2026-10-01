"""Document logger collision honestly and render the retained mask A/B cloud.

Only reads retained outputs. Does not repeat the mask experiment.
"""
import json,sys
from pathlib import Path
import numpy as np,cv2
from plyfile import PlyData
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
REPO=Path(__file__).resolve().parents[2];sys.path[:0]=[str(REPO),str(REPO/'src')]
from audit.scripts.inspect_artifacts import ROOT,EVIDENCE,project,dump,digest
from audit.scripts.official_experiments import WASS,BIN

def main():
    legacy=EVIDENCE/'official_experiment_commands.json'
    if legacy.exists():
        records=json.loads(legacy.read_text('utf-8'))
        if all('grid_only_' in ' '.join(x['argv']) or 'generategridconfig' in ' '.join(x['argv']) for x in records):
            legacy.rename(EVIDENCE/'legacy_isolated_grid_commands.json')
        else:
            raise RuntimeError('Unexpected original manifest; preserve rather than rename')
    recovered=[]
    index=0
    for case in ['repeat1','repeat2','repeat3','mask_A','mask_B']:
        base=ROOT/'experiments'/case;ws=base/'workspaces/000000_wd'
        invocations=[('stereo',[WASS/'wass_stereo.exe',base/'stereo_config.txt',ws])]
        if case!='mask_B':
            invocations.extend([
                ('grid',[BIN/'wassgridsurface.exe','--action','grid',base/'workspaces',base/'surface','--gridsetup',base/'surface/config.mat','--num_frames','1','--parallel','1','--stereo_image_idx','0']),
                ('ncplot',[BIN/'wassncplot.exe',base/'surface/gridded.nc',base/'pixel','-f','0','-l','1','--savexyz','--save-img','--no-textoverlay','--pxscale','1'])])
        for stage,argv in invocations:
            log=ROOT/f'experiment_command_{index:02d}.log'
            retained=index>=4 and log.exists()
            recovered.append({'case':case,'stage':stage,'argv':[str(x) for x in argv],
                'origin':'reconstructed from executed official_experiments.py and retained case artifacts; not original command-recorder output',
                'elapsed_s':None,'original_console_log':str(log) if retained else None,
                'console_log_status':'retained' if retained else 'overwritten by early isolated-grid recorder',
                'workspace_scientific_outputs_retained':str(ws),
                'stereo_config_sha256':digest(base/'stereo_config.txt')})
            index+=1
    dump('recovered_experiment_invocations.json',recovered)
    fig,axs=plt.subplots(1,2,figsize=(14,5),layout='constrained')
    summary={}
    for ax,case in zip(axs,['mask_A','mask_B']):
        ws=ROOT/'experiments'/case/'workspaces/000000_wd'
        im=cv2.cvtColor(cv2.imread(str(ws/'undistorted/00000000.png')),cv2.COLOR_BGR2RGB)
        v=PlyData.read(ws/'mesh_full.ply')['vertex'].data
        points=np.column_stack([v[x] for x in ['x','y','z']]);uv=project(np.loadtxt(ws/'P0cam.txt'),points)
        ix=np.arange(0,len(uv),max(1,len(uv)//20000))
        ax.imshow(im);ax.scatter(uv[ix,0],uv[ix,1],s=1,c='red');ax.set_xlim(0,1920);ax.set_ylim(1080,0)
        ax.set_title(f'{case}: preplane {len(points):,} points'+('\nOFFICIAL PLANE FAILURE; filtered/grid/overlay=N/A' if case=='mask_B' else '\nfiltered/grid/overlay retained'))
        summary[case]={'preplane_count':len(points),'mesh_full_path':str(ws/'mesh_full.ply'),'filtered_present':(ws/'mesh_cam.xyzC').exists()}
    fig.suptitle('One controlled official mask A/B: same prepared input, RANDOM_SEED=20261001')
    fig.savefig(EVIDENCE/'official_mask_AB_preplane_comparison.png',dpi=130);plt.close(fig)
    dump('mask_AB_retained_outputs.json',summary)
    print(json.dumps(summary))

if __name__=='__main__':main()
