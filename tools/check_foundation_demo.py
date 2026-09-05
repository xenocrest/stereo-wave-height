"""Real model acceptance through the same GUI runner; no WASS calls."""
import argparse
import json
from pathlib import Path
from application.backend_runner import FrozenBackendRunner
from application.visualization import DenseMeasurementView


def main():
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);a=p.parse_args()
    config=json.loads(Path(a.config).read_text(encoding='utf-8'))
    root=Path(config['repository']);out=Path(config['output']);out.mkdir(parents=True,exist_ok=False)
    runner=FrozenBackendRunner(root,Path(config['template']))
    records=[];ref=None
    for mode,target in [('reference',config['reference_time_s']),('measurement',config['measurement_time_s'])]:
        record=runner.run(Path(config['left']),Path(config['right']),target,out/mode,out/'acceptance.log',
            Path(config['calibration']),config['roi'],solve_mode=mode,reference_artifact=ref)
        ref=record.reference_artifact_path
        view=DenseMeasurementView(record.dense_npz_path,record.pixel_xyz_path,Path(config['mapping']))
        x,y=config['query_pixel'];query=view.query(x,y)
        records.append({'mode':mode,'result':str(record.unified_result_path),'query':query.__dict__,
            'summary':record.summary_metadata})
    (out/'acceptance.json').write_text(json.dumps(records,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps([{'mode':r['mode'],'query':r['query'],'dense':r['summary']['dense_height']} for r in records],indent=2))


if __name__=='__main__':main()
