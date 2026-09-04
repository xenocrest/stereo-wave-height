"""Check same-camera background image coordinates across recording sessions."""
from pathlib import Path
import json
import cv2
import numpy as np
from hometank006_guided_corners import decode
from hometank006_target_release_diagnostic import orient_grid


def main():
    cv2.setRNGSeed(42);root=Path('D:/stereo-wave-height-runs/HomeTank_006');out=root/'capture_transfer';out.mkdir(exist_ok=True)
    sift=cv2.SIFT_create(nfeatures=20000,contrastThreshold=.01);records=[]
    for side,role in [(0,'LEFT'),(1,'RIGHT')]:
        images=[];features=[]
        for kind,time in [('calibration',105.),('wave',1.)]:
            p=Path('experiments/real_video/HomeTank_006/videos')/kind/f'HomeTank_006_{kind}_cam{side}_{role}.mp4'
            cap=cv2.VideoCapture(str(p));cap.set(cv2.CAP_PROP_ORIENTATION_AUTO,0);gray,pts=decode(cap,time,side);cap.release()
            small=cv2.resize(gray,(1920,1080),interpolation=cv2.INTER_AREA);mask=np.full(small.shape,255,np.uint8)
            if kind=='calibration':
                r=next(r for r in json.loads((root/'partial_calibration_larger'/f'{role}_result.json').read_text())['records'] if r['time_s']==105)
                grid=orient_grid(r).reshape(-1,2)*.5;hull=cv2.convexHull(grid.astype(np.int32))
                board=np.zeros(mask.shape,np.uint8);cv2.fillConvexPoly(board,hull,255);board=cv2.dilate(board,np.ones((151,151),np.uint8))
                mask[board>0]=0
            else:
                # Tank, water and ruler absent from calibration scene: exclude all.
                polygon=([(190,360),(480,260),(1830,20),(1919,1079),(0,1079)] if side==0 else [(0,120),(1600,0),(1919,500),(1919,1079),(0,1079)])
                cv2.fillPoly(mask,[np.array(polygon,np.int32)],0)
            images.append(small);features.append(sift.detectAndCompute(small,mask))
        ka,da=features[0];kb,db=features[1]
        if da is None or db is None:
            records.append(dict(camera=role,status='NO_STATIC_BACKGROUND_FEATURES'));continue
        matcher=cv2.BFMatcher();forward=matcher.knnMatch(da,db,k=2);reverse=matcher.knnMatch(db,da,k=2)
        back={m.queryIdx:m.trainIdx for pair in reverse if len(pair)==2 for m,n in [pair] if m.distance<.65*n.distance}
        good=[m for pair in forward if len(pair)==2 for m,n in [pair] if m.distance<.65*n.distance and back.get(m.trainIdx)==m.queryIdx]
        r=dict(camera=role,match_count=len(good),status='INSUFFICIENT_STATIC_BACKGROUND_CORRESPONDENCES')
        if len(good)>=8:
            a=np.float32([ka[m.queryIdx].pt for m in good]);b=np.float32([kb[m.trainIdx].pt for m in good])
            H,mask=cv2.findHomography(a,b,cv2.RANSAC,1.)
            if H is not None:
                ok=mask.ravel()>0;delta=(b-a)[ok]
                r.update(status='DIAGNOSTIC_BACKGROUND_TRANSFER_NOT_APPROVED',inliers=int(ok.sum()),
                         median_shift_halfres_px=np.median(delta,axis=0).tolist(),p95_identity_error_halfres_px=float(np.percentile(np.linalg.norm(delta,axis=1),95)),H_halfres=H.tolist())
        cv2.imwrite(str(out/f'{role}_background_matches.jpg'),cv2.resize(cv2.drawMatches(images[0],ka,images[1],kb,good,None,flags=2),(1920,540)))
        records.append(r);print(json.dumps(r))
    (out/'result.json').write_text(json.dumps(records,indent=2),encoding='utf-8')


if __name__=='__main__':main()
