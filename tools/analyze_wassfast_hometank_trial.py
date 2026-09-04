"""Read-only support/ROI audit of a prepared official WASSfast trial."""
from pathlib import Path
import argparse
import json

import cv2 as cv
import numpy as np
from scipy.io import loadmat
from netCDF4 import Dataset
from matplotlib.path import Path as PolygonPath

from adapters.wassfast.output import read_cnn_output


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, required=True)
    args = ap.parse_args()
    root = args.root
    plan = json.loads((root/'input_manifest.json').read_text())
    cfg = loadmat(root/'grid/config.mat')
    grid = np.column_stack((cfg['XX'].ravel(), cfg['YY'].ravel(), np.zeros(cfg['XX'].size)))
    camera = (grid / cfg['CAM_BASELINE'].item() - cfg['Tpl'].ravel()) @ cfg['Rpl']
    projections, visible = [], []
    for side in (0,1):
        def read_xml(name):
            file = cv.FileStorage(str(root/'config'/name), cv.FILE_STORAGE_READ)
            value = file.getFirstTopLevelNode().mat()
            file.release()
            return value
        k = read_xml(f'intrinsics_{side:02d}.xml')
        d = read_xml(f'distortion_{side:02d}.xml')
        pose = np.linalg.solve(k, cfg[f'P{side}cam'])
        uv = cv.projectPoints(camera, cv.Rodrigues(pose[:,:3])[0], pose[:,3], k, d)[0].reshape(-1,2)
        positive = (camera @ pose[:,:3].T + pose[:,3])[:,2] > 0
        visible.append(positive & (uv[:,0]>=0) & (uv[:,0]<1920) & (uv[:,1]>=0) & (uv[:,1]<1080))
        projections.append(uv)
    polygon = np.asarray(plan['candidate_roi_cam1_px'])
    roi = PolygonPath(polygon).contains_points(projections[1]).reshape(256,256)
    common = (visible[0] & visible[1]).reshape(256,256)
    counts = np.zeros((1080,1920), np.uint8)
    cv.fillPoly(counts, [polygon.astype(np.int32)], 1)
    out = {'roi_camera_pixel_count':int(counts.sum()),'roi_image_fraction':float(counts.mean()),
           'roi_grid_node_count':int(roi.sum()), 'grid_common_view_fraction':float(common.mean()),
           'roi_common_view_fraction':float(common[roi].mean()),
           'roi_definition':'fixed predeclared canonical cam1 polygon; NOT shrunk to support', 'conditions':{}}
    for condition in ('static','wave'):
        parsed = read_cnn_output(root/condition/'output.nc', root/'grid/config.mat')
        g, raw = parsed.grid, parsed.raw_support_mask
        z = g.z[:,roi]
        good = np.isfinite(z)
        p = z[good]
        cloud_counts = [int(np.loadtxt(path).reshape(-1,3).shape[0]) for path in sorted((root/condition/'observations').glob('*point_cloud.txt'))]
        clouds = [np.loadtxt(path).reshape(-1,3) for path in sorted((root/condition/'observations').glob('*point_cloud.txt'))]
        raw_points = np.concatenate(clouds)
        raw_roi = PolygonPath(np.asarray(plan['roi_plane_xy_m'])).contains_points(raw_points[:,:2])
        raw_heights = raw_points[raw_roi,2]
        frames = []
        for i in range(len(g.z)):
            vals = z[i,good[i]]
            frames.append({'frame':i,'roi_supported_nodes':int(raw[i,roi].sum()),
                           'roi_finite_estimated_nodes':int(good[i].sum()),
                           'roi_height_mean_m':float(vals.mean()) if len(vals) else None})
        out['conditions'][condition] = {'frame_count':len(g.z),'point_counts':cloud_counts,
            'grid_raw_support_fraction':float(raw.mean()), 'grid_estimate_fraction':float(g.valid_mask.mean()),
            'roi_raw_support_fraction':float(raw[:,roi].mean()),'roi_estimate_fraction':float(good.mean()),
            'roi_height_min_m':float(p.min()) if len(p) else None,'roi_height_max_m':float(p.max()) if len(p) else None,
            'roi_height_mean_m':float(p.mean()) if len(p) else None,
            'roi_height_rms_m':float(np.sqrt(np.mean(p*p))) if len(p) else None,
            'raw_roi_point_count':int(raw_roi.sum()),
            'raw_roi_height_rms_m':float(np.sqrt(np.mean(raw_heights**2))) if len(raw_heights) else None,
            'raw_roi_height_min_m':float(raw_heights.min()) if len(raw_heights) else None,
            'raw_roi_height_max_m':float(raw_heights.max()) if len(raw_heights) else None,'frames':frames}
    out['classification'] = 'UPSTREAM_RUN_COMPLETED_WATER_HEIGHT_NOT_VALIDATED'
    (root/'trial_summary.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1,2,figsize=(12,4),layout='constrained')
    first = sorted((root/'wave/input/cam1').glob('*.png'))[0]
    axes[0].imshow(cv.imread(str(first),cv.IMREAD_GRAYSCALE),cmap='gray')
    axes[0].plot(*np.vstack([polygon,polygon[0]]).T,'c-')
    axes[0].set_title('Predeclared candidate ROI (not support-selected)')
    r = read_cnn_output(root/'wave/output.nc',root/'grid/config.mat')
    data = r.grid.z[0].copy()
    data[~roi] = np.nan
    im = axes[1].imshow(data*1000,origin='lower',extent=[r.grid.x[0],r.grid.x[-1],r.grid.y[0],r.grid.y[-1]],cmap='coolwarm')
    axes[1].set_title('ROI CNN estimates only; NOT validated height')
    fig.colorbar(im,ax=axes[1],label='Official plane-relative estimate (mm)')
    fig.savefig(root/'roi_and_wave_estimate.png',dpi=120)
    plt.close(fig)
    print(json.dumps(out,indent=2))


if __name__ == '__main__':
    main()
