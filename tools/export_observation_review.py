"""Package small, traceable previews from completed fixed-ROI WASS runs."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import yaml
from PIL import Image


def export_review(result: Path, destination: Path) -> Path:
    data = yaml.safe_load(result.read_text(encoding="utf-8"))
    if destination.exists():
        raise FileExistsError(destination)
    destination.mkdir(parents=True)
    output = {"schema": "wass_observation_review_v1", "experiment": "HomeTank_006",
              "height_available": False, "source_result_sha256": hashlib.sha256(result.read_bytes()).hexdigest(),
              "fixed_roi_pixels": data["fixed_roi_pixels"],
              "fixed_roi_full_image_ratio": data["fixed_roi_full_image_ratio"], "frames": []}
    for frame in data["frames"]:
        item = {key: frame[key] for key in ("frame_id", "left_target_s", "decoded_pts_s", "final_xyz_count",
                                            "raw_roi_support_ratio", "stereo_seconds")}
        name = f"frame_{frame['frame_id']}"
        original = Path(data["baseline_source"]) / name / "cam1.png"
        target = destination / f"{name}_original.jpg"
        with Image.open(original) as image:
            image.convert("RGB").resize((960, 540), Image.Resampling.LANCZOS).save(target, quality=90)
        item["original"] = target.name
        target = destination / f"{name}_support.jpg"
        shutil.copy2(Path(data["replay_source"]) / name / "canonical_right_support_preview.jpg", target)
        item["support"] = target.name
        for key in ("original", "support"):
            item[key + "_sha256"] = hashlib.sha256((destination / item[key]).read_bytes()).hexdigest()
        output["frames"].append(item)
    target = destination / "review.json"
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(export_review(args.result, args.output))
