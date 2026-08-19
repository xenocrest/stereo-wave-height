"""Dependency-light V0.x desktop shell for the final measurement system."""

from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from input import OpenCVVideoBackend, StereoVideoSource
from .calibration_model import CalibrationPageModel


class StereoWaveHeightApplication:
    """Tkinter shell preserving the final input-to-export module boundaries."""

    title = "Stereo Wave Height Measurement System"

    def __init__(self) -> None:
        self.root: tk.Tk | None = None
        self.left_path: tk.StringVar | None = None
        self.right_path: tk.StringVar | None = None
        self.metadata_text: tk.Text | None = None
        self.calibration_page: ttk.Frame | None = None

    def _choose(self, variable: tk.StringVar) -> None:
        path = filedialog.askopenfilename(title="Select stereo video", filetypes=[("Video files", "*.mp4 *.mov *.avi *.mkv *.m4v"), ("All files", "*.*")])
        if path:
            variable.set(path)

    def _load_metadata(self) -> None:
        assert self.left_path is not None and self.right_path is not None and self.metadata_text is not None
        if not self.left_path.get() or not self.right_path.get():
            messagebox.showerror(self.title, "Select both left and right video files.")
            return
        try:
            source = StereoVideoSource(Path(self.left_path.get()), Path(self.right_path.get()), backend=OpenCVVideoBackend())
        except Exception as error:
            messagebox.showerror(self.title, str(error))
            return
        lines = []
        for role, metadata in (("cam0 / left", source.left), ("cam1 / right", source.right)):
            lines.append(f"{role}: {metadata.path}\n  {metadata.width_px}x{metadata.height_px}, {metadata.frame_count} frames, {metadata.fps:.6g} fps\n  timestamp source: {metadata.timestamp_source}")
        self.metadata_text.delete("1.0", tk.END)
        self.metadata_text.insert(tk.END, "\n".join(lines))

    @staticmethod
    def _placeholder(parent: ttk.Frame, text: str) -> None:
        ttk.Label(parent, text=text, justify=tk.LEFT, padding=16).pack(anchor=tk.NW)

    def _build_input(self, parent: ttk.Frame) -> None:
        assert self.left_path is not None and self.right_path is not None
        for row, (label, variable) in enumerate((("cam0 / left video", self.left_path), ("cam1 / right video", self.right_path))):
            ttk.Label(parent, text=label).grid(row=row, column=0, sticky=tk.W, padx=8, pady=8)
            ttk.Entry(parent, textvariable=variable, width=80).grid(row=row, column=1, sticky=tk.EW, padx=8)
            ttk.Button(parent, text="Browse...", command=lambda value=variable: self._choose(value)).grid(row=row, column=2, padx=8)
        ttk.Button(parent, text="Load metadata", command=self._load_metadata).grid(row=2, column=1, sticky=tk.W, padx=8, pady=8)
        self.metadata_text = tk.Text(parent, height=12, width=100)
        self.metadata_text.grid(row=3, column=0, columnspan=3, sticky=tk.NSEW, padx=8, pady=8)
        parent.columnconfigure(1, weight=1); parent.rowconfigure(3, weight=1)
        ttk.Label(parent, text="Live Stereo Cameras — unavailable until professional hardware and SDK are confirmed", state=tk.DISABLED).grid(row=4, column=0, columnspan=3, sticky=tk.W, padx=8, pady=8)

    @staticmethod
    def _build_calibration(parent: ttk.Frame, model: CalibrationPageModel | None = None) -> None:
        """Render preflight/quality state; all metrics are computed outside GUI."""
        current = model or CalibrationPageModel.pending()
        ttk.Label(parent, text=current.target_text, padding=12).pack(anchor=tk.W)
        ttk.Separator(parent).pack(fill=tk.X, padx=12)
        for text in (current.cam0_text, current.cam1_text, current.dataset_text, current.result_text):
            ttk.Label(parent, text=text, padding=(12, 8), justify=tk.LEFT).pack(anchor=tk.W)
        ttk.Label(parent, text=f"Experiment status: {current.experiment_status}", padding=12).pack(anchor=tk.W)

    def show_calibration_model(self, model: CalibrationPageModel) -> None:
        """Refresh the page from shared calibration results without recomputing them."""
        if self.calibration_page is None:
            raise RuntimeError("build the application before showing calibration results")
        for child in self.calibration_page.winfo_children():
            child.destroy()
        self._build_calibration(self.calibration_page, model)

    def build(self) -> tk.Tk:
        root = tk.Tk(); root.title(self.title); root.geometry("1100x720")
        self.root = root; self.left_path = tk.StringVar(root); self.right_path = tk.StringVar(root)
        notebook = ttk.Notebook(root); notebook.pack(fill=tk.BOTH, expand=True)
        input_page = ttk.Frame(notebook); notebook.add(input_page, text="Input"); self._build_input(input_page)
        calibration_page = ttk.Frame(notebook); notebook.add(calibration_page, text="Calibration")
        self.calibration_page = calibration_page
        self._build_calibration(calibration_page)
        pages = {
            "Synchronization": "Enter shared flash events, fit offset/drift, pair frames, and review diagnostics.",
            "Reconstruction": "WASS prepare / match / autocalibrate / stereo / grid stage orchestration placeholder.",
            "3D Surface": "Regular 3-D surface visualization placeholder; no OpenGL dependency in V0.x.",
            "Height Map": "H(x,y,t), valid mask, and raw-observation-support overlay placeholder.",
            "Point Wave Height": "Select a physical (x,y) point and display H(t) placeholder.",
            "QA / Export": "Point counts, support, coverage, extrema, provenance, and export placeholder.",
        }
        for name, description in pages.items():
            page = ttk.Frame(notebook); notebook.add(page, text=name); self._placeholder(page, description)
        return root

    def run(self) -> None:
        """Build and enter the desktop event loop."""
        (self.root or self.build()).mainloop()
