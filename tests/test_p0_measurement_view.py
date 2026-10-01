"""I01 regressions against synthetic boundaries and the two real datasets."""
import json,os,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import cv2,numpy as np
from app import core

class MeasurementViewTests(unittest.TestCase):
    def test_full_extent_map_raster_and_missing_image_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            result={'run_dir':directory,'frame_id':2,'height':np.zeros((6,8))}
            with self.assertRaisesRegex(ValueError,'missing official camera image'):core.measurement_image(result)
            folder=Path(directory)/'wass/workspaces/000002_wd/undistorted';folder.mkdir(parents=True)
            image=np.arange(3*4*3,dtype=np.uint8).reshape(3,4,3)
            cv2.imencode('.png',image)[1].tofile(folder/'00000000.png')
            expected=cv2.cvtColor(cv2.resize(image,(8,6)),cv2.COLOR_BGR2RGB)
            np.testing.assert_array_equal(core.measurement_image(result),expected)
            result['height']=np.zeros((6,9))
            with self.assertRaisesRegex(ValueError,'different aspect/crop'):core.measurement_image(result)

    def test_raw_hover_and_raw_region_boundary_are_disabled(self):
        from PySide6.QtWidgets import QApplication
        from app.main import MainWindow
        app=QApplication.instance() or QApplication([]);window=MainWindow()
        try:
            window.result={'height':np.ones((3,4))};window.raw_rgb=np.zeros((3,4,3),np.uint8)
            window.measurement_region=(.1,.1,.9,.9)
            window._display_mode('raw')
            with patch('app.main.core.hover',side_effect=AssertionError('raw queried map')):window._hover(1,1)
            self.assertIn('高度查询关闭',window.hover_label.text());self.assertIsNone(window.image_canvas.border)
            self.assertIsNone(window.image_canvas.region)
        finally:window.close()

    def test_measurement_hover_corners_edges_center_exactly_uses_map_indices(self):
        from PySide6.QtWidgets import QApplication
        from app.main import MainWindow
        app=QApplication.instance() or QApplication([]);window=MainWindow()
        try:
            h,w=6,8;window.result={'height':np.ones((h,w)),'source':np.full((h,w),2,np.uint8),
                'xyz':np.indices((h,w)).transpose(1,2,0).astype(float),'units':'m','timestamp_s':1.}
            window.result['xyz']=np.concatenate([window.result['xyz'],np.ones((h,w,1))],axis=2)
            window.measurement_rgb=np.zeros((h,w,3),np.uint8);window.reference_confirmed=True
            window._build_overlay()
            for mode in ('measurement','overlay'):
                window._display_mode(mode)
                for u,v in [(0,0),(w-1,0),(0,h-1),(w-1,h-1),(w//2,0),(0,h//2),(w-1,h//2),(w//2,h-1),(w//2,h//2)]:
                    with patch('app.main.core.hover',wraps=core.hover) as lookup:
                        window._hover(u,v);lookup.assert_called_once_with(window.result,u,v)
        finally:window.close()

    def test_real_official_images_and_overlay_background_both_datasets(self):
        from app.main import MainWindow
        evidence=core.ROOT/'audit/evidence'
        for label in ('HomeTank21','Vieira0'):
            data=json.loads((evidence/(label+'.json')).read_text('utf-8'));root=Path(data['root'])
            if not root.exists():self.skipTest('External real datasets not installed')
            from pipeline.instantaneous_validation.load_vision import load_frame
            from pipeline.instantaneous_validation.schemas import ReferencePlane
            r=data['reference'];ref=ReferencePlane(r['reference_plane_id'],tuple(r['normal']),r['d'],r['mode'],r['coordinate_system'])
            # Immutable historical fixtures for this spatial regression only;
            # does not authorize old reference use in newly generated results.
            result=load_frame(root,data['frame'],ref);result['run_dir']=str(root)
            official=core.measurement_image(result)
            ui=SimpleNamespace(result=result,measurement_rgb=official,measurement_region=None)
            MainWindow._build_overlay(ui)
            self.assertEqual(official.shape[:2],result['height'].shape)
            invalid=~np.isfinite(result['height']);np.testing.assert_array_equal(ui.overlay_rgb[invalid],official[invalid])
            for sample in data['projection_samples']:
                u,v=sample['map_uv'];item=core.hover(result,u,v)
                np.testing.assert_allclose([item['X'],item['Y'],item['Z']],sample['grid_xyz'])

if __name__=='__main__':unittest.main(verbosity=2)
