"""Small stdout protocol for wrapper observations; never estimates work."""
import json
import math
import os

PREFIX = "MINIMAL_PROGRESS "


def emit(stage, **fields):
    print(PREFIX + json.dumps(dict(task=os.environ.get("MINIMAL_PROGRESS_TASK", ""),
        stage=stage, **fields), ensure_ascii=False), flush=True)


class ProgressReader:
    def __init__(self):
        self.buffer = ""

    def feed(self, text):
        self.buffer += text
        events = []
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            if not line.startswith(PREFIX):
                continue
            try:
                value = json.loads(line[len(PREFIX):])
                if isinstance(value, dict) and isinstance(value.get("stage"), str):
                    if not isinstance(value.get("counts", {}), dict):
                        value["counts"] = {}
                    for key in ("side", "object", "tool", "note"):
                        if key in value and not isinstance(value[key], str):
                            value[key] = str(value[key])
                    events.append(value)
            except (ValueError, TypeError):
                pass  # A log protocol error cannot fail a scientific task.
        return events


def fraction(event):
    current, total = event.get("current"), event.get("total")
    if (isinstance(current, (int, float)) and not isinstance(current, bool)
            and isinstance(total, (int, float)) and not isinstance(total, bool)
            and math.isfinite(current) and math.isfinite(total) and 0 <= current <= total and total > 0):
        return current / total
    return None


LABELS = {
    "starting": "启动已有工作流", "load_config": "读取任务配置",
    "checkerboard_scan": "视频扫描 / 棋盘检测", "view_selection": "选择标定视图",
    "calibrate_camera": "OpenCV calibrateCamera", "calibration_validation": "读取标定输出 / 原有结果检查",
    "save_calibration": "保存标定视图", "save_matrices": "保存 K/D 和标定报告",
    "camera_complete": "相机标定完成", "calibration_complete": "左右相机标定完成",
    "opencv_calibration_left": "左相机 · 打开标定视频", "opencv_calibration_right": "右相机 · 打开标定视频",
    "audio_extract": "提取相机音频", "official_audio_filter": "作者音频滤波 / Praat 脚本生成",
    "praat_tlcc": "Praat / wass_lowcost 音频 TLCC", "parse_sync_offset": "解析同步偏移",
    "source_frame": "提取实际源帧 / 生成对应关系", "sync_complete": "视频同步完成",
    "wass_lowcost_tlcc": "运行作者视频同步入口", "autocalibrate": "WASS autocalibrate",
    "generate_matcher_config": "生成官方 WASS matcher 配置",
    "generate_stereo_config": "生成官方 WASS stereo 配置",
    "wassgridsurface_setup": "wassgridsurface setup", "wassgridsurface_grid": "wassgridsurface grid",
    "wassncplot": "wassncplot · 生成官方 pixel mapping",
    "read_results": "读取已有 XYZ/H 结果", "measurement_image": "读取 Measurement Image",
    "serialize_view": "准备 GUI 结果文件", "save_reference": "保存固定参考面",
    "read_view": "读取 GUI NPZ 结果", "prepare_overlay": "准备 Overlay",
    "prepare_cloud": "读取 PLY / 准备三维点云显示", "display_complete": "结果显示准备完成",
    "preview_complete": "实际暂停源帧读取完成", "save_result": "保存任务结果摘要",
}


def stage_label(event):
    stage = event.get("stage", "starting")
    label = LABELS.get(stage, stage)
    if "_prepare_" in stage:
        label = "WASS prepare · 图像准备"
    elif stage.startswith("match_"):
        label = "WASS match · 特征匹配"
    elif stage.startswith("stereo_"):
        label = "WASS stereo · 密集双目重建"
    side = {"left": "左相机", "right": "右相机"}.get(event.get("side"))
    return f"{side} · {label}" if side else label


COUNT_LABELS = {"sampled": "已采样", "detections": "完整棋盘", "target_views": "目标视图",
    "used_views": "实际采用视图", "rms_px": "RMS (px)", "board": "棋盘内角点",
    "offset_s": "Right - Left offset (s)", "residual_ms": "当前帧 residual (ms)",
    "source_frame_index": "源帧 index", "actual_pts_s": "Actual PTS (s)"}


def counts_label(event):
    return " | ".join(f"{COUNT_LABELS.get(key, key)}：{value}" for key, value in event.get("counts", {}).items()) or "暂无可用计数"
