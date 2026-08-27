# HomeTank_004 Phase 4 人工标尺读数说明

状态：`MANUAL_REFERENCE_LOCATION_REQUIRED`

请只查看冻结的正式 R0 图像，不要调整同步、标定、WASS、参考平面或高度结果。

## 需要查看的时刻

| 场景 | 正式目标时刻 |
|---|---:|
| Static R0 | 10.012256 s |
| Wave R0 | 20.000000 s |

用户已提供：读取相机 `cam1`；Static `9.1 ± 1.0 mm`；Wave `9.2 ± 2.0 mm`；标尺数值向上增大。当前只缺两个水面线像素和人工像素定位不确定度。

## 点击操作

在仓库根目录打开 PowerShell，依次执行：

```powershell
$env:PYTHONPATH = "src"
python tools/manual_reference_picker.py --image experiments/real_video/HomeTank_004/manual_reference/static_cam1_canonical_reference.png --label static --coordinate-system canonical_cam1 --points-file experiments/real_video/HomeTank_004/manual_reference/manual_reference_points.yaml
python tools/manual_reference_picker.py --image experiments/real_video/HomeTank_004/manual_reference/wave_cam1_canonical_reference.png --label wave --coordinate-system canonical_cam1 --points-file experiments/real_video/HomeTank_004/manual_reference/manual_reference_points.yaml
```

1. Static 图打开后，点击“读取 9.1 mm 时尺子旁边的实际水面点”，按 Enter 或 `y` 确认。
2. Wave 图打开后，点击“读取 9.2 mm 时尺子旁边同一物理位置附近的实际水面点”，按 Enter 或 `y` 确认。
3. 打开 [manual_reference_points.yaml](manual_reference/manual_reference_points.yaml)，只补充两个 `pixel_uncertainty_px`，例如人工判断为 ±2 px 时填写 `2.0`。

`*_canonical_reference.png` 是按冻结 PTS 导出的未增强 RGB cam1 图，cam1 rotation 为 0°，所以 raw-to-canonical 是 identity。工具在用户确认后，严格复现 WASS 的两阶段坐标变换：先以冻结 `K1/D1` 和 `P=K1` 映射到 prepare 去畸变坐标，再以冻结运行时的零畸变 rectification `R/P` 映射到 computational cam0 坐标。它不会按分辨率缩放，也不会用最近邻反查 remap。原有 `static_cam1_reference.png`/`wave_cam1_reference.png` 继续作为冻结 rectified 身份证据，不再要求用户在其上点击。

如果默认 Python 报告缺少 OpenCV Python bindings，请为当前 Python 安装轻量、无 GUI 的坐标映射依赖：

```powershell
python -m pip install opencv-python-headless
```

点击窗口由 Python 标准 `tkinter` 与 Pillow 显示，OpenCV 只执行坐标数学映射。工具不检测标尺或水面，也不根据重建结果建议位置。

## 已登记字段与注意事项

不要把未知量填写为 `0`；未知时保持 `null`。标尺“向上增大”已按用户原话记录，但与冻结参考平面法向正号的物理对应仍须在最终计算前明确，不能凭名称假设。

## 比较方式

标尺变化量先按已填写的刻度方向转换为算法参考平面法向的正高度。算法端只查询人工水面线像素附近已经存在的 pixel–XYZ/height 观测，不插值生成点。正式局部读数采用局部中位数，同时保留最近点高度、点数、像素距离和局部离散度。

距离门、局部半径和最少点数当前保持 `null`，需在取得人工像素不确定度并检查冻结结果采样密度后确定。若附近没有观测，必须返回 `NO_VALID_RECONSTRUCTION_NEAR_REFERENCE`。两次读数仅相差 0.1 mm，而单次不确定度为 ±1 mm 和 ±2 mm；后续应优先报告绝对误差、读尺不确定度和局部 stereo spread，不把相对百分比误差作为主要指标。
