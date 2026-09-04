"""Audit raw matcher support, without computing or claiming water heights."""
from pathlib import Path
import json
import cv2
import numpy as np
from reconstruction.opencv_dense import DenseStereoPolicy,_matcher,_remap_support,disparity_observation_mask,left_right_consistency


def describe(values):
    x=np.asarray(values);x=x[np.isfinite(x)]
    return dict(count=int(x.size),percentiles_p0_p5_p50_p95_p100=np.percentile(x,[0,5,50,95,100]).tolist() if x.size else None)


def main():
    root=Path('D:/stereo-wave-height-runs/HomeTank_006')
    data=json.loads((root/'shared_target_stereo/result.json').read_text())
    out=root/'disparity_validity';out.mkdir(exist_ok=True)
    k0=np.array(data['K0']);k1=np.array(data['K1']);k0[:2]*=.25;k1[:2]*=.25
    size=(960,540);policy=DenseStereoPolicy()
    r0,r1,p0,p1,q,*_=cv2.stereoRectify(k0,np.array(data['D0']),k1,np.array(data['D1']),size,
        np.array(data['R']),np.array(data['T_m']).reshape(3,1),flags=cv2.CALIB_ZERO_DISPARITY,alpha=-1)
    maps=[cv2.initUndistortRectifyMap(k,d,r,p,size,cv2.CV_32FC1) for k,d,r,p in
          [(k0,np.array(data['D0']),r0,p0),(k1,np.array(data['D1']),r1,p1)]]
    support=[_remap_support(m,960,540,policy.block_size) for m in maps]
    records=[]
    for time in [1.,2.,10.]:
        images=[]
        for side,role in [(0,'LEFT'),(1,'RIGHT')]:
            path=Path('experiments/real_video/HomeTank_006/videos/wave')/f'HomeTank_006_wave_cam{side}_{role}.mp4'
            cap=cv2.VideoCapture(str(path));cap.set(cv2.CAP_PROP_ORIENTATION_AUTO,0);cap.set(cv2.CAP_PROP_POS_MSEC,time*1000)
            ok,frame=cap.read();cap.release()
            if not ok:raise RuntimeError('frame decode failed')
            if side==0:frame=cv2.rotate(frame,cv2.ROTATE_180)
            frame=cv2.resize(frame,size,interpolation=cv2.INTER_AREA)
            images.append(cv2.cvtColor(cv2.remap(frame,*maps[side],cv2.INTER_LINEAR),cv2.COLOR_BGR2GRAY))
        dl=_matcher(policy).compute(*images).astype(float)/16
        legacy_right=_matcher(policy,right=True);legacy_right.setMinDisparity(-256)
        old_dr=legacy_right.compute(images[1],images[0]).astype(float)/16
        old_mask=left_right_consistency(dl,old_dr,1.5)&(dl>0)&(dl<256)
        dr=_matcher(policy,right=True).compute(images[1],images[0]).astype(float)/16
        valid,counts=disparity_observation_mask(dl,dr,*support,policy)
        xyz=cv2.reprojectImageTo3D(dl.astype(np.float32),q)
        valid &= np.all(np.isfinite(xyz),axis=2)&(xyz[:,:,2]>0)
        window=np.zeros(dl.shape,bool);window[280:430,250:750]=True
        records.append(dict(time_s=time,legacy_mask_count=int(old_mask.sum()),
            legacy_endpoint_count=int(np.sum(old_mask&(dl==255))),
            diagnostic_window_legacy_count=int(np.sum(old_mask&window)),
            diagnostic_window_legacy_endpoint_count=int(np.sum(old_mask&window&(dl==255))),
            corrected_mask_count=int(valid.sum()),gates=counts,
            corrected_disparity_px=describe(dl[valid]),corrected_depth_m=describe(xyz[:,:,2][valid])))
    result=dict(status='DIAGNOSTIC_NOT_WATER_HEIGHT_VALIDATION',frames=records,
        limitations=['Unapproved candidate geometry unchanged','Nominal timestamps are NOT verified synchronization',
                     'Whole-image support is not a water-surface mask','Legacy diagnostic window is not a validated water ROI',
                     'No height, completion, reference update or GUI change'])
    (out/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':main()
