import unittest
import numpy as np

from calibration.checkerboard import CheckerboardSpec
from calibration.adaptive_calibration import SplitCalibrationProvenance,calibrate_split_official,parameter_plausibility,rectification_residuals,select_distortion_complexity,classify_rectification_health
from calibration.capture_qa import evaluate_split_capture
from reconstruction.scene_diagnostics import diagnose_stereo_scene
from reconstruction.adaptation import choose_adaptation,geometry_disparity_expectation
from reconstruction.quality import component_diagnostics,height_confidence,resolve_quality


class RealWorldAdaptationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:import cv2
        except ImportError as error:raise unittest.SkipTest(str(error))
        cls.cv2=cv2;cls.spec=CheckerboardSpec(9,6,.02)

    def correspondences(self,count=18):
        cv2=self.cv2;obj=self.spec.object_points_m();k0=np.array([[820.,0,320],[0,815,240],[0,0,1.]]);k1=np.array([[825.,0,318],[0,818,242],[0,0,1.]]);r01,_=cv2.Rodrigues(np.array([.004,-.009,.003]));t01=np.array([[-.12],[.001],[.002]])
        objects=[];left=[];right=[]
        for i in range(count):
            rv=np.array([.05*np.sin(i),.12*np.cos(i/2),.03*np.sin(i/3)]);r0,_=cv2.Rodrigues(rv);t0=np.array([[-.1+.012*i],[-.06+.006*i],[.85+.02*i]]);r1=r01@r0;t1=r01@t0+t01;rv1,_=cv2.Rodrigues(r1);lp,_=cv2.projectPoints(obj,rv,t0,k0,np.zeros(5));rp,_=cv2.projectPoints(obj,rv1,t1,k1,np.zeros(5));objects.append(obj);left.append(lp);right.append(rp)
        return objects,left,right

    def test_split_mono_sets_may_differ_and_stereo_is_bilateral_subset(self):
        objects,left,right=self.correspondences();prov=SplitCalibrationProvenance(tuple(f"l{i}" for i in range(18)),tuple(f"r{i}" for i in range(16)),tuple(f"s{i}" for i in range(12)),tuple(f"h{i}" for i in range(3)))
        result=calibrate_split_official(mono_object_points_left=objects,mono_image_points_left=left,mono_object_points_right=objects[:16],mono_image_points_right=right[:16],stereo_object_points=objects[:12],stereo_image_points_left=left[:12],stereo_image_points_right=right[:12],image_size_wh=(640,480),square_size_m=.02,provenance=prov)
        self.assertEqual(result.backend,"OPENCV_OFFICIAL_SPLIT_MONO_FIX_INTRINSIC");self.assertLess(result.stereo_rms_px,1e-3);self.assertEqual(len(result.mono_left.per_view_rms_px),18);self.assertEqual(len(result.mono_right.per_view_rms_px),16)
        self.assertEqual(parameter_plausibility(result)["status"],"CALIBRATION_PARAMETER_STABLE_PROXY")

    def test_heldout_validation_is_disjoint_and_spatial(self):
        objects,left,right=self.correspondences();prov=SplitCalibrationProvenance(tuple(f"l{i}" for i in range(15)),tuple(f"r{i}" for i in range(15)),tuple(f"s{i}" for i in range(12)),("s0",))
        with self.assertRaisesRegex(ValueError,"disjoint"):prov.validate()
        result=calibrate_split_official(mono_object_points_left=objects[:15],mono_image_points_left=left[:15],mono_object_points_right=objects[:15],mono_image_points_right=right[:15],stereo_object_points=objects[:12],stereo_image_points_left=left[:12],stereo_image_points_right=right[:12],image_size_wh=(640,480),square_size_m=.02,provenance=SplitCalibrationProvenance(tuple(f"l{i}" for i in range(15)),tuple(f"r{i}" for i in range(15)),tuple(f"s{i}" for i in range(12))))
        qa=rectification_residuals(left[12:],right[12:],k0=result.mono_left.camera_matrix,d0=result.mono_left.distortion,k1=result.mono_right.camera_matrix,d1=result.mono_right.distortion,r=result.rotation_right_from_left,t=result.translation_right_from_left_m,image_size_wh=(640,480));self.assertEqual(len(qa["spatial_3x3"]),9);self.assertLess(qa["rms_px"],1e-3)

    def test_capture_qa_uses_independent_mono_and_overlap_coordinates(self):
        def item(i,x,y):return {"frame_id":str(i),"pts_s":i/10,"center_x_px":x,"center_y_px":y}
        left=[item(i,50+(i%4)*150,50+(i//4)*120) for i in range(16)];right=[item(i,70+(i%4)*145,60+(i//4)*115) for i in range(16)];pairs=[{"left":left[i],"right":right[i]} for i in range(12)]
        result=evaluate_split_capture(left,right,pairs,image_size_wh=(640,480));self.assertFalse(result["bilateral_full_fov_required"]);self.assertEqual(result["left_mono"]["candidate_count"],16);self.assertEqual(result["stereo_overlap"]["status"],"STEREO_OVERLAP_READY")

    def test_scene_diagnostics_detects_exposure_blur_texture_and_glare(self):
        rng=np.random.default_rng(4);left=np.full((120,160),40,np.uint8);right=np.full((120,160),245,np.uint8);right[:,::5]=255
        result=diagnose_stereo_scene(left,right);self.assertIn("PHOTOMETRIC_RISK",result["quality_reasons"]);self.assertIn("TEXTURE_LIMITED",result["quality_reasons"]);self.assertIn("SPECULAR_OR_CLIPPING_RISK",result["quality_reasons"])
        textured=rng.integers(20,100,(120,160),dtype=np.uint8);sharp=diagnose_stereo_scene(textured,textured)["left"]["blur_laplacian_variance"];blur=diagnose_stereo_scene(self.cv2.GaussianBlur(textured,(15,15),0),textured)["left"]["blur_laplacian_variance"];self.assertGreater(sharp,blur)
        self.assertEqual(result,diagnose_stereo_scene(left,right))

    def test_quality_precedence_components_and_adaptation_provenance(self):
        quality=resolve_quality(["TEXTURE_LIMITED"],geometry_valid=False,support_valid=True);self.assertEqual(quality["quality_status"],"GEOMETRY_UNRELIABLE")
        labels=np.array([[1,0,2],[1,0,2]]);components=component_diagnostics(labels);self.assertEqual([x["count"] for x in components],[2,2])
        self.assertEqual(height_confidence(point_source="UNSUPPORTED",matching_reliable=True,reference_confidence="HIGH"),"UNSUPPORTED")
        scene={"quality_reasons":["TEXTURE_LIMITED"]};manifest=choose_adaptation(scene);self.assertEqual(manifest["matcher_profile_status"],"EXPERIMENTAL_NOT_PROMOTED");self.assertFalse(manifest["photometric_preprocessing_applied"])
        disparity=geometry_disparity_expectation(focal_px=3000,baseline_m=.25,depth_min_m=1.5,depth_max_m=3);self.assertEqual(disparity["maximum_disparity_px"],500)

    def test_distortion_complexity_and_rectification_health_use_heldout_evidence(self):
        candidates=[{"model":"OPENCV_4_COEFFICIENT","complexity":4,"heldout_rectification_rms_px":.42,"parameter_stability":"STABLE"},{"model":"OPENCV_5_COEFFICIENT","complexity":5,"heldout_rectification_rms_px":.40,"parameter_stability":"STABLE"},{"model":"RATIONAL","complexity":8,"heldout_rectification_rms_px":.2,"parameter_stability":"CALIBRATION_PARAMETER_UNSTABLE"}]
        self.assertEqual(select_distortion_complexity(candidates)["selected_model"],"OPENCV_4_COEFFICIENT")
        health=classify_rectification_health({"rms_px":.3,"p95_px":.8,"max_px":1.2},matcher_vertical_tolerance_px=2,image_height_px=1080);self.assertEqual(health["status"],"RECTIFICATION_PASS")

if __name__=="__main__":unittest.main()
