"""Read-only audit and presentation-domain masking of official Demo outputs."""
import argparse
import json
from pathlib import Path
import cv2
import netCDF4
import numpy as np
import scipy.io as sio
from scipy.spatial import Delaunay
from wassgridsurface.wass_utils import load_camera_mesh, align_on_sea_plane


def audit(root):
    root = Path(root)
    config = sio.loadmat(root/'gridding/config.mat')
    planes = np.loadtxt(root/'planes.txt')
    plane = np.median(planes, axis=0)
    baseline = float(config['CAM_BASELINE'].item())
    frames = []
    with netCDF4.Dataset(str(root/'gridding/gridded.nc')) as dataset:
        x, y = np.asarray(dataset['X_grid'][:]), np.asarray(dataset['Y_grid'][:])
        grid_xy = np.column_stack([x.ravel(), y.ravel()])
        for index in range(len(dataset['Z'])):
            mesh = load_camera_mesh(root/f'workspaces/{index:06d}_wd/mesh_cam.xyzC')
            projection = np.loadtxt(root/f'workspaces/{index:06d}_wd/P0cam.txt')
            camera = projection @ np.vstack([mesh, np.ones(mesh.shape[1])])
            uv = camera[:2]/camera[2]
            water = (camera[2]>0)&(uv[0]>=650)&(uv[0]<=950)&(uv[1]>=700)&(uv[1]<=950)
            points = align_on_sea_plane(mesh, plane)*baseline*1000
            # Same nearest-grid rounding used by the official gridder.
            ix = np.floor((points[0]-x.min())/(x.max()-x.min())*255+.5).astype(int)
            iy = np.floor((points[1]-y.min())/(y.max()-y.min())*255+.5).astype(int)
            good = (ix>=0)&(ix<256)&(iy>=0)&(iy<256)
            supported = np.zeros(65536, dtype=bool)
            supported[iy[good]*256+ix[good]] = True
            inside_hull = Delaunay(points[:2, good].T).find_simplex(grid_xy)>=0
            z = np.asarray(dataset['Z'][index])
            frames.append({'index': index, 'source_points': mesh.shape[1], 'finite_points': int(np.isfinite(mesh).all(0).sum()),
                           'positive_projective_depth_points': int((camera[2]>0).sum()),
                           'source_points_in_water_display_roi': int(water.sum()),
                           'source_occupied_grid_cells': int(supported.sum()), 'source_supported_grid_percent': float(supported.mean()*100),
                           'interpolated_inside_hull_percent': float((inside_hull&~supported).mean()*100),
                           'extrapolated_outside_hull_percent': float((~inside_hull&~supported).mean()*100),
                           'finite_grid_cells': int(np.isfinite(z).sum()), 'height_min_mm': float(np.nanmin(z)),
                           'height_max_mm': float(np.nanmax(z)), 'height_median_mm': float(np.nanmedian(z))})
    mapping = sio.loadmat(root/'wassncplot/00000000.mat')['px_2_3D']
    valid = np.isfinite(mapping).all(2)&~np.all(np.isclose(mapping,0),2)&~np.all(np.isclose(mapping,1),2)
    # Query is explicitly a rendered pixel in the official 2400x1350 image.
    px, py = 1000, 1050
    if not valid[py,px]:
        raise ValueError('fixed water query has no official mapping')
    xyz = mapping[py,px]
    projected = config['P0plane'] @ np.r_[xyz,1.]
    logical = np.array([(projected[0]/projected[2]+1)*1920/2, (projected[1]/projected[2]+1)*1080/2])
    rendered = logical*np.array([mapping.shape[1]/1920,mapping.shape[0]/1080])
    closure = float(np.linalg.norm(rendered-np.array([px+.5,py+.5])))
    if closure>1:
        raise ValueError(f'official mapping closure failed: {closure}')
    # Display-only ROI in undistorted computational cam0 pixels. Raw output stays unchanged.
    roi = np.array([[650,700],[950,700],[950,950],[650,950]], dtype=float)
    polygon = np.rint(roi*np.array([mapping.shape[1]/1920,mapping.shape[0]/1080])).astype(np.int32)
    original = cv2.imread(str(root/'wassncplot/00000000.png'))
    overlay = cv2.imread(str(root/'wassncplot/00000000_grid.png'))
    mask = np.zeros(original.shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask,[polygon],255)
    shown = np.where(mask[:,:,None]>0,overlay,original)
    cv2.polylines(shown,[polygon],True,(0,255,255),3)
    cv2.putText(shown,'DEMO ONLY - INTERPOLATED / ESTIMATED', (40,60), cv2.FONT_HERSHEY_SIMPLEX,1,(0,255,255),2)
    cv2.imwrite(str(root/'overlay_water_roi.png'),shown)
    result = {'status': 'OFFICIAL_OUTPUTS_AUDITED', 'frames': frames,
              'official_mapping_valid_pixels': int(valid.sum()), 'mean_plane': plane.tolist(),
              'water_display_roi_undistorted_computational_cam0': roi.tolist(),
              'query': {'rendered_pixel_xy': [px,py], 'sea_plane_xyz_m': xyz.tolist(),
                        'height_mm_from_official_render': float(xyz[2]*1000), 'pixel_center_closure_error_px': closure,
                        'provenance': 'OFFICIAL_GRID_INTERPOLATED_ESTIMATED_NOT_DIRECT_PIXEL_MEASUREMENT',
                        'height_convention': 'wassncplot shader: NetCDF Z/1000 minus official meta.zmean'},
              'physically_validated': False, 'under_1cm_verified': False,
              'full_grid_is_not_full_direct_water_measurement': True}
    (root/'output_audit.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    print(json.dumps(audit(parser.parse_args().root),indent=2))
