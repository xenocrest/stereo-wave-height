"""Unapproved calibration diagnostic: never a physical measurement PASS."""
from pathlib import Path
import json
import cv2
import numpy as np
from reconstruction.opencv_dense import reconstruct_dense_stereo, DenseStereoPolicy
from reconstruction.height import height_from_plane


def main():
    root=Path('D:/stereo-wave-height-runs/HomeTank_006')
    data=json.loads((root/'shared_target_stereo/result.json').read_text())
    out=root/'diagnostic_height';out.mkdir(exist_ok=True)
    results=[];normal=None;offset=None
    for time in [1.,2.,10.]:
        images=[]
        for side,role in [(0,'LEFT'),(1,'RIGHT')]:
            path=Path('experiments/real_video/HomeTank_006/videos/wave')/f'HomeTank_006_wave_cam{side}_{role}.mp4'
            c=cv2.VideoCapture(str(path));c.set(cv2.CAP_PROP_ORIENTATION_AUTO,0);c.set(cv2.CAP_PROP_POS_MSEC,time*1000)
            ok,f=c.read();c.release()
            if not ok:raise RuntimeError('frame decode failed')
            if side==0:f=cv2.rotate(f,cv2.ROTATE_180)
            images.append(cv2.resize(f,(960,540),interpolation=cv2.INTER_AREA))
        k0=np.array(data['K0']);k1=np.array(data['K1']);k0[:2]*=.25;k1[:2]*=.25
        r=reconstruct_dense_stereo(*images,K0=k0,D0=np.array(data['D0']),K1=k1,D1=np.array(data['D1']),R_right_from_left=np.array(data['R']),T_right_from_left_m=np.array(data['T_m']),policy=DenseStereoPolicy(),rectification_alpha=-1)
        # Diagnostic central lower image window, NOT a user-validated water ROI.
        roi=np.zeros((540,960),bool);roi[280:430,250:750]=True
        valid=r.valid_mask&roi&(r.xyz_m[:,:,2]>0)
        pts=r.xyz_m[valid]
        if len(pts)<12:raise RuntimeError('insufficient stereo points')
        if normal is None:
            center=np.mean(pts,axis=0);_,_,vt=np.linalg.svd(pts-center,full_matrices=False);normal=vt[-1]
            if normal[2]>0:normal=-normal
            offset=-float(normal@center)
        h=height_from_plane(pts,normal,offset)
        grid=np.full(valid.shape,np.nan);grid[valid]=h
        np.savez_compressed(out/f'frame_{int(time):02d}.npz',height_m=grid,xyz_m=r.xyz_m,valid_mask=valid)
        cv2.imwrite(str(out/f'frame_{int(time):02d}_left.png'),r.rectified_left)
        results.append(dict(time_s=time,valid_points=len(pts),candidate_roi_coverage=float(valid.sum()/roi.sum()),height_mean_m=float(h.mean()),height_rms_m=float(np.sqrt(np.mean(h*h))),height_p5_p95_m=np.percentile(h,[5,95]).tolist(),height_range_m=[float(h.min()),float(h.max())]))
    report=dict(status='DIAGNOSTIC_HEIGHT_ONLY_NOT_VALIDATED',limitations=['calibration not approved','nominal-time pairs: synchronization not established','ROI and surface identity not verified; may include tank bottom','960x540 diagnostic, NOT original 4K per-pixel result','No completion of missing pixels'],normal=normal.tolist(),offset_m=offset,frames=results)
    (out/'result.json').write_text(json.dumps(report),encoding='utf-8');print(json.dumps(report))

if __name__=='__main__':main()
