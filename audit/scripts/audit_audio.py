"""Re-extract raw audio, apply the published TLCC wrapper, verify lag/sign."""
import sys,json,subprocess
from pathlib import Path
REPO=Path(__file__).resolve().parents[2];sys.path[:0]=[str(REPO),str(REPO/'src')]
from audit.scripts.inspect_artifacts import ROOT,RUNS,dump,digest
from tools.vieira_tlcc_sync import extract_and_filter_audio,write_official_praat_script

def main():
    s=json.loads((RUNS['HomeTank21'][0]/'sync/sync.json').read_text('utf-8'))
    folder=ROOT/'independent_audio';folder.mkdir(exist_ok=True)
    wavs=[]
    for i,key in enumerate(['left_video','right_video']):
        wav=folder/f'cam{i}_filtered.wav';extract_and_filter_audio(Path(s['ffmpeg']),Path(s[key]),wav,35);wavs.append(wav)
    script=folder/'crosscorrelate.praat';write_official_praat_script(script,0,30)
    records=[]
    for order in [wavs,list(reversed(wavs))]:
        argv=[s['praat'],'--run',str(script),*[str(p) for p in order],'0','30']
        r=subprocess.run(argv,capture_output=True)
        stdout=r.stdout.decode('utf-16-le').strip()
        lag=float(stdout.splitlines()[0]);records.append({'argv':argv,'returncode':r.returncode,'stdout':stdout,'lag_s':lag,'wav_hashes':[digest(p) for p in order]})
    dump('independent_audio_tlcc.json',{'original_offset_s':s['audio_lag_right_minus_left_s'],'fresh_raw_audio_tlcc':records,'physical_exposure_sync_proven':False,'scope':'audio TLCC and sign only; no independent audio-video latency or rolling-shutter measurement'})
    print(json.dumps(records,ensure_ascii=False))

if __name__=='__main__':main()
