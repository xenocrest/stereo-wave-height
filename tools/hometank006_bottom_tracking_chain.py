"""Short-step bottom texture tracking; no temporal interpolation of heights.

Compose measured DIS pixel correspondences toward the frozen static reference.
Every link has bidirectional checks; lost tracks stay unsupported. This does not
make the unapproved static background geometry physically validated.
"""
from pathlib import Path
import json
import cv2
import numpy as np
from hometank006_refractive_height_probe import DisCorrespondence, sample, directions
from hometank006_refraction_probe import bottom_intersections

ROOT=Path('D:/stereo-wave-height-runs/HomeTank_006')


def main():
    out=ROOT/'refractive_height_probe_dis_chain';out.mkdir(exist_ok=True)
    ref=np.load(ROOT/'surface_chain_raft_centered/frame_01_correspondences.npz')
    cal=json.loads((ROOT/'rig_features_metric/result.json').read_text())
    p=json.loads((ROOT/'refraction_probe/result.json').read_text())['frames'][0]['fit']
    n=np.array(p['normal']);c=p['offset_m'];d=p['water_depth_m']
    y,x=np.indices(ref['left_roi'].shape,dtype=np.float32)
    grid=np.stack([x,y],axis=2)
    offset=-.225 # Existing audio candidate; never promoted to verified sync.
    target_times=[2.,3.,4.,5.,6.]+list(np.round(np.arange(6.1,10.01,.1),1))
    model=DisCorrespondence();records=[];final_maps=[]
    for i,side in enumerate(['left','right']):
        K=ref[f'P{i}'][:,:3];C=-np.linalg.inv(K)@ref[f'P{i}'][:,3]
        rot=ref['R0'] if i==0 else ref['R0']@np.array(cal['R']).T
        maps=cv2.initUndistortRectifyMap(ref[f'K{i}'],ref[f'D{i}'],rot,ref[f'P{i}'],(960,540),cv2.CV_32FC1)
        video=Path('experiments/real_video/HomeTank_006/videos/wave')/f'HomeTank_006_wave_cam{i}_{side.upper()}.mp4'
        cap=cv2.VideoCapture(str(video));cap.set(cv2.CAP_PROP_ORIENTATION_AUTO,0)
        previous=ref[f'rectified_{side}'];mapping=grid.copy();mapping[~ref[f'{side}_roi']]=np.nan
        for time in target_times:
            cap.set(cv2.CAP_PROP_POS_MSEC,(time+i*offset)*1000)
            ok,frame=cap.read();pts=cap.get(cv2.CAP_PROP_POS_MSEC)/1000
            if not ok:raise RuntimeError(f'decode failed at {time}')
            if i==0:frame=cv2.rotate(frame,cv2.ROTATE_180)
            current=cv2.remap(cv2.resize(frame,(960,540),interpolation=cv2.INTER_AREA),*maps,cv2.INTER_LINEAR)
            backward=model._flow(current,previous).transpose(1,2,0)
            forward=model._flow(previous,current).transpose(1,2,0)
            uv=grid+backward
            check=sample(forward,uv).reshape(*x.shape,2)
            valid=np.linalg.norm(backward+check,axis=2)<1.5
            mapping=sample(mapping,uv).reshape(*x.shape,2)
            mapping[~valid]=np.nan
            records.append(dict(camera=side,time_s=float(time),actual_pts_s=pts,
                                surviving_tracks=int(np.all(np.isfinite(mapping),axis=2).sum())))
            if time in [6.,8.,10.]:
                print(records[-1],flush=True)
            previous=current
        cap.release()
        P=bottom_intersections(directions(mapping.reshape(-1,2),K),C,n,c,d).reshape(*x.shape,3).astype(np.float32)
        final_maps.append(P)
    np.savez_compressed(out/'frame_10_reference01_background.npz',left=final_maps[0],right=final_maps[1])
    (out/'tracking.json').write_text(json.dumps(dict(status='CANDIDATE_TRACKS_NOT_VALIDATED_HEIGHT',
        offset_s=offset,offset_verified=False,step_s=.1,records=records,
        meaning='composed bottom pixel identity, not height interpolation'),indent=2),encoding='utf-8')


if __name__=='__main__':main()
