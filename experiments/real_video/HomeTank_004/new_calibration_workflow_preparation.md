# HomeTank_004 新标定采集与验证流程准备

状态：`NEW_CALIBRATION_WORKFLOW_READY`  
界面状态：`DEMO_UI_FROZEN`

本轮没有重新标定、没有运行 WASS，也没有修改 GUI、正式重建或既有标定结果。目标是让新视频到手后先验收采集质量，再决定是否值得标定和进行唯一一次 WASS A/B。

## 明日流程

1. 用 `calibration.capture_qa` 以 2 Hz 快速抽帧，复用正式 9 × 6 OpenCV SB 检测器。
2. 检查左右各自九宫格覆盖、双侧同时检测、按候选分位数划分的尺度、姿态重复和棋盘区域清晰度。
3. 只有 `CAPTURE_READY_FOR_CALIBRATION` 才采用工具输出的、互不重叠的确定性 training/held-out ID。
4. 用 `calibration.compare_calibrations` 在同一 held-out 集上比较 OLD/NEW。
5. 只有 `CALIBRATION_READY_FOR_WASS_AB` 才按 `calibration_wass_ab_template.yaml` 对 NEW 运行一次 WASS；OLD 复用冻结结果。

推荐第一条命令：

```powershell
$env:PYTHONPATH='src;.'
python -m calibration.capture_qa --left <NEW_LEFT_VIDEO> --right <NEW_RIGHT_VIDEO> --quick --output D:\stereo-wave-height-runs\HomeTank_004\new-calibration-capture-qa
```

若相机 metadata 要求规范化方向，应显式附加 `--left-rotate 180` 或 `--right-rotate 180`；工具不会自动猜测方向。

## 旧数据工具自检

复用冻结的 192 对检测结果执行 QA，不重新解码视频。结果为 `CAPTURE_INCOMPLETE_NEEDS_MORE_VIEWS`：LEFT 九宫格仅 3/9 有候选，RIGHT 仅 2/9；工具识别出顶部、左右边缘和角落缺失。该结果来自通用覆盖规则，没有针对 HomeTank_004 硬编码。

## 比较与门禁

OLD/NEW 比较输出 mono RMS、stereo RMS、epipolar RMS、held-out rectified vertical median/RMS/P95/max、baseline 对 70 mm 的 sanity、相对旋转及 K/D/R/T 有限性。门禁要求 held-out RMS 与 P95 至少改善 30%，epipolar RMS 不恶化超过 5%，baseline 位于 70 mm 的 ±5%，参数有限且内参合理，并且 held-out 最大误差不恶化。

WASS A/B 锁定视频、目标时刻、同步帧与模型、0.6165 ms 同步残差、rectification policy、matcher/stereo、后处理和 water ROI；唯一变量是 K/D/R/T 标定文件。
