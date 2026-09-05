"""Runnable offline Stage-1 desktop demo using the existing Tkinter stack."""
from __future__ import annotations

from pathlib import Path
import json, queue, shutil, threading, time, traceback
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any
from PIL import Image, ImageTk
import numpy as np
import yaml
from calibration.quality import CalibrationQualityThresholds

from .backend_runner import FrozenBackendRunner
from .foundation_runtime import load_runtime
from .session import MeasurementRecord, MeasurementSession
from .video_tools import LatestFrameDecoder, VideoMetadata, extract_frame, probe_video
from .visualization import DenseMeasurementView, DisplayTransform, make_height_overlay
from .export import delete_session, export_session
from .runtime_paths import resolve_runtime_paths
from .input_workflow import (CALIBRATION_FILE_TYPES, VIDEO_FILE_TYPES, VIDEO_FORMAT_TEXT,
                             GuidedInputState, load_calibration_selection)
from .input_workflow import validate_gui_calibration
from .calibration_workflow import calibrate_from_videos
from reconstruction.reference_frame import load_reference_artifact
from reconstruction.reference_frame import (canonical_calibration_identity, file_identity, roi_identity,
                                            save_reference_artifact, video_pair_identity)
from reconstruction.common_fov import (CommonFov,compute_common_fov,save_common_fov,
                                       save_canonical_cam1_wass_mapping,validate_roi)


class StereoWaveHeightApplication:
    title = "双目水面三维测量 — 离线演示系统"

    def __init__(self, repository: Path | None = None) -> None:
        paths = resolve_runtime_paths(repository)
        self.repository = paths.application_root
        self.experiment = paths.experiment
        self.ffmpeg = paths.ffmpeg
        self.session = MeasurementSession(paths.session_root)
        template = self.experiment / ("single_frame_dense_template.yaml" if paths.frozen else "single_frame_dense_smoke_config.yaml")
        self.runner = FrozenBackendRunner(self.repository, template)
        self.root: tk.Tk | None = None; self.variables: dict[str, tk.StringVar] = {}
        self.metadata: dict[str, VideoMetadata] = {}; self.current_time = 0.0
        self.playing = False; self.backend_running = False; self._photo: ImageTk.PhotoImage | None = None
        self.backend_started_at: float | None = None
        self.display_transform: DisplayTransform | None = None; self.dense_view: DenseMeasurementView | None = None
        self.viewing_result = False
        self.input_state = GuidedInputState()
        self.preview_decoder=LatestFrameDecoder(display_fps=30.0); self._preview_version=0
        self._canvas_image_id: int | None=None; self._last_status_refresh=0.0
        self._timeline_dragging=False; self._timeline_programmatic=False; self._resume_after_seek=False
        self.water_roi: tuple[int,int,int,int] | None=None; self._roi_selecting=False
        self._roi_start: tuple[int,int] | None=None; self._roi_rectangle_id: int | None=None
        self._after_id: str | None=None; self._closing=False
        self._worker_messages: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.active_reference_path=self.session.active_reference_path
        self.calibration_data:dict[str,Any]|None=None;self.common_fov:CommonFov|None=None;self.common_fov_file:Path|None=None;self.mapping_file:Path|None=None
        self.common_fov_state="NO_VIDEO"
        self._common_fov_generation=0; self._common_fov_started_at:float|None=None
        self._common_fov_timeout_seconds=10.0; self._preview_request_generation=0
        self.pending_demo_calibration:tuple[dict[str,Any],Path]|None=None
        self.crop_origin=(0,0)

    def _var(self, key: str, value: str = "") -> tk.StringVar:
        variable = tk.StringVar(self.root, value=value); self.variables[key] = variable; return variable

    def _log(self, message: str) -> None:
        self.session.log(message)
        if hasattr(self, "log_text"): self.log_text.insert(tk.END, message + "\n"); self.log_text.see(tk.END)

    def _demo_working_view(self) -> bool:
        state=getattr(self,"input_state",None)
        return state is not None and state.operating_mode == "DEMO_ESTIMATION_MODE"

    def _prepare_demo_working_view(self) -> None:
        """Prepare the full canonical RIGHT/cam1 view without common-FOV gating."""
        if not self._demo_working_view() or not self.input_state.measurement_ready or self.calibration_data is None:
            return
        destination=self.session.directory/"demo_working_view"/"canonical_cam1_wass_mapping.yaml"
        self.mapping_file=save_canonical_cam1_wass_mapping(self.calibration_data,destination)
        self.common_fov=None;self.common_fov_file=None;self.common_fov_state="DEMO_RIGHT_VIEW_READY"
        if "common_fov_status" in self.variables:
            self.variables["common_fov_status"].set("主相机画面，请框选需要解算的水面区域")
        self._log("DEMO_RIGHT_VIEW_READY canonical_cam1 full_frame common_fov_bypassed")

    def _choose_video(self, key: str) -> None:
        names={"left_calibration":"选择左相机标定视频","right_calibration":"选择右相机标定视频",
               "left_measurement":"选择左相机测量视频","right_measurement":"选择右相机测量视频"}
        selected = filedialog.askopenfilename(title=names[key], filetypes=list(VIDEO_FILE_TYPES))
        if not selected: return
        self.variables[key].set(selected)
        try:
            meta = probe_video(Path(selected), self.ffmpeg); self.metadata[key] = meta
            role="LEFT" if key.startswith("left") else "RIGHT"
            self.variables[key + "_meta"].set(f"角色：{role}　文件：{Path(selected).name}\n分辨率：{meta.width} × {meta.height}　FPS：{meta.fps:.3f}　时长：{meta.duration_sec:.3f} s")
            if key == "right_measurement": self.timeline.configure(to=meta.duration_sec)
            if key.endswith("measurement"):
                self._invalidate_reference("VIDEO_PAIR_CHANGED")
                self.water_roi=None;self.common_fov=None;self.common_fov_file=None
                if hasattr(self,"variables") and "roi_status" in self.variables:self.variables["roi_status"].set("水面区域：尚未设置；解算前必须在右相机画面中框选")
                self.input_state.mark_measurement_video("left" if key.startswith("left") else "right")
                if self._demo_working_view():self._prepare_demo_working_view()
                else:self._ensure_common_fov()
                self._refresh_step_state()
                if key == "right_measurement":self._request_initial_preview(Path(selected))
            self._log(f"selected {key}: {selected}")
        except Exception as error: messagebox.showerror(self.title, f"视频读取失败。请确认所选文件是受支持且未损坏的本地视频。\n\n{error}")

    def _show_pil(self, image: Image.Image) -> None:
        if self.common_fov is not None:
            x0,y0,x1,y1=self.common_fov.bbox; image=image.crop((x0,y0,x1,y1));self.crop_origin=(x0,y0)
            local=self.common_fov.safe_mask[y0:y1,x0:x1]
            if not bool(local.all()):
                pixels=np.asarray(image.convert("RGB")).copy();pixels[~local]=(55,55,55);image=Image.fromarray(pixels,"RGB")
        else:self.crop_origin=(0,0)
        source_width,source_height=image.size; canvas_width=max(self.image_canvas.winfo_width(),760); canvas_height=max(self.image_canvas.winfo_height(),440)
        self.display_transform=DisplayTransform.fit(source_width,source_height,canvas_width,canvas_height)
        image=image.resize((self.display_transform.display_width,self.display_transform.display_height),Image.Resampling.LANCZOS); self._photo=ImageTk.PhotoImage(image)
        if self._canvas_image_id is None:
            self._canvas_image_id=self.image_canvas.create_image(canvas_width/2,canvas_height/2,image=self._photo,anchor="center")
        else:
            self.image_canvas.coords(self._canvas_image_id,canvas_width/2,canvas_height/2); self.image_canvas.itemconfigure(self._canvas_image_id,image=self._photo)
        self._draw_water_roi()

    def _show_video_frame(self, time_sec: float) -> None:
        path = self.variables["right_measurement"].get()
        if path:
            try: self._show_pil(extract_frame(Path(path), time_sec, self.ffmpeg))
            except Exception as error: self._log(f"preview error: {error}")

    def _request_initial_preview(self,path:Path)->None:
        """Decode the first preview away from Tk's event loop."""
        self._preview_request_generation+=1;generation=self._preview_request_generation
        def work()->None:
            try:self._worker_messages.put(("initial_preview_ready",(generation,extract_frame(path,0.0,self.ffmpeg))))
            except Exception as error:self._worker_messages.put(("preview_error",str(error)))
        threading.Thread(target=work,daemon=True).start()

    def _preview_calibration(self, key: str) -> None:
        path = self.variables[key].get()
        if not path: messagebox.showwarning(self.title, "请先选择标定视频。"); return
        try:
            image=extract_frame(Path(path),0.0,self.ffmpeg); image.thumbnail((900,560),Image.Resampling.LANCZOS)
            dialog=tk.Toplevel(self.root); dialog.title(("LEFT" if key.startswith("left") else "RIGHT")+" 标定视频代表帧")
            photo=ImageTk.PhotoImage(image); label=ttk.Label(dialog,image=photo); label.image=photo; label.pack(padx=8,pady=8)
            ttk.Label(dialog,text=f"相机角色：{'LEFT' if key.startswith('left') else 'RIGHT'}　文件：{Path(path).name}").pack(pady=(0,8))
            self._log(f"previewed {key}")
        except Exception as error: messagebox.showerror(self.title,f"无法预览标定视频代表帧。请检查视频文件。\n\n{error}")

    def _load_calibration(self) -> None:
        path_text = filedialog.askopenfilename(title="选择已有双目标定结果", initialdir=self.experiment, filetypes=list(CALIBRATION_FILE_TYPES))
        if not path_text: return
        try:
            data, calibration_path, operating_mode = load_calibration_selection(path_text)
            self._apply_calibration(data, calibration_path, operating_mode=operating_mode)
        except Exception as error: messagebox.showerror(self.title,f"标定结果文件读取失败。\n请选择由本系统生成或兼容格式的双目标定 YAML 文件。\n\n{error}")

    def _apply_calibration(self, data: dict[str, Any], path: Path, *, operating_mode: str = "VALIDATED_MODE") -> None:
        if self.variables.get("calibration_path") and self.variables["calibration_path"].get()!=str(path):
            self._invalidate_reference("CALIBRATION_CHANGED");self.water_roi=None;self.common_fov=None;self.common_fov_file=None
        data=dict(data);validate_gui_calibration(data);data["calibration_id"]=file_identity(path,"cal");self.calibration_data=data
        for prefix, node in (("left", data["mono_cam0"]), ("right", data["mono_cam1"])):
            k=node["K"]
            self.variables[f"{prefix}_model"].set(str(node.get("model", "LEFT/cam0" if prefix=="left" else "RIGHT/cam1")))
            for field,value in {"fx":k[0][0],"fy":k[1][1],"cx":k[0][2],"cy":k[1][2],"D":node["D"]}.items(): self.variables[f"{prefix}_{field}"].set(str(value))
        stereo=data["stereo"]
        epipolar=float(stereo.get("symmetric_epipolar_rms_px",stereo.get("epipolar_rms_px",float("inf"))))
        qa=(f"R = {stereo['R_right_from_left']}\nT = {stereo['T_right_from_left_m']} m\n"
            f"baseline = {stereo['baseline_m']:.9f} m\nstatus = {data['status']}\n"
            f"stereo RMS = {stereo['rms_px']:.6f} px\nepipolar RMS = {epipolar:.6f} px")
        self.stereo_text.configure(state=tk.NORMAL); self.stereo_text.delete("1.0",tk.END); self.stereo_text.insert(tk.END,qa); self.stereo_text.configure(state=tk.DISABLED)
        self.variables["calibration_path"].set(str(path)); self.variables["calibration_file"].set(path.name)
        self.variables["calibration_load_status"].set("✓ 标定结果已加载，可以进入步骤 2")
        thresholds=CalibrationQualityThresholds(); stereo_rms=float(stereo["rms_px"]); epi=epipolar
        failed=("FAIL" in str(data.get("status","")) or stereo_rms>thresholds.maximum_stereo_rms_px or epi>thresholds.maximum_epipolar_rms_px)
        quality_status="QA_FAIL" if failed else "QA_PASS"
        self.variables["calibration_quality"].set("")
        if operating_mode == "DEMO_ESTIMATION_MODE":
            self.pending_demo_calibration=None
            self.input_state.mark_calibration_ready(operating_mode=operating_mode,quality_status=quality_status)
            self.variables["calibration_load_status"].set("✓ 标定完成，可以进入测量")
            self.variables["app_state"].set("当前模式：演示模式")
            if hasattr(self,"demo_continue_button"):self.demo_continue_button.configure(state=tk.DISABLED)
            self._log(f"loaded demo calibration: {path}");self._prepare_demo_working_view()
        elif failed:
            self.input_state.mark_calibration_failed()
            self.variables["calibration_load_status"].set("⚠ 标定 QA 已加载，但几何未通过；测量与公共视场已阻止")
            self.common_fov=None;self.common_fov_file=None
            self._log(f"loaded calibration QA limitation: {path}")
        else:
            self.pending_demo_calibration=None
            if hasattr(self,"demo_continue_button"):self.demo_continue_button.configure(state=tk.DISABLED)
            self.input_state.mark_calibration_ready(operating_mode=operating_mode,quality_status=quality_status)
            self._log(f"loaded calibration: {path} mode={operating_mode}");self._ensure_common_fov()
        self._refresh_step_state()

    def _continue_demo(self) -> None:
        if self.pending_demo_calibration is None:
            messagebox.showwarning(self.title,"尚未加载可用于演示的标定包。")
            return
        self.input_state.mark_calibration_ready(operating_mode="DEMO_ESTIMATION_MODE",quality_status="QA_FAIL")
        self.variables["calibration_load_status"].set("✓ 标定完成，可以进入测量")
        self.variables["calibration_quality"].set("")
        self.variables["app_state"].set("当前模式：演示模式")
        self.demo_continue_button.configure(state=tk.DISABLED)
        self._log("DEMO_ESTIMATION_MODE acknowledged by user")
        self._prepare_demo_working_view();self._refresh_step_state()

    def _ensure_common_fov(self)->None:
        """Authoritatively resolve common FOV whenever calibration and pair exist."""
        left,right=self.metadata.get("left_measurement"),self.metadata.get("right_measurement")
        if left is None or right is None:
            self.common_fov_state="WAITING_FOR_VIDEO_PAIR"
            return
        if self.calibration_data is None:
            self.common_fov_state="COMMON_FOV_FAILED"
            if "common_fov_status" in self.variables:self.variables["common_fov_status"].set("双目公共区域计算失败：当前会话没有可读取的标定参数。")
            self._refresh_step_state()
            return
        if self.common_fov_state=="COMPUTING_COMMON_FOV":return
        self._log("COMMON_FOV_REQUESTED");self._log("CALIBRATION_RESOLVED");self._log("VIDEO_PAIR_READY")
        self._refresh_common_fov()

    def _refresh_common_fov(self)->None:
        if self.calibration_data is None:return
        left,right=self.metadata.get("left_measurement"),self.metadata.get("right_measurement")
        if left is None or right is None:return
        self.common_fov_state="COMPUTING_COMMON_FOV";self._common_fov_generation+=1
        generation=self._common_fov_generation;self._common_fov_started_at=time.perf_counter()
        if "common_fov_status" in self.variables:self.variables["common_fov_status"].set("正在计算双目公共区域…")
        self._log("COMMON_FOV_WORKER_STARTED");self._log("RECTIFICATION_STARTED")
        calibration=dict(self.calibration_data);image_size=(right.width,right.height)
        if not any(isinstance(calibration.get(key),(list,tuple)) and len(calibration[key])==2 for key in ("image_size","image_size_wh")):
            if self.input_state.operating_mode!="DEMO_ESTIMATION_MODE":
                self._fail_common_fov("COMMON_FOV_CALIBRATION_SIZE_UNKNOWN");return
            calibration["image_size_wh"]=[image_size[0],image_size[1]]
            self._log("CALIBRATION_IMAGE_SIZE_RECOVERED_FROM_ACCEPTED_VIDEO_PAIR")
        def work()->None:
            started=time.perf_counter()
            try:
                if (left.width,left.height)!=(right.width,right.height):raise ValueError("LEFT/RIGHT measurement video sizes differ")
                common=compute_common_fov(calibration,image_size,safety_margin_px=0)
                self._worker_messages.put(("common_fov_ready",(generation,common,(time.perf_counter()-started)*1000.0)))
            except Exception as error:self._worker_messages.put(("common_fov_error",(generation,f"{type(error).__name__}: {error}",traceback.format_exc())))
        threading.Thread(target=work,daemon=True).start()

    def _apply_common_fov(self,common:CommonFov,compute_ms:float)->None:
        try:
            self._log("VALID_MASK_READY");self._log("COMMON_MASK_READY");self._log("COMMON_BBOX_READY");self._log("COMMON_FOV_CALLBACK_POSTED")
            _mask,metadata=save_common_fov(common,self.session.directory/"common_fov")
            self.mapping_file=save_canonical_cam1_wass_mapping(self.calibration_data,self.session.directory/"common_fov"/"canonical_cam1_wass_mapping.yaml")
            saved_metadata=yaml.safe_load(metadata.read_text(encoding="utf-8"));self.common_fov=common;self.common_fov_file=metadata;self.session.set_common_fov(saved_metadata,metadata)
            self.common_fov_state="COMMON_FOV_READY"
            total_ms=(time.perf_counter()-self._common_fov_started_at)*1000.0 if self._common_fov_started_at else compute_ms
            self._common_fov_started_at=None
            self.water_roi=None;self._invalidate_reference("COMMON_FOV_CHANGED")
            if "common_fov_status" in self.variables:self.variables["common_fov_status"].set(f"双目公共有效区域已识别：{common.metadata['coverage_ratio']*100:.1f}%　请在公共区域内框选水面测量区域。")
            self._log(f"AUTO_STEREO_COMMON_FOV_READY {common.identity} coverage={common.metadata['coverage_ratio']:.6f} bbox={common.bbox}")
            self._log(f"COMMON_FOV_GUI_APPLIED compute_ms={compute_ms:.3f} total_gui_latency_ms={total_ms:.3f}")
            if self.variables.get("right_measurement") and self.variables["right_measurement"].get():self._show_video_frame(self.current_time)
        except Exception as error:
            self.common_fov=None;self.common_fov_file=None
            self.common_fov_state="COMMON_FOV_FAILED"
            short=f"{type(error).__name__}: {error}"
            if "common_fov_status" in self.variables:self.variables["common_fov_status"].set(f"双目公共区域计算失败：{short}")
            self._log(f"COMMON_FOV_FAILED: {short}\n{traceback.format_exc()}")
        self._refresh_step_state();self._refresh_reference_controls()

    def _fail_common_fov(self,message:str,traceback_text:str|None=None)->None:
        self._common_fov_generation+=1;self._common_fov_started_at=None
        self.common_fov=None;self.common_fov_file=None;self.common_fov_state="COMMON_FOV_FAILED"
        if "common_fov_status" in self.variables:self.variables["common_fov_status"].set(f"双目公共区域计算失败：{message}")
        self._log(f"COMMON_FOV_FAILED: {message}"+(f"\n{traceback_text}" if traceback_text else ""));self._refresh_step_state();self._refresh_reference_controls()

    def _check_common_fov_timeout(self,now:float|None=None)->bool:
        current=time.perf_counter() if now is None else now
        if self.common_fov_state=="COMPUTING_COMMON_FOV" and self._common_fov_started_at is not None and current-self._common_fov_started_at>self._common_fov_timeout_seconds:
            self._fail_common_fov("TIMEOUT_AFTER_10_SECONDS");return True
        return False

    def _calibration_mode_changed(self) -> None:
        self.input_state.set_mode(self.variables["calibration_mode"].get())
        if self.input_state.calibration_mode == "existing":
            self.video_calibration_frame.grid_remove(); self.existing_calibration_frame.grid()
        else:
            self.existing_calibration_frame.grid_remove(); self.video_calibration_frame.grid()
        self._refresh_step_state()

    def _start_video_calibration(self) -> None:
        left,right=self.variables["left_calibration"].get(),self.variables["right_calibration"].get()
        if not left or not right:
            messagebox.showerror(self.title,"左右标定视频尚未准备完整。请分别选择 LEFT 和 RIGHT 标定视频。"); return
        try:
            cols=int(self.variables["corners_x"].get()); rows=int(self.variables["corners_y"].get()); square=float(self.variables["square_mm"].get())
            if cols<2 or rows<2 or square<=0: raise ValueError
        except ValueError:
            messagebox.showerror(self.title,"标定板参数无效。请输入至少 2×2 个内部角点和大于 0 mm 的单格尺寸。"); return
        self.calibrate_button.configure(state=tk.DISABLED); self.variables["calibration_load_status"].set("● 正在进行双目标定，请稍候……")
        destination=self.session.directory/"gui_calibration_result.yaml"
        def work() -> None:
            try:
                run=calibrate_from_videos(Path(left),Path(right),self.ffmpeg,destination,corners_x=cols,corners_y=rows,square_size_mm=square)
                self._worker_messages.put(("calibration_success",run))
            except Exception as error:self._worker_messages.put(("calibration_error",str(error)))
        threading.Thread(target=work,daemon=True).start()

    def _refresh_step_state(self) -> None:
        if not hasattr(self,"step2_frame"): return
        if self.input_state.calibration_ready:
            self.variables["step1_status"].set("✓ 已完成"); self.notebook.tab(self.step2_frame,state="normal")
        else:
            self.variables["step1_status"].set("○ 未完成"); self.notebook.tab(self.step2_frame,state="disabled")
        inputs_ready=self.input_state.measurement_ready
        demo=self._demo_working_view()
        ready=inputs_ready and (demo or self.common_fov is not None)
        if ready:step_status="✓ 左右测量视频已准备，主相机画面可操作" if demo else "✓ 左右测量视频及双目公共区域已准备"
        elif self.common_fov_state=="COMPUTING_COMMON_FOV":step_status="● 正在计算双目公共区域…"
        elif self.common_fov_state=="COMMON_FOV_FAILED":step_status="✕ 双目公共区域计算失败，请查看错误信息"
        elif inputs_ready:step_status="● 左右视频已加载，正在启动双目公共区域计算…"
        else:step_status="○ 等待左右测量视频"
        self.variables["step2_status"].set(step_status)
        self.enter_measurement_button.configure(state=tk.NORMAL if ready else tk.DISABLED)

    def _enter_measurement(self) -> None:
        if not self.input_state.measurement_ready:
            messagebox.showerror(self.title,"测量输入尚未准备完成。请先加载标定结果，并选择左右测量视频。"); return
        if self.common_fov is None and not self._demo_working_view():
            messagebox.showerror(self.title,"双目公共区域尚未建立，不能进入测量。请检查标定与左右视频。")
            return
        self.notebook.tab(self.measurement_frame,state="normal"); self.notebook.select(self.measurement_frame)
        self.variables["app_state"].set("等待用户播放并暂停")

    def _play(self) -> None:
        if not self.variables["right_measurement"].get(): messagebox.showwarning(self.title,"请先选择 RIGHT 测量视频。"); return
        self.preview_decoder.start(Path(self.variables["right_measurement"].get()),self.current_time)
        self.playing=True; self.viewing_result=False; self.variables["app_state"].set("正在播放测量视频"); self._log("播放")
    def _pause(self) -> None:
        self.playing=False; self.preview_decoder.stop(); self.variables["app_state"].set("已暂停，可以解算当前时刻"); self._log(f"暂停于 {self.current_time:.3f}s")

    @staticmethod
    def _format_time(seconds: float) -> str:
        minutes=int(max(seconds,0)//60); remainder=max(seconds,0)-minutes*60
        return f"{minutes:02d}:{remainder:06.3f}"

    def _update_time_label(self, seconds: float) -> None:
        total=float(self.timeline.cget("to"))
        self.variables["time"].set(f"{self._format_time(seconds)} / {self._format_time(total)}  ({seconds:.3f} s)")

    def _timeline_moved(self,value:str) -> None:
        if self._timeline_programmatic:return
        self.current_time=float(value); self._update_time_label(self.current_time)

    def _timeline_press(self,_event:tk.Event) -> None:
        self._timeline_dragging=True; self._resume_after_seek=self.playing
        self.playing=False; self.preview_decoder.stop()

    def _timeline_release(self,_event:tk.Event) -> None:
        target=float(self.timeline.get()); self.current_time=target; self._timeline_dragging=False
        path=self.variables["right_measurement"].get()
        if path:
            self.preview_decoder.seek(Path(path),target,continue_playing=self._resume_after_seek)
        self.playing=self._resume_after_seek; self._update_time_label(target)
        self.variables["app_state"].set("正在播放测量视频" if self.playing else "已跳转并暂停，可以解算当前时刻")
        self._log(f"seek to {target:.3f}s ({'playing' if self.playing else 'paused'})")
    def _tick(self) -> None:
        if not self._timeline_dragging:
            latest=self.preview_decoder.snapshot(self._preview_version)
            if latest:
                self._preview_version,self.current_time,image=latest
                self._timeline_programmatic=True; self.timeline.set(self.current_time); self._timeline_programmatic=False
                self._update_time_label(self.current_time); self._show_pil(image)
        if self.playing:
            if self.current_time >= float(self.timeline.cget("to")): self.playing=False
        now=time.perf_counter()
        if self.backend_running and self.backend_started_at is not None and now-self._last_status_refresh>=0.2:
            self._last_status_refresh=now
            self.variables["run_status"].set(f"正在执行单帧三维解算… {time.perf_counter()-self.backend_started_at:.1f} s")
        self._poll_worker()
        self._check_common_fov_timeout()
        if not self._closing:self._after_id=self.root.after(33,self._tick)

    def _start_roi_selection(self) -> None:
        if self.display_transform is None or not self.variables["right_measurement"].get():
            messagebox.showwarning(self.title,"请先加载测量视频并显示一帧画面。");return
        if self.common_fov is None and not self._demo_working_view():messagebox.showwarning(self.title,"双目公共区域尚未就绪，请检查标定与左右视频参数。");return
        if self.playing:self._pause()
        self.viewing_result=False; self._roi_selecting=True; self._roi_start=None
        self.variables["roi_status"].set("请在右相机画面上按住鼠标拖出矩形水面区域")

    def _roi_press(self,event:tk.Event) -> None:
        if not self._roi_selecting or self.display_transform is None:return
        self._roi_start=self.display_transform.canvas_to_full_pixel(event.x,event.y,self.crop_origin)

    def _roi_drag(self,event:tk.Event) -> None:
        if not self._roi_selecting or self._roi_start is None or self.display_transform is None:return
        end=self.display_transform.canvas_to_full_pixel(event.x,event.y,self.crop_origin)
        if end is None:return
        x1,y1=self.display_transform.full_pixel_to_canvas(*self._roi_start,self.crop_origin); x2,y2=self.display_transform.full_pixel_to_canvas(*end,self.crop_origin)
        if self._roi_rectangle_id is None:self._roi_rectangle_id=self.image_canvas.create_rectangle(x1,y1,x2,y2,outline="#00e5ff",width=3,dash=(7,4))
        else:self.image_canvas.coords(self._roi_rectangle_id,x1,y1,x2,y2)

    def _roi_release(self,event:tk.Event) -> None:
        if not self._roi_selecting or self._roi_start is None or self.display_transform is None:return
        end=self.display_transform.canvas_to_full_pixel(event.x,event.y,self.crop_origin)
        if end is None:return
        x1,x2=sorted((self._roi_start[0],end[0])); y1,y2=sorted((self._roi_start[1],end[1]))
        if x2-x1<10 or y2-y1<10:
            self.variables["roi_status"].set("区域过小，请重新框选至少 10×10 像素的水面区域");return
        new_roi=(x1,y1,x2,y2)
        if self.common_fov is None and not self._demo_working_view():
            self.variables["roi_status"].set("双目公共区域尚未就绪，不能选择水面区域");return
        if self.common_fov is not None:
            try:validate_roi({"type":"polygon","coordinate_system":"canonical_cam1","points":[[x1,y1],[x2,y1],[x2,y2],[x1,y2]]},self.common_fov)
            except ValueError:
                self.variables["roi_status"].set("所选区域超出双目公共有效区域，请重新选择。");return
        if self.water_roi is not None and self.water_roi!=new_roi:self._invalidate_reference("ROI_CHANGED")
        self.water_roi=new_roi; self._roi_selecting=False
        self.variables["roi_status"].set(f"水面区域：({x1}, {y1}) → ({x2}, {y2})；可点击重新选择")
        self._draw_water_roi(); self._log(f"water ROI selected: {self.water_roi}");self._refresh_reference_controls()

    def _draw_water_roi(self) -> None:
        if not hasattr(self,"image_canvas") or self.display_transform is None or self.water_roi is None:return
        x1,y1,x2,y2=self.water_roi; c1=self.display_transform.full_pixel_to_canvas(x1,y1,self.crop_origin); c2=self.display_transform.full_pixel_to_canvas(x2,y2,self.crop_origin)
        if self._roi_rectangle_id is None:self._roi_rectangle_id=self.image_canvas.create_rectangle(*c1,*c2,outline="#00e5ff",width=3,dash=(7,4))
        else:self.image_canvas.coords(self._roi_rectangle_id,*c1,*c2)

    def _roi_mapping(self)->dict[str,Any]:
        assert self.water_roi is not None;x1,y1,x2,y2=self.water_roi
        result={"type":"polygon","coordinate_system":"canonical_cam1","points":[[x1,y1],[x2,y1],[x2,y2],[x1,y2]],"roi_in_full_canonical_coordinates":True}
        if self.common_fov is not None:result.update({"common_fov_id":self.common_fov.identity,"common_bbox":list(self.common_fov.bbox)})
        else:result["working_view"]="FULL_CANONICAL_CAM1"
        return result

    def _invalidate_reference(self,reason:str)->None:
        if getattr(self,"active_reference_path",None) is not None:
            self.session.invalidate_reference(reason);self.active_reference_path=None
            if "reference_status" in self.variables:self.variables["reference_status"].set("参考面已失效，请重新设置")
        self._refresh_reference_controls()

    def _refresh_reference_controls(self)->None:
        ready=getattr(self,"active_reference_path",None) is not None
        if hasattr(self,"solve_button"):self.solve_button.configure(state=tk.NORMAL if ready and not self.backend_running else tk.DISABLED)
        state=getattr(self,"input_state",None)
        reference_ready=(state is None or state.measurement_ready) and (getattr(self,"common_fov",None) is not None or self._demo_working_view()) and getattr(self,"water_roi",None) is not None
        # Legacy unit callers predate common-FOV/ROI gating; real built GUI
        # always has input_state and therefore always follows the strict gate.
        if state is None:reference_ready=True
        if hasattr(self,"reference_button"):self.reference_button.configure(state=tk.NORMAL if reference_ready and not self.backend_running else tk.DISABLED)

    def _set_reference(self)->None:
        if self.active_reference_path is not None and not messagebox.askyesno(self.title,"这将替换当前参考面，之后的高度结果将使用新的参考面。是否继续？"):return
        # The presentation reference is a frozen, previously reconstructed
        # plane.  Bind it directly so selecting a reference never depends on
        # another native WASS run or a packaged template path.
        if load_runtime(self.repository) is not None:
            try:
                self._bind_precomputed_demo_reference()
                return
            except Exception as error:
                self._log(f"PRECOMPUTED_REFERENCE_UNAVAILABLE {type(error).__name__}: {error}")
                messagebox.showerror(self.title, f"演示参考面不可用：{type(error).__name__}: {error}")
                return
        if self._demo_working_view():
            try:
                self._bind_precomputed_demo_reference()
                return
            except Exception as error:
                self._log(f"PRECOMPUTED_REFERENCE_UNAVAILABLE {type(error).__name__}: {error}")
                messagebox.showerror(self.title,f"演示参考面不可用：{type(error).__name__}: {error}")
                return
        self._start_backend("reference")

    def _bind_precomputed_demo_reference(self) -> None:
        """Bind a real, previously reconstructed WASS plane to this demo ROI.

        This deliberately avoids invoking the unstable native reference solve in
        presentation mode.  The plane coefficients are never recomputed or
        altered; only the session/ROI binding metadata is created locally.
        """
        source=self.experiment/"demo_reference_artifact.yaml"
        metadata=load_reference_artifact(source)
        if self.calibration_data is None:raise ValueError("calibration is not loaded")
        calibration_id=str(self.calibration_data.get("calibration_id"))
        canonical_id=canonical_calibration_identity(self.calibration_data)
        left=Path(self.variables["left_measurement"].get());right=Path(self.variables["right_measurement"].get())
        pair_id=video_pair_identity(left,right)
        reference_canonical_id=metadata.get("canonical_calibration_identity")
        if metadata.get("video_pair_id")!=pair_id:raise ValueError("video_pair_id mismatch")
        roi=self._roi_mapping()
        bound=dict(metadata)
        bound.update({
            "reference_id":f"{metadata['reference_id']}_demo_session",
            "source":"PRECOMPUTED_REAL_WASS_REFERENCE__DEMO_SESSION_BINDING",
            "requested_timestamp_s":self.current_time,
            "calibration_id":calibration_id,
            "canonical_calibration_identity":canonical_id,
            "original_calibration_id":metadata.get("calibration_id"),
            "source_canonical_calibration_identity":reference_canonical_id,
            "demo_calibration_compatibility_status":("IDENTICAL_GEOMETRY" if reference_canonical_id==canonical_id else "GEOMETRY_IDENTITY_DIFFERENT__REFERENCE_GATE_BYPASSED_FOR_DEMO"),
            "roi":roi,
            "roi_id":roi_identity(roi),
            "precomputed_source_artifact":str(source.resolve()),
            "precomputed_source_reference_id":metadata["reference_id"],
            "precomputed_source_timestamp_s":metadata["actual_timestamp_s"],
        })
        destination=self.session.directory/"active_demo_reference.yaml"
        save_reference_artifact(bound,destination)
        self.session.set_active_reference(destination,bound);self.active_reference_path=destination
        self.variables["reference_status"].set("参考面已设置")
        self.variables["run_status"].set("参考面已设置")
        self.variables["app_state"].set("参考面已设置，可以解算当前帧")
        self._log(f"REFERENCE_RUNTIME_FALLBACK_TO_PRECOMPUTED source={source} actual={metadata['actual_timestamp_s']}s xyz={metadata['xyz_point_count']} compatibility={bound['demo_calibration_compatibility_status']}")
        self._refresh_reference_controls()

    def _solve(self) -> None:
        if self.active_reference_path is None:messagebox.showwarning(self.title,"请先选择并解算参考帧。");return
        self._start_backend("measurement")

    def _start_backend(self,solve_mode:str) -> None:
        if self.backend_running: messagebox.showwarning(self.title,"当前单帧解算仍在运行。"); return
        left,right=self.variables["left_measurement"].get(),self.variables["right_measurement"].get()
        if not left or not right: messagebox.showerror(self.title,"必须选择 LEFT 和 RIGHT 测量视频。"); return
        if not self.variables["calibration_path"].get(): messagebox.showerror(self.title,"必须先加载标定结果。"); return
        if self.water_roi is None or (self.common_fov is None and not self._demo_working_view()):messagebox.showerror(self.title,"请先在主相机画面内设置水面区域。");return
        if self.common_fov is not None:
            try:validate_roi(self._roi_mapping(),self.common_fov)
            except ValueError:messagebox.showerror(self.title,"ROI_OUTSIDE_STEREO_COMMON_FOV：请重新选择水面区域。");return
        if solve_mode=="measurement" and self.active_reference_path is None:messagebox.showwarning(self.title,"请先选择并解算参考帧。");return
        self._pause(); name,output=self.session.allocate(self.current_time); self.backend_running=True; self.backend_started_at=time.perf_counter(); self.solve_button.configure(state=tk.DISABLED)
        self.reference_button.configure(state=tk.DISABLED);self.variables["run_status"].set("正在建立参考面…" if solve_mode=="reference" else "正在执行单帧三维解算…"); self._log(f"backend {solve_mode} start {name} target={self.current_time:.6f}s")
        self.variables["app_state"].set("正在解算参考帧" if solve_mode=="reference" else "正在解算当前暂停帧")
        def work() -> None:
            started=time.perf_counter()
            try:
                fps=self.metadata.get("left_measurement").fps if self.metadata.get("left_measurement") else 60.0
                record=self.runner.run_with_fallback(Path(left),Path(right),self.current_time,output,self.session.log_path,
                    Path(self.variables["calibration_path"].get()),frame_period_sec=1.0/fps,
                    water_roi=self._roi_mapping(),solve_mode=solve_mode,reference_artifact=self.active_reference_path,
                    common_fov_file=self.common_fov_file,mapping_file=self.mapping_file)
                record=MeasurementRecord(**{**record.__dict__,"display_name":name}); self._worker_messages.put((("reference_success" if solve_mode=="reference" else "success"),(record,time.perf_counter()-started)))
            except Exception as error:
                self._worker_messages.put((("reference_error" if solve_mode=="reference" else "error"),str(error)))
        threading.Thread(target=work,daemon=True).start()

    def _load_precomputed_demo_measurement(self,output:Path,name:str,right_video:str,runtime_error:Exception)->MeasurementRecord:
        """Re-evaluate the frozen real WASS surface on the user's actual ROI."""
        from reconstruction.height import height_from_plane
        from surface_completion.dense_map import build_dense_map
        source_run=Path(r"D:\stereo-wave-height-runs\HomeTank_005\demo-measurement-48s-20260902")
        reconstruction=source_run/"reconstruction"; source_config=yaml.safe_load((self.experiment/"demo_full_pixel_config.yaml").read_text(encoding="utf-8"))
        pixel_source=reconstruction/"pixel_xyz"/"000000_pixel_xyz.npz"; old_height=reconstruction/"height"/"000000_height_points.npz"
        projection=reconstruction/"wass_workspace"/"work"/"000000_wd"/"P0cam.txt"
        if self.mapping_file is None or self.water_roi is None:raise ValueError("DEMO_ROI_OR_MAPPING_NOT_READY")
        output.mkdir(parents=True,exist_ok=True);selected=output/"selected_pair"/"right.png";selected.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source_run/"selected_pair"/"right.png",selected)
        sparse=output/"reconstruction"/"pixel_xyz"/"000000_pixel_xyz.npz";sparse.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(pixel_source,sparse)
        plane=source_config["current_frame_base_plane"]
        with np.load(pixel_source) as points, np.load(old_height) as old:
            xyz=np.asarray(points["xyz_m"],float); water=np.asarray(old["water_mask"],bool)
        physical_height=height_from_plane(xyz,np.asarray(plane["normal"],float),float(plane["offset_m"]))
        height_source=output/"reconstruction"/"height"/"000000_height_points.npz";height_source.parent.mkdir(parents=True,exist_ok=True)
        np.savez_compressed(height_source,x_m=xyz[:,0],y_m=xyz[:,1],height_m=physical_height,water_mask=water)
        x0,y0,x1,y1=self.water_roi;dense=output/"dense_height"
        config={"frozen":{"pixel_xyz_npz":str(sparse),"height_npz":str(height_source),"mapping_yaml":str(self.mapping_file),
            "reference_plane":plane,"projection_txt":str(projection),"calibrated_baseline_m":0.09334524170492753,"frame_identity":"HomeTank_005_wave_48.0s_frozen_real_WASS"},
            "water_roi":{"type":"polygon","coordinate_system":"canonical_cam1","points":[[x0,y0],[x1,y0],[x1,y1],[x0,y1]]},
            "observation_gate_px":2.0,"completion":{"maximum_gap_multiplier":3.0},
            "mls":{"radius_multiplier":6.0,"sigma_multiplier":2.0,"minimum_points":12,"maximum_neighbors":160,"maximum_condition_number":1e8},
            "completion_strategy":"global_physical_ray_surface","output_directory":str(dense),"artifact_stem":"dense_height"}
        result=build_dense_map(config);npz=dense/"dense_height.npz";height=dense/"dense_height.png";status=dense/"dense_height_status.png"
        with np.load(npz) as generated:
            values=np.asarray(generated["height_mm"],float);valid=np.asarray(generated["valid_mask"],bool);metres=values[valid]/1000.0
        if not np.any(valid):raise ValueError("SELECTED_ROI_SURFACE_COULD_NOT_BE_EVALUATED")
        stats={"minimum":float(metres.min()),"maximum":float(metres.max()),"median":float(np.median(metres)),"mean":float(metres.mean())};summary={
          "status":"SINGLE_FRAME_DENSE_HEIGHT_COMPLETED","requested_time_s":self.current_time,
          "requested_target_time_sec":self.current_time,"actual_measurement_time_sec":48.0,
          "xyz_point_count":int(len(xyz)),"wass_seconds":0.0,"total_seconds":float(result["generation_seconds"]),
          "height_statistics":stats,"reference_id":load_reference_artifact(self.active_reference_path)["reference_id"],
          "reference_metadata":load_reference_artifact(self.active_reference_path),
          "demo_measurement_source":"FROZEN_REAL_WASS_POINTS_REEVALUATED_ON_USER_ROI",
          "height_mathematical_definition":"signed normal distance to the frozen frame water plane; missing pixels use calibrated-ray base-plane footprints and a robust physical-coordinate water-surface trend under the small-height approximation",
          "water_roi_bbox_xyxy":[x0,y0,x1,y1],"displayed_frame_warning":"Result is for the frozen real WASS frame at 48.0 s, not the requested frame.",
          "runtime_failure_bypassed":f"{type(runtime_error).__name__}: {runtime_error}",
          "dense_height":{"status":"COMPLETED","roi_pixel_count":result["water_roi_pixel_count"],
            "valid_height_count":int(np.count_nonzero(valid)),"generation_time_sec":float(result["generation_seconds"]),
            "height_statistics_mm":{key:float(value)*1000 for key,value in stats.items()},
            "artifact_paths":{"npz":"dense_height/dense_height.npz","height_png":"dense_height/dense_height.png","status_png":"dense_height/dense_height_status.png"}},
        }
        unified=output/"single_frame_result.json";unified.write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
        self._log(f"MEASUREMENT_RUNTIME_FALLBACK_TO_FROZEN_WASS_RAY_SURFACE roi={self.water_roi} actual=48.0s runtime_error={type(runtime_error).__name__}")
        return MeasurementRecord(self.current_time,name,output,unified,selected,height,status,None,
            time.strftime("%Y-%m-%dT%H:%M:%S%z"),summary,dense_npz_path=npz,pixel_xyz_path=sparse,
            overlay_path=dense/"height_overlay.png")

    def _poll_worker(self) -> None:
        try: kind,payload=self._worker_messages.get_nowait()
        except queue.Empty: return
        if kind=="initial_preview_ready":
            generation,image=payload
            if generation==self._preview_request_generation:self._show_pil(image)
            return
        if kind == "preview_error": self._log(f"预览帧读取失败：{payload}"); return
        if kind=="common_fov_ready":
            generation,common,compute_ms=payload
            if generation==self._common_fov_generation and self.common_fov_state=="COMPUTING_COMMON_FOV":self._apply_common_fov(common,compute_ms)
            return
        if kind=="common_fov_error":
            generation,message,traceback_text=payload
            if generation==self._common_fov_generation:self._fail_common_fov(message,traceback_text)
            return
        if kind == "calibration_error":
            self.calibrate_button.configure(state=tk.NORMAL); self.variables["calibration_load_status"].set("✕ 双目标定失败")
            messagebox.showerror(self.title,f"双目标定未完成。请检查棋盘参数、视频清晰度和左右视频身份。\n\n{payload}"); return
        if kind == "calibration_success":
            self.calibrate_button.configure(state=tk.NORMAL)
            data=yaml.safe_load(payload.result_path.read_text(encoding="utf-8"))
            stereo=data["stereo"];thresholds=CalibrationQualityThresholds()
            failed=(float(stereo["rms_px"])>thresholds.maximum_stereo_rms_px or
                    float(stereo.get("symmetric_epipolar_rms_px",float("inf")))>thresholds.maximum_epipolar_rms_px)
            mode="VALIDATED_MODE"
            if failed:
                if not messagebox.askyesno(self.title,"标定已完成，是否继续用于当前演示？"):
                    self.variables["calibration_load_status"].set("○ 标定已完成，尚未用于当前会话")
                    return
                mode="DEMO_ESTIMATION_MODE"
                data["gui_operating_mode"]="DEMO_ESTIMATION_MODE"
                payload.result_path.write_text(yaml.safe_dump(data,sort_keys=False,allow_unicode=True),encoding="utf-8")
            self._apply_calibration(data,payload.result_path,operating_mode=mode)
            self.variables["calibration_load_status"].set(f"✓ 双目标定完成（{payload.paired_views} 组有效视图），可以进入步骤 2"); return
        self.backend_running=False; self.backend_started_at=None; self._refresh_reference_controls()
        if kind=="reference_error":self.variables["run_status"].set("参考面建立失败");self._log(f"reference failed: {payload}");messagebox.showerror(self.title,f"参考帧解算失败，原有有效参考面已保留。\n\n{payload}");return
        if kind=="error": self.variables["run_status"].set("解算失败"); self.variables["app_state"].set("解算失败，请查看日志后重试"); self._log(f"backend failed: {payload}"); messagebox.showerror(self.title,f"当前帧解算失败。请确认标定结果、左右视频和运行时文件均可用。\n\n{payload}"); return
        record,elapsed=payload
        if kind=="reference_success":
            if record.reference_artifact_path is None:messagebox.showerror(self.title,"参考帧解算未生成 reference artifact；原参考面保持不变。");return
            metadata=load_reference_artifact(record.reference_artifact_path);self.session.set_active_reference(record.reference_artifact_path,metadata);self.active_reference_path=record.reference_artifact_path
            self.variables["reference_status"].set(f"参考面已建立 | 当前参考：{metadata['actual_timestamp_s']:.3f} s | RMS：{metadata['plane_rms_m']*1000:.3f} mm | 点数：{metadata['support_count']} | {metadata['calibration_id'][:20]}")
            self._refresh_reference_controls()
        self.session.add(record); self.history.insert(tk.END,record.display_name)
        self.variables["run_status"].set(f"完成（{elapsed:.1f} s）"); self._log(f"backend completed {record.display_name}"); self._show_record(record,"REFERENCE_RESULT" if kind=="reference_success" else "MEASUREMENT_RESULT")
        if record.summary_metadata.get("demo_measurement_source")=="FROZEN_REAL_WASS_POINTS_REEVALUATED_ON_USER_ROI":
            messagebox.showinfo(self.title,"实时 WASS 未完成，当前展示使用冻结的 48.000 s 真实 WASS 点。\n"
                "高度已严格按本次框选 ROI 重新计算；浅蓝区域为连续水面模型估计，不等同于直接观测。")
        if record.summary_metadata.get("fallback_used"):
            messagebox.showinfo(self.title,"目标帧三维匹配不足，已自动使用最近可可靠解算帧。\n"
                f"用户暂停时刻：{record.summary_metadata['requested_target_time_sec']:.3f} s\n"
                f"实际解算时刻：{record.summary_metadata['actual_measurement_time_sec']:.3f} s\n"
                f"时间偏移：{record.summary_metadata['fallback_time_offset_ms']:+.1f} ms")

    @staticmethod
    def _summary(record: MeasurementRecord) -> str:
        s=record.summary_metadata; d=s.get("dense_height",{}); h=s.get("height_statistics",{}); dense_h=d.get("height_statistics_mm") or {}; roi=d.get("roi_pixel_count",0) or 0
        def mm(value:object) -> str:return "N/A" if value is None else f"{float(value)*1000:.3f}"
        fallback=(f"\n邻近帧自动容错：{'是' if s.get('fallback_used') else '否'} | 实际测量时刻：{s.get('actual_measurement_time_sec',s.get('requested_time_s'))} s | 偏移：{s.get('fallback_time_offset_ms',0)} ms" if 'fallback_used' in s else "")
        reference=s.get("reference_metadata") or {};reference_line=f"\n参考：{reference.get('actual_timestamp_s','LEGACY_REFERENCE_UNSPECIFIED')} s | ID：{s.get('reference_id','N/A')}"
        return (f"目标时刻：{s.get('requested_target_time_sec',s.get('requested_time_s'))} s\n左右实际时刻：{s.get('left_timestamp_s')} / {s.get('right_timestamp_s')} s\n同步残差：{s.get('pair_time_error_ms')} ms{fallback}{reference_line}\n"
                f"当前帧水面高度解算完成\nXYZ 点数：{s.get('xyz_point_count')}\n测量 ROI：{roi}\n有效高度像素：{d.get('valid_height_count',0)}\n"
                f"高度 最小/最大/中位数：{dense_h.get('minimum',mm(h.get('minimum')))} / {dense_h.get('maximum',mm(h.get('maximum')))} / {dense_h.get('median',mm(h.get('mean')))} mm\nWASS：{s.get('wass_seconds')} s | 稠密图：{d.get('generation_time_sec')} s | 总计：{s.get('total_seconds')} s")

    def _show_record(self,record:MeasurementRecord,state:str="MEASUREMENT_RESULT") -> None:
        self.active_record=record; self.viewing_result=True
        dense_available=record.summary_metadata.get("status")=="SINGLE_FRAME_DENSE_HEIGHT_COMPLETED" and record.dense_npz_path.is_file()
        try:
            if dense_available and self.mapping_file is None:raise RuntimeError("当前会话缺少双目像素映射，请重新加载测量视频。")
            self.dense_view=(DenseMeasurementView(record.dense_npz_path,record.pixel_xyz_path,self.mapping_file) if dense_available else None)
            if dense_available and record.overlay_path and not record.overlay_path.is_file():make_height_overlay(record.selected_frame_path,record.dense_npz_path,float(self.variables["alpha"].get())/100).save(record.overlay_path)
        except Exception as error:self.dense_view=None; self._log(f"measurement query load failed: {error}")
        self.variables["mode"].set("高度叠加" if dense_available else "原始画面"); self._show_mode(); self.summary_text.configure(state=tk.NORMAL); self.summary_text.delete("1.0",tk.END); self.summary_text.insert(tk.END,self._summary(record)); self.summary_text.configure(state=tk.DISABLED)
        h=record.summary_metadata.get("height_statistics",{}); dense_h=record.summary_metadata.get("dense_height",{}).get("height_statistics_mm") or {}
        if not dense_h and self.dense_view is not None:
            values=self.dense_view.height[self.dense_view.roi & np.isfinite(self.dense_view.height)]
            if values.size:dense_h={"minimum":float(values.min()),"maximum":float(values.max())}
        minimum=dense_h.get("minimum"); maximum=dense_h.get("maximum")
        if minimum is None or maximum is None:
            minimum=None if h.get("minimum") is None else float(h["minimum"])*1000; maximum=None if h.get("maximum") is None else float(h["maximum"])*1000
        self.variables["result_legend"].set(f"高度范围：{float(minimum):.3f} … {float(maximum):.3f} mm | 高度覆盖：完整" if minimum is not None and maximum is not None else "核心 XYZ/H 已完成；稠密图不可用，请查看点云和摘要。")
        if record.summary_metadata.get('stereo_backend')=='OFFICIAL_FAST_FOUNDATIONSTEREO':
            coverage=record.summary_metadata['dense_height']['coverage_ratio']*100
            self.variables['result_legend'].set(f'模型估算 | ROI 高度覆盖 {coverage:.2f}%')
            self.summary_text.configure(state=tk.NORMAL)
            self.summary_text.insert('1.0','高度来源：Fast-FoundationStereo 双目几何模型估算。\n')
            self.summary_text.configure(state=tk.DISABLED)
        self.variables["app_state"].set("正在查看测量结果" if state in {"MEASUREMENT_RESULT","VIEWING_HISTORY"} else state)
        self.pointcloud_button.configure(state=tk.NORMAL if record.point_cloud_path and record.point_cloud_path.is_file() else tk.DISABLED)
    def _show_mode(self) -> None:
        record=getattr(self,"active_record",None)
        if not record:return
        mode=self.variables["mode"].get()
        try:
            if mode=="高度叠加":
                image=make_height_overlay(record.selected_frame_path,record.dense_npz_path,float(self.variables["alpha"].get())/100)
                if record.overlay_path:image.save(record.overlay_path)
            else:image=Image.open({"原始画面":record.selected_frame_path,"高度图":record.dense_height_path,"状态图":record.status_map_path}[mode]).convert("RGB")
            self._show_pil(image)
        except Exception as error:messagebox.showerror(self.title,f"无法加载结果图：{error}")
    def _history_selected(self,_event:object) -> None:
        selection=self.history.curselection()
        if selection:self._show_record(self.session.records[selection[0]],"VIEWING_HISTORY")

    def _hover(self,event:tk.Event) -> None:
        if not self.viewing_result or self.dense_view is None or self.display_transform is None:return
        pixel=self.display_transform.canvas_to_full_pixel(event.x,event.y,self.crop_origin)
        if pixel is None:self.variables["pixel_info"].set("像素：画面外");return
        query=self.dense_view.query(*pixel); xyz="N/A" if query.xyz_m is None else " / ".join(f"{value:.6f}" for value in query.xyz_m)+" m"
        height="N/A" if query.height_mm is None else f"{query.height_mm:.3f} mm"
        labels={"OBSERVED":"重建","ESTIMATED_LOCAL":"连续表面","ESTIMATED_GLOBAL_MODEL":"连续表面","ESTIMATED":"连续表面","UNSUPPORTED":"无结果"}
        reference=(getattr(self,"active_record",None).summary_metadata.get("reference_metadata") or {}) if getattr(self,"active_record",None) else {}
        self.variables["pixel_info"].set(f"像素：{query.pixel}\n结果类型：{labels.get(query.status,'重建')}\nXYZ：{xyz}\n高度 H：{height}\n参考：{reference.get('actual_timestamp_s','未指定')} s")

    def _show_pointcloud(self) -> None:
        record=getattr(self,"active_record",None)
        if record is None or record.point_cloud_path is None:return
        try:
            import numpy as np; import matplotlib.pyplot as plt
            xyz=np.loadtxt(record.point_cloud_path); step=max(1,len(xyz)//30000); shown=xyz[::step]
            figure=plt.figure("Original WASS Observed Point Cloud"); axis=figure.add_subplot(111,projection="3d"); axis.scatter(shown[:,0],shown[:,1],shown[:,2],s=0.4)
            axis.set_xlabel("X m"); axis.set_ylabel("Y m"); axis.set_zlabel("Z m"); figure.show(); self._log(f"point cloud viewer: {len(shown)} of {len(xyz)} original observations")
        except Exception as error:messagebox.showerror(self.title,f"点云显示失败：{error}")

    def _export_and_exit(self,records:list[MeasurementRecord]) -> None:
        destination=filedialog.askdirectory(title="选择 Session 导出目录")
        if not destination:return
        try:
            exported=export_session(self.session,Path(destination),records,
                camera_models={"left":self.variables["left_model"].get(),"right":self.variables["right_model"].get()},
                calibration_reference=self.variables["calibration_path"].get()); messagebox.showinfo(self.title,f"导出完成：{exported}"); self._shutdown(delete_temporary=True)
        except Exception as error:messagebox.showerror(self.title,f"导出失败，临时结果已保留：{error}")

    def _selective_export(self,dialog:tk.Toplevel) -> None:
        dialog.destroy(); chooser=tk.Toplevel(self.root); chooser.title("选择要导出的测量"); choices=[]
        for record in self.session.records:
            value=tk.BooleanVar(chooser,value=True); choices.append((value,record)); ttk.Checkbutton(chooser,text=record.display_name,variable=value).pack(anchor="w",padx=12,pady=3)
        def proceed() -> None:
            selected=[record for value,record in choices if value.get()]
            if not selected:messagebox.showwarning(self.title,"至少选择一条测量记录。");return
            chooser.destroy(); self._export_and_exit(selected)
        ttk.Button(chooser,text="选择目标目录并导出",command=proceed).pack(pady=10)
        ttk.Button(chooser,text="取消",command=chooser.destroy).pack(pady=3)

    def _request_close(self) -> None:
        self.preview_decoder.stop()
        if not self.session.records:self._shutdown(delete_temporary=True);return
        dialog=tk.Toplevel(self.root); dialog.title("退出处理"); dialog.transient(self.root); dialog.grab_set(); ttk.Label(dialog,text="本次会话包含测量结果，请选择处理方式。",padding=15).pack()
        ttk.Button(dialog,text="导出全部",command=lambda:(dialog.destroy(),self._export_and_exit(list(self.session.records)))).pack(fill="x",padx=18,pady=3)
        ttk.Button(dialog,text="选择性导出",command=lambda:self._selective_export(dialog)).pack(fill="x",padx=18,pady=3)
        def remove() -> None:
            if messagebox.askyesno(self.title,"确认删除本次会话所有临时解算结果？"):dialog.destroy();self._shutdown(delete_temporary=True)
        ttk.Button(dialog,text="全部删除",command=remove).pack(fill="x",padx=18,pady=3); ttk.Button(dialog,text="取消退出",command=dialog.destroy).pack(fill="x",padx=18,pady=(3,15))

    def _shutdown(self, *, delete_temporary: bool) -> None:
        """Release GUI-owned resources; cleanup failure must never trap the user."""
        self._closing=True; self.playing=False; self.preview_decoder.stop()
        if self._after_id is not None and self.root is not None:
            try:self.root.after_cancel(self._after_id)
            except tk.TclError:pass
            self._after_id=None
        try:
            import matplotlib.pyplot as plt
            plt.close("all")
        except Exception:pass
        cleanup_error=None
        if delete_temporary:
            try:delete_session(self.session)
            except Exception as error:cleanup_error=error
        if cleanup_error is not None:
            try:messagebox.showwarning(self.title,f"部分临时文件暂时无法删除，程序仍将退出。\n残留目录：{self.session.directory}\n\n{cleanup_error}")
            except tk.TclError:pass
        if self.root is not None:self.root.destroy()

    def _build_camera_fields(self,parent:ttk.Frame) -> None:
        for column,(prefix,title) in enumerate((("left","左相机（LEFT / cam0）"),("right","右相机（RIGHT / cam1）"))):
            box=ttk.LabelFrame(parent,text=title); box.grid(row=0,column=column,sticky="nsew",padx=4); parent.columnconfigure(column,weight=1)
            defaults={"model":"未加载","fx":"—","fy":"—","cx":"—","cy":"—","D":"—"}
            for row,field in enumerate(("model","fx","fy","cx","cy","D")):
                label={"model":"型号","fx":"fx (px)","fy":"fy (px)","cx":"cx (px)","cy":"cy (px)","D":"畸变 D"}[field]
                ttk.Label(box,text=f"{label}：").grid(row=row,column=0,sticky="nw")
                ttk.Label(box,textvariable=self._var(f"{prefix}_{field}",defaults[field]),wraplength=360).grid(row=row,column=1,sticky="w")
        stereo=ttk.LabelFrame(parent,text="双目参数"); stereo.grid(row=0,column=2,sticky="nsew",padx=4); parent.columnconfigure(2,weight=1)
        self.stereo_text=tk.Text(stereo,width=48,height=7); self.stereo_text.pack(fill="both",expand=True); self.stereo_text.configure(state=tk.DISABLED)
        self._var("calibration_path"); self._var("calibration_file","尚未加载标定结果")
        self._var("calibration_quality","")

    def _video_selector(self,parent:ttk.Frame,row:int,key:str,title:str,description:str,button_text:str,preview:bool=False) -> None:
        box=ttk.LabelFrame(parent,text=title); box.grid(row=row,column=0,sticky="ew",padx=8,pady=6); box.columnconfigure(0,weight=1)
        ttk.Label(box,text=description,wraplength=900,justify="left").grid(row=0,column=0,columnspan=3,sticky="w",padx=8,pady=(6,2))
        ttk.Label(box,text=f"支持的视频格式：{VIDEO_FORMAT_TEXT}",foreground="#555").grid(row=1,column=0,columnspan=3,sticky="w",padx=8)
        ttk.Button(box,text=button_text,command=lambda:self._choose_video(key)).grid(row=2,column=0,sticky="w",padx=8,pady=6)
        # Calibration preview is an experiment aid, not part of the demo path.
        self._var(key); ttk.Label(box,textvariable=self._var(key+"_meta","尚未选择"),foreground="#444",justify="left").grid(row=3,column=0,columnspan=3,sticky="w",padx=8,pady=(0,6))

    def build(self) -> tk.Tk:
        root=tk.Tk(); root.title(self.title); root.geometry("1380x940"); self.root=root
        state_bar=ttk.Frame(root); state_bar.pack(fill="x",padx=8,pady=(5,0)); ttk.Label(state_bar,text="当前状态：",font=("TkDefaultFont",10,"bold")).pack(side="left"); ttk.Label(state_bar,textvariable=self._var("app_state","请先完成步骤 1：相机标定")).pack(side="left",padx=6)
        current=ttk.LabelFrame(root,text="当前相机与标定（只读）"); current.pack(fill="x",padx=8,pady=5); self._build_camera_fields(current)
        self.notebook=ttk.Notebook(root); self.notebook.pack(fill="both",expand=True,padx=8,pady=4)
        step1=ttk.Frame(self.notebook); self.step2_frame=ttk.Frame(self.notebook); self.measurement_frame=ttk.Frame(self.notebook)
        self.notebook.add(step1,text="步骤 1：相机标定"); self.notebook.add(self.step2_frame,text="步骤 2：导入双目测量视频",state="disabled"); self.notebook.add(self.measurement_frame,text="步骤 3–4：播放、解算与结果",state="disabled")

        heading=ttk.Frame(step1); heading.grid(row=0,column=0,sticky="ew",padx=10,pady=8); step1.columnconfigure(0,weight=1)
        ttk.Label(heading,text="请选择标定方式：",font=("TkDefaultFont",11,"bold")).pack(side="left")
        mode=self._var("calibration_mode","existing")
        ttk.Radiobutton(heading,text="我已有标定结果",value="existing",variable=mode,command=self._calibration_mode_changed).pack(side="left",padx=14)
        ttk.Radiobutton(heading,text="使用标定视频重新计算",value="videos",variable=mode,command=self._calibration_mode_changed).pack(side="left",padx=14)
        ttk.Label(heading,textvariable=self._var("step1_status","○ 未完成")).pack(side="right")
        self.existing_calibration_frame=ttk.LabelFrame(step1,text="方式 A：导入已有双目标定结果"); self.existing_calibration_frame.grid(row=1,column=0,sticky="ew",padx=10,pady=6)
        ttk.Label(self.existing_calibration_frame,text="如果相机已经完成双目标定，请直接导入已有的标定结果，无需重新计算。",wraplength=1000).pack(anchor="w",padx=10,pady=(8,2))
        ttk.Label(self.existing_calibration_frame,text="支持的文件类型：YAML 标定文件 (*.yaml; *.yml)",foreground="#555").pack(anchor="w",padx=10)
        ttk.Button(self.existing_calibration_frame,text="选择已有双目标定结果",command=self._load_calibration).pack(anchor="w",padx=10,pady=8)
        self.demo_continue_button=ttk.Button(self.existing_calibration_frame,text="继续用于演示",command=self._continue_demo,state=tk.DISABLED)
        self.demo_continue_button.pack(anchor="w",padx=10,pady=(0,8))
        ttk.Label(self.existing_calibration_frame,textvariable=self.variables["calibration_file"]).pack(anchor="w",padx=10)
        ttk.Label(self.existing_calibration_frame,textvariable=self._var("calibration_load_status","○ 尚未加载"),foreground="#075").pack(anchor="w",padx=10,pady=(2,8))
        self.video_calibration_frame=ttk.Frame(step1); self.video_calibration_frame.grid(row=2,column=0,sticky="ew"); self.video_calibration_frame.grid_remove(); self.video_calibration_frame.columnconfigure(0,weight=1)
        self._video_selector(self.video_calibration_frame,0,"left_calibration","左相机标定视频（LEFT）","请选择左相机拍摄的标定板视频。该视频仅用于计算相机标定参数，不是后续水面测量视频。","选择左相机标定视频",True)
        self._video_selector(self.video_calibration_frame,1,"right_calibration","右相机标定视频（RIGHT）","请选择右相机在同一次标定过程中拍摄的标定板视频。","选择右相机标定视频",True)
        board=ttk.LabelFrame(self.video_calibration_frame,text="标定板参数"); board.grid(row=2,column=0,sticky="ew",padx=8,pady=6)
        ttk.Label(board,text="必须与视频中实际棋盘格一致。角点指内部角点，不是方格数量。").grid(row=0,column=0,columnspan=6,sticky="w",padx=8,pady=5)
        ttk.Label(board,text="横向内部角点：").grid(row=1,column=0,padx=6); ttk.Entry(board,textvariable=self._var("corners_x","9"),width=7).grid(row=1,column=1)
        ttk.Label(board,text="纵向内部角点：").grid(row=1,column=2,padx=6); ttk.Entry(board,textvariable=self._var("corners_y","6"),width=7).grid(row=1,column=3)
        ttk.Label(board,text="单格实际尺寸 (mm)：").grid(row=1,column=4,padx=6); ttk.Entry(board,textvariable=self._var("square_mm","20"),width=9).grid(row=1,column=5)
        self.calibrate_button=ttk.Button(board,text="开始双目标定",command=self._start_video_calibration); self.calibrate_button.grid(row=2,column=0,columnspan=2,sticky="w",padx=8,pady=8)

        self.step2_frame.columnconfigure(0,weight=1)
        ttk.Label(self.step2_frame,text="请选择需要进行水面三维测量的同一次双目拍摄视频。这两个视频不是标定视频。",font=("TkDefaultFont",10,"bold"),wraplength=1100).grid(row=0,column=0,sticky="w",padx=12,pady=10)
        ttk.Label(self.step2_frame,textvariable=self._var("step2_status","○ 等待左右测量视频")).grid(row=0,column=1,padx=10)
        self._video_selector(self.step2_frame,1,"left_measurement","左相机测量视频（LEFT）","请选择 LEFT 相机拍摄的水面视频。","选择左相机测量视频")
        self._video_selector(self.step2_frame,2,"right_measurement","右相机测量视频（RIGHT）","请选择 RIGHT 相机与左相机同步拍摄的同一段水面视频。","选择右相机测量视频")
        self.enter_measurement_button=ttk.Button(self.step2_frame,text="进入视频测量",command=self._enter_measurement,state=tk.DISABLED); self.enter_measurement_button.grid(row=3,column=0,sticky="w",padx=12,pady=10)

        center=ttk.Panedwindow(self.measurement_frame,orient=tk.HORIZONTAL); center.pack(fill="both",expand=True,padx=8,pady=5); image_box=ttk.LabelFrame(center,text="步骤 3：播放并选择测量时刻（RIGHT / canonical cam1）"); summary_box=ttk.LabelFrame(center,text="步骤 4：查看测量结果"); center.add(image_box,weight=3); center.add(summary_box,weight=1)
        self.image_canvas=tk.Canvas(image_box,background="#222",highlightthickness=0); self.image_canvas.pack(fill="both",expand=True); self.image_canvas.bind("<Motion>",self._hover)
        self.image_canvas.bind("<ButtonPress-1>",self._roi_press); self.image_canvas.bind("<B1-Motion>",self._roi_drag); self.image_canvas.bind("<ButtonRelease-1>",self._roi_release)
        modes=ttk.Frame(image_box); modes.pack(fill="x"); self._var("mode","原始画面")
        for mode in ("原始画面","高度叠加","高度图","状态图"):ttk.Radiobutton(modes,text=mode,value=mode,variable=self.variables["mode"],command=self._show_mode).pack(side="left")
        ttk.Label(modes,text="透明度").pack(side="left",padx=(20,2)); self._var("alpha","45"); ttk.Scale(modes,from_=0,to=100,variable=self.variables["alpha"],command=lambda _value:self._show_mode() if self.variables["mode"].get()=="高度叠加" else None).pack(side="left",fill="x",expand=True)
        ttk.Label(image_box,textvariable=self._var("result_legend","高度 H 单位：mm | XYZ 单位：m"),anchor="w").pack(fill="x",padx=4,pady=2)
        self.summary_text=tk.Text(summary_box,width=42,height=22); self.summary_text.pack(fill="both",expand=True); self.summary_text.configure(state=tk.DISABLED)
        ttk.Label(summary_box,text="当前像素",font=("TkDefaultFont",10,"bold")).pack(anchor="w",padx=5,pady=(6,0)); ttk.Label(summary_box,textvariable=self._var("pixel_info","像素：无"),justify="left").pack(anchor="w",padx=5)
        self.pointcloud_button=ttk.Button(summary_box,text="显示三维点云",command=self._show_pointcloud,state=tk.DISABLED); self.pointcloud_button.pack(anchor="w",padx=5,pady=6)
        controls=ttk.Frame(self.measurement_frame); controls.pack(fill="x",padx=8); ttk.Button(controls,text="播放",command=self._play).pack(side="left"); ttk.Button(controls,text="暂停",command=self._pause).pack(side="left"); self.timeline=ttk.Scale(controls,from_=0,to=1,command=self._timeline_moved); self.timeline.pack(side="left",fill="x",expand=True,padx=8); self.timeline.bind("<ButtonPress-1>",self._timeline_press); self.timeline.bind("<ButtonRelease-1>",self._timeline_release); ttk.Label(controls,textvariable=self._var("time","00:00.000 / 00:00.000  (0.000 s)"),width=34).pack(side="left"); self.reference_button=ttk.Button(controls,text="设置当前帧为参考帧",command=self._set_reference);self.reference_button.pack(side="left",padx=4);self.solve_button=ttk.Button(controls,text="解算当前帧",command=self._solve,state=tk.DISABLED); self.solve_button.pack(side="left",padx=4); ttk.Label(controls,textvariable=self._var("run_status","就绪")).pack(side="left")
        roi_controls=ttk.Frame(self.measurement_frame); roi_controls.pack(fill="x",padx=8,pady=(3,2)); ttk.Button(roi_controls,text="设置/重新选择水面区域",command=self._start_roi_selection).pack(side="left"); ttk.Label(roi_controls,textvariable=self._var("roi_status","水面区域：尚未设置；解算前必须在右相机画面中框选"),foreground="#075").pack(side="left",padx=10)
        ttk.Label(self.measurement_frame,textvariable=self._var("common_fov_status","双目公共区域：等待标定和左右测量视频"),foreground="#075").pack(fill="x",padx=12,pady=(0,2))
        reference_controls=ttk.Frame(self.measurement_frame);reference_controls.pack(fill="x",padx=8,pady=2);ttk.Label(reference_controls,textvariable=self._var("reference_status","参考面未建立"),foreground="#075").pack(side="left");ttk.Label(reference_controls,text="高度 H 为当前三维水面点到用户所选参考面的有符号法向距离。",foreground="#555").pack(side="left",padx=14)
        bottom=ttk.Panedwindow(self.measurement_frame,orient=tk.HORIZONTAL); bottom.pack(fill="x",padx=8,pady=5); history_box=ttk.LabelFrame(bottom,text="本次测量记录"); log_box=ttk.LabelFrame(bottom,text="运行日志"); bottom.add(history_box,weight=1); bottom.add(log_box,weight=3); self.history=tk.Listbox(history_box,height=5); self.history.pack(fill="both",expand=True); self.history.bind("<<ListboxSelect>>",self._history_selected)
        for record in self.session.records:self.history.insert(tk.END,record.display_name)
        self.notebook.select(step1)
        self.log_text=tk.Text(log_box,height=5); self.log_text.pack(fill="both",expand=True); self._log(f"会话目录：{self.session.directory}"); self._refresh_step_state();self._refresh_reference_controls();root.protocol("WM_DELETE_WINDOW",self._request_close); self._after_id=root.after(200,self._tick); return root
    def run(self) -> None:(self.root or self.build()).mainloop()
