"""Read-only input analysis; no reconstruction, no nominal-time stereo pairing."""
from pathlib import Path
from dataclasses import asdict
import json
import argparse
from calibration.capture_qa import scan_video
from synchronization.video_sync import extract_frame_brightness_pts, detect_frame_level_light_events

def main():
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['corners','events'],required=True);a=p.parse_args()
    root=Path('experiments/real_video/HomeTank_006/videos')
    out=Path('D:/stereo-wave-height-runs/HomeTank_006/input_analysis');out.mkdir(parents=True,exist_ok=True)
    for kind in (['calibration'] if a.mode=='corners' else ['calibration','wave']):
        for cam,role,rotation in [(0,'LEFT',180),(1,'RIGHT',0)]:
            path=root/kind/f'HomeTank_006_{kind}_cam{cam}_{role}.mp4'
            target=out/f'{kind}_{cam}_{a.mode}.json'
            if target.exists():continue
            if a.mode=='corners':
                detections,count,size=scan_video(path,camera=role,sample_hz=1,rotate_deg=rotation)
                result=dict(source=str(path),detections=detections,sampled=count,size=size)
            else:
                s=extract_frame_brightness_pts(path,ffmpeg_executable='D:/FormatFactory/ffmpeg.exe')
                result=dict(source=str(path),pts=s.pts.tolist(),timestamps_s=s.timestamps_s.tolist(),brightness=s.brightness.tolist(),events=[asdict(e) for e in detect_frame_level_light_events(s)])
            target.write_text(json.dumps(result),encoding='utf-8');print(target,flush=True)

if __name__=='__main__':main()
