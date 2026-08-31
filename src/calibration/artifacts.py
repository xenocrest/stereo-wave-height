"""Atomic calibration packages, provenance hashes and promotion registry.

This module packages existing calibration values; it never estimates or alters
K/D/R/T and it never invokes WASS.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import argparse
from typing import Any
import xml.etree.ElementTree as ET

import numpy as np
import yaml

from adapters.wass.input.opencv_xml import write_opencv_matrix_xml, write_wass_calibration_xml
from .compare_calibrations import load_mapping, normalize_calibration, model_sanity

XML_NAMES=("intrinsics_00.xml","intrinsics_01.xml","distortion_00.xml","distortion_01.xml","ext_R.xml","ext_T.xml")

def sha256_file(path: str | Path) -> str:
    digest=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024),b""):digest.update(block)
    return digest.hexdigest()

def canonical_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")).hexdigest()

def read_opencv_xml(path: str | Path) -> np.ndarray:
    node=list(ET.parse(path).getroot())[0];rows=int(node.findtext("rows","0"));cols=int(node.findtext("cols","0"));data=np.fromstring(node.findtext("data", ""),sep=" ")
    if data.size != rows*cols:raise ValueError(f"invalid OpenCV XML matrix: {path}")
    return data.reshape(rows,cols)

def verify_package_consistency(package_root: str | Path, *, tolerance: float=1e-12) -> dict[str, Any]:
    root=Path(package_root);manifest=yaml.safe_load((root/"manifest.yaml").read_text(encoding="utf-8"));model=normalize_calibration(load_mapping(root/manifest["artifacts"]["opencv_calibration"]["path"]))
    expected={"intrinsics_00.xml":np.asarray(model["K0"]),"intrinsics_01.xml":np.asarray(model["K1"]),"distortion_00.xml":np.asarray(model["D0"]).reshape(-1,1),"distortion_01.xml":np.asarray(model["D1"]).reshape(-1,1),"ext_R.xml":np.asarray(model["R"]),"ext_T.xml":np.asarray(model["T"]).reshape(3,1)}
    mismatches=[]
    for name,wanted in expected.items():
        actual=read_opencv_xml(root/"wass_fixed"/name)
        if actual.shape != wanted.shape or not np.allclose(actual,wanted,rtol=0,atol=tolerance):mismatches.append(name)
    hashes=manifest["artifacts"]
    for item in [hashes["opencv_calibration"],*hashes["wass_fixed"].values()]:
        if sha256_file(root/item["path"]) != item["sha256"]:mismatches.append(f"HASH:{item['path']}")
    return {"status":"PASS" if not mismatches else "CALIBRATION_WASS_EXPORT_MISMATCH","mismatches":mismatches,"tolerance":tolerance}

def build_calibration_package(calibration_path: str | Path, package_root: str | Path, *, calibration_id: str, source: dict[str,Any], qa: dict[str,Any], status: str="CANDIDATE", created_at: str|None=None) -> Path:
    if status not in {"CANDIDATE","APPROVED","REJECTED"}:raise ValueError("invalid immutable manifest status")
    root=Path(package_root);root.mkdir(parents=True,exist_ok=False);wass=root/"wass_fixed";wass.mkdir();source_path=Path(calibration_path);suffix=source_path.suffix.lower();copied=root/f"opencv_calibration{suffix}";shutil.copyfile(source_path,copied)
    model=normalize_calibration(load_mapping(copied));write_wass_calibration_xml(wass,intrinsic_00=model["K0"],intrinsic_01=model["K1"],distortion_00=model["D0"],distortion_01=model["D1"]);write_opencv_matrix_xml(wass/"ext_R.xml",model["R"],node_name="ext_R");write_opencv_matrix_xml(wass/"ext_T.xml",np.asarray(model["T"]).reshape(3,1),node_name="ext_T")
    xml={name:{"path":f"wass_fixed/{name}","sha256":sha256_file(wass/name)} for name in XML_NAMES}
    manifest={"schema_version":"1.0","calibration_id":calibration_id,"created_at":created_at or datetime.now(timezone.utc).isoformat(),"source":source,
              "camera_left":{"K":model["K0"],"D":model["D0"]},"camera_right":{"K":model["K1"],"D":model["D1"]},
              "stereo":{"R":model["R"],"T_m":model["T"],"baseline_m":model_sanity(model)["baseline_m"]},"qa":qa,"status":status,
              "artifacts":{"opencv_calibration":{"path":copied.name,"sha256":sha256_file(copied)},"wass_fixed":xml}}
    manifest["package_content_sha256"]=canonical_hash({"calibration_id":calibration_id,"artifacts":manifest["artifacts"]})
    (root/"manifest.yaml").write_text(yaml.safe_dump(manifest,sort_keys=False,allow_unicode=True),encoding="utf-8")
    check=verify_package_consistency(root)
    if check["status"]!="PASS":raise RuntimeError(check["status"])
    return root

def load_registry(path: str|Path) -> dict[str,Any]:return yaml.safe_load(Path(path).read_text(encoding="utf-8"))

def approve_for_wass_ab(registry: dict[str,Any], calibration_id: str, *, calibration_gate: str, consistency: str) -> dict[str,Any]:
    if calibration_gate!="CALIBRATION_READY_FOR_WASS_AB" or consistency!="PASS":raise ValueError("candidate is not eligible for WASS A/B")
    updated=json.loads(json.dumps(registry));updated["calibrations"][calibration_id]["lifecycle_status"]="APPROVED_FOR_WASS_AB";return updated

def promote_production(registry: dict[str,Any], calibration_id: str, *, recommendation: str, approved_at: str, reason: str) -> dict[str,Any]:
    if registry["calibrations"][calibration_id]["lifecycle_status"]!="APPROVED_FOR_WASS_AB" or recommendation!="PROMOTE":raise ValueError("candidate cannot directly become production")
    updated=json.loads(json.dumps(registry));updated["calibrations"][calibration_id]["lifecycle_status"]="PROMOTED_PRODUCTION_CALIBRATION";updated["current_production_calibration_id"]=calibration_id;updated["approved_at"]=approved_at;updated["reason"]=reason;return updated

def rollback_production(registry: dict[str,Any], calibration_id: str, *, reason: str) -> dict[str,Any]:
    if calibration_id not in registry["calibrations"]:raise KeyError(calibration_id)
    updated=json.loads(json.dumps(registry));updated["current_production_calibration_id"]=calibration_id;updated["reason"]=reason;return updated

def generate_future_wass_config(package_root: str|Path, template: dict[str,Any], output: str|Path, *, old_calibration_id: str) -> Path:
    check=verify_package_consistency(package_root)
    if check["status"]!="PASS":raise ValueError("CALIBRATION_WASS_EXPORT_MISMATCH")
    manifest=yaml.safe_load((Path(package_root)/"manifest.yaml").read_text(encoding="utf-8"));result=json.loads(json.dumps(template));result.update({"calibration_id":manifest["calibration_id"],"calibration_package":str(Path(package_root).resolve()),"calibration_package_hash":manifest["package_content_sha256"],"old_baseline_calibration_id":old_calibration_id,"single_variable_changed":"calibration K/D/R/T","wass_execution":"FUTURE_NOT_EXECUTED"})
    destination=Path(output);destination.write_text(yaml.safe_dump(result,sort_keys=False),encoding="utf-8");return destination

def _write_registry(path: str|Path, value: dict[str,Any])->None:Path(path).write_text(yaml.safe_dump(value,sort_keys=False),encoding="utf-8")

def main()->None:
    parser=argparse.ArgumentParser(description="Build and promote immutable calibration packages without running calibration or WASS")
    sub=parser.add_subparsers(dest="command",required=True)
    build=sub.add_parser("build");build.add_argument("--calibration",required=True);build.add_argument("--package",required=True);build.add_argument("--calibration-id",required=True);build.add_argument("--source-json",required=True);build.add_argument("--qa-json",required=True)
    approve=sub.add_parser("approve-ab");approve.add_argument("--registry",required=True);approve.add_argument("--calibration-id",required=True);approve.add_argument("--calibration-gate",required=True);approve.add_argument("--package",required=True)
    config=sub.add_parser("future-config");config.add_argument("--package",required=True);config.add_argument("--template",required=True);config.add_argument("--output",required=True);config.add_argument("--old-calibration-id",required=True)
    promote=sub.add_parser("promote");promote.add_argument("--registry",required=True);promote.add_argument("--calibration-id",required=True);promote.add_argument("--recommendation",required=True);promote.add_argument("--reason",required=True)
    rollback=sub.add_parser("rollback");rollback.add_argument("--registry",required=True);rollback.add_argument("--calibration-id",required=True);rollback.add_argument("--reason",required=True)
    args=parser.parse_args()
    if args.command=="build":build_calibration_package(args.calibration,args.package,calibration_id=args.calibration_id,source=json.loads(Path(args.source_json).read_text(encoding="utf-8")),qa=json.loads(Path(args.qa_json).read_text(encoding="utf-8")))
    elif args.command=="approve-ab":_write_registry(args.registry,approve_for_wass_ab(load_registry(args.registry),args.calibration_id,calibration_gate=args.calibration_gate,consistency=verify_package_consistency(args.package)["status"]))
    elif args.command=="future-config":generate_future_wass_config(args.package,load_mapping(args.template),args.output,old_calibration_id=args.old_calibration_id)
    elif args.command=="promote":_write_registry(args.registry,promote_production(load_registry(args.registry),args.calibration_id,recommendation=args.recommendation,approved_at=datetime.now(timezone.utc).isoformat(),reason=args.reason))
    else:_write_registry(args.registry,rollback_production(load_registry(args.registry),args.calibration_id,reason=args.reason))

if __name__=="__main__":main()
