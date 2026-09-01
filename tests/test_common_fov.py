from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import numpy as np

from reconstruction.common_fov import CommonFov, CommonFovError, compute_common_fov, crop_to_full, load_common_fov, save_common_fov, validate_roi
from application.visualization import DisplayTransform


def calibration(*,cx1:float=49.5,distortion:float=0.0)->dict:
    k0=[[100.,0.,49.5],[0.,100.,39.5],[0.,0.,1.]]
    k1=[[100.,0.,cx1],[0.,100.,39.5],[0.,0.,1.]]
    return {"calibration_id":"fixture","image_size":[100,80],
        "mono_cam0":{"K":k0,"D":[0,0,0,0,0]},"mono_cam1":{"K":k1,"D":[distortion,0,0,0,0]},
        "stereo":{"R_right_from_left":np.eye(3).tolist(),"T_right_from_left_m":[-.1,0,0]},
        "rectification":{"alpha":1.0,"flags":"CALIB_ZERO_DISPARITY"}}


class CommonFovTests(unittest.TestCase):
    def test_identity_geometry_is_deterministic_and_bbox_encloses_mask(self):
        first=compute_common_fov(calibration(),(100,80));second=compute_common_fov(calibration(),(100,80))
        self.assertEqual(first.identity,second.identity);self.assertTrue(np.array_equal(first.safe_mask,second.safe_mask))
        x0,y0,x1,y1=first.bbox;ys,xs=np.nonzero(first.safe_mask)
        self.assertLessEqual(x0,int(xs.min()));self.assertGreaterEqual(x1,int(xs.max())+1)
        self.assertGreater(first.metadata["coverage_ratio"],.9)

    def test_asymmetric_geometry_reduces_common_fov(self):
        normal=compute_common_fov(calibration(),(100,80));shifted=compute_common_fov(calibration(cx1=70,distortion=.3),(100,80))
        self.assertLess(shifted.metadata["coverage_ratio"],normal.metadata["coverage_ratio"])

    def test_size_mismatch_is_structured(self):
        with self.assertRaisesRegex(CommonFovError,"COMMON_FOV_CALIBRATION_SIZE_MISMATCH"):compute_common_fov(calibration(),(99,80))

    def test_roi_checks_every_pixel_not_only_corners(self):
        mask=np.ones((20,20),bool);mask[10,10]=False
        common=CommonFov(mask,mask,(0,0,20,20),{"common_fov_id":"x","image_size":[20,20]})
        valid={"type":"polygon","coordinate_system":"canonical_cam1","points":[[1,1],[5,1],[5,5],[1,5]]}
        validate_roi(valid,common)
        invalid={"type":"polygon","coordinate_system":"canonical_cam1","points":[[5,5],[15,5],[15,15],[5,15]]}
        with self.assertRaisesRegex(CommonFovError,"ROI_OUTSIDE_STEREO_COMMON_FOV"):validate_roi(invalid,common)

    def test_crop_canvas_full_mapping_and_artifact_roundtrip(self):
        transform=DisplayTransform.fit(40,20,400,300)
        canvas=transform.full_pixel_to_canvas(15,27,(10,20))
        self.assertEqual(transform.canvas_to_full_pixel(*canvas,(10,20)),(15,27));self.assertEqual(crop_to_full((5,7),(10,20,50,40)),(15,27))
        value=compute_common_fov(calibration(),(100,80))
        with tempfile.TemporaryDirectory() as tmp:
            _mask,metadata=save_common_fov(value,Path(tmp));loaded=load_common_fov(metadata)
            self.assertEqual(loaded.identity,value.identity);self.assertTrue(np.array_equal(loaded.safe_mask,value.safe_mask))


if __name__=="__main__":unittest.main()
