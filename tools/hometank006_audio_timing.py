"""Record independent audio timing evidence for each new video pair."""
from pathlib import Path
import json
from synchronization.audio_sync import analyze_audio_pair

root=Path('experiments/real_video/HomeTank_006/videos')
out=Path('D:/stereo-wave-height-runs/HomeTank_006/audio_timing');out.mkdir(parents=True,exist_ok=True)
for kind in ['calibration','wave']:
    result=analyze_audio_pair(root/kind/f'HomeTank_006_{kind}_cam0_LEFT.mp4',root/kind/f'HomeTank_006_{kind}_cam1_RIGHT.mp4',Path('D:/FormatFactory/ffmpeg.exe'))
    (out/f'{kind}.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(kind,json.dumps(result),flush=True)
