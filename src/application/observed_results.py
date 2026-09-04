"""Read-only review of real WASS runs; never a measurement fallback."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk


def load_review(path: Path) -> dict:
    """Validate a self-contained result bundle and its preview identities."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "wass_observation_review_v1" or data.get("height_available") is not False:
        raise ValueError("Expected observation-only review, not validated water heights")
    if not data.get("frames"):
        raise ValueError("No recorded frames")
    for frame in data["frames"]:
        if not 0 <= frame["raw_roi_support_ratio"] <= 1:
            raise ValueError("Invalid observed support ratio")
        for key in ("original", "support"):
            image = (path.parent / frame[key]).resolve()
            if not image.is_relative_to(path.parent.resolve()):
                raise ValueError("Review image outside bundle")
            if hashlib.sha256(image.read_bytes()).hexdigest() != frame[key + "_sha256"]:
                raise ValueError("Review image hash mismatch")
    return data


class ObservedResultsPanel(ttk.Frame):
    """Show frozen images and exact ROI statistics without touching the session."""

    def __init__(self, parent: tk.Misc, manifest: Path) -> None:
        super().__init__(parent)
        self.manifest = manifest
        self.photo = None
        self.mode = tk.StringVar(self, "support")
        self.summary = tk.StringVar(self)
        self.current_index = 0
        ttk.Label(self, text="最新实测结果 · 只读回放（不是当前视频即时解算）",
                  font=("TkDefaultFont", 12, "bold")).pack(anchor="w", padx=12, pady=8)
        ttk.Label(self, text="黄色：预先固定的诊断 ROI；绿色：实际 WASS 点投影（含 ROI 外点）。"
                  "绿色不是高度或已确认水面。未观测区域不补色。", wraplength=1100).pack(anchor="w", padx=12)
        try:
            self.data = load_review(manifest)
        except (OSError, ValueError, KeyError, TypeError) as error:
            ttk.Label(self, text=f"实测结果无法加载：{type(error).__name__}: {error}", wraplength=1000).pack(padx=12, pady=20)
            self.data = None
            return
        ttk.Label(self, text=f"{self.data['experiment']}：10 帧中 10 帧生成 XYZ；固定 ROI "
                  f"{self.data['fixed_roi_pixels']:,} 像素，占全图 {100*self.data['fixed_roi_full_image_ratio']:.2f}%。\n"
                  "高度尚不可用：观测稀疏，水面来源与几何仍待验证；本页不输出波高。",
                  foreground="#963b00", wraplength=1100).pack(anchor="w", padx=12, pady=6)
        controls = ttk.Frame(self); controls.pack(fill="x", padx=12)
        self.selector = ttk.Combobox(controls, state="readonly", width=48, values=[
            f"帧 {f['frame_id']} · LEFT 目标时刻 {f['left_target_s']} s" for f in self.data["frames"]])
        self.selector.pack(side="left")
        self.selector.bind("<<ComboboxSelected>>", lambda _: self.show_frame(self.selector.current()))
        ttk.Button(controls, text="上一帧", command=lambda: self.show_frame((self.current_index-1) % len(self.data['frames']))).pack(side="left", padx=4)
        ttk.Button(controls, text="下一帧", command=lambda: self.show_frame((self.current_index+1) % len(self.data['frames']))).pack(side="left")
        for text, value in (("原始 RIGHT 画面", "original"), ("真实重建点与 ROI", "support")):
            ttk.Radiobutton(controls, text=text, value=value, variable=self.mode,
                            command=lambda: self.show_frame(self.current_index)).pack(side="left", padx=6)
        self.image_label = ttk.Label(self, anchor="center"); self.image_label.pack(fill="both", expand=True, padx=12, pady=6)
        ttk.Label(self, textvariable=self.summary, wraplength=1150, justify="left").pack(fill="x", padx=12, pady=8)
        self.show_frame(0)

    def show_frame(self, index: int) -> None:
        """Render exactly the saved frame, without changing reconstruction inputs."""
        frame = self.data["frames"][index]
        self.current_index = index; self.selector.current(index)
        with Image.open(self.manifest.parent / frame[self.mode.get()]) as source:
            image = source.convert("RGB")
            image.thumbnail((960, 340), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(image, master=self)
        self.image_label.configure(image=self.photo)
        pts = frame["decoded_pts_s"]
        self.summary.set(f"帧 {frame['frame_id']} | 解码时刻 LEFT {pts[0]:.6f} s / RIGHT {pts[1]:.6f} s\n"
                         f"整帧 XYZ：{frame['final_xyz_count']:,} 点（不等于水面点数） | "
                         f"固定 ROI 观测支持率：{100*frame['raw_roi_support_ratio']:.4f}% | "
                         f"WASS stereo：{frame['stereo_seconds']:.2f} s\n"
                         "处理策略 alpha=-1；原 K/D/R/T 未改。ROI 由诊断预先固定、未经用户确认；"
                         "预览已缩小，支持率按原生 3840×2160 像素计算。仅展示已有结果，不使用槽底反演。")
