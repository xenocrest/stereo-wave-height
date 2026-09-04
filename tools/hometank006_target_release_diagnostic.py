"""Official object-release diagnostic; nominal scale is NOT surveyed scale."""
import json
from pathlib import Path
import cv2
import numpy as np


def orient_grid(record):
    cols,rows=record['pattern_size']
    p=np.asarray(record['corners'],np.float32).reshape(rows,cols,2)
    if (rows,cols)==(9,6):p=p.transpose(1,0,2)
    if p.shape!=(6,9,2):raise ValueError('complete board required for object release')
    # Restrict this diagnostic to board views whose axes agree with image axes.
    if np.mean(p[:,-1,0]-p[:,0,0])<0:p=p[:,::-1]
    if np.mean(p[-1,:,1]-p[0,:,1])<0:p=p[::-1]
    return p.copy().reshape(-1,1,2)


def main():
    root=Path('D:/stereo-wave-height-runs/HomeTank_006')
    out=root/'target_release_diagnostic';out.mkdir(exist_ok=True)
    obj=np.zeros((54,3),np.float32);obj[:,:2]=np.mgrid[:9,:6].T.reshape(-1,2)*.020
    results={}
    for side in ['LEFT','RIGHT']:
        d=json.loads((root/'partial_calibration_larger'/f'{side}_result.json').read_text())
        records=[r for r in d['records'] if r['found'] and sorted(r['pattern_size'])==[6,9]]
        images=[orient_grid(r) for r in records];objects=[obj.copy() for _ in images]
        flags=cv2.CALIB_FIX_K3
        rms,k,dist,_,_=cv2.calibrateCamera(objects,images,(3840,2160),None,None,flags=flags)
        ro,kr,dr,_,_,newobj=cv2.calibrateCameraRO(objects,images,(3840,2160),8,None,None,flags=flags)
        heldout=[]
        for i in range(len(images)):
            train=[im for j,im in enumerate(images) if j!=i]
            _,hk,hd,_,_,ho=cv2.calibrateCameraRO([obj.copy() for _ in train],train,(3840,2160),8,None,None,flags=flags)
            success,rv,tv=cv2.solvePnP(ho,images[i],hk,hd)
            if not success:raise RuntimeError('heldout pose estimation failed')
            projected,_=cv2.projectPoints(ho,rv,tv,hk,hd)
            error=projected.reshape(-1,2)-images[i].reshape(-1,2)
            heldout.append(dict(time_s=records[i]['time_s'],rms_px=float(np.sqrt(np.mean(np.sum(error**2,axis=1)))),K=hk.tolist()))
        results[side]=dict(times=[r['time_s'] for r in records],fixed_grid_rms_px=float(rms),released_grid_rms_px=float(ro),fixed_K=k.tolist(),released_K=kr.tolist(),released_D=dr.tolist(),released_object_points_m=np.asarray(newobj).reshape(-1,3).tolist(),heldout=heldout,approved_for_reconstruction=False)
        print(side,'views',len(images),'fixed',rms,'release',ro,'K',kr,flush=True)
    payload=dict(status='DIAGNOSTIC_ONLY_NO_STEREO_OR_HEIGHT',scale_source='USER_NOMINAL_20MM_NOT_SURVEYED_160MM_EDGE',method='OPENCV_CALIBRATE_CAMERA_RO',results=results)
    (out/'result.json').write_text(json.dumps(payload),encoding='utf-8')

if __name__=='__main__':main()
