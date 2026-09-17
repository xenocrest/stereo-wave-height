"""Real official-tool acceptance; no fake results and no core edits."""
import json
from pathlib import Path
import traceback
from production_app.application import ProjectService,source_snapshot,ExportService
from production_app.worker import execute
from production_app.storage import write_json

def main():
    tools=json.loads(Path('config/production_toolchain.json').read_text(encoding='utf-8'))
    directory=Path(tools['project_root'])/'acceptance-20260917'
    before=source_snapshot(tools)
    service=ProjectService(tools)
    if (directory/'project.json').exists():
        from production_app.storage import ProjectStore
        p=ProjectStore().open(directory/'project.json')
    else:
        p=service.create(directory,'V1 独立官方流程验收')
        for key in ['calibration_left','calibration_right','measurement_left','measurement_right']:
            service.input(p,key,tools['example'][key])
    records=[]
    def job(action,**args):
        r=execute(dict(project=str(directory/'project.json'),tools=tools,action=action,args=args))
        records.append(r)
        write_json(directory/'acceptance.json',dict(records=records,core_unchanged=before==source_snapshot(tools)))
        print(action,r['status'],r.get('error',''),flush=True)
        return r
    try:
        time=tools['example']['known_time_s']
        if job('detect',pattern=tools['example']['pattern'],interval=60,max_candidates=120)['status']!='PASS':return
        if job('calibrate',square_m=.02)['status']!='PASS':return
        if job('sync',window_end=30,wind_filter=True)['status']!='PASS':return
        ext=job('extrinsics',start_s=time,count=3)
        if ext['status']=='PASS':
            ref=job('reference',left_time=time,baseline_m=.07,area=[-.03,.22,.24,256])
        else:
            ref={'status':'FAIL'}
        if ref['status']!='PASS':
            # Explicit documented HomeTank-only fallback allowed by the task.
            job('load_calibration',source=tools['example']['historical_calibration'],provenance_record=tools['example'])
            if job('reference',left_time=time,baseline_m=.07,area=[-.03,.22,.24,256])['status']!='PASS':return
        result=job('reconstruct',left_time=time+.1,baseline_m=.07)
        if result['status']=='PASS':
            ExportService().run(result['result'],directory/'export')
            job('reconstruct',left_time=time+.1,baseline_m=.07)
    except Exception:
        print(traceback.format_exc(),flush=True)

if __name__=='__main__':main()
