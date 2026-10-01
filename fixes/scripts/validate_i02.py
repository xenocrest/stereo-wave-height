"""Re-extract actual 21/22/23 source frames and independently check audit identities."""
import sys,json
from pathlib import Path
REPO=Path(__file__).resolve().parents[2];sys.path[:0]=[str(REPO),str(REPO/'src')]
from tools.vieira_tlcc_sync import run
from argparse import Namespace
import cv2,numpy as np
ROOT=Path('D:/stereo-wave-height-runs/reconstruction-quality-p0-20261001')
def main():
    origin=REPO/'audit/evidence/sync_absolute_pts_and_frame_identity.json'
    audit=json.loads(origin.read_text('utf-8'))
    s=json.loads(Path('D:/stereo-wave-height-runs/fixed-coordinate-acceptance-20261001-final/Run_A/science/sync/sync.json').read_text('utf-8'))
    result=run(Namespace(left=s['left_video'],right=s['right_video'],ffmpeg=s['ffmpeg'],praat=s['praat'],
        output=str(ROOT/'I02_sync'),window_start_s=0.,window_end_s=30.,start_s=21.,output_fps=1.,frame_count=3))
    for row,expected in zip(result['frame_mapping'],audit['records']):
        for cam,key in [('cam0','left'),('cam1','right')]:
            match=next(x for x in expected['images'][cam] if x['pixel_identical_to_stored'])
            assert row[key+'_source_frame_index']==match['source_frame_index']
            assert abs(row[key+'_actual_timestamp_s']-match['absolute_pts_s'])<.000001
            actual=cv2.imread(row[key+'_file']);old=cv2.imread(expected['reported'][key+'_file'])
            assert np.array_equal(actual,old)
        row['pixel_identical_to_audited_original_pair']=True
        row['nearest_available_right_for_fixed_left']=True
    out=REPO/'fixes/evidence/I02_validation.json';out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps([{k:r[k] for k in ['requested_timestamp','actual_left_source_pts','actual_right_source_pts','left_source_frame_index','right_source_frame_index','pair_residual_s']} for r in result['frame_mapping']]))
if __name__=='__main__':main()
