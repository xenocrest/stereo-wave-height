"""Re-grid immutable real WASS observations to isolate the I12 adapter change."""
import json, os, shutil, sys
from pathlib import Path
# Official VisPy renderer needs the native OpenGL context on Windows.
os.environ.pop('QT_QPA_PLATFORM', None)
REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO/'src')]
import numpy as np
from scipy.io import loadmat
from app import core, coordinates
from pipeline.adapters import surface
from pipeline.adapters.plane_contract import real_point_metrics
from pipeline.common import CommandRecorder, write_json, sha256, require_empty

ROOT = Path('D:/stereo-wave-height-runs/reconstruction-quality-p0-20261001')
SOURCES = {
    'HomeTank': Path('D:/stereo-wave-height-runs/pipeline/hometank004_multiframe_acceptance/run_20260928/science'),
    'Vieira': Path('D:/stereo-wave-height-runs/pipeline/vieira_official/run_20260928_113344')}

def main():
    all_results = []
    for label, origin in SOURCES.items():
        root = require_empty(ROOT/'I12_contract_fixture'/label)
        config = core.read_project(REPO/'examples'/('hometank004.yaml' if label=='HomeTank' else 'vieira_official.yaml'))
        old = loadmat(origin/'surface/config.mat')
        # Preserve the old plotting rectangle exactly: domain/support is a later issue.
        config['surface'].update(area_center_x=float((old['xmin']+old['xmax']).item()/2),
            area_center_y=float((old['ymin']+old['ymax']).item()/2),
            area_size=float((old['xmax']-old['xmin']).item()))
        for folder in ('wass/config', 'reconstruction/ply'):
            shutil.copytree(origin/folder, root/folder)
        (root/'calibration').mkdir()
        for path in (origin/'calibration').iterdir():
            if path.is_file(): shutil.copy2(path,root/'calibration'/path.name)
        shutil.copytree(origin/'sync', root/'sync')
        shutil.copy2(origin/'wass/run_summary.json', root/'wass/run_summary.json')
        copy_hashes = []
        workspaces = sorted((origin/'wass/workspaces').glob('*_wd'))
        for workspace in workspaces:
            target = root/'wass/workspaces'/workspace.name
            target.mkdir(parents=True)
            for path in workspace.iterdir():
                if path.is_file() and (path.suffix in ('.xml','.txt') or path.name=='mesh_cam.xyzC'):
                    shutil.copy2(path, target/path.name)
                    copy_hashes.append({'source':str(path),'copy':str(target/path.name),
                        'source_sha256':sha256(path),'copy_sha256':sha256(target/path.name)})
            shutil.copytree(workspace/'undistorted', target/'undistorted')
        recorder = CommandRecorder(root/'logs/pipeline')
        sync = json.loads((root/'sync/sync.json').read_text('utf-8'))
        report = surface.run(config['surface'], config['tools'], sync, root, recorder)
        write_json(root/'run_report.json', {'status':'I12_ISOLATED_CONTRACT_FIXTURE',
            'origin':str(origin),'stages':{'surface':report},'commands':recorder.calls})
        new = loadmat(root/'surface/config.mat')
        observations = []
        for workspace in workspaces:
            observations.append({'frame':workspace.name,
                'before':real_point_metrics(old, workspace),
                'after':real_point_metrics(new, root/'wass/workspaces'/workspace.name)})
        reference = core.reference_from_run(root,0)
        core.save_reference(reference,reference.calibration_id,root/'reference_plane.json',root,0)
        config['presentation']={'frozen_reference':{**reference.as_dict(),
            'calibration_identity':reference.calibration_id,'scientific_run':str(root),
            'reference_time_s':20.0 if label=='HomeTank' else 0.,
            'project_input_identity':core.project_input_identity(config)}}
        core.save_project(config,root/'gui_project.yaml')
        # Actual old bindings are rejected; never refit or rebind their coefficients.
        evidence = json.loads((REPO/'audit/evidence'/('HomeTank21.json' if label=='HomeTank' else 'Vieira0.json')).read_text('utf-8'))
        old_ref = {**evidence['reference'],**evidence['identity'],'scientific_run':str(origin)}
        try: core.reference_from_metadata(old_ref)
        except ValueError as e: rejection=str(e)
        else: raise AssertionError('Legacy reference accepted')
        all_results.append({'label':label,'origin':str(origin),'new_fixture':str(root),
            'same_real_wass_input_hashes':copy_hashes,'observations':observations,
            'new_identity':coordinates.identity(root),'new_reference':reference.as_dict(),
            'legacy_reference_rejection':rejection,
            'input_contract':report['plane']['coordinate_contract']})
        write_json(REPO/'fixes/evidence/I12_validation.json',all_results)
        print(label, observations[0]['before']['orthogonality_frobenius'],
            observations[0]['after']['orthogonality_frobenius'],flush=True)

if __name__=='__main__': main()
