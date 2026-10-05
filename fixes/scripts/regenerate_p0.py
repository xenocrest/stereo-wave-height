"""Fresh official P0 acceptance runs, executed AFTER the full test suite."""
import copy, json, os, sys
from pathlib import Path
os.environ.pop('QT_QPA_PLATFORM',None)
REPO=Path(__file__).resolve().parents[2];sys.path[:0]=[str(REPO),str(REPO/'src')]
from app import core, fixed_run
from pipeline.common import write_json
from pipeline.run_pipeline import run_pipeline

ROOT=Path('D:/stereo-wave-height-runs/reconstruction-quality-p0-20261001')

def main():
    # Reuse corrected, certified official setup; never reuse old reference.
    config=core.read_project(ROOT/'I12_contract_fixture/HomeTank/gui_project.yaml')
    config['sync'].update(start_s=20.,output_fps=1.,frame_count=1)
    print('Fresh HomeTank 20s reference source',flush=True)
    origin=ROOT/'final/HomeTank20_reference'
    fixed_run.run(config,origin)
    reference=core.reference_from_run(origin,0)
    core.save_reference(reference,reference.calibration_id,ROOT/'final/reference_plane.json',origin,0)
    binding={**reference.as_dict(),'calibration_identity':reference.calibration_id,
        'scientific_run':str(origin),'source_frame_id':0,'reference_time_s':20.,
        'project_input_identity':core.project_input_identity(config)}
    config['presentation']['frozen_reference']=binding
    core.save_project(config,ROOT/'final/gui_project.yaml')
    rows=[]
    for target in (21,22,23):
        run_config=copy.deepcopy(config)
        run_config['sync'].update(start_s=float(target),output_fps=1.,frame_count=1)
        directory=ROOT/'final'/f'HomeTank{target}'
        print(f'Fresh HomeTank {target}s official prepare/stereo/grid/ncplot',flush=True)
        report=fixed_run.run(run_config,directory)
        rows.append({'label':f'HomeTank{target}','root':str(directory),'status':report['status'],
            'frame_id':0,'reference':binding,
            'sync':json.loads((directory/'sync/sync.json').read_text('utf-8'))['frame_mapping'][0]})
        write_json(REPO/'fixes/evidence/P0_regenerated_runs.json',rows)
    print('Fresh Vieira official sample: prepare/match/autocalibrate/stereo/setup/grid/ncplot',flush=True)
    vieira=core.read_project(REPO/'examples/vieira_official.yaml')
    project=ROOT/'final/vieira_project.yaml';core.save_project(vieira,project)
    directory=ROOT/'final/Vieira'
    report=run_pipeline(project,str(directory))
    reference=core.reference_from_run(directory,0)
    core.save_reference(reference,reference.calibration_id,ROOT/'final/vieira_reference_plane.json',directory,0)
    rows.append({'label':'Vieira0','root':str(directory),'status':report['status'],
        'frame_id':0,'reference':{**reference.as_dict(),'calibration_identity':reference.calibration_id,
            'scientific_run':str(directory),'reference_time_s':0.,'source_frame_id':0}})
    write_json(REPO/'fixes/evidence/P0_regenerated_runs.json',rows)
    print('All requested official runs complete',flush=True)

if __name__=='__main__':main()
