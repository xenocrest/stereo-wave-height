"""Independent reference-window analysis, reusing project plane/height math.

Does not overwrite the frozen WASS reference or inference outputs. No wave
point enters the reference plane. This is NOT independent physical accuracy.
"""
from pathlib import Path
import argparse
import json
import cv2
import numpy as np
import yaml
from reconstruction.height import height_from_plane
from validation.diagnostics import fit_plane_orthogonal
from analyze_foundationstereo_trial import describe


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--analysis',type=Path,required=True)
    parser.add_argument('--inputs',type=Path,required=True)
    parser.add_argument('--reference-prefix',choices=('static','reference'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--canonical-config',type=Path,help='Optional native pixel export configuration')
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    references=[np.load(args.analysis/f'{args.reference_prefix}_{i:06d}.npz') for i in (0,3,7)]
    common=np.logical_and.reduce([frame['roi']&frame['lr_consistent'] for frame in references])
    points=np.concatenate([frame['xyz_camera1_m'][common] for frame in references])
    fit=fit_plane_orthogonal(points)
    # Camera origin positive: height points toward the camera above the plane.
    sign=1 if fit.offset>0 else -1
    normal,offset=fit.normal*sign,fit.offset*sign
    geometry=np.load(args.inputs/'geometry.npz')
    canonical_maps=None
    if args.canonical_config:
        config=json.loads(args.canonical_config.read_text(encoding='utf-8'))
        calibration=yaml.safe_load(Path(config['calibration']).read_text(encoding='utf-8'))
        camera=calibration['camera_right'] if 'camera_right' in calibration else calibration['mono_cam1']
        yy,xx=np.indices((1080,1920),dtype=np.float32)
        uv=np.stack((xx,yy),axis=-1)
        rect=cv2.undistortPoints(uv.reshape(-1,1,2),np.asarray(camera['K'],dtype=float),
            np.asarray(camera['D'],dtype=float),R=geometry['R1'],P=geometry['P1']).reshape(1080,1920,2)
        canonical_maps=(rect[...,0].copy(),rect[...,1].copy())
        canonical_roi=np.zeros((1080,1920),dtype=np.uint8)
        cv2.fillPoly(canonical_roi,[np.asarray(config['candidate_roi_cam1_px'],dtype=np.int32)],1)
    old=geometry['reference_plane'][:3]
    angle=float(np.degrees(np.arccos(np.clip(abs(old@normal)/np.linalg.norm(old),-1,1))))
    records=[]
    for condition in (args.reference_prefix,'wave'):
        for index in (0,3,7):
            identity=f'{condition}_{index:06d}'
            frame=np.load(args.analysis/f'{identity}.npz')
            xyz=frame['xyz_camera1_m']
            h=height_from_plane(xyz.reshape(-1,3),normal,offset).reshape(xyz.shape[:2])
            raw=frame['roi']&frame['visible']&np.isfinite(h)
            consistent=raw&frame['lr_consistent']
            np.savez_compressed(args.output/f'{identity}.npz',height_m=h,roi=frame['roi'],
                visible=frame['visible'],lr_consistent=frame['lr_consistent'])
            record={'id':identity,'raw_roi':describe(h[raw]),
                    'consistent_roi':describe(h[consistent]),
                    'consistent_coverage':float(consistent.sum()/frame['roi'].sum())}
            if canonical_maps is not None:
                # Upstream recommends nearest-neighbor disparity resampling.
                # Use the actual canonical query ray, not a stretched heat map.
                xyz_rect=xyz@geometry['R1'].T
                disparity=(geometry['P0'][0,0]*float(geometry['baseline_m'])/xyz_rect[...,2]).astype(np.float32)
                sampled=cv2.remap(disparity,*canonical_maps,cv2.INTER_NEAREST,
                                 borderMode=cv2.BORDER_CONSTANT,borderValue=float('nan'))
                uvdisp=np.stack((*canonical_maps,sampled),axis=-1)
                query_xyz=cv2.perspectiveTransform(uvdisp.reshape(-1,1,3),geometry['Q']).reshape(1080,1920,3)@geometry['R1']
                canonical_h=(query_xyz@normal+offset)/np.linalg.norm(normal)
                visible=cv2.remap(frame['visible'].astype(np.uint8),*canonical_maps,cv2.INTER_NEAREST)>0
                supported=cv2.remap(frame['lr_consistent'].astype(np.uint8),*canonical_maps,cv2.INTER_NEAREST)>0
                selected=(canonical_roi>0)&visible&np.isfinite(sampled)&(sampled>0)
                canonical_h[~selected]=np.nan
                np.savez_compressed(args.output/f'{identity}_canonical.npz',height_m=canonical_h,
                    roi=canonical_roi>0,estimated=selected,lr_consistent=selected&supported)
                record['canonical_roi_pixels']=int(canonical_roi.sum())
                record['canonical_estimated_ratio']=float(selected.sum()/canonical_roi.sum())
                record['canonical_consistent_ratio']=float((selected&supported).sum()/canonical_roi.sum())
                record['canonical_height']=describe(canonical_h[selected])
                record['native_model_resolution']=[960,540]
                record['canonical_export_resolution']=[1920,1080]
            records.append(record)
            print(json.dumps(record),flush=True)
    result={'status':'SAME_MODEL_REFERENCE_DIAGNOSTIC_NOT_PHYSICALLY_VALIDATED',
        'reference_sources':[f'{args.reference_prefix}_{i:06d}' for i in (0,3,7)],
        'wave_points_used_for_reference':0,'common_reference_pixels':int(common.sum()),
        'reference_point_count':len(points),'normal':normal.tolist(),'offset_m':offset,
        'reference_fit_rms_m':fit.residual_rmse,'old_plane_normal_difference_deg':angle,
        'warning':'Planarity does not establish that matched features lie on water; no true-height/trend reference available.',
        'records':records}
    (args.output/'summary.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    main()
