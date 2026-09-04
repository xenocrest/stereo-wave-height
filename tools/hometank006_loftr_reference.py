"""Official LoFTR 2-D matches for static bottom refraction; never predicts height.

Optional isolated environment: torch 2.7.1, kornia 0.8.1. No GUI dependency.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
import torch
from kornia.feature import LoFTR
from kornia.feature.loftr.loftr import default_cfg
from hometank006_refraction_probe import ROOT, fit, describe


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    checkpoint_hash=hashlib.sha256(args.checkpoint.read_bytes()).hexdigest()
    if checkpoint_hash!='be9ff88b323ec27889114719f668ae41aff7034b56a4c4acbd46b8b180b87ed3':
        raise ValueError('Unexpected indoor_new checkpoint identity')
    if (args.output/'result.json').exists():raise FileExistsError('Do not overwrite diagnostics')
    args.output.mkdir(parents=True,exist_ok=True)
    torch.set_num_threads(4)
    config=copy.deepcopy(default_cfg);config['coarse']['temp_bug_fix']=True
    model=LoFTR(pretrained=None,config=config).eval()
    state=torch.load(args.checkpoint,map_location='cpu',weights_only=True)
    model.load_state_dict(state['state_dict'])
    records=[]
    for time in [1,2,3]:
        path=ROOT/'surface_chain_raft_centered'/f'frame_{time:02d}_correspondences.npz'
        with np.load(path) as data:
            inputs={};transforms=[];masks=[]
            for i,side in enumerate(['left','right']):
                mask=data[f'{side}_roi'];yy,xx=np.where(mask)
                x0,y0,x1,y1=int(xx.min()),int(yy.min()),int(xx.max()+1),int(yy.max()+1)
                image=cv2.cvtColor(data[f'rectified_{side}'][y0:y1,x0:x1],cv2.COLOR_BGR2GRAY)
                # Image-coordinate transform only. No height/surface interpolation.
                size=(640,max(64,int(round(image.shape[0]*640/image.shape[1]/8))*8))
                transforms.append((x0,y0,(x1-x0)/size[0],(y1-y0)/size[1]))
                inputs[f'image{i}']=torch.from_numpy(cv2.resize(image,size).astype(np.float32)/255)[None,None]
                inputs[f'mask{i}']=torch.from_numpy(cv2.resize(mask[y0:y1,x0:x1].astype(np.uint8),size,interpolation=cv2.INTER_NEAREST).astype(np.float32))[None]
                masks.append(mask)
            with torch.inference_mode():result=model(inputs)
            uv=[]
            for i,(x0,y0,sx,sy) in enumerate(transforms):
                pts=result[f'keypoints{i}'].cpu().numpy()
                uv.append((pts+.5)*[sx,sy]-.5+[x0,y0])
            confidence=result['confidence'].cpu().numpy()
            valid=np.ones(len(confidence),bool)
            for pts,mask in zip(uv,masks):
                xy=np.rint(pts).astype(int)
                inside=(xy[:,0]>=0)&(xy[:,0]<mask.shape[1])&(xy[:,1]>=0)&(xy[:,1]<mask.shape[0])
                valid &= inside
                valid[inside] &= mask[xy[inside,1],xy[inside,0]]
            uv=[p[valid] for p in uv];confidence=confidence[valid]
            record=dict(time_s=time,match_count=len(confidence),status='INSUFFICIENT_MATCHES')
            np.savez_compressed(args.output/f'frame_{time:02d}_matches.npz',left_uv=uv[0],right_uv=uv[1],confidence=confidence)
            if len(confidence)>=16:
                split=((uv[0][:,0]//32+uv[0][:,1]//32)%2).astype(bool)
                record.update(train_count=int(split.sum()),heldout_count=int((~split).sum()))
                if min(split.sum(),(~split).sum())>=6:
                    rays=[];centers=[]
                    for i in [0,1]:
                        P=data[f'P{i}'];inv=np.linalg.inv(P[:,:3]);v=np.column_stack([uv[i],np.ones(len(uv[i]))])@inv.T
                        rays.append(v/np.linalg.norm(v,axis=1)[:,None]);centers.append(-inv@P[:,3])
                    solution=fit([r[split] for r in rays],centers,.105)
                    record.update(status='UNVALIDATED_REFRACTION_FIT',fit=describe(solution,[r[~split] for r in rays],centers,.105))
            records.append(record);print(json.dumps(record),flush=True)
    (args.output/'result.json').write_text(json.dumps(dict(model='Kornia 0.8.1 official LoFTR indoor_new',
        checkpoint_sha256=checkpoint_hash,
        depth_m=.105,depth_source='USER_REPORTED_APPROXIMATE',index=1.333,
        index_source='IDEAL_ASSUMPTION',calibration_modified=False,water_height_produced=False,
        frames=records),indent=2,allow_nan=False),encoding='utf-8')


if __name__=='__main__':main()
