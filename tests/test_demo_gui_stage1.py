from pathlib import Path
import json
import tempfile
import unittest

from application.backend_runner import BackendResultError, parse_backend_result
from application.backend_runner import FrozenBackendRunner
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
            with self.assertRaisesRegex(BackendResultError,"未完成"): parse_backend_result(output)

    def test_external_request_config_makes_template_resources_absolute(self):
        repository=Path(__file__).resolve().parents[1]
        runner=FrozenBackendRunner(repository,repository/"experiments/real_video/HomeTank_004/single_frame_dense_smoke_config.yaml")
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)/"measurement"
            config=runner.prepare_config(repository/"left.mp4",repository/"right.mp4",1.25,output)
            import yaml
            data=yaml.safe_load(config.read_text(encoding="utf-8"))
            self.assertTrue(Path(data["calibration"]["source"]).is_absolute())
            self.assertTrue(Path(data["processing"]["reference_plane_file"]).is_absolute())
            self.assertTrue(Path(data["dense_height"]["mapping_file"]).is_absolute())

    def test_application_imports_without_opening_window(self):
        from application import StereoWaveHeightApplication
        self.assertTrue(callable(StereoWaveHeightApplication))

    def test_canvas_mapping_accounts_for_letterbox(self):
        transform=DisplayTransform.fit(1920,1080,1000,700)
        self.assertIsNone(transform.canvas_to_pixel(500,20))
        self.assertEqual(transform.canvas_to_pixel(500,350),(960,540))

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
