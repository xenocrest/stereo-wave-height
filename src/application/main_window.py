"""Runnable offline Stage-1 desktop demo using the existing Tkinter stack."""
from __future__ import annotations

from pathlib import Path
import queue, threading, time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any
from PIL import Image, ImageTk
import yaml

from .backend_runner import FrozenBackendRunner
from .session import MeasurementRecord, MeasurementSession
from .video_tools import VideoMetadata, extract_frame, probe_video


class StereoWaveHeightApplication:
    title = "Stereo Wave Height — Offline Demo Stage 1"

    def __init__(self, repository: Path | None = None) -> None:
        self.repository = (repository or Path(__file__).resolve().parents[2]).resolve()
        self.experiment = self.repository / "experiments/real_video/HomeTank_004"
        self.ffmpeg = Path("D:/FormatFactory/ffmpeg.exe")
        self.session = MeasurementSession(Path("D:/stereo-wave-height-runs/gui_sessions"))
        self.runner = FrozenBackendRunner(self.repository, self.experiment / "single_frame_dense_smoke_config.yaml")
        self.root: tk.Tk | None = None; self.variables: dict[str, tk.StringVar] = {}
        self.metadata: dict[str, VideoMetadata] = {}; self.current_time = 0.0
        self.playing = False; self.backend_running = False; self._photo: ImageTk.PhotoImage | None = None
        self.backend_started_at: float | None = None
        self._worker_messages: queue.Queue[tuple[str, Any]] = queue.Queue()

    def _var(self, key: str, value: str = "") -> tk.StringVar:
        variable = tk.StringVar(self.root, value=value); self.variables[key] = variable; return variable

    def _log(self, message: str) -> None:
        self.session.log(message)
        if hasattr(self, "log_text"): self.log_text.insert(tk.END, message + "\n"); self.log_text.see(tk.END)

    def _choose_video(self, key: str) -> None:
        selected = filedialog.askopenfilename(title="选择离线视频", filetypes=[("Video", "*.mp4 *.mov *.avi *.mkv *.m4v")])
        if not selected: return
        self.variables[key].set(selected)
        try:
            meta = probe_video(Path(selected), self.ffmpeg); self.metadata[key] = meta
            self.variables[key + "_meta"].set(f"{meta.width}×{meta.height} | {meta.fps:.3f} fps | {meta.duration_sec:.3f} s")
            if key == "right_measurement": self.timeline.configure(to=meta.duration_sec); self._show_video_frame(0.0)
            self._log(f"selected {key}: {selected}")
        except Exception as error: messagebox.showerror(self.title, str(error))

    def _show_pil(self, image: Image.Image) -> None:
        image.thumbnail((760, 440), Image.Resampling.LANCZOS); self._photo = ImageTk.PhotoImage(image)
        self.image_label.configure(image=self._photo, text="")

    def _show_video_frame(self, time_sec: float) -> None:
        path = self.variables["right_measurement"].get()
        if path:
            try: self._show_pil(extract_frame(Path(path), time_sec, self.ffmpeg))
            except Exception as error: self._log(f"preview error: {error}")

    def _preview_calibration(self, key: str) -> None:
        path = self.variables[key].get()
        if not path: messagebox.showwarning(self.title, "请先选择标定视频。"); return
        try: self._show_pil(extract_frame(Path(path), 0.0, self.ffmpeg)); self._log(f"previewed {key}")
        except Exception as error: messagebox.showerror(self.title, str(error))

    def _load_calibration(self) -> None:
        path_text = filedialog.askopenfilename(title="加载标定结果", initialdir=self.experiment, filetypes=[("YAML", "*.yaml *.yml")])
        if not path_text: return
        try:
            data = yaml.safe_load(Path(path_text).read_text(encoding="utf-8"))
            for prefix, node in (("left", data["mono_cam0"]), ("right", data["mono_cam1"])):
                k=node["K"]
                for field,value in {"fx":k[0][0],"fy":k[1][1],"cx":k[0][2],"cy":k[1][2],"D":node["D"]}.items(): self.variables[f"{prefix}_{field}"].set(str(value))
            stereo=data["stereo"]
            qa=(f"R = {stereo['R_right_from_left']}\nT = {stereo['T_right_from_left_m']} m\n"
                f"baseline = {stereo['baseline_m']:.9f} m\nstatus = {data['status']}\n"
                f"stereo RMS = {stereo['rms_px']:.6f} px\nepipolar RMS = {stereo['symmetric_epipolar_rms_px']:.6f} px")
            self.stereo_text.configure(state=tk.NORMAL); self.stereo_text.delete("1.0",tk.END); self.stereo_text.insert(tk.END,qa); self.stereo_text.configure(state=tk.DISABLED)
            self.variables["calibration_path"].set(path_text); self._log(f"loaded calibration: {path_text}")
        except Exception as error: messagebox.showerror(self.title,f"标定文件读取失败：{error}")

    def _play(self) -> None:
        if not self.variables["right_measurement"].get(): messagebox.showwarning(self.title,"请先选择 RIGHT 测量视频。"); return
        self.playing=True; self._log("play")
    def _pause(self) -> None: self.playing=False; self._log(f"pause at {self.current_time:.3f}s")
    def _seek(self,value:str) -> None:
        self.current_time=float(value); self.variables["time"].set(f"{self.current_time:.3f} s")
        if not self.playing: self._show_video_frame(self.current_time)
    def _tick(self) -> None:
        if self.playing:
            self.current_time=min(self.current_time+0.2,float(self.timeline.cget("to"))); self.timeline.set(self.current_time)
            self.variables["time"].set(f"{self.current_time:.3f} s"); self._show_video_frame(self.current_time)
            if self.current_time >= float(self.timeline.cget("to")): self.playing=False
        if self.backend_running and self.backend_started_at is not None:
            self.variables["run_status"].set(f"正在执行单帧三维解算… {time.perf_counter()-self.backend_started_at:.1f} s")
        self._poll_worker(); self.root.after(200,self._tick)

    def _solve(self) -> None:
        if self.backend_running: messagebox.showwarning(self.title,"当前单帧解算仍在运行。"); return
        left,right=self.variables["left_measurement"].get(),self.variables["right_measurement"].get()
        if not left or not right: messagebox.showerror(self.title,"必须选择 LEFT 和 RIGHT 测量视频。"); return
        if not self.variables["calibration_path"].get(): messagebox.showerror(self.title,"必须先加载标定结果。"); return
        self._pause(); name,output=self.session.allocate(self.current_time); self.backend_running=True; self.backend_started_at=time.perf_counter(); self.solve_button.configure(state=tk.DISABLED)
        self.variables["run_status"].set("正在执行单帧三维解算…"); self._log(f"backend start {name} target={self.current_time:.6f}s")
        def work() -> None:
            started=time.perf_counter()
            try:
                record=self.runner.run(Path(left),Path(right),self.current_time,output,self.session.log_path)
                record=MeasurementRecord(**{**record.__dict__,"display_name":name}); self._worker_messages.put(("success",(record,time.perf_counter()-started)))
            except Exception as error: self._worker_messages.put(("error",str(error)))
        threading.Thread(target=work,daemon=True).start()

    def _poll_worker(self) -> None:
        try: kind,payload=self._worker_messages.get_nowait()
        except queue.Empty: return
        self.backend_running=False; self.backend_started_at=None; self.solve_button.configure(state=tk.NORMAL)
        if kind=="error": self.variables["run_status"].set("解算失败"); self._log(f"backend failed: {payload}"); messagebox.showerror(self.title,payload); return
        record,elapsed=payload; self.session.add(record); self.history.insert(tk.END,record.display_name)
        self.variables["run_status"].set(f"完成（{elapsed:.1f} s）"); self._log(f"backend completed {record.display_name}"); self._show_record(record)

    @staticmethod
    def _summary(record: MeasurementRecord) -> str:
        s=record.summary_metadata; d=s.get("dense_height",{}); h=s.get("height_statistics",{}); roi=d.get("roi_pixel_count",0) or 0
        pct=lambda v:f"{100*v/roi:.2f}%" if roi else "N/A"
        return (f"Target: {s.get('requested_time_s')} s\nActual L/R: {s.get('left_timestamp_s')} / {s.get('right_timestamp_s')} s\nSync residual: {s.get('pair_time_error_ms')} ms\n"
                f"Status: {s.get('status')}\nXYZ: {s.get('xyz_point_count')}\nROI: {roi}\nOBSERVED: {d.get('observed_count')} ({pct(d.get('observed_count',0))})\n"
                f"ESTIMATED: {d.get('estimated_count')} ({pct(d.get('estimated_count',0))})\nUNSUPPORTED: {d.get('unsupported_count')} ({pct(d.get('unsupported_count',0))})\n"
                f"H min/max/mean: {h.get('minimum')} / {h.get('maximum')} / {h.get('mean')} m\nWASS: {s.get('wass_seconds')} s | Dense: {d.get('generation_time_sec')} s | Total: {s.get('total_seconds')} s")

    def _show_record(self,record:MeasurementRecord) -> None:
        self.active_record=record; self._show_mode(); self.summary_text.configure(state=tk.NORMAL); self.summary_text.delete("1.0",tk.END); self.summary_text.insert(tk.END,self._summary(record)); self.summary_text.configure(state=tk.DISABLED)
    def _show_mode(self) -> None:
        record=getattr(self,"active_record",None)
        if not record:return
        path={"原始画面":record.selected_frame_path,"高度图":record.dense_height_path,"状态图":record.status_map_path}[self.variables["mode"].get()]
        try:self._show_pil(Image.open(path).convert("RGB"))
        except Exception as error:messagebox.showerror(self.title,f"无法加载结果图：{error}")
    def _history_selected(self,_event:object) -> None:
        selection=self.history.curselection()
        if selection:self._show_record(self.session.records[selection[0]])

    def _build_camera_fields(self,parent:ttk.Frame) -> None:
        for column,(prefix,title) in enumerate((("left","LEFT / cam0"),("right","RIGHT / cam1"))):
            box=ttk.LabelFrame(parent,text=title); box.grid(row=0,column=column,sticky="nsew",padx=4)
            for row,field in enumerate(("model","fx","fy","cx","cy","D")):
                default=("iQOO Neo5S" if prefix=="left" else "iQOO Z10 Turbo+") if field=="model" else ""
                ttk.Label(box,text=field).grid(row=row,column=0,sticky="w"); ttk.Entry(box,textvariable=self._var(f"{prefix}_{field}",default),width=34).grid(row=row,column=1,sticky="ew")
        stereo=ttk.LabelFrame(parent,text="Stereo / QA"); stereo.grid(row=0,column=2,sticky="nsew",padx=4); self.stereo_text=tk.Text(stereo,width=48,height=8); self.stereo_text.pack(fill="both",expand=True); self.stereo_text.configure(state=tk.DISABLED)
        ttk.Entry(parent,textvariable=self._var("calibration_path"),width=85).grid(row=1,column=0,columnspan=2,sticky="ew",pady=3); ttk.Button(parent,text="加载现有 calibration",command=self._load_calibration).grid(row=1,column=2,sticky="w")
    def _video_row(self,parent:ttk.Frame,row:int,key:str,label:str,preview:bool=False) -> None:
        ttk.Label(parent,text=label).grid(row=row,column=0,sticky="w"); ttk.Entry(parent,textvariable=self._var(key),width=72).grid(row=row,column=1,sticky="ew"); ttk.Button(parent,text="选择",command=lambda:self._choose_video(key)).grid(row=row,column=2)
        if preview:ttk.Button(parent,text="预览",command=lambda:self._preview_calibration(key)).grid(row=row,column=3)
        ttk.Label(parent,textvariable=self._var(key+"_meta"),foreground="#555").grid(row=row+1,column=1,sticky="w")

    def build(self) -> tk.Tk:
        root=tk.Tk(); root.title(self.title); root.geometry("1320x900"); self.root=root
        top=ttk.LabelFrame(root,text="Camera / Calibration"); top.pack(fill="x",padx=8,pady=5); self._build_camera_fields(top)
        videos=ttk.Frame(root); videos.pack(fill="x",padx=8); self._video_row(videos,0,"left_calibration","LEFT calibration",True); self._video_row(videos,2,"right_calibration","RIGHT calibration",True); self._video_row(videos,4,"left_measurement","LEFT measurement"); self._video_row(videos,6,"right_measurement","RIGHT measurement"); ttk.Button(videos,text="运行双目标定（Stage 2）",state=tk.DISABLED).grid(row=0,column=4,padx=6)
        center=ttk.Panedwindow(root,orient=tk.HORIZONTAL); center.pack(fill="both",expand=True,padx=8,pady=5); image_box=ttk.LabelFrame(center,text="Main View: RIGHT / canonical cam1"); summary_box=ttk.LabelFrame(center,text="当前状态 / 解算摘要"); center.add(image_box,weight=3); center.add(summary_box,weight=1)
        self.image_label=ttk.Label(image_box,text="请选择 RIGHT 测量视频",anchor="center"); self.image_label.pack(fill="both",expand=True); modes=ttk.Frame(image_box); modes.pack(fill="x"); self._var("mode","原始画面")
        for mode in ("原始画面","高度图","状态图"):ttk.Radiobutton(modes,text=mode,value=mode,variable=self.variables["mode"],command=self._show_mode).pack(side="left")
        self.summary_text=tk.Text(summary_box,width=42,height=22); self.summary_text.pack(fill="both",expand=True); self.summary_text.configure(state=tk.DISABLED)
        controls=ttk.Frame(root); controls.pack(fill="x",padx=8); ttk.Button(controls,text="Play",command=self._play).pack(side="left"); ttk.Button(controls,text="Pause",command=self._pause).pack(side="left"); self.timeline=ttk.Scale(controls,from_=0,to=1,command=self._seek); self.timeline.pack(side="left",fill="x",expand=True,padx=8); ttk.Label(controls,textvariable=self._var("time","0.000 s"),width=12).pack(side="left"); self.solve_button=ttk.Button(controls,text="解算当前帧",command=self._solve); self.solve_button.pack(side="left",padx=8); ttk.Label(controls,textvariable=self._var("run_status","就绪")).pack(side="left")
        bottom=ttk.Panedwindow(root,orient=tk.HORIZONTAL); bottom.pack(fill="x",padx=8,pady=5); history_box=ttk.LabelFrame(bottom,text="本次测量记录"); log_box=ttk.LabelFrame(bottom,text="Session log"); bottom.add(history_box,weight=1); bottom.add(log_box,weight=3); self.history=tk.Listbox(history_box,height=5); self.history.pack(fill="both",expand=True); self.history.bind("<<ListboxSelect>>",self._history_selected)
        for record in self.session.records:self.history.insert(tk.END,record.display_name)
        self.log_text=tk.Text(log_box,height=5); self.log_text.pack(fill="both",expand=True); self._log(f"session directory: {self.session.directory}"); root.after(200,self._tick); return root
    def run(self) -> None:(self.root or self.build()).mainloop()
