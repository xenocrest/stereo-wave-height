"""Isolated fixed-input WASS batch diagnosis, never a calibration/height approval.

Uses existing candidate calibration and runtime. No autocalibration, tuning,
completion or background-to-water relabelling. All planned frames count.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import time

import cv2
import numpy as np
import yaml
from scipy.spatial import cKDTree
from adapters.wass.input.opencv_xml import write_wass_coarse_fixed_calibration
from adapters.wass.output.xyzc import read_wass_xyzc
from adapters.wass.runtime import load_runtime_binding
from adapters.wass.rectification_policy import RectificationPolicy
from process_utils import hidden_process_kwargs
from validation.wass_support_extent import read_precluster_depth


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def parse_counts(log):
    patterns={'filtered_points':r'([\d]+) filtered points',
              'valid_triangulated_points':r'(\d+) valid points found',
              'largest_component_points':r'biggest component:\s*\d+\s+size:\s*(\d+)'}
    return {key:(int(m[-1]) if (m:=re.findall(pattern,log,re.I)) else None)
            for key,pattern in patterns.items()}


def project_input_right(points, geometry, swapped):
    """Dense triangulation XYZ is in computational-left, not rectified, axes.

    With WASS auto-swap this is input RIGHT; otherwise transform with fixed
    R/T (T normalized by WASS). Then apply RIGHT K and original distortion.
    Do not treat P0cam.txt as a rectified projection matrix.
    """
    points=np.asarray(points,float)
    if not swapped:
        t=np.asarray(geometry['T_m'],float).reshape(3)
        points=points@np.asarray(geometry['R'],float).T+t/np.linalg.norm(t)
    uv=cv2.projectPoints(points,np.zeros(3),np.zeros(3),
        np.asarray(geometry['K1'],float),np.asarray(geometry['D1'],float))[0].reshape(-1,2)
    return uv[np.isfinite(uv).all(1)&(points[:,2]>0)]


def execute(runtime,stage,args,folder,timeout):
    command=runtime.command(stage,[str(a) for a in args]);start=time.perf_counter()
    record={'argv':command,'stage':stage}
    try:
        proc=subprocess.run(command,cwd=runtime.working_directory or folder,
            env=runtime.process_environment(),capture_output=True,timeout=timeout,
            **hidden_process_kwargs())
        record.update(returncode=proc.returncode,status='PASS' if proc.returncode==0 else 'FAIL')
        stdout,stderr=proc.stdout,proc.stderr
    except subprocess.TimeoutExpired as error:
        record.update(returncode=None,status='TIMEOUT');stdout,stderr=error.stdout or b'',error.stderr or b''
    for kind,data in [('stdout',stdout),('stderr',stderr)]:
        (folder/f'{stage}.{kind}.log').write_bytes(data)
    record['seconds']=time.perf_counter()-start
    (folder/f'{stage}.command.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    return record


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--config',type=Path,required=True)
    args=ap.parse_args();cfg=yaml.safe_load(args.config.read_text(encoding='utf-8'))
    output=Path(cfg['output']);output.mkdir(parents=True,exist_ok=False)
    geometry_path=Path(cfg['geometry_file']);g=json.loads(geometry_path.read_text())
    runtime=load_runtime_binding(cfg['runtime_binding']);configdir=output/'config'
    write_wass_coarse_fixed_calibration(configdir,intrinsic_00=g['K0'],intrinsic_01=g['K1'],
        distortion_00=g['D0'],distortion_01=g['D1'],rotation_01=g['R'],translation_01_m=g['T_m'],
        coarse_fixed_calibration_allowed=True,metrological_validity=False,
        purpose='ALGORITHM_CLOSURE_VALIDATION_ONLY',source=str(geometry_path))
    for name in ('matcher_config.txt','stereo_config.txt'):
        shutil.copy2(Path(cfg['existing_wass_config'])/name,configdir/name)
    frozen={str(p):sha(p) for p in [geometry_path,*configdir.iterdir(),args.config,
            Path(cfg['runtime_binding']),*[Path(runtime.executables[k]) for k in ('prepare','match','stereo')],
            Path(cfg['left_video']),Path(cfg['right_video'])] if p.is_file()}
    (output/'frozen_plan.json').write_text(json.dumps({'config':cfg,'hashes':frozen},indent=2),encoding='utf-8')
    w,h=cfg['image_size'];roi=np.zeros((h,w),np.uint8)
    cv2.fillPoly(roi,[np.asarray(cfg['water_roi']['points'],np.int32)],1)
    denominator=int(roi.sum());yy,xx=np.nonzero(roi);query=np.column_stack((xx,yy))
    report={'status':'ISOLATED_CANDIDATE_GEOMETRY_NOT_WATER_HEIGHT_VALIDATION',
        'geometry_approved':False,'synchronization_verified':False,
        'planned_frames':len(cfg['left_times_s']),'roi_pixels':denominator,
        'roi_full_image_ratio':denominator/(w*h),'roi':cfg['water_roi'],
        'coverage_denominator':'entire predeclared canonical RIGHT polygon; never shrunk to support',
        'observation_subject':'UNKNOWN_OR_REFRACTED_BOTTOM_NOT_VERIFIED_WATER',
        'frames':[],'height_computed':False,'completion_run':False}
    for index,left_time in enumerate(cfg['left_times_s']):
        folder=output/f'frame_{index:06d}';folder.mkdir();pts=[]
        rec={'frame_id':f'{index:06d}','left_target_s':left_time,'stages':[]}
        report['frames'].append(rec)
        for side,video in enumerate((cfg['left_video'],cfg['right_video'])):
            target=left_time+side*cfg['right_minus_left_s']
            cap=cv2.VideoCapture(video);cap.set(cv2.CAP_PROP_ORIENTATION_AUTO,0)
            cap.set(cv2.CAP_PROP_POS_MSEC,target*1000);ok,frame=cap.read()
            pts.append(cap.get(cv2.CAP_PROP_POS_MSEC)/1000);cap.release()
            if not ok:raise RuntimeError(f'video decode failed {side} {target}')
            if cfg['rotation_deg'][side]==180:frame=cv2.rotate(frame,cv2.ROTATE_180)
            elif cfg['rotation_deg'][side]!=0:raise ValueError('unsupported explicit rotation')
            if frame.shape[:2]!=(h,w):raise ValueError('native image size mismatch')
            cv2.imwrite(str(folder/f'cam{side}.png'),frame)
            if side==1:
                preview=frame.copy();cv2.polylines(preview,[np.asarray(cfg['water_roi']['points'],np.int32)],True,(0,255,255),8)
                cv2.imwrite(str(folder/'fixed_roi.jpg'),cv2.resize(preview,(960,540)))
        rec['decoded_pts_s']=pts
        rec['pair_residual_s']=pts[1]-pts[0]-cfg['right_minus_left_s']
        work=folder/'work'
        for stage,arguments in [('prepare',['--workdir',work,'--calibdir',configdir,'--c0',folder/'cam0.png','--c1',folder/'cam1.png']),
                                ('match',[configdir/'matcher_config.txt',work]),
                                ('stereo',[configdir/'stereo_config.txt',work])]:
            if stage=='stereo':
                for name in ('ext_R.xml','ext_T.xml'):shutil.copy2(configdir/name,work/name)
            stage_result=execute(runtime,stage,arguments,folder,cfg['stage_timeout_s']);rec['stages'].append(stage_result)
            if stage_result['status']!='PASS':rec['failed_stage']=stage;break
        log=(work/'wass_stereo_log.txt').read_text(errors='replace') if (work/'wass_stereo_log.txt').exists() else ''
        rec.update(parse_counts(log))
        rec['log_tail']=log.splitlines()[-12:]
        rec['completed_xyz']=False;rec['raw_roi_support_ratio']=None
        if (work/'mesh_cam.xyzC').exists():
            points=read_wass_xyzc(work/'mesh_cam.xyzC').points_camera
            uv=project_input_right(points,g,'auto-swapping left-right images' in log)
            distances=cKDTree(uv).query(query)[0] if len(uv) else np.full(len(query),np.inf)
            supported=distances<=cfg['observation_gate_px']
            rec.update(completed_xyz=True,final_xyz_count=len(points),raw_roi_support_ratio=float(supported.mean()))
            mask=np.zeros((h,w),np.uint8);mask[yy[supported],xx[supported]]=255
            cv2.imwrite(str(folder/'raw_roi_support.png'),mask)
        (output/'result.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
        print(json.dumps({k:v for k,v in rec.items() if k not in ['stages','log_tail']}),flush=True)
    report['completed_xyz_frames']=sum(f['completed_xyz'] for f in report['frames'])
    report['pipeline_success_ratio']=report['completed_xyz_frames']/report['planned_frames']
    report['frozen_inputs_unchanged']=all(sha(p)==digest for p,digest in frozen.items())
    (output/'result.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')


def replay_stereo(source, output, alpha, roi_mask=False, frame_ids=None):
    """One isolated policy change, reuse exact prepared inputs and fixed pose."""
    RectificationPolicy(alpha=alpha)
    plan=json.loads((source/'frozen_plan.json').read_text());cfg=plan['config']
    previous=json.loads((source/'result.json').read_text())
    if len(previous['frames'])!=previous['planned_frames']:
        raise ValueError('baseline batch must finish before controlled replay')
    if frame_ids is not None:
        previous['frames']=[f for f in previous['frames'] if f['frame_id'] in frame_ids]
        if len(previous['frames'])!=len(set(frame_ids)):raise ValueError('unknown frame IDs')
        previous['planned_frames']=len(previous['frames'])
    output.mkdir(parents=True,exist_ok=False);configdir=output/'config'
    shutil.copytree(source/'config',configdir)
    path=configdir/'stereo_config.txt';text=path.read_text()
    text,count=re.subn(r'^RECTIFICATION_ALPHA=.*$',f'RECTIFICATION_ALPHA={alpha}',text,flags=re.M)
    if count!=1:raise ValueError('expected exactly one alpha configuration')
    path.write_text(text,encoding='utf-8')
    g=json.loads(Path(cfg['geometry_file']).read_text());runtime=load_runtime_binding(cfg['runtime_binding'])
    w,h=cfg['image_size'];roi=np.zeros((h,w),np.uint8)
    cv2.fillPoly(roi,[np.asarray(cfg['water_roi']['points'],np.int32)],1)
    if roi_mask:
        # Native triangulate() reads LEFT_MASK_IMAGE after auto-swap, in
        # undistorted computational-left image coordinates (pi), not rectified.
        if not all('auto-swapping left-right images' in (source/f"frame_{f['frame_id']}"/'work'/'wass_stereo_log.txt').read_text()
                   for f in previous['frames']):raise ValueError('mask needs verified computational-left=input-right convention')
        mx,my=cv2.initUndistortRectifyMap(np.asarray(g['K1']),np.asarray(g['D1']),np.eye(3),np.asarray(g['K1']),(w,h),cv2.CV_32FC1)
        undistorted_mask=cv2.remap(roi,mx,my,cv2.INTER_NEAREST,borderMode=cv2.BORDER_CONSTANT)*255
        with path.open('a',encoding='utf-8') as stream:stream.write('\nLEFT_MASK_IMAGE="water_roi_mask.png"\n')
    yy,xx=np.nonzero(roi);query=np.column_stack((xx,yy))
    report={k:v for k,v in previous.items() if k not in ['frames','completed_xyz_frames','pipeline_success_ratio']}
    report.update(frames=[],controlled_change={'RECTIFICATION_ALPHA':alpha},baseline_source=str(source),frozen_inputs_unchanged=None)
    if roi_mask:report['controlled_change']['LEFT_MASK_IMAGE']='fixed canonical RIGHT ROI mapped through undistortion'
    (output/'frozen_plan.json').write_text(json.dumps({'baseline_plan_sha256':sha(source/'frozen_plan.json'),
        'controlled_changes':report['controlled_change'],'selected_frame_ids':[f['frame_id'] for f in previous['frames']],
        'derived_stereo_config_sha256':sha(path)},indent=2))
    for old in previous['frames']:
        frame=old['frame_id'];folder=output/f'frame_{frame}';work=folder/'work';work.mkdir(parents=True)
        oldwork=source/f'frame_{frame}'/'work'
        copied=[]
        for name in ['intrinsics_00000000.xml','intrinsics_00000001.xml','undistorted/00000000.png','undistorted/00000001.png']:
            dst=work/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(oldwork/name,dst)
            copied.append({'path':name,'source_sha256':sha(oldwork/name),'copy_sha256':sha(dst)})
        for name in ['ext_R.xml','ext_T.xml']:shutil.copy2(configdir/name,work/name)
        if roi_mask:cv2.imwrite(str(work/'water_roi_mask.png'),undistorted_mask)
        rec={k:old[k] for k in ['frame_id','left_target_s','decoded_pts_s','pair_residual_s']}
        rec.update(prepared_inputs_reused=copied,match_reused=True,
                   roi_mask_sha256=sha(work/'water_roi_mask.png') if roi_mask else None)
        rec['stages']=[execute(runtime,'stereo',[path,work],folder,cfg['stage_timeout_s'])]
        log=(work/'wass_stereo_log.txt').read_text(errors='replace') if (work/'wass_stereo_log.txt').exists() else ''
        rec.update(parse_counts(log));rec['log_tail']=log.splitlines()[-12:]
        rec['completed_xyz']=False;rec['raw_roi_support_ratio']=None
        if rec['stages'][0]['status']!='PASS':rec['failed_stage']='stereo'
        if (work/'mesh_cam.xyzC').exists():
            points=read_wass_xyzc(work/'mesh_cam.xyzC').points_camera
            uv=project_input_right(points,g,'auto-swapping left-right images' in log)
            d=cKDTree(uv).query(query)[0] if len(uv) else np.full(len(query),np.inf)
            supported=d<=cfg['observation_gate_px']
            mask=np.zeros((h,w),np.uint8);mask[yy[supported],xx[supported]]=255
            cv2.imwrite(str(folder/'raw_roi_support.png'),mask)
            rec.update(completed_xyz=True,final_xyz_count=len(points),raw_roi_support_ratio=float(supported.mean()))
        report['frames'].append(rec)
        report['completed_xyz_frames']=sum(f['completed_xyz'] for f in report['frames'])
        report['pipeline_success_ratio']=report['completed_xyz_frames']/report['planned_frames']
        (output/'result.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
        print(json.dumps({k:v for k,v in rec.items() if k not in ['stages','log_tail','prepared_inputs_reused']}),flush=True)
    report['frozen_inputs_unchanged']=all(sha(p)==digest for p,digest in plan['hashes'].items())
    (output/'result.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')


def summarize(source, replay, destination):
    """Read final outputs again, including optional native observability files."""
    base=json.loads((source/'result.json').read_text());run=json.loads((replay/'result.json').read_text())
    if len(run['frames'])!=run['planned_frames']:raise ValueError('wait for every planned frame')
    cfg=json.loads((source/'frozen_plan.json').read_text())['config']
    g=json.loads(Path(cfg['geometry_file']).read_text());rows=[]
    for frame in run['frames']:
        row={k:frame.get(k) for k in ['frame_id','left_target_s','decoded_pts_s','pair_residual_s','completed_xyz','final_xyz_count','raw_roi_support_ratio']}
        work=replay/f"frame_{frame['frame_id']}"/'work'
        log=(work/'wass_stereo_log.txt').read_text(errors='replace') if (work/'wass_stereo_log.txt').exists() else ''
        row.update(parse_counts(log));row['stereo_status']=frame['stages'][0]['status']
        row['stereo_seconds']=frame['stages'][0]['seconds'];row['returncode']=frame['stages'][0]['returncode']
        if (work/'precluster_depth.bin').exists():
            artifact=read_precluster_depth(work/'precluster_depth.bin')
            row['precluster_raster_shape_hw']=list(artifact.depth.shape)
            row['precluster_valid_fraction_of_stereo_crop']=float(artifact.valid.mean())
            row['candidate_camera_depth_percentiles_m']=np.percentile(artifact.depth[artifact.valid],[0,5,50,95,100]).tolist()
            row['candidate_camera_depth_percentiles_m']=[z*g['baseline_m'] for z in row['candidate_camera_depth_percentiles_m']]
            assert int(artifact.valid.sum())==row['valid_triangulated_points']
        if (work/'component_sizes.csv').exists():
            sizes=np.atleast_2d(np.loadtxt(work/'component_sizes.csv',delimiter=',',skiprows=1,dtype=np.int64))[:,1]
            row['component_count']=len(sizes);row['top5_component_sizes']=sorted(sizes.tolist(),reverse=True)[:5]
            row['largest_component_retained_fraction']=int(sizes.max())/row['valid_triangulated_points']
            row['zgap_metadata']=(work/'zgap_threshold.txt').read_text().splitlines()
        if frame['completed_xyz']:
            p=read_wass_xyzc(work/'mesh_cam.xyzC').points_camera;uv=project_input_right(p,g,'auto-swapping left-right images' in log)
            image=cv2.imread(str(source/f"frame_{frame['frame_id']}"/'cam1.png'))
            small=cv2.resize(image,(960,540));pix=np.rint(uv/4).astype(np.int64)
            ok=(pix[:,0]>=0)&(pix[:,0]<960)&(pix[:,1]>=0)&(pix[:,1]<540)
            small[pix[ok,1],pix[ok,0]]=(0,255,0)
            cv2.polylines(small,[(np.asarray(cfg['water_roi']['points'])/4).astype(np.int32)],True,(0,255,255),1)
            cv2.imwrite(str(replay/f"frame_{frame['frame_id']}"/'canonical_right_support_preview.jpg'),small)
            row['final_candidate_camera_Z_median_m']=float(np.median(p[:,2])*g['baseline_m'])
        rows.append(row)
    result={'status':'WASS_PROCESS_RECOVERY_NOT_WATER_MEASUREMENT_SUCCESS','baseline_source':str(source),'replay_source':str(replay),
        'planned_frames':run['planned_frames'],'baseline_xyz_frames':sum(f['completed_xyz'] for f in base['frames']),
        'replay_xyz_frames':sum(f['completed_xyz'] for f in run['frames']),
        'fixed_roi_pixels':run['roi_pixels'],'fixed_roi_full_image_ratio':run['roi_full_image_ratio'],
        'roi_selection':'analyst_predeclared_NOT_user_confirmed','denominator':'entire fixed canonical RIGHT polygon without support shrink',
        'controlled_change':run['controlled_change'],'frames':rows,'water_height_computed':False,
        'limitations':['candidate calibration not approved','candidate audio offset not frame verified',
            'visible texture includes user-confirmed tank bottom; XYZ support is not verified water support',
            'no common-FOV trimming of diagnostic denominator; stricter entire ROI statistic',
            'legacy P0cam rectified pixel assumption invalid; earlier ocean ROI percentage withdrawn']}
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(yaml.safe_dump(result,sort_keys=False,allow_unicode=True),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    import sys
    if '--summarize-source' in sys.argv:
        parser=argparse.ArgumentParser();parser.add_argument('--summarize-source',type=Path,required=True)
        parser.add_argument('--replay',type=Path,required=True);parser.add_argument('--result-yaml',type=Path,required=True)
        args=parser.parse_args();summarize(args.summarize_source,args.replay,args.result_yaml)
    elif '--replay-from' in sys.argv:
        parser=argparse.ArgumentParser();parser.add_argument('--replay-from',type=Path,required=True)
        parser.add_argument('--output',type=Path,required=True);parser.add_argument('--alpha',type=float,required=True)
        parser.add_argument('--roi-mask',action='store_true');parser.add_argument('--frames',nargs='+')
        args=parser.parse_args();replay_stereo(args.replay_from,args.output,args.alpha,args.roi_mask,args.frames)
    else:main()
