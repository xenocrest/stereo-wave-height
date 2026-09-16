"""Read-only loaders for Golden Demo v1. Never invokes processing tools."""
import hashlib
import json
from pathlib import Path
import netCDF4
import numpy as np
from plyfile import PlyData
from scipy.io import loadmat

ASSETS = Path(__file__).resolve().parents[1]/'presentation_assets/vieira2025_end_to_end_demo'


class AssetError(Exception):
    pass


def require(path):
    path = Path(path)
    if not path.is_file():
        raise AssetError(f'Golden Demo asset missing: {path}')
    return path


def manifest():
    return json.loads(require(ASSETS/'demo_manifest.json').read_text(encoding='utf8'))


def frame_paths(root, index):
    if index not in range(5):
        raise AssetError('Frame index must be 0–4')
    root = Path(root)
    return {'left':root/f'sync/cam0/{index:06d}.png',
            'right':root/f'sync/cam1/{index:06d}.png',
            'ply':root/f'workspaces/{index:06d}_wd/mesh.ply',
            'overlay':root/f'wassncplot/{index:08d}_grid.png',
            'image':root/f'wassncplot/{index:08d}.png',
            'mat':root/f'wassncplot/{index:08d}.mat'}


def point_cloud(path, max_display=25000):
    vertices = PlyData.read(str(require(path)))['vertex'].data
    xyz = np.column_stack([vertices[k] for k in ('x','y','z')])
    stride = max(1, int(np.ceil(len(xyz)/max_display)))
    return xyz[::stride].copy(), len(xyz)


def height_grid(path, index):
    with netCDF4.Dataset(str(require(path)), 'r') as data:
        if index not in range(len(data['Z'])):
            raise AssetError('Frame index out of range')
        return tuple(np.asarray(data[k][index] if k=='Z' else data[k][:]).copy()
                     for k in ('X_grid','Y_grid','Z'))


def pixel_mapping(path):
    return loadmat(require(path), variable_names=['px_2_3D'])['px_2_3D']


def query(mapping, u, v):
    if not (0 <= u < mapping.shape[1] and 0 <= v < mapping.shape[0]):
        raise AssetError(f'Pixel outside image: u=0–{mapping.shape[1]-1}, v=0–{mapping.shape[0]-1}')
    xyz = np.asarray(mapping[v,u], dtype=float)
    valid = np.isfinite(xyz).all() and not np.all(np.isclose(xyz,0)) and not np.all(np.isclose(xyz,1))
    if not valid:
        return {'u':u,'v':v,'provenance':'UNSUPPORTED','reason':'Official mapping contains background/sentinel, no XYZ'}
    return {'u':u,'v':v,'X_m':float(xyz[0]),'Y_m':float(xyz[1]),'Z_m':float(xyz[2]),
            'H_mm':float(xyz[2]*1000), 'provenance':'UNKNOWN',
            'estimate_method':'OFFICIAL_RENDERED_DCT_GRID',
            'support_class':'UNKNOWN',
            'reason':'Official rendered DCT grid estimate, not a direct pixel observation. Per-pixel source versus extrapolation not available.',
            'convention':'wassncplot shader: NetCDF Z/1000 minus official meta.zmean; no UI correction'}


def verify_frozen(record):
    root = Path(record['outputs']['root'])
    checked = 0
    for relative, expected in record['frozen_payload_sha256'].items():
        path = require(root/relative)
        h = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda:stream.read(1024*1024), b''):
                h.update(block)
        if h.hexdigest()!=expected:
            raise AssetError(f'Golden Demo checksum mismatch: {path}')
        checked += 1
    return checked
