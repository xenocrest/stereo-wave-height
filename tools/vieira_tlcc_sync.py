"""Run the Vieira/wass_lowcost audio TLCC and extract new synchronized frames.

Cross-correlation itself is executed by Praat using the script emitted by the
official wass_lowcost implementation.  FFmpeg performs audio and frame
extraction.  This file fixes only the official script's platform/path handling
and records the exact time mapping; it does not introduce a new synchronizer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
from scipy import signal
from scipy.io import wavfile


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_checked(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True, encoding="utf-8", errors="replace")
    if completed.returncode:
        raise RuntimeError(f"command failed ({completed.returncode}): {' '.join(command)}\n{completed.stdout}\n{completed.stderr}")
    return completed


def extract_and_filter_audio(ffmpeg: Path, video: Path, wav: Path, duration_s: float) -> None:
    run_checked(
        [str(ffmpeg), "-hide_banner", "-loglevel", "error", "-y", "-i", str(video), "-t", f"{duration_s:.6f}", "-vn", "-acodec", "pcm_s16le", "-ar", "48000", "-ac", "2", str(wav)]
    )
    sample_rate, samples = wavfile.read(wav)
    if samples.ndim != 2 or samples.shape[1] < 2:
        raise ValueError(f"stereo audio required by configured wind filter: {wav}")
    coefficients = signal.firwin(101, cutoff=1000, fs=sample_rate, pass_zero=False)
    filtered = np.column_stack([signal.lfilter(coefficients, [1.0], samples[:, channel]) for channel in range(2)])
    wavfile.write(wav, sample_rate, filtered.astype(np.int16))


def write_official_praat_script(path: Path, window_start_s: float, window_end_s: float) -> None:
    path.write_text(
        "\n".join(
            [
                "form Cross Correlate two Sounds",
                "    sentence Input_sound_1",
                "    sentence Input_sound_2",
                f"    real start_time {window_start_s}",
                f"    real end_time {window_end_s}",
                "endform",
                "Open long sound file... 'input_sound_1$'",
                f"Extract part: {window_start_s},{window_end_s},\"no\"",
                "Extract one channel... 1",
                "sound1 = selected(\"Sound\")",
                "Open long sound file... 'input_sound_2$'",
                f"Extract part: {window_start_s},{window_end_s},\"no\"",
                "Extract one channel... 1",
                "sound2 = selected(\"Sound\")",
                "select sound1",
                "plus sound2",
                "Cross-correlate: \"peak 0.99\", \"zero\"",
                "offset = Get time of maximum: 0, 0, \"Sinc70\"",
                "writeInfoLine: 'offset'",
                "",
            ]
        ),
        encoding="utf-8",
    )


def extract_frame(ffmpeg: Path, video: Path, timestamp_s: float, output: Path) -> None:
    run_checked(
        [str(ffmpeg), "-hide_banner", "-loglevel", "error", "-y", "-i", str(video), "-ss", f"{timestamp_s:.9f}", "-frames:v", "1", "-vsync", "0", str(output)]
    )
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError(f"FFmpeg did not create frame: {output}")


def run(args: argparse.Namespace) -> dict[str, object]:
    left = Path(args.left).resolve()
    right = Path(args.right).resolve()
    ffmpeg = Path(args.ffmpeg).resolve()
    praat = Path(args.praat).resolve()
    output = Path(args.output).resolve()
    cam0, cam1 = output / "cam0", output / "cam1"
    cam0.mkdir(parents=True, exist_ok=True)
    cam1.mkdir(parents=True, exist_ok=True)

    audio_duration = args.window_end_s + max(5.0, abs(args.start_s))
    wav0, wav1 = output / "wav_file_0_filtered.wav", output / "wav_file_1_filtered.wav"
    extract_and_filter_audio(ffmpeg, left, wav0, audio_duration)
    extract_and_filter_audio(ffmpeg, right, wav1, audio_duration)
    script = output / "crosscorrelate.praat"
    write_official_praat_script(script, args.window_start_s, args.window_end_s)
    correlation = run_checked(
        [str(praat), "--run", str(script), str(wav0), str(wav1), str(args.window_start_s), str(args.window_end_s)],
        cwd=output,
    )
    # Current Windows Praat writes UTF-16LE bytes to stdout; subprocess' UTF-8
    # replacement path preserves ASCII digits interleaved with NUL characters.
    praat_stdout = correlation.stdout.replace("\x00", "")
    first_line = next((line.strip() for line in praat_stdout.splitlines() if line.strip()), "")
    try:
        offset_s = float(first_line)
    except ValueError as error:
        raise RuntimeError(f"Praat did not return a numeric TLCC offset: {correlation.stdout!r} {correlation.stderr!r}") from error

    mapping = []
    for index in range(args.frame_count):
        left_time = args.start_s + index / args.output_fps
        # Praat defines cross-corr(f,g)(tau) = integral f(t)g(t+tau)dt.
        right_time = left_time + offset_s
        left_name, right_name = cam0 / f"{index:06d}.png", cam1 / f"{index:06d}.png"
        extract_frame(ffmpeg, left, left_time, left_name)
        extract_frame(ffmpeg, right, right_time, right_name)
        mapping.append(
            {
                "output_index": index,
                "left_requested_timestamp_s": left_time,
                "right_requested_timestamp_s": right_time,
                "right_minus_left_s": offset_s,
                "left_file": str(left_name),
                "right_file": str(right_name),
            }
        )
    result = {
        "schema_version": "1.0",
        "method": "wass_lowcost TLCC: FFmpeg PCM 48 kHz stereo; 101-tap 1000 Hz FIR high-pass; Praat peak cross-correlation/Sinc70 maximum",
        "praat_cross_correlation_definition": "cross_corr(left,right)(tau)=integral left(t)*right(t+tau)dt; paired right_time=left_time+tau",
        "left_video": str(left),
        "left_sha256": sha256(left),
        "right_video": str(right),
        "right_sha256": sha256(right),
        "ffmpeg": str(ffmpeg),
        "praat": str(praat),
        "praat_sha256": sha256(praat),
        "window_start_s": args.window_start_s,
        "window_end_s": args.window_end_s,
        "audio_lag_right_minus_left_s": offset_s,
        "nominal_frame_lag_at_60fps": offset_s * 60.0,
        "output_sampling_fps": args.output_fps,
        "output_frame_count": args.frame_count,
        "source_vfr_cfr_note": "Both raw containers retain their original timing; frames are newly sampled by timestamp after TLCC, so no historical frame indices or synchronization are reused.",
        "frame_mapping": mapping,
    }
    (output / "sync_result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--left", required=True)
    parser.add_argument("--right", required=True)
    parser.add_argument("--ffmpeg", required=True)
    parser.add_argument("--praat", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--window-start-s", type=float, default=0.0)
    parser.add_argument("--window-end-s", type=float, default=30.0)
    parser.add_argument("--start-s", type=float, default=10.0)
    parser.add_argument("--output-fps", type=float, default=2.0)
    parser.add_argument("--frame-count", type=int, default=20)
    args = parser.parse_args()
    result = run(args)
    print(json.dumps({key: result[key] for key in ("audio_lag_right_minus_left_s", "nominal_frame_lag_at_60fps", "output_sampling_fps", "output_frame_count")}, indent=2))


if __name__ == "__main__":
    main()
