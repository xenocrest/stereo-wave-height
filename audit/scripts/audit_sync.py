"""Enumerate original decoder PTS and identify actual extracted images by pixels."""
import json,re,subprocess,sys,hashlib
from pathlib import Path
import cv2,numpy as np
REPO=Path(__file__).resolve().parents[2]; sys.path[:0]=[str(REPO),str(REPO/'src')]
from audit.scripts.inspect_artifacts import RUNS,ROOT,dump
FFMPEG='D:/FormatFactory/ffmpeg.exe'

def run(argv,log):
    p=subprocess.run(argv,capture_output=True,text=True,encoding='utf-8',errors='replace')
    (ROOT/log).write_text(p.stdout+'\n'+p.stderr,encoding='utf-8')
    if p.returncode:raise RuntimeError(p.stderr[-1000:])
    return p.stderr

def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    s=json.loads((RUNS['HomeTank21'][0]/'sync/sync.json').read_text('utf-8'))
    offset=s['audio_lag_right_minus_left_s']; frames={}; videos={}
    for cam,key in [('cam0','left_video'),('cam1','right_video')]:
        video=s[key]; videos[cam]=video
        log=run([FFMPEG,'-hide_banner','-i',video,'-t','24','-vf','showinfo','-vsync','0','-f','null','-'],f'{cam}_absolute_pts.log')
        values=[(int(n),float(t),c) for n,t,c in re.findall(r'n:\s*(\d+)\s+pts:\s*-?\d+\s+pts_time:\s*([-+0-9.eE]+).*?checksum:([A-F0-9]+)',log)]
        if not values:raise RuntimeError('no absolute PTS found')
        frames[cam]=values
    records=[]
    for label,(root,frame) in RUNS.items():
        if not label.startswith('HomeTank'):continue
        row=json.loads((root/'sync/sync.json').read_text('utf-8'))['frame_mapping'][frame]
        entry={'label':label,'reported':row,'images':{}}
        actual={}
        for cam,key in [('cam0','left'),('cam1','right')]:
            request=row[key+'_requested_timestamp_s']; stored=cv2.imread(row[key+'_file'])
            nearby=sorted(frames[cam],key=lambda item:abs(item[1]-request))[:6]
            candidates=[]
            for index,pts,checksum in nearby:
                out=ROOT/f'{label}_{cam}_source_{index}.png'
                if not out.exists():
                    run([FFMPEG,'-hide_banner','-y','-i',videos[cam],'-vf',f"select='eq(n,{index})'",'-vsync','0','-frames:v','1',str(out)],f'{label}_{cam}_{index}.log')
                decoded=cv2.imread(str(out)); same=bool(np.array_equal(stored,decoded))
                candidates.append({'source_frame_index':index,'absolute_pts_s':pts,'checksum':checksum,'pixel_identical_to_stored':same})
                if same:actual[cam]=pts
            entry['images'][cam]=candidates
        if len(actual)!=2:raise RuntimeError(f'unidentified decoded image {label}')
        target=actual['cam0']+offset
        nearest=min(frames['cam1'],key=lambda item:abs(item[1]-target))
        entry.update(actual_left_pts_s=actual['cam0'],actual_right_pts_s=actual['cam1'],actual_residual_ms=1000*(actual['cam1']-actual['cam0']-offset),
                     nearest_right_for_fixed_left={'source_frame_index':nearest[0],'pts_s':nearest[1],'residual_ms':1000*(nearest[1]-target)},
                     source_intervals_near_target={cam:[round(1000*(frames[cam][i+1][1]-frames[cam][i][1]),4) for i in range(len(frames[cam])-1) if abs(frames[cam][i][1]-target)<0.05] for cam in frames})
        records.append(entry);print(label,json.dumps({k:entry[k] for k in ('actual_left_pts_s','actual_right_pts_s','actual_residual_ms','nearest_right_for_fixed_left')}))
    dump('sync_absolute_pts_and_frame_identity.json',{'offset_s':offset,'records':records,'method':'full timeline showinfo before output seek; six original frame candidates tested by exact decoded RGB equality; fixed actual left PTS'})

if __name__=='__main__':main()
