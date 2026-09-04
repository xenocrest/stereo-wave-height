"""Recover candidate essential-pose scale from the measured checkerboard span."""
from pathlib import Path
import json
import cv2
import numpy as np
import yaml
from hometank006_guided_corners import decode
from hometank006_target_release_diagnostic import orient_grid


def main():
    root=Path('D:/stereo-wave-height-runs/HomeTank_006');out=root/'rig_features_metric';out.mkdir(exist_ok=True)
    data=json.loads((root/'rig_features_motion_candidate/result.json').read_text())
    span=yaml.safe_load(Path('experiments/real_video/HomeTank_006/manifest.yaml').read_text(encoding='utf-8'))['calibration']['measured_grid_span']
    raw={side:{r['time_s']:r for r in json.loads((root/'partial_calibration_larger'/f'{side}_result.json').read_text())['records'] if r['found'] and sorted(r['pattern_size'])==[6,9]} for side in ['LEFT','RIGHT']}
    K=[np.array(data[f'K{i}']) for i in [0,1]];D=[np.array(data[f'D{i}']) for i in [0,1]]
    R=np.array(data['R']);t=np.array(data['T_m']);t/=np.linalg.norm(t)
    cap=cv2.VideoCapture('experiments/real_video/HomeTank_006/videos/calibration/HomeTank_006_calibration_cam1_RIGHT.mp4');cap.set(cv2.CAP_PROP_ORIENTATION_AUTO,0)
    rows=[]
    for time in [70,95,105]:
        anchor,_=decode(cap,time,1);target,pts=decode(cap,raw['LEFT'][time]['pts_s']+data['timing_offset_s'],1)
        a=cv2.resize(anchor,(960,540));b=cv2.resize(target,(960,540));p=orient_grid(raw['RIGHT'][time])*.25
        q,st,_=cv2.calcOpticalFlowPyrLK(a,b,p,None,winSize=(21,21),maxLevel=3)
        back,sb,_=cv2.calcOpticalFlowPyrLK(b,a,q,None,winSize=(21,21),maxLevel=3)
        good=(st.ravel()>0)&(sb.ravel()>0)&(np.linalg.norm(back-p,axis=2).ravel()<.25)
        q*=4;cv2.cornerSubPix(target,q,(5,5),(-1,-1),(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_MAX_ITER,40,1e-4))
        left=orient_grid(raw['LEFT'][time]);uv=[cv2.undistortPoints(z,k,d).reshape(-1,2) for z,k,d in zip([left,q],K,D)]
        xyz=cv2.triangulatePoints(np.c_[np.eye(3),np.zeros(3)],np.c_[R,t],uv[0].T,uv[1].T);xyz=(xyz[:3]/xyz[3]).T
        finite=np.all(np.isfinite(xyz),axis=1)&(xyz[:,2]>0)&((xyz@R.T+t)[:,2]>0)
        if not np.all((good&finite)[[0,8]]):
            rows.append(dict(time_s=time,status='ENDPOINT_OBSERVATION_REJECTED'));continue
        length=float(np.linalg.norm(xyz[8]-xyz[0]));baseline=float(span['value_m']/length)
        project=[]
        for points,k in [(xyz,K[0]),(xyz@R.T+t,K[1])]:
            pp=points[:,:2]/points[:,2:];project.append(pp)
        errors=np.sqrt(sum(np.sum((u-v)**2,axis=1) for u,v in zip(uv,project)))*np.mean([K[0][0,0],K[1][0,0]])
        rows.append(dict(time_s=time,right_pts_s=pts,status='SCALE_OBSERVATION',baseline_m=baseline,
                         normalized_span=length,endpoint_reprojection_px=errors[[0,8]].tolist()))
    cap.release();values=[r['baseline_m'] for r in rows if 'baseline_m' in r]
    if len(values)<2:raise ValueError('insufficient measured span observations')
    baseline=float(np.median(values));data['T_m']=(t*baseline).tolist();data['baseline_m']=baseline
    data['scale_source']=span;data['scale_observations']=rows;data['baseline_spread_m']=float(np.ptp(values))
    data.pop('observations',None)
    data['status']='MEASURED_SPAN_SCALE_CANDIDATE_NOT_PHYSICAL_APPROVAL'
    (out/'result.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
    print(json.dumps(dict(baseline_m=baseline,spread_m=np.ptp(values),observations=rows)))


if __name__=='__main__':main()
