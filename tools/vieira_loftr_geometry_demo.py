"""One bounded pretrained LoFTR -> official OpenCV geometry rescue for Demo.

No training, custom matching, triangulation or numerical surface reconstruction.
Writes real correspondences and OpenCV estimated R/T with auditable provenance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
import torch
from kornia.feature import LoFTR


def matrix(path):
    fs = cv2.FileStorage(str(path), cv2.FILE_STORAGE_READ)
    result = fs.getFirstTopLevelNode().mat()
    fs.release()
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sync', type=Path, required=True)
    p.add_argument('--calibration', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    torch.manual_seed(20260916)
    cv2.setRNGSeed(20260916)
    matcher = LoFTR(pretrained='outdoor').eval().cuda()
    all_pairs = []
    for index in (0, 4, 9):
        images, sizes = [], []
        for side in (0, 1):
            path = a.sync/f'cam{side}'/f'{index:06d}.png'
            image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
            sizes.append(np.array([image.shape[1]/640, image.shape[0]/360]))
            images.append(torch.from_numpy(cv2.resize(image, (640,360))).float()[None,None].cuda()/255)
        with torch.inference_mode():
            found = matcher({'image0': images[0], 'image1': images[1]})
        keep = found['confidence'].cpu().numpy() >= .8
        pair = [found[f'keypoints{side}'].cpu().numpy()[keep]*sizes[side] for side in (0,1)]
        all_pairs.append(pair)
    points = [np.concatenate([pair[side] for pair in all_pairs]) for side in (0,1)]
    np.savez_compressed(a.output/'real_matches.npz', left=points[0], right=points[1])
    k, d, normalized = [], [], []
    for side in (0,1):
        k.append(matrix(a.calibration/f'intrinsics_0{side}.xml'))
        d.append(matrix(a.calibration/f'distortion_0{side}.xml'))
        normalized.append(cv2.undistortPoints(points[side][:,None,:], k[side], d[side]).reshape(-1,2))
    threshold = 1.0/np.mean([k[0][0,0],k[0][1,1],k[1][0,0],k[1][1,1]])
    e, mask = cv2.findEssentialMat(*normalized, np.eye(3), method=cv2.RANSAC, prob=.999, threshold=threshold)
    count, r, t, pose_mask = cv2.recoverPose(e, *normalized, np.eye(3), mask=mask)
    for name, value in [('ext_R', r), ('ext_T', t)]:
        fs = cv2.FileStorage(str(a.output/(name+'.xml')), cv2.FILE_STORAGE_WRITE)
        fs.write(name, value)
        fs.release()
    record = {'method': 'Kornia LoFTR outdoor pretrained inference -> OpenCV undistortPoints/findEssentialMat/recoverPose',
              'status': 'DEMO_GEOMETRY_FALLBACK', 'frame_indices': [0,4,9], 'confidence_gate': .8,
              'inference_size_wh': [640,360], 'matches': len(points[0]), 'positive_depth_inliers': count,
              'R': r.tolist(), 'T_unit_baseline': t.tolist(), 'threshold_normalized': threshold,
              'intrinsics_source': str(a.calibration), 'physically_validated': False,
              'matches_sha256': hashlib.sha256((a.output/'real_matches.npz').read_bytes()).hexdigest()}
    (a.output/'provenance.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf8')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
