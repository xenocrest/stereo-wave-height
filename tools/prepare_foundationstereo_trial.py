"""Prepare an isolated calibrated stereo trial; no calibration changes.

OpenCV alpha=1 retains field of view. Valid image masks and the same broad
canonical-cam1 polygon are retained, not selected using reconstruction success.
"""
from pathlib import Path
import argparse
import hashlib
import json
import cv2
import numpy as np
import yaml


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--upstream', type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding='utf-8'))
    calibration_path = Path(config['calibration'])
    calibration = yaml.safe_load(calibration_path.read_text(encoding='utf-8'))
    if 'camera_left' in calibration:
        # Package schema -> same explicitly declared OpenCV convention, no fit.
        calibration = {'mono_cam0':calibration['camera_left'],
            'mono_cam1':calibration['camera_right'], 'stereo':{
                'R_right_from_left':calibration['stereo']['R'],
                'T_right_from_left_m':calibration['stereo']['T_m'],
                'baseline_m':calibration['stereo']['baseline_m']}}
    stereo = calibration['stereo']
    k = [np.asarray(calibration[f'mono_cam{i}']['K'], dtype=float) for i in (0,1)]
    d = [np.asarray(calibration[f'mono_cam{i}']['D'], dtype=float).reshape(-1,1) for i in (0,1)]
    rotation = np.asarray(stereo['R_right_from_left'], dtype=float)
    translation = np.asarray(stereo['T_right_from_left_m'], dtype=float).reshape(3,1)
    if not np.isclose(np.linalg.norm(translation),stereo['baseline_m'],rtol=1e-10):
        raise ValueError('Declared metric baseline differs from frozen T')
    size = (960,540)
    r0,r1,p0,p1,q,roi0,roi1 = cv2.stereoRectify(k[0],d[0],k[1],d[1],(1920,1080),
        rotation,translation,flags=cv2.CALIB_ZERO_DISPARITY,alpha=1,newImageSize=size)
    if not (p1[0,3] < 0 and np.isclose(p1[1,3],0)):
        raise ValueError('Model requires conventional positive horizontal left disparity')
    args.output.mkdir(parents=True, exist_ok=False)
    maps = [cv2.initUndistortRectifyMap(k[i],d[i],r,p,size,cv2.CV_32FC1)
            for i,(r,p) in enumerate(((r0,p0),(r1,p1)))]
    valid = [(mx>=0)&(mx<1919)&(my>=0)&(my<1079) for mx,my in maps]
    polygon = np.asarray(config['candidate_roi_cam1_px'], dtype=np.int32)
    raw_mask = np.zeros((1080,1920), dtype=np.uint8)
    cv2.fillPoly(raw_mask,[polygon],1)
    roi_mask = cv2.remap(raw_mask,*maps[1],cv2.INTER_NEAREST)>0
    input_hashes = {}
    pairs = [{'id':'official_sample','left':str(args.upstream/'demo_data/left.png'),
              'right':str(args.upstream/'demo_data/right.png')}]
    frame_times = []
    for condition in config['sequences']:
        for index in (0,3,7):
            identity = f'{condition}_{index:06d}'
            paths = []
            for side in (0,1):
                if config.get('decode_videos',False):
                    capture=cv2.VideoCapture(config['videos'][condition][side])
                    capture.set(cv2.CAP_PROP_ORIENTATION_AUTO,0)
                    timing=config['sequences'][condition]
                    target=timing['left_start_s']+index/config['fps']+(timing['right_minus_left_s'] if side else 0)
                    capture.set(cv2.CAP_PROP_POS_MSEC,target*1000)
                    ok,image=capture.read()
                    actual=capture.get(cv2.CAP_PROP_POS_MSEC)/1000
                    capture.release()
                    if not ok:
                        raise ValueError('Video frame decode failed')
                    if side==0:
                        image=cv2.rotate(image,cv2.ROTATE_180)
                    frame_times.append({'id':identity,'side':side,'target_s':target,'actual_s':actual})
                    frozen=args.output/f'{identity}_canonical_cam{side}.png'
                    cv2.imwrite(str(frozen),image)
                    input_hashes[str(frozen)]=hashlib.sha256(frozen.read_bytes()).hexdigest()
                else:
                    source = sorted((Path(config['output'])/condition/'input'/f'cam{side}').glob(f'{index:06d}_*.png'))
                    if len(source)!=1:
                        raise ValueError('Frozen input pair missing/ambiguous')
                    input_hashes[str(source[0])] = hashlib.sha256(source[0].read_bytes()).hexdigest()
                    image = cv2.imread(str(source[0]), cv2.IMREAD_COLOR)
                if image.shape[:2] != (1080,1920):
                    raise ValueError('Calibration image size mismatch')
                image = cv2.remap(image,*maps[side],cv2.INTER_LINEAR)
                path = args.output/f'{identity}_cam{side}.png'
                cv2.imwrite(str(path),image)
                paths.append(str(path))
                cv2.imwrite(str(args.output/f'{identity}_cam{side}_flip.png'),cv2.flip(image,1))
            pairs.append({'id':identity,'left':paths[0],'right':paths[1]})
            # Standard swapped + horizontally flipped pair yields right disparity.
            pairs.append({'id':identity+'_reverse',
                'left':str(args.output/f'{identity}_cam1_flip.png'),
                'right':str(args.output/f'{identity}_cam0_flip.png')})
    np.savez_compressed(args.output/'geometry.npz',R0=r0,R1=r1,P0=p0,P1=p1,Q=q,
        R=rotation,T=translation,valid_left=valid[0],valid_right=valid[1],roi_right=roi_mask,
        map_right_x=maps[1][0],map_right_y=maps[1][1],
        reference_plane=np.loadtxt(Path(config['frozen_workdir'])/'plane.txt'),
        baseline_m=stereo['baseline_m'])
    (args.output/'pairs.json').write_text(json.dumps({'pairs':pairs},indent=2)+'\n',encoding='utf-8')
    metadata = {'calibration_sha256':hashlib.sha256(calibration_path.read_bytes()).hexdigest(),
        'alpha':1,'flags':int(cv2.CALIB_ZERO_DISPARITY),'source_image_size':[1920,1080],
        'rectified_size':list(size),'P0':p0.tolist(),'P1':p1.tolist(),
        'valid_pix_roi_left':list(roi0),'valid_pix_roi_right':list(roi1),
        'roi_canonical_cam1':polygon.tolist(),'roi_rectified_pixel_count':int(roi_mask.sum()),
        'status':'ISOLATED_RESEARCH_NOT_CALIBRATION_APPROVAL',
        'reference':'frozen WASS plane in camera1, baseline-normalized; not re-fit',
        'reference_sha256':hashlib.sha256((Path(config['frozen_workdir'])/'plane.txt').read_bytes()).hexdigest(),
        'frozen_input_sha256':input_hashes,
        'decoded_timestamps':frame_times,
        'timing_manifest':str(Path(config['output'])/'input_manifest.json') if not frame_times else None,
        'warning':'CALIBRATION_QUALITY_FAIL and synchronization warning remain'}
    (args.output/'preparation.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(metadata))


if __name__=='__main__':
    main()
