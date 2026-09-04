"""Isolated video-to-point-to-reference-to-height run, with explicit quality gates.

Never promotes experimental calibration, labels a background plane as water,
or fills missing pixels to manufacture a measurement pass.
"""
from pathlib import Path
import json
import argparse
import cv2
import numpy as np
from reconstruction.opencv_dense import reconstruct_dense_stereo,DenseStereoPolicy
from reconstruction.height import height_from_plane

ROOT=Path('D:/stereo-wave-height-runs/HomeTank_006')


def plane_candidate(points,threshold=.005):
    rng=np.random.default_rng(42);best=np.zeros(len(points),bool)
    for _ in range(1000):
        p=points[rng.choice(len(points),3,replace=False)]
        normal=np.cross(p[1]-p[0],p[2]-p[0]);size=np.linalg.norm(normal)
        if size<1e-12:continue
        normal/=size;mask=abs((points-p[0])@normal)<=threshold
        if mask.sum()>best.sum():best=mask
    if best.sum()<12:raise ValueError('INSUFFICIENT_PLANE_SUPPORT')
    center=points[best].mean(axis=0);_,_,vt=np.linalg.svd(points[best]-center,full_matrices=False)
    n=vt[-1]
    if n[2]>0:n=-n
    return n,-float(n@center),best


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--raft-checkpoint',type=Path)
    parser.add_argument('--geometry',type=Path,default=ROOT/'rig_features_motion_candidate/result.json')
    parser.add_argument('--width',type=int)
    parser.add_argument('--num-disparities',type=int,default=1024)
    parser.add_argument('--correspondence-shift',type=int,default=0)
    parser.add_argument('--output-name')
    args=parser.parse_args();backend=None
    if args.raft_checkpoint:
        from reconstruction.learned_correspondence import TorchvisionRaftCorrespondence
        backend=TorchvisionRaftCorrespondence(args.raft_checkpoint,horizontal_crop_offset_px=args.correspondence_shift)
    out=ROOT/(args.output_name or ('surface_chain_raft' if backend else 'surface_chain_padded'));out.mkdir(exist_ok=True)
    cal=json.loads(args.geometry.read_text())
    # Candidate only: offset differences cancel a constant audio/video latency.
    # Constant latency has NOT been verified; retain this limitation in outputs.
    audio={k:json.loads((ROOT/'audio_timing'/f'{k}.json').read_text()) for k in ['calibration','wave']}
    audio_lag={k:float(np.median([w['right_minus_left_s'] for w in a['windows']])) for k,a in audio.items()}
    offset=cal['timing_offset_s']+audio_lag['wave']-audio_lag['calibration']
    width=args.width or (960 if backend else 1920);size=(width,round(width*2160/3840));scale=size[0]/3840
    K=[np.array(cal[f'K{i}']) for i in [0,1]];D=[np.array(cal[f'D{i}']) for i in [0,1]]
    for k in K:
        k[0,0]*=scale;k[1,1]*=scale;k[0,2]=(k[0,2]+.5)*scale-.5;k[1,2]=(k[1,2]+.5)*scale-.5
    R=np.array(cal['R']);T=np.array(cal['T_m']).reshape(3,1)
    r0,r1,p0,p1,q,*_=cv2.stereoRectify(K[0],D[0],K[1],D[1],size,R,T,flags=cv2.CALIB_ZERO_DISPARITY,alpha=-1)
    maps=[cv2.initUndistortRectifyMap(k,d,r,p,size,cv2.CV_32FC1) for k,d,r,p in zip(K,D,[r0,r1],[p0,p1])]
    # Conservative image-labelled water candidates, NOT independently verified
    # surface identity. Ruler and tank rim are outside these masks.
    masks=[]
    for side in [0,1]:
        m=np.zeros((size[1],size[0]),np.uint8)
        vertices=([(300,440),(860,440),(940,530),(180,530)] if side==0 else [(100,375),(800,375),(900,530),(130,530)])
        cv2.fillPoly(m,[(np.array(vertices)*size[0]/960).astype(np.int32)],1)
        masks.append(cv2.remap(m,*maps[side],cv2.INTER_NEAREST).astype(bool))
    frames=[];reference=None
    for time in [1.,2.,3.,10.]:
        images=[];pts=[]
        for side,role in [(0,'LEFT'),(1,'RIGHT')]:
            path=Path('experiments/real_video/HomeTank_006/videos/wave')/f'HomeTank_006_wave_cam{side}_{role}.mp4'
            cap=cv2.VideoCapture(str(path));cap.set(cv2.CAP_PROP_ORIENTATION_AUTO,0)
            cap.set(cv2.CAP_PROP_POS_MSEC,(time+side*offset)*1000);ok,f=cap.read();pts.append(cap.get(cv2.CAP_PROP_POS_MSEC)/1000);cap.release()
            if not ok:raise RuntimeError('decode failed')
            if side==0:f=cv2.rotate(f,cv2.ROTATE_180)
            images.append(cv2.resize(f,size,interpolation=cv2.INTER_AREA))
        result=reconstruct_dense_stereo(*images,K0=K[0],D0=D[0],K1=K[1],D1=D[1],
            R_right_from_left=R,T_right_from_left_m=T,policy=DenseStereoPolicy(num_disparities=args.num_disparities,pad_search_canvas=True),rectification_alpha=-1,disparity_backend=backend)
        valid=result.valid_mask&masks[0]
        yy,xx=np.indices(valid.shape);xr=np.rint(xx-np.nan_to_num(result.disparity_px)).astype(int)
        inside=(xr>=0)&(xr<size[0]);both=np.zeros(valid.shape,bool);both[inside]=masks[1][yy[inside],xr[inside]]
        left_count=int(valid.sum());valid &= both
        points=result.xyz_m[valid]
        record=dict(time_s=time,actual_pts_s=pts,point_count=len(points),candidate_left_roi_pixels=int(masks[0].sum()),
                    candidate_roi_coverage=float(valid.sum()/masks[0].sum()),left_roi_point_count=left_count,matcher=result.metadata)
        if backend:
            flow=backend.last_forward_flow
            fp=flow[:,masks[0]];finite=np.all(np.isfinite(fp),axis=0)
            record['ungated_model_flow_in_roi_px']={name:np.percentile(fp[i,finite],[5,50,95]).tolist() if finite.any() else None for i,name in enumerate(['horizontal','vertical'])}
            np.savez_compressed(out/f'frame_{int(time):02d}_correspondences.npz',forward=flow,backward=backend.last_backward_flow,
                                rectified_left=result.rectified_left,rectified_right=result.rectified_right,
                                left_roi=masks[0],right_roi=masks[1],P0=p0,P1=p1,R0=r0,K0=K[0],D0=D[0],K1=K[1],D1=D[1])
        preview=[]
        for im,mask in zip([result.rectified_left,result.rectified_right],masks):
            canvas=im.copy();cv2.drawContours(canvas,cv2.findContours(mask.astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[0],-1,(0,255,255),2)
            preview.append(cv2.resize(canvas,(960,540)))
        cv2.imwrite(str(out/f'frame_{int(time):02d}_candidate_roi.jpg'),np.hstack(preview))
        if len(points)<12:
            record['status']='INSUFFICIENT_SURFACE_OBSERVATIONS';frames.append(record);print(json.dumps(record),flush=True);continue
        normal,off,inliers=plane_candidate(points)
        residual=height_from_plane(points[inliers],normal,off)
        record.update(depth_percentiles_m=np.percentile(points[:,2],[0,5,50,95,100]).tolist(),
            candidate_plane=dict(normal=normal.tolist(),offset_m=off,inlier_count=int(inliers.sum()),inlier_ratio=float(inliers.mean()),
                                 rms_m=float(np.sqrt(np.mean(residual**2))),distance_gate_m=.005))
        if reference is None and time==1.:reference=(normal,off)
        if reference is not None:
            heights=height_from_plane(points,*reference)
            height_map=np.full(valid.shape,np.nan);height_map[valid]=heights
            record['raw_height_m']=dict(mean=float(heights.mean()),rms=float(np.sqrt(np.mean(heights**2))),p5_p50_p95=np.percentile(heights,[5,50,95]).tolist(),minimum=float(heights.min()),maximum=float(heights.max()))
            # Inlier-only figures are diagnostics, never replacements for raw errors.
            hi=height_from_plane(points[inliers],*reference)
            record['plane_inlier_height_diagnostic_m']=dict(mean=float(hi.mean()),rms=float(np.sqrt(np.mean(hi**2))))
            np.savez_compressed(out/f'frame_{int(time):02d}.npz',xyz_m=result.xyz_m,valid_mask=valid,height_m=height_map,
                canonical_left_u=(maps[0][0]+.5)/scale-.5,canonical_left_v=(maps[0][1]+.5)/scale-.5)
        record['status']='EXPERIMENTAL_POINT_HEIGHT_OUTPUT_NOT_PHYSICAL_PASS'
        cv2.imwrite(str(out/f'frame_{int(time):02d}_rectified_left.jpg'),result.rectified_left)
        frames.append(record);print(json.dumps(record),flush=True)
    report=dict(status='FULL_PIXEL_WATER_HEIGHT_NOT_VALIDATED',frames=frames,offset_candidate_s=offset,
        geometry_source=str(args.geometry),baseline_m=cal['baseline_m'],
        reference_source='first static candidate at 1s; plane identity NOT physically validated',
        height_formula='(n dot P + D)/norm(n)',height_unit='m',coordinate_system='rectified_left_camera',
        limitations=['geometry unapproved','frame synchronization unverified','candidate water region may include refracted background',
                     'plane inliers are only diagnostic; all supported raw heights retained',f'{size[0]}x{size[1]} evaluation, not full 4K',
                     'no completion of unsupported pixels; no ruler inputs'])
    (out/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__=='__main__':main()
