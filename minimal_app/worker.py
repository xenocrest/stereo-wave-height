"""CLI glue and live logging. Delegates science to existing adapters/tools."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from unittest.mock import patch

from pipeline.common import CommandRecorder, StageFailure, write_json
from minimal_app.progress import emit


def stream_command(argv, *, cwd=None, env=None, timeout=None):
    """Preserve both channels for parsers while forwarding bytes immediately."""
    command = list(map(str, argv))
    print("COMMAND: " + subprocess.list2cmdline(command), flush=True)
    with subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)) as process:
        captured = {"stdout": [], "stderr": []}

        def pump(channel):
            source, target = getattr(process, channel), getattr(sys, channel)
            while chunk := source.read1(65536):
                captured[channel].append(chunk)
                target.buffer.write(chunk)
                target.buffer.flush()

        threads = [threading.Thread(target=pump, args=(channel,), daemon=True)
                   for channel in captured]
        for thread in threads:
            thread.start()
        try:
            code = process.wait(timeout=timeout)
        except BaseException:
            process.kill()
            process.wait()
            raise
        finally:
            for thread in threads:
                thread.join()
    return subprocess.CompletedProcess(command, code,
        b"".join(captured["stdout"]).decode("utf-8", "replace"),
        b"".join(captured["stderr"]).decode("utf-8", "replace"))


class LiveRecorder(CommandRecorder):
    def run(self, stage, argv, *, cwd=None, check=True, timeout=None):
        command = list(map(str, argv))
        # Route only this known existing TLCC CLI to the author-file adapter.
        if len(command) > 1 and Path(command[1]).name == "vieira_tlcc_sync.py":
            source = os.environ["MINIMAL_WASS_LOWCOST_SOURCE"]
            command = [command[0], "-u", "-m", "minimal_app.tlcc",
                       "--official-source", source, *command[2:]]
        index = len(self.calls)
        log = self.root / f"{index:03d}_{stage}.log"
        started = time.perf_counter()
        print(f"STAGE: {stage}", flush=True)
        subject = (command[command.index("--video") + 1] if "--video" in command else
                   cwd or next((value for value in command[1:] if Path(value).is_absolute()), command[-1]))
        emit(stage, object=str(subject), tool=Path(command[0]).name, note="官方工具未提供百分比；原始输出见实时日志")
        environment = self._clean_env()
        if stage in {"opencv_calibration_left", "opencv_calibration_right"}:
            environment["MINIMAL_PROGRESS_SIDE"] = stage.rsplit("_", 1)[-1]
        result = stream_command(command, cwd=cwd, env=environment, timeout=timeout)
        record = dict(stage=stage, argv=command, cwd=str(cwd) if cwd else None,
            return_code=result.returncode, elapsed_s=time.perf_counter() - started, log=str(log))
        self.calls.append(record)
        log.write_text("COMMAND: " + subprocess.list2cmdline(command) +
            f"\nCWD: {record['cwd']}\nRETURN_CODE: {result.returncode}\nELAPSED_S: {record['elapsed_s']}\n\n" +
            "STDOUT\n" + result.stdout + "\n\nSTDERR\n" + result.stderr, encoding="utf-8")
        if check and result.returncode:
            raise StageFailure(stage, f"{stage} failed with return code {result.returncode}; see {log}")
        return record


def official_reference(run, frame_id=0, destination=None):
    """Serialize the official setup's Z=0 plane; never fit a new plane."""
    from app import core, coordinates
    from pipeline.instantaneous_validation.schemas import ReferencePlane
    from pipeline.instantaneous_validation.load_vision import frame_times
    from pipeline.common import sha256
    root = Path(run)
    ids = coordinates.identity(root)
    raw_plane = root / "wass" / "workspaces" / f"{frame_id:06d}_wd" / "plane.txt"
    if not raw_plane.is_file():
        raise FileNotFoundError(raw_plane)
    reference = coordinates.bind(ReferencePlane(
        f"official_wass_plane_{ids['coordinate_frame_id'][:16]}", (0., 0., 1.), 0.,
        "designated_static_water_frame", ids["coordinate_system"]), ids)
    value = reference.as_dict()
    value.update(calibration_identity=core.calibration_identity(root), scientific_run=str(root.resolve()),
        source_frame_id=frame_id, frame_id=frame_id, timestamp=frame_times(root)[frame_id])
    value.update(reference_definition="OFFICIAL_WASS_PLANE_GRID_Z0",
        official_plane_file=str(raw_plane), official_plane_sha256=sha256(raw_plane),
        reference_time_s=frame_times(root)[frame_id], physically_validated=False)
    if destination is not None:
        write_json(destination, value)
    return value


def prepare_view(run, frame_id, binding, target):
    """Read existing result interfaces; prepare H once, outside hover/UI."""
    import numpy as np
    from app import core
    emit("read_results", object=str(run), note="读取既有结果；不改变 XYZ/H")
    reference, cal_id = core.reference_from_metadata(binding)
    result = core.load_result(run, frame_id, reference, cal_id)
    emit("measurement_image", object=str(result.get("measurement_image", run)))
    image = core.measurement_image(result)
    emit("serialize_view", object=str(target / "view.npz"))
    np.savez_compressed(target / "view.npz", xyz=result.pop("xyz"),
        height=result.pop("height"), source=result.pop("source"), measurement=image)
    result.update(reference=binding, ply=str(Path(run) / "reconstruction" / "ply" / f"{frame_id:06d}.ply"))
    return result


def run(action, config_path, target):
    from app import core, worker, fixed_run
    from pipeline import run_pipeline
    os.environ["MINIMAL_PROGRESS_TASK"] = action
    emit("load_config", object=str(config_path))
    config = core.read_project(config_path)
    if config.get("wass", {}).get("fallback_calibration") and not config["wass"].get("allow_extrinsic_fallback", False):
        raise ValueError("EXTRINSICS_FALLBACK requires explicit allow_extrinsic_fallback=true")
    os.environ["MINIMAL_WASS_LOWCOST_SOURCE"] = str(Path(config["tools"]["wass_lowcost"]) / "wass_sync.py")
    target.mkdir(parents=True, exist_ok=True)
    if action == "preview":
        from tools.vieira_tlcc_sync import extract_source_frame
        from tools import vieira_tlcc_sync
        def checked(argv, **kwargs):
            result = stream_command(argv, **kwargs)
            if result.returncode:
                raise RuntimeError(f"FFmpeg failed ({result.returncode}): {result.stderr}")
            return result
        time_s, offset = config["minimal"]["time_s"], config["minimal"]["offset_s"]
        with patch.object(vieira_tlcc_sync, "run_checked", checked):
            emit("source_frame", side="left", tool="FFmpeg", object=config["sync"]["left_video"], note="FFmpeg 正在运行；无可靠百分比")
            left = extract_source_frame(Path(config["tools"]["ffmpeg"]),
                Path(config["sync"]["left_video"]), time_s, target / "left.png")
            emit("source_frame", side="right", tool="FFmpeg", object=config["sync"]["right_video"], note="FFmpeg 正在运行；无可靠百分比")
            right = extract_source_frame(Path(config["tools"]["ffmpeg"]),
                Path(config["sync"]["right_video"]), time_s + offset, target / "right.png")
        return dict(requested_time_s=time_s, actual_left_source_pts=left["actual_source_pts_s"],
            actual_right_source_pts=right["actual_source_pts_s"],
            stereo_pair_residual_ms=(right["actual_source_pts_s"] - left["actual_source_pts_s"] - offset) * 1000,
            left=left, right=right, left_file=str(target / "left.png"), right_file=str(target / "right.png"))
    if action == "view":
        data = config["minimal"]
        run_root = Path(data["run"])
        binding = data.get("reference") or official_reference(run_root, data["frame_id"])
        return prepare_view(run_root, data["frame_id"], binding, target)
    with patch.object(worker, "CommandRecorder", LiveRecorder), \
         patch.object(run_pipeline, "CommandRecorder", LiveRecorder), \
         patch.object(fixed_run, "CommandRecorder", LiveRecorder):
        if action in {"calibrate", "sync"}:
            result = worker.run(action, config_path, target)
            if action == "calibrate":
                counts = {}
                for side, label in (("left", "左相机"), ("right", "右相机")):
                    report = result.get(side, {})
                    for key, name in (("complete_detection_count", "完整棋盘"), ("selected_view_count", "采用视图"), ("rms_px", "RMS (px)")):
                        if key in report:
                            counts[label + name] = report[key]
                emit("calibration_complete", counts=counts, note="左右结果及官方配置已保存")
            else:
                emit_sync_complete(result)
            return result
        if action in {"reference", "reconstruct"}:
            report = worker.run("reconstruct", config_path, target)
            root = Path(report["science_run"])
            emit("save_reference" if action == "reference" else "read_results", object=str(root))
            binding = (official_reference(root, destination=target / "reference.json") if action == "reference" else
                       config["presentation"]["frozen_reference"])
            view = prepare_view(root, 0, binding, target)
            return dict(report, reference=binding, view=view)
    raise ValueError(f"Unknown action: {action}")


def emit_sync_complete(result):
    frame = result.get("frame_mapping", [{}])[0]
    emit("sync_complete", counts={key: value for key, value in
        dict(offset_s=result.get("audio_lag_right_minus_left_s"), residual_ms=frame.get("stereo_pair_residual_ms")).items() if value is not None})


def main():
    # The GUI assigns the Windows job before granting access to scientific tools.
    if os.environ.get("MINIMAL_PROCESS_GATE") == "1" and sys.stdin.readline().strip() != "RUN":
        raise SystemExit("Process-tree gate was not released")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("calibrate", "sync", "preview", "reference", "reconstruct", "view"))
    parser.add_argument("config", type=Path)
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    result = run(args.action, args.config, args.run_dir)
    # Keep a completed calibration/sync summary; other actions finish in the viewer.
    write_json(args.run_dir / "result.json", result)
    print(json.dumps({"status": "PROCESS_COMPLETE", "run_dir": str(args.run_dir)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
