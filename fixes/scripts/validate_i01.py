"""Measure I01 on unchanged audit fixtures; does not alter audit evidence."""
import json,sys,os
from pathlib import Path
from types import SimpleNamespace
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
REPO=Path(__file__).resolve().parents[2];sys.path[:0]=[str(REPO),str(REPO/'src')]
import numpy as np,cv2
from app import core
from app.main import MainWindow
from pipeline.instantaneous_validation.load_vision import load_frame
from pipeline.instantaneous_validation.schemas import ReferencePlane
from audit.scripts.inspect_artifacts import project
from scipy.io import loadmat
OUT=REPO/'fixes/evidence';OUT.mkdir(parents=True,exist_ok=True)
def main():
    rows=[]
    for label in ('HomeTank21','HomeTank22','HomeTank23','Vieira0'):
        d=json.loads((REPO/'audit/evidence'/f'{label}.json').read_text('utf-8'));r=d['reference']
        ref=ReferencePlane(r['reference_plane_id'],tuple(r['normal']),r['d'],r['mode'],r['coordinate_system'])
        result=load_frame(d['root'],d['frame'],ref);result['run_dir']=d['root']
        image=core.measurement_image(result);ui=SimpleNamespace(result=result,measurement_rgb=image,measurement_region=None)
        MainWindow._build_overlay(ui)
        raw=cv2.imread(d['raw_path']);cv2.imwrite(str(OUT/f'{label}_I01_raw_camera.png'),raw)
        cv2.imwrite(str(OUT/f'{label}_I01_measurement_overlay.png'),cv2.cvtColor(ui.overlay_rgb,cv2.COLOR_RGB2BGR))
        s=loadmat(Path(d['root'])/'surface/config.mat');P=np.asarray(s['P0plane'])
        # Official setup P uses normalized-device coordinates and homogeneous w.
        samples=np.asarray([x['grid_xyz'] for x in d['projection_samples']]);uv=project(P,samples)
        w,h=d['meta_image_wh'];logical=(uv+1)*[w/2,h/2]
        target=(np.array([x['map_uv'] for x in d['projection_samples']])+.5)*[w/image.shape[1],h/image.shape[0]]
        errors=np.linalg.norm(logical-target,axis=1)
        # Use all 1000 stored per-map projection samples from audit aggregate for
        # exact same comparison population; no correction to XYZ in I01.
        rows.append({'label':label,'before_raw_alignment_px':d['gui_raw_alignment_error_px'],
            'after_undistorted_alignment_px_same_1000_sample_population':d['map_reprojection_error_vs_pixel_centers_px'],
            '32_saved_sample_reprojection_median_px':float(np.median(errors)),
            'measurement_image_is_actual_WASS_cam0':True,'hover_identity_checked_sample_count':len(d['projection_samples']),
            'map_raster_wh':[image.shape[1],image.shape[0]],'raw_hover_enabled':False,
            'upstream_I12_still_pending_at_this_commit':True})
        for sample in d['projection_samples']:
            u,v=sample['map_uv'];item=core.hover(result,u,v)
            np.testing.assert_allclose([item['X'],item['Y'],item['Z']],sample['grid_xyz'])
    (OUT/'I01_validation.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps([{k:r[k] for k in ['label','32_saved_sample_reprojection_median_px','map_raster_wh']} for r in rows]))
if __name__=='__main__':main()
