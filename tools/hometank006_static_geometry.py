"""Static-scene essential geometry candidate, retaining calibration metric scale."""
from pathlib import Path
import json
import cv2
import numpy as np

def frame(side,time):
    role=['LEFT','RIGHT'][side]
    p=Path('experiments/real_video/HomeTank_006/videos/wave')/f'HomeTank_006_wave_cam{side}_{role}.mp4'
    c=cv2.VideoCapture(str(p));c.set(cv2.CAP_PROP_ORIENTATION_AUTO,0);c.set(cv2.CAP_PROP_POS_MSEC,time*1000);ok,f=c.read();pts=c.get(cv2.CAP_PROP_POS_MSEC)/1000;c.release()
    if not ok:raise RuntimeError('decode failed')
    if side==0:f=cv2.rotate(f,cv2.ROTATE_180)
    return cv2.resize(f,(960,540),interpolation=cv2.INTER_AREA),pts

def epipolar_error(a,b,E):
    x=np.c_[a,np.ones(len(a))];y=np.c_[b,np.ones(len(b))];ex=x@E.T;ey=y@E
    return np.abs(np.sum(y*ex,axis=1))/np.sqrt(ex[:,0]**2+ex[:,1]**2+ey[:,0]**2+ey[:,1]**2)

def main():
    cv2.setRNGSeed(42)
    root=Path('D:/stereo-wave-height-runs/HomeTank_006');out=root/'static_geometry_no_ruler';out.mkdir(exist_ok=True)
    cal=json.loads((root/'shared_target_stereo/result.json').read_text())
    K=[np.array(cal[f'K{i}']) for i in range(2)];D=[np.array(cal[f'D{i}']) for i in range(2)]
    for k in K:k[:2]*=.25
    images=[frame(i,1.)[0] for i in range(2)]
    sift=cv2.SIFT_create(nfeatures=8000)
    # Conservative visually identified exclusion: ruler cannot enter geometry.
    masks=[np.full((540,960),255,np.uint8) for _ in images]
    masks[0][:,680:]=0;masks[1][:,420:620]=0
    features=[sift.detectAndCompute(cv2.cvtColor(im,cv2.COLOR_BGR2GRAY),mask) for im,mask in zip(images,masks)]
    matches=cv2.BFMatcher().knnMatch(features[0][1],features[1][1],k=2)
    good=[m for m,n in matches if m.distance<.7*n.distance]
    if len(good)<15:
        result=dict(status='INSUFFICIENT_NON_RULER_FEATURES',matched_features=len(good),approved_for_reconstruction=False)
        (out/'result.json').write_text(json.dumps(result),encoding='utf-8');print(result);return
    xy=[np.float32([features[i][0][m.queryIdx if i==0 else m.trainIdx].pt for m in good]) for i in range(2)]
    # Features here may include non-water objects; only camera geometry is estimated.
    norm=[cv2.undistortPoints(p.reshape(-1,1,2),k,d).reshape(-1,2) for p,k,d in zip(xy,K,D)]
    ids=np.arange(len(good));train=ids%3!=0;hold=~train
    E,mask=cv2.findEssentialMat(norm[0][train],norm[1][train],np.eye(3),method=cv2.RANSAC,prob=.999,threshold=.0015)
    if E is None or E.shape!=(3,3):raise RuntimeError('essential estimation failed')
    count,R,T,posemask=cv2.recoverPose(E,norm[0][train],norm[1][train],np.eye(3),mask=mask)
    scale=float(np.median([p['baseline_m'] for p in cal['per_pair_pose']]))
    T=T*scale
    errors=epipolar_error(norm[0][hold],norm[1][hold],E)*np.mean([K[0][0,0],K[1][0,0]])
    held=errors<1.5
    report=dict(status='STATIC_SCENE_GEOMETRY_CANDIDATE_NOT_PHYSICAL_VALIDATION',source_frames=[1.,1.],matched_features=len(good),train_count=int(train.sum()),cheirality_inliers=count,heldout_count=int(hold.sum()),heldout_inlier_count=int(held.sum()),heldout_inlier_rms_px=float(np.sqrt(np.mean(errors[held]**2))),heldout_all_p95_px=float(np.percentile(errors,95)),processing_size=[960,540],K0=cal['K0'],D0=cal['D0'],K1=cal['K1'],D1=cal['D1'],R=R.tolist(),T_m=T.ravel().tolist(),baseline_m=scale,scale_source='median calibration-board per-pair baseline; uncertainty not established',approved_for_reconstruction=False)
    (out/'result.json').write_text(json.dumps(report),encoding='utf-8')
    canvas=cv2.drawMatches(images[0],features[0][0],images[1],features[1][0],good[:100],None,flags=2)
    cv2.imwrite(str(out/'feature_matches.jpg'),canvas)
    print(json.dumps(report))

if __name__=='__main__':main()
