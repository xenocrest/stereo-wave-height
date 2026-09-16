"""Copy audited demo outputs and emit provenance; no numerical processing."""
import hashlib
import json
from pathlib import Path
import shutil


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


if __name__ == '__main__':
    repo = Path(__file__).resolve().parents[1]
    run = Path('D:/stereo-wave-height-runs/vieira2025-end-to-end-demo-20260916')
    source = run/'fresh_004/chain'
    golden = run/'golden_004_demo'
    shutil.copytree(source, golden)
    shutil.copytree(run/'fresh_004/sync', golden/'sync')
    assets = repo/'presentation_assets/vieira2025_end_to_end_demo'
    copies = {'left.png':'sync/cam0/000000.png', 'right.png':'sync/cam1/000000.png',
              'height_map.png':'gridding/gridded.png', 'overlay.png':'overlay_water_roi.png',
              'overlay_full_official.png':'wassncplot/00000000_grid.png',
              'source_support_and_grid.png':'gridding/area_grid.png',
              'output_audit.json':'output_audit.json', 'sync_metadata.json':'sync/sync_result.json',
              'chain_summary.json':'chain_summary.json'}
    for target, original in copies.items():
        shutil.copy2(golden/original, assets/target)
    sync = json.loads((golden/'sync/sync_result.json').read_text(encoding='utf8'))
    audit = json.loads((golden/'output_audit.json').read_text(encoding='utf8'))
    summary = json.loads((golden/'chain_summary.json').read_text(encoding='utf8'))
    calibration = Path('D:/stereo-wave-height-runs/HomeTank_004/wave-reconstruction-pipeline-20260824/wass_workspace/config')
    provenance = {'source':str(calibration), 'experiment':'HomeTank_004 wave-reconstruction-pipeline-20260824',
                  'repository_audit_commit':'9a6bf946b16ec678ce1538f7e948d8ebf3fda6fb',
                  'original_generation_commit':'NOT_RELIABLY_IDENTIFIED',
                  'report':'VIEIRA_WASS_REPRO_AUDIT_ZH.md; VIEIRA_2025_FULL_REPRODUCTION_ZH.md',
                  'fallback':True, 'physically_validated':False,
                  'source_file_sha256':{p.name:digest(p) for p in sorted(calibration.iterdir()) if p.is_file()}}
    manifest = {'status':'END_TO_END_DEMO_PASS', 'label':'DEMO_ONLY_MEASUREMENT_NOT_VALIDATED',
                'scope':'Frozen five-frame engineering chain; display-only central water ROI; NOT full raw-data scientific reproduction',
                'starting_head':'a7e063be090b8f1780fcc83786c5cd60a76f4ae9',
                'dataset':'HomeTank_004', 'source_left_video':sync['left_video'], 'source_right_video':sync['right_video'],
                'sync':{'method':sync['method'], 'lag_seconds':sync['audio_lag_right_minus_left_s'], 'fallback':False, 'praat':sync['praat']},
                'intrinsics':provenance, 'extrinsics':dict(provenance, method='Historical OpenCV stereo R/T; attempted new WASS autocalibration preserved but not used'),
                'wass':{'version':'1.11_heads/master-0-g6b82aeb', 'core_modified':False, 'prepare':'5/5', 'match':'5/5', 'autocalibrate':'EXECUTED_RETURN_0_NOT_USED', 'stereo':'5/5'},
                'surface':{'wassgridsurface':'0.11.4', 'wassncplot':'2.5.3', 'mean_plane':audit['mean_plane']},
                'outputs':{'root':str(golden), 'xyz':'workspaces/*_wd/mesh_cam.xyzC', 'mesh':'workspaces/*_wd/mesh.ply', 'gridded_nc':'gridding/gridded.nc', 'overlay':'overlay_water_roi.png', 'pixel_xyz':'wassncplot/*.mat'},
                'query':audit['query'], 'frame_metrics':audit['frames'],
                'logs_index':summary['stages'],
                'validation':{'physically_validated':False, 'under_1cm_verified':False, 'wave_trend_verified':False, 'full_grid_is_not_full_direct_water_measurement':True,
                              'tests':'476 passed, 1 skipped, 4 subtests passed; Python compile, JSON, UTF-8 and diff checks'},
                'github_backup':'Small assets/config/code only; full local payload not uploaded',
                'frozen_payload_sha256':{str(p.relative_to(golden)):digest(p) for p in sorted(golden.rglob('*')) if p.is_file()}}
    (assets/'demo_manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+'\n', encoding='utf8')
    shutil.copy2(assets/'demo_manifest.json', golden/'demo_manifest.json')
    print(f'Frozen {len(manifest["frozen_payload_sha256"])} files: {golden}')
