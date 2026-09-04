"""Local planar photometric Snell inversion, diagnostic only.

Known approximate water depth, frozen static geometry and image texture. Height
and two local slopes predict BOTH current views via ray tracing to the bottom.
No temporal feature tracks, no ruler, no WASS and no GUI promotion.
"""
from pathlib import Path
import json
import cv2
import numpy as np
from scipy.optimize import least_squares
from hometank006_refractive_height_probe import directions

ROOT=Path('D:/stereo-wave-height-runs/HomeTank_006')


def sample(array,uv):
    """Continuous bilinear intensity sampling, without remap's 1/32px table.

    Numerical differentiation of the photometric objective needs actual
    subpixel continuity. This samples intensity/background, never height.
    """
    uv=np.asarray(uv,float).reshape(-1,2)
    finite=np.isfinite(uv).all(1);safe=np.where(finite[:,None],uv,0)
    x=np.floor(safe[:,0]).astype(int);y=np.floor(safe[:,1]).astype(int)
    valid=finite&(x>=0)&(y>=0)&(x<array.shape[1]-1)&(y<array.shape[0]-1)
    xx=np.clip(x,0,array.shape[1]-2);yy=np.clip(y,0,array.shape[0]-2)
    a=safe[:,0]-x;b=safe[:,1]-y
    val=(1-a)*(1-b)*array[yy,xx]+a*(1-b)*array[yy,xx+1]+(1-a)*b*array[yy+1,xx]+a*b*array[yy+1,xx+1]
    return np.where(valid,val,np.nan)[:,None]


def project_static_bottom(bottom,C,K,n,c,depth,index=1.333):
    """Inverse planar refraction by scalar Snell solve, not pinhole bottom XYZ."""
    altitude=float(n@C+c)
    if altitude<=0 or depth<=0:raise ValueError('camera must be above interface; depth positive')
    foot=C-altitude*n
    delta=bottom+depth*n-foot
    rho=np.linalg.norm(delta,axis=1)
    direction=np.divide(delta,rho[:,None],out=np.zeros_like(delta),where=rho[:,None]>0)
    low=np.zeros(len(bottom));high=np.full(len(bottom),np.pi/2-1e-7)
    for _ in range(35):
        theta=(low+high)/2
        sinw=np.sin(theta)/index
        travel=altitude*np.tan(theta)+depth*sinw/np.sqrt(1-sinw*sinw)
        high=np.where(travel>rho,theta,high);low=np.where(travel<=rho,theta,low)
    entry=foot+direction*(altitude*np.tan((low+high)/2))[:,None]
    q=(entry-C)@K.T
    return q[:,:2]/q[:,2:3]


def refract_bottom(v,C,N,P,n,c,depth,index=1.333):
    """Air rays intersect local water plane through P; trace to fixed bottom."""
    nv=v@N;distance=((P-C)@N)/nv
    E=C+distance[:,None]*v
    eta=1/index;cosi=-nv
    w=eta*v+(eta*cosi-np.sqrt(1-eta*eta*(1-cosi*cosi)))[:,None]*N
    t=-(E@n+c+depth)/(w@n)
    B=E+t[:,None]*w
    valid=(nv<0)&(distance>0)&(t>0)&np.isfinite(B).all(1)
    return E,B,valid


def main():
    out=ROOT/'photometric_refraction_105mm';out.mkdir(exist_ok=True)
    ref=np.load(ROOT/'surface_chain_raft_centered/frame_01_correspondences.npz')
    model=json.loads((ROOT/'refraction_probe_depth_105mm/result.json').read_text())
    fit=model['frames'][0]['fit'];n=np.array(fit['normal']);c=fit['offset_m'];depth=fit['water_depth_m']
    Ks=[ref[f'P{i}'][:,:3] for i in [0,1]];Cs=[-np.linalg.inv(Ks[i])@ref[f'P{i}'][:,3] for i in [0,1]]
    refgray=[cv2.cvtColor(ref[f'rectified_{s}'],cv2.COLOR_BGR2GRAY).astype(np.float32)/255 for s in ['left','right']]
    tangent=np.array([1.,0,0]);tangent-=n*(n@tangent);tangent/=np.linalg.norm(tangent);tangent2=np.cross(n,tangent)
    y,x=np.indices(ref['left_roi'].shape)
    v=directions(np.column_stack([x.ravel(),y.ravel()]),Ks[0]);Q=Cs[0]-((Cs[0]@n+c)/(v@n))[:,None]*v
    qr=(Q-Cs[1])@Ks[1].T;uvr=qr[:,:2]/qr[:,2:3]
    common=(sample(ref['right_roi'].astype(np.float32),uvr)[:,0]>.999).reshape(x.shape)&ref['left_roi']
    common=cv2.erode(common.astype(np.uint8),np.ones((25,25),np.uint8)).astype(bool)
    yy,xx=np.where(common);select=np.random.default_rng(42).choice(len(xx),8,replace=False)
    centers=np.column_stack([xx[select],yy[select]])
    gx,gy=np.meshgrid(np.arange(-8,9),np.arange(-8,9));delta=np.column_stack([gx.ravel(),gy.ravel()])
    train=((gx+gy).ravel()%2==0);hold=~train
    frames=[]
    for time in [1,2,8,10]:
        if time in [1,2]:im=[ref[f'rectified_{s}'] if time==1 else np.load(ROOT/'surface_chain_raft_centered/frame_02_correspondences.npz')[f'rectified_{s}'] for s in ['left','right']]
        else:
            cal=json.loads((ROOT/'rig_features_metric/result.json').read_text());im=[]
            for i,side in enumerate(['left','right']):
                video=Path('experiments/real_video/HomeTank_006/videos/wave')/f'HomeTank_006_wave_cam{i}_{side.upper()}.mp4'
                cap=cv2.VideoCapture(str(video));cap.set(cv2.CAP_PROP_ORIENTATION_AUTO,0);cap.set(cv2.CAP_PROP_POS_MSEC,(time-i*.225)*1000)
                ok,f=cap.read();cap.release()
                if not ok:raise RuntimeError('video decode failed')
                if i==0:f=cv2.rotate(f,cv2.ROTATE_180)
                r=ref['R0'] if i==0 else ref['R0']@np.array(cal['R']).T
                maps=cv2.initUndistortRectifyMap(ref[f'K{i}'],ref[f'D{i}'],r,ref[f'P{i}'],(960,540),cv2.CV_32FC1)
                im.append(cv2.remap(cv2.resize(f,(960,540),interpolation=cv2.INTER_AREA),*maps,cv2.INTER_LINEAR))
        gray=[cv2.cvtColor(f,cv2.COLOR_BGR2GRAY).astype(np.float32)/255 for f in im]
        results=[]
        for center in centers:
            uv=center+delta;rays=directions(uv,Ks[0]);vc=directions(center[None],Ks[0])[0]
            observed_left=sample(gray[0],uv)[:,0]
            def evaluate(params,which):
                h=params[0]*depth
                N=n+params[1]*tangent+params[2]*tangent2;N/=np.linalg.norm(N)
                P=Cs[0]+((h-c-Cs[0]@n)/(vc@n))*vc
                E,B,valid0=refract_bottom(rays,Cs[0],N,P,n,c,depth)
                q=(E-Cs[1])@Ks[1].T;uv1=q[:,:2]/q[:,2:3]
                vr=E-Cs[1];vr/=np.linalg.norm(vr,axis=1)[:,None]
                _,B1,valid1=refract_bottom(vr,Cs[1],N,P,n,c,depth)
                ref_uv=[project_static_bottom(bg,Cs[i],Ks[i],n,c,depth) for i,bg in enumerate([B,B1])]
                preds=[sample(refgray[i],ref_uv[i])[:,0] for i in [0,1]]
                obs=[observed_left,sample(gray[1],uv1)[:,0]]
                # All image samples must remain in image-labelled bottom/water
                # domains. Ruler/wall texture must never drive height fitting.
                domains=(sample(ref['right_roi'].astype(float),uv1)[:,0]>.999)
                domains &= sample(ref['left_roi'].astype(float),ref_uv[0])[:,0]>.999
                domains &= sample(ref['right_roi'].astype(float),ref_uv[1])[:,0]>.999
                residual=[]
                for a,b in zip(preds,obs):
                    valid=valid0&valid1&domains&np.isfinite(a)&np.isfinite(b)
                    # Per-patch additive brightness nuisance, not depth correction.
                    dif=a-b;bias=np.mean(dif[valid&train]) if np.any(valid&train) else 0
                    residual.append(np.where(valid,dif-bias,1.)[which])
                return np.concatenate(residual)
            solutions=[]
            for h0 in [0.,-.2,.2]:
                sol=least_squares(lambda p:evaluate(p,train),[h0,0.,0.],bounds=([-.9,-1,-1],[.9,1,1]),
                    diff_step=.001,max_nfev=60,x_scale=[.2,.2,.2],loss='soft_l1',f_scale=.02)
                solutions.append(sol)
            best=min(solutions,key=lambda s:np.mean(evaluate(s.x,train)**2))
            singular=np.linalg.svd(best.jac,compute_uv=False)
            results.append(dict(center_uv=center.tolist(),height_m=float(best.x[0]*depth),slopes=best.x[1:].tolist(),
                train_intensity_rms=float(np.sqrt(np.mean(evaluate(best.x,train)**2))),
                heldout_intensity_rms=float(np.sqrt(np.mean(evaluate(best.x,hold)**2))),
                start_height_results_m=[float(s.x[0]*depth) for s in solutions],
                start_train_intensity_rms=[float(np.sqrt(np.mean(evaluate(s.x,train)**2))) for s in solutions],
                start_heldout_intensity_rms=[float(np.sqrt(np.mean(evaluate(s.x,hold)**2))) for s in solutions],
                solver_success=bool(best.success),singular_values=singular.tolist(),active_bounds=best.active_mask.tolist()))
        rec=dict(time_s=time,patches=results);frames.append(rec)
        print(json.dumps(rec),flush=True)
        (out/'masked_continuous_sampler_result.json').write_text(json.dumps(dict(status='PHOTOMETRIC_REFRACTION_DIAGNOSTIC_NOT_VALIDATED',
            water_depth_m=depth,reference_time_s=1,patch_size_px=17,seed=42,plane_model='local plane',
            input_geometry='unchanged unapproved candidate',synchronization='candidate, not verified',
            water_domain_gates=True,no_gui_promotion=True,frames=frames),indent=2),encoding='utf-8')


if __name__=='__main__':main()
