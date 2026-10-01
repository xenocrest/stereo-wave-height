"""Diagnostic plots and exact GUI renderer calls, without changing scientific data."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import sys,json
from pathlib import Path
import numpy as np,cv2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from types import SimpleNamespace
REPO=Path(__file__).resolve().parents[2];sys.path[:0]=[str(REPO),str(REPO/'src')]
from audit.scripts.inspect_artifacts import RUNS,ROOT,EVIDENCE,HROOT,project,dump
from app import core
from app.main import MainWindow,PointCloudView
from PySide6.QtWidgets import QApplication

def rgb(p):return cv2.cvtColor(cv2.imread(str(p)),cv2.COLOR_BGR2RGB)

def equal(ax,p):
    low=p.min(axis=1);high=p.max(axis=1);ranges=high-low
    for setter,a,b in zip((ax.set_xlim,ax.set_ylim,ax.set_zlim),low,high):setter(a,b)
    ax.set_box_aspect(ranges) # one physical unit has same displayed length on X/Y/Z.

def main():
    app=QApplication.instance() or QApplication([])
    for label,(root,frame) in RUNS.items():
        data=json.loads((EVIDENCE/f'{label}.json').read_text('utf-8'))
        a=np.load(ROOT/f'{label}_analysis.npz')
        ws=root/'wass/workspaces'/f'{frame:06d}_wd'
        ref=core.load_reference(HROOT/'reference_plane.json')[0] if label.startswith('HomeTank') else core.reference_from_run(root,0)
        result=core.load_result(root,frame,ref)
        raw=rgb(data['raw_path']);undist=rgb(ws/'undistorted/00000000.png')
        ui=SimpleNamespace(result=result,raw_rgb=raw,measurement_region=None)
        MainWindow._build_overlay(ui) # exact production overlay implementation.
        plt.imsave(EVIDENCE/f'{label}_GUI_overlay.png',ui.overlay_rgb)
        cloud=PointCloudView(); cloud.show_ply(root/'reconstruction/ply'/f'{frame:06d}.ply')
        cloud.figure.savefig(EVIDENCE/f'{label}_GUI_cloud.png',dpi=140)
        cloud.close()
        fig,axes=plt.subplots(2,3,figsize=(16,9),layout='constrained')
        axes[0,0].imshow(raw);axes[0,0].set_title('Extracted original cam0')
        axes[0,1].imshow(undist);axes[0,1].set_title('Official undistorted cam0')
        axes[0,2].imshow(rgb(ws/'disparity_stereo_ouput.png'));axes[0,2].set_title('Official disparity preview (not numeric d)')
        axes[1,0].imshow(undist)
        uv=a['rawuv'];aligned=a['aligned'];ix=np.arange(0,len(uv),max(1,len(uv)//14000))
        lo,hi=np.percentile(aligned[2],(2,98))
        axes[1,0].scatter(uv[ix,0],uv[ix,1],c=aligned[2,ix],s=0.5,cmap='turbo',vmin=lo,vmax=hi)
        axes[1,0].set_xlim(0,undist.shape[1]);axes[1,0].set_ylim(undist.shape[0],0)
        axes[1,0].set_title('Filtered WASS cloud projected into undistorted cam0')
        axes[1,1].imshow(a['ZZ'],origin='lower',extent=data['grid_xy_extent'],cmap='turbo',vmin=lo,vmax=hi)
        axes[1,1].set_title('Official grid Z; all finite cells shown')
        axes[1,2].imshow(ui.overlay_rgb);axes[1,2].set_title('Exact GUI H overlay on original image')
        for ax in axes.flat:ax.tick_params(labelsize=7)
        syncaudit=json.loads((EVIDENCE/'sync_absolute_pts_and_frame_identity.json').read_text('utf-8'))
        correct=next((r['actual_left_pts_s'] for r in syncaudit['records'] if r['label']==label),None)
        time_label=(f'source PTS={correct:.6f}s; recorded={data["timestamp"]:.6f}s' if correct is not None else f'nominal sequence t={data["timestamp"]:.6f}s')
        fig.suptitle(f'{label} | {time_label} | units={result["units"]}',fontsize=13)
        fig.savefig(EVIDENCE/f'{label}_stages.png',dpi=115);plt.close(fig)
        for factor in [1,10]:
            fig=plt.figure(figsize=(12,5),layout='constrained')
            pts=aligned.copy();pts[2]*=factor
            for j,title in enumerate(['Filtered WASS points','Official regular grid']):
                ax=fig.add_subplot(1,2,j+1,projection='3d')
                if j==0:
                    ii=np.arange(0,pts.shape[1],max(1,pts.shape[1]//30000))
                    ax.scatter(*pts[:,ii],c=aligned[2,ii],s=.15,cmap='turbo',vmin=lo,vmax=hi)
                else:
                    ax.plot_surface(a['XX'],a['YY'],a['ZZ']*factor,cmap='turbo',rstride=3,cstride=3,linewidth=0)
                gridpts=np.vstack((a['XX'].ravel(),a['YY'].ravel(),a['ZZ'].ravel()*factor))
                equal(ax,np.c_[pts,gridpts]);ax.view_init(elev=25,azim=-65)
                ax.set(xlabel=f'X ({result["units"]})',ylabel=f'Y ({result["units"]})',zlabel=f'Z ({result["units"]})',title=title)
            mode='TRUE_SCALE_VIEW' if factor==1 else 'VERTICAL_EXAGGERATION_10X'
            fig.suptitle(f'{label} {mode}; official fixed grid coordinates',fontsize=12)
            fig.savefig(EVIDENCE/f'{label}_{mode}.png',dpi=140);plt.close(fig)
        fig,axs=plt.subplots(1,2,figsize=(12,5),layout='constrained')
        axs[0].imshow(raw);axs[1].imshow(undist)
        for i,row in enumerate(data['projection_samples'][:12]):
            ur,vr=row['project_raw_uv'];uu,vv=row['project_undist_uv'];ug,vg=row['gui_raw_uv']
            axs[0].plot([ug,ur],[vg,vr],'-r',lw=1);axs[0].plot(ur,vr,'+g');axs[0].text(ur,vr,str(i),color='yellow',fontsize=7)
            axs[1].plot(uu,vv,'+g');axs[1].text(uu,vv,str(i),color='yellow',fontsize=7)
        axs[0].set_title('Raw: green=distorted projection; red=GUI offset')
        axs[1].set_title('Undistorted: actual projection of same grid XYZ')
        fig.savefig(EVIDENCE/f'{label}_projection_check.png',dpi=150);plt.close(fig)
        print('rendered',label,flush=True)

if __name__=='__main__':main()
