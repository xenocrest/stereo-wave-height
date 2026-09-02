"""Held-out OLD/NEW calibration comparison and WASS A/B admission gate."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import yaml


def load_mapping(path: str | Path) -> dict[str, Any]:
    text = Path(path).read_text(encoding="utf-8")
    return json.loads(text) if Path(path).suffix.lower() == ".json" else yaml.safe_load(text)


def normalize_calibration(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize the two project calibration schemas without changing values."""
    if "mono_left" in payload:
        return {"mono_left_rms": payload["mono_left"]["rms_px"], "mono_right_rms": payload["mono_right"]["rms_px"],
                "K0": payload["mono_left"]["camera_matrix"], "D0": payload["mono_left"]["distortion"],
                "K1": payload["mono_right"]["camera_matrix"], "D1": payload["mono_right"]["distortion"],
                "stereo_rms": payload["stereo_rms_px"], "epipolar_rms": payload["epipolar_rms_px"],
                "R": payload["rotation_right_from_left"], "T": payload["translation_right_from_left_m"],
                "image_size": payload["image_size_wh"]}
    return {"mono_left_rms": payload["mono_cam0"]["rms_px"], "mono_right_rms": payload["mono_cam1"]["rms_px"],
            "K0": payload["mono_cam0"]["K"], "D0": payload["mono_cam0"]["D"],
            "K1": payload["mono_cam1"]["K"], "D1": payload["mono_cam1"]["D"],
            "stereo_rms": payload["stereo"]["rms_px"], "epipolar_rms": payload["stereo"].get("symmetric_epipolar_rms_px",payload["stereo"].get("epipolar_rms_px")),
            "R": payload["stereo"]["R_right_from_left"], "T": payload["stereo"]["T_right_from_left_m"],
            "image_size": [1920, 1080]}


def heldout_vertical_errors(model: dict[str, Any], pairs: Sequence[dict[str, Any]], heldout_ids: Sequence[str]) -> np.ndarray:
    """Measure rectified vertical residuals on one explicitly shared held-out set."""
    import cv2
    selected = [pair for pair in pairs if pair["pair_id"] in set(heldout_ids)]
    if {p["pair_id"] for p in selected} != set(heldout_ids):
        raise ValueError("held-out IDs are missing from candidates")
    k0, d0, k1, d1, r, t = (np.asarray(model[key], dtype=np.float64) for key in ("K0", "D0", "K1", "D1", "R", "T"))
    r1, r2, p1, p2, *_ = cv2.stereoRectify(k0, d0, k1, d1, tuple(model["image_size"]), r, t.reshape(3, 1), flags=cv2.CALIB_ZERO_DISPARITY, alpha=0)
    values = []
    for pair in selected:
        left = np.asarray(pair["left_corners"], np.float32).reshape(-1, 1, 2)
        right = np.asarray(pair["right_corners"], np.float32).reshape(-1, 1, 2)
        ly = cv2.undistortPoints(left, k0, d0, R=r1, P=p1).reshape(-1, 2)[:, 1]
        ry = cv2.undistortPoints(right, k1, d1, R=r2, P=p2).reshape(-1, 2)[:, 1]
        values.extend(np.abs(ly - ry))
    return np.asarray(values)


def error_summary(errors: np.ndarray) -> dict[str, float]:
    if errors.size == 0 or np.any(~np.isfinite(errors)): raise ValueError("finite non-empty errors required")
    return {"median_px": float(np.median(errors)), "rms_px": float(np.sqrt(np.mean(errors**2))),
            "p95_px": float(np.percentile(errors, 95)), "max_px": float(np.max(errors))}


def model_sanity(model: dict[str, Any], reference_baseline_m: float = .070) -> dict[str, Any]:
    arrays = [np.asarray(model[x], dtype=float) for x in ("K0", "D0", "K1", "D1", "R", "T")]
    baseline = float(np.linalg.norm(arrays[-1])); finite = all(np.all(np.isfinite(x)) for x in arrays)
    plausible = finite and baseline > 0 and all(x[0, 0] > 0 and x[1, 1] > 0 and abs(x[2, 2]-1) < 1e-8 for x in (arrays[0], arrays[2]))
    trace = float(np.trace(arrays[4])); angle = math.degrees(math.acos(np.clip((trace-1)/2, -1, 1)))
    return {"finite_and_plausible": plausible, "baseline_m": baseline,
            "baseline_difference_percent": 100*abs(baseline-reference_baseline_m)/reference_baseline_m,
            "relative_rotation_deg": angle}


def calibration_ab_gate(old: dict[str, Any], new: dict[str, Any], new_sanity: dict[str, Any]) -> dict[str, Any]:
    checks = {"heldout_rms_significantly_improved": new["rms_px"] <= .70*old["rms_px"],
              "heldout_p95_significantly_improved": new["p95_px"] <= .70*old["p95_px"],
              "epipolar_not_worse": new["epipolar_rms_px"] <= 1.05*old["epipolar_rms_px"],
              "baseline_within_5_percent": new_sanity["baseline_difference_percent"] <= 5,
              "parameters_finite_and_plausible": bool(new_sanity["finite_and_plausible"]),
              "heldout_max_not_worse": new["max_px"] <= old["max_px"]}
    return {"status": "CALIBRATION_READY_FOR_WASS_AB" if all(checks.values()) else "CALIBRATION_NOT_READY_FOR_WASS_AB", "checks": checks}


def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("--old",required=True);parser.add_argument("--new",required=True);parser.add_argument("--candidates",required=True);parser.add_argument("--output",required=True);args=parser.parse_args()
    old,new=normalize_calibration(load_mapping(args.old)),normalize_calibration(load_mapping(args.new)); candidates=load_mapping(args.candidates)
    pairs=candidates if isinstance(candidates,list) else candidates["pairs"];held=(candidates.get("proposed_split") or {}).get("heldout_pair_ids") if isinstance(candidates,dict) else None
    if not held: raise ValueError("candidates must include one shared heldout_pair_ids set")
    oe,ne=heldout_vertical_errors(old,pairs,held),heldout_vertical_errors(new,pairs,held);os,ns=error_summary(oe),error_summary(ne)
    os.update({"mono_left_rms_px":old["mono_left_rms"],"mono_right_rms_px":old["mono_right_rms"],"stereo_rms_px":old["stereo_rms"],"epipolar_rms_px":old["epipolar_rms"]})
    ns.update({"mono_left_rms_px":new["mono_left_rms"],"mono_right_rms_px":new["mono_right_rms"],"stereo_rms_px":new["stereo_rms"],"epipolar_rms_px":new["epipolar_rms"]})
    result={"heldout_pair_ids":list(held),"same_heldout_set":True,"old":os,"new":ns,"new_sanity":model_sanity(new)};result["gate"]=calibration_ab_gate(os,ns,result["new_sanity"])
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True);(output/"old_vs_new_calibration.yaml").write_text(yaml.safe_dump(result,sort_keys=False),encoding="utf-8")
    import matplotlib.pyplot as plt
    for name,values in (("old_vs_new_rectification_error",(oe,ne)),("heldout_old_vs_new_error",(np.sort(oe),np.sort(ne)))):
        fig,ax=plt.subplots(figsize=(6,3));ax.hist(values[0],bins=30,alpha=.55,label="OLD");ax.hist(values[1],bins=30,alpha=.55,label="NEW");ax.set_xlabel("absolute rectified vertical error (px)");ax.legend();fig.savefig(output/f"{name}.png",dpi=140,bbox_inches="tight");plt.close(fig)

if __name__ == "__main__": main()
