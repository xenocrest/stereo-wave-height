"""CLI for reproducible hold-out validation on frozen WASS height points."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import numpy as np
import yaml

from .mls import evaluate_holdout


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    results: dict[str, object] = {}
    for frame in config["frames"]:
        source = Path(frame["height_npz"])
        digest = _sha256(source)
        if digest != frame["sha256"]:
            raise ValueError(f"FROZEN_ARTIFACT_HASH_MISMATCH: {frame['id']}")
        with np.load(source, allow_pickle=False) as data:
            result = evaluate_holdout(
                np.column_stack((data["x_m"], data["y_m"])), data["height_m"],
                holdout_ratio=config["holdout"]["ratio"],
                maximum_test_points=config["holdout"]["maximum_test_points"],
                seed=config["holdout"]["seed"],
                **config["mls"],
            )
        results[frame["id"]] = {"source_sha256": digest, **result.to_dict()}
    frame_values = list(results.values())
    promising = all(
        item["coverage_percent"] >= 95
        and item["rmse_m"] is not None and item["rmse_m"] <= 0.002
        and item["p95_absolute_error_m"] is not None and item["p95_absolute_error_m"] <= 0.003
        for item in frame_values
    )
    near_usable = all(
        item["strata"]["near"]["p95_absolute_error_m"] is not None
        and item["strata"]["near"]["p95_absolute_error_m"] <= 0.0035
        for item in frame_values
    )
    classification = (
        "SPATIAL_SURFACE_COMPLETION_PROMISING" if promising else
        "SPATIAL_SURFACE_COMPLETION_LIMITED_BY_SUPPORT" if near_usable else
        "SPATIAL_SURFACE_COMPLETION_NOT_SUPPORTED"
    )
    output = {"schema_version": "1.0", "experiment": "FROZEN_WASS_SPATIAL_COMPLETION_HOLDOUT",
              "method": "local_weighted_quadratic_surface_in_physical_XY", "config": config, "frames": results,
              "classification": classification,
              "classification_screen": {
                  "purpose": "continue-or-stop research screen, not physical accuracy acceptance",
                  "promising": "all frames coverage >=95%, RMSE <=2 mm, P95 absolute error <=3 mm",
                  "limited": "promising screen fails but all near-support P95 absolute error <=3.5 mm",
              }}
    destination = Path(config["output_yaml"])
    destination.write_text(yaml.safe_dump(output, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
