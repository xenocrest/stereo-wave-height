"""Fresh OpenCV calibration of both raw videos in the canonical convention."""
import sys,json,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from argparse import Namespace
REPO=Path(__file__).resolve().parents[2];sys.path[:0]=[str(REPO),str(REPO/'src')]
from app import core
from tools.vieira_intrinsics_from_raw import run
from pipeline.common import sha256
ROOT=Path('D:/stereo-wave-height-runs/reconstruction-quality-p0-20261001/I03_fresh_intrinsics')
def calibrate(side,config):
    print(f'Fresh {side} canonical calibration started',flush=True)
    target=ROOT/side
    if (target/'calibration.json').exists():
        raise FileExistsError(f'Preserve existing fresh result: {target}')
    board=config['checkerboard'];start=time.time()
    result=run(Namespace(video=config[side+'_video'],output=str(target),pattern_cols=board['columns'],pattern_rows=board['rows'],
        square_size_m=board['square_size_m'],sample_hz=config['sample_hz'],target_views=config['target_views'],minimum_views=config['minimum_views']))
    print(f'Fresh {side} completed: views={result["selected_view_count"]}, RMS={result["rms_px"]}',flush=True)
    return {'side':side,'source_video':result['source_video'],'output_directory':str(target),
        'elapsed_s':time.time()-start,'canonical_camera_image_orientation':result['canonical_camera_image_orientation'],
        'source_orientation_metadata_deg':result['source_orientation_metadata_deg'],'opencv_orientation_auto':result['opencv_orientation_auto'],
        'rms_px':result['rms_px'],'selected_view_count':result['selected_view_count'],'complete_detection_count':result['complete_detection_count'],
        'camera_matrix':result['camera_matrix'],'distortion':result['distortion_k1_k2_p1_p2_k3'],
        'selected_frame_indices':result['selected_frame_indices'],
        'intrinsics_sha256':sha256(target/'intrinsics.xml'),'distortion_sha256':sha256(target/'distortion.xml'),
        'fresh_R_T_not_estimated_or_combined_with_history':True,'calibration_report_sha256':sha256(target/'calibration.json')}
def main():
    config=core.read_project(REPO/'examples/hometank004.yaml')['calibration']
    # Independent camera calibrations; no shared images/poses/fit. Both retain
    # all configured samples and the existing error-independent selection rule.
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda side:calibrate(side,config),['left','right']))
    (REPO/'fixes/evidence/I03_fresh_calibration.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Fresh canonical intrinsics preserved separately; active fallback is unchanged',flush=True)
if __name__=='__main__':main()
