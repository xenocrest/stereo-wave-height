"""Thin, provenance-preserving launcher for unmodified WASS/official tools.

Only command orchestration and output auditing: no stereo, triangulation,
autocalibration, plane fitting, or interpolation is implemented here.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import numpy as np
import scipy.io as sio
from vieira_wass_full_run import command


def run(config):
    root = Path(config['output'])
    root.mkdir(parents=True, exist_ok=False)
    calibration = Path(config['fallback_calibration'])
    cfg = root/'config'
    shutil.copytree(calibration, cfg)
    work, logs = root/'workspaces', root/'logs'
    work.mkdir()
    logs.mkdir()
    stages = {'prepare': [], 'match': [], 'stereo': []}
    paths = []
    frames = sorted((Path(config['sync'])/'cam0').glob('*.png'))
    for index, left in enumerate(frames):
        wd = work/f'{index:06d}_wd'
        paths.append(wd)
        arguments = [str(Path(config['wass_bin'])/'wass_prepare.exe'), '--workdir', str(wd),
                     '--calibdir', str(cfg), '--c0', str(left), '--c1', str(Path(config['sync'])/'cam1'/left.name)]
        result = command(arguments, logs/f'prepare_{index:06d}.log')
        stages['prepare'].append(result)
        if result['return_code']:
            raise RuntimeError(f"prepare failed: {result['log']}")
        stages['match'].append(command([str(Path(config['wass_bin'])/'wass_match.exe'),
                              str(cfg/'matcher_config.txt'), str(wd)], logs/f'match_{index:06d}.log'))
    (root/'workspaces.txt').write_text('\n'.join(map(str, paths))+'\n', encoding='utf8')
    stages['autocalibrate'] = command([str(Path(config['wass_bin'])/'wass_autocalibrate.exe'),
                                      str(root/'workspaces.txt')], logs/'autocalibrate.log')
    # Explicit Level-1 fallback. Preserve all attempted autocalibration files.
    for index, wd in enumerate(paths):
        for name in ('ext_R.xml', 'ext_T.xml'):
            if (wd/name).exists():
                shutil.copy2(wd/name, wd/('attempted_autocal_'+name))
            shutil.copy2(calibration/name, wd/name)
        result = command([str(Path(config['wass_bin'])/'wass_stereo.exe'), config['stereo_config'], str(wd)],
                         logs/f'stereo_{index:06d}.log')
        stages['stereo'].append(result)
    successful = [wd for wd, result in zip(paths, stages['stereo']) if not result['return_code'] and (wd/'mesh_cam.xyzC').exists()]
    summary = {'stages': stages, 'successful_stereo_count': len(successful), 'workspace_count': len(paths),
               'extrinsics_fallback': True, 'intrinsics_fallback': True, 'physically_validated': False,
               'status': 'BLOCKED' if len(successful)!=len(paths) else 'WASS_STEREO_PASS'}
    (root/'chain_summary.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf8')
    if len(successful)!=len(paths):
        return summary
    planes = np.vstack([np.loadtxt(wd/'plane.txt') for wd in successful])
    np.savetxt(root/'planes.txt', planes)
    # Use official decoder/alignment only to select a physical grid extent.
    from wassgridsurface.wass_utils import load_camera_mesh, align_on_sea_plane
    plane = np.median(planes, axis=0)
    points = align_on_sea_plane(load_camera_mesh(successful[0]/'mesh_cam.xyzC'), plane)*config['baseline_m']
    lo, hi = points[:2].min(axis=1), points[:2].max(axis=1)
    center, side = (lo+hi)/2, float(np.max(hi-lo))
    grid = root/'gridding'
    grid.mkdir()
    (grid/'gridconfig.txt').write_text(f'[Area]\narea_center_x={center[0]}\narea_center_y={center[1]}\narea_size={side}\nN=256\n', encoding='ascii')
    # Official gridder expects planes.txt alongside NN_wd directories.
    shutil.copy2(root/'planes.txt', work/'planes.txt')
    base = str(Path(sys.executable).parent/'wassgridsurface.exe')
    (root/'wassncplot').mkdir()
    for label, arguments in [('setup', [base, '--action', 'setup', str(work), str(grid), '--gridconfig', str(grid/'gridconfig.txt'), '--baseline', str(config['baseline_m']), '--fps', '10', '--stereo_image_idx', '0']),
                              ('grid', [base, '--action', 'grid', str(work), str(grid), '--gridsetup', str(grid/'config.mat'), '--num_frames', str(len(paths)), '--parallel', '1', '--stereo_image_idx', '0']),
                              ('wassncplot', [str(Path(sys.executable).parent/'wassncplot.exe'), str(grid/'gridded.nc'), str(root/'wassncplot'), '-f', '0', '-l', str(len(paths)), '--savexyz', '--save-img', '--no-textoverlay', '--pxscale', '1'])]:
        result = command(arguments, logs/(label+'.log'))
        stages[label] = result
        if result['return_code']:
            summary['status'] = 'BLOCKED_AT_'+label.upper()
            break
    else:
        mapping = sio.loadmat(root/'wassncplot'/'00000000.mat')['px_2_3D']
        valid = np.isfinite(mapping).all(axis=2)&~np.all(np.isclose(mapping, 1), axis=2)&~np.all(np.isclose(mapping, 0), axis=2)
        summary['valid_mapping_pixels'] = int(valid.sum())
        summary['status'] = 'OFFICIAL_OUTPUTS_GENERATED_REQUIRES_OVERLAY_REVIEW' if valid.any() else 'BLOCKED_AT_PIXEL_MAPPING'
    (root/'chain_summary.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(json.loads(args.config.read_text(encoding='utf8'))), indent=2))
