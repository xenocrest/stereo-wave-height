"""Recover measured chess corners using image features only as search seeds.

Homography predictions are never accepted as observations: full-resolution
corner refinement and measured alternating-cell contrast are required.
"""
from pathlib import Path
import json
import cv2
import numpy as np
from hometank006_target_release_diagnostic import orient_grid

ROOT=Path('D:/stereo-wave-height-runs/HomeTank_006')


def decode(cap,time,side):
    cap.set(cv2.CAP_PROP_POS_MSEC,time*1000);ok,im=cap.read()
    if not ok:raise RuntimeError('calibration frame decode failed')
    pts=cap.get(cv2.CAP_PROP_POS_MSEC)/1000
    if side==0:im=cv2.rotate(im,cv2.ROTATE_180)
    return cv2.cvtColor(im,cv2.COLOR_BGR2GRAY),pts


def contrast_gate(gray,points,grid):
    """Require two bright and two dark diagonal physical cells at each corner."""
    p=points.reshape(6,9,2);g=grid.reshape(6,9,2);valid=np.zeros(54,bool)
    contrast=[]
    for j in range(6):
        for i in range(9):
            u=(g[j,min(i+1,8)]-g[j,max(i-1,0)])/(1 if i in (0,8) else 2)
            v=(g[min(j+1,5),i]-g[max(j-1,0),i])/(1 if j in (0,5) else 2)
            samples=[]
            for a,b in [(1,1),(-1,-1),(1,-1),(-1,1)]:
                x,y=np.rint(p[j,i]+.23*(a*u+b*v)).astype(int)
                if not 2<=x<gray.shape[1]-2 or not 2<=y<gray.shape[0]-2:
                    samples=[];break
                samples.append(float(np.median(gray[y-2:y+3,x-2:x+3])))
            if len(samples)==4:
                s=np.array(samples);d=float(s[:2].mean()-s[2:].mean())
                valid[j*9+i]=abs(d)>=20 and max(abs(s[0]-s[1]),abs(s[2]-s[3]))<abs(d)
                contrast.append(abs(d))
    return valid


def main():
    cv2.setRNGSeed(42)
    out=ROOT/'guided_corners';out.mkdir(exist_ok=True)
    sift=cv2.SIFT_create(nfeatures=10000,contrastThreshold=.02)
    all_records={}
    for side,role in [(0,'LEFT'),(1,'RIGHT')]:
        records=json.loads((ROOT/'partial_calibration_larger'/f'{role}_result.json').read_text())['records']
        known={r['time_s']:r for r in records if r['found'] and sorted(r['pattern_size'])==[6,9]}
        path=Path('experiments/real_video/HomeTank_006/videos/calibration')/f'HomeTank_006_calibration_cam{side}_{role}.mp4'
        cap=cv2.VideoCapture(str(path));cap.set(cv2.CAP_PROP_ORIENTATION_AUTO,0)
        templates={}
        for time,r in known.items():
            gray,pts=decode(cap,time,side);small=cv2.resize(gray,(1920,1080),interpolation=cv2.INTER_AREA)
            grid=orient_grid(r).reshape(-1,2);mask=np.zeros(small.shape,np.uint8)
            cv2.fillConvexPoly(mask,cv2.convexHull((grid*.5).astype(np.int32)),255)
            kp,desc=sift.detectAndCompute(small,mask)
            templates[time]=(kp,desc,grid*.5)
        recovered=[]
        for time in range(5,106,5):
            gray,pts=decode(cap,time,side);small=cv2.resize(gray,(1920,1080),interpolation=cv2.INTER_AREA)
            kp,desc=sift.detectAndCompute(small,None)
            rec=dict(time_s=time,pts_s=pts,status='NO_SUPPORTED_CORNER_SEEDS')
            # Exclude the target itself to validate the guided detector on known views.
            for anchor in sorted((t for t in templates if t!=time),key=lambda t:abs(t-time))[:2]:
                ka,da,ga=templates[anchor]
                if desc is None or da is None:continue
                matches=cv2.BFMatcher().knnMatch(da,desc,k=2)
                good=[m for pair in matches if len(pair)==2 for m,n in [pair] if m.distance<.7*n.distance]
                if len(good)<12:continue
                a=np.float32([ka[m.queryIdx].pt for m in good]);b=np.float32([kp[m.trainIdx].pt for m in good])
                H,inliers=cv2.findHomography(a,b,cv2.RANSAC,2.)
                if H is None or int(inliers.sum())<12:continue
                seed=cv2.perspectiveTransform(ga.astype(np.float32).reshape(-1,1,2),H)*2
                inside=(seed[:,:,0]>12)&(seed[:,:,0]<3828)&(seed[:,:,1]>12)&(seed[:,:,1]<2148)
                corners=seed.copy();ids=np.flatnonzero(inside.ravel())
                if len(ids)<12:continue
                refined=corners[ids].copy()
                cv2.cornerSubPix(gray,refined,(9,9),(-1,-1),(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_MAX_ITER,50,1e-4))
                corners[ids]=refined
                valid=inside.ravel()&contrast_gate(gray,corners,seed)
                valid &= np.linalg.norm(corners-seed,axis=2).ravel()<9
                if valid.sum()<12:continue
                rec.update(status='IMAGE_REFINED_OBSERVATIONS',anchor_s=anchor,homography_inliers=int(inliers.sum()),
                    corners=corners.reshape(-1,2).tolist(),valid=valid.tolist(),valid_count=int(valid.sum()))
                if time in known:
                    error=np.linalg.norm(corners-orient_grid(known[time]),axis=2).ravel()
                    rec['independent_sb_comparison']=dict(count=int(valid.sum()),rms_px=float(np.sqrt(np.mean(error[valid]**2))),p95_px=float(np.percentile(error[valid],95)))
                break
            recovered.append(rec);print(role,time,rec.get('valid_count',0),rec.get('independent_sb_comparison'),flush=True)
        cap.release();all_records[role]=recovered
        (out/f'{role}.json').write_text(json.dumps(recovered),encoding='utf-8')
    (out/'result.json').write_text(json.dumps(dict(status='OBSERVATIONS_ONLY_NOT_CALIBRATION_APPROVAL',records=all_records)),encoding='utf-8')


if __name__=='__main__':main()
