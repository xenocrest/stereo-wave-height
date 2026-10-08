"""Offline GUI: inputs, one QProcess, playback, existing official outputs."""
import argparse
import copy
import json
from pathlib import Path
import sys
import time

import cv2
import numpy as np
from PySide6.QtCore import QSignalBlocker, Qt, QTimer
from PySide6.QtWidgets import (QApplication, QDoubleSpinBox, QFileDialog, QFormLayout,
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPlainTextEdit, QPushButton, QScrollArea, QSlider, QSpinBox, QSplitter,
    QTabWidget, QVBoxLayout, QWidget)
from app import core, coordinates
from app.main import ImageCanvas
from minimal_app.runner import ProcessRunner
from minimal_app.viewer import ResultView
from tools.camera_image import open_canonical_video


class MainWindow(QMainWindow):
    def __init__(self, config_path=None):
        super().__init__()
        self.setWindowTitle("极简离线 WASS 演示")
        self.resize(1180, 800)
        self.config = core.new_project("minimal_offline", "D:/stereo-wave-height-runs/minimal-offline")
        self.active_calibration = self.sync_result = self.reference = self._pending = None
        self._exit_when_done = self._populating = False
        self.playing = False
        self.captures = []
        self.play_timer = QTimer(self)
        self.play_timer.timeout.connect(self.video_tick)
        self.runner = ProcessRunner(self)
        self._build_ui()
        self.runner.output.connect(self.append_log)
        self.runner.changed.connect(self.update_task)
        self.runner.completed.connect(self.task_done)
        self.clock = QTimer(self)
        self.clock.timeout.connect(self.update_task)
        self.clock.start(500)
        self.populate()
        if config_path:
            self.load_config(config_path)
        self.update_task()

    def button(self, text, callback, layout):
        button = QPushButton(text)
        button.setObjectName(text)
        button.clicked.connect(callback)
        layout.addWidget(button)
        return button

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        self.task_label = QLabel("当前任务：空闲")
        self.task_label.setObjectName("current_task")
        root.addWidget(self.task_label)
        splitter = QSplitter()
        root.addWidget(splitter, 1)
        self.inputs = QWidget()
        left = QVBoxLayout(self.inputs)
        config_row = QHBoxLayout()
        self.button("打开配置", self.open_config, config_row)
        self.button("保存配置", self.save_config, config_row)
        left.addLayout(config_row)
        form = QFormLayout()
        left.addLayout(form)
        self.paths = {}
        for key, label in (("cal_left", "左标定视频"), ("cal_right", "右标定视频"),
                           ("wave_left", "左水面视频"), ("wave_right", "右水面视频")):
            row = QHBoxLayout()
            edit = QLineEdit()
            edit.setObjectName(key)
            edit.setAccessibleName(label)
            edit.editingFinished.connect(self.inputs_changed)
            row.addWidget(edit)
            self.button("选择" + label, lambda checked=False, e=edit: self.pick_video(e), row)
            self.paths[key] = edit
            form.addRow(label, row)
        self.output = QLineEdit()
        self.output.setAccessibleName("输出目录")
        output_row = QHBoxLayout()
        output_row.addWidget(self.output)
        self.button("选择输出目录", self.pick_output, output_row)
        form.addRow("输出目录", output_row)
        self.columns, self.rows = QSpinBox(), QSpinBox()
        for spin in (self.columns, self.rows):
            spin.setRange(2, 100)
            spin.valueChanged.connect(self.inputs_changed)
        self.square, self.baseline, self.window_end = QDoubleSpinBox(), QDoubleSpinBox(), QDoubleSpinBox()
        for spin in (self.square, self.baseline):
            spin.setRange(0.000001, 100)
            spin.setDecimals(6)
            spin.valueChanged.connect(self.inputs_changed)
        self.window_end.setRange(0.1, 600)
        self.window_end.valueChanged.connect(self.inputs_changed)
        for label, spin in (("棋盘内角点列", self.columns), ("棋盘内角点行", self.rows),
                            ("棋盘格长 (m)", self.square), ("相机基线 / B 单位配置", self.baseline),
                            ("TLCC 音频窗口结束 (s)", self.window_end)):
            form.addRow(label, spin)
        self.calibration_label, self.sync_label, self.fallback_label = QLabel("标定：未运行"), QLabel("同步：未运行"), QLabel()
        for label in (self.calibration_label, self.sync_label, self.fallback_label):
            label.setWordWrap(True)
            left.addWidget(label)
        for label, callback in (("运行标定", lambda: self.scientific_task("calibrate")),
                                ("运行同步", lambda: self.scientific_task("sync")), ("载入左右视频", self.load_videos)):
            self.button(label, callback, left)
        self.reference_label = QLabel("当前参考面：未设置")
        self.reference_label.setWordWrap(True)
        left.addWidget(self.reference_label)
        for label, callback in (("用当前暂停帧建立参考面", lambda: self.scientific_task("reference")),
            ("选择固定参考面", self.import_reference), ("解算当前暂停帧", lambda: self.scientific_task("reconstruct")),
            ("打开已有结果", self.open_result)):
            self.button(label, callback, left)
        left.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.inputs)
        splitter.addWidget(scroll)
        self.pages = QTabWidget()
        splitter.addWidget(self.pages)
        splitter.setSizes([400, 780])
        video = QWidget()
        layout = QVBoxLayout(video)
        previews = QHBoxLayout()
        layout.addLayout(previews, 1)
        self.pause_images = []
        for side in ("左相机", "右相机"):
            image = ImageCanvas()
            image.setMinimumSize(240, 135)
            previews.addWidget(image)
            self.pause_images.append(image)
        raw = QLabel("RAW_CAMERA_IMAGE · 原视频播放；暂停图使用 P0 canonical 帧；XYZ/H：N/A")
        raw.setWordWrap(True)
        layout.addWidget(raw)
        controls = QHBoxLayout()
        self.play_button = self.button("播放", self.toggle_play, controls)
        self.requested = QDoubleSpinBox()
        self.requested.setRange(0, 99999)
        self.requested.setDecimals(6)
        self.requested.setSuffix(" s")
        self.requested.setAccessibleName("Requested Time")
        self.requested.valueChanged.connect(self.selection_changed)
        self.requested.editingFinished.connect(self.seek)
        controls.addWidget(self.requested)
        self.pause_button = self.button("读取当前暂停帧", self.pause_preview, controls)
        layout.addLayout(controls)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 60000)
        self.slider.sliderMoved.connect(self.slider_moved)
        self.slider.sliderReleased.connect(self.pause_preview)
        layout.addWidget(self.slider)
        self.time_label = QLabel()
        self.time_label.setWordWrap(True)
        layout.addWidget(self.time_label)
        self.pages.addTab(video, "视频 / 暂停")
        self.viewer = ResultView()
        self.pages.addTab(self.viewer, "结果")
        root.addWidget(QLabel("实时 stdout / stderr（完整记录保存在本次输出目录）"))
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(4000)
        self.log.setMaximumHeight(150)
        self.log.setObjectName("live_log")
        root.addWidget(self.log)
        self.stop_button = self.button("终止当前任务", self.runner.terminate, root)

    def append_log(self, text):
        self.log.moveCursor(self.log.textCursor().MoveOperation.End)
        self.log.insertPlainText(text)
        if self._pending:
            with (self._pending[1] / "console.log").open("a", encoding="utf-8") as stream:
                stream.write(text)
        self.log.ensureCursorVisible()

    def populate(self):
        self._populating = True
        try:
            for key, block, name in self.input_keys():
                self.paths[key].setText(self.config[block].get(name, ""))
            board = self.config["calibration"].get("checkerboard", {})
            self.columns.setValue(board.get("columns", 9))
            self.rows.setValue(board.get("rows", 6))
            self.square.setValue(board.get("square_size_m", .02))
            self.baseline.setValue(self.config["surface"]["baseline_m"])
            self.output.setText(self.config["output_root"])
            self.window_end.setValue(self.config["sync"].get("window_end_s", 30))
            self.requested.setValue(self.config["sync"].get("start_s", 0))
            self.slider.setValue(round(self.requested.value() * 1000))
            self.fallback_label.setText("EXTRINSICS_FALLBACK：配置已明确允许" if self.config.get("wass", {}).get("allow_extrinsic_fallback") else "EXTRINSICS_FALLBACK：未允许")
            self.invalidate_time()
        finally:
            self._populating = False

    @staticmethod
    def input_keys():
        return (("cal_left", "calibration", "left_video"), ("cal_right", "calibration", "right_video"),
                ("wave_left", "sync", "left_video"), ("wave_right", "sync", "right_video"))

    def gather(self):
        config = copy.deepcopy(self.config)
        for key, block, name in self.input_keys():
            if config["source_type"] == "stereo_video":
                config[block][name] = self.paths[key].text().strip()
        config["output_root"] = self.output.text().strip()
        config["calibration"]["checkerboard"] = dict(columns=self.columns.value(), rows=self.rows.value(), square_size_m=self.square.value())
        config["surface"]["baseline_m"] = self.baseline.value()
        config["sync"]["window_end_s"] = self.window_end.value()
        if self.active_calibration:
            config["calibration"].update(status="provided", config_path=str(self.active_calibration))
        if self.reference:
            config.setdefault("presentation", {})["frozen_reference"] = self.reference
        return config

    def inputs_changed(self):
        if self._populating:
            return
        previous = copy.deepcopy(self.config)
        if self.active_calibration:
            previous["calibration"].update(status="provided", config_path=str(self.active_calibration))
        # Ignore representation-only path spelling changes from the file chooser.
        for key, block, name in self.input_keys():
            old, new = previous[block].get(name), self.paths[key].text().strip()
            if old and new and Path(old).resolve() == Path(new).resolve():
                previous[block][name] = new
        if core.project_input_identity(self.gather()) == core.project_input_identity(previous):
            return
        self.active_calibration = self.sync_result = self.reference = None
        self.config.pop("presentation", None)
        self.config["calibration"].update(status="compute")
        self.config["calibration"].pop("config_path", None)
        self.config["wass"] = {"allow_extrinsic_fallback": False}
        self.config = self.gather()
        self.release_videos()
        self.show_reference()
        self.calibration_label.setText("标定：输入已变更，请重新运行")
        self.sync_label.setText("同步：输入已变更，请重新运行")
        self.fallback_label.setText("EXTRINSICS_FALLBACK：未允许（输入变更）")
        self.viewer.clear()
        self.invalidate_time()

    def pick_video(self, edit):
        path, _ = QFileDialog.getOpenFileName(self, "选择视频", edit.text(), "视频 (*.mp4 *.mov *.avi *.mkv *.mts);;所有文件 (*)")
        if path:
            edit.setText(str(Path(path).resolve()))
            self.inputs_changed()

    def pick_output(self):
        path = QFileDialog.getExistingDirectory(self, "选择输出目录", self.output.text())
        if path:
            self.output.setText(path)

    def open_config(self):
        path, _ = QFileDialog.getOpenFileName(self, "打开配置", str(core.ROOT / "examples"), "项目配置 (*.yaml *.yml)")
        if path:
            self.load_config(path)

    def load_config(self, path):
        try:
            value = core.read_project(path)
            reference = value.get("presentation", {}).get("frozen_reference")
            if reference:
                core.reference_from_metadata(reference)
            self.config, self.reference = value, reference
            self.release_videos()
            self.active_calibration = self.sync_result = None
            self.populate()
            self.viewer.clear()
            self.show_reference()
            self.append_log(f"[配置] {path}\n")
        except Exception as error:
            self.show_error(error)

    def save_config(self):
        path, _ = QFileDialog.getSaveFileName(self, "保存配置", str(Path(self.output.text()) / "minimal_project.yaml"), "项目配置 (*.yaml)")
        if path:
            try:
                core.save_project(self.gather(), path)
            except Exception as error:
                self.show_error(error)

    def launch(self, action, config, name):
        if self.runner.current_process is not None:
            self.show_error(f"当前任务：{self.runner.current_task_name}")
            return
        self.stop_playback()
        try:
            snapshot, target = core.stage_paths(config, action)
            self._pending = (action, target, config)
            self.runner.start(name, [config["tools"]["python"], "-u", "-m", "minimal_app.worker", action,
                str(snapshot), str(target)], core.ROOT, gated=True)
        except Exception as error:
            self._pending = None
            self.show_error(error)

    def scientific_task(self, action):
        try:
            if self.runner.current_process is not None:
                raise ValueError(f"当前任务：{self.runner.current_task_name}")
            if self.playing:
                raise ValueError("请先暂停到具体时刻")
            config = self.gather()
            config["sync"].update(start_s=self.requested.value(), frame_count=1, output_fps=1)
            if action == "calibrate":
                if config["source_type"] == "stereo_video":
                    config["calibration"]["status"] = "compute"
                self.reference = self.active_calibration = None
                config.pop("presentation", None)
                self.show_reference()
            if action in {"reference", "reconstruct"}:
                if not self.active_calibration and config["calibration"]["status"] != "provided":
                    raise ValueError("请先运行标定，或打开具有官方标定文件的配置")
                if config["source_type"] == "stereo_video" and self.sync_result is None:
                    raise ValueError("请先运行同步")
                if action == "reconstruct" and self.reference is None:
                    raise ValueError("请先建立或选择固定参考面")
                self.viewer.clear()
            if action == "reference":
                config.pop("presentation", None)
            self.launch(action, config, {"calibrate": "相机标定", "sync": "视频同步", "reference": "当前帧参考面（官方 WASS）", "reconstruct": "当前帧三维重建"}[action])
        except Exception as error:
            self.show_error(error)

    def task_done(self, status, code):
        pending, self._pending = self._pending, None
        if self._exit_when_done:
            QTimer.singleShot(0, self.close)
            return
        if pending is None or status != "PROCESS_COMPLETE":
            return
        action, target, config = pending
        try:
            payload = json.loads((target / "result.json").read_text(encoding="utf-8"))
            if action == "calibrate":
                self.active_calibration = target / "calibration"
                self.calibration_label.setText(f"标定：PROCESS_COMPLETE | {payload.get('method')}\n{payload.get('rms_px', '')}")
            elif action == "sync":
                self.sync_result = payload
                self.sync_label.setText(f"同步：PROCESS_COMPLETE | offset={self.offset():+.9f}s")
                self.show_time(payload.get("frame_mapping", [{}])[0])
            elif action == "preview":
                for canvas, side in zip(self.pause_images, ("left", "right")):
                    bgr = cv2.imdecode(np.fromfile(payload[f"{side}_file"], np.uint8), cv2.IMREAD_COLOR)
                    if bgr is None:
                        raise ValueError("无法读取 P0 canonical 暂停帧")
                    canvas.set_rgb(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
                self.show_time(payload)
            elif action in {"reference", "reconstruct"}:
                if action == "reference":
                    self.reference = payload["reference"]
                    self.active_calibration = Path(payload["science_run"]) / "wass" / "config"
                    self.show_reference()
                self.viewer.load(target, payload["view"])
                self.show_time(payload["view"])
                self.pages.setCurrentIndex(1)
            elif action == "view":
                self.viewer.load(target, payload)
                self.pages.setCurrentIndex(1)
        except Exception as error:
            self.viewer.clear()
            self.show_error(error)

    def update_task(self):
        busy = self.runner.current_process is not None
        elapsed = time.monotonic() - self.runner.started_at if busy else self.runner.elapsed_s
        self.task_label.setText(f"当前任务：{self.runner.current_task_name} | PROCESS_RUNNING | {elapsed:.1f}s" if busy else
            f"当前任务：空闲 | {self.runner.last_task_name} {self.runner.status} | {elapsed:.1f}s")
        for widget in (self.inputs, self.play_button, self.pause_button, self.requested, self.slider):
            widget.setEnabled(not busy)
        self.stop_button.setEnabled(busy)

    def offset(self):
        return float((self.sync_result or {}).get("audio_lag_right_minus_left_s", 0))

    def load_videos(self):
        self.inputs_changed()
        self.release_videos()
        try:
            for key in ("wave_left", "wave_right"):
                capture = open_canonical_video(self.paths[key].text())
                self.captures.append(capture)
                if not capture.isOpened():
                    raise ValueError(f"无法打开视频：{self.paths[key].text()}")
            meta = core.video_metadata(self.paths["wave_left"].text())
            self.slider.setMaximum(round(meta["duration_s"] * 1000))
            self.render_raw(self.requested.value())
            self.pages.setCurrentIndex(0)
            self.invalidate_time()
        except Exception as error:
            self.show_error(error)

    def invalidate_time(self):
        self.time_label.setText(f"Requested Time：{self.requested.value():.6f}s | Left Actual PTS：N/A | Right Actual PTS：N/A | Delta t：N/A")

    def show_time(self, data):
        fmt = lambda value, unit: "N/A" if value is None else f"{value:.9f}{unit}"
        self.time_label.setText(f"Requested Time：{self.requested.value():.6f}s | Left Actual PTS：{fmt(data.get('actual_left_source_pts'), 's')} | "
            f"Right Actual PTS：{fmt(data.get('actual_right_source_pts'), 's')} | Delta t：{fmt(data.get('stereo_pair_residual_ms'), 'ms')}")

    def stop_playback(self):
        self.playing = False
        self.play_timer.stop()
        self.play_button.setText("播放")

    def release_videos(self):
        self.stop_playback()
        for capture in self.captures:
            capture.release()
        self.captures = []
        for image in self.pause_images:
            image.set_rgb(None)

    def render_raw(self, stamp):
        for capture, canvas, t in zip(self.captures, self.pause_images, (stamp, stamp + self.offset())):
            capture.set(cv2.CAP_PROP_POS_MSEC, max(0, t) * 1000)
            ok, frame = capture.read()
            canvas.set_rgb(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) if ok else None)

    def video_tick(self):
        if not self.playing:
            return
        stamp = self._play_origin + time.monotonic() - self._play_started
        if stamp * 1000 >= self.slider.maximum():
            self.stop_playback()
            return
        with QSignalBlocker(self.requested), QSignalBlocker(self.slider):
            self.requested.setValue(stamp)
            self.slider.setValue(round(stamp * 1000))
        self.render_raw(stamp)
        self.invalidate_time()

    def toggle_play(self):
        if self.playing:
            self.stop_playback()
            self.pause_preview()
        else:
            if len(self.captures) != 2 or not all(capture.isOpened() for capture in self.captures):
                self.show_error("请先载入左右视频")
                return
            self.viewer.clear()
            self.playing = True
            self._play_origin, self._play_started = self.requested.value(), time.monotonic()
            self.play_timer.start(100)
            self.play_button.setText("暂停")
            self.invalidate_time()

    def slider_moved(self, value):
        self.stop_playback()
        self.requested.setValue(value / 1000)
        self.viewer.clear()
        self.invalidate_time()

    def seek(self):
        self.stop_playback()
        self.slider.setValue(round(self.requested.value() * 1000))
        self.viewer.clear()
        self.invalidate_time()
        self.render_raw(self.requested.value())

    def selection_changed(self):
        if not self._populating:
            self.viewer.clear()
            self.invalidate_time()

    def pause_preview(self):
        if self.runner.current_process is not None:
            return
        if self.sync_result is None:
            self.invalidate_time()
            return
        config = self.gather()
        config["minimal"] = dict(time_s=self.requested.value(), offset_s=self.offset())
        self.launch("preview", config, "暂停源帧读取")

    def show_reference(self):
        if self.reference is None:
            self.reference_label.setText("当前参考面：未设置")
        else:
            self.reference_label.setText(f"Reference: {self.reference.get('timestamp', self.reference.get('reference_time_s'))}\n"
                f"{self.reference['reference_plane_id']}\nsource: {self.reference.get('reference_definition', self.reference.get('source'))}")

    def import_reference(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择固定参考面", self.output.text(), "参考面 (*.json)")
        if path:
            try:
                binding = json.loads(Path(path).read_text(encoding="utf-8"))
                reference, _ = core.reference_from_metadata(binding)
                origin = Path(binding["scientific_run"])
                core.validate_run_inputs(origin, self.gather())
                coordinates.require_match(reference, coordinates.identity(origin))
                if self.active_calibration:
                    from pipeline.common import sha256
                    for name in ("intrinsics_00.xml", "intrinsics_01.xml", "distortion_00.xml", "distortion_01.xml"):
                        if sha256(self.active_calibration / name) != sha256(origin / "wass" / "config" / name):
                            raise ValueError("REFERENCE_FRAME_MISMATCH: active intrinsics differ; 请重新建立参考面")
                self.reference, self.active_calibration = binding, origin / "wass" / "config"
                self.show_reference()
            except Exception as error:
                self.show_error(error)

    def open_result(self):
        path, _ = QFileDialog.getOpenFileName(self, "打开已有官方结果", self.output.text(), "运行报告 (run_report.json)")
        if path:
            try:
                run = Path(path).parent
                frames = sorted((run / "pixel" / "pixel_height").glob("*.npz"))
                if not frames:
                    raise ValueError("没有现有 pixel XYZ/H 输出")
                frame_id, ok = QInputDialog.getItem(self, "结果帧", "frame id", [str(int(item.stem)) for item in frames], 0, False)
                if not ok:
                    return
                config = self.gather()
                config["minimal"] = dict(run=str(run), frame_id=int(frame_id))
                reference = run / "reference_plane.json"
                if reference.is_file():
                    config["minimal"]["reference"] = json.loads(reference.read_text(encoding="utf-8"))
                self.launch("view", config, "读取官方结果")
            except Exception as error:
                self.show_error(error)

    def show_error(self, error):
        self.append_log(f"[失败] {error}\n")
        self.statusBar().showMessage(str(error))

    def closeEvent(self, event):
        if self.runner.current_process is None:
            self.release_videos()
            event.accept()
            return
        dialog = QMessageBox(self)
        dialog.setWindowTitle("关闭软件")
        dialog.setText(f"当前正在运行：{self.runner.current_task_name}")
        dialog.addButton("继续等待", QMessageBox.ButtonRole.AcceptRole)
        terminate = dialog.addButton("终止任务并退出", QMessageBox.ButtonRole.DestructiveRole)
        cancel = dialog.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(cancel)
        dialog.exec()
        if dialog.clickedButton() is terminate:
            if self.runner.current_process is None:
                event.accept()
                return
            self._exit_when_done = True
            self.runner.terminate()
        event.ignore()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", nargs="?", type=Path)
    args = parser.parse_args()
    app = QApplication(sys.argv)
    window = MainWindow(args.config)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
