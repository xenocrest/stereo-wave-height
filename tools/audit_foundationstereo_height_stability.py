"""Audit frozen network predictions, without fitting or correcting any height.

Same-camera rays across frames are NOT fixed world XY. This is an image-domain
stability diagnostic, not physical wave validation or a confidence calibration.
"""
from pathlib import Path
import argparse
import hashlib
import json
import cv2
import numpy as np
from analyze_foundationstereo_trial import right_camera_points


def statistics(values):
    values = np.asarray(values)
    values = values[np.isfinite(values)]
    if not values.size:
        return dict(count=0, mean_mm=None, rms_mm=None, p95_abs_mm=None)
    return dict(count=int(values.size), mean_mm=float(values.mean()*1000),
                rms_mm=float(np.sqrt(np.mean(values**2))*1000),
                p95_abs_mm=float(np.percentile(abs(values),95)*1000))


def temporal_comparison(heights, masks, roi):
    """Use the intersection, never compare means from changing support."""
    common = roi & np.logical_and.reduce(masks)
    return {'common_pixels':int(common.sum()),
            'common_roi_ratio':float(common.sum()/roi.sum()),
            'relative_to_first':[statistics((h-heights[0])[common]) for h in heights]}


def audit(inputs, predictions, analysis, reference, prefix):
    sources = [inputs/'geometry.npz', reference/'summary.json']
    geometry = np.load(sources[0])
    ref = json.loads(sources[1].read_text(encoding='utf-8'))
    n = np.asarray(ref['normal']); c = ref['offset_m']
    records=[]; series={}
    for condition in (prefix,'wave'):
        heights=[]; masks=[]
        for index in (0,3,7):
            identity=f'{condition}_{index:06d}'
            paths=[predictions/f'{identity}.npy',predictions/f'{identity}_reverse.npy',
                   analysis/f'{identity}.npz',reference/f'{identity}.npz']
            sources.extend(paths)
            left=np.load(paths[0]); right=np.fliplr(np.load(paths[1])).copy()
            frame=np.load(paths[2]); h=np.load(paths[3])['height_m']
            yy,xx=np.indices(right.shape,dtype=np.float32)
            sampled=cv2.remap(left,xx+right,yy,cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_CONSTANT,borderValue=float('nan'))
            alternate=right_camera_points(sampled,geometry['Q'],geometry['R1'])
            alternate_h=(alternate@n+c)/np.linalg.norm(n)
            roi=frame['roi']
            supported=roi & frame['lr_consistent'] & np.isfinite(h)
            # h(d)=k/d+c for a fixed calibrated ray. This derivative is a
            # sensitivity, NOT an empirically calibrated uncertainty bound.
            sensitivity=abs((h-c/np.linalg.norm(n))/right)
            records.append({'id':identity,'lr_consistent_ratio':float(supported.sum()/roi.sum()),
                'height_lr_disagreement':statistics((alternate_h-h)[supported]),
                'height_sensitivity_per_1px':statistics(sensitivity[supported])})
            heights.append(h); masks.append(supported)
        series[condition]=temporal_comparison(heights,masks,roi)
    # Record content hashes; this script has no writes to input paths.
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    return {'classification':'HEIGHT_TREND_NOT_INDEPENDENTLY_VALIDATED',
        'demo_promotion_allowed':False,'reference_condition':prefix,
        'coordinate_scope':'FIXED_RECTIFIED_CAMERA_RAYS_NOT_FIXED_WORLD_XY',
        'reference_warning':'Reference window is not an independent water-surface truth.',
        'consistency_warning':'Two network directions are not independent physical truth.',
        'records':records,'temporal':series,'source_sha256':hashes}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('inputs','predictions','analysis','reference','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--reference-prefix',choices=('static','reference'),required=True)
    args=parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Refusing to overwrite audit results')
    result=audit(args.inputs,args.predictions,args.analysis,args.reference,args.reference_prefix)
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='source_sha256'},indent=2))


if __name__=='__main__':
    main()
