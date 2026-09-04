"""Audio-only timing evidence; never a replacement for visual sync validation."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import numpy as np
from scipy import signal

from process_utils import hidden_process_kwargs


def read_audio(video: Path, ffmpeg: Path, sample_rate: int = 12000) -> tuple[np.ndarray, float]:
    """Decode mono PCM and retain the first audio presentation timestamp."""
    command = [str(ffmpeg), '-hide_banner', '-loglevel', 'info', '-copyts', '-i', str(video),
               '-map', '0:a:0', '-vn', '-af', f'aresample={sample_rate},ashowinfo',
               '-ac', '1', '-ar', str(sample_rate), '-f', 'f32le', 'pipe:1']
    result = subprocess.run(command, capture_output=True, check=False, **hidden_process_kwargs())
    log = result.stderr.decode('utf-8', errors='replace')
    if result.returncode:
        raise RuntimeError(f'audio decode failed: {log[-1500:]}')
    matches = re.findall(r'pts_time:([-+0-9.eE]+)', log)
    if not matches:
        raise ValueError('audio PTS missing')
    audio = np.frombuffer(result.stdout, dtype='<f4').astype(float)
    if len(audio) < sample_rate or not np.all(np.isfinite(audio)):
        raise ValueError('audio missing or invalid')
    return audio, float(matches[0])


def lag_seconds(left: np.ndarray, right: np.ndarray, sample_rate: int, maximum_lag_s: float) -> float:
    """Right-minus-left sample-time lag of an audio event (not frame index)."""
    x=np.asarray(left,float);y=np.asarray(right,float)
    if x.ndim!=1 or y.ndim!=1 or min(len(x),len(y))<2 or sample_rate<=0:
        raise ValueError('nonempty one-dimensional audio and positive sample rate required')
    x=x-x.mean();y=y-y.mean()
    if min(np.linalg.norm(x),np.linalg.norm(y))<1e-9:raise ValueError('silent audio')
    corr=signal.correlate(y,x,mode='full',method='fft')
    lags=signal.correlation_lags(len(y),len(x),mode='full')
    valid=np.abs(lags)<=maximum_lag_s*sample_rate
    return float(lags[valid][np.argmax(corr[valid])]/sample_rate)


def analyze_audio_pair(left_path: Path, right_path: Path, ffmpeg: Path) -> dict:
    fs=12000
    left,lp=read_audio(left_path,ffmpeg,fs);right,rp=read_audio(right_path,ffmpeg,fs)
    sos=signal.butter(4,[300,3500],btype='bandpass',fs=fs,output='sos')
    left=signal.sosfiltfilt(sos,left);right=signal.sosfiltfilt(sos,right)
    coarse=lag_seconds(left,right,fs,5.)
    windows=[]
    for start in np.arange(5.,min(len(left),len(right))/fs-10,10.):
        x=left[round(start*fs):round((start+5)*fs)]
        rs=start+coarse
        y=right[round(rs*fs):round((rs+5)*fs)]
        if len(y)!=len(x):continue
        delta=lag_seconds(x,y,fs,.15);n=round(delta*fs)
        xa=x[:len(x)-n] if n>=0 else x[-n:]
        ya=y[n:] if n>=0 else y[:len(y)+n]
        correlation=float(np.corrcoef(xa,ya)[0,1])
        windows.append(dict(left_audio_time_s=float(start+lp),right_minus_left_s=float(coarse+delta+rp-lp),correlation=correlation))
    good=[w for w in windows if w['correlation']>=.6]
    offsets=np.array([w['right_minus_left_s'] for w in good])
    b=float(np.median(offsets)) if len(good)>=3 else None
    residual=float(np.max(np.abs(offsets-b))) if b is not None else None
    return dict(status='AUDIO_TIMELINE_ALIGNED_PENDING_VISUAL_CHECK' if b is not None and residual<=.01 else 'AUDIO_SYNC_NOT_ESTABLISHED',
                offset_s=b,maximum_window_residual_s=residual,windows=windows,good_window_count=len(good),
                left_audio_start_pts_s=lp,right_audio_start_pts_s=rp,video_frame_sync_established=False,
                warning='Audio/video latency and acoustic propagation not independently measured; visual verification required.')
