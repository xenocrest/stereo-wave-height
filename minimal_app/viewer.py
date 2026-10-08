"""Display existing official pixels and PLY with P0 presentation widgets."""
from pathlib import Path
import numpy as np
from PySide6.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget
from app import core
from app.main import ImageCanvas, PointCloudView, MainWindow as ExistingWindow


class ResultView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.summary = QLabel("尚无结果")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.tabs = QTabWidget()
        self.measurement, self.overlay, self.cloud = ImageCanvas(), ImageCanvas(), PointCloudView()
        for name, view in (("Measurement Image", self.measurement),
                           ("3D Point Cloud", self.cloud), ("Overlay", self.overlay)):
            view.setMinimumSize(240, 135)
            self.tabs.addTab(view, name)
        layout.addWidget(self.tabs, 1)
        self.hover_label = QLabel("XYZ/H：N/A")
        self.hover_label.setWordWrap(True)
        layout.addWidget(self.hover_label)
        self.measurement.hovered.connect(self.hover)
        self.overlay.hovered.connect(self.hover)
        self.result = None
        self.measurement_region = None

    def clear(self):
        self.result = None
        self.measurement.set_rgb(None)
        self.overlay.set_rgb(None)
        self.cloud.figure.clear()
        self.cloud.draw_idle()
        self.summary.setText("当前暂停帧尚无结果")
        self.hover_label.setText("XYZ/H：N/A")

    def load(self, directory, metadata):
        self.clear()
        with np.load(Path(directory) / "view.npz", allow_pickle=False) as data:
            result = dict(metadata, xyz=data["xyz"].copy(), height=data["height"].copy(), source=data["source"].copy())
            self.measurement_rgb = data["measurement"].copy()
        if self.measurement_rgb.shape[:2] != result["height"].shape:
            raise ValueError("UNDISTORTED_MEASUREMENT_VIEW raster mismatch")
        self.result = result
        ExistingWindow._build_overlay(self)  # Existing display-only colour mapping.
        self.measurement.set_rgb(self.measurement_rgb)
        self.overlay.set_rgb(self.overlay_rgb)
        count = self.cloud.show_ply(Path(metadata["ply"]))
        self.summary.setText(f"UNDISTORTED_MEASUREMENT_VIEW | frame={result['frame_id']} t={result['timestamp_s']:.9f}s "
            f"| 单位={result['units']} | WASS PLY={count:,}\nReference: {result['reference_plane_id']}\n"
            "颜色和 hover 读取已有官方 grid map；provenance 按原输出显示。")
        self.tabs.setCurrentIndex(0)

    def hover(self, u, v):
        if self.result is None:
            self.hover_label.setText(f"u={u} v={v} | XYZ/H：N/A")
            return
        value = core.hover(self.result, u, v)
        prefix = f"u={u} v={v} | t={self.result['timestamp_s']:.9f}s | {value['provenance']}"
        if value["provenance"] == "NO_DATA":
            self.hover_label.setText(prefix + " | XYZ/H：N/A")
        else:
            height = f"{value['height_mm']:.4f} mm" if value["height_mm"] is not None else f"{value['height_native']:.7f} {self.result['units']}"
            self.hover_label.setText(prefix + f"\nXYZ=({value['X']:.7f}, {value['Y']:.7f}, {value['Z']:.7f}) {self.result['units']} | H={height}")
