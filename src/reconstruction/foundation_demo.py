"""Official dense stereo -> calibrated rays -> independent reference -> GUI.

Research estimates only. No WASS, ruler, hidden alternate time or gap filling.
The external verified model runtime remains separate from the desktop binary.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import cv2
import numpy as np
import yaml
from reconstruction.io import load_calibration, CalibrationParameters
from application.input_workflow import load_calibration_selection
from reconstruction.reference_frame import (canonical_calibration_identity, roi_identity,
    video_pair_identity, save_reference_artifact, load_reference_artifact)
from validation.diagnostics import fit_plane_orthogonal
from process_utils import hidden_process_kwargs


def identity(calibration, rotations, size):
    return {'geometry':canonical_calibration_identity(calibration),
            'rotations':rotations,'size':list(size),'model':'C_FAST_FOUNDATIONSTEREO_7aee8594',
            'rectification':{'alpha':1.,'zero_disparity':True,'size':[960,540]}}


def compatible(reference, expected, pair, roi):
    demo_bound = str(reference.get('demo_calibration_compatibility_status','')).startswith('GEOMETRY_IDENTITY_DIFFERENT__REFERENCE_GATE_BYPASSED_FOR_DEMO')
    if reference.get('foundation_identity')!=expected and not demo_bound:
        raise ValueError('Model reference calibration/orientation identity mismatch; set a new reference')
    if reference.get('video_pair_id')!=pair or reference.get('roi_id')!=roi_identity(roi):
        raise ValueError('Model reference video/ROI mismatch; set a new reference')


def read_frame(path, timestamp, rotation):
    cap=cv2.VideoCapture(str(path)); cap.set(cv2.CAP_PROP_ORIENTATION_AUTO,0)
    cap.set(cv2.CAP_PROP_POS_MSEC,timestamp*1000)
    ok,image=cap.read(); actual=cap.get(cv2.CAP_PROP_POS_MSEC)/1000; cap.release()
    if not ok:raise ValueError('Cannot decode selected video timestamp')
    if rotation not in (0,90,180,270):raise ValueError('Unsupported canonical rotation')
    if rotation:image=cv2.rotate(image,{90:cv2.ROTATE_90_CLOCKWISE,180:cv2.ROTATE_180,270:cv2.ROTATE_90_COUNTERCLOCKWISE}[rotation])
    return image,actual

def write_png(path, image):
    ok, encoded = cv2.imencode('.png', image)
    if not ok: raise RuntimeError(f'Cannot encode image: {path}')
    Path(path).write_bytes(encoded.tobytes())


def run(request):
    start=time.perf_counter(); runtime=request['foundation_runtime']
    out=Path(request['output']['directory']);out.mkdir(parents=True,exist_ok=False)
    for folder in ('selected_pair','rectified','dense_height','report','reconstruction/pixel_xyz','reconstruction/pointcloud'):
        (out/folder).mkdir(parents=True,exist_ok=True)
    input_=request['input']; roi=request['dense_height']['water_roi']
    if roi.get('coordinate_system')!='canonical_cam1' or roi.get('type')!='polygon':
        raise ValueError('Explicit canonical cam1 polygon ROI required')
    calibration_path=Path(request['calibration']['source'])
    raw, calibration_path, _mode = load_calibration_selection(calibration_path)
    if 'camera_left' in raw:
        l,r,s=raw['camera_left'],raw['camera_right'],raw['stereo']
        cal=CalibrationParameters(*[np.asarray(v,dtype=float) for v in
            (l['K'],l['D'],r['K'],r['D'],s['R'],s['T_m'])],False,calibration_path)
        if not np.isclose(cal.baseline_m,float(s['baseline_m']),rtol=1e-10):
            raise ValueError('Declared package baseline differs from translation')
    else:
        cal=load_calibration(calibration_path,quality_mode='diagnostic_allow_failed_gate')
    rotations=input_['canonical_rotation_deg']; sync=request['synchronization']
    target=float(input_['target_time_s']); right_target=float(sync['a'])*target+float(sync['b_s'])
    left,lt=read_frame(input_['left_video'],target,rotations['left'])
    right,rt=read_frame(input_['right_video'],right_target,rotations['right'])
    if left.shape!=right.shape:raise ValueError('Unequal canonical image sizes')
    size=(right.shape[1],right.shape[0])
    if list(size)!=raw.get('image_size_wh',[1920,1080]):raise ValueError('Calibration image size mismatch')
    ident=identity(raw,rotations,size); pair=video_pair_identity(input_['left_video'],input_['right_video'])
    reference=None
    if request['solve_mode']=='measurement':
        reference=load_reference_artifact(request['processing']['reference_artifact_file'])
        compatible(reference,ident,pair,roi)
    elif request['solve_mode']!='reference':raise ValueError('Explicit reference or measurement mode required')
    r0,r1,p0,p1,q,_,_=cv2.stereoRectify(cal.k0,cal.d0,cal.k1,cal.d1,size,cal.r,cal.t_m.reshape(3,1),
        flags=cv2.CALIB_ZERO_DISPARITY,alpha=1,newImageSize=(960,540))
    if p1[0,3]>=0 or abs(p1[1,3])>1e-8 or abs(q[3,3])>1e-8:
        raise ValueError('Model requires positive horizontal stereo disparity')
    maps=[cv2.initUndistortRectifyMap(k,d,r,p,(960,540),cv2.CV_32FC1)
          for k,d,r,p in ((cal.k0,cal.d0,r0,p0),(cal.k1,cal.d1,r1,p1))]
    validmaps=[(mx>=0)&(mx<size[0]-1)&(my>=0)&(my<size[1]-1) for mx,my in maps]
    paths=[]
    for index,image in enumerate((left,right)):
        name=('left','right')[index]
        write_png(out/'selected_pair'/f'{name}.png',image)
        rect=cv2.remap(image,*maps[index],cv2.INTER_LINEAR)
        path=out/'rectified'/f'{name}.png';write_png(path,rect);paths.append(str(path))
        write_png(out/'rectified'/f'{name}_flip.png',cv2.flip(rect,1))
    pairs={'pairs':[{'id':'frame','left':paths[0],'right':paths[1]},
        {'id':'frame_reverse','left':str(out/'rectified/right_flip.png'),'right':str(out/'rectified/left_flip.png')}]}
    (out/'pairs.json').write_text(json.dumps(pairs),encoding='utf-8')
    env=os.environ.copy();env['TORCHDYNAMO_DISABLE']='1'
    cmd=[runtime['python'],str(Path(runtime['project_root'])/'tools/run_official_fast_foundationstereo.py'),
        '--source',runtime['source'],'--weights',runtime['weights'],'--pairs',str(out/'pairs.json'),'--output',str(out/'predictions')]
    completed=subprocess.run(cmd,env=env,capture_output=True,timeout=240,**hidden_process_kwargs(enabled=True))
    (out/'model.log').write_bytes(completed.stdout+b'\n'+completed.stderr)
    if completed.returncode:
        detail=(completed.stdout+completed.stderr).decode('utf-8','replace')[-1800:]
        raise RuntimeError(f'Official model failed ({completed.returncode}): {detail}')
    dl=np.load(out/'predictions/frame.npy'); dr=np.fliplr(np.load(out/'predictions/frame_reverse.npy')).copy()
    yy,xx=np.indices(dr.shape,dtype=np.float32)
    sample=cv2.remap(dl,xx+dr,yy,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=float('nan'))
    visible=validmaps[1] & (cv2.remap(validmaps[0].astype(np.uint8),xx+dr,yy,cv2.INTER_NEAREST)>0)
    visible &= np.isfinite(dr)&(dr>0)&np.isfinite(sample)&(sample>0)&(xx+dr<959)&(xx+dr>=0)
    lr=visible&(abs(dr-sample)<=1)
    native_roi=np.zeros(right.shape[:2],np.uint8)
    polygon=np.asarray(roi['points'],np.int32)
    if np.any(polygon<0) or np.any(polygon[:,0]>=size[0]) or np.any(polygon[:,1]>=size[1]):raise ValueError('ROI outside image')
    cv2.fillPoly(native_roi,[polygon],1)
    roi_rect=cv2.remap(native_roi,*maps[1],cv2.INTER_NEAREST)>0
    xyz=cv2.reprojectImageTo3D(dr,q)@r1
    if reference is None:
        support=xyz[roi_rect&lr]
        if len(support)<12:raise ValueError('Reference has fewer than 12 consistent points inside selected ROI')
        fit=fit_plane_orthogonal(support); sign=1 if fit.offset>0 else -1
        normal=fit.normal*sign;offset=float(fit.offset*sign)
        reference={'status':'REFERENCE_PLANE_READY','reference_id':f'foundation_{time.time_ns()}',
            'source':'USER_SELECTED_OFFICIAL_MODEL_REFERENCE__UNVALIDATED',
            'foundation_identity':ident,'calibration_id':ident['geometry'],'video_pair_id':pair,
            'roi_id':roi_identity(roi),'roi':roi,'actual_timestamp_s':rt,'requested_timestamp_s':target,
            'plane':{'normal':normal.tolist(),'offset_m':offset},'plane_rms_m':float(fit.residual_rmse),
            'support_count':len(support),'xyz_point_count':int(visible.sum()),'unit':'m',
            'warning':'Reference plane is a model estimate; surface identity and physical accuracy unverified'}
    normal=np.asarray(reference['plane']['normal']);offset=reference['plane']['offset_m']
    save_reference_artifact(reference,out/'reference.yaml')
    ny,nx=np.indices(right.shape[:2],dtype=np.float32)
    uv=np.stack((nx,ny),axis=-1)
    rectuv=cv2.undistortPoints(uv.reshape(-1,1,2),cal.k1,cal.d1,R=r1,P=p1).reshape(*right.shape[:2],2)
    mx,my=rectuv[...,0].copy(),rectuv[...,1].copy()
    disp=cv2.remap(dr,mx,my,cv2.INTER_NEAREST,borderMode=cv2.BORDER_CONSTANT,borderValue=float('nan'))
    points=cv2.perspectiveTransform(np.dstack((mx,my,disp)).reshape(-1,1,3),q).reshape(*right.shape[:2],3)@r1
    valid=(native_roi>0)&(cv2.remap(visible.astype(np.uint8),mx,my,cv2.INTER_NEAREST)>0)&np.isfinite(points).all(axis=2)
    h=(points@normal+offset)/np.linalg.norm(normal);h[~valid]=np.nan
    consistent=valid&(cv2.remap(lr.astype(np.uint8),mx,my,cv2.INTER_NEAREST)>0)
    if not valid.any():raise ValueError('Selected ROI has no positive in-FOV model estimates')
    status=np.where(valid,3,0).astype(np.uint8) # all model estimates, never OBSERVED
    np.savez_compressed(out/'dense_height/dense_height.npz',height_m=h,source_status=status,
        confidence=np.where(valid,1,0).astype(np.uint8),water_roi_mask=native_roi>0,
        valid_mask=valid,lr_consistent=consistent)
    np.savez_compressed(out/'reconstruction/pixel_xyz/000000_pixel_xyz.npz',
        xyz_m=points[valid],u_px=nx[valid],v_px=ny[valid])
    np.savetxt(out/'reconstruction/pointcloud/000000.xyz',points[valid],fmt='%.7f')
    values=h[valid];lo,hi=np.percentile(values,[2,98]);scaled=np.zeros(h.shape,np.uint8)
    scaled[valid]=(np.clip((values-lo)/max(hi-lo,1e-9),0,1)*255).astype(np.uint8)
    color=cv2.applyColorMap(scaled,cv2.COLORMAP_TURBO);color[~valid]=0
    cv2.imwrite(str(out/'dense_height/dense_height.png'),color)
    cv2.imwrite(str(out/'dense_height/dense_height_status.png'),status*80)
    overlay=right.copy();overlay[valid]=(.55*right[valid]+.45*color[valid]).astype(np.uint8)
    cv2.imwrite(str(out/'dense_height/height_overlay.png'),overlay)
    result={'status':'SINGLE_FRAME_DENSE_HEIGHT_COMPLETED','quality_status':'MODEL_ESTIMATED_NOT_PHYSICALLY_VALIDATED',
        'stereo_backend':'OFFICIAL_FAST_FOUNDATIONSTEREO','requested_time_s':target,
        'left_timestamp_s':lt,'right_timestamp_s':rt,'pair_time_error_ms':(rt-(float(sync['a'])*lt+float(sync['b_s'])))*1000,
        'xyz_point_count':int(valid.sum()),'reference_id':reference['reference_id'],'reference_metadata':reference,
        'output_paths':{'reference_artifact':'reference.yaml'},'wass_seconds':0,'total_seconds':time.perf_counter()-start,
        'height_statistics':{'minimum':float(values.min()),'maximum':float(values.max()),'mean':float(values.mean())},
        'dense_height':{'roi_pixel_count':int(native_roi.sum()),'valid_height_count':int(valid.sum()),
            'consistent_height_count':int(consistent.sum()),'coverage_ratio':float(valid.sum()/native_roi.sum()),
            'height_statistics_mm':{'minimum':float(values.min()*1000),'maximum':float(values.max()*1000),'median':float(np.median(values)*1000)},
            'artifact_paths':{'npz':'dense_height/dense_height.npz','height_png':'dense_height/dense_height.png','status_png':'dense_height/dense_height_status.png'}},
        'warning':'All finite values are model estimates. Missing pixels remain unsupported. No independent physical accuracy or trend claim.',
        'calibration_sha256':hashlib.sha256(calibration_path.read_bytes()).hexdigest()}
    (out/'single_frame_result.json').write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    (out/'report/single_frame_report.md').write_text('# 官方稠密模型演示结果\n\n模型估算，未独立验证物理精度。无效像素未补造。\n\n'+json.dumps(result['dense_height'],indent=2,ensure_ascii=False),encoding='utf-8')
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--config',required=True);args=parser.parse_args()
    run(yaml.safe_load(Path(args.config).read_text(encoding='utf-8')))


if __name__=='__main__':main()
