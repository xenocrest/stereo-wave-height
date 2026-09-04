"""Independent feature correspondence check of existing static refraction geometry.

No new video, WASS, calibration modification or water-height output.
SIFT descriptor matching does not impose pinhole epipolar geometry on bottom rays.
"""
from pathlib import Path
import argparse
import hashlib
import json
import cv2
import numpy as np
from hometank006_refraction_probe import ROOT, fit, describe, normal_from_parameters, bottom_intersections
from hometank006_photometric_refraction import project_static_bottom


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-resolution',action='store_true')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    out=args.output or ROOT/('static_sift_refraction_native' if args.native_resolution else 'static_sift_refraction')
    out.mkdir(parents=True,exist_ok=True)
    if (out/'result.json').exists():raise FileExistsError('Preserve previous results')
    records=[]; pooled=[[],[]]
    for time in [1,2,3]:
        source=ROOT/'surface_chain_raft_centered'/f'frame_{time:02d}_correspondences.npz'
        digest=hashlib.sha256(source.read_bytes()).hexdigest()
        with np.load(source) as data:
            sift=cv2.SIFT_create(contrastThreshold=.01 if args.native_resolution else .04)
            features=[]
            P=[data[f'P{i}'].copy() for i in [0,1]]
            for i,side in enumerate(['left','right']):
                image=data[f'rectified_{side}'];mask=data[f'{side}_roi'].astype(np.uint8)*255
                if args.native_resolution:
                    video=Path('experiments/real_video/HomeTank_006/videos/wave')/f'HomeTank_006_wave_cam{i}_{side.upper()}.mp4'
                    cap=cv2.VideoCapture(str(video));cap.set(cv2.CAP_PROP_ORIENTATION_AUTO,0)
                    cap.set(cv2.CAP_PROP_POS_MSEC,(time-i*.0775)*1000)
                    ok,image=cap.read();cap.release()
                    if not ok:raise RuntimeError('native frame decode failed')
                    if i==0:image=cv2.rotate(image,cv2.ROTATE_180)
                    scale=np.array([[4.,0,1.5],[0,4.,1.5],[0,0,1.]])
                    K=scale@data[f'K{i}'];P[i]=scale@P[i]
                    R=np.array(json.loads((ROOT/'rig_features_metric/result.json').read_text())['R'])
                    rotation=data['R0'] if i==0 else data['R0']@R.T
                    maps=cv2.initUndistortRectifyMap(K,data[f'D{i}'],rotation,P[i],(3840,2160),cv2.CV_32FC1)
                    image=cv2.remap(image,*maps,cv2.INTER_LINEAR)
                    mask=cv2.resize(mask,(3840,2160),interpolation=cv2.INTER_NEAREST)
                features.append(sift.detectAndCompute(cv2.cvtColor(image,cv2.COLOR_BGR2GRAY),mask))
        record=dict(time_s=time,source_sha256=digest,keypoint_counts=[len(f[0]) for f in features])
        if any(f[1] is None or len(f[1])<2 for f in features):
            record['status']='INSUFFICIENT_DESCRIPTORS';records.append(record);continue
        matcher=cv2.BFMatcher(cv2.NORM_L2)
        matches=[]
        for a,b in [(0,1),(1,0)]:
            matches.append({m.queryIdx:m.trainIdx for pair in matcher.knnMatch(features[a][1],features[b][1],k=2)
                            if len(pair)==2 for m,n in [pair] if m.distance<.75*n.distance})
        pairs=[(i,j) for i,j in matches[0].items() if matches[1].get(j)==i]
        record['mutual_ratio_matches']=len(pairs)
        uv=[np.array([features[k][0][pair[k]].pt for pair in pairs],float).reshape(-1,2) for k in [0,1]]
        for k in [0,1]:pooled[k].append(uv[k])
        np.savez_compressed(out/f'frame_{time:02d}_all_matches.npz',left_uv=uv[0],right_uv=uv[1])
        if len(pairs)<16:
            record['status']='INSUFFICIENT_MUTUAL_MATCHES';records.append(record);continue
        # Spatial split, not a quality/error-based selection of favorable points.
        block=128 if args.native_resolution else 32
        split=((uv[0][:,0]//block+uv[0][:,1]//block)%2).astype(bool)
        record.update(train_count=int(split.sum()),heldout_count=int((~split).sum()))
        if min(split.sum(),(~split).sum())<6:
            record['status']='INSUFFICIENT_SPATIAL_SPLIT';records.append(record);continue
        Ks=[p[:,:3] for p in P];centers=[-np.linalg.inv(K)@p[:,3] for K,p in zip(Ks,P)]
        rays=[]
        for pixels,K in zip(uv,Ks):
            v=np.column_stack([pixels,np.ones(len(pixels))])@np.linalg.inv(K).T
            rays.append(v/np.linalg.norm(v,axis=1)[:,None])
        solution=fit([v[split] for v in rays],centers,.105)
        result=describe(solution,[v[~split] for v in rays],centers,.105)
        n=normal_from_parameters(solution.x);c=solution.x[2]
        bottom=bottom_intersections(rays[0][~split],centers[0],n,c,.105)
        prediction=project_static_bottom(bottom,centers[1],Ks[1],n,c,.105)
        error=np.linalg.norm(prediction-uv[1][~split],axis=1)
        record.update(status='UNVALIDATED_FEATURE_GEOMETRY',fit=result,
                      heldout_pixel_error=dict(rms=float(np.sqrt(np.mean(error**2))),
                                              median=float(np.median(error)),p95=float(np.percentile(error,95))))
        np.savez_compressed(out/f'frame_{time:02d}_matches.npz',left_uv=uv[0],right_uv=uv[1],train_mask=split)
        assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
        records.append(record)
    pooled_result={'status':'INSUFFICIENT_SPATIAL_SUPPORT'}
    if pooled[0]:
        uv=[np.concatenate(v) for v in pooled]
        block=128 if args.native_resolution else 32
        split=((uv[0][:,0]//block+uv[0][:,1]//block)%2).astype(bool)
        pooled_result.update(train_count=int(split.sum()),heldout_count=int((~split).sum()))
        if min(split.sum(),(~split).sum())>=6:
            Ks=[p[:,:3] for p in P];centers=[-np.linalg.inv(K)@p[:,3] for K,p in zip(Ks,P)]
            rays=[]
            for pixels,K in zip(uv,Ks):
                v=np.column_stack([pixels,np.ones(len(pixels))])@np.linalg.inv(K).T
                rays.append(v/np.linalg.norm(v,axis=1)[:,None])
            solution=fit([v[split] for v in rays],centers,.105)
            pooled_result.update(status='UNVALIDATED_POOLED_STATIC_FIT',
                                 fit=describe(solution,[v[~split] for v in rays],centers,.105))
    result=dict(status='STATIC_FEATURE_REFRACTION_DIAGNOSTIC',water_depth_m=.105,
                depth_source='USER_REPORTED_APPROXIMATE',water_index=1.333,
                index_source='IDEAL_ASSUMPTION',bottom_parallel='USER_SPECIFIED_ASSUMPTION',
                matcher='OpenCV SIFT mutual Lowe ratio 0.75; no epipolar constraint',
                resolution=[3840,2160] if args.native_resolution else [960,540],
                contrast_threshold=.01 if args.native_resolution else .04,
                spatial_split='128 native / 32 diagnostic pixel alternating blocks',calibration_changed=False,
                water_height_produced=False,frames=records,pooled=pooled_result)
    (out/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
