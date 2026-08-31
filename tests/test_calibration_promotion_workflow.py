from pathlib import Path
import tempfile
import unittest
import yaml
import numpy as np

from calibration.artifacts import (approve_for_wass_ab,build_calibration_package,canonical_hash,
    generate_future_wass_config,load_registry,promote_production,rollback_production,verify_package_consistency)
from calibration.wass_support_ab import evaluate,spatial_occupancy,validate_single_variable


def calibration():
    return {"schema_version":"1.0","image_size_wh":[640,480],"mono_left":{"rms_px":.2,"camera_matrix":np.diag([500,500,1]).tolist(),"distortion":[0]*5},"mono_right":{"rms_px":.2,"camera_matrix":np.diag([500,500,1]).tolist(),"distortion":[0]*5},"stereo_rms_px":.3,"epipolar_rms_px":.2,"rotation_right_from_left":np.eye(3).tolist(),"translation_right_from_left_m":[-.07,0,0]}

def metadata(calibration_id="old",rms=.002,success=True):
    return {"calibration_id":calibration_id,"stereo_videos":"v","target_time_s":1.,"left_frame_id":"l","right_frame_id":"r","sync_model":"s","sync_residual_ms":.5,"matcher_config_hash":"m","stereo_config_hash":"t","post_filter":"p","water_roi":[0,0,100,100],"rectification_policy":"fixed","reconstruction_success":success,"triangulated_count":100,"final_xyz_count":80,"common_fov_observed_percent":5.,"xyz_extent":{"x":[0,1],"y":[0,1],"z":[1,2]},"geometry_qa":{"finite":True,"plane_rms_m":rms}}

class PromotionWorkflowTests(unittest.TestCase):
    def test_manifest_hash_deterministic_and_roundtrip(self):
        self.assertEqual(canonical_hash({"b":2,"a":1}),canonical_hash({"a":1,"b":2}))
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/"cal.yaml";source.write_text(yaml.safe_dump(calibration()),encoding="utf-8")
            package=build_calibration_package(source,Path(directory)/"package",calibration_id="c1",source={"capture_left_video":"l","capture_right_video":"r","selected_candidate_ids":[],"heldout_candidate_ids":[],"checkerboard":{"inner_corners":[9,6],"square_size_m":.02}},qa={},created_at="fixed")
            self.assertEqual(verify_package_consistency(package)["status"],"PASS")

    def test_xml_mismatch_blocks_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/"cal.yaml";source.write_text(yaml.safe_dump(calibration()),encoding="utf-8");package=build_calibration_package(source,Path(directory)/"package",calibration_id="c1",source={},qa={},created_at="fixed")
            xml=package/"wass_fixed/intrinsics_00.xml";xml.write_text(xml.read_text(encoding="utf-8").replace("500","501",1),encoding="utf-8")
            check=verify_package_consistency(package);self.assertEqual(check["status"],"CALIBRATION_WASS_EXPORT_MISMATCH")
            with self.assertRaises(ValueError):approve_for_wass_ab({"calibrations":{"c1":{}}},"c1",calibration_gate="CALIBRATION_READY_FOR_WASS_AB",consistency=check["status"])

    def test_promotion_requires_both_levels_and_rollback_preserves_old(self):
        registry={"current_production_calibration_id":"old","calibrations":{"old":{"lifecycle_status":"PROMOTED_PRODUCTION_CALIBRATION","package_path":"old"},"new":{"lifecycle_status":"CANDIDATE","package_path":"new"}}}
        with self.assertRaises(ValueError):promote_production(registry,"new",recommendation="PROMOTE",approved_at="now",reason="x")
        approved=approve_for_wass_ab(registry,"new",calibration_gate="CALIBRATION_READY_FOR_WASS_AB",consistency="PASS");promoted=promote_production(approved,"new",recommendation="PROMOTE",approved_at="now",reason="ab")
        rolled=rollback_production(promoted,"old",reason="rollback");self.assertEqual(rolled["current_production_calibration_id"],"old");self.assertIn("old",rolled["calibrations"])

    def test_future_config_binds_package_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/"cal.yaml";source.write_text(yaml.safe_dump(calibration()),encoding="utf-8");package=build_calibration_package(source,Path(directory)/"package",calibration_id="new",source={},qa={},created_at="fixed");destination=Path(directory)/"run.yaml"
            generate_future_wass_config(package,{"target_time_s":1},destination,old_calibration_id="old");result=yaml.safe_load(destination.read_text(encoding="utf-8"));self.assertEqual(result["calibration_id"],"new");self.assertEqual(result["single_variable_changed"],"calibration K/D/R/T")

    def test_ab_rejects_frame_or_other_variable_change(self):
        old,new=metadata(),metadata("new");new["left_frame_id"]="other"
        with self.assertRaisesRegex(ValueError,"AB_INVALID_MULTIPLE_VARIABLES_CHANGED"):validate_single_variable(old,new)

    def test_spatial_occupancy_fixed_grid(self):
        result=spatial_occupancy(np.array([[1,1],[99,99],[2,2]]),(0,0,100,100));self.assertEqual(result["occupied_cells"],2);self.assertEqual(result["coverage_percent"],2.)

    def test_identity_is_no_material_improvement(self):
        old=metadata();points=np.array([[5,5],[25,25],[75,75]])
        result=evaluate(old,dict(old),points,points);self.assertEqual(result["decision"],{"classification":"WASS_AB_NO_MATERIAL_IMPROVEMENT","recommendation":"KEEP_OLD"})

    def test_geometry_regression_blocks_even_with_more_support(self):
        old,new=metadata(),metadata("new",rms=.01);a=np.array([[5,5]]);b=np.array([[5,5],[25,25],[45,45],[65,65]])
        self.assertEqual(evaluate(old,new,a,b)["decision"]["recommendation"],"KEEP_OLD")

    def test_support_and_spatial_gain_recommends_promotion(self):
        old,new=metadata(),metadata("new");a=np.array([[5,5]]);b=np.array([[5,5],[25,25],[45,45]])
        result=evaluate(old,new,a,b);self.assertEqual(result["decision"],{"classification":"WASS_AB_SUPPORT_IMPROVED","recommendation":"PROMOTE"})

    def test_old_baseline_registry_integration(self):
        root=Path(__file__).resolve().parents[1]/"experiments/real_video/HomeTank_004/calibrations"
        registry=load_registry(root/"calibration_registry.yaml");self.assertEqual(registry["current_production_calibration_id"],"HomeTank_004_frozen_calibration_v1")
        self.assertEqual(verify_package_consistency(root/"HomeTank_004_frozen_calibration_v1")["status"],"PASS")

if __name__=="__main__":unittest.main()
