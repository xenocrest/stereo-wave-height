"""Two-page PySide6 shell for the frozen Vieira/WASS pipeline.

Run from the repository root with the scientific environment's Python:
    python -m app.main
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2
import numpy as np
from plyfile import PlyData
from PySide6.QtCore import QPoint, QRect, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QImage, QPainter, QPen
from PySide6.QtWidgets import (QApplication, QCheckBox, QDoubleSpinBox, QFileDialog,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPushButton, QSlider, QSpinBox, QTabWidget,
    QTextEdit, QVBoxLayout, QWidget)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from app import core, presentation, coordinates


class WorkThread(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, action: str, config: dict):
        super().__init__()
        self.action = action
        self.config = deepcopy(config)

    def run(self) -> None:
        target = None
        try:
            snapshot, target = core.stage_paths(self.config, self.action)
            command = core.command_for(self.action, snapshot, target, self.config["tools"]["python"])
            report = core.run_external(command, target / "tool.log")
            self.done.emit({"action": self.action, "target": str(target), "report": report,
                            "config": self.config})
        except Exception as error:
            detail = str(error)
            report_path = target / "science" / "run_report.json" if target is not None else None
            if report_path is not None and report_path.is_file():
                report = json.loads(report_path.read_text(encoding="utf-8"))
                detail += f"\nScientific stage: {report.get('status')} | {report.get('error', {}).get('message', '')}"
            self.failed.emit(detail)


class ExportThread(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, destination, result, raw, overlay, ply, reference, region):
        super().__init__()
        self.arguments = (destination, result, raw, overlay, ply, reference, region)

    def run(self) -> None:
        try:
            self.done.emit(presentation.export_current_frame(*self.arguments))
        except Exception as error:
            self.failed.emit(str(error))


class ImageCanvas(QWidget):
    hovered = Signal(int, int)
    region_selected = Signal(object)

    def __init__(self):
        super().__init__()
        self.setMouseTracking(True)
        self.setMinimumSize(550, 300)
        self.image: QImage | None = None
        self.border: np.ndarray | None = None
        self.image_shape = (1, 1)
        self.region: tuple[float, float, float, float] | None = None
        self.selecting_region = False
        self._region_start: QPoint | None = None

    def set_region(self, region: tuple[float, float, float, float] | None) -> None:
        self.region = region
        self.update()

    def set_rgb(self, rgb: np.ndarray | None, border: np.ndarray | None = None) -> None:
        if rgb is None:
            self.image = None
            self.border = None
        else:
            arr = np.ascontiguousarray(rgb, dtype=np.uint8)
            self.image = QImage(arr.data, arr.shape[1], arr.shape[0], 3 * arr.shape[1],
                                QImage.Format.Format_RGB888).copy()
            self.image_shape = arr.shape[:2]
            self.border = border
        self.update()

    def _draw_rect(self) -> QRect:
        if self.image is None:
            return QRect()
        scaled = self.image.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        return QRect((self.width() - scaled.width()) // 2,
                     (self.height() - scaled.height()) // 2,
                     scaled.width(), scaled.height())

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.black)
        if self.image is None:
            painter.setPen(Qt.GlobalColor.white)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "尚无画面")
            return
        rect = self._draw_rect()
        painter.drawImage(rect, self.image)
        if self.border is not None:
            mask = cv2.resize(self.border.astype(np.uint8),
                              (rect.width(), rect.height()), interpolation=cv2.INTER_NEAREST)
            outlines, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            painter.setPen(QPen(Qt.GlobalColor.cyan, 2))
            for line in outlines:
                if len(line) < 2:
                    continue
                points = [QPoint(rect.left() + int(x), rect.top() + int(y)) for [[x, y]] in line]
                for start, end in zip(points, points[1:]):
                    painter.drawLine(start, end)
        if self.region is not None:
            x0, y0, x1, y1 = self.region
            painter.setPen(QPen(Qt.GlobalColor.magenta, 2))
            painter.drawRect(QRect(rect.left() + round(x0 * rect.width()), rect.top() + round(y0 * rect.height()),
                                   round((x1 - x0) * rect.width()), round((y1 - y0) * rect.height())))

    def mousePressEvent(self, event) -> None:
        if self.selecting_region and event.button() == Qt.MouseButton.LeftButton:
            self._region_start = event.position().toPoint()

    def mouseReleaseEvent(self, event) -> None:
        if not self.selecting_region or self._region_start is None:
            return
        rect = self._draw_rect()
        if rect.isEmpty():
            return
        first, last = self._region_start, event.position().toPoint()
        self._region_start = None
        self.selecting_region = False
        x0, x1 = sorted((max(rect.left(), min(rect.right(), p.x())) for p in (first, last)))
        y0, y1 = sorted((max(rect.top(), min(rect.bottom(), p.y())) for p in (first, last)))
        if x1 - x0 < 3 or y1 - y0 < 3:
            return
        self.region_selected.emit(((x0 - rect.left()) / rect.width(), (y0 - rect.top()) / rect.height(),
                                   (x1 - rect.left()) / rect.width(), (y1 - rect.top()) / rect.height()))

    def mouseMoveEvent(self, event) -> None:
        rect = self._draw_rect()
        pos = event.position().toPoint()
        if rect.contains(pos) and rect.width() and rect.height():
            u = min(self.image_shape[1] - 1, max(0, int((pos.x() - rect.left()) * self.image_shape[1] / rect.width())))
            v = min(self.image_shape[0] - 1, max(0, int((pos.y() - rect.top()) * self.image_shape[0] / rect.height())))
            self.hovered.emit(u, v)


class PointCloudView(FigureCanvasQTAgg):
    def __init__(self):
        self.figure = Figure(figsize=(7, 5))
        super().__init__(self.figure)
        self.setMinimumSize(550, 300)

    def show_ply(self, path: Path) -> int:
        vertex = PlyData.read(path)["vertex"].data
        total = len(vertex)
        step = max(1, (total + 19999) // 20000)
        chosen = vertex[::step]
        x, y, z = (np.asarray(chosen[name], dtype=float) for name in ("x", "y", "z"))
        self.figure.clear()
        ax = self.figure.add_subplot(111, projection="3d")
        ax.scatter(x, y, z, c=z, cmap="turbo", s=0.3)
        ax.set(xlabel="X", ylabel="Y", zlabel="Z", title=f"Official WASS XYZ ({total:,} points; shown {len(x):,})")
        self.draw_idle()
        return total


def labeled_path(button_text: str, callback) -> tuple[QWidget, QLineEdit]:
    container = QWidget()
    row = QHBoxLayout(container)
    row.setContentsMargins(0, 0, 0, 0)
    edit = QLineEdit()
    button = QPushButton(button_text)
    button.clicked.connect(lambda: callback(edit))
    row.addWidget(edit, 1)
    row.addWidget(button)
    return container, edit


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("双目瞬时水面三维测量 — 离线基础流程")
        self.resize(1320, 890)
        self.config: dict | None = None
        self.project_path: Path | None = None
        self.calibration_run: Path | None = None
        self.sync_run: Path | None = None
        self.science_run: Path | None = None
        self.reference = None
        self.reference_time_s: float | None = None
        self.reference_identity = ""
        self.reference_run: Path | None = None
        self.result: dict | None = None
        self.raw_rgb: np.ndarray | None = None
        self.overlay_rgb: np.ndarray | None = None
        self.preview_left: np.ndarray | None = None
        self.preview_right: np.ndarray | None = None
        self.worker: WorkThread | None = None
        self.playing = False
        self.offset_s = 0.0
        self.frame_rate = 30.0
        self.cache: dict[str, Path] = {}
        self._viewing_existing_run = False
        self.reconstruction_failed = False
        self.result_stale = False
        self.reference_confirmed = False
        self.measurement_region: tuple[float, float, float, float] | None = None
        self.export_worker: ExportThread | None = None
        self._ready_summary = ""
        self._populating = False
        self._input_signature = ""
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self._build_ui()
        for edit in (self.cal_left, self.cal_right, self.wave_left, self.wave_right):
            edit.editingFinished.connect(self._inputs_changed)
        for spin in (self.board_cols, self.board_rows, self.square_mm, self.baseline_mm):
            spin.editingFinished.connect(self._inputs_changed)
        self._update_status()

    def _pick_video(self, edit: QLineEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择视频", "", "Video (*.mp4 *.mov *.avi *.mkv);;All files (*)")
        if path:
            edit.setText(path)
            self._inputs_changed()

    def _pick_json(self, edit: QLineEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择参考面 JSON", "", "JSON (*.json)")
        if path:
            edit.setText(path)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        project_row = QHBoxLayout()
        self.new_button = QPushButton("新建空项目")
        self.new_button.clicked.connect(self._new_project)
        self.open_button = QPushButton("打开项目 YAML")
        self.open_button.clicked.connect(self._open_project)
        self.save_button = QPushButton("保存项目")
        self.save_button.clicked.connect(self._save_project)
        self.tools_button = QPushButton("检查工具链")
        self.tools_button.clicked.connect(self._check_toolchain)
        for button in (self.new_button, self.open_button, self.save_button, self.tools_button):
            project_row.addWidget(button)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addLayout(project_row)
        layout.addWidget(self.status)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        self._build_calibration_page()
        self._build_measurement_page()

    def _build_calibration_page(self) -> None:
        page = QWidget()
        self.tabs.addTab(page, "1 相机标定")
        layout = QVBoxLayout(page)
        form = QFormLayout()
        container, self.cal_left = labeled_path("选择…", self._pick_video)
        form.addRow("左标定视频", container)
        container, self.cal_right = labeled_path("选择…", self._pick_video)
        form.addRow("右标定视频", container)
        board_row = QHBoxLayout()
        self.board_cols, self.board_rows = QSpinBox(), QSpinBox()
        self.board_cols.setRange(2, 50)
        self.board_rows.setRange(2, 50)
        self.square_mm = QDoubleSpinBox()
        self.square_mm.setRange(0.01, 1000.0)
        self.square_mm.setDecimals(3)
        for label, widget in (("columns", self.board_cols), ("rows", self.board_rows), ("square mm", self.square_mm)):
            board_row.addWidget(QLabel(label))
            board_row.addWidget(widget)
        form.addRow("棋盘内角点", board_row)
        self.baseline_mm = QDoubleSpinBox()
        self.baseline_mm.setRange(0.01, 100000.0)
        self.baseline_mm.setDecimals(3)
        form.addRow("双目基线（mm）", self.baseline_mm)
        self.output_root = QLineEdit()
        form.addRow("科学运行输出根目录（ASCII）", self.output_root)
        layout.addLayout(form)
        self.calibrate_button = QPushButton("开始标定（调用已冻结 OpenCV 流程）")
        self.calibrate_button.clicked.connect(self._calibrate)
        layout.addWidget(self.calibrate_button)
        self.calibration_status = QLabel("INTRINSICS_NOT_READY | EXTRINSICS_NOT_READY")
        layout.addWidget(self.calibration_status)
        self.calibration_text = QTextEdit()
        self.calibration_text.setReadOnly(True)
        layout.addWidget(self.calibration_text, 1)

    def _build_measurement_page(self) -> None:
        page = QWidget()
        self.tabs.addTab(page, "2 瞬时水面测量")
        layout = QVBoxLayout(page)
        form = QFormLayout()
        container, self.wave_left = labeled_path("选择…", self._pick_video)
        form.addRow("左水面视频", container)
        container, self.wave_right = labeled_path("选择…", self._pick_video)
        form.addRow("右水面视频", container)
        layout.addLayout(form)
        sync_row = QHBoxLayout()
        self.sync_button = QPushButton("同步（TLCC）")
        self.sync_button.clicked.connect(self._synchronize)
        self.sync_status = QLabel("NOT_READY")
        sync_row.addWidget(self.sync_button)
        sync_row.addWidget(self.sync_status, 1)
        self.batch_count = QSpinBox()
        self.batch_count.setRange(2, 1000)
        sync_row.addWidget(QLabel("同次官方运行帧数"))
        sync_row.addWidget(self.batch_count)
        layout.addLayout(sync_row)
        reference_row = QHBoxLayout()
        self.static_button = QPushButton("将当前暂停时刻设为静水参考")
        self.static_button.clicked.connect(self._set_static_reference)
        self.import_reference_button = QPushButton("导入固定参考面")
        self.import_reference_button.clicked.connect(self._import_reference)
        self.confirm_reference_button = QPushButton("确认并冻结参考面")
        self.confirm_reference_button.clicked.connect(self._confirm_reference)
        self.reference_label = QLabel("参考面：NOT_READY")
        self.reference_label.setWordWrap(True)
        reference_row.addWidget(self.static_button)
        reference_row.addWidget(self.import_reference_button)
        reference_row.addWidget(self.confirm_reference_button)
        reference_row.addWidget(self.reference_label, 1)
        layout.addLayout(reference_row)
        controls = QHBoxLayout()
        self.play_button = QPushButton("播放")
        self.play_button.clicked.connect(self._toggle_play)
        self.previous_button = QPushButton("上一帧")
        self.previous_button.clicked.connect(lambda: self._step(-1))
        self.next_button = QPushButton("下一帧")
        self.next_button.clicked.connect(lambda: self._step(1))
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.valueChanged.connect(self._seek)
        self.time_label = QLabel("Frame: — | t=—")
        for widget in (self.play_button, self.previous_button, self.next_button):
            controls.addWidget(widget)
        controls.addWidget(self.slider, 1)
        controls.addWidget(self.time_label)
        layout.addLayout(controls)
        views = QHBoxLayout()
        self.image_canvas = ImageCanvas()
        self.image_canvas.hovered.connect(self._hover)
        self.image_canvas.region_selected.connect(self._set_measurement_region)
        self.right_canvas = ImageCanvas()
        views.addWidget(self.image_canvas, 1)
        views.addWidget(self.right_canvas, 1)
        layout.addLayout(views, 1)
        action_row = QHBoxLayout()
        self.reconstruct_button = QPushButton("解算当前暂停帧")
        self.reconstruct_button.clicked.connect(self._reconstruct)
        self.open_run_button = QPushButton("查看已有科学运行")
        self.open_run_button.clicked.connect(self._open_run)
        self.show_common = QCheckBox("显示官方有效重建区域边界")
        self.show_common.stateChanged.connect(self._display_mode)
        self.region_button = QPushButton("设置测量区域（拖动矩形）")
        self.region_button.clicked.connect(self._start_region_selection)
        self.clear_region_button = QPushButton("清除测量区域")
        self.clear_region_button.clicked.connect(lambda: self._set_measurement_region(None))
        self.export_button = QPushButton("导出当前帧结果")
        self.export_button.clicked.connect(self._export_result)
        action_row.addWidget(self.reconstruct_button)
        action_row.addWidget(self.open_run_button)
        action_row.addWidget(self.show_common)
        layout.addLayout(action_row)
        region_row = QHBoxLayout()
        for button in (self.region_button, self.clear_region_button, self.export_button):
            region_row.addWidget(button)
        layout.addLayout(region_row)
        modes = QHBoxLayout()
        self.raw_button = QPushButton("原始水面")
        self.cloud_button = QPushButton("三维点云")
        self.overlay_button = QPushButton("叠加显示")
        for button in (self.raw_button, self.cloud_button, self.overlay_button):
            modes.addWidget(button)
        self.raw_button.clicked.connect(lambda: self._display_mode("raw"))
        self.cloud_button.clicked.connect(lambda: self._display_mode("cloud"))
        self.overlay_button.clicked.connect(lambda: self._display_mode("overlay"))
        layout.addLayout(modes)
        self.point_cloud = PointCloudView()
        self.point_cloud.hide()
        layout.addWidget(self.point_cloud, 1)
        self.frame_summary = QLabel("尚未解算")
        self.frame_summary.setWordWrap(True)
        self.scope_notice = QLabel("COMMON_STEREO_REGION：NOT_AVAILABLE（COMMON_REGION_NOT_AVAILABLE）；MEASUREMENT_REGION：NONE；"
                                   "HEIGHT_AVAILABLE_REGION：官方有限 XYZ/H 像素（青色边界）。彩色叠加含 OFFICIAL_GRID_ESTIMATE，"
                                   "不是全部直接三角测量；非水面结构可能包含在官方结果内。")
        self.scope_notice.setWordWrap(True)
        self.hover_label = QLabel("像素高度：N/A | 来源：NO_DATA")
        self.hover_label.setWordWrap(True)
        layout.addWidget(self.frame_summary)
        layout.addWidget(self.scope_notice)
        layout.addWidget(self.hover_label)

    def _new_project(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            self._error("科学任务仍在运行，完成后才能切换项目")
            return
        path, _ = QFileDialog.getSaveFileName(self, "新建项目", "project.yaml", "YAML (*.yaml *.yml)")
        if not path:
            return
        name = Path(path).stem.replace(" ", "_")
        self.config = core.new_project(name, "D:/stereo-wave-height-runs/offline_app")
        self.project_path = Path(path)
        self._populate()
        self._save_project()

    def _open_project(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            self._error("科学任务仍在运行，完成后才能切换项目")
            return
        path, _ = QFileDialog.getOpenFileName(self, "打开项目", "", "YAML (*.yaml *.yml)")
        if not path:
            return
        try:
            self.config = core.read_project(path)
            self.project_path = Path(path)
            self._populate()
        except Exception as error:
            self._error(str(error))

    def _populate(self) -> None:
        assert self.config is not None
        self._populating = True
        self.timer.stop()
        self.playing = False
        self.play_button.setText("播放")
        self.calibration_run = None
        self.sync_run = None
        self.science_run = None
        self.reference = None
        self.reference_time_s = None
        self.reference_identity = ""
        self.reference_run = None
        self.result = None
        self.raw_rgb = None
        self.overlay_rgb = None
        self.preview_left = None
        self.preview_right = None
        self.offset_s = 0.0
        self.cache.clear()
        self._viewing_existing_run = False
        self.reconstruction_failed = False
        self.result_stale = False
        self.reference_confirmed = False
        self.measurement_region = None
        self._ready_summary = ""
        self.calibration_status.setText("INTRINSICS_NOT_READY | EXTRINSICS_NOT_READY")
        self.calibration_text.clear()
        self.sync_status.setText("NOT_READY")
        self.reference_label.setText("未设置参考面")
        self.frame_summary.setText("尚未解算当前帧")
        self.hover_label.setText("像素高度：N/A | 来源：NO_DATA")
        self.scope_notice.setText("COMMON_STEREO_REGION：NOT_AVAILABLE（COMMON_REGION_NOT_AVAILABLE）；MEASUREMENT_REGION：NONE；"
                                  "HEIGHT_AVAILABLE_REGION：当前无结果。")
        self.point_cloud.hide()
        self.image_canvas.show()
        self.right_canvas.show()
        self.image_canvas.set_rgb(None)
        self.right_canvas.set_rgb(None)
        self.slider.blockSignals(True)
        self.slider.setRange(0, 0)
        self.slider.setValue(0)
        self.slider.blockSignals(False)
        self.time_label.setText("Frame ≈0 | t=0.000s")
        cal = self.config["calibration"]
        sync = self.config["sync"]
        board = cal.get("checkerboard", {})
        self.cal_left.setText(cal.get("left_video", ""))
        self.cal_right.setText(cal.get("right_video", ""))
        self.wave_left.setText(sync.get("left_video", ""))
        self.wave_right.setText(sync.get("right_video", ""))
        self.board_cols.setValue(int(board.get("columns", 9)))
        self.board_rows.setValue(int(board.get("rows", 6)))
        self.square_mm.setValue(float(board.get("square_size_m", 0.02)) * 1000)
        self.baseline_mm.setValue(float(self.config.get("surface", {}).get("baseline_m", 0.16)) * 1000)
        self.output_root.setText(str(self.config.get("output_root", "")))
        self.batch_count.setValue(int(sync.get("frame_count", 20)))
        self.image_canvas.set_region(None)
        self.image_canvas.selecting_region = False
        saved_region = self.config.get("presentation", {}).get("measurement_region_normalized")
        if saved_region is not None:
            self._set_measurement_region(tuple(float(value) for value in saved_region))
        try:
            self._load_videos()
        finally:
            self._populating = False
        self._input_signature = core.project_input_identity(self.config)
        binding = self.config.get("presentation", {}).get("frozen_reference")
        if binding:
            self._restore_reference(binding)
        self._update_status()

    def _gather(self) -> dict:
        if self.config is None:
            raise ValueError("请先新建或打开项目")
        config = deepcopy(self.config)
        config["calibration"]["left_video"] = self.cal_left.text().strip()
        config["calibration"]["right_video"] = self.cal_right.text().strip()
        config["calibration"]["checkerboard"] = {"columns": self.board_cols.value(),
            "rows": self.board_rows.value(), "square_size_m": self.square_mm.value() / 1000}
        config["sync"]["left_video"] = self.wave_left.text().strip()
        config["sync"]["right_video"] = self.wave_right.text().strip()
        config["sync"]["frame_count"] = self.batch_count.value()
        config["surface"]["baseline_m"] = self.baseline_mm.value() / 1000
        config["output_root"] = self.output_root.text().strip()
        fallback = config.get("wass", {}).get("fallback_calibration")
        if fallback and (not config["wass"].get("allow_extrinsic_fallback") or not fallback.get("path")):
            raise ValueError("历史外参 fallback 必须同时显式设置 allow_extrinsic_fallback=true 和可追溯的 fallback path")
        config.setdefault("presentation", {}).update({
            "measurement_region_source": "USER_RECTANGLE" if self.measurement_region is not None else "NONE",
            "measurement_region_normalized": self.measurement_region,
            "roi_affects_science": False,
        })
        return config

    def _inputs_changed(self) -> None:
        if self._populating or self.config is None:
            return
        config = self._gather()
        identity = core.project_input_identity(config)
        if identity == self._input_signature:
            return
        self.timer.stop()
        self.playing = False
        self.play_button.setText("播放")
        self._mark_stale()
        self.calibration_run = self.sync_run = self.science_run = self.reference_run = None
        self.reference = None
        self.reference_time_s = None
        self.reference_identity = ""
        self.reference_confirmed = False
        self.cache.clear()
        self.preview_left = self.preview_right = None
        self.offset_s = 0.0
        self.measurement_region = None
        self.image_canvas.set_region(None)
        self.image_canvas.set_rgb(None)
        self.right_canvas.set_rgb(None)
        self.slider.blockSignals(True)
        self.slider.setRange(0, 0)
        self.slider.setValue(0)
        self.slider.blockSignals(False)
        self.time_label.setText("Frame ≈0 | t=0.000s")
        self.scope_notice.setText("COMMON_STEREO_REGION：NOT_AVAILABLE（COMMON_REGION_NOT_AVAILABLE）；MEASUREMENT_REGION：NONE；"
                                  "HEIGHT_AVAILABLE_REGION：输入已改变，当前无结果。")
        self.reference_label.setText("输入已改变：请重新同步并选择参考面")
        self.calibration_status.setText("INTRINSICS_NOT_READY | EXTRINSICS_NOT_READY")
        self.sync_status.setText("NOT_READY")
        config.get("presentation", {}).pop("frozen_reference", None)
        config["presentation"].update(measurement_region_source="NONE", measurement_region_normalized=None)
        self.config = config
        self._input_signature = identity
        self._load_videos()
        self._update_status()

    def _restore_reference(self, binding: dict) -> None:
        if binding.get("project_input_identity") != core.project_input_identity(self.config):
            raise ValueError("Saved reference belongs to different project inputs")
        reference, identity = core.reference_from_metadata(binding)
        run = Path(binding["scientific_run"])
        core.validate_run_inputs(run, self.config)
        if not identity or core.calibration_identity(run) != identity:
            raise ValueError("Saved reference and scientific run calibration identities differ")
        self.reference, self.reference_identity, self.reference_run = reference, identity, run
        self.reference_time_s = binding.get("reference_time_s")
        self.reference_confirmed = True
        self.sync_run = run
        sync = json.loads((run / "sync" / "sync.json").read_text(encoding="utf-8"))
        self.offset_s = float(sync.get("audio_lag_right_minus_left_s", 0.0))
        label = "内部固定参考面" if reference.mode == "designated_static_water_frame" else "提供的物理参考面"
        self.reference_label.setText(f"{label} {reference.plane_id} | n={reference.normal} d={reference.d} | 项目已冻结")

    def _persist_reference(self) -> None:
        config = self._gather()
        binding = self.reference.as_dict()
        binding.update(calibration_identity=self.reference_identity, scientific_run=str(self.reference_run.resolve()),
                       reference_time_s=self.reference_time_s, project_input_identity=core.project_input_identity(config))
        if self.reference_time_s is not None:
            mapping = json.loads((self.reference_run / "sync" / "sync.json").read_text(encoding="utf-8"))["frame_mapping"]
            row = min(mapping, key=lambda item: abs(float(item["left_actual_timestamp_s"]) - self.reference_time_s))
            binding.update(source_frame_id=int(row["output_index"]),
                           source_timestamp_s=float(row["left_actual_timestamp_s"]),
                           frame_id=int(row["output_index"]), timestamp=float(row["left_actual_timestamp_s"]))
        else:
            binding.update(frame_id=None, timestamp=None)
        config["presentation"]["frozen_reference"] = binding
        if self.project_path is not None:
            (self.project_path.parent / "reference_plane.json").write_text(
                json.dumps(binding, ensure_ascii=False, indent=2), encoding="utf-8")
            core.save_project(config, self.project_path)
        self.config = config

    def _save_project(self) -> None:
        try:
            self.config = self._gather()
            if self.project_path is None:
                raise ValueError("No project path")
            core.save_project(self.config, self.project_path)
            self._update_status()
        except Exception as error:
            self._error(str(error))

    def _update_status(self) -> None:
        name = self.config.get("project", "未打开") if self.config else "未打开"
        cal = "READY" if self.calibration_run else "NOT_READY"
        if self.science_run:
            report = json.loads((self.science_run / "wass" / "run_summary.json").read_text(encoding="utf-8"))
            cal = "FALLBACK" if report["active_calibration"]["fallback"] else "READY"
        reconstruction = ("READY" if self.result is not None else "FAILED" if self.reconstruction_failed else
                          "STALE" if self.result_stale else "NOT_RUN")
        current_frame = self.preview_left is not None and not self.playing
        self.status.setText(f"项目：{name}    Calibration: {cal}    Sync: {'READY' if self.sync_run else 'NOT_READY'}"
            f"    Reference: {'READY' if self.reference_confirmed else 'CANDIDATE' if self.reference_time_s is not None else 'NOT_READY'}"
            f"    Current Frame: {'READY' if current_frame else 'NOT_READY'}"
            f"    Reconstruction: {reconstruction}")

    def _start_work(self, action: str, config: dict) -> None:
        if self.worker and self.worker.isRunning():
            self._error("已有任务正在运行")
            return
        if action == "reconstruct":
            self.result = None
            self.raw_rgb = None
            self.overlay_rgb = None
            self.reconstruction_failed = False
            self.result_stale = False
            self.frame_summary.setText("官方科学流程运行中；结果尚未产生。")
            self.point_cloud.hide()
            self.image_canvas.show()
            self.right_canvas.show()
            self.image_canvas.set_rgb(self.preview_left)
            self.right_canvas.set_rgb(self.preview_right)
        self.worker = WorkThread(action, config)
        self.worker.done.connect(self._work_done)
        self.worker.failed.connect(lambda message: self._work_failed(action, message))
        self.worker.start()
        self.status.setText(f"{action} 运行中；科学工具完成后自动更新。")

    def _calibrate(self) -> None:
        try:
            config = self._gather()
            for key in ("left_video", "right_video"):
                if not Path(config["calibration"][key]).is_file():
                    raise FileNotFoundError(config["calibration"][key])
            self._start_work("calibrate", config)
        except Exception as error:
            self._error(str(error))

    def _synchronize(self) -> None:
        try:
            config = self._gather()
            self._load_videos()
            config["sync"].update(start_s=self.slider.value() / 1000)
            self._start_work("sync", config)
        except Exception as error:
            self._error(str(error))

    def _work_done(self, payload: dict) -> None:
        try:
            if core.project_input_identity(payload["config"]) != core.project_input_identity(self._gather()):
                raise ValueError("运行期间输入发生变化；完成结果已保留在原运行目录，不能绑定到当前项目")
            action, target, report = payload["action"], Path(payload["target"]), payload["report"]
            if action == "calibrate":
                self.calibration_run = target
                matrix = core.calibration_matrices(target)
                fallback = payload["config"].get("wass", {}).get("fallback_calibration")
                self.calibration_status.setText("INTRINSICS_COMPUTED | " +
                    ("EXTRINSICS_FALLBACK configured; actual active bundle selected during WASS" if fallback else
                     "EXTRINSICS_NOT_READY (requires WASS autocalibration)"))
                self.calibration_text.setText(json.dumps(matrix, ensure_ascii=False, indent=2))
            elif action == "sync":
                self.sync_run = target
                self.offset_s = float(report["audio_lag_right_minus_left_s"])
                self.sync_status.setText(f"READY | right-left={self.offset_s:+.6f} s | {report['method']}")
                self._render_preview()
            elif action == "reconstruct":
                self.science_run = Path(report["science_run"])
                self._viewing_existing_run = False
                self.reconstruction_failed = False
                self._receive_reconstruction(payload["config"])
            self._update_status()
        except Exception as error:
            if payload.get("action") == "reconstruct":
                self.reconstruction_failed = True
            self._error(str(error))

    def _load_videos(self) -> None:
        left, right = self.wave_left.text().strip(), self.wave_right.text().strip()
        if not (Path(left).is_file() and Path(right).is_file()):
            return
        lm, rm = core.video_metadata(left), core.video_metadata(right)
        self.frame_rate = lm["fps"] if lm["fps"] > 0 else 30.0
        duration_ms = int(min(lm["duration_s"], rm["duration_s"]) * 1000)
        self.slider.setRange(0, duration_ms)
        self._render_preview()

    def _seek(self, value: int) -> None:
        self.time_label.setText(f"Frame ≈{value * self.frame_rate / 1000:.0f} | t={value / 1000:.3f}s")
        if self.result is not None and value != getattr(self, "_result_selection_ms", None):
            self._mark_stale()
        if not self.playing:
            self._render_preview()

    def _mark_stale(self) -> None:
        if self.result is None:
            return
        self.result = None
        self.raw_rgb = None
        self.overlay_rgb = None
        self.result_stale = True
        self.image_canvas.set_rgb(None)
        self.right_canvas.set_rgb(None)
        self.scope_notice.setText("COMMON_STEREO_REGION：NOT_AVAILABLE（COMMON_REGION_NOT_AVAILABLE）；MEASUREMENT_REGION："
            f"{'USER_RECTANGLE' if self.measurement_region else 'NONE'}；HEIGHT_AVAILABLE_REGION：STALE，旧结果已隐藏。")
        self.frame_summary.setText("STALE：已切换帧或参考面；上一帧 XYZ/H 已隐藏，请解算当前暂停帧")
        self.hover_label.setText("像素高度：N/A | NO_DATA（当前帧尚未解算）")
        self.point_cloud.hide()
        self.image_canvas.show()
        self.right_canvas.show()
        self._update_status()

    def _render_preview(self) -> None:
        if not (Path(self.wave_left.text().strip()).is_file() and Path(self.wave_right.text().strip()).is_file()):
            return
        left_t, right_t = core.aligned_preview_times(self.slider.value() / 1000, self.offset_s)
        try:
            self.preview_left = core.read_preview(self.wave_left.text().strip(), left_t)
            self.preview_right = core.read_preview(self.wave_right.text().strip(), right_t)
            if self.result is None or self.playing:
                self.image_canvas.set_rgb(self.preview_left)
                self.right_canvas.set_rgb(self.preview_right)
        except Exception as error:
            self.sync_status.setText(f"Preview error: {error}")

    def _tick(self) -> None:
        next_value = self.slider.value() + round(1000 / self.frame_rate)
        if next_value >= self.slider.maximum():
            self._toggle_play()
            return
        self.slider.setValue(next_value)
        self._render_preview()

    def _toggle_play(self) -> None:
        self.playing = not self.playing
        self.play_button.setText("暂停" if self.playing else "播放")
        if self.playing:
            self._mark_stale()
            self.timer.start(max(15, round(1000 / self.frame_rate)))
        else:
            self.timer.stop()
        self._update_status()

    def _step(self, sign: int) -> None:
        if self.playing:
            self._toggle_play()
        self.slider.setValue(max(0, min(self.slider.maximum(),
            self.slider.value() + sign * round(1000 / self.frame_rate))))

    def _set_static_reference(self) -> None:
        if self.playing:
            self._error("请先暂停视频")
            return
        if self.reference_confirmed:
            self._error("项目参考面已冻结；请新建项目开展另一组参考面运行，不能自动替换当前项目参考面")
            return
        self.reference_time_s = self.slider.value() / 1000
        self._mark_stale()
        self.reference = None
        self.reference_confirmed = False
        self.reference_identity = ""
        self.reference_run = None
        self.reference_label.setText(f"内部静水参考候选 t={self.reference_time_s:.3f}s；预览后解算以显示 n/d，再点击确认冻结。未作物理验证")
        self._update_status()

    def _import_reference(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "导入固定参考面", "", "JSON (*.json)")
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            reference, identity = core.load_reference(path)
            if self.reference_confirmed and (reference != self.reference or identity != self.reference_identity
                    or Path(data.get("scientific_run", "")).resolve() != self.reference_run.resolve()):
                raise ValueError("当前项目参考面已冻结，不能更换其系数、身份或来源运行")
            if reference.mode == "designated_static_water_frame":
                if "scientific_run" not in data or "source_frame_id" not in data:
                    raise ValueError("内部静水参考缺少源运行和帧编号，不能跨运行导入")
                run = Path(data["scientific_run"])
                mapping = json.loads((run / "sync" / "sync.json").read_text(encoding="utf-8"))["frame_mapping"]
                reference_time = float(mapping[int(data["source_frame_id"])]["left_actual_timestamp_s"])
            else:
                if "scientific_run" not in data:
                    raise ValueError("物理参考面必须提供 scientific_run，证明已配准到指定官方网格坐标；不能盲目应用到新运行")
                run = Path(data["scientific_run"])
                reference_time = None
            core.validate_run_inputs(run, self._gather())
            if not identity or core.calibration_identity(run) != identity:
                raise ValueError("Imported reference has different active K/D/R/T")
            self._mark_stale()
            self.reference, self.reference_identity, self.reference_run = reference, identity, run
            self.reference_time_s = reference_time
            self.reference_confirmed = True
            self._persist_reference()
            self.reference_label.setText(f"{self.reference.plane_id} | n={self.reference.normal} d={self.reference.d} | {self.reference.mode} | 已导入并冻结")
            self._update_status()
        except Exception as error:
            self._error(str(error))

    def _confirm_reference(self) -> None:
        if self.reference is None or self.reference_run is None:
            self._error("请先选择候选静水帧并完成一次官方重建，取得参考面的 n/d 后再确认")
            return
        try:
            if self.reference_time_s is not None:
                mapping = json.loads((self.reference_run / "sync" / "sync.json").read_text(encoding="utf-8"))["frame_mapping"]
                row = min(mapping, key=lambda item: abs(float(item["left_actual_timestamp_s"]) - self.reference_time_s))
                frame_id = int(row["output_index"])
                self.reference_label.setText(f"内部固定参考面 {self.reference.plane_id} | n={self.reference.normal} "
                                             f"d={self.reference.d} | frame={frame_id} "
                                             f"t={row['left_actual_timestamp_s']:.6f}s | 未经独立物理验证")
            self.reference_confirmed = True
            self._persist_reference()
            if self.result is not None:
                self._build_overlay()
                self.frame_summary.setText(self._ready_summary)
            self._update_status()
        except Exception as error:
            self._error(str(error))

    def _start_region_selection(self) -> None:
        if self.preview_left is None:
            self._error("请先加载并预览左水面视频")
            return
        self._display_mode("raw")
        self.image_canvas.selecting_region = True
        self.region_button.setText("在左图拖动测量矩形…")

    def _set_measurement_region(self, region) -> None:
        self.measurement_region = tuple(region) if region is not None else None
        self.image_canvas.set_region(self.measurement_region)
        self.region_button.setText("设置测量区域（拖动矩形）")
        self.scope_notice.setText("COMMON_STEREO_REGION：NOT_AVAILABLE（COMMON_REGION_NOT_AVAILABLE）；"
            f"MEASUREMENT_REGION：{'USER_RECTANGLE（紫色）' if region is not None else 'NONE'}，仅限制显示/查询/导出；"
            "HEIGHT_AVAILABLE_REGION：当前帧官方有限 XYZ/H（青色边界）；彩色叠加含 OFFICIAL_GRID_ESTIMATE，"
            "非水面结构仍可能存在。")
        if self.result is not None:
            self._build_overlay()
            self._display_mode("raw")

    def _check_toolchain(self) -> None:
        config = self.config or core.new_project("empty", "D:/stereo-wave-height-runs/offline_app")
        lines = [f"{entry['name']}: {entry['status']} | {entry['version']} | {entry['path']}"
                 for entry in presentation.toolchain(config)]
        QMessageBox.information(self, "本地科学工具链", "\n".join(lines))

    def _export_result(self) -> None:
        if self.result is None or not self.reference_confirmed or self.raw_rgb is None or self.overlay_rgb is None:
            self._error("当前帧尚无已确认参考面的结果，不能导出旧帧或候选参考的高度")
            return
        if self.export_worker is not None and self.export_worker.isRunning():
            self._error("当前帧导出仍在运行")
            return
        run = Path(self.result["run_dir"])
        frame_id = int(self.result["frame_id"])
        folder = QFileDialog.getExistingDirectory(self, "选择当前帧导出目录", str(run / "frames"))
        if not folder:
            return
        ply = run / "reconstruction" / "ply" / f"{frame_id:06d}.ply"
        self.export_worker = ExportThread(folder, self.result, self.raw_rgb, self.overlay_rgb,
                                          ply, self.reference, self.measurement_region)
        self.export_worker.done.connect(lambda info: QMessageBox.information(
            self, "导出完成", f"Frame {info['frame_id']} | {info['exported_pixel_count']:,} 个高度像素\n{folder}"))
        self.export_worker.failed.connect(self._error)
        self.export_worker.start()

    def _reconstruct(self) -> None:
        try:
            if self.playing:
                raise ValueError("必须先暂停当前帧")
            if self.sync_run is None:
                raise ValueError("请先完成左右视频同步")
            if self.reference is None and self.reference_time_s is None:
                raise ValueError("请先选择固定参考面")
            if self.reference_run is not None and not self.reference_confirmed:
                raise ValueError("请先确认并冻结已拟合的内部参考面，再切换其他待测帧")
            config = self._gather()
            target_s = self.slider.value() / 1000
            if self.reference_run is not None:
                mapping = json.loads((self.reference_run / "sync" / "sync.json").read_text(encoding="utf-8"))["frame_mapping"]
                nearest = min(mapping, key=lambda row: abs(float(row["left_actual_timestamp_s"]) - target_s))
                tolerance = 1.5 / max(self.frame_rate, 1)
                if abs(float(nearest["left_actual_timestamp_s"]) - target_s) > tolerance:
                    config["_app_target_s"] = target_s
                    config["_app_target_frame"] = 0
                    config["sync"].update(start_s=target_s, frame_count=1)
                    self._pending_key = core.cache_key(config, target_s)
                    cached = self.cache.get(self._pending_key)
                    if cached is not None and (cached / "run_report.json").is_file():
                        self.science_run = cached
                        self._receive_reconstruction(config)
                    else:
                        self._start_work("reconstruct", config)
                    return
                config["_app_target_s"] = target_s
                config["_app_target_frame"] = int(nearest["output_index"])
                if self.reference_time_s is not None:
                    config["_app_reference_frame"] = next(
                        int(row["output_index"]) for row in mapping
                        if abs(float(row["left_actual_timestamp_s"]) - self.reference_time_s) <= tolerance)
                self.science_run = self.reference_run
                self._pending_key = core.cache_key(config, target_s)
                self._receive_reconstruction(config)
                return
            config["_app_target_s"] = target_s
            if self.reference_time_s is not None:
                reference_s = self.reference_time_s
                config["_app_reference_time_s"] = reference_s
                span = abs(target_s - reference_s)
                count = config["sync"]["frame_count"]
                config["sync"].update(start_s=min(reference_s, target_s),
                    output_fps=(count - 1) / span if span > 0.001 else config["sync"].get("output_fps", 2.0))
                config["_app_reference_frame"] = 0 if reference_s <= target_s else count - 1
                config["_app_target_frame"] = count - 1 if reference_s < target_s - 0.001 else 0
            else:
                config["_app_reference_plane_id"] = self.reference.plane_id
                config["sync"].update(start_s=target_s)
                config["_app_target_frame"] = 0
            key = core.cache_key(config, target_s)
            self._pending_key = key
            cached = self.cache.get(key)
            if cached is not None and (cached / "run_report.json").is_file():
                self.science_run = cached
                self._receive_reconstruction(config)
                return
            self._start_work("reconstruct", config)
        except Exception as error:
            self._error(str(error))

    def _open_run(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择已完成的 run_report.json", "", "JSON (*.json)")
        if not path:
            return
        self._open_run_path(path)

    def _open_run_path(self, path: str) -> None:
        try:
            root = Path(path).parent
            core.validate_run_inputs(root, self._gather())
            if self.reference is not None:
                coordinates.require_match(self.reference, coordinates.identity(root))
            report = json.loads(Path(path).read_text(encoding="utf-8"))
            if report["status"].startswith("FAILED_AT_"):
                raise ValueError("该科学运行失败，不能作为结果显示")
            mapping = json.loads((root / "sync" / "sync.json").read_text(encoding="utf-8"))["frame_mapping"]
            target = min(mapping, key=lambda row: abs(float(row["left_actual_timestamp_s"]) - self.slider.value() / 1000))
            target_id = int(target["output_index"])
            if self.reference_time_s is None and self.reference is None:
                raise ValueError("请先选择静水参考时刻或导入固定参考面")
            config = self._gather()
            config["_app_target_s"] = float(target["left_actual_timestamp_s"])
            config["_app_target_frame"] = target_id
            if self.reference_time_s is not None:
                ref = min(mapping, key=lambda row: abs(float(row["left_actual_timestamp_s"]) - self.reference_time_s))
                config["_app_reference_frame"] = int(ref["output_index"])
            self.science_run = root
            self._viewing_existing_run = True
            self.sync_run = root
            self.calibration_run = root
            sync_info = json.loads((root / "sync" / "sync.json").read_text(encoding="utf-8"))
            self.offset_s = float(sync_info.get("audio_lag_right_minus_left_s", 0.0))
            self.sync_status.setText(f"READY | right-left={self.offset_s:+.6f} s | {sync_info.get('method', 'provided')}")
            cal = core.calibration_matrices(root)
            self.calibration_text.setText(json.dumps(cal, ensure_ascii=False, indent=2))
            wass_info = json.loads((root / "wass" / "run_summary.json").read_text(encoding="utf-8"))
            self.calibration_status.setText("INTRINSICS_COMPUTED | " +
                ("EXTRINSICS_FALLBACK (complete historical bundle)" if wass_info["active_calibration"]["fallback"]
                 else "EXTRINSICS_COMPUTED (official WASS autocalibration)"))
            self._pending_key = core.cache_key(config, config["_app_target_s"])
            self._receive_reconstruction(config)
        except Exception as error:
            self._error(str(error))

    def _receive_reconstruction(self, config: dict) -> None:
        assert self.science_run is not None
        run = self.science_run
        core.validate_run_inputs(run, config)
        target_id = int(config["_app_target_frame"])
        active_id = core.calibration_identity(run)
        if self.reference_time_s is not None:
            if self.reference is None:
                ref_id = int(config["_app_reference_frame"])
                self.reference = core.reference_from_run(run, ref_id)
                self.reference_identity = active_id
                self.reference_run = run
        assert self.reference is not None
        self.result = core.load_result(run, target_id, self.reference, self.reference_identity)
        self._result_selection_ms = self.slider.value()
        self.result_stale = False
        if not self._viewing_existing_run:
            core.write_frame_manifest(run, float(config["_app_target_s"]), self.reference.plane_id, target_id)
        self.cache[self._pending_key] = run
        raw_path = sorted((run / "sync" / "frames" / "cam0").glob("*"))[target_id]
        raw_bgr = cv2.imread(str(raw_path))
        if raw_bgr is None:
            raise ValueError(f"Cannot read extracted scientific input: {raw_path}")
        self.raw_rgb = cv2.cvtColor(raw_bgr, cv2.COLOR_BGR2RGB)
        right_path = sorted((run / "sync" / "frames" / "cam1").glob("*"))[target_id]
        right_bgr = cv2.imread(str(right_path))
        self.preview_right = cv2.cvtColor(right_bgr, cv2.COLOR_BGR2RGB) if right_bgr is not None else None
        self._build_overlay()
        ply = run / "reconstruction" / "ply" / f"{target_id:06d}.ply"
        count = self.point_cloud.show_ply(ply) if ply.is_file() else 0
        report = json.loads((run / "wass" / "run_summary.json").read_text(encoding="utf-8"))
        fallback = bool(report["active_calibration"]["fallback"])
        self.calibration_run = run
        self.sync_run = run
        sync_info = json.loads((run / "sync" / "sync.json").read_text(encoding="utf-8"))
        self.offset_s = float(sync_info.get("audio_lag_right_minus_left_s", 0.0))
        self.sync_status.setText(f"READY | right-left={self.offset_s:+.6f} s | {sync_info.get('method', 'provided')}")
        self.calibration_status.setText("INTRINSICS_COMPUTED | " +
            ("EXTRINSICS_FALLBACK (complete historical bundle)" if fallback
             else "EXTRINSICS_COMPUTED (official WASS autocalibration)"))
        self.calibration_text.setText(json.dumps(core.calibration_matrices(run), ensure_ascii=False, indent=2))
        mapped = int(np.count_nonzero(self.result["source"] != 0))
        self._ready_summary = (f"Frame {target_id} | actual t={self.result['timestamp_s']:.6f}s | "
            f"WASS XYZ={count:,} | official valid map={mapped:,} | reference={self.reference.plane_id} | "
            f"calibration={'EXTRINSICS_FALLBACK' if fallback else 'EXTRINSICS_COMPUTED'} | PASS")
        self._ready_summary += (f"\nCalibration ID: {self.result['calibration_id']} | "
            f"Extrinsics ID: {self.result['extrinsics_id']}\n"
            f"Coordinate Frame ID: {self.result['coordinate_frame_id']} | "
            f"Reference Plane ID: {self.reference.plane_id} | Reference status: MATCHED")
        self.frame_summary.setText(self._ready_summary if self.reference_confirmed else
                                   self._ready_summary + " | REFERENCE_UNCONFIRMED: height hidden")
        if not self.reference_confirmed:
            self.reference_label.setText(f"内部参考面待确认 {self.reference.plane_id} | n={self.reference.normal} "
                                         f"d={self.reference.d} | frame={config.get('_app_reference_frame', '—')} "
                                         f"t≈{self.reference_time_s}s | 未经独立物理验证")
        self._set_measurement_region(self.measurement_region)
        self._display_mode("raw")
        self._update_status()

    def _build_overlay(self) -> None:
        assert self.result is not None and self.raw_rgb is not None
        h = self.result["height"]
        valid = np.isfinite(h) & (self.result["source"] != 0)
        region = presentation.rectangle_mask(h.shape, self.measurement_region)
        raw = cv2.resize(self.raw_rgb, (h.shape[1], h.shape[0]), interpolation=cv2.INTER_LINEAR)
        self.height_available_mask = valid.astype(np.uint8)
        if not valid.any():
            self.overlay_rgb = raw
            return
        lo, hi = np.percentile(h[valid], (2, 98))
        if hi <= lo:
            hi = lo + 1e-9
        scaled = np.clip((h - lo) / (hi - lo) * 255, 0, 255)
        scaled[~valid] = 0
        color = cv2.cvtColor(cv2.applyColorMap(scaled.astype(np.uint8), cv2.COLORMAP_TURBO), cv2.COLOR_BGR2RGB)
        blend = cv2.addWeighted(raw, 0.52, color, 0.48, 0)
        raw[valid & region] = blend[valid & region]
        self.overlay_rgb = raw

    def _display_mode(self, mode="raw") -> None:
        if isinstance(mode, int):
            mode = "raw"
        if self.result is None:
            return
        if mode == "overlay" and not self.reference_confirmed:
            self.frame_summary.setText("官方 XYZ 已载入；请先确认并冻结内部参考面，才能显示相对高度叠加")
            mode = "raw"
        border = self.height_available_mask if self.show_common.isChecked() else None
        if mode == "cloud":
            self.image_canvas.hide()
            self.right_canvas.hide()
            self.point_cloud.show()
        else:
            self.point_cloud.hide()
            self.image_canvas.show()
            self.right_canvas.show()
            self.image_canvas.set_rgb(self.overlay_rgb if mode == "overlay" else self.raw_rgb, border)
            self.right_canvas.set_rgb(self.preview_right)

    def _hover(self, u: int, v: int) -> None:
        if self.result is None:
            self.hover_label.setText(f"Pixel ({u},{v}) | H: N/A | Source: NO_DATA | 当前帧未解算或旧结果 STALE")
            return
        grid_h, grid_w = self.result["height"].shape
        image_h, image_w = self.image_canvas.image_shape
        mu = min(grid_w - 1, int(u * grid_w / image_w))
        mv = min(grid_h - 1, int(v * grid_h / image_h))
        region_in = presentation.point_in_rectangle(mu, mv, (grid_h, grid_w), self.measurement_region)
        region_status = "IN" if region_in else "OUT"
        prefix = (f"Pixel ({u},{v}) | map ({mu},{mv}) | Measurement Region: {region_status} | "
                  "Stereo Common Region: NOT_AVAILABLE (COMMON_REGION_NOT_AVAILABLE) | ")
        if not region_in or not self.reference_confirmed:
            reason = "OUTSIDE_MEASUREMENT_REGION" if not region_in else "REFERENCE_NOT_CONFIRMED"
            self.hover_label.setText(prefix + f"H: N/A | Source: NO_DATA | {reason}")
            return
        item = core.hover(self.result, mu, mv)
        if item["provenance"] == "NO_DATA":
            self.hover_label.setText(prefix + f"H: N/A | t={self.result['timestamp_s']:.6f}s | Source: {item['provenance']}")
        else:
            height_text = (f"{item['height_mm']:.2f} mm" if item["height_mm"] is not None else
                           f"{item['height_native']:.6f} {self.result['units']} (no metric scale)")
            self.hover_label.setText(prefix +
                f"XYZ=({item['X']:.5f}, {item['Y']:.5f}, {item['Z']:.5f}) {self.result['units']} | "
                f"H={height_text} | t={self.result['timestamp_s']:.6f}s | Source: {item['provenance']}")

    def _error(self, message: str) -> None:
        if "REFERENCE_FRAME_MISMATCH" in message:
            self._mark_stale()
            self.frame_summary.setText("REFERENCE_FRAME_MISMATCH | Reference status: FRAME_MISMATCH | H: N/A")
        self._update_status()
        QMessageBox.critical(self, "当前阶段失败", message)

    def _work_failed(self, action: str, message: str) -> None:
        if action == "reconstruct":
            self.reconstruction_failed = True
            self.frame_summary.setText("RECONSTRUCTION_FAILED | " + message.splitlines()[0])
            if "autocalibr" in message.lower():
                self.calibration_status.setText("EXTRINSICS_FAILED | " + message.splitlines()[0])
        elif action == "calibrate":
            self.calibration_status.setText("CALIBRATION_FAILED | " + message.splitlines()[0])
        elif action == "sync":
            self.sync_status.setText("SYNC_FAILED | " + message.splitlines()[0])
        self._error(message)

    def closeEvent(self, event) -> None:
        if ((self.worker is not None and self.worker.isRunning()) or
                (self.export_worker is not None and self.export_worker.isRunning())):
            QMessageBox.warning(self, "科学任务仍在运行", "请等待当前科学工具结束后再关闭程序；结果和日志将完整保留。")
            event.ignore()
            return
        super().closeEvent(event)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("project", nargs="?")
    parser.add_argument("--inspect-run", help="open a completed scientific run_report.json")
    parser.add_argument("--reference-time", type=float)
    parser.add_argument("--target-time", type=float)
    args = parser.parse_args()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    if args.project:
        try:
            window.config = core.read_project(args.project)
            window.project_path = Path(args.project)
            window._populate()
        except Exception as error:
            window._error(str(error))
    if args.inspect_run:
        if args.reference_time is not None:
            window.slider.setValue(int(args.reference_time * 1000))
            window._set_static_reference()
        if args.target_time is not None:
            window.slider.setValue(int(args.target_time * 1000))
        window.tabs.setCurrentIndex(1)
        QTimer.singleShot(0, lambda: window._open_run_path(args.inspect_run))
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
