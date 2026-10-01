"""Make evidence inventories and comparison plots. Does not run reconstruction."""
import sys,json,subprocess,shutil
from pathlib import Path
import cv2,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.io import loadmat
from plyfile import PlyData
REPO=Path(__file__).resolve().parents[2];sys.path[:0]=[str(REPO),str(REPO/'src')]
from audit.scripts.inspect_artifacts import ROOT,RUNS,EVIDENCE,dump,digest,project,stats
from wassgridsurface.wass_utils import align_on_sea_plane_RT

def main():
    baseline=json.loads(Path('D:/stereo-wave-height-runs/pipeline/hometank004/run_20260928_113734/run_report.json').read_text('utf-8'))['toolchain']
    guard=[]
    for group in ['wass_source_source_hashes','wass_lowcost_source_hashes']:
        for path,expected in baseline[group].items():guard.append({'path':path,'baseline_hash':expected,'current_hash':digest(path),'unchanged':expected==digest(path)})
    for key in ['python','ffmpeg','praat']:
        guard.append({'path':baseline[key],'baseline_hash':baseline[key+'_sha256'],'current_hash':digest(baseline[key]),'unchanged':baseline[key+'_sha256']==digest(baseline[key])})
    stereo=Path(baseline['wass_bin'])/'wass_stereo.exe';guard.append({'path':str(stereo),'baseline_hash':baseline['wass_stereo_sha256'],'current_hash':digest(stereo),'unchanged':baseline['wass_stereo_sha256']==digest(stereo)})
    dump('third_party_unchanged_guard.json',guard)
    for label in ['HomeTank21','Vieira0']:
        root,frame=RUNS[label];ws=root/'wass/workspaces'/f'{frame:06d}_wd';s=loadmat(root/'surface/config.mat')
        if not (ws/'mesh_full.ply').exists():
            # Public configuration does not save pre-plane mesh. Add only the
            # official diagnostic output switch in a separate copied workspace.
            target=ROOT/'Vieira_full_mesh_review/000000_wd'
            if not target.exists():
                target.mkdir(parents=True)
                shutil.copytree(ws/'undistorted',target/'undistorted')
                for name in ['intrinsics_00000000.xml','intrinsics_00000001.xml','ext_R.xml','ext_T.xml']:shutil.copy2(ws/name,target/name)
                config=target.parent/'stereo_config.txt'
                config.write_text((root/'wass/config/stereo_config.txt').read_text('utf-8')+'\nSAVE_FULL_MESH=true\n',encoding='utf-8')
                import audit.scripts.official_experiments as recorder
                recorder.RECORD_NAME='vieira_diagnostic_commands.json';recorder.LOG_PREFIX='vieira_diagnostic'
                recorder.call([Path('D:/wass/dist/bin/wass_stereo.exe'),config,target])
            ws=target
            dump('Vieira_preplane_diagnostic.json',{'source_frame_path':str(root/'sync/frames/cam0/000000.tif'),'workspace':str(ws),'config_change':'SAVE_FULL_MESH=true only; fresh official stereo on same prepared inputs; random plane fit may differ from historical filtered mesh'})
        fig,axs=plt.subplots(1,2,figsize=(12,5),layout='constrained')
        im=cv2.cvtColor(cv2.imread(str(ws/'undistorted/00000000.png')),cv2.COLOR_BGR2RGB)
        for ax,name in zip(axs,['mesh_full.ply','mesh.ply']):
            vertex=PlyData.read(ws/name)['vertex'].data;p=np.vstack([vertex[n] for n in ['x','y','z']]);aligned=align_on_sea_plane_RT(p,s['Rpl'],s['Tpl'])*s['CAM_BASELINE'].item();uv=project(np.loadtxt(ws/'P0cam.txt'),p.T)
            idx=np.arange(0,len(uv),max(1,len(uv)//20000));ax.imshow(im);ax.scatter(uv[idx,0],uv[idx,1],c=aligned[2,idx],s=.2,cmap='turbo');ax.set_xlim(0,1920);ax.set_ylim(1080,0);ax.set_title(f'{name}: {len(uv):,} points')
        fig.suptitle(f'{label}: after z-gap / before plane vs after plane (same frozen transform)')
        fig.savefig(EVIDENCE/f'{label}_preplane_vs_filtered.png',dpi=150);plt.close(fig)
    fig,axs=plt.subplots(1,3,figsize=(15,5),layout='constrained')
    for ax,label in zip(axs,['HomeTank21','HomeTank22','HomeTank23']):
        root,frame=RUNS[label]
        ref=__import__('app.core',fromlist=['core']).load_reference(Path('D:/stereo-wave-height-runs/fixed-coordinate-acceptance-20261001-final/reference_plane.json'))[0]
        from app import core
        r=core.load_result(root,frame,ref);h=r['height']*1000
        im=ax.imshow(h,cmap='coolwarm',vmin=-40,vmax=40);ax.set_title(f'{label}: fixed H scale [-40,+40] mm')
    fig.colorbar(im,ax=axs,label='H (mm)');fig.savefig(EVIDENCE/'HomeTank_fixed_color_scale_comparison.png',dpi=120);plt.close(fig)
    # Preserve the full diagnostic file inventory outside Git, including failures.
    external=[{'path':str(p),'bytes':p.stat().st_size,'sha256':digest(p)} for p in ROOT.rglob('*') if p.is_file()]
    dump('external_evidence_manifest.json',external)
    site=Path('D:/stereo-wave-height-runs/wassgridsurface-0.11.4-venv/Lib/site-packages')
    dump('installed_scientific_package_source_hashes.json',[{'path':str(p),'sha256':digest(p)} for d in ['wassgridsurface','wassncplot'] for p in (site/d).rglob('*.py')])
    print(json.dumps({'third_party_guard_count':len(guard),'changed':sum(not x['unchanged'] for x in guard),'external_files':len(external),'external_bytes':sum(x['bytes'] for x in external)}))

if __name__=='__main__':main()
