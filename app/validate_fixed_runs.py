"""Explicit opt-in real official A/B/C acceptance; never runs at app startup."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import subprocess

import numpy as np

from app import core, coordinates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--source-run", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--reference-time", type=float, required=True)
    parser.add_argument("--times", type=float, nargs=3, required=True)
    args = parser.parse_args()
    root = Path(args.output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    base = core.read_project(args.config)
    origin = Path(args.source_run)
    seed = core.reference_from_run(origin, 0)
    seed_path = root / "seed_reference.json"
    core.save_reference(seed, seed.calibration_id, seed_path, origin, 0)
    binding = json.loads(seed_path.read_text(encoding="utf-8"))
    results = []
    for index, target in enumerate(args.times):
        config = deepcopy(base)
        config.setdefault("presentation", {})["frozen_reference"] = binding
        config["sync"].update(start_s=args.reference_time if index == 0 else target,
            frame_count=2 if index == 0 else 1,
            output_fps=1 / (target - args.reference_time) if index == 0 else 1)
        letter = chr(ord("A") + index)
        folder = root / f"Run_{letter}"
        folder.mkdir()
        path = folder / "project.yaml"
        core.save_project(config, path)
        with (folder / "worker.log").open("w", encoding="utf-8") as log:
            subprocess.run(core.command_for("reconstruct", path, folder, base["tools"]["python"]),
                cwd=core.ROOT, env=core.clean_environment(), stdout=log, stderr=subprocess.STDOUT, check=True)
        run = folder / "science"
        if index == 0:
            # A's freshly reconstructed frame 0 becomes the new project candidate.
            # Existing frozen reference algorithm is used unchanged, then frozen once.
            reference = core.reference_from_run(run, 0)
            plane_path = root / "reference_plane.json"
            core.save_reference(reference, reference.calibration_id, plane_path, run, 0)
            binding = json.loads(plane_path.read_text(encoding="utf-8"))
            (run / "reference_plane.json").write_text(json.dumps(binding, indent=2), encoding="utf-8")
            for frame_id, requested in enumerate((args.reference_time, target)):
                core.write_frame_manifest(run, requested, reference.plane_id, frame_id)
        reference, _ = core.reference_from_metadata(binding)
        frame = core.load_result(run, 1 if index == 0 else 0, reference, reference.calibration_id)
        valid = np.argwhere((frame["source"] != 0) & np.isfinite(frame["height"]))
        pixel = valid[len(valid) // 2]
        from plyfile import PlyData
        row = {"run": letter, "workspace": str(run), "frame_id": frame["frame_id"],
               "timestamp_s": frame["timestamp_s"], **coordinates.identity(run),
               "reference_plane_id": reference.plane_id, "supported_pixels": len(valid),
               "xyz_count": len(PlyData.read(run / "reconstruction" / "ply" / f"{frame['frame_id']:06d}.ply")["vertex"].data),
               "hover": core.hover(frame, int(pixel[1]), int(pixel[0]))}
        results.append(row)
        print(json.dumps(row), flush=True)
    (root / "acceptance.json").write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
