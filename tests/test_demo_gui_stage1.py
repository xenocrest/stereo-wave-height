from pathlib import Path
import json
import queue
import subprocess
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace

from application.backend_runner import BackendResultError, parse_backend_result
from application.backend_runner import FrozenBackendRunner, backend_command
from application.runtime_paths import resolve_runtime_paths
from application.input_workflow import CALIBRATION_FILE_TYPES, VIDEO_FILE_TYPES, GuidedInputState, load_calibration_selection, validate_gui_calibration
from application.fallback import FALLBACK_FRAME_OFFSETS, run_bounded_fallback
from application.video_tools import LatestFrameDecoder
from process_utils import hidden_process_kwargs
from application.session import MeasurementRecord, MeasurementSession
from application.export import export_session
from application.visualization import DisplayTransform, DenseMeasurementView, make_height_overlay
import numpy as np
import yaml


class DemoGuiStage1Tests(unittest.TestCase):
    @staticmethod
    def _gui_calibration_harness():
        from application.main_window import StereoWaveHeightApplication
        app=StereoWaveHeightApplication.__new__(StereoWaveHeightApplication)
        app.variables={key:mock.Mock() for key in (
            "calibration_path","calibration_file","calibration_load_status","calibration_quality","app_state",
            "left_model","left_fx","left_fy","left_cx","left_cy","left_D",
            "right_model","right_fx","right_fy","right_cx","right_cy","right_D")}
        app.variables["calibration_path"].get.return_value=""
        app.stereo_text=mock.Mock();app.demo_continue_button=mock.Mock()
        app.input_state=GuidedInputState();app.pending_demo_calibration=None
        app.calibration_data=None;app.common_fov=None;app.common_fov_file=None;app.water_roi=None
        app.common_fov_state="WAITING_FOR_VIDEO_PAIR";app._common_fov_generation=0
        app._common_fov_started_at=None;app._common_fov_timeout_seconds=10.0;app._preview_request_generation=0
        app._refresh_common_fov=mock.Mock();app._ensure_common_fov=mock.Mock();app._refresh_step_state=mock.Mock();app._log=mock.Mock()
        app._invalidate_reference=mock.Mock()
        app._worker_messages=queue.Queue();app.calibrate_button=mock.Mock()
        return app

    def _record(self, directory: Path, name: str) -> MeasurementRecord:
        return MeasurementRecord(29.4654055, name, directory, directory/"single_frame_result.json",
            directory/"right.png", directory/"height.png", directory/"status.png", None,
            "2026-08-29T00:00:00+08:00", {"status":"SINGLE_FRAME_DENSE_HEIGHT_COMPLETED"})

    def test_duplicate_timestamp_names_do_not_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            session=MeasurementSession(Path(temporary),"session")
            name1,_=session.allocate(29.4654055); session.add(self._record(session.directory,name1))
            name2,_=session.allocate(29.4654055)
            self.assertEqual((name1,name2),("29.465s","29.465s_02"))

    def test_result_parser_and_session_reload(self):
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)/"result"; (output/"selected_pair").mkdir(parents=True); (output/"dense_height").mkdir()
            for path in (output/"selected_pair/right.png",output/"dense_height/dense_height.png",output/"dense_height/dense_height_status.png"): path.write_bytes(b"png")
            (output/"single_frame_result.json").write_text(json.dumps({"status":"SINGLE_FRAME_DENSE_HEIGHT_COMPLETED","requested_time_s":29.4654055,"dense_height":{"artifact_paths":{}}}),encoding="utf-8")
            record=parse_backend_result(output); session=MeasurementSession(Path(temporary),"session"); session.add(record)
            reloaded=MeasurementSession(Path(temporary),"session")
            self.assertEqual(reloaded.records[0].target_time_sec,29.4654055)
            self.assertEqual(reloaded.records[0].dense_height_path,output/"dense_height/dense_height.png")

    def test_failed_or_incomplete_backend_is_explicit(self):
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary); (output/"single_frame_result.json").write_text(json.dumps({"status":"FAILED","requested_time_s":1}),encoding="utf-8")
            with self.assertRaisesRegex(BackendResultError,"FAILED"): parse_backend_result(output)

    def test_external_request_config_makes_template_resources_absolute(self):
        repository=Path(__file__).resolve().parents[1]
        runner=FrozenBackendRunner(repository,repository/"experiments/real_video/HomeTank_004/single_frame_dense_smoke_config.yaml")
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)/"measurement"
            config=runner.prepare_config(repository/"left.mp4",repository/"right.mp4",1.25,output)
            import yaml
            data=yaml.safe_load(config.read_text(encoding="utf-8"))
            self.assertTrue(Path(data["calibration"]["source"]).is_absolute())
            self.assertTrue(Path(data["input"]["ffmpeg_executable"]).is_absolute())
            self.assertTrue(Path(data["processing"]["reference_plane_file"]).is_absolute())
            self.assertTrue(Path(data["dense_height"]["mapping_file"]).is_absolute())

    def test_demo_request_without_common_fov_removes_template_artifact_dependency(self):
        repository=Path(__file__).resolve().parents[1]
        runner=FrozenBackendRunner(repository,repository/"experiments/real_video/HomeTank_004/single_frame_dense_smoke_config.yaml")
        roi={"type":"polygon","coordinate_system":"canonical_cam1","points":[[10,10],[20,10],[20,20],[10,20]],"working_view":"FULL_CANONICAL_CAM1"}
        with tempfile.TemporaryDirectory() as temporary:
            config=runner.prepare_config(repository/"left.mp4",repository/"right.mp4",1.25,Path(temporary)/"measurement",water_roi=roi)
            data=yaml.safe_load(config.read_text(encoding="utf-8"))
            self.assertNotIn("common_fov_file",data["dense_height"])

    def test_application_imports_without_opening_window(self):
        from application import StereoWaveHeightApplication
        self.assertTrue(callable(StereoWaveHeightApplication))

    def test_development_and_packaged_resource_resolution(self):
        repository=Path(__file__).resolve().parents[1]
        development=resolve_runtime_paths(repository,frozen=False)
        packaged=resolve_runtime_paths(executable=Path("C:/portable/StereoWaveHeightDemo/StereoWaveHeightDemo.exe"),frozen=True)
        self.assertEqual(development.experiment,repository/"experiments/real_video/HomeTank_005")
        self.assertEqual(packaged.experiment,Path("C:/portable/StereoWaveHeightDemo/resources/HomeTank_005"))
        self.assertEqual(packaged.ffmpeg,Path("C:/portable/StereoWaveHeightDemo/runtime/ffmpeg/ffmpeg.exe"))

    def test_demo_only_calibration_package_loads_without_relaxing_production_status(self):
        repository=Path(__file__).resolve().parents[1]
        manifest=repository/"experiments/real_video/HomeTank_005/calibrations/HomeTank_005_demo_only_v1/manifest.yaml"
        calibration,path,mode=load_calibration_selection(manifest)
        self.assertEqual(mode,"DEMO_ESTIMATION_MODE")
        self.assertEqual(calibration["status"],"CALIBRATION_OPERATIONAL_DOMAIN_FAIL")
        self.assertEqual(path.name,"opencv_calibration.yaml")
        state=GuidedInputState();state.mark_calibration_ready(operating_mode=mode)
        self.assertTrue(state.calibration_ready);self.assertTrue(state.calibration_step_completed)
        self.assertEqual(state.operating_mode,"DEMO_ESTIMATION_MODE")

    def test_backend_command_switches_to_packaged_executable_mode(self):
        config=Path("C:/request.yaml")
        packaged=backend_command(config,executable=Path("C:/Demo.exe"),frozen=True)
        development=backend_command(config,executable=Path("C:/python.exe"),frozen=False)
        self.assertEqual(packaged[:2],[str(Path("C:/Demo.exe").resolve()),"--backend-single-frame"])
        self.assertIn("src.reconstruction.run_single_frame",development)

    def test_guided_calibration_modes_gate_measurement_step(self):
        state=GuidedInputState()
        self.assertFalse(state.measurement_ready)
        state.set_mode("videos"); state.mark_measurement_video("left"); state.mark_measurement_video("right")
        self.assertFalse(state.measurement_ready)
        state.mark_calibration_ready(); self.assertTrue(state.measurement_ready)
        self.assertTrue(state.calibration_step_completed)
        state.mark_calibration_failed(); self.assertFalse(state.measurement_ready)
        self.assertFalse(state.calibration_step_completed)
        state.set_mode("existing"); self.assertFalse(state.calibration_ready)

    def test_scientific_qa_status_does_not_reset_gui_completion(self):
        state=GuidedInputState()
        state.mark_calibration_ready(operating_mode="DEMO_ESTIMATION_MODE",quality_status="QA_FAIL")
        self.assertTrue(state.calibration_step_completed)
        self.assertTrue(state.calibration_ready)
        self.assertEqual(state.calibration_quality_status,"QA_FAIL")

    def test_non_finite_calibration_is_an_engineering_failure(self):
        data={"image_size_wh":[10,10],"mono_cam0":{"K":[[1,0,0],[0,1,0],[0,0,1]],"D":[0]},
              "mono_cam1":{"K":[[1,0,0],[0,1,0],[0,0,1]],"D":[0]},
              "stereo":{"R_right_from_left":[[1,0,0],[0,1,0],[0,0,1]],"T_right_from_left_m":[float("nan"),0,0]}}
        with self.assertRaisesRegex(ValueError,"NaN or Inf"):validate_gui_calibration(data)

    def test_loaded_demo_calibration_is_immediately_completed_without_qa_mutation(self):
        from application.main_window import StereoWaveHeightApplication
        repository=Path(__file__).resolve().parents[1]
        manifest=repository/"experiments/real_video/HomeTank_005/calibrations/HomeTank_005_demo_only_v1/manifest.yaml"
        calibration,path,mode=load_calibration_selection(manifest);original_status=calibration["status"]
        app=self._gui_calibration_harness()
        StereoWaveHeightApplication._apply_calibration(app,calibration,path,operating_mode=mode)
        self.assertTrue(app.input_state.calibration_step_completed)
        self.assertTrue(app.input_state.calibration_ready)
        self.assertEqual(app.input_state.calibration_quality_status,"QA_FAIL")
        self.assertEqual(app.calibration_data["status"],original_status)
        app.variables["calibration_load_status"].set.assert_any_call("✓ 标定完成，可以进入测量")
        app.variables["app_state"].set.assert_called_with("当前模式：演示模式")
        app.demo_continue_button.configure.assert_called_with(state="disabled")

    def test_accepted_demo_qa_failure_bypasses_common_fov_after_second_video(self):
        from application.main_window import StereoWaveHeightApplication
        app=self._gui_calibration_harness();app.session=SimpleNamespace(directory=Path("C:/session"))
        app.calibration_data={"status":"GUI_CALIBRATION_COMPLETED_REQUIRES_QA"};app.mapping_file=None
        app.input_state.mark_calibration_ready(operating_mode="DEMO_ESTIMATION_MODE",quality_status="QA_FAIL")
        app.input_state.mark_measurement_video("left");app.input_state.mark_measurement_video("right")
        app.metadata={"left_measurement":SimpleNamespace(width=1920,height=1080),"right_measurement":SimpleNamespace(width=1920,height=1080)}
        app.variables["common_fov_status"]=mock.Mock()
        with mock.patch("application.main_window.save_canonical_cam1_wass_mapping",return_value=Path("C:/session/mapping.yaml")):
            StereoWaveHeightApplication._prepare_demo_working_view(app)
        self.assertEqual(app.common_fov_state,"DEMO_RIGHT_VIEW_READY")
        self.assertIsNone(app.common_fov)
        self.assertEqual(app.mapping_file,Path("C:/session/mapping.yaml"))
        app._refresh_common_fov.assert_not_called()

    def test_demo_roi_mapping_uses_full_canonical_cam1_without_common_fov(self):
        from application.main_window import StereoWaveHeightApplication
        app=self._gui_calibration_harness();app.water_roi=(20,350,480,680)
        app.input_state.mark_calibration_ready(operating_mode="DEMO_ESTIMATION_MODE",quality_status="QA_FAIL")
        mapping=StereoWaveHeightApplication._roi_mapping(app)
        self.assertEqual(mapping["coordinate_system"],"canonical_cam1")
        self.assertEqual(mapping["working_view"],"FULL_CANONICAL_CAM1")
        self.assertNotIn("common_fov_id",mapping)

    def test_common_fov_worker_exception_becomes_failed(self):
        from application.main_window import StereoWaveHeightApplication
        app=self._gui_calibration_harness();app._refresh_reference_controls=mock.Mock()
        app.variables["common_fov_status"]=mock.Mock();app._common_fov_generation=2
        StereoWaveHeightApplication._fail_common_fov(app,"boom")
        self.assertEqual(app.common_fov_state,"COMMON_FOV_FAILED")
        app.variables["common_fov_status"].set.assert_called_with("双目公共区域计算失败：boom")

    def test_common_fov_result_reaches_gui_apply(self):
        from application.main_window import StereoWaveHeightApplication
        app=self._gui_calibration_harness();app._apply_common_fov=mock.Mock();app._common_fov_generation=3
        app.common_fov_state="COMPUTING_COMMON_FOV";sentinel=object()
        app._worker_messages.put(("common_fov_ready",(3,sentinel,12.5)))
        StereoWaveHeightApplication._poll_worker(app)
        app._apply_common_fov.assert_called_once_with(sentinel,12.5)

    def test_common_fov_timeout_cannot_wait_indefinitely(self):
        from application.main_window import StereoWaveHeightApplication
        app=self._gui_calibration_harness();app.common_fov_state="COMPUTING_COMMON_FOV"
        app._common_fov_started_at=100.0;app._common_fov_timeout_seconds=10.0;app._fail_common_fov=mock.Mock()
        self.assertTrue(StereoWaveHeightApplication._check_common_fov_timeout(app,110.1))
        app._fail_common_fov.assert_called_once_with("TIMEOUT_AFTER_10_SECONDS")

    def test_legacy_demo_calibration_without_size_uses_accepted_video_pair_size(self):
        from application.main_window import StereoWaveHeightApplication
        app=self._gui_calibration_harness();app.input_state.mark_calibration_ready(operating_mode="DEMO_ESTIMATION_MODE",quality_status="QA_FAIL")
        app.calibration_data={"backend":"OPENCV_OFFICIAL"};app.metadata={"left_measurement":SimpleNamespace(width=1920,height=1080),"right_measurement":SimpleNamespace(width=1920,height=1080)}
        app.variables["common_fov_status"]=mock.Mock();app._refresh_reference_controls=mock.Mock()
        with mock.patch("application.main_window.threading.Thread") as thread:
            StereoWaveHeightApplication._refresh_common_fov(app)
        self.assertEqual(app.common_fov_state,"COMPUTING_COMMON_FOV")
        self.assertEqual(thread.call_count,1)

    def test_validated_calibration_without_size_still_fails_closed(self):
        from application.main_window import StereoWaveHeightApplication
        app=self._gui_calibration_harness();app.input_state.mark_calibration_ready(operating_mode="VALIDATED_MODE",quality_status="QA_PASS")
        app.calibration_data={"backend":"OPENCV_OFFICIAL"};app.metadata={"left_measurement":SimpleNamespace(width=1920,height=1080),"right_measurement":SimpleNamespace(width=1920,height=1080)}
        app.variables["common_fov_status"]=mock.Mock();app._refresh_reference_controls=mock.Mock();app._fail_common_fov=mock.Mock()
        StereoWaveHeightApplication._refresh_common_fov(app)
        app._fail_common_fov.assert_called_once_with("COMMON_FOV_CALIBRATION_SIZE_UNKNOWN")

    def test_validated_calibration_completion_keeps_validated_mode(self):
        from application.main_window import StereoWaveHeightApplication
        repository=Path(__file__).resolve().parents[1]
        source=repository/"experiments/real_video/HomeTank_004/calibration_result.yaml"
        data=yaml.safe_load(source.read_text(encoding="utf-8"));data["status"]="PASS"
        data["stereo"]["rms_px"]=0.1;data["stereo"]["symmetric_epipolar_rms_px"]=0.1
        app=self._gui_calibration_harness()
        StereoWaveHeightApplication._apply_calibration(app,data,source)
        self.assertTrue(app.input_state.calibration_step_completed)
        self.assertEqual(app.input_state.operating_mode,"VALIDATED_MODE")
        self.assertEqual(app.input_state.calibration_quality_status,"QA_PASS")

    def test_video_calibration_continue_completes_workflow_in_one_confirmation(self):
        from application.main_window import StereoWaveHeightApplication
        repository=Path(__file__).resolve().parents[1]
        source=repository/"experiments/real_video/HomeTank_005/calibrations/HomeTank_005_demo_only_v1/opencv_calibration.yaml"
        with tempfile.TemporaryDirectory() as temporary:
            result=Path(temporary)/"calibration.yaml";result.write_bytes(source.read_bytes())
            original=yaml.safe_load(source.read_text(encoding="utf-8"))
            app=self._gui_calibration_harness()
            app._worker_messages.put(("calibration_success",SimpleNamespace(result_path=result,paired_views=68)))
            with mock.patch("application.main_window.messagebox.askyesno",return_value=True):
                StereoWaveHeightApplication._poll_worker(app)
            self.assertTrue(app.input_state.calibration_step_completed)
            self.assertTrue(app.input_state.calibration_ready)
            self.assertEqual(app.input_state.operating_mode,"DEMO_ESTIMATION_MODE")
            app.variables["calibration_load_status"].set.assert_called_with("✓ 双目标定完成（68 组有效视图），可以进入步骤 2")
            saved=yaml.safe_load(result.read_text(encoding="utf-8"))
            self.assertEqual(saved["status"],"CALIBRATION_OPERATIONAL_DOMAIN_FAIL")
            self.assertEqual(saved.get("approved_for_wass"),original.get("approved_for_wass"))
            self.assertEqual(saved["gui_operating_mode"],"DEMO_ESTIMATION_MODE")

    def test_video_calibration_artifact_preserves_image_size_for_common_fov(self):
        from PIL import Image
        from application.calibration_workflow import calibrate_from_videos
        detection=SimpleNamespace(corners_px=np.zeros((54,1,2),dtype=np.float32))
        mono=SimpleNamespace(rms_px=1.0,camera_matrix=np.eye(3),distortion=np.zeros(5))
        result=SimpleNamespace(mono_left=mono,mono_right=mono,stereo_rms_px=1.0,
            rotation_right_from_left=np.eye(3),translation_right_from_left_m=np.asarray([.1,0,0]),baseline_m=.1,
            epipolar_rms_px=1.0,epipolar_max_px=2.0,
            rectification=SimpleNamespace(vertical_disparity_rms_px=1.0,vertical_disparity_max_px=2.0))
        meta=SimpleNamespace(width=1920,height=1080,duration_sec=2.0)
        with tempfile.TemporaryDirectory() as temporary, \
             mock.patch("application.calibration_workflow.probe_video",return_value=meta), \
             mock.patch("application.calibration_workflow.extract_frame",return_value=Image.new("L",(1920,1080))), \
             mock.patch("application.calibration_workflow.detect_checkerboard_official",return_value=detection), \
             mock.patch("application.calibration_workflow.calibrate_stereo_official",return_value=result):
            destination=Path(temporary)/"calibration.yaml"
            calibrate_from_videos(Path("left.mp4"),Path("right.mp4"),Path("ffmpeg.exe"),destination,
                                  corners_x=9,corners_y=6,square_size_mm=20,sample_count=4)
            self.assertEqual(yaml.safe_load(destination.read_text(encoding="utf-8"))["image_size_wh"],[1920,1080])

    def test_demo_height_basis_rejects_incompatible_cross_frame_plane(self):
        from reconstruction.single_frame import demo_height_basis
        reference={"normal":[0,0,1],"offset_m":-2.0};current={"normal":[1,0,0],"offset_m":-1.0}
        basis,status,angle=demo_height_basis(reference,current,demo_enabled=True)
        self.assertIs(basis,current);self.assertGreater(angle,30)
        self.assertEqual(status,"DEMO_CURRENT_FRAME_SURFACE_SHAPE__REFERENCE_FRAME_INCOMPATIBLE")
        production,status,_=demo_height_basis(reference,current,demo_enabled=False)
        self.assertIs(production,reference);self.assertEqual(status,"SELECTED_REFERENCE_PLANE")

    def test_result_view_uses_active_common_fov_mapping_not_legacy_experiment_file(self):
        source=Path("C:/session/common_fov/canonical_cam1_wass_mapping.yaml")
        text=Path("src/application/main_window.py").read_text(encoding="utf-8")
        self.assertIn("DenseMeasurementView(record.dense_npz_path,record.pixel_xyz_path,self.mapping_file)",text)
        self.assertNotIn('self.experiment/"manual_reference/frozen_cam1_validation_mapping.yaml"',text)

    def test_guided_file_dialog_filters_match_supported_inputs(self):
        self.assertEqual(CALIBRATION_FILE_TYPES,(("YAML 双目标定文件","*.yaml *.yml"),))
        self.assertEqual(VIDEO_FILE_TYPES,(("本地视频","*.mp4 *.mov *.avi *.mkv *.m4v"),))

    def test_selected_calibration_overrides_only_request_calibration_source(self):
        repository=Path(__file__).resolve().parents[1]
        runner=FrozenBackendRunner(repository,repository/"experiments/real_video/HomeTank_004/single_frame_dense_smoke_config.yaml")
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary)
            chosen=repository/"experiments/real_video/HomeTank_004/calibration_result.yaml"
            config=runner.prepare_config(repository/"left.mp4",repository/"right.mp4",1.0,base/"result",chosen)
            import yaml
            data=yaml.safe_load(config.read_text(encoding="utf-8"))
            self.assertEqual(Path(data["calibration"]["source"]),chosen.resolve())
            generated=Path(data["processing"]["wass_config_dir"])
            self.assertEqual(generated,base/"result_wass_config")
            self.assertTrue((generated/"intrinsics_00.xml").is_file())
            from reconstruction.io import load_calibration, verify_wass_calibration
            verify_wass_calibration(generated,load_calibration(chosen,quality_mode="diagnostic_allow_failed_gate"))

    def test_multiple_measurement_configs_do_not_overwrite_generated_calibration(self):
        repository=Path(__file__).resolve().parents[1]
        runner=FrozenBackendRunner(repository,repository/"experiments/real_video/HomeTank_004/single_frame_dense_smoke_config.yaml")
        calibration=repository/"experiments/real_video/HomeTank_004/calibration_result.yaml"
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary)
            first=runner.prepare_config(repository/"left.mp4",repository/"right.mp4",1.0,base/"attempt_+0",calibration)
            second=runner.prepare_config(repository/"left.mp4",repository/"right.mp4",1.1,base/"attempt_-1",calibration)
            import yaml
            first_dir=Path(yaml.safe_load(first.read_text(encoding="utf-8"))["processing"]["wass_config_dir"])
            second_dir=Path(yaml.safe_load(second.read_text(encoding="utf-8"))["processing"]["wass_config_dir"])
            self.assertNotEqual(first_dir,second_dir)
            self.assertTrue(first_dir.is_dir() and second_dir.is_dir())

    def test_bounded_fallback_order_and_first_success(self):
        attempted=[]
        def attempt(time_sec,offset):
            attempted.append((time_sec,offset))
            if offset!=1: raise RuntimeError("fixture failure")
            return "ok"
        result=run_bounded_fallback(10.0,0.02,attempt)
        self.assertEqual(FALLBACK_FRAME_OFFSETS,(0,-1,1,-2,2))
        self.assertEqual([item[1] for item in attempted],[0,-1,1])
        self.assertEqual(result.actual_time_sec,10.02)

    def test_target_success_does_not_retry_and_pair_model_is_preserved(self):
        pairs=[]
        result=run_bounded_fallback(5.0,1/60,lambda left,offset:pairs.append((left,left-0.0654055)) or "ok")
        self.assertEqual(result.frame_offset,0); self.assertEqual(len(pairs),1)
        self.assertAlmostEqual(pairs[0][1],pairs[0][0]-0.0654055)

    def test_latest_frame_decoder_has_bounded_storage(self):
        decoder=LatestFrameDecoder()
        self.assertEqual(decoder.pending_frame_count,0)
        decoder._latest=(1,0.0,None)  # type: ignore[assignment]
        decoder._latest=(2,0.1,None)  # type: ignore[assignment]
        self.assertEqual(decoder.pending_frame_count,1)

    def test_windows_hidden_process_policy_is_explicit(self):
        import os
        options=hidden_process_kwargs()
        if os.name=="nt": self.assertIn("creationflags",options); self.assertIn("startupinfo",options)

    def test_core_reconstruction_survives_dense_artifact_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary); (output/"selected_pair").mkdir(); (output/"reconstruction/pointcloud").mkdir(parents=True)
            (output/"selected_pair/right.png").write_bytes(b"png"); (output/"reconstruction/pointcloud/000000.xyz").write_text("0 0 0\n")
            payload={"status":"SINGLE_FRAME_RECONSTRUCTION_COMPLETED_DENSE_HEIGHT_FAILED","requested_time_s":1.0,"dense_height":{"status":"FAILED"}}
            (output/"single_frame_result.json").write_text(json.dumps(payload),encoding="utf-8")
            record=parse_backend_result(output)
            self.assertEqual(record.summary_metadata["status"],"SINGLE_FRAME_RECONSTRUCTION_COMPLETED_DENSE_HEIGHT_FAILED")

    def test_fallback_metadata_records_requested_and_actual_time(self):
        repository=Path(__file__).resolve().parents[1]
        runner=FrozenBackendRunner(repository,repository/"experiments/real_video/HomeTank_004/single_frame_dense_smoke_config.yaml")
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); calls=[]
            def fake_run(_left,_right,time_sec,output,_log,_calibration,_water_roi):
                calls.append(time_sec)
                if len(calls)==1: raise BackendResultError("target failed",retry_neighbor=True)
                output.mkdir(parents=True); unified=output/"single_frame_result.json"; unified.write_text(json.dumps({"status":"SINGLE_FRAME_DENSE_HEIGHT_COMPLETED","requested_time_s":time_sec}),encoding="utf-8")
                return MeasurementRecord(time_sec,"fixture",output,unified,output/"right.png",output/"h.png",output/"s.png",None,"now",{"status":"SINGLE_FRAME_DENSE_HEIGHT_COMPLETED","requested_time_s":time_sec})
            with mock.patch.object(runner,"run",side_effect=fake_run):
                record=runner.run_with_fallback(Path("l"),Path("r"),2.0,root/"out",root/"log",root/"cal.yaml",frame_period_sec=0.02)
            self.assertTrue(record.summary_metadata["fallback_used"])
            self.assertEqual(record.summary_metadata["fallback_frame_offset"],-1)
            self.assertAlmostEqual(record.summary_metadata["actual_measurement_time_sec"],1.98)
            self.assertAlmostEqual(record.summary_metadata["fallback_time_offset_ms"],-20.0)

    def test_engineering_failure_does_not_trigger_neighbor_fallback(self):
        attempted=[]
        def attempt(_time,offset):
            attempted.append(offset)
            raise BackendResultError("missing calibration",stage="固定标定准备",retry_neighbor=False)
        with self.assertRaisesRegex(BackendResultError,"missing calibration"):
            run_bounded_fallback(2.0,0.02,attempt,should_retry=lambda error:isinstance(error,BackendResultError) and error.retry_neighbor)
        self.assertEqual(attempted,[0])

    def test_frame_local_failure_still_uses_bounded_neighbor_fallback(self):
        attempted=[]
        def attempt(_time,offset):
            attempted.append(offset)
            if offset==1:return "ok"
            raise BackendResultError("insufficient matching support",stage="双目匹配",retry_neighbor=True)
        result=run_bounded_fallback(2.0,0.02,attempt,should_retry=lambda error:isinstance(error,BackendResultError) and error.retry_neighbor)
        self.assertEqual(attempted,[0,-1,1]); self.assertEqual(result.frame_offset,1)

    def test_backend_structured_root_error_survives_exit_code_wrapper(self):
        repository=Path(__file__).resolve().parents[1]
        runner=FrozenBackendRunner(repository,repository/"experiments/real_video/HomeTank_004/single_frame_dense_smoke_config.yaml")
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary); output=base/"out"; output.mkdir()
            payload={"status":"WASS_RECONSTRUCTION_FAILED","warnings":["Fixed-calibration reconstruction terminated: ValueError: missing intrinsics_00.xml"]}
            (output/"single_frame_result.json").write_text(json.dumps(payload),encoding="utf-8")
            completed=subprocess.CompletedProcess(["backend"],1,stdout=b"WASS_RECONSTRUCTION_FAILED\n",stderr=b"")
            with mock.patch.object(runner,"prepare_config",return_value=base/"request.yaml"), mock.patch("application.backend_runner.subprocess.run",return_value=completed):
                with self.assertRaises(BackendResultError) as raised:
                    runner.run(Path("left"),Path("right"),1.0,output,base/"session.log",None)
            self.assertIn("固定标定准备",str(raised.exception)); self.assertIn("intrinsics_00.xml",str(raised.exception))
            self.assertNotIn("退出码 1",str(raised.exception))

    def test_backend_subprocess_preserves_cwd_environment_and_runtime_config(self):
        repository=Path(__file__).resolve().parents[1]
        runner=FrozenBackendRunner(repository,repository/"experiments/real_video/HomeTank_004/single_frame_dense_smoke_config.yaml")
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary); output=base/"out"; config=base/"request.yaml"; config.write_text("fixture: true\n")
            record=self._record(output,"fixture")
            completed=subprocess.CompletedProcess(["backend"],0,stdout=b"ok\xff\n",stderr=b"")
            with mock.patch.object(runner,"prepare_config",return_value=config), mock.patch("application.backend_runner.subprocess.run",return_value=completed) as launched, mock.patch("application.backend_runner.parse_backend_result",return_value=record):
                runner.run(Path("left"),Path("right"),1.0,output,base/"session.log",None)
            kwargs=launched.call_args.kwargs
            self.assertEqual(kwargs["cwd"],repository)
            self.assertIn(str(repository/"src"),kwargs["env"]["PYTHONPATH"])
            self.assertFalse(kwargs["text"])
            self.assertIn("ok�",(base/"session.log").read_text(encoding="utf-8"))

    def test_result_summary_uses_demo_friendly_height_units(self):
        from application.main_window import StereoWaveHeightApplication
        record=self._record(Path("result"),"1.000s")
        record=MeasurementRecord(**{**record.__dict__,"summary_metadata":{"height_statistics":{"minimum":-0.025,"maximum":-0.014,"mean":-0.020},"dense_height":{}}})
        summary=StereoWaveHeightApplication._summary(record)
        self.assertIn("-25.000 / -14.000 / -20.000 mm",summary)

    def test_selected_water_roi_replaces_template_demo_polygon(self):
        repository=Path(__file__).resolve().parents[1]
        runner=FrozenBackendRunner(repository,repository/"experiments/real_video/HomeTank_004/single_frame_dense_smoke_config.yaml")
        selected={"type":"polygon","coordinate_system":"canonical_cam1","points":[[10,20],[300,20],[300,400],[10,400]]}
        with tempfile.TemporaryDirectory() as temporary:
            config=runner.prepare_config(repository/"left.mp4",repository/"right.mp4",1.0,Path(temporary)/"out",water_roi=selected)
            import yaml
            data=yaml.safe_load(config.read_text(encoding="utf-8"))
            self.assertEqual(data["dense_height"]["water_roi"],selected)
            self.assertNotEqual(data["dense_height"]["water_roi"]["points"],[[700,340],[900,340],[900,520],[700,520]])

    def test_paused_and_playing_slider_release_submit_one_latest_seek(self):
        from application.main_window import StereoWaveHeightApplication
        class Timeline:
            def get(self):return 60.0
            def cget(self,_key):return 161.171
        for resume in (False,True):
            app=StereoWaveHeightApplication.__new__(StereoWaveHeightApplication)
            app.timeline=Timeline(); app.preview_decoder=mock.Mock(); app._resume_after_seek=resume
            app._timeline_dragging=True; app.current_time=0.0; app.playing=False
            app.variables={key:mock.Mock() for key in ("right_measurement","time","app_state")}
            app.variables["right_measurement"].get.return_value="right.mp4"; app._log=mock.Mock()
            app._timeline_release(mock.Mock())
            app.preview_decoder.seek.assert_called_once_with(Path("right.mp4"),60.0,continue_playing=resume)
            self.assertEqual(app.current_time,60.0); self.assertEqual(app.playing,resume)

    def test_decoder_seek_generation_makes_older_request_stale(self):
        decoder=LatestFrameDecoder()
        with mock.patch("application.video_tools.threading.Thread") as thread:
            first=decoder.seek(Path("video.mp4"),20.0,continue_playing=False)
            second=decoder.seek(Path("video.mp4"),60.0,continue_playing=False)
        self.assertGreater(second,first); self.assertEqual(thread.call_count,2)

    def test_delete_session_only_removes_current_session(self):
        from application.export import delete_session
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); current=MeasurementSession(root,"current"); other=MeasurementSession(root,"other")
            delete_session(current)
            self.assertFalse(current.directory.exists()); self.assertTrue(other.directory.exists())

    def test_cleanup_failure_does_not_block_application_exit(self):
        from application.main_window import StereoWaveHeightApplication
        app=StereoWaveHeightApplication.__new__(StereoWaveHeightApplication)
        app._closing=False; app.playing=True; app.preview_decoder=mock.Mock(); app._after_id=None
        app.root=mock.Mock(); app.session=mock.Mock(); app.session.directory=Path("C:/locked/session")
        with mock.patch("application.main_window.delete_session",side_effect=PermissionError("locked")), mock.patch("application.main_window.messagebox.showwarning"):
            app._shutdown(delete_temporary=True)
        app.preview_decoder.stop.assert_called_once(); app.root.destroy.assert_called_once()

    def test_canvas_mapping_accounts_for_letterbox(self):
        transform=DisplayTransform.fit(1920,1080,1000,700)
        self.assertIsNone(transform.canvas_to_pixel(500,20))
        self.assertEqual(transform.canvas_to_pixel(500,350),(960,540))
        canvas=transform.pixel_to_canvas(960,540)
        self.assertEqual(transform.canvas_to_pixel(*canvas),(960,540))

    def test_export_all_and_selective_smoke(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary); session=MeasurementSession(base/"sessions","export")
            records=[]
            for index in range(2):
                source=base/f"source{index}"; source.mkdir(); (source/"result.json").write_text("{}")
                record=MeasurementRecord(float(index),f"{index}.000s",source,source/"result.json",source/"missing.png",source/"h.png",source/"s.png",None,"now",{"status":"OK"})
                session.add(record); records.append(record)
            all_path=export_session(session,base/"all",records)
            selected_path=export_session(session,base/"selected",[records[1]])
            self.assertEqual(json.loads((all_path/"session_manifest.json").read_text())["measurement_count"],2)
            self.assertEqual(json.loads((selected_path/"session_manifest.json").read_text())["measurement_count"],1)

    def test_selective_export_copies_only_selected_record(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary); session=MeasurementSession(base/"sessions","s")
            records=[]
            for index,name in enumerate(("1.000s","2.000s")):
                source=base/f"source{index}"; source.mkdir();
                for filename in ("right.png","height.png","status.png","single_frame_result.json"):(source/filename).write_text(filename,encoding="utf-8")
                record=MeasurementRecord(float(index+1),name,source,source/"single_frame_result.json",source/"right.png",source/"height.png",source/"status.png",None,"now",{"status":"OK"})
                session.add(record); records.append(record)
            exported=export_session(session,base/"exports",[records[1]])
            self.assertFalse((exported/"measurement_1.000s").exists())
            self.assertTrue((exported/"measurement_2.000s/selected_frame.png").is_file())
            self.assertTrue(session.directory.exists())

    def test_unsupported_hover_returns_na_not_zero(self):
        view=DenseMeasurementView.__new__(DenseMeasurementView)
        view.height=np.asarray([[np.nan]],dtype=np.float32); view.status=np.asarray([[0]],dtype=np.uint8); view.roi=np.asarray([[True]])
        query=view.query(0,0)
        self.assertEqual(query.status,"UNSUPPORTED"); self.assertIsNone(query.height_mm); self.assertIsNone(query.xyz_m)

    def test_global_model_hover_reports_low_confidence(self):
        view=DenseMeasurementView.__new__(DenseMeasurementView)
        view.height=np.asarray([[1.5]],dtype=np.float32);view.status=np.asarray([[3]],dtype=np.uint8)
        view.roi=np.asarray([[True]]);view.confidence=np.asarray([[1]],dtype=np.uint8)
        query=view.query(0,0)
        self.assertEqual(query.source,"ESTIMATED_GLOBAL_MODEL");self.assertEqual(query.confidence,"LOW")

    def test_failed_export_preserves_temporary_session(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary); session=MeasurementSession(base/"sessions","s")
            destination=base/"exports"; (destination/"session_s").mkdir(parents=True)
            with self.assertRaises(FileExistsError): export_session(session,destination,[])
            self.assertTrue(session.directory.is_dir())

    def test_overlay_changes_only_valid_pixels(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary); original=base/"original.png"; dense=base/"dense.npz"
            Image.new("RGB",(2,1),(100,100,100)).save(original)
            np.savez(dense,height_mm=np.asarray([[1.0,np.nan]],dtype=np.float32),status=np.asarray([[1,0]],dtype=np.uint8),valid_mask=np.asarray([[True,False]]),water_roi_mask=np.asarray([[True,True]]))
            pixels=np.asarray(make_height_overlay(original,dense,0.45))
            self.assertFalse(np.array_equal(pixels[0,0],[100,100,100]))
            np.testing.assert_array_equal(pixels[0,1],[100,100,100])


if __name__ == "__main__": unittest.main()
