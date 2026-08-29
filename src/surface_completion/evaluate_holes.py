"""CLI for the minimal continuous-hole completion experiment."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import numpy as np
import yaml

from .holes import evaluate_spatial_holes


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _passes(level: dict[str, object]) -> bool:
    return (
        level["coverage_percent"] >= 90
        and level["rmse_m"] is not None and level["rmse_m"] <= 0.002
        and level["p95_absolute_error_m"] is not None and level["p95_absolute_error_m"] <= 0.003
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    frames: dict[str, object] = {}
    for frame in config["frames"]:
        source = Path(frame["height_npz"])
        digest = _sha256(source)
        if digest != frame["sha256"]:
            raise ValueError(f"FROZEN_ARTIFACT_HASH_MISMATCH: {frame['id']}")
        with np.load(source, allow_pickle=False) as data:
            result = evaluate_spatial_holes(
                np.column_stack((data["x_m"], data["y_m"])), data["height_m"],
                maximum_test_centers=config["experiment"]["maximum_test_centers"],
                seed=config["experiment"]["seed"],
                hole_radius_multipliers=tuple(config["experiment"]["hole_radius_multipliers"]),
                **config["mls"],
            )
        frames[frame["id"]] = {"source_sha256": digest, **result}
    small_medium_pass = all(
        _passes(frame["levels"][level]) for frame in frames.values() for level in ("hole_0", "hole_1", "hole_2")
    )
    small_pass = all(
        _passes(frame["levels"][level]) for frame in frames.values() for level in ("hole_0", "hole_1")
    )
    classification = (
        "HOLE_COMPLETION_USABLE_FOR_DENSE_MVP" if small_medium_pass else
        "HOLE_COMPLETION_ONLY_FOR_SMALL_GAPS" if small_pass else
        "HOLE_COMPLETION_UNRELIABLE"
    )
    output = {
        "schema_version": "1.0", "experiment": "FROZEN_WASS_CONTINUOUS_HOLE_COMPLETION",
        "method": "existing_local_weighted_quadratic_MLS_in_physical_XY",
        "interpretation_boundary": "internal WASS surface consistency, not independent physical accuracy",
        "config": config, "frames": frames, "classification": classification,
        "classification_screen": "each required level on every frame: coverage >=90%, RMSE <=2 mm, P95 <=3 mm",
    }
    Path(config["output_yaml"]).write_text(
        yaml.safe_dump(output, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
