"""CLI for an explicitly unvalidated, provenance-preserving full-pixel demo."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any
import numpy as np
from PIL import Image
import yaml
from reconstruction.height import height_from_plane
from .constrained_full_domain import SOURCE_NAMES, CONFIDENCE_NAMES, fit_constrained_surface


def _plane_basis(normal: np.ndarray) -> np.ndarray:
    unit=normal/np.linalg.norm(normal);seed=np.array([1.,0.,0.]) if abs(unit[0])<.9 else np.array([0.,1.,0.])
    first=seed-unit*float(seed@unit);first/=np.linalg.norm(first)
    return np.vstack((first,np.cross(unit,first)))


def run(config: dict[str, Any]) -> dict[str, Any]:
    pixel_path=Path(config["pixel_xyz_npz"]);height_path=Path(config["height_npz"])
    with np.load(pixel_path) as data: xyz=np.asarray(data["xyz_m"],float)
    with np.load(height_path) as data: water=np.asarray(data["water_mask"],bool)
    xyz=xyz[water]
    plane=config["current_frame_base_plane"];normal=np.asarray(plane["normal"],float);offset=float(plane["offset_m"])
    height=height_from_plane(xyz,normal,offset)
    xy=xyz@_plane_basis(normal).T
    low=np.percentile(xy,1,axis=0);high=np.percentile(xy,99,axis=0);span=np.maximum(high-low,1e-9)
    normalized=np.clip((xy-low)/span,0,1)
    x0,y0,x1,y1=(int(v) for v in config["water_roi_bbox_xyxy"])
    result=fit_constrained_surface(normalized,height,output_shape=(y1-y0,x1-x0),model_grid_shape=tuple(config.get("model_grid_shape",[64,96])))
    image_size=tuple(config.get("image_size_wh",[1920,1080]));width,image_height=image_size
    full_h=np.full((image_height,width),np.nan,np.float32);source=np.zeros((image_height,width),np.uint8);confidence=np.zeros((image_height,width),np.uint8);distance=np.full((image_height,width),np.nan,np.float32);roi=np.zeros((image_height,width),bool)
    slices=np.s_[y0:y1,x0:x1];full_h[slices]=result.height_m;source[slices]=result.source_status;confidence[slices]=result.confidence;distance[slices]=result.distance_to_support_normalized;roi[slices]=True
    output=Path(config["output_directory"]);output.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(output/"full_pixel_height.npz",height_m=full_h,source_status=source,confidence=confidence,distance_to_support_normalized=distance,water_roi_mask=roi,valid_mask=roi)
    values=result.height_m;lo,hi=np.percentile(values,(2,98));norm=np.clip((values-lo)/max(hi-lo,1e-12),0,1)
    rgb=np.zeros((image_height,width,3),np.uint8);color=np.stack((255*norm,255*(1-np.abs(2*norm-1)),255*(1-norm)),axis=-1).astype(np.uint8);rgb[slices]=color
    Image.fromarray(rgb).save(output/"full_pixel_height.png")
    Image.fromarray((source*80).astype(np.uint8)).save(output/"source_status.png")
    counts={SOURCE_NAMES[int(code)]:int(np.count_nonzero(source==code)) for code in (1,2,3)}
    confidence_counts={CONFIDENCE_NAMES[code]:int(np.count_nonzero(confidence==code)) for code in (1,2,3)}
    total=int(np.count_nonzero(roi));metadata={
      "status":"HOMETANK005_MODEL_ESTIMATED_FULL_PIXEL_DEMO_READY","quality_status":"DEMO_ONLY_GEOMETRY_UNVERIFIED",
      "quality_reasons":["CALIBRATION_GEOMETRY_UNRELIABLE","REFERENCE_FRAME_COORDINATE_INCOMPATIBILITY","PIXEL_XYZ_CANONICAL_MAPPING_UNVERIFIED","MODEL_ESTIMATION_DOMINANT_WARNING"],
      "water_roi_bbox_xyxy":[x0,y0,x1,y1],"roi_pixel_count":total,"finite_height_count":int(np.count_nonzero(np.isfinite(full_h[roi]))),"finite_coverage_ratio":float(np.isfinite(full_h[roi]).mean()),
      "source_counts":counts,"source_ratios":{key:value/total for key,value in counts.items()},"confidence_counts":confidence_counts,"confidence_ratios":{key:value/total for key,value in confidence_counts.items()},
      "reference_artifact":config["reference_artifact"],"measurement_run":str(Path(config["measurement_run"]).resolve()),
      "height_definition":"signed orthogonal residual to the current measurement frame robust WASS water-plane base; demo surface-shape only",
      "reference_warning":"The frozen 9 s reference plane is retained for traceability but cannot be subtracted because WASS frame coordinates were not invariant.",
      "reconstruction_independence":"No ruler or manual ground truth is used.","model":result.metadata,
      "artifact_paths":{"npz":"full_pixel_height.npz","height_png":"full_pixel_height.png","source_png":"source_status.png"},
    }
    (output/"full_pixel_result.json").write_text(json.dumps(metadata,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return metadata


def main()->int:
    parser=argparse.ArgumentParser();parser.add_argument("--config",required=True);args=parser.parse_args()
    config=yaml.safe_load(Path(args.config).read_text(encoding="utf-8"));print(json.dumps(run(config),indent=2,ensure_ascii=False));return 0


if __name__=="__main__":raise SystemExit(main())
