"""Bounded adaptive split calibration for a real stereo capture.

Only mature OpenCV four- and five-coefficient pinhole models are compared.
Cross-validation is pose-group disjoint and stereo extrinsics always use
``CALIB_FIX_INTRINSIC``.  This runner never invokes WASS.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import yaml

from .adaptive_calibration import deterministic_group_folds, rectification_residuals
from .capture_qa import pair_detections, scan_video
from .checkerboard import CheckerboardSpec
from .spatial_selection import build_bilateral_descriptor, descriptor_distance


def _object(count:int)->list[np.ndarray]:
    item=CheckerboardSpec(9,6,.020).object_points_m().astype(np.float32)
    return [item.copy() for _ in range(count)]


def _mono(images:list[np.ndarray],size:tuple[int,int],*,fix_k3:bool):
    flags=cv2.CALIB_FIX_K3 if fix_k3 else 0
    rms,k,d,rvecs,tvecs=cv2.calibrateCamera(_object(len(images)),images,size,None,None,flags=flags)
    d=np.asarray(d,float).reshape(-1)
    if fix_k3:d[4]=0.
    errors=[]
    for obj,img,rv,tv in zip(_object(len(images)),images,rvecs,tvecs):
        projected,_=cv2.projectPoints(obj,rv,tv,k,d)
        errors.append(float(np.sqrt(np.mean(np.sum((projected.reshape(-1,2)-img.reshape(-1,2))**2,axis=1)))))
    return float(rms),np.asarray(k,float),d,errors


def _stereo(left,right,size,k0,d0,k1,d1):
    result=cv2.stereoCalibrate(_object(len(left)),left,right,k0.copy(),d0.copy(),k1.copy(),d1.copy(),size,
        flags=cv2.CALIB_FIX_INTRINSIC,criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_MAX_ITER,100,1e-5))
    rms,ko0,do0,ko1,do1,r,t,_e,f=result
    if not (np.array_equal(ko0,k0) and np.array_equal(ko1,k1) and np.array_equal(do0.reshape(-1),d0) and np.array_equal(do1.reshape(-1),d1)):
        raise RuntimeError("CALIB_FIX_INTRINSIC did not preserve K/D")
    epi=[]
    for lp,rp in zip(left,right):
        lu=cv2.undistortPoints(lp,k0,d0,P=k0);ru=cv2.undistortPoints(rp,k1,d1,P=k1)
        lr=cv2.computeCorrespondEpilines(lu,1,f).reshape(-1,3);ll=cv2.computeCorrespondEpilines(ru,2,f).reshape(-1,3)
        lxy=lu.reshape(-1,2);rxy=ru.reshape(-1,2)
        dl=np.abs(np.sum(ll[:,:2]*lxy,axis=1)+ll[:,2])/np.linalg.norm(ll[:,:2],axis=1)
        dr=np.abs(np.sum(lr[:,:2]*rxy,axis=1)+lr[:,2])/np.linalg.norm(lr[:,:2],axis=1)
        epi.extend(((dl+dr)*.5).tolist())
    return float(rms),r,np.asarray(t,float).reshape(3),float(np.sqrt(np.mean(np.asarray(epi)**2)))


def _pose_groups(pairs:list[dict[str,Any]],size:tuple[int,int])->list[str]:
    representatives=[];result=[]
    for item in [build_bilateral_descriptor(p,image_size_wh=size) for p in pairs]:
        distances=[(descriptor_distance(item,rep),i) for i,rep in enumerate(representatives)]
        if distances and min(distances)[0] < .02:index=min(distances)[1]
        else:index=len(representatives);representatives.append(item)
        result.append(f"pose_{index:03d}")
    return result


def run(left_path:Path,right_path:Path,output:Path)->dict[str,Any]:
    output.mkdir(parents=True,exist_ok=True);cache=output/"detection_cache.json"
    if cache.is_file():
        cached=json.loads(cache.read_text(encoding="utf-8"));left,right=cached["left"],cached["right"];size=tuple(cached["image_size_wh"]);right_size=size
    else:
        left,_,size=scan_video(left_path,camera="left",sample_hz=5.,rotate_deg=180)
        right,_,right_size=scan_video(right_path,camera="right",sample_hz=5.,rotate_deg=0)
        cache.write_text(json.dumps({"image_size_wh":size,"left":left,"right":right}),encoding="utf-8")
    if size!=right_size:raise RuntimeError("canonical size mismatch")
    pairs=[{"pair_id":f"p{i:04d}","left":a,"right":b,"left_corners":a["corners"],"right_corners":b["corners"]} for i,(a,b) in enumerate(pair_detections(left,right,maximum_delta_s=.12))]
    identity=np.median([np.linalg.norm(np.asarray(p["left_corners"])-np.asarray(p["right_corners"]),axis=1) for p in pairs])
    reversed_order=np.median([np.linalg.norm(np.asarray(p["left_corners"])-np.asarray(p["right_corners"])[::-1],axis=1) for p in pairs])
    ordering="IDENTITY"
    if reversed_order < .75*identity:
        ordering="RIGHT_REVERSED_180_FROM_IMAGE_EVIDENCE"
        for pair in pairs:pair["right_corners"]=list(reversed(pair["right_corners"]));pair["right"]["corners"]=pair["right_corners"]
    group_ids=_pose_groups(pairs,size);folds=deterministic_group_folds(group_ids)
    mono_l=[np.asarray(x["corners"],np.float32).reshape(-1,1,2) for x in left]
    mono_r=[np.asarray(x["corners"],np.float32).reshape(-1,1,2) for x in right]
    all_l=[np.asarray(p["left_corners"],np.float32).reshape(-1,1,2) for p in pairs]
    all_r=[np.asarray(p["right_corners"],np.float32).reshape(-1,1,2) for p in pairs]
    models=[];finals={}
    for name,fix_k3,complexity in (("OPENCV_4_COEFFICIENT",True,4),("OPENCV_5_COEFFICIENT",False,5)):
        ml=_mono(mono_l,size,fix_k3=fix_k3);mr=_mono(mono_r,size,fix_k3=fix_k3);stereo=_stereo(all_l,all_r,size,ml[1],ml[2],mr[1],mr[2])
        fold_records=[];samples=[]
        for fold_index,valid_indices in enumerate(folds):
            valid=set(valid_indices);train=[i for i in range(len(pairs)) if i not in valid]
            train_l=[all_l[i] for i in train];train_r=[all_r[i] for i in train]
            cml=_mono(train_l,size,fix_k3=fix_k3);cmr=_mono(train_r,size,fix_k3=fix_k3);cs=_stereo(train_l,train_r,size,cml[1],cml[2],cmr[1],cmr[2])
            qa=rectification_residuals([all_l[i] for i in valid_indices],[all_r[i] for i in valid_indices],k0=cml[1],d0=cml[2],k1=cmr[1],d1=cmr[2],r=cs[1],t=cs[2].reshape(3,1),image_size_wh=size)
            fold_records.append({"fold":fold_index,"train_groups":sorted(set(group_ids[i] for i in train)),"validation_groups":sorted(set(group_ids[i] for i in valid_indices)),"validation_pair_count":len(valid_indices),"vertical":qa,"baseline_m":float(np.linalg.norm(cs[2])),"relative_rotation_deg":float(np.degrees(np.linalg.norm(cv2.Rodrigues(cs[1])[0]))),"epipolar_rms_px":cs[3],"K0":cml[1].tolist(),"K1":cmr[1].tolist(),"D0":cml[2].tolist(),"D1":cmr[2].tolist()});samples.append((cml,cmr,cs))
        vrms=np.asarray([x["vertical"]["rms_px"] for x in fold_records],float)
        focal=np.asarray([[s[0][1][0,0],s[1][1][0,0]] for s in samples]);pp=np.asarray([[s[0][1][0,2]/size[0],s[0][1][1,2]/size[1],s[1][1][0,2]/size[0],s[1][1][1,2]/size[1]] for s in samples]);bases=np.asarray([np.linalg.norm(s[2][2]) for s in samples]);rots=np.asarray([np.degrees(np.linalg.norm(cv2.Rodrigues(s[2][1])[0])) for s in samples]);dist=np.asarray([np.r_[s[0][2],s[1][2]] for s in samples])
        stability={"focal_max_relative_range":float(np.max(np.ptp(focal,axis=0)/np.maximum(np.mean(focal,axis=0),1e-12))),"principal_max_normalized_range":float(np.max(np.ptp(pp,axis=0))),"baseline_relative_range":float(np.ptp(bases)/np.mean(bases)),"relative_rotation_range_deg":float(np.ptp(rots)),"distortion_max_range":float(np.max(np.ptp(dist,axis=0)))}
        stable=stability["focal_max_relative_range"]<=.10 and stability["principal_max_normalized_range"]<=.10 and stability["baseline_relative_range"]<=.15
        models.append({"model":name,"complexity":complexity,"mono_left_rms_px":ml[0],"mono_right_rms_px":mr[0],"stereo_rms_px":stereo[0],"epipolar_rms_px":stereo[3],"heldout_rectification_rms_px":float(np.sqrt(np.mean(vrms**2))),"worst_fold_rms_px":float(vrms.max()),"parameter_stability":"CALIBRATION_PARAMETER_STABLE_PROXY" if stable else "CALIBRATION_PARAMETER_UNSTABLE","stability":stability,"folds":fold_records});finals[name]=(ml,mr,stereo)
    stable=[x for x in models if x["parameter_stability"]!="CALIBRATION_PARAMETER_UNSTABLE"];pool=stable or models
    best=min(x["heldout_rectification_rms_px"] for x in pool);chosen=min((x for x in pool if x["heldout_rectification_rms_px"]<=best+.05),key=lambda x:x["complexity"]);ml,mr,stereo=finals[chosen["model"]]
    global_qa=rectification_residuals(all_l,all_r,k0=ml[1],d0=ml[2],k1=mr[1],d1=mr[2],r=stereo[1],t=stereo[2].reshape(3,1),image_size_wh=size)
    classification="CALIBRATION_OPERATIONAL_DOMAIN_VALID" if chosen["worst_fold_rms_px"]<5 and chosen["epipolar_rms_px"]<5 and math.isfinite(float(np.linalg.norm(stereo[2]))) else "CALIBRATION_OPERATIONAL_DOMAIN_FAIL"
    result={"schema_version":"1.0","status":classification,"image_size_wh":list(size),"square_size_m":.020,"corner_ordering":{"selected":ordering,"identity_median_distance_px":float(identity),"reversed_median_distance_px":float(reversed_order)},"left_mono_count":len(left),"right_mono_count":len(right),"stereo_pair_count":len(pairs),"independent_pose_group_count":len(set(group_ids)),"fold_count":len(folds),"models":models,"selected_model":chosen["model"],"global_sensor_qa":{**global_qa,"status":"GLOBAL_EXTRAPOLATION_WEAK"},"operational_domain_qa":{**global_qa,"scope":"STEREO_COMMON_VALID_FOV"},"mono_cam0":{"K":ml[1].tolist(),"D":ml[2].tolist(),"rms_px":ml[0]},"mono_cam1":{"K":mr[1].tolist(),"D":mr[2].tolist(),"rms_px":mr[0]},"stereo":{"R_right_from_left":stereo[1].tolist(),"T_right_from_left_m":stereo[2].tolist(),"rms_px":stereo[0],"epipolar_rms_px":stereo[3],"baseline_m":float(np.linalg.norm(stereo[2]))},"rectification":{"alpha":0.,"flags":"CALIB_ZERO_DISPARITY"}}
    (output/"adaptive_calibration.yaml").write_text(yaml.safe_dump(result,sort_keys=False,allow_unicode=True),encoding="utf-8")
    return result


def main()->None:
    parser=argparse.ArgumentParser();parser.add_argument("--left",type=Path,required=True);parser.add_argument("--right",type=Path,required=True);parser.add_argument("--output",type=Path,required=True);args=parser.parse_args();print(json.dumps(run(args.left,args.right,args.output),ensure_ascii=False))


if __name__=="__main__":main()
