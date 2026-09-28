"""Pinhole stereo depth sensitivity; this is geometry, not measured accuracy."""
from __future__ import annotations

import argparse
import json


def calculate(baseline_mm: float, focal_length_px: float, distance_mm: float,
              disparity_perturbations_px: list[float]) -> dict:
    if min(baseline_mm, focal_length_px, distance_mm) <= 0:
        raise ValueError("baseline, focal length and working distance must be positive")
    disparity_px = focal_length_px * baseline_mm / distance_mm
    return {"baseline_mm": baseline_mm, "focal_length_px": focal_length_px,
            "distance_mm": distance_mm, "nominal_disparity_px": disparity_px,
            "theoretical_depth_sensitivity_mm": [
                {"delta_disparity_px": delta, "abs_delta_depth_mm_approx": distance_mm**2 / (focal_length_px * baseline_mm) * delta}
                for delta in disparity_perturbations_px],
            "equations": ["Z = f B / disparity", "|delta Z| ≈ Z² |delta disparity| / (f B)"],
            "interpretation": "theoretical geometric sensitivity only; not observed system error"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-mm", type=float, required=True)
    parser.add_argument("--focal-px", type=float, required=True)
    parser.add_argument("--distance-mm", type=float, required=True)
    parser.add_argument("--delta-d-px", type=float, nargs="+", default=[0.1, 0.2, 0.5])
    args = parser.parse_args()
    print(json.dumps(calculate(args.baseline_mm, args.focal_px, args.distance_mm,
                               args.delta_d_px), indent=2))


if __name__ == "__main__":
    main()
