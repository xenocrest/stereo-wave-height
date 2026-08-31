from pathlib import Path
import json
import subprocess
import tempfile
import unittest
from unittest import mock

from application.backend_runner import BackendResultError, parse_backend_result
from application.backend_runner import FrozenBackendRunner, backend_command
from application.runtime_paths import resolve_runtime_paths
from application.input_workflow import CALIBRATION_FILE_TYPES, VIDEO_FILE_TYPES, GuidedInputState
from application.fallback import FALLBACK_FRAME_OFFSETS, run_bounded_fallback
from application.video_tools import LatestFrameDecoder
from process_utils import hidden_process_kwargs
from application.session import MeasurementRecord, MeasurementSession
from application.export import export_session
from application.visualization import DisplayTransform, DenseMeasurementView, make_height_overlay
import numpy as np


class DemoGuiStage1Tests(unittest.TestCase):
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

    def test_application_imports_without_opening_window(self):
        from application import StereoWaveHeightApplication
        self.assertTrue(callable(StereoWaveHeightApplication))

    def test_development_and_packaged_resource_resolution(self):
        repository=Path(__file__).resolve().parents[1]
        development=resolve_runtime_paths(repository,frozen=False)
        packaged=resolve_runtime_paths(executable=Path("C:/portable/StereoWaveHeightDemo/StereoWaveHeightDemo.exe"),frozen=True)
        self.assertEqual(development.experiment,repository/"experiments/real_video/HomeTank_004")
        self.assertEqual(packaged.experiment,Path("C:/portable/StereoWaveHeightDemo/resources/HomeTank_004"))
        self.assertEqual(packaged.ffmpeg,Path("C:/portable/StereoWaveHeightDemo/runtime/ffmpeg/ffmpeg.exe"))

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
        state.set_mode("existing"); self.assertFalse(state.calibration_ready)

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
