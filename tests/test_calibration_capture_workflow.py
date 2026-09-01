import json
from pathlib import Path
import unittest

import numpy as np

from calibration.capture_qa import deterministic_scale_bins, evaluate_capture, grid_cell, pair_detections, prepare_training_and_holdout, optional_training_and_holdout
from calibration.compare_calibrations import calibration_ab_gate
from calibration.wass_ab_plan import validate_ab_plan


def camera(cx, cy, area=.05, sharp=200):
    x=np.linspace(cx-40,cx+40,9);y=np.linspace(cy-25,cy+25,6);corners=np.array([[a,b] for b in y for a in x])
    return {"center_x_px":cx,"center_y_px":cy,"area_fraction":area,"perspective_score":.1,
            "sharpness":sharp,"corners":corners.tolist()}

def pair(index,cx,cy,area=.05):
    left=camera(cx,cy,area);right=camera(cx+5,cy+2,area)
    return {"pair_id":f"p{index:03d}","left":left,"right":right,"left_corners":left["corners"],"right_corners":right["corners"]}

class CaptureWorkflowTests(unittest.TestCase):
    def test_grid_assignment(self):
        self.assertEqual([grid_cell(x,y,(900,600)) for y in (10,250,590) for x in (10,450,890)],list(range(9)))

    def test_bilateral_pairing_is_timestamp_based(self):
        left=[{"frame_id":"l0","pts_s":1.0},{"frame_id":"l1","pts_s":2.0}];right=[{"frame_id":"r0","pts_s":2.01},{"frame_id":"r1","pts_s":1.01}]
        self.assertEqual([(a["frame_id"],b["frame_id"]) for a,b in pair_detections(left,right,maximum_delta_s=.02)],[('l0','r1'),('l1','r0')])

    def test_scale_bins_and_quick_qa_are_deterministic(self):
        self.assertEqual(deterministic_scale_bins([1,2,3]),deterministic_scale_bins([1,2,3]))
        pairs=[pair(i,100+(i%3)*300,80+(i//3%3)*200,.02+.002*i) for i in range(27)]
        a=evaluate_capture(pairs,image_size_wh=(900,600),sampled_left=27,sampled_right=27,detected_left=27,detected_right=27)
        b=evaluate_capture(pairs,image_size_wh=(900,600),sampled_left=27,sampled_right=27,detected_left=27,detected_right=27)
        self.assertEqual(a,b);self.assertEqual(a["grid"]["left"], [3]*9)

    def test_training_and_heldout_are_disjoint_and_deterministic(self):
        pairs=[pair(i,100+(i%3)*300+(i%4),80+(i//3%3)*200+(i%5),.02+.001*i) for i in range(45)]
        first=prepare_training_and_holdout(pairs,image_size_wh=(900,600),training_count=10,heldout_count=10)
        second=prepare_training_and_holdout(pairs,image_size_wh=(900,600),training_count=10,heldout_count=10)
        self.assertEqual(first,second);self.assertTrue(set(first["training_pair_ids"]).isdisjoint(first["heldout_pair_ids"]))

    def test_optional_split_does_not_discard_qa_for_duplicate_poses(self):
        pairs=[pair(i,450,300,.05) for i in range(40)]
        result=optional_training_and_holdout(pairs,image_size_wh=(900,600))
        self.assertEqual(result["proposed_split_status"],"INSUFFICIENT_NON_DUPLICATE_POSES_FOR_20_20_SPLIT")

    def test_gate_blocks_bad_and_passes_clear_improvement(self):
        old={"rms_px":10.,"p95_px":20.,"max_px":40.,"epipolar_rms_px":8.}
        sanity={"baseline_difference_percent":2.,"finite_and_plausible":True}
        bad={"rms_px":9.,"p95_px":18.,"max_px":50.,"epipolar_rms_px":9.}
        good={"rms_px":5.,"p95_px":10.,"max_px":30.,"epipolar_rms_px":7.}
        self.assertEqual(calibration_ab_gate(old,bad,sanity)["status"],"CALIBRATION_NOT_READY_FOR_WASS_AB")
        self.assertEqual(calibration_ab_gate(old,good,sanity)["status"],"CALIBRATION_READY_FOR_WASS_AB")

    def test_ab_plan_allows_only_calibration_change(self):
        common={"stereo_videos":"v","target_time_s":1,"selected_frames":"f","sync_model":"s","sync_residual_ms":.1,"rectification_policy":"r","matcher_config":"m","stereo_config":"st","post_filter":"p","water_roi":"w"}
        plan={"gate_required":"CALIBRATION_READY_FOR_WASS_AB","max_new_wass_runs":1,"old":{**common,"calibration":"old","execution":"FROZEN_EXISTING_RESULT"},"new":{**common,"calibration":"new","execution":"FUTURE_SINGLE_RUN"}}
        validate_ab_plan(plan);plan["new"]["water_roi"]="changed"
        with self.assertRaises(ValueError):validate_ab_plan(plan)

    def test_frozen_artifacts_self_test_remains_incomplete(self):
        source=Path(r"D:\stereo-wave-height-runs\HomeTank_004\calibration_attempt\stereo_pairs.json")
        if not source.exists():self.skipTest("local frozen detection artifact unavailable")
        from calibration.capture_qa import normalize_existing_pairs
        pairs,size=normalize_existing_pairs(json.loads(source.read_text(encoding="utf-8")))
        result=evaluate_capture(pairs,image_size_wh=size,sampled_left=192,sampled_right=192,detected_left=192,detected_right=192)
        self.assertEqual(result["status"],"CAPTURE_INCOMPLETE_NEEDS_MORE_VIEWS")
        self.assertTrue(any("TOP" in item for item in result["missing"]));self.assertTrue(any("EDGE" in item for item in result["missing"]));self.assertTrue(any("CORNER" in item for item in result["missing"]))

if __name__ == "__main__": unittest.main()
