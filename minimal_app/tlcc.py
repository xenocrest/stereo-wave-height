"""Execute the author's unchanged wass_sync.py in a WAV-only sandbox.

Only path/config/encoding I/O is adapted. FIR and Praat script generation are
executed from the original source. P0 extraction/mapping stays in its old CLI.
"""
import argparse
import os
from pathlib import Path
import runpy
import shutil
import sys
from types import ModuleType
from unittest.mock import patch

from minimal_app.worker import stream_command, emit_sync_complete
from minimal_app.progress import emit
from pipeline.common import sha256, write_json
from tools import vieira_tlcc_sync as existing


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--official-source", required=True, type=Path)
    options, remaining = parser.parse_known_args()
    source = options.official_source.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Official wass_lowcost source missing: {source}")
    source_hash = sha256(source)
    pcm_files = []
    cached = None
    praat_path = None

    def pcm(ffmpeg, video, wav, duration_s):
        emit("audio_extract", side="left" if not pcm_files else "right", object=str(video), tool="FFmpeg",
            note="FFmpeg 正在运行；当前调用未提供可靠百分比")
        result = stream_command([ffmpeg, "-hide_banner", "-loglevel", "info", "-y", "-i", video,
            "-t", f"{duration_s:.6f}", "-vn", "-acodec", "pcm_s16le", "-ar", "48000", "-ac", "2", wav])
        if result.returncode:
            raise RuntimeError(f"FFmpeg PCM extraction failed ({result.returncode}): {result.stderr}")
        pcm_files.append(Path(wav))

    def author_script(path, start, end):
        nonlocal cached
        sandbox = Path(path).parent / "official_tlcc"
        sandbox.mkdir()
        for index, wav in enumerate(pcm_files):
            shutil.copy2(wav, sandbox / f"wav_file_{index}.wav")
        settings = ModuleType("setup_sync")
        settings.__dict__.update({key: value for key, value in runpy.run_path(
            str(source.with_name("setup_sync.py"))).items() if not key.startswith("__")})
        settings.__dict__.update(pathname=str(sandbox) + os.sep, op_system="linux", camera_id="",
            camera_type="gopro", video_format_input="mp4", video_format_output="mp4",
            audio_sync_cc_window_ini=start, audio_sync_cc_window_fin=end,
            audio_wind_filter="on", audio_stereo="on", count=0)

        def praat_io(command, *args, **kwargs):
            nonlocal cached
            if not isinstance(command, str) or not command.startswith("/usr/bin/praat --run crosscorrelate.praat "):
                raise RuntimeError(f"Unsupported upstream external command: {command!r}")
            emit("praat_tlcc", object=str(sandbox / "crosscorrelate.praat"), tool="Praat / wass_lowcost", note="官方工具未提供百分比")
            cached = stream_command([praat_path, "--run", sandbox / "crosscorrelate.praat",
                sandbox / "wav_file_0.wav", sandbox / "wav_file_1.wav", str(start), str(end)], cwd=sandbox)
            if cached.returncode:
                raise RuntimeError(f"Official Praat TLCC failed ({cached.returncode}): {cached.stderr}")
            cached.stdout = cached.stdout.replace("\x00", "")
            return cached.stdout.encode("utf-8")

        def reject_system(command):
            raise RuntimeError(f"Unexpected upstream shell command: {command}")

        previous = Path.cwd()
        emit("official_audio_filter", object=str(sandbox), tool="wass_lowcost", note="执行作者原文件；无官方百分比")
        try:
            with patch.dict(sys.modules, {"setup_sync": settings}), \
                 patch("subprocess.check_output", praat_io), patch("os.system", reject_system):
                print(f"OFFICIAL_SOURCE: {source} sha256={source_hash}", flush=True)
                namespace = runpy.run_path(str(source), run_name="__main__")
        finally:
            os.chdir(previous)
        if cached is None:
            raise RuntimeError("Official source did not call Praat")
        if sha256(source) != source_hash:
            raise RuntimeError("Official source changed during execution")
        shutil.copy2(sandbox / "crosscorrelate.praat", path)
        for index, wav in enumerate(pcm_files):
            shutil.copy2(sandbox / f"wav_file_{index}.wav", wav)
        write_json(sandbox / "invocation.json", dict(source=str(source), sha256=source_hash,
            setup_source_sha256=sha256(source.with_name("setup_sync.py")),
            raw_offset=namespace["results"][1][1], praat_argv=cached.args,
            adapter="WAV-only input, setup config, Windows Praat path/stdout; P0 source extraction retained"))

    def checked(command, **kwargs):
        if cached is not None and str(command[0]) == praat_path and "--run" in command:
            emit("parse_sync_offset", object=str(command[2]), tool="现有同步 wrapper")
            return cached  # Already executed once by the original author script.
        result = stream_command(command, **kwargs)
        if result.returncode:
            raise RuntimeError(f"External tool failed ({result.returncode}): {result.stderr}")
        return result

    # The old CLI parser and P0 run/extract_source_frame implementation are reused.
    praat_path = remaining[remaining.index("--praat") + 1]
    sys.argv = [str(source), *remaining]
    original_extract, original_run = existing.extract_source_frame, existing.run

    def frame_io(ffmpeg, video, timestamp_s, output):
        emit("source_frame", side="left" if Path(output).parent.name == "cam0" else "right",
            object=str(video), tool="FFmpeg", note="提取实际源帧；无可靠百分比")
        result = original_extract(ffmpeg, video, timestamp_s, output)
        emit("source_frame", side="left" if Path(output).parent.name == "cam0" else "right",
            object=str(output), counts=dict(source_frame_index=result["source_frame_index"], actual_pts_s=result["actual_source_pts_s"]),
            note="已读取真实源帧身份")
        return result

    def reported_run(args):
        result = original_run(args)
        emit_sync_complete(result)
        return result

    with patch.object(existing, "extract_and_filter_audio", pcm), \
         patch.object(existing, "write_official_praat_script", author_script), \
         patch.object(existing, "run_checked", checked), \
         patch.object(existing, "extract_source_frame", frame_io), patch.object(existing, "run", reported_run):
        existing.main()


if __name__ == "__main__":
    main()
