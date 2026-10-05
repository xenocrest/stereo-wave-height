import json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from pipeline.instantaneous_validation.load_vision import frame_time_metadata
from pipeline.instantaneous_validation.run_validation import run

class TimeGateTests(unittest.TestCase):
    def test_verified_integer_source_pts_accepted_legacy_and_tampered_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'sync').mkdir();(root/'pixel/pixel_height').mkdir(parents=True)
            np.savez(root/'pixel/pixel_height/00000000.npz',xyz=np.ones((2,2,3)),source=np.full((2,2),2),units='m')
            row={'output_index':0,'left_requested_timestamp_s':12.5,'timestamp_basis':'ABSOLUTE_SOURCE_PTS_COPYTS',
                 'left_actual_timestamp_s':12.5,'right_actual_timestamp_s':12.501,'actual_left_source_pts':12.5,
                 'actual_right_source_pts':12.501,'left_source_frame_index':750,'right_source_frame_index':751,
                 'left_source_frame':{'source_frame_index':750,'source_pts_ticks':12500,'source_time_base':'1/1000'},
                 'right_source_frame':{'source_frame_index':751,'source_pts_ticks':12501,'source_time_base':'1/1000'},
                 'stereo_pair_residual_ms':1.}
            def save(): (root/'sync/sync.json').write_text(json.dumps({'frame_mapping':[row]}))
            save();self.assertTrue(frame_time_metadata(root,0)['source_time_verified'])
            config={'reference':{'mode':'provided_physical_plane','coordinate_system':'synthetic_grid',
                    'n_x':0,'n_y':0,'n_z':1,'d':0},'export_vision_csv':False,
                    'truth':{'data_file':'unused'},'validation':{'max_stereo_time_difference_ms':5}}
            with patch('pipeline.instantaneous_validation.run_validation.load_truth',side_effect=RuntimeError('reached truth loader')):
                with self.assertRaisesRegex(RuntimeError,'reached truth loader'):run(config,root,root/'out')
            row['timestamp_basis']='ACTUAL_DECODED_PTS';save()
            with self.assertRaisesRegex(ValueError,'VISION_TIMESTAMP_UNVERIFIED'):run(config,root,root/'out')
            row['timestamp_basis']='ABSOLUTE_SOURCE_PTS_COPYTS';row['right_source_frame']['source_pts_ticks']=12502;save()
            self.assertFalse(frame_time_metadata(root,0)['source_time_verified'])
            with self.assertRaisesRegex(ValueError,'VISION_TIMESTAMP_UNVERIFIED'):run(config,root,root/'out')

if __name__=='__main__':unittest.main()
