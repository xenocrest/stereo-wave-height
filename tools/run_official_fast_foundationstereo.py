"""Headless research runner for unmodified NVIDIA Fast-FoundationStereo.

This replaces only the upstream demo's interactive display/file handling.
Model forward, padding, RGB input scale and AMP match scripts/run_demo.py.
No disparity clipping, denoising, interpolation or height correction is applied.
Requires the official source checkout and verified NVIDIA serialized weights.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import sys
import time


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--weights', type=Path, required=True)
    parser.add_argument('--pairs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--max-disp', type=int, default=192)
    args = parser.parse_args()
    digest = hashlib.sha256(args.weights.read_bytes()).hexdigest()
    if digest != '7aee85948373da62b0503c2542507129a3e7cab9d97d10e6790d89512a7db214':
        raise ValueError('Expected verified NVIDIA c-fast-foundationstereo weights')
    sys.path.insert(0, str(args.source.resolve()))
    import cv2
    import numpy as np
    import torch
    from core.utils.utils import InputPadder
    from Utils import AMP_DTYPE, set_seed

    args.output.mkdir(parents=True, exist_ok=False)
    set_seed(0)
    torch.autograd.set_grad_enabled(False)
    # Pickle is only loaded after verifying the official NVIDIA LFS SHA256.
    model = torch.load(args.weights, map_location='cpu', weights_only=False)
    # NVIDIA commercial checkpoint omits this field. Upstream's own
    # scripts/make_plugin_onnx.py:123 and GWC builder both default to True.
    restored_normalize = 'normalize' not in model.args
    if restored_normalize:
        model.args.normalize = True
    model.args.valid_iters = 8
    model.args.max_disp = args.max_disp
    model.cuda().eval()
    records = []
    for pair in json.loads(args.pairs.read_text(encoding='utf-8'))['pairs']:
        images = [cv2.imread(pair[side], cv2.IMREAD_COLOR) for side in ('left', 'right')]
        if any(image is None for image in images) or images[0].shape != images[1].shape:
            raise ValueError('Unreadable or unequal stereo images')
        rgb = [cv2.cvtColor(image, cv2.COLOR_BGR2RGB) for image in images]
        height, width = rgb[0].shape[:2]
        tensors = [torch.as_tensor(image).cuda().float()[None].permute(0,3,1,2) for image in rgb]
        padder = InputPadder(tensors[0].shape, divis_by=32, force_square=False)
        left, right = padder.pad(*tensors)
        torch.cuda.synchronize()
        start = time.perf_counter()
        with torch.amp.autocast('cuda', enabled=True, dtype=AMP_DTYPE):
            prediction = model.forward(left, right, iters=8, test_mode=True,
                                       optimize_build_volume='pytorch1')
        torch.cuda.synchronize()
        elapsed = time.perf_counter() - start
        disparity = padder.unpad(prediction.float()).cpu().numpy().reshape(height, width)
        np.save(args.output / (pair['id'] + '.npy'), disparity)
        finite = disparity[np.isfinite(disparity)]
        record = {'id': pair['id'], 'seconds': elapsed, 'shape': list(disparity.shape),
                  'finite_ratio': float(np.isfinite(disparity).mean()),
                  'disparity_percentiles_px': np.percentile(finite, [0,5,50,95,100]).tolist()}
        records.append(record)
        print(json.dumps(record), flush=True)
        # Diagnostic visualization only, never used for geometry.
        lo, hi = np.percentile(finite, [2,98])
        visual = np.clip((disparity-lo)/max(hi-lo, 1e-6)*255, 0, 255).astype(np.uint8)
        cv2.imwrite(str(args.output/(pair['id']+'.jpg')),
                    np.concatenate((images[0], cv2.applyColorMap(visual, cv2.COLORMAP_TURBO)), axis=1))
    report = {'status': 'DISPARITY_OUTPUT_NOT_PHYSICAL_VALIDATION', 'weights_sha256': digest,
              'torch': torch.__version__, 'opencv': cv2.__version__,
              'gpu': torch.cuda.get_device_name(0), 'max_disp': args.max_disp,
              'valid_iters': 8, 'normalize': bool(model.args.normalize),
              'torchdynamo_disable': os.environ.get('TORCHDYNAMO_DISABLE','0'),
              'restored_upstream_default_normalize': restored_normalize, 'records': records}
    (args.output/'run.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
