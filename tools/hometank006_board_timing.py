"""Geometric timing diagnostic from observed forward/backward tracked corners."""
from pathlib import Path
import json
import cv2
import numpy as np
from hometank006_target_release_diagnostic import orient_grid

def main():
    cv2.setRNGSeed(42)
    root=Path('D:/stereo-wave-height-runs/HomeTank_006');out=root/'board_timing';out.mkdir(exist_ok=True)
    mono=json.loads((root/'target_release_measured_span/result.json').read_text())['results']
    raw={s:{r['time_s']:r for r in json.loads((root/'partial_calibration_larger'/f'{s}_result.json').read_text())['records'] if r['found'] and sorted(r['pattern_size'])==[6,9]} for s in ['LEFT','RIGHT']}
    common=sorted(set(raw['LEFT'])&set(raw['RIGHT']))
    k0=np.array(mono['LEFT']['released_K']);d0=np.array(mono['LEFT']['released_D']);k1=np.array(mono['RIGHT']['released_K']);d1=np.array(mono['RIGHT']['released_D']);obj=np.asarray(mono['LEFT']['released_object_points_m'],np.float32)
    cap=cv2.VideoCapture('experiments/real_video/HomeTank_006/videos/calibration/HomeTank_006_calibration_cam1_RIGHT.mp4');cap.set(cv2.CAP_PROP_ORIENTATION_AUTO,0)
    tracks={}
    for time in common:
        cap.set(cv2.CAP_PROP_POS_MSEC,time*1000);ok,anchor=cap.read()
        if not ok:raise RuntimeError('anchor decode failed')
        small=cv2.cvtColor(cv2.resize(anchor,(960,540)),cv2.COLOR_BGR2GRAY);p=orient_grid(raw['RIGHT'][time])*.25
        rows=[]
        for delta in range(-21,7):
            idx=round(time*30)+delta;cap.set(cv2.CAP_PROP_POS_FRAMES,idx);ok,frame=cap.read()
            if not ok:continue
            pts=cap.get(cv2.CAP_PROP_POS_MSEC)/1000
            gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY);target=cv2.resize(gray,(960,540))
            q,st,_=cv2.calcOpticalFlowPyrLK(small,target,p,None,winSize=(21,21),maxLevel=3)
            back,sb,_=cv2.calcOpticalFlowPyrLK(target,small,q,None,winSize=(21,21),maxLevel=3)
            valid=(st.ravel()>0)&(sb.ravel()>0)&(np.linalg.norm(back-p,axis=2).ravel()<.25)
            full=q*4;before=full.copy();cv2.cornerSubPix(gray,full,(5,5),(-1,-1),(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_MAX_ITER,30,1e-4))
            valid &= np.linalg.norm(full-before,axis=2).ravel()<4
            rows.append(dict(pts_s=pts,corners=full.reshape(-1,2).tolist(),valid=valid.tolist()))
        tracks[time]=rows
    cap.release();scores=[]
    for b in np.arange(-.65,.151,1/30):
        objects=[];left=[];right=[];pairs=[]
        for time in common:
            l=raw['LEFT'][time];r=min(tracks[time],key=lambda x:abs(x['pts_s']-l['pts_s']-b));valid=np.array(r['valid'])
            if valid.sum()<20:continue
            objects.append(obj[valid]);left.append(orient_grid(l)[valid]);right.append(np.asarray(r['corners'],np.float32).reshape(-1,1,2)[valid]);pairs.append(dict(left_s=l['pts_s'],right_s=r['pts_s'],count=int(valid.sum())))
        if len(objects)!=3:continue
        ans=cv2.stereoCalibrate(objects,left,right,k0.copy(),d0.copy(),k1.copy(),d1.copy(),(3840,2160),flags=cv2.CALIB_FIX_INTRINSIC)
        rms,_,_,_,_,R,T,_,F=ans
        held=[]
        for i in range(3):
            j=[n for n in range(3) if n!=i]
            fit=cv2.stereoCalibrate([objects[n] for n in j],[left[n] for n in j],[right[n] for n in j],k0.copy(),d0.copy(),k1.copy(),d1.copy(),(3840,2160),flags=cv2.CALIB_FIX_INTRINSIC)
            lu=cv2.undistortPoints(left[i],k0,d0,P=k0);ru=cv2.undistortPoints(right[i],k1,d1,P=k1).reshape(-1,2);lines=cv2.computeCorrespondEpilines(lu,1,fit[-1]).reshape(-1,3)
            e=np.abs(np.sum(lines[:,:2]*ru,axis=1)+lines[:,2])/np.linalg.norm(lines[:,:2],axis=1);held.append(float(np.sqrt(np.mean(e**2))))
        scores.append(dict(offset_s=float(b),rms_px=float(rms),heldout_epipolar_rms_px=held,R=R.tolist(),T_m=T.ravel().tolist(),baseline_m=float(np.linalg.norm(T)),pairs=pairs))
    best=min(scores,key=lambda r:np.mean(np.square(r['heldout_epipolar_rms_px'])))
    report=dict(status='GEOMETRIC_TIMING_DIAGNOSTIC_NOT_APPROVED',scores=scores,best_diagnostic=best,warning='Only three pose groups; score minimum alone is not frame-level synchronization proof.')
    (out/'result.json').write_text(json.dumps(report),encoding='utf-8');print(json.dumps(best))

if __name__=='__main__':main()
