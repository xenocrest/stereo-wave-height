from __future__ import annotations

import glob
import json
from pathlib import Path
import shutil
from typing import Any

import cv2
import numpy as np

from pipeline.common import CommandRecorder, sha256, write_json


def _video_metadata(path: str | Path) -> dict[str, Any]:
    source = Path(path).resolve()
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise ValueError(f"cannot open measurement video: {source}")
    record = {
        "path": str(source),
        "sha256": sha256(source),
        "width": int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "fps": float(capture.get(cv2.CAP_PROP_FPS)),
        "frame_count": int(capture.get(cv2.CAP_PROP_FRAME_COUNT)),
    }
    capture.release()
    record["duration_s"] = record["frame_count"] / record["fps"] if record["fps"] > 0 else None
    return record


def _provided_sequence(config: dict[str, Any], output: Path) -> dict[str, Any]:
    left = [Path(item).resolve() for item in sorted(glob.glob(config["left_images"]))]
    right = [Path(item).resolve() for item in sorted(glob.glob(config["right_images"]))]
    if not left or len(left) != len(right):
        raise ValueError("provided synchronized image sequences are empty or unequal")
    cam0, cam1 = output / "frames" / "cam0", output / "frames" / "cam1"
    cam0.mkdir(parents=True, exist_ok=True)
    cam1.mkdir(parents=True, exist_ok=True)
    mapping = []
    for index, (source_left, source_right) in enumerate(zip(left, right)):
        suffix_left = source_left.suffix.lower()
        suffix_right = source_right.suffix.lower()
        target_left = cam0 / f"{index:06d}{suffix_left}"
        target_right = cam1 / f"{index:06d}{suffix_right}"
        shutil.copy2(source_left, target_left)
        shutil.copy2(source_right, target_right)
        mapping.append(
            {
                "index": index,
                "left_source": str(source_left),
                "right_source": str(source_right),
                "left_sha256": sha256(source_left),
                "right_sha256": sha256(source_right),
                "left_file": str(target_left),
                "right_file": str(target_right),
                "time_s": index / float(config["fps"]),
            }
        )
    first_path = cam0 / f"{0:06d}{left[0].suffix.lower()}"
    first = cv2.imdecode(np.fromfile(first_path, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if first is None:
        raise ValueError(f"cannot read provided image: {left[0]}")
    return {
        "status": "PROVIDED",
        "method": "author-provided synchronized image sequence; copied losslessly without video encoding",
        "fps": float(config["fps"]),
        "frame_count": len(mapping),
        "image_size_wh": [int(first.shape[1]), int(first.shape[0])],
        "right_minus_left_s": 0.0,
        "frames": mapping,
    }


def _tlcc(
    config: dict[str, Any],
    tools: dict[str, Any],
    output: Path,
    repo_root: Path,
    recorder: CommandRecorder,
) -> dict[str, Any]:
    frames = output / "frames"
    script = repo_root / "tools" / "vieira_tlcc_sync.py"
    recorder.run(
        "wass_lowcost_tlcc",
        [
            tools["python"], script,
            "--left", config["left_video"],
            "--right", config["right_video"],
            "--ffmpeg", tools["ffmpeg"],
            "--praat", tools["praat"],
            "--output", frames,
            "--window-start-s", str(config.get("window_start_s", 0.0)),
            "--window-end-s", str(config.get("window_end_s", 30.0)),
            "--start-s", str(config.get("start_s", 10.0)),
            "--output-fps", str(config.get("output_fps", 2.0)),
            "--frame-count", str(config.get("frame_count", 20)),
        ],
        cwd=repo_root,
    )
    result = json.loads((frames / "sync_result.json").read_text(encoding="utf-8"))
    result["status"] = "COMPUTED"
    result["video_metadata"] = {
        "left": _video_metadata(config["left_video"]),
        "right": _video_metadata(config["right_video"]),
    }
    return result


def run(
    source_type: str,
    config: dict[str, Any],
    tools: dict[str, Any],
    run_dir: Path,
    repo_root: Path,
    recorder: CommandRecorder,
) -> dict[str, Any]:
    output = run_dir / "sync"
    output.mkdir(parents=True, exist_ok=True)
    if source_type == "synchronized_image_sequence":
        result = _provided_sequence(config, output)
    elif source_type == "stereo_video":
        if config.get("method") != "wass_lowcost_tlcc":
            raise ValueError("stereo_video requires sync.method=wass_lowcost_tlcc")
        result = _tlcc(config, tools, output, repo_root, recorder)
    else:
        raise ValueError(f"unsupported source_type: {source_type}")
    write_json(output / "sync.json", result)
    return result
