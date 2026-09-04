"""Track individual bottom features without repeated NaN map resampling.

Official pyramidal LK, forward/backward check at decoded consecutive PTS.
Tracks are pixel correspondences only, not height observations. No WASS/GUI.
"""
from pathlib import Path
import argparse
import json
import cv2
import numpy as np

ROOT=Path('D:/stereo-wave-height-runs/HomeTank_006')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--restart-time',type=int,choices=[1,6],default=1)
    args=parser.parse_args()
    out=ROOT/('lk_bottom_tracks' if args.restart_time==1 else 'lk_bottom_tracks_restart06');out.mkdir(exist_ok=True)
    ref=np.load(ROOT/'surface_chain_raft_centered/frame_01_correspondences.npz')
    cal=json.loads((ROOT/'rig_features_metric/result.json').read_text())
    report=[]
    for i,side in enumerate(['left','right']):
        rot=ref['R0'] if i==0 else ref['R0']@np.array(cal['R']).T
        maps=cv2.initUndistortRectifyMap(ref[f'K{i}'],ref[f'D{i}'],rot,ref[f'P{i}'],(960,540),cv2.CV_32FC1)
        video=Path('experiments/real_video/HomeTank_006/videos/wave')/f'HomeTank_006_wave_cam{i}_{side.upper()}.mp4'
        cap=cv2.VideoCapture(str(video));cap.set(cv2.CAP_PROP_ORIENTATION_AUTO,0)
        initial_pts=1.0006666666666668 if i==0 else .9333333333333333
        if args.restart_time==6:initial_pts=6.0039 if i==0 else 5.766666666666667
        cap.set(cv2.CAP_PROP_POS_MSEC,initial_pts*1000)
        ok,frame=cap.read()
        if not ok:raise RuntimeError('initial decode failed')
        def rectify(f):
            if i==0:f=cv2.rotate(f,cv2.ROTATE_180)
            small=cv2.resize(f,(960,540),interpolation=cv2.INTER_AREA)
            return cv2.cvtColor(cv2.remap(small,*maps,cv2.INTER_LINEAR),cv2.COLOR_BGR2GRAY)
        previous=rectify(frame)
        actual_initial=cap.get(cv2.CAP_PROP_POS_MSEC)/1000
        seed_mask=ref[f'{side}_roi'].copy()
        bg=None
        if args.restart_time==6:
            bg=np.load(ROOT/'refractive_height_probe_dis_t6_offset-0.225/frame_06_reference01_background.npz')[side]
            seed_mask &= np.all(np.isfinite(bg),axis=2)
        p0=cv2.goodFeaturesToTrack(previous,maxCorners=5000,qualityLevel=.005,minDistance=2,
                                   mask=seed_mask.astype(np.uint8)*255,blockSize=5)
        if p0 is None:raise RuntimeError('no bottom features')
        origin=p0.reshape(-1,2).copy();current=p0.copy();ids=np.arange(len(origin));initial=len(ids)
        records=[];next_target=2
        targets=list(range(args.restart_time+1,11));ti=0
        while ti<len(targets):
            ok,frame=cap.read()
            if not ok:break
            pts=cap.get(cv2.CAP_PROP_POS_MSEC)/1000
            image=rectify(frame)
            if len(current):
                forward,status,error=cv2.calcOpticalFlowPyrLK(previous,image,current,None,winSize=(21,21),maxLevel=3,
                      criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,30,.01))
                backward,status2,_=cv2.calcOpticalFlowPyrLK(image,previous,forward,None,winSize=(21,21),maxLevel=3,
                      criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,30,.01))
                p=forward.reshape(-1,2)
                valid=(status.ravel()>0)&(status2.ravel()>0)&(np.linalg.norm(backward-current,axis=2).ravel()<1.5)
                valid &= np.isfinite(p).all(1)&(p[:,0]>=0)&(p[:,0]<960)&(p[:,1]>=0)&(p[:,1]<540)
                current=forward[valid];ids=ids[valid]
            previous=image
            # Audio-derived candidate only; timestamps are kept, never rewritten.
            if pts >= targets[ti]+(0 if i==0 else -.225):
                t=targets[ti]
                extra={}
                if bg is not None:
                    from hometank006_refractive_height_probe import sample
                    extra['background_m']=sample(bg,origin[ids])
                np.savez_compressed(out/f'{side}_{t:02d}.npz',origin_uv=origin[ids],current_uv=current.reshape(-1,2),
                     ids=ids,origin_pts_s=actual_initial,current_pts_s=pts,image_gray=image,**extra)
                r=dict(camera=side,target_time_s=t,actual_pts_s=pts,initial_count=initial,surviving_count=len(ids))
                records.append(r);print(json.dumps(r),flush=True);ti+=1
        cap.release();report.extend(records)
    (out/'result.json').write_text(json.dumps(dict(status='BOTTOM_FEATURE_TRACKS_NOT_HEIGHT',
        algorithm='OpenCV pyramidal LK, individual identity, no NaN image composition',
        fb_gate_px=1.5,frame_selection='consecutive decoded frames with actual PTS',
        right_offset_candidate_s=-.225,synchronization_verified=False,track_restart_s=args.restart_time,
        height_reference_s=1,records=report),indent=2),encoding='utf-8')


if __name__=='__main__':main()
