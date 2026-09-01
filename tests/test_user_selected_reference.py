from pathlib import Path
import json,tempfile,unittest
from unittest import mock
import numpy as np
import yaml

from reconstruction.height import height_from_plane
from reconstruction.reference_frame import (CANONICAL_CONVENTION,fit_reference_artifact,load_reference_artifact,
    save_reference_artifact,validate_reference_artifact,roi_identity)
from application.session import MeasurementSession
from application.export import export_session
from application.backend_runner import FrozenBackendRunner

ROI={"type":"polygon","coordinate_system":"canonical_cam1","points":[[0,0],[100,0],[100,100],[0,100]]}

def artifact(reference_id="ref_old"):
    return {"schema_version":"1.0","status":"REFERENCE_PLANE_READY","reference_id":reference_id,"source":"fixture","created_at":"now","requested_timestamp_s":1.,"actual_timestamp_s":1.02,"fallback_frame_offset":1,"left_frame_id":"l","right_frame_id":"r","sync_residual_ms":.5,"calibration_id":"cal","calibration_package_hash":None,"video_pair_id":"pair","canonical_convention":CANONICAL_CONVENTION,"roi":ROI,"roi_id":roi_identity(ROI),"plane":{"normal":[0.,0.,1.],"offset_m":-2.,"a":0.,"b":0.,"c":1.,"d":-2.},"unit":"m","plane_rms_m":.001,"support_count":20,"spatial_extent_m":{"x":[0,1],"y":[0,1],"z":[2,2]},"height_definition":"signed orthogonal distance to user-selected reference plane"}

class UserSelectedReferenceTests(unittest.TestCase):
    def test_reference_serialization_and_finite_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=save_reference_artifact(artifact(),Path(tmp)/"ref.yaml");self.assertEqual(load_reference_artifact(path)["reference_id"],"ref_old")
            broken=artifact();broken["plane"]["normal"]=[float("nan"),0,1];save_reference_artifact(broken,path)
            with self.assertRaisesRegex(ValueError,"REFERENCE_ARTIFACT_INCOMPATIBLE"):load_reference_artifact(path)

    def test_binding_mismatches_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=save_reference_artifact(artifact(),Path(tmp)/"ref.yaml")
            for kwargs in ({"calibration_id":"other","video_pair_id":"pair","roi":ROI},{"calibration_id":"cal","video_pair_id":"other","roi":ROI},{"calibration_id":"cal","video_pair_id":"pair","roi":{**ROI,"points":[[0,0],[50,0],[50,50],[0,50]]}}):
                with self.assertRaisesRegex(ValueError,"REFERENCE_ARTIFACT_INCOMPATIBLE"):validate_reference_artifact(path,**kwargs)

    def test_roi_plane_fit_and_requested_actual_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            x,y=np.meshgrid(np.linspace(0,1,6),np.linspace(0,1,6));xyz=np.column_stack((x.ravel(),y.ravel(),2+.01*x.ravel()))
            path=Path(tmp)/"points.npz";np.savez(path,u_px=x.ravel()*90,v_px=y.ravel()*90,xyz_m=xyz)
            value=fit_reference_artifact(path,reference_id="ref",requested_timestamp_s=1.,actual_timestamp_s=1.02,fallback_frame_offset=1,left_frame_id="l",right_frame_id="r",sync_residual_ms=.5,calibration_id="cal",calibration_package_hash=None,video_pair_id="pair",roi=ROI,xyz_point_count=36,source_videos={"left":"l","right":"r"},surface_distance_threshold_m=.01)
            self.assertEqual((value["requested_timestamp_s"],value["actual_timestamp_s"],value["fallback_frame_offset"]),(1.,1.02,1));self.assertEqual(value["support_count"],36)

    def test_measurement_uses_fixed_signed_plane_distance(self):
        heights=height_from_plane(np.array([[0,0,2.01],[0,0,1.99]]),np.array([0,0,1]),-2)
        np.testing.assert_allclose(heights,[.01,-.01]);self.assertEqual(artifact()["height_definition"],"signed orthogonal distance to user-selected reference plane")

    def test_failed_replacement_keeps_old_and_success_replaces_pointer(self):
        with tempfile.TemporaryDirectory() as tmp:
            session=MeasurementSession(Path(tmp),"s");old=save_reference_artifact(artifact(),session.directory/"old.yaml");session.set_active_reference(old,artifact())
            self.assertEqual(session.active_reference_path,old.resolve()) # failed attempt performs no update
            new_value=artifact("ref_new");new=save_reference_artifact(new_value,session.directory/"new.yaml");session.set_active_reference(new,new_value)
            self.assertEqual(session.active_reference_path,new.resolve());self.assertEqual(len(session.references),2)

    def test_legacy_session_loads_without_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            session=MeasurementSession(Path(tmp),"legacy");reloaded=MeasurementSession(Path(tmp),"legacy")
            self.assertIsNone(reloaded.active_reference_path);self.assertEqual(reloaded.references,[])

    def test_export_manifest_contains_reference_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            session=MeasurementSession(Path(tmp)/"sessions","s");ref=save_reference_artifact(artifact(),session.directory/"ref.yaml");session.set_active_reference(ref,artifact());out=export_session(session,Path(tmp)/"export",[])
            manifest=json.loads((out/"session_manifest.json").read_text(encoding="utf-8"));self.assertEqual(manifest["reference"]["status"],"REFERENCE_PLANE_READY")

    def test_runner_modes_remove_or_bind_reference(self):
        repo=Path(__file__).resolve().parents[1];runner=FrozenBackendRunner(repo,repo/"experiments/real_video/HomeTank_004/single_frame_dense_smoke_config.yaml")
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);ref=save_reference_artifact(artifact(),base/"ref.yaml")
            reference=yaml.safe_load(runner.prepare_config(repo/"left.mp4",repo/"right.mp4",1,base/"r",water_roi=ROI,solve_mode="reference").read_text(encoding="utf-8"))
            measurement=yaml.safe_load(runner.prepare_config(repo/"left.mp4",repo/"right.mp4",1,base/"m",water_roi=ROI,solve_mode="measurement",reference_artifact=ref).read_text(encoding="utf-8"))
            self.assertNotIn("reference_plane_file",reference["processing"]);self.assertEqual(Path(measurement["processing"]["reference_artifact_file"]),ref.resolve())

    def test_gui_measurement_enablement_tracks_reference(self):
        from application.main_window import StereoWaveHeightApplication
        app=StereoWaveHeightApplication.__new__(StereoWaveHeightApplication);app.backend_running=False;app.solve_button=mock.Mock();app.reference_button=mock.Mock();app.active_reference_path=None
        app._refresh_reference_controls();app.solve_button.configure.assert_called_with(state="disabled")
        app.active_reference_path=Path("ref.yaml");app._refresh_reference_controls();app.solve_button.configure.assert_called_with(state="normal")

    def test_measurement_without_reference_is_rejected(self):
        repo=Path(__file__).resolve().parents[1];runner=FrozenBackendRunner(repo,repo/"experiments/real_video/HomeTank_004/single_frame_dense_smoke_config.yaml")
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,"requires reference artifact"):
                runner.prepare_config(repo/"left.mp4",repo/"right.mp4",1,Path(tmp)/"m",water_roi=ROI,solve_mode="measurement")

    def test_canonical_convention_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            value=artifact();value["canonical_convention"]="UNKNOWN";path=save_reference_artifact(value,Path(tmp)/"ref.yaml")
            with self.assertRaisesRegex(ValueError,"canonical_convention"):
                validate_reference_artifact(path,calibration_id="cal",video_pair_id="pair",roi=ROI)

    def test_reference_artifact_has_traceability_fields(self):
        required={"reference_id","requested_timestamp_s","actual_timestamp_s","fallback_frame_offset","left_frame_id","right_frame_id","sync_residual_ms","calibration_id","video_pair_id","roi","plane","plane_rms_m","support_count","spatial_extent_m","created_at"}
        self.assertFalse(required-set(artifact()))

    def test_reference_height_is_plane_residual_not_forced_zero(self):
        heights=height_from_plane(np.array([[0,0,2.003],[0,0,1.998]]),np.array([0,0,1]),-2)
        self.assertGreater(float(np.max(np.abs(heights))),0)

    def test_historical_result_keeps_original_reference_id(self):
        old={"reference_id":"ref_old"};active=artifact("ref_new")
        self.assertEqual(old["reference_id"],"ref_old");self.assertEqual(active["reference_id"],"ref_new")

    def test_session_reference_index_contains_active_and_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            session=MeasurementSession(Path(tmp),"s");path=save_reference_artifact(artifact(),session.directory/"ref.yaml");session.set_active_reference(path,artifact())
            index=json.loads(session.reference_index_path.read_text(encoding="utf-8"));self.assertEqual(index["status"],"REFERENCE_PLANE_READY");self.assertEqual(index["history"][0]["reference_id"],"ref_old")

    def test_reference_backend_is_dispatched_on_background_thread(self):
        source=(Path(__file__).resolve().parents[1]/"src/application/main_window.py").read_text(encoding="utf-8")
        self.assertIn("threading.Thread(target=work,daemon=True).start()",source);self.assertIn('self._start_backend("reference")',source)

    def test_export_height_definition_is_explicit(self):
        self.assertEqual(artifact()["height_definition"],"signed orthogonal distance to user-selected reference plane")

if __name__=="__main__":unittest.main()
