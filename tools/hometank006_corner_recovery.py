"""Bounded official-detector recovery on clear sampled original frames."""
from pathlib import Path
import json
import cv2
import numpy as np

out=Path('D:/stereo-wave-height-runs/HomeTank_006/input_analysis')
for side,role in [(0,'LEFT'),(1,'RIGHT')]:
    path=Path('experiments/real_video/HomeTank_006/videos/calibration')/f'HomeTank_006_calibration_cam{side}_{role}.mp4'
    c=cv2.VideoCapture(str(path));c.set(cv2.CAP_PROP_ORIENTATION_AUTO,0);records=[]
    for t in [5,10,15,20,25,30,34,40,50,60,65,75,85,90,100]:
        c.set(cv2.CAP_PROP_POS_MSEC,t*1000);ok,f=c.read()
        if not ok:continue
        if side==0:f=cv2.rotate(f,cv2.ROTATE_180)
        gray=cv2.cvtColor(f,cv2.COLOR_BGR2GRAY)
        small=cv2.resize(gray,None,fx=.25,fy=.25,interpolation=cv2.INTER_AREA)
        attempts=[];found_corners=None
        for name,image in [('CLASSIC_QUARTER',small),('CLASSIC_CLAHE_QUARTER',cv2.createCLAHE(2,(8,8)).apply(small)),('SB_QUARTER',small)]:
            if name.startswith('CLASSIC'):
                found,pts=cv2.findChessboardCorners(image,(9,6),cv2.CALIB_CB_ADAPTIVE_THRESH|cv2.CALIB_CB_NORMALIZE_IMAGE)
            else:found,pts=cv2.findChessboardCornersSB(image,(9,6),cv2.CALIB_CB_NORMALIZE_IMAGE|cv2.CALIB_CB_EXHAUSTIVE)
            attempts.append(dict(method=name,detected=bool(found)))
            if found:
                pts=np.asarray(pts,np.float32)*4
                cv2.cornerSubPix(gray,pts,(5,5),(-1,-1),(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_MAX_ITER,40,1e-4))
                found_corners=pts.reshape(-1,2).tolist();break
        records.append(dict(time_s=t,actual_pts_s=c.get(cv2.CAP_PROP_POS_MSEC)/1000,attempts=attempts,corners=found_corners))
        print(role,t,attempts,flush=True)
    c.release();(out/f'calibration_{side}_recovery.json').write_text(json.dumps(records),encoding='utf-8')
