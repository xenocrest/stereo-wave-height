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
        result = stream_command(command, cwd=cwd, env=self._clean_env(), timeout=timeout)
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
    reference, cal_id = core.reference_from_metadata(binding)
    result = core.load_result(run, frame_id, reference, cal_id)
    image = core.measurement_image(result)
    np.savez_compressed(target / "view.npz", xyz=result.pop("xyz"),
        height=result.pop("height"), source=result.pop("source"), measurement=image)
    result.update(reference=binding, ply=str(Path(run) / "reconstruction" / "ply" / f"{frame_id:06d}.ply"))
    return result


def run(action, config_path, target):
    from app import core, worker, fixed_run
    from pipeline import run_pipeline
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
            left = extract_source_frame(Path(config["tools"]["ffmpeg"]),
                Path(config["sync"]["left_video"]), time_s, target / "left.png")
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
            return worker.run(action, config_path, target)
        if action in {"reference", "reconstruct"}:
            report = worker.run("reconstruct", config_path, target)
            root = Path(report["science_run"])
            binding = (official_reference(root, destination=target / "reference.json") if action == "reference" else
                       config["presentation"]["frozen_reference"])
            view = prepare_view(root, 0, binding, target)
            return dict(report, reference=binding, view=view)
    raise ValueError(f"Unknown action: {action}")


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
    write_json(args.run_dir / "result.json", result)
    print(json.dumps({"status": "PROCESS_COMPLETE", "run_dir": str(args.run_dir)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
