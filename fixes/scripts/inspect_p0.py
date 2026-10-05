"""Actual newly generated P0 points -> projection -> GUI overlay -> hover/export."""
import json, os, sys
from pathlib import Path
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM']='offscreen'
REPO=Path(__file__).resolve().parents[2];sys.path[:0]=[str(REPO),str(REPO/'src')]
import cv2, numpy as np
from scipy.io import loadmat
from plyfile import PlyData
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QFontDatabase
from app import core, coordinates, presentation
from app.main import MainWindow
from pipeline.common import sha256, write_json
from pipeline.adapters.plane_contract import real_point_metrics

OUT=REPO/'fixes/evidence';ROOT=Path('D:/stereo-wave-height-runs/reconstruction-quality-p0-20261001')
def project(P,points):
    q=np.column_stack((points,np.ones(len(points))))@P.T
    return q[:,:2]/q[:,2,None]
def stats(values):
    values=np.asarray(values);values=values[np.isfinite(values)]
    return {'count':len(values),'median':float(np.median(values)),'max':float(np.max(values)),
        'min':float(np.min(values))}
def main():
    app=QApplication.instance() or QApplication([])
    # Offscreen Windows does not enumerate native fallback fonts reliably.
    font_id=QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc')
    if font_id < 0: raise RuntimeError('Chinese evidence font unavailable')
    app.setFont(QFont(QFontDatabase.applicationFontFamilies(font_id)[0],9))
    rows=json.loads((OUT/'P0_regenerated_runs.json').read_text('utf-8'));results=[]
    for row in rows:
        label=row['label'];root=Path(row['root']);frame=row['frame_id']
        ref,_=core.reference_from_metadata(row['reference'])
        window=MainWindow()
        try:
            if label.startswith('Home'):
                window.config=core.read_project(ROOT/'final/gui_project.yaml');window._populate()
                window.slider.setValue(int(label[-2:])*1000)
                with patch.object(window,'_error',side_effect=AssertionError):
                    window._open_run_path(str(root/'run_report.json'))
            else:
                config=core.read_project(REPO/'examples/vieira_official.yaml')
                config['presentation']={'frozen_reference':{**row['reference'],
                    'project_input_identity':core.project_input_identity(config)}}
                window.config=config;window._populate()
                window.science_run=root;window._viewing_existing_run=True;window._pending_key='vieira-test'
                config.update(_app_target_s=0.,_app_target_frame=0,_app_reference_frame=0)
                window._receive_reconstruction(config)
            result=window.result
            assert result is not None and window.reference==ref
            assert result['source_time_verified'] == label.startswith('Home')
            if label.startswith('Home'):
                original=json.loads((OUT/'I02_validation.json').read_text('utf-8'))['frame_mapping'][int(label[-2:])-21]
                for key in ('actual_left_source_pts','actual_right_source_pts','left_source_frame_index','right_source_frame_index','pair_residual_s'):
                    assert row['sync'][key]==original[key]
                for side in ('left','right'):
                    np.testing.assert_array_equal(cv2.imread(row['sync'][f'{side}_file']),cv2.imread(original[f'{side}_file']))
            h,w=result['height'].shape
            setup=loadmat(root/'surface/config.mat')
            ws=root/'wass/workspaces'/f'{frame:06d}_wd'
            logical=cv2.imread(str(ws/'undistorted/00000000.png'))
            ih,iw=logical.shape[:2]
            valid=np.argwhere(np.isfinite(result['height']))
            chosen=np.random.default_rng(20261001).choice(len(valid),min(1000,len(valid)),replace=False)
            vu=valid[chosen];points=result['xyz'][vu[:,0],vu[:,1]]
            uv=(project(setup['P0plane'],points)+1)*[iw/2,ih/2]
            target=(vu[:,::-1]+.5)*[iw/w,ih/h]
            reproj=stats(np.linalg.norm(uv-target,axis=1))
            # The original distorted camera cannot host this map directly.
            local=np.column_stack((points,np.ones(len(points))))@np.linalg.inv(setup['Cam0toGrid']).T
            from pipeline.adapters.wass import load_matrix
            raw_uv=cv2.projectPoints(np.ascontiguousarray(local[:,:3]),np.zeros(3),np.zeros(3),
                setup['K0'],load_matrix(root/'wass/config/distortion_00.xml'))[0].reshape(-1,2)
            hypothetical_raw=stats(np.linalg.norm(raw_uv-target,axis=1))
            samples=[]
            for i,(v,u) in enumerate(vu[:32]):
                item=core.hover(result,int(u),int(v))
                np.testing.assert_allclose([item['X'],item['Y'],item['Z']],points[i],rtol=0,atol=0)
                window._display_mode('overlay')
                with patch('app.main.core.hover',wraps=core.hover) as query:
                    window._hover(int(u),int(v));query.assert_called_once_with(result,int(u),int(v))
                samples.append({'map_uv':[int(u),int(v)],'projection_logical_uv':uv[i].tolist(),'hover':item})
            bounds=[(0,0),(w-1,0),(0,h-1),(w-1,h-1),(w//2,0),(0,h//2),(w-1,h//2),(w//2,h-1),(w//2,h//2)]
            boundary=[]
            for mode in ('measurement','overlay'):
                window._display_mode(mode)
                for u,v in bounds:
                    with patch('app.main.core.hover',wraps=core.hover) as query:
                        window._hover(u,v);query.assert_called_once_with(result,u,v)
                    boundary.append({'mode':mode,'uv':[u,v],'hover':core.hover(result,u,v)})
            window._display_mode('raw')
            with patch('app.main.core.hover',side_effect=AssertionError('raw hover enabled')):window._hover(w//2,h//2)
            assert window.image_canvas.border is None and window.image_canvas.region is None
            assert '高度查询关闭' in window.hover_label.text()
            window._display_mode('overlay');window.tabs.setCurrentIndex(1)
            v,u=vu[0];window._hover(int(u),int(v))
            window.resize(1700,1000);window.show();app.processEvents()
            window.grab().save(str(OUT/f'{label}_P0_GUI.png'))
            presentation.save_rgb(OUT/f'{label}_P0_measurement_overlay.png',window.overlay_rgb)
            presentation.save_rgb(OUT/f'{label}_P0_measurement.png',window.measurement_rgb)
            image=window.measurement_rgb.copy()
            # Green dots show projected real map XYZ in the same scientific image raster.
            for u,v in uv[:32]*[w/iw,h/ih]:cv2.circle(image,(int(u),int(v)),4,(0,255,0),1)
            presentation.save_rgb(OUT/f'{label}_P0_projection.png',image)
            v,u=vu[0]
            roi=(max(0,(u-3)/w),max(0,(v-3)/h),min(1,(u+4)/w),min(1,(v+4)/h))
            ply=root/'reconstruction/ply'/f'{frame:06d}.ply'
            export=presentation.export_current_frame(ROOT/'final/exports'/label,result,window.raw_rgb,
                window.overlay_rgb,ply,ref,roi)
            assert sha256(ply)==sha256(ROOT/'final/exports'/label/'pointcloud.ply')
            assert export['reference_plane_id']==ref.plane_id and export['coordinate_frame_id']==ref.coordinate_frame_id
            if result['units']=='B':assert all(core.hover(result,int(u),int(v))['height_mm'] is None for v,u in vu[:32])
            historical=None
            if label.startswith('Home'):
                history=Path('D:/stereo-wave-height-runs/HomeTank_004/wave-reconstruction-pipeline-20260824/wass_workspace/config')
                historical={name:sha256(root/'wass/config'/name)==sha256(history/name) for name in
                    ('intrinsics_00.xml','distortion_00.xml','intrinsics_01.xml','distortion_01.xml','ext_R.xml','ext_T.xml')}
                assert all(historical.values())
            results.append({'label':label,'root':str(root),'status':row['status'],
                'identities':coordinates.identity(root),'reference':ref.as_dict(),
                'map_size_wh':[w,h],'measurement_logical_wh':[iw,ih],
                'source_time_verified':result['source_time_verified'],
                'new_map_measurement_reprojection_logical_px':reproj,
                'hypothetical_raw_alignment_logical_px':hypothetical_raw,
                'actual_wass_transform_checks':real_point_metrics(setup,ws),
                'mapped_official_grid_estimates':int(np.sum(result['source']==2)),
                'no_data':int(np.sum(result['source']==0)),'direct_stereo_pixels':int(np.sum(result['source']==1)),
                'filtered_wass_points':len(PlyData.read(ply)['vertex'].data),
                'H_native':stats(result['height']),'units':result['units'],
                'same_complete_historical_bundle':historical,'raw_hover_disabled':True,
                'boundaries':boundary,'samples':samples,'export':export})
            write_json(OUT/'P0_final_measurements.json',results)
            print(label,reproj,'points',results[-1]['filtered_wass_points'],flush=True)
        finally:window.close()
    guards=[]
    for filename,key in [('third_party_unchanged_guard.json','baseline_hash'),('installed_scientific_package_source_hashes.json','sha256')]:
        for item in json.loads((REPO/'audit/evidence'/filename).read_text('utf-8')):
            current=sha256(item['path']);guards.append({'path':item['path'],'expected':item[key],
                'current':current,'unchanged':current==item[key]})
    assert all(x['unchanged'] for x in guards)
    write_json(OUT/'P0_third_party_unchanged.json',guards)
    print('GUARD',len(guards),'unchanged',flush=True)

if __name__=='__main__':main()
