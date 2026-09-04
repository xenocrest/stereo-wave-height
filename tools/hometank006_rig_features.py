"""Multi-pose calibrated essential geometry from real board texture matches.

No ruler, wave heights or artificial point coordinates enter pose estimation.
Metric scale remains the measured-board calibration's uncertain baseline.
"""
from pathlib import Path
import argparse
import json
import cv2
import numpy as np
from hometank006_guided_corners import decode

ROOT=Path('D:/stereo-wave-height-runs/HomeTank_006')


def residual_px(a,b,E,f):
    x=np.c_[a,np.ones(len(a))];y=np.c_[b,np.ones(len(b))]
    l=x@E.T;r=y@E
    return abs(np.sum(y*l,axis=1))/np.sqrt(l[:,0]**2+l[:,1]**2+r[:,0]**2+r[:,1]**2)*f


def main():
    cv2.setRNGSeed(42)
    parser=argparse.ArgumentParser();parser.add_argument('--offset',type=float);parser.add_argument('--name',default='rig_features')
    args=parser.parse_args()
    out=ROOT/args.name;out.mkdir(exist_ok=True)
    cal=json.loads((ROOT/'shared_target_stereo/result.json').read_text())
    timing=json.loads((ROOT/'board_timing/result.json').read_text())['best_diagnostic']
    offset=timing['offset_s'] if args.offset is None else args.offset
    K=[np.array(cal[f'K{i}']) for i in range(2)];D=[np.array(cal[f'D{i}']).reshape(-1) for i in range(2)]
    caps=[]
    for side,role in [(0,'LEFT'),(1,'RIGHT')]:
        p=Path('experiments/real_video/HomeTank_006/videos/calibration')/f'HomeTank_006_calibration_cam{side}_{role}.mp4'
        cap=cv2.VideoCapture(str(p));cap.set(cv2.CAP_PROP_ORIENTATION_AUTO,0);caps.append(cap)
    observations=[];sift=cv2.SIFT_create(nfeatures=12000,contrastThreshold=.02)
    for time in [5,20,40,65,70,90,95,105]:
        images=[];times=[];features=[]
        for side in [0,1]:
            gray,pts=decode(caps[side],time+side*offset,side)
            small=cv2.resize(gray,(1920,1080),interpolation=cv2.INTER_AREA)
            images.append(small);times.append(pts)
            features.append(sift.detectAndCompute(small,None))
        good=[]
        if all(d is not None for k,d in features):
            match=cv2.BFMatcher();forward=match.knnMatch(features[0][1],features[1][1],k=2)
            reverse=match.knnMatch(features[1][1],features[0][1],k=2)
            back={m.queryIdx:m.trainIdx for pair in reverse if len(pair)==2 for m,n in [pair] if m.distance<.7*n.distance}
            good=[m for pair in forward if len(pair)==2 for m,n in [pair] if m.distance<.7*n.distance and back.get(m.trainIdx)==m.queryIdx]
        xy=[np.float32([features[i][0][m.queryIdx if i==0 else m.trainIdx].pt for m in good])*2 for i in [0,1]]
        if len(good)<15:print(time,'insufficient',len(good),flush=True);continue
        norm=[cv2.undistortPoints(p.reshape(-1,1,2),k,d).reshape(-1,2) for p,k,d in zip(xy,K,D)]
        observations.append(dict(time_s=time,pts_s=times,pixels=[p.tolist() for p in xy],normalized=[p.tolist() for p in norm],count=len(good)))
        cv2.imwrite(str(out/f'matches_{time:03d}.jpg'),cv2.resize(cv2.drawMatches(images[0],features[0][0],images[1],features[1][0],good[:100],None,flags=2),(1920,540)))
        print(time,len(good),flush=True)
    for c in caps:c.release()
    if len(observations)<4:raise RuntimeError('not enough independent pose groups')
    f=float(np.mean([k[0,0] for k in K]));threshold=2/f
    held=[]
    for i,ob in enumerate(observations):
        a,b=[np.concatenate([np.asarray(o['normalized'][side]) for j,o in enumerate(observations) if j!=i]) for side in [0,1]]
        E,mask=cv2.findEssentialMat(a,b,np.eye(3),method=cv2.RANSAC,prob=.999,threshold=threshold)
        e=residual_px(*[np.asarray(p) for p in ob['normalized']],E,f)
        held.append(dict(time_s=ob['time_s'],count=len(e),median_px=float(np.median(e)),p95_px=float(np.percentile(e,95)),within_2px_ratio=float(np.mean(e<=2))))
    a,b=[np.concatenate([np.asarray(o['normalized'][side]) for o in observations]) for side in [0,1]]
    E,mask=cv2.findEssentialMat(a,b,np.eye(3),method=cv2.RANSAC,prob=.999,threshold=threshold)
    count,R,T,positive=cv2.recoverPose(E,a,b,np.eye(3),mask=mask)
    scale=timing['baseline_m'];T*=scale
    r0,r1,p0,p1,q,roi0,roi1=cv2.stereoRectify(K[0],D[0],K[1],D[1],(3840,2160),R,T,flags=cv2.CALIB_ZERO_DISPARITY,alpha=-1)
    report=dict(status='MULTIPOSE_ESSENTIAL_CANDIDATE_NOT_PHYSICAL_APPROVAL',
        K0=K[0].tolist(),D0=D[0].tolist(),K1=K[1].tolist(),D1=D[1].tolist(),R=R.tolist(),T_m=T.ravel().tolist(),
        baseline_m=scale,scale_source='measured-board calibration timing candidate; uncertainty UNKNOWN',
        timing_offset_s=offset,heldout=held,match_count=len(a),cheirality_inliers=count,
        rectified_rois=[list(roi0),list(roi1)],rectified_focal_px=float(p0[0,0]),
        observations=observations,approved_for_reconstruction=False)
    (out/'result.json').write_text(json.dumps(report),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='observations'}))


if __name__=='__main__':main()
