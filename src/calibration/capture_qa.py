"""Calibration-video capture QA before any OpenCV calibration is attempted.

The tool uses the project's existing OpenCV checkerboard detector.  It measures
coverage, scale, blur and pose repetition only; it never runs calibration or
WASS.  Existing detection JSON can be supplied to avoid video rescanning.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

from .checkerboard import CheckerboardSpec
from .opencv_backend import detect_checkerboard_official
from .spatial_selection import (
    BilateralPoseDescriptor, build_bilateral_descriptor, descriptor_distance,
    select_spatially_diverse, spatial_grid_counts,
)


GRID_NAMES = ("top_left", "top_center", "top_right", "mid_left", "mid_center",
              "mid_right", "bottom_left", "bottom_center", "bottom_right")


def grid_cell(x_px: float, y_px: float, image_size_wh: tuple[int, int]) -> int:
    """Assign an image point to a row-major 3x3 cell."""
    width, height = image_size_wh
    if width <= 0 or height <= 0 or not (0 <= x_px < width and 0 <= y_px < height):
        raise ValueError("point must lie inside a positive-size image")
    return min(2, int(y_px * 3 / height)) * 3 + min(2, int(x_px * 3 / width))


def deterministic_scale_bins(values: Sequence[float]) -> tuple[str, ...]:
    """Bin board area using deterministic 1/3 and 2/3 sample quantiles."""
    array = np.asarray(values, dtype=np.float64)
    if array.size == 0 or np.any(~np.isfinite(array)) or np.any(array <= 0):
        raise ValueError("positive finite board areas are required")
    q1, q2 = np.quantile(array, [1 / 3, 2 / 3], method="linear")
    return tuple("FAR_SMALL" if value <= q1 else "MEDIUM" if value <= q2 else "NEAR_LARGE" for value in array)


def pair_detections(left: Sequence[dict[str, Any]], right: Sequence[dict[str, Any]], *, maximum_delta_s: float) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Greedy one-to-one nearest-PTS pairing without frame-index assumptions."""
    candidates = sorted((abs(float(a["pts_s"]) - float(b["pts_s"])), str(a["frame_id"]), str(b["frame_id"]), a, b)
                        for a in left for b in right)
    used_l: set[str] = set(); used_r: set[str] = set(); result = []
    for delta, lid, rid, a, b in candidates:
        if delta > maximum_delta_s or lid in used_l or rid in used_r:
            continue
        result.append((a, b)); used_l.add(lid); used_r.add(rid)
    return sorted(result, key=lambda pair: (float(pair[0]["pts_s"]), str(pair[0]["frame_id"])))


def _camera_record(corners: np.ndarray, sharpness: float, width: int, height: int) -> dict[str, Any]:
    xy = corners.reshape(-1, 2).astype(float); minimum = xy.min(0); maximum = xy.max(0)
    row0 = xy[8] - xy[0]; row5 = xy[-1] - xy[-9]
    col0 = xy[-9] - xy[0]; col8 = xy[-1] - xy[8]
    perspective = max(abs(np.linalg.norm(row0)-np.linalg.norm(row5))/max(np.linalg.norm(row0),np.linalg.norm(row5)),
                      abs(np.linalg.norm(col0)-np.linalg.norm(col8))/max(np.linalg.norm(col0),np.linalg.norm(col8)))
    return {"center_x_px": float(xy[:,0].mean()), "center_y_px": float(xy[:,1].mean()),
            "bbox_width_px": float(maximum[0]-minimum[0]), "bbox_height_px": float(maximum[1]-minimum[1]),
            "area_fraction": float(np.prod(maximum-minimum)/(width*height)), "perspective_score": float(perspective),
            "sharpness": float(sharpness), "corners": xy.tolist()}


def scan_video(path: str | Path, *, camera: str, sample_hz: float, rotate_deg: int = 0) -> tuple[list[dict[str, Any]], int, tuple[int, int]]:
    """Sample a video by decoder timestamps and reuse the official detector."""
    import cv2
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened() or sample_hz <= 0:
        raise ValueError(f"cannot open video or invalid sample rate: {path}")
    fps = float(capture.get(cv2.CAP_PROP_FPS)); width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)); height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    interval = max(1, round(fps / sample_hz)); sampled = 0; detections = []; index = 0
    spec = CheckerboardSpec(9, 6, .020)
    while True:
        ok, frame = capture.read()
        if not ok: break
        if index % interval: index += 1; continue
        sampled += 1; pts_s = float(capture.get(cv2.CAP_PROP_POS_MSEC))/1000.0
        if rotate_deg == 180: frame = cv2.rotate(frame, cv2.ROTATE_180)
        elif rotate_deg not in (0,): raise ValueError("only 0 or 180 degree canonical rotation is supported")
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY); detection = detect_checkerboard_official(gray, spec)
        if detection is not None:
            corners = detection.corners_px.reshape(-1,2); lo=np.floor(corners.min(0)).astype(int);hi=np.ceil(corners.max(0)).astype(int);roi=gray[max(0,lo[1]):min(height,hi[1]+1),max(0,lo[0]):min(width,hi[0]+1)]
            sharp=float(cv2.Laplacian(roi,cv2.CV_64F).var()) if roi.size else 0.0
            detections.append({"frame_id":f"{camera}_{index:08d}","pts_s":pts_s,"method":detection.method,
                               **_camera_record(corners,sharp,width,height)})
        index += 1
    capture.release(); return detections, sampled, (width,height)


def normalize_existing_pairs(payload: Sequence[dict[str, Any]]) -> tuple[list[dict[str, Any]], tuple[int, int]]:
    """Accept the frozen stereo-pair schema as capture-QA input."""
    result=[]
    for pair in payload:
        result.append({"pair_id":pair["pair_id"],"left":pair["left"],"right":pair["right"],
                       "left_corners":pair["left_corners"],"right_corners":pair["right_corners"],
                       "delta_s":float(pair["time_residual_s"])})
    return result,(1920,1080)


def prepare_training_and_holdout(pairs: Sequence[dict[str, Any]], *, image_size_wh: tuple[int,int], training_count: int = 20, heldout_count: int = 20) -> dict[str, Any]:
    """Create deterministic disjoint candidate IDs for later calibration."""
    descriptors=[build_bilateral_descriptor(pair,image_size_wh=image_size_wh) for pair in pairs]
    held=select_spatially_diverse(descriptors,count=heldout_count,duplicate_distance=.02)
    train=select_spatially_diverse(descriptors,count=training_count,excluded_pair_ids={x.pair_id for x in held},duplicate_distance=.02)
    return {"training_pair_ids":[x.pair_id for x in train],"heldout_pair_ids":[x.pair_id for x in held]}


def evaluate_capture(pairs: Sequence[dict[str, Any]], *, image_size_wh: tuple[int,int], sampled_left: int, sampled_right: int, detected_left: int, detected_right: int) -> dict[str, Any]:
    """Return transparent capture readiness without running calibration."""
    descriptors=[build_bilateral_descriptor(pair,image_size_wh=image_size_wh) for pair in pairs]
    lg,rg=spatial_grid_counts(descriptors); areas=[x.minimum_area_fraction for x in descriptors]
    bins=Counter(deterministic_scale_bins(areas)) if areas else Counter(); sharp=np.array([x.minimum_sharpness for x in descriptors])
    duplicates=0
    if descriptors:
        selected=[]
        for item in sorted(descriptors,key=lambda x:x.pair_id):
            if selected and min(descriptor_distance(item,x) for x in selected)<.02: duplicates+=1
            else:selected.append(item)
    missing=[]
    for side,grid in (("LEFT",lg),("RIGHT",rg)):
        if sum(grid[:3])==0:missing.append(f"MISSING_TOP_COVERAGE_{side}")
        if sum(grid[6:])==0:missing.append(f"MISSING_BOTTOM_COVERAGE_{side}")
        if sum(grid[0::3])==0:missing.append(f"MISSING_LEFT_EDGE_{side}")
        if sum(grid[2::3])==0:missing.append(f"MISSING_RIGHT_EDGE_{side}")
        if sum(grid[i] for i in (0,2,6,8))==0:missing.append(f"MISSING_CORNER_COVERAGE_{side}")
    if len(bins)<3 or (areas and max(areas)/min(areas)<1.5):missing.append("INSUFFICIENT_SCALE_DIVERSITY")
    if descriptors and duplicates/len(descriptors)>.70:missing.append("INSUFFICIENT_POSE_DIVERSITY")
    if sharp.size and float(np.percentile(sharp,10))<80:missing.append("EXCESSIVE_BLUR")
    rate=len(pairs)/max(1,min(detected_left,detected_right))
    if len(pairs)<20 or rate<.30:missing.append("LOW_BILATERAL_DETECTION_RATE")
    status="CAPTURE_READY_FOR_CALIBRATION" if not missing else "CAPTURE_INCOMPLETE_NEEDS_MORE_VIEWS"
    return {"status":status,"missing":missing,"sampled":{"left":sampled_left,"right":sampled_right},"detected":{"left":detected_left,"right":detected_right},"bilateral_pairs":len(pairs),"bilateral_rate":rate,
            "grid":{"names":list(GRID_NAMES),"left":list(lg),"right":list(rg)},"scale_bins":dict(bins),
            "pose_diversity":{"near_duplicate_count":duplicates,"near_duplicate_ratio":duplicates/max(1,len(descriptors)),"diverse_estimate":len(descriptors)-duplicates},
            "sharpness":{"median":float(np.median(sharp)) if sharp.size else None,"p10":float(np.percentile(sharp,10)) if sharp.size else None,"p90":float(np.percentile(sharp,90)) if sharp.size else None}}


def save_diagnostic_images(result: dict[str, Any], output: Path) -> None:
    """Save compact coverage/quality plots; no source video frames are retained."""
    import matplotlib.pyplot as plt
    figure, axes = plt.subplots(1, 2, figsize=(7, 3))
    maximum = max(1, *result["grid"]["left"], *result["grid"]["right"])
    for axis, side in zip(axes, ("left", "right")):
        image = axis.imshow(np.asarray(result["grid"][side]).reshape(3, 3), vmin=0, vmax=maximum, cmap="viridis")
        for row in range(3):
            for column in range(3):
                axis.text(column, row, str(result["grid"][side][row * 3 + column]), ha="center", va="center", color="white")
        axis.set_title(side.upper()); axis.set_xticks([]); axis.set_yticks([])
    figure.colorbar(image, ax=axes.ravel().tolist(), shrink=.75, label="bilateral candidates")
    figure.savefig(output / "capture_coverage_heatmap.png", dpi=140, bbox_inches="tight")
    plt.close(figure)


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument('--left');parser.add_argument('--right');parser.add_argument('--candidates-json');parser.add_argument('--output',required=True);parser.add_argument('--quick',action='store_true');parser.add_argument('--left-rotate',type=int,default=0);parser.add_argument('--right-rotate',type=int,default=0);args=parser.parse_args()
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
    if args.candidates_json:
        raw=json.loads(Path(args.candidates_json).read_text(encoding='utf8'));pairs,size=normalize_existing_pairs(raw);sl=sr=dl=dr=len(pairs)
    else:
        if not args.left or not args.right:parser.error('provide both videos or --candidates-json')
        hz=2.0 if args.quick else 5.0;l,sl,size=scan_video(args.left,camera='left',sample_hz=hz,rotate_deg=args.left_rotate);r,sr,size_r=scan_video(args.right,camera='right',sample_hz=hz,rotate_deg=args.right_rotate)
        if size!=size_r:raise ValueError('left/right canonical image sizes differ')
        matched=pair_detections(l,r,maximum_delta_s=.12);pairs=[]
        for i,(a,b) in enumerate(matched):pairs.append({'pair_id':f'p{i:04d}','left':a,'right':b,'left_corners':a['corners'],'right_corners':b['corners'],'delta_s':b['pts_s']-a['pts_s']})
        dl,dr=len(l),len(r)
    result=evaluate_capture(pairs,image_size_wh=size,sampled_left=sl,sampled_right=sr,detected_left=dl,detected_right=dr);result['mode']='QUICK' if args.quick else 'FULL';result['image_size_wh']=list(size)
    if len(pairs)>=40:result['proposed_split']=prepare_training_and_holdout(pairs,image_size_wh=size)
    candidate_output={"schema_version":"1.0","image_size_wh":list(size),"pairs":pairs,"proposed_split":result.get("proposed_split")}
    (output/'capture_candidates.json').write_text(json.dumps(candidate_output,ensure_ascii=False),encoding='utf8');
    import yaml
    (output/'capture_qa.yaml').write_text(yaml.safe_dump(result,sort_keys=False,allow_unicode=True),encoding='utf8')
    save_diagnostic_images(result, output)
    lines=['# Calibration capture QA','',f"Status: `{result['status']}`",'',f"Bilateral pairs: {result['bilateral_pairs']}",'',f"Missing: {', '.join(result['missing']) or 'none'}",'',f"LEFT grid: `{result['grid']['left']}`",'',f"RIGHT grid: `{result['grid']['right']}`",'',f"Scale bins: `{result['scale_bins']}`",'',f"Sharpness: `{result['sharpness']}`"]
    (output/'capture_qa.md').write_text('\n'.join(lines)+'\n',encoding='utf8')

if __name__=='__main__':main()
