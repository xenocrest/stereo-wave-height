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
import re
import subprocess
from fractions import Fraction
import math
import sys
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.camera_image import CANONICAL_CAMERA_IMAGE_ORIENTATION, ffmpeg_orientation_args

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


def parse_source_frame(log: str) -> dict:
    """Join selected output PTS to its decoder index before the select filter."""
    time_base = re.search(r'\[showinfo@source[^\]]*\].*config in time_base:\s*(\d+/\d+)', log)
    selected = re.search(r'\[showinfo@selected[^\]]*\].*\bn:\s*0\s+pts:\s*(-?\d+)\s+pts_time:\s*([-+0-9.eE]+)', log)
    if time_base is None or selected is None:
        raise RuntimeError("FFmpeg did not identify the selected source frame/time base")
    ticks = int(selected.group(1))
    sources = re.findall(r'\[showinfo@source[^\]]*\].*\bn:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:\s*([-+0-9.eE]+)', log)
    matches = [(int(n), int(pts)) for n, pts, _ in sources if int(pts) == ticks]
    if len(matches) != 1:
        raise RuntimeError("Selected source PTS is missing or ambiguous; frame identity unavailable")
    return {"source_frame_index": matches[0][0], "source_pts_ticks": ticks,
            "source_time_base": time_base.group(1),
            "actual_source_pts_s": float(ticks * Fraction(time_base.group(1))),
            "timestamp_basis": "ABSOLUTE_SOURCE_PTS_COPYTS; decoded index before select; selected output joined by integer PTS"}


def extract_source_frame(ffmpeg: Path, video: Path, timestamp_s: float, output: Path) -> dict:
    if not math.isfinite(timestamp_s) or timestamp_s < 0:
        raise ValueError("Requested source timestamp must be finite and nonnegative")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Decode the original timeline, preserve PTS, and select the first source
    # frame at/after the request. No output seek, timestamp rebasing, or fps filter.
    filters = f"showinfo@source,select='gte(t,{timestamp_s:.9f})',showinfo@selected"
    argv = [str(ffmpeg), "-hide_banner", "-loglevel", "info", "-y", "-copyts", *ffmpeg_orientation_args(), "-i", str(video),
            "-vf", filters, "-frames:v", "1", "-vsync", "0", str(output)]
    completed = run_checked(
        argv
    )
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError(f"FFmpeg did not create frame: {output}")
    identified = parse_source_frame(completed.stderr)
    logs = (output.parent.parent if output.parent.name in {"cam0", "cam1"} else output.parent) / "frame_identification"
    logs.mkdir(parents=True, exist_ok=True)
    log_path = logs / f"{output.parent.name}_{output.stem}.log"
    log_path.write_text(completed.stderr, encoding="utf-8")
    return {**identified, "requested_timestamp_s": timestamp_s,
            "canonical_camera_image_orientation": CANONICAL_CAMERA_IMAGE_ORIENTATION,
            "extraction_argv": argv, "identification_log": str(log_path),
            "decoded_png_sha256": sha256(output)}


def extract_frame(ffmpeg: Path, video: Path, timestamp_s: float, output: Path) -> float:
    """Compatibility API; actual PTS comes from the identified original frame."""
    return extract_source_frame(ffmpeg, video, timestamp_s, output)["actual_source_pts_s"]


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
        left_source = extract_source_frame(ffmpeg, left, left_time, left_name)
        right_source = extract_source_frame(ffmpeg, right, right_time, right_name)
        left_actual = left_source["actual_source_pts_s"]
        right_actual = right_source["actual_source_pts_s"]
        mapping.append(
            {
                "output_index": index,
                "left_requested_timestamp_s": left_time,
                "right_requested_timestamp_s": right_time,
                "left_actual_timestamp_s": left_actual,
                "right_actual_timestamp_s": right_actual,
                "requested_timestamp": left_time,
                "actual_left_source_pts": left_actual,
                "actual_right_source_pts": right_actual,
                "left_source_frame_index": left_source["source_frame_index"],
                "right_source_frame_index": right_source["source_frame_index"],
                "left_source_frame": left_source,
                "right_source_frame": right_source,
                "TLCC_offset": offset_s,
                "pair_residual_s": right_actual - left_actual - offset_s,
                "stereo_pair_residual_ms": (right_actual - left_actual - offset_s) * 1000,
                "timestamp_basis": "ABSOLUTE_SOURCE_PTS_COPYTS",
                "right_minus_left_s": offset_s,
                "left_file": str(left_name),
                "right_file": str(right_name),
            }
        )
    result = {
        "schema_version": "2.0",
        "canonical_camera_image_orientation": CANONICAL_CAMERA_IMAGE_ORIENTATION,
        "requested_timestamp_definition": "target on original source PTS timeline; select first decoded source frame at/after target",
        "pair_residual_definition": "right_source_pts - left_source_pts - TLCC_offset; seconds (stereo_pair_residual_ms is x1000)",
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
        "source_vfr_cfr_note": "Both raw containers retain their original timing; frames are newly sampled by timestamp after TLCC. Actual selected decoded PTS and left/right residual are recorded per output pair.",
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
