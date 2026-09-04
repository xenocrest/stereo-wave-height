"""Integrable continuous-surface photometric hypothesis, frozen geometry.

Unlike independent patch heights, one quadratic and its analytic derivatives
generate all surface positions/normals in both views. This is a model estimate;
fit and held-out images decide consistency, not a preferred height appearance.
"""
from pathlib import Path
import argparse
import json
import cv2
import numpy as np
from scipy.optimize import least_squares
from reconstruction.refractive_surface import QuadraticWaterSurface
from hometank006_refractive_height_probe import directions
from hometank006_photometric_refraction import sample,project_static_bottom

ROOT=Path('D:/stereo-wave-height-runs/HomeTank_006')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--times',type=int,nargs='+',default=[1,2,8,10])
    parser.add_argument('--output',type=Path,default=ROOT/'continuous_refraction_105mm')
    parser.add_argument('--right-offset-s',type=float,default=-.225)
    parser.add_argument('--static-fit-frame',type=int,choices=[1,2,3],default=1)
    parser.add_argument('--sample-count',type=int,default=500)
    parser.add_argument('--stable-jacobian',action='store_true')
    parser.add_argument('--image-scales',type=float,nargs='+',default=[2.,0.])
    args=parser.parse_args()
    if any(t<1 for t in args.times):raise ValueError('times must be positive seconds')
    if args.sample_count<6:raise ValueError('at least six samples required')
    if not np.isfinite(args.right_offset_s):raise ValueError('time offset must be finite')
    if any(not np.isfinite(s) or s<0 for s in args.image_scales) or args.image_scales[-1]!=0:
        raise ValueError('image scales must be nonnegative and end with unfiltered images')
    out=args.output
    if (out/'result.json').exists():raise FileExistsError('Preserve previous diagnostics; select a new output directory')
    out.mkdir(parents=True,exist_ok=True)
    ref=np.load(ROOT/'surface_chain_raft_centered/frame_01_correspondences.npz')
    fit=json.loads((ROOT/'refraction_probe_depth_105mm/result.json').read_text())['frames'][args.static_fit_frame-1]['fit']
    cal=json.loads((ROOT/'rig_features_metric/result.json').read_text())
    n=np.array(fit['normal']);c=fit['offset_m'];depth=fit['water_depth_m']
    K=[ref[f'P{i}'][:,:3] for i in [0,1]];C=[-np.linalg.inv(K[i])@ref[f'P{i}'][:,3] for i in [0,1]]
    y,x=np.indices(ref['left_roi'].shape);alluv=np.column_stack([x.ravel(),y.ravel()])
    rays=directions(alluv,K[0]);flat=C[0]-((C[0]@n+c)/(rays@n))[:,None]*rays
    qr=(flat-C[1])@K[1].T
    common=ref['left_roi'].ravel()&(sample(ref['right_roi'].astype(float),qr[:,:2]/qr[:,2:3])[:,0]>.999)
    # Same physical common-domain rule as previous experiment, not error-based ROI selection.
    fitmask=cv2.erode(common.reshape(x.shape).astype(np.uint8),np.ones((17,17),np.uint8)).ravel()>0
    origin=flat[common].mean(0);e1=np.array([1.,0,0]);e1-=n*(e1@n);e1/=np.linalg.norm(e1);e2=np.cross(n,e1)
    scale=float(max(np.ptp((flat[common]-origin)@e1),np.ptp((flat[common]-origin)@e2))/2)
    make=lambda a:QuadraticWaterSurface(n,c,origin,e1,e2,scale,np.array(a,float))
    split=(x.ravel()//16+y.ravel()//16)%2
    rng=np.random.default_rng(42)
    ids=[rng.choice(np.flatnonzero(fitmask&(split==i)),min(args.sample_count,int((fitmask&(split==i)).sum())),replace=False) for i in [0,1]]
    frames=[]
    for time in args.times:
        images=[];pts=[]
        for i,side in enumerate(['left','right']):
            if time in [1,2]:
                a=ref if time==1 else np.load(ROOT/'surface_chain_raft_centered/frame_02_correspondences.npz')
                im=a[f'rectified_{side}'];pts.append(None)
            else:
                video=Path('experiments/real_video/HomeTank_006/videos/wave')/f'HomeTank_006_wave_cam{i}_{side.upper()}.mp4'
                cap=cv2.VideoCapture(str(video));cap.set(cv2.CAP_PROP_ORIENTATION_AUTO,0);cap.set(cv2.CAP_PROP_POS_MSEC,(time+i*args.right_offset_s)*1000)
                ok,f=cap.read();pts.append(cap.get(cv2.CAP_PROP_POS_MSEC)/1000);cap.release()
                if not ok:raise RuntimeError('decode failed')
                if i==0:f=cv2.rotate(f,cv2.ROTATE_180)
                rot=ref['R0'] if i==0 else ref['R0']@np.array(cal['R']).T
                maps=cv2.initUndistortRectifyMap(ref[f'K{i}'],ref[f'D{i}'],rot,ref[f'P{i}'],(960,540),cv2.CV_32FC1)
                im=cv2.remap(cv2.resize(f,(960,540),interpolation=cv2.INTER_AREA),*maps,cv2.INTER_LINEAR)
            images.append(cv2.cvtColor(im,cv2.COLOR_BGR2GRAY).astype(float)/255)
        reference=[cv2.cvtColor(ref[f'rectified_{s}'],cv2.COLOR_BGR2GRAY).astype(float)/255 for s in ['left','right']]
        def rendering(a,index):
            E,N,H,valid=make(a).intersect(C[0],rays[index]);bs=[]
            air=[rays[index],E-C[1]];air[1]/=np.linalg.norm(air[1],axis=1)[:,None]
            for i in [0,1]:
                cosi=-np.sum(air[i]*N,axis=1);eta=1/1.333
                w=eta*air[i]+(eta*cosi-np.sqrt(1-eta*eta*(1-cosi*cosi)))[:,None]*N
                tb=-(E@n+c+depth)/(w@n);bs.append(E+tb[:,None]*w)
                valid &= (cosi>0)&(tb>0)
            uv0=alluv[index];p=(E-C[1])@K[1].T;uv1=p[:,:2]/p[:,2:3]
            bg_uv=[project_static_bottom(bs[i],C[i],K[i],n,c,depth) for i in [0,1]]
            valid &= sample(ref['right_roi'].astype(float),uv1)[:,0]>.999
            for i,side in enumerate(['left','right']):valid &= sample(ref[f'{side}_roi'].astype(float),bg_uv[i])[:,0]>.999
            return [uv0,uv1],bg_uv,valid,H
        def residual(a,index,refs,curs,bias=None):
            uv,bguv,valid,_=rendering(a,index);res=[];biases=[]
            for i in [0,1]:
                pred=sample(refs[i],bguv[i])[:,0];obs=sample(curs[i],uv[i])[:,0]
                good=valid&np.isfinite(pred)&np.isfinite(obs)
                b=float(np.mean((pred-obs)[good])) if bias is None and good.any() else (bias[i] if bias is not None else 0.)
                res.append(np.where(good,pred-obs-b,1.));biases.append(b)
            return np.concatenate(res),biases
        candidates=[]
        for initial in [0.,-.5,.5]:
            a=np.zeros(6);a[0]=initial
            for sigma in args.image_scales:
                blur=lambda im:cv2.GaussianBlur(im,(0,0),sigma) if sigma else im
                refs=[blur(im) for im in reference];curs=[blur(im) for im in images]
                objective=lambda p:residual(p,ids[0],refs,curs)[0]
                def absolute_jacobian(p):
                    # Fixed dimensionless central step avoids near-zero coefficient
                    # steps falling below inverse-projection numerical resolution.
                    step=1e-4
                    return np.column_stack([(objective(p+step*np.eye(6)[j])-objective(p-step*np.eye(6)[j]))/(2*step) for j in range(6)])
                solution=least_squares(objective,a,
                    jac=absolute_jacobian if args.stable_jacobian else '2-point',
                    bounds=([-depth*.9/scale]+[-1.]*5,[depth*.9/scale]+[1.]*5),
                    max_nfev=65,loss='soft_l1',f_scale=.02,diff_step=.001,x_scale='jac')
                a=solution.x
            train,bias=residual(a,ids[0],reference,images)
            test,_=residual(a,ids[1],reference,images,bias)
            _,_,valid,H=rendering(a,np.flatnonzero(common))
            candidates.append(dict(initial=initial,coefficients=a.tolist(),
                train_rms=float(np.sqrt(np.mean(train*train))),heldout_rms=float(np.sqrt(np.mean(test*test))),
                valid_domain_ratio=float(valid.mean()),height_p5_p50_p95_m=np.nanpercentile(H,[5,50,95]).tolist(),
                solver_success=bool(solution.success),active_bounds=solution.active_mask.tolist()))
        best=min(candidates,key=lambda r:r['train_rms'])
        idx=np.flatnonzero(common);_,_,valid,H=rendering(best['coefficients'],idx)
        height=np.full(len(alluv),np.nan);height[idx[valid]]=H[valid]
        # All finite values are explicitly UNVALIDATED_MODEL_ESTIMATES, not observed heights.
        np.savez_compressed(out/f'frame_{time:02d}_unvalidated_model.npz',height_m=height.reshape(x.shape),
            finite_model_mask=np.isfinite(height).reshape(x.shape),reference_common_mask=common.reshape(x.shape),
            coefficients=best['coefficients'],origin_m=origin,e1=e1,e2=e2,normal=n,scale_m=scale)
        record=dict(time_s=time,actual_pts_s=pts,best=best,all_starts=candidates);frames.append(record)
        print(json.dumps(record),flush=True)
        (out/'result.json').write_text(json.dumps(dict(status='CONTINUOUS_REFRACTION_MODEL_NOT_VALIDATED',
            model='integrable quadratic in physical coordinates',scale_m=scale,water_depth_m=depth,
            right_offset_s=args.right_offset_s,static_fit_frame=args.static_fit_frame,
            jacobian='central_absolute_1e-4' if args.stable_jacobian else 'relative_2point',
            optimization_image_scales=args.image_scales,
            train_count=len(ids[0]),heldout_count=len(ids[1]),split='16px spatial checkerboard blocks',
            common_domain_pixels=int(common.sum()),source_geometry='unchanged unapproved candidate',
            not_independent_physical_accuracy=True,no_gui_promotion=True,frames=frames),indent=2),encoding='utf-8')


if __name__=='__main__':main()
