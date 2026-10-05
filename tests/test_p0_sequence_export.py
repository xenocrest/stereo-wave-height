import csv, json, tempfile, unittest
from pathlib import Path
import numpy as np
from plyfile import PlyData, PlyElement
from app import presentation
from pipeline.instantaneous_validation.schemas import ReferencePlane

class SequenceExportTests(unittest.TestCase):
    def test_provided_source_identity_nominal_time_and_B_units_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'run'
            (root/'sync').mkdir(parents=True);(root/'wass').mkdir()
            images=root/'wass/workspaces/000007_wd/undistorted';images.mkdir(parents=True)
            rgb=np.zeros((1,2,3),np.uint8)
            presentation.save_rgb(images/'00000000.png',rgb)
            pair={'index':7,'time_s':7/12,'left_source':'left8.tif','right_source':'right8.tif',
                  'left_sha256':'left-hash','right_sha256':'right-hash'}
            (root/'sync/sync.json').write_text(json.dumps({'status':'PROVIDED','frames':[pair]}))
            (root/'wass/run_summary.json').write_text(json.dumps({'active_calibration':{'fallback':False}}))
            ply=root/'cloud.ply'
            points=np.array([(1.,2.,3.)],dtype=[('x','f4'),('y','f4'),('z','f4')])
            PlyData([PlyElement.describe(points,'vertex')],text=True).write(ply)
            result={'run_dir':str(root),'frame_id':7,'timestamp_s':7/12,'units':'B',
                'calibration_identity':'c','source':np.array([[2,0]],np.uint8),
                'xyz':np.array([[[1.,2.,3.],[0.,0.,0.]]]),'height':np.array([[.2,np.nan]])}
            plane=ReferencePlane('ref',(0.,0.,1.),0.,'designated_static_water_frame','official_wass_grid_B')
            out=Path(directory)/'export'
            meta=presentation.export_current_frame(out,result,rgb,rgb,ply,plane,None)
            self.assertEqual(meta['source_image_pair'],pair)
            self.assertEqual(meta['timestamp_basis'],'PROVIDED_SEQUENCE_NOMINAL_TIME')
            for key in ('actual_left_source_pts','actual_right_source_pts','left_source_frame_index',
                        'right_source_frame_index','pair_residual_s','TLCC_offset'):
                self.assertIsNone(meta[key])
            self.assertEqual(meta['timestamp_s'],7/12)
            with (out/'instantaneous_height.csv').open(newline='',encoding='utf-8') as stream:
                rows=list(csv.DictReader(stream))
            self.assertEqual(len(rows),1);self.assertEqual(rows[0]['H_mm'],'')
            self.assertEqual(float(rows[0]['H_native']),.2)

if __name__=='__main__':unittest.main()
