"""Subprocess entry point; delegates every scientific stage to frozen pipeline code."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from pipeline.adapters import calibration, sync
from pipeline.common import CommandRecorder
from pipeline.run_pipeline import run_pipeline

from app.core import ROOT, read_project


def run(action: str, config_path: Path, run_dir: Path) -> dict:
    config = read_project(config_path)
    if action == "reconstruct":
        if config.get("presentation", {}).get("frozen_reference"):
            from app.fixed_run import run as run_fixed
            report = run_fixed(config, run_dir / "science")
        else:
            report = run_pipeline(config_path, str(run_dir / "science"))
        return {"status": report["status"], "science_run": report["run_directory"]}
    recorder = CommandRecorder(run_dir / "logs" / "scientific_tools")
    if action == "calibrate":
        result = calibration.run(config["calibration"], config["tools"], run_dir, ROOT, recorder)
    elif action == "sync":
        result = sync.run(config["source_type"], config["sync"], config["tools"], run_dir, ROOT, recorder)
    else:
        raise ValueError(f"Unknown action: {action}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("calibrate", "sync", "reconstruct"))
    parser.add_argument("config")
    parser.add_argument("run_dir")
    args = parser.parse_args()
    target = Path(args.run_dir)
    result = run(args.action, Path(args.config), target)
    (target / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": result.get("status"), "run_dir": str(target)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
