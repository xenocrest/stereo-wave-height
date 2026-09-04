"""Bounded partial-board monocular feasibility; never assumes stereo IDs."""
from pathlib import Path
import json
import cv2
import numpy as np


def main():
    out=Path('D:/stereo-wave-height-runs/HomeTank_006/partial_calibration_larger')
    out.mkdir(parents=True,exist_ok=True)
    # Minimum contiguous 7x4 subset of the confirmed 9x6 board; LARGER
    # returns the actually observed lattice dimensions through metadata.
    # Its origin is view-local: valid for mono pose, NOT stereo correspondence.
    for side,role in [(0,'LEFT'),(1,'RIGHT')]:
        path=Path('experiments/real_video/HomeTank_006/videos/calibration')/f'HomeTank_006_calibration_cam{side}_{role}.mp4'
        cap=cv2.VideoCapture(str(path));cap.set(cv2.CAP_PROP_ORIENTATION_AUTO,0)
        records=[]
        for t in range(5,106,5):
            cap.set(cv2.CAP_PROP_POS_MSEC,t*1000);ok,f=cap.read()
            if not ok:continue
            if side==0:f=cv2.rotate(f,cv2.ROTATE_180)
            gray=cv2.cvtColor(f,cv2.COLOR_BGR2GRAY)
            small=cv2.resize(gray,None,fx=.25,fy=.25,interpolation=cv2.INTER_AREA)
            found,points,meta=cv2.findChessboardCornersSBWithMeta(small,(7,4),cv2.CALIB_CB_NORMALIZE_IMAGE|cv2.CALIB_CB_EXHAUSTIVE|cv2.CALIB_CB_LARGER)
            rec=dict(time_s=t,pts_s=cap.get(cv2.CAP_PROP_POS_MSEC)/1000,found=bool(found))
            if found:
                rec['pattern_size']=[int(meta.shape[1]),int(meta.shape[0])]
                points=np.asarray(points,np.float32)*4
                cv2.cornerSubPix(gray,points,(5,5),(-1,-1),(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_MAX_ITER,40,1e-4))
                rec['corners']=points.reshape(-1,2).tolist()
                canvas=f.copy();cv2.drawChessboardCorners(canvas,tuple(rec['pattern_size']),points,True)
                cv2.imwrite(str(out/f'{role}_{t:03d}_overlay.jpg'),cv2.resize(canvas,(1280,720)))
            records.append(rec);print(role,t,found,flush=True)
        cap.release()
        accepted=[r for r in records if r['found']]
        good=[np.array(r['corners'],np.float32).reshape(-1,1,2) for r in accepted]
        objects=[]
        for rec in accepted:
            cols,rows=rec['pattern_size'];obj=np.zeros((cols*rows,3),np.float32)
            obj[:,:2]=np.mgrid[:cols,:rows].T.reshape(-1,2)*.020;objects.append(obj)
        result=dict(status='INSUFFICIENT_PARTIAL_OBSERVATIONS',source=str(path),minimum_pattern=[7,4],square_size_m=.020,identity='VIEW_LOCAL_NOT_STEREO_REGISTERED',approved_for_reconstruction=False,records=records)
        if len(good)>=8:
            rms,K,D,rv,tv=cv2.calibrateCamera(objects,good,(3840,2160),None,None)
            result.update(status='MONO_DIAGNOSTIC_ONLY' if rms<=5 else 'MONO_REPROJECTION_FAIL',diagnostic_rms_limit_px=5.,rms_px=float(rms),K=K.tolist(),D=D.tolist())
        (out/f'{role}_result.json').write_text(json.dumps(result),encoding='utf-8')

if __name__=='__main__':main()
