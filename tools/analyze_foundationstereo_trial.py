"""Read-only geometry and left/right consistency audit of official disparity.

No learned confidence is claimed. A one-pixel left/right threshold is only a
diagnostic, not measurement acceptance. All raw predictions remain preserved.
"""
from pathlib import Path
import argparse
import json
import cv2
import numpy as np


def right_camera_points(disparity: np.ndarray, q: np.ndarray, r1: np.ndarray) -> np.ndarray:
    """Reproject right-view disparity for a zero-disparity horizontal pair.

    Q has identical principal points in both rectified cameras. Applied at
    right pixels it yields right-camera rectified XYZ; R1.T returns camera1.
    """
    if not np.isclose(q[3,3], 0):
        raise ValueError('This diagnostic requires zero-disparity rectification')
    xyz = cv2.reprojectImageTo3D(np.asarray(disparity,dtype=np.float32),q)
    return xyz @ r1


def signed_height(points: np.ndarray, plane: np.ndarray, baseline: float) -> np.ndarray:
    """Official WASS plane convention, positive height opposite its normal."""
    normal = plane[:3]
    if baseline<=0 or not np.isfinite(plane).all() or np.linalg.norm(normal)==0:
        raise ValueError('Invalid metric reference plane')
    return -(points@normal+plane[3]*baseline)/np.linalg.norm(normal)


def describe(values: np.ndarray) -> dict:
    values = np.asarray(values)
    values = values[np.isfinite(values)]
    if not len(values):
        return {'count':0,'mean_m':None,'rms_m':None,'p5_p50_p95_m':None,'range_m':None}
    return {'count':len(values),'mean_m':float(values.mean()),
            'rms_m':float(np.sqrt(np.mean(values**2))),
            'p5_p50_p95_m':np.percentile(values,[5,50,95]).tolist(),
            'range_m':[float(values.min()),float(values.max())]}


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,required=True)
    parser.add_argument('--predictions',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    geometry=np.load(args.inputs/'geometry.npz')
    records=[]
    pairs=json.loads((args.inputs/'pairs.json').read_text(encoding='utf-8'))['pairs']
    for pair in pairs:
        identity=pair['id']
        if identity!='official_sample' and not identity.endswith('_reverse'):
            dl=np.load(args.predictions/f'{identity}.npy')
            dr=np.fliplr(np.load(args.predictions/f'{identity}_reverse.npy')).copy()
            yy,xx=np.indices(dr.shape,dtype=np.float32)
            xl=xx+dr
            sampled=cv2.remap(dl,xl,yy,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=float('nan'))
            valid_left=cv2.remap(geometry['valid_left'].astype(np.uint8),xl,yy,cv2.INTER_NEAREST)>0
            visible=geometry['valid_right'] & valid_left & (xl>=0)&(xl<dr.shape[1]-1)
            positive=np.isfinite(dr)&(dr>0)&np.isfinite(sampled)&(sampled>0)
            roi=geometry['roi_right']
            consistency=np.abs(dr-sampled)
            passed=visible&positive&(consistency<=1)
            points=right_camera_points(dr,geometry['Q'],geometry['R1'])
            heights=signed_height(points,geometry['reference_plane'],float(geometry['baseline_m']))
            record={'id':identity,'roi_pixels':int(roi.sum()),
                'finite_positive_roi_ratio':float(positive[roi].mean()),
                'visible_roi_ratio':float(visible[roi].mean()),
                'lr_1px_roi_ratio':float(passed[roi].mean()),
                'lr_2px_roi_ratio':float((visible&positive&(consistency<=2))[roi].mean()),
                'height_raw_roi':describe(heights[roi&positive&visible]),
                'height_lr_consistent_roi':describe(heights[roi&passed]),
                'camera_depth_roi':describe(points[...,2][roi&passed])}
            np.savez_compressed(args.output/f'{identity}.npz',height_m=heights,xyz_camera1_m=points,
                roi=roi,visible=visible,lr_consistent=passed,lr_error_px=consistency)
            image=cv2.imread(str(args.inputs/f'{identity}_cam1.png'))
            image[roi&~passed]=(0,0,160)
            image[roi&passed]=(0,180,0)
            cv2.imwrite(str(args.output/f'{identity}_support.png'),image)
            records.append(record)
            print(json.dumps(record),flush=True)
    (args.output/'summary.json').write_text(json.dumps({
        'status':'DIAGNOSTIC_ONLY_NOT_WATER_HEIGHT_VALIDATED',
        'height_formula':'-(n dot X_cam1 + c*baseline_m)/norm(n)',
        'lr_gate_px':1,'roi_source':'predeclared canonical cam1 polygon, not fitted to support',
        'records':records},indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    main()
