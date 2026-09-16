"""Convert raw-sensor OpenCV intrinsics to a 180-degree canonical image.

This is a coordinate adapter, not calibration: K'=H K S, with image rotation H
and camera-axis rotation S=diag(-1,-1,1). Radial coefficients are invariant;
tangential coefficients p1,p2 change sign. Original artifacts remain untouched.
"""
import argparse
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np


def convert(k, d, width, height):
    h = np.array([[-1., 0., width-1], [0., -1., height-1], [0., 0., 1.]])
    s = np.diag([-1., -1., 1.])
    result_d = np.asarray(d).copy()
    result_d.flat[2] *= -1
    result_d.flat[3] *= -1
    return h @ k @ s, result_d


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    meta = json.loads((a.source/'calibration.json').read_text(encoding='utf8'))
    values = []
    for name in ('intrinsics', 'distortion'):
        storage = cv2.FileStorage(str(a.source/(name+'.xml')), cv2.FILE_STORAGE_READ)
        values.append(storage.getFirstTopLevelNode().mat())
        storage.release()
    k, d = convert(*values, *meta['image_size_wh'])
    a.output.mkdir(parents=True, exist_ok=False)
    for name, key, matrix in [('intrinsics', 'intr', k), ('distortion', 'dist', d)]:
        storage = cv2.FileStorage(str(a.output/(name+'.xml')), cv2.FILE_STORAGE_WRITE)
        storage.write(key, matrix)
        storage.release()
    record = {'method': 'exact 180-degree coordinate transform K_prime=H*K*S; p1,p2 sign reversal',
              'source': str(a.source), 'source_hashes': {name: hashlib.sha256((a.source/name).read_bytes()).hexdigest()
              for name in ('intrinsics.xml', 'distortion.xml')}, 'K': k.tolist(), 'D': d.tolist(),
              'physically_validated': False, 'rotation_deg': 180}
    (a.output/'provenance.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf8')


if __name__ == '__main__':
    main()
