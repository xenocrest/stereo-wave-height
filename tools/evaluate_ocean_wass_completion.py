"""Read-only real-sea WASS hold-out test of observation-anchored completion.

Uses a historical same-frame plane for spatial shape consistency only, NOT an
independent static datum or physical wave-height truth. Never invokes WASS.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from adapters.wass.output.xyzc import read_wass_xyzc
from reconstruction.ocean_surface import OceanSurfacePolicy, complete_water_surface
from reconstruction.dense_height_solver import DenseHeightPolicy
from surface_completion.dense_map import plane_basis


def main():
    started=time.perf_counter()
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workdir',type=Path,required=True)
    parser.add_argument('--baseline-file',type=Path,required=True)
    parser.add_argument('--roi',nargs=4,type=int,required=True,metavar=('X0','Y0','X1','Y1'))
    parser.add_argument('--stride',type=int,default=4)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--allow-unverified-legacy-projection',action='store_true',
                        help='Historical numeric reproduction only: P0cam is NOT a verified rectified image mapping')
    args=parser.parse_args()
    if not args.allow_unverified_legacy_projection:
        raise ValueError('LEGACY_P0CAM_PIXEL_DOMAIN_NOT_VERIFIED: use the corrected camera projection audit before reporting ROI coverage')
    if args.output.exists():raise FileExistsError('Use a new diagnostic directory')
    if args.stride<1:raise ValueError('positive image stride required')
    scale=float(args.baseline_file.read_text().strip())
    if not np.isfinite(scale) or scale<=0:raise ValueError('explicit positive source baseline needed')
    source=args.workdir/'mesh_cam.xyzC';sha=hashlib.sha256(source.read_bytes()).hexdigest()
    cloud=read_wass_xyzc(source).points_camera
    P=np.loadtxt(args.workdir/'P0cam.txt');projection=cloud@P[:,:3].T+P[:,3]
    uv=projection[:,:2]/projection[:,2:3]
    tree=cKDTree(uv)
    x0,y0,x1,y1=args.roi
    if x1<=x0 or y1<=y0:raise ValueError('empty ROI')
    u,v=np.meshgrid(np.arange(x0,x1,args.stride),np.arange(y0,y1,args.stride))
    query=np.column_stack((u.ravel(),v.ravel()));distance,nearest=tree.query(query)
    observed=(distance<=.75).reshape(u.shape)
    plane=np.loadtxt(args.workdir/'plane.txt');normal=-plane[:3]/np.linalg.norm(plane[:3]);offset=-plane[3]*scale/np.linalg.norm(plane[:3])
    height=((cloud[nearest]*scale)@normal+offset).reshape(u.shape)
    metric=P.copy();metric[:,3]*=scale;center=-np.linalg.solve(metric[:,:3],metric[:,3])
    rays=np.linalg.solve(metric[:,:3],np.column_stack((query,np.ones(len(query)))).T).T
    t=-(center@normal+offset)/(rays@normal)
    if not np.isfinite(t).all() or np.any(t<=0):raise ValueError('ROI has invalid water-plane rays')
    foot=center+t[:,None]*rays;xy=foot@plane_basis(normal).T
    roi=np.ones(u.shape,bool)
    policy=OceanSurfacePolicy(.3,DenseHeightPolicy(anchor_mode='hard'))
    full=complete_water_surface(height,observed,roi,roi,xy[:,0].reshape(u.shape),xy[:,1].reshape(u.shape),observation_subject='WATER_SURFACE',policy=policy)
    # Fixed spatial blocks, not error-selected pixels. All points in held-out
    # blocks are absent from support, including the query's nearest observation.
    rr,cc=np.indices(u.shape);test=observed&(((rr//8+cc//8)%7)==0)
    # No retained pixel may reuse an XYZ observation hidden for evaluation.
    hidden_xyz=np.unique(nearest.reshape(u.shape)[test])
    support=observed&~np.isin(nearest.reshape(u.shape),hidden_xyz)
    assert not np.intersect1d(nearest.reshape(u.shape)[support],hidden_xyz).size
    predicted=complete_water_surface(height,support,roi,roi,xy[:,0].reshape(u.shape),xy[:,1].reshape(u.shape),observation_subject='WATER_SURFACE',policy=policy)
    error=predicted.height_m[test]-height[test]
    record=dict(status='LEGACY_PIXEL_DOMAIN_UNVERIFIED_NUMERIC_REPRODUCTION_ONLY',
        source=str(source),source_sha256=sha,source_baseline_m=scale,source_baseline_file=str(args.baseline_file),
        scale_metrology_status='LEGACY_FILE_NOT_INDEPENDENTLY_VERIFIED',
        raw_wass_points=len(cloud),roi_rectified_xyxy=args.roi,stride_native_pixels=args.stride,
        evaluated_pixel_count=int(roi.sum()),raw_supported_ratio=float(observed.mean()),
        pixel_observation_association='nearest projected raw XYZ within 0.75 native pixel; not an exact dense stereo raster',
        observation_gate_native_px=.75,
        full_model_finite_ratio=float(np.isfinite(full.height_m).mean()),
        height_reference='historical same-frame official plane: shape only, NOT independent static reference',
        baseline_minimum_support_ratio=.3,minimum_support_source='EXPLICIT_DIAGNOSTIC_GATE_NOT_ACCEPTANCE_STANDARD',
        holdout=dict(rule='8x8 sampled-pixel blocks; (row_block+col_block)%7==0; exclude every shared hidden raw XYZ',count=int(test.sum()),
            remaining_support_count=int(support.sum()),
            rmse_m=float(np.sqrt(np.mean(error**2))),mae_m=float(np.mean(abs(error))),
            p95_absolute_error_m=float(np.percentile(abs(error),95)),max_absolute_error_m=float(np.max(abs(error))),
            correlation=float(np.corrcoef(height[test],predicted.height_m[test])[0,1])),
        elapsed_analysis_seconds=time.perf_counter()-started,
        wass_rerun=False,gui_promoted=False,not_full_original_resolution=args.stride!=1)
    args.output.mkdir(parents=True)
    np.savez_compressed(args.output/'height_maps.npz',u_px=u,v_px=v,observed_mask=observed,
        observed_height_m=np.where(observed,height,np.nan),completed_height_m=full.height_m,
        heldout_mask=test,heldout_completed_height_m=predicted.height_m,source_status=full.source_status)
    assert hashlib.sha256(source.read_bytes()).hexdigest()==sha
    (args.output/'result.json').write_text(json.dumps(record,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(record,indent=2))


if __name__=='__main__':main()
