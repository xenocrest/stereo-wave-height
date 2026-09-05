"""Check the same official model on the official WASSfast sea sample.

Uses published calibration, baseline and mean-plane transform unchanged.
No model fitting, parameter search, or camera calibration is performed.
"""
from pathlib import Path
import argparse
import json
import cv2
import numpy as np
from scipy.io import loadmat
from analyze_foundationstereo_trial import right_camera_points, signed_height, describe


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample',type=Path,required=True)
    parser.add_argument('--inputs',type=Path,required=True)
    parser.add_argument('--predictions',type=Path)
    parser.add_argument('--reference-nc',type=Path,help='Optional official WASSfast comparison, NOT truth')
    args=parser.parse_args()
    if args.predictions:
        g=np.load(args.inputs/'geometry.npz')
        records=[]
        for index in (0,25,49):
            identity=f'sea_{index:06d}'
            dl=np.load(args.predictions/f'{identity}.npy')
            dr=np.fliplr(np.load(args.predictions/f'{identity}_reverse.npy')).copy()
            yy,xx=np.indices(dr.shape,dtype=np.float32)
            xl=xx+dr
            sampled=cv2.remap(dl,xl,yy,cv2.INTER_LINEAR,borderValue=float('nan'))
            visible=g['valid_right']&(cv2.remap(g['valid_left'].astype(np.uint8),xl,yy,cv2.INTER_NEAREST)>0)
            gate=visible&(dr>0)&(sampled>0)&(np.abs(dr-sampled)<=1)
            points=right_camera_points(dr,g['Q'],g['R1'])
            height=signed_height(points,g['reference_plane'],float(g['baseline_m']))
            roi=g['roi']
            record={'id':identity,'roi_pixels':int(roi.sum()),
                'finite_height_roi_ratio':float(np.isfinite(height[roi]).mean()),
                'lr_consistent_roi_ratio':float(gate[roi].mean()),
                'all_height_roi':describe(height[roi&visible]),
                'consistent_height_roi':describe(height[roi&gate])}
            if args.reference_nc:
                from netCDF4 import Dataset
                m=loadmat(args.sample/'config256.mat')
                plane_points=points@m['Rpl'].T+m['Tpl'].reshape(1,1,3)*float(g['baseline_m'])
                mx=((plane_points[...,0]-m['xmin'].item())/m['x_spacing'].item()).astype(np.float32)
                my=((plane_points[...,1]-m['ymin'].item())/m['y_spacing'].item()).astype(np.float32)
                with Dataset(args.reference_nc) as nc:
                    if nc['Z'].units!='millimeter': raise ValueError('Unknown reference units')
                    reference=np.ma.filled(nc['Z'][index],np.nan).astype(np.float32)/1000
                expected=cv2.remap(reference,mx,my,cv2.INTER_LINEAR,
                    borderMode=cv2.BORDER_CONSTANT,borderValue=float('nan'))
                comparison=roi&gate&np.isfinite(expected)
                error=height[comparison]-expected[comparison]
                record['versus_wassfast_NOT_truth']={'count':int(comparison.sum()),
                    'mae_m':float(np.mean(np.abs(error))),
                    'rmse_m':float(np.sqrt(np.mean(error**2))),
                    'correlation':float(np.corrcoef(height[comparison],expected[comparison])[0,1])}
            records.append(record)
        report={'status':'OFFICIAL_SEA_GEOMETRY_CHECK_NOT_INDEPENDENT_ACCURACY','records':records}
        (args.predictions/'sea_geometry.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(report,indent=2))
        return
    args.inputs.mkdir(parents=True,exist_ok=False)
    m=loadmat(args.sample/'config256.mat')
    def xml(name):
        fs=cv2.FileStorage(str(args.sample/'config'/name),cv2.FILE_STORAGE_READ)
        value=fs.getFirstTopLevelNode().mat()
        fs.release()
        return value
    k=[xml(f'intrinsics_0{i}.xml') for i in (0,1)]
    d=[xml(f'distortion_0{i}.xml') for i in (0,1)]
    baseline=float(m['CAM_BASELINE'].item())
    rotation=xml('ext_R.xml')
    translation=xml('ext_T.xml')
    if not np.isclose(np.linalg.norm(translation),1,atol=1e-6):
        raise ValueError('Official sample extrinsic scale differs from documented unit baseline')
    size=(960,804)
    r0,r1,p0,p1,q,_,_=cv2.stereoRectify(k[0],d[0],k[1],d[1],(2456,2058),rotation,
        translation*baseline,flags=cv2.CALIB_ZERO_DISPARITY,alpha=1,newImageSize=size)
    maps=[cv2.initUndistortRectifyMap(k[i],d[i],r,p,size,cv2.CV_32FC1)
          for i,(r,p) in enumerate(((r0,p0),(r1,p1)))]
    valid=[(mx>=0)&(mx<2455)&(my>=0)&(my<2057) for mx,my in maps]
    corners=np.array([[x,y,0] for x,y in [(m['xmin'].item(),m['ymin'].item()),
        (m['xmax'].item(),m['ymin'].item()),(m['xmax'].item(),m['ymax'].item()),
        (m['xmin'].item(),m['ymax'].item())]])
    camera=(corners/baseline-m['Tpl'].reshape(1,3))@m['Rpl']
    projected=(camera@r1.T)@p1[:,:3].T
    polygon=np.rint(projected[:,:2]/projected[:,2:3]).astype(np.int32)
    roi=np.zeros(size[::-1],dtype=np.uint8)
    cv2.fillPoly(roi,[polygon],1)
    pairs=[]
    for index in (0,25,49):
        identity=f'sea_{index:06d}'
        paths=[]
        for side in (0,1):
            source=sorted((args.sample/'input'/f'cam{side}').glob(f'{index:06d}_*'))
            if len(source)!=1: raise ValueError('Sample frame pairing ambiguous')
            image=cv2.imread(str(source[0]))
            if image.shape[:2]!=(2058,2456): raise ValueError('Sample resolution mismatch')
            image=cv2.remap(image,*maps[side],cv2.INTER_LINEAR)
            path=args.inputs/f'{identity}_{side}.png'
            cv2.imwrite(str(path),image)
            cv2.imwrite(str(args.inputs/f'{identity}_{side}_flip.png'),cv2.flip(image,1))
            paths.append(str(path))
        pairs.extend([{'id':identity,'left':paths[0],'right':paths[1]},
            {'id':identity+'_reverse','left':str(args.inputs/f'{identity}_1_flip.png'),
             'right':str(args.inputs/f'{identity}_0_flip.png')}])
    np.savez_compressed(args.inputs/'geometry.npz',R1=r1,Q=q,baseline_m=baseline,
        reference_plane=np.r_[m['Rpl'][2],m['Tpl'][2,0]],valid_left=valid[0],valid_right=valid[1],roi=roi>0)
    (args.inputs/'pairs.json').write_text(json.dumps({'pairs':pairs},indent=2)+'\n',encoding='utf-8')
    print('Prepared official sample',baseline,p0,polygon,flush=True)


if __name__=='__main__': main()
