"""Use observed chess-cell parity to register complete board views."""
import json
from pathlib import Path
import cv2
from calibration.board_identity import parity_contrast,register_parity
from hometank006_target_release_diagnostic import orient_grid

root=Path('D:/stereo-wave-height-runs/HomeTank_006')
out=root/'registered_board';out.mkdir(exist_ok=True)
reference=None;result={}
for side,role in [(0,'LEFT'),(1,'RIGHT')]:
    source=json.loads((root/'partial_calibration_larger'/f'{role}_result.json').read_text())
    records=[r for r in source['records'] if r['found'] and sorted(r['pattern_size'])==[6,9]]
    path=Path('experiments/real_video/HomeTank_006/videos/calibration')/f'HomeTank_006_calibration_cam{side}_{role}.mp4'
    cap=cv2.VideoCapture(str(path));cap.set(cv2.CAP_PROP_ORIENTATION_AUTO,0)
    accepted=[]
    for r in records:
        cap.set(cv2.CAP_PROP_POS_MSEC,r['time_s']*1000);ok,frame=cap.read()
        if not ok:raise RuntimeError('cannot decode cached corner source')
        if side==0:frame=cv2.rotate(frame,cv2.ROTATE_180)
        gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
        grid=orient_grid(r).reshape(6,9,2);contrast=parity_contrast(gray,grid)
        if reference is None:reference=contrast
        p,flip=register_parity(grid,contrast,reference)
        accepted.append(dict(time_s=r['time_s'],pts_s=r['pts_s'],contrast=contrast,flipped=flip,corners=p.reshape(-1,2).tolist()))
    cap.release();result[role]=accepted
    print(role,[(r['time_s'],r['contrast'],r['flipped']) for r in accepted])
(out/'observations.json').write_text(json.dumps(dict(reference='LEFT_5s',reference_contrast=reference,observations=result)),encoding='utf-8')
