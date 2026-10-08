"""Process-lifetime regressions plus P0/result routing guards."""
import ctypes
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton
from PySide6.QtTest import QTest

from app import core
from minimal_app.runner import ProcessRunner
from minimal_app.main import MainWindow
from minimal_app.worker import official_reference


APP = QApplication.instance() or QApplication([])


def until(predicate, timeout=8):
    end = time.monotonic() + timeout
    while not predicate() and time.monotonic() < end:
        APP.processEvents()
        QTest.qWait(10)
    assert predicate(), "Qt condition timed out"


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.runner = ProcessRunner()
        self.output = []
        self.runner.output.connect(self.output.append)

    def tearDown(self):
        if self.runner.current_process:
            self.runner.terminate()
            until(lambda: self.runner.current_process is None)

    def start(self, script):
        self.runner.start("视频同步", [sys.executable, "-u", "-c", script], core.ROOT)

    def test_streams_both_channels_before_finish_and_allows_restart(self):
        self.start("import sys,time; print('LIVE_OUT',flush=True); print('LIVE_ERR',file=sys.stderr,flush=True); time.sleep(1)")
        until(lambda: "[stderr] LIVE_ERR" in "".join(self.output) and "[stdout] LIVE_OUT" in "".join(self.output))
        self.assertIsNotNone(self.runner.current_process)
        self.assertEqual(self.runner.current_task_name, "视频同步")
        self.assertIn("[stdout] LIVE_OUT", "".join(self.output))
        until(lambda: self.runner.current_process is None)
        self.assertEqual(self.runner.status, "PROCESS_COMPLETE")
        self.start("print('NEXT')")
        until(lambda: self.runner.current_process is None)
        self.assertEqual(self.runner.status, "PROCESS_COMPLETE")

    def test_failed_start_and_nonzero_clear_process(self):
        with self.assertRaises(ValueError):
            self.runner.start("invalid", [], core.ROOT)
        self.assertIsNone(self.runner.current_process)
        self.runner.start("missing", [str(core.ROOT / "does_not_exist.exe")], core.ROOT)
        until(lambda: self.runner.current_process is None)
        self.assertEqual(self.runner.status, "PROCESS_FAILED")
        self.start("raise RuntimeError('EXPECTED_FAILURE')")
        until(lambda: self.runner.current_process is None)
        self.assertEqual(self.runner.status, "PROCESS_FAILED")
        self.start("print('RECOVERED')")
        until(lambda: self.runner.current_process is None)
        self.assertEqual(self.runner.status, "PROCESS_COMPLETE")

    def test_crash_and_immediate_cancel_clear_process(self):
        self.start("import time; time.sleep(30)")
        until(lambda: self.runner.current_process.processId() != 0)
        self.runner.current_process.kill()
        until(lambda: self.runner.current_process is None)
        self.assertEqual(self.runner.status, "PROCESS_FAILED")
        self.start("import time; time.sleep(30)")
        self.runner.terminate()
        until(lambda: self.runner.current_process is None)
        self.assertEqual(self.runner.status, "USER_TERMINATED")

    @unittest.skipUnless(os.name == "nt", "Windows process-tree contract")
    def test_cancel_kills_child_and_grandchild(self):
        with tempfile.TemporaryDirectory() as directory:
            pid_file = Path(directory) / "pids.json"
            grandchild = "import time; time.sleep(60)"
            child = ("import os,subprocess,time,json; from pathlib import Path; "
                f"p=subprocess.Popen([{sys.executable!r},'-c',{grandchild!r}]); "
                f"f=Path({str(pid_file)!r}); f.with_suffix('.tmp').write_text(json.dumps([os.getpid(),p.pid])); "
                "f.with_suffix('.tmp').replace(f); time.sleep(60)")
            self.start(f"import subprocess,time; subprocess.Popen([{sys.executable!r},'-c',{child!r}]); time.sleep(60)")
            until(pid_file.is_file)
            pids = json.loads(pid_file.read_text())
            self.runner.terminate()
            until(lambda: self.runner.current_process is None)
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.OpenProcess.restype = ctypes.c_void_p
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
            for pid in pids:
                handle = kernel.OpenProcess(0x00100000, False, pid)
                if handle:
                    self.assertEqual(kernel.WaitForSingleObject(handle, 3000), 0)
                    kernel.CloseHandle(handle)
            self.assertEqual(self.runner.status, "USER_TERMINATED")


class WindowTests(unittest.TestCase):
    def setUp(self):
        self.window = MainWindow()

    def tearDown(self):
        if self.window.runner.current_process:
            self.window.runner.terminate()
            until(lambda: self.window.runner.current_process is None)
        self.window.close()

    def test_idle_close_and_defaults_have_no_hometank_fallback(self):
        self.window.show()
        self.assertIsNone(self.window.reference)
        self.assertFalse(self.window.config["wass"]["allow_extrinsic_fallback"])
        self.assertTrue(all(not edit.text() for edit in self.window.paths.values()))
        self.window.close()
        self.assertFalse(self.window.isVisible())

    def test_cancel_close_then_terminate_exit(self):
        self.window.show()
        self.window.runner.start("视频同步", [sys.executable, "-c", "import time; time.sleep(30)"], core.ROOT)
        until(lambda: self.window.runner.current_process.processId() != 0)
        def click_dialog(text):
            dialog = APP.activeModalWidget()
            self.assertIsInstance(dialog, QMessageBox)
            self.assertIn("视频同步", dialog.text())
            next(button for button in dialog.buttons() if button.text() == text).click()
        QTimer.singleShot(100, lambda: click_dialog("取消"))
        self.window.close()
        self.assertTrue(self.window.isVisible())
        self.assertIsNotNone(self.window.runner.current_process)
        QTimer.singleShot(100, lambda: click_dialog("终止任务并退出"))
        self.window.close()
        until(lambda: self.window.runner.current_process is None and not self.window.isVisible())

    def test_same_paths_keep_explicit_config_new_video_clears_binding(self):
        self.window.load_config(core.ROOT / "examples" / "hometank004.yaml")
        self.window.paths["cal_left"].setText(str(Path(self.window.paths["cal_left"].text()).resolve()))
        self.window.inputs_changed()
        self.assertTrue(self.window.config["wass"]["allow_extrinsic_fallback"])
        self.window.paths["wave_left"].setText("D:/new_input.mp4")
        self.window.inputs_changed()
        self.assertFalse(self.window.config["wass"]["allow_extrinsic_fallback"])
        self.assertNotIn("fallback_calibration", self.window.config["wass"])
        self.assertIsNone(self.window.reference)

    def test_finished_read_exception_does_not_retain_busy(self):
        with tempfile.TemporaryDirectory() as directory:
            self.window._pending = ("sync", Path(directory), self.window.config)
            self.window.runner.start("视频同步", [sys.executable, "-c", "print('done')"], core.ROOT)
            until(lambda: self.window.runner.current_process is None and self.window._pending is None)
            self.assertTrue(self.window.inputs.isEnabled())
            self.assertIn("[失败]", self.window.log.toPlainText())

    def test_time_change_hides_previous_source_identity_and_result(self):
        self.window.viewer.result = {"previous_frame": True}
        self.window.show_time(dict(actual_left_source_pts=20., actual_right_source_pts=19.9, stereo_pair_residual_ms=7.))
        self.window.requested.setValue(21.)
        self.assertIsNone(self.window.viewer.result)
        self.assertIn("Left Actual PTS：N/A", self.window.time_label.text())

    def test_time_edit_does_not_start_worker_before_clicked_task(self):
        self.window.sync_result = {"audio_lag_right_minus_left_s": -.075}
        self.window.requested.setValue(21.)
        with patch.object(self.window, "launch") as launch:
            self.window.seek()
        launch.assert_not_called()
        self.assertIsNone(self.window.runner.current_process)
        self.assertEqual(self.window.slider.value(), 21000)

    def test_reference_uses_official_setup_without_grid_fitting(self):
        run = Path("D:/stereo-wave-height-runs/reconstruction-quality-p0-20261001/final/Vieira")
        if not run.is_dir():
            self.skipTest("P0 official run unavailable")
        with patch("numpy.linalg.lstsq", side_effect=AssertionError("Must not fit")), \
             patch("app.core.reference_from_run", side_effect=AssertionError("Must not fit")):
            reference = official_reference(run)
        self.assertEqual(reference["normal"], [0., 0., 1.])
        self.assertEqual(reference["d"], 0.)
        self.assertEqual(reference["coordinate_system"], "official_wass_grid_B")
        core.reference_from_metadata(reference)


if __name__ == "__main__":
    unittest.main()
