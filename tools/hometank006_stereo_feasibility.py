"""Shared-target stereo feasibility, never a calibration approval."""
from pathlib import Path
import json
import cv2
import numpy as np
from hometank006_target_release_diagnostic import orient_grid


def main():
    root=Path('D:/stereo-wave-height-runs/HomeTank_006')
    out=root/'shared_target_stereo';out.mkdir(exist_ok=True)
    mono=json.loads((root/'target_release_measured_span/result.json').read_text())['results']
    records={s:{r['time_s']:r for r in json.loads((root/'partial_calibration_larger'/f'{s}_result.json').read_text())['records'] if r['found'] and sorted(r['pattern_size'])==[6,9]} for s in ['LEFT','RIGHT']}
    times=sorted(set(records['LEFT'])&set(records['RIGHT']))
    points=[np.asarray(mono['LEFT']['released_object_points_m'],np.float32) for _ in times]
    images={s:[orient_grid(records[s][t]) for t in times] for s in records}
    k0=np.array(mono['LEFT']['released_K']);d0=np.array(mono['LEFT']['released_D'])
    k1=np.array(mono['RIGHT']['released_K']);d1=np.array(mono['RIGHT']['released_D'])
    poses=[]
    for i,t in enumerate(times):
        p=[]
        for s,k,d in [('LEFT',k0,d0),('RIGHT',k1,d1)]:
            ok,rv,tv=cv2.solvePnP(points[i],images[s][i],k,d)
            if not ok:raise RuntimeError('pose estimation failed')
            p.append((cv2.Rodrigues(rv)[0],tv))
        r=p[1][0]@p[0][0].T;tr=p[1][1]-r@p[0][1]
        poses.append(dict(time_s=t,R=r.tolist(),T_m=tr.ravel().tolist(),baseline_m=float(np.linalg.norm(tr))))
    result=cv2.stereoCalibrate(points,images['LEFT'],images['RIGHT'],k0.copy(),d0.copy(),k1.copy(),d1.copy(),(3840,2160),flags=cv2.CALIB_FIX_INTRINSIC)
    rms,_,_,_,_,r,t,_,_=result
    r0,r1,p0,p1,q,roi0,roi1=cv2.stereoRectify(k0,d0,k1,d1,(3840,2160),r,t,flags=cv2.CALIB_ZERO_DISPARITY,alpha=0)
    errors=[]
    for l,rr in zip(images['LEFT'],images['RIGHT']):
        a=cv2.undistortPoints(l,k0,d0,R=r0,P=p0).reshape(-1,2);b=cv2.undistortPoints(rr,k1,d1,R=r1,P=p1).reshape(-1,2);errors.extend((a[:,1]-b[:,1]).tolist())
    payload=dict(status='DIAGNOSTIC_ONLY_UNVERIFIED_TIME_PAIRS',approved_for_reconstruction=False,paired_times_s=times,per_pair_pose=poses,stereo_rms_px=float(rms),vertical_rms_px=float(np.sqrt(np.mean(np.square(errors)))),K0=k0.tolist(),D0=d0.tolist(),K1=k1.tolist(),D1=d1.tolist(),R=r.tolist(),T_m=t.ravel().tolist(),baseline_m=float(np.linalg.norm(t)),rectified_roi_left=list(roi0),rectified_roi_right=list(roi1),warning='Same nominal times are feasibility pairs, not verified synchronization; no production approval.')
    (out/'result.json').write_text(json.dumps(payload),encoding='utf-8');print(json.dumps(payload))

if __name__=='__main__':main()
