"""Separate-process job endpoint. Never a web server."""
import argparse
import json
from pathlib import Path
import traceback
from .application import (CalibrationService,SyncService,ReferenceService,ReconstructionService,ExportService)
from .storage import ProjectStore,write_json


def execute(request):
    project = ProjectStore().open(request['project'])
    action,tools,args = request['action'],request['tools'],request.get('args',{})
    classes = {'detect':CalibrationService,'calibrate':CalibrationService,'load_calibration':CalibrationService,
               'extrinsics':CalibrationService,'sync':SyncService,'reference':ReferenceService,
               'load_reference':ReferenceService,'reconstruct':ReconstructionService}
    service = classes[action](project,tools,lambda s:print(s,flush=True))
    try:
        if action=='detect':
            result = service.detect(**args)
        elif action=='calibrate':
            result = service.calibrate(**args)
        elif action=='load_calibration':
            result = service.load_existing(**args)
        elif action=='extrinsics':
            result = service.autocalibrate(**args)
        elif action=='sync':
            result = service.run(**args)
        elif action=='reference':
            result = service.establish(**args)
        elif action=='load_reference':
            result = service.load_existing(**args)
        else:
            result = service.run(**args)
        return dict(status='PASS',action=action,result=result,job=str(service.job))
    except Exception as error:
        write_json(service.job/'calls.json',service.runner.calls)
        (service.job/'error.log').write_text(traceback.format_exc(),encoding='utf-8')
        return dict(status='FAIL',action=action,error=f'{type(error).__name__}: {error}',job=str(service.job))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--request',required=True)
    a = parser.parse_args()
    request_path = Path(a.request)
    result = execute(json.loads(request_path.read_text(encoding='utf-8')))
    write_json(request_path.with_suffix('.result.json'),result)
    print(json.dumps(result,ensure_ascii=False),flush=True)
    return 0 if result['status']=='PASS' else 1


if __name__=='__main__':
    raise SystemExit(main())
