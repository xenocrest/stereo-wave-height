# 极简离线 GUI 调用盘点（先调查，后实现）

调查日期：2026-10-08。基线 `fix/reconstruction-quality@f4c8ead`，调查时工作区干净，无 AGENTS.md。新分支 `app/minimal-offline-wrapper`。旧 `app/`、audit/ 和 P0 科学接口保留。

## 当前实际路径

以下均已通过本机文件系统检查，不能用推测路径替代：

|依赖|实际位置|
|---|---|
|仓库|`D:/research/stereo-wave-height`|
|科学输出|`D:/stereo-wave-height-runs`|
|Python|`D:/stereo-wave-height-runs/wassgridsurface-0.11.4-venv/Scripts/python.exe`|
|WASS prepare/match/autocalibrate/stereo|`D:/wass/dist/bin/wass_*.exe`|
|FFmpeg|`D:/FormatFactory/ffmpeg.exe`|
|Praat|`D:/stereo-wave-height-runs/vieira2025-full-repro-20260916/sources/praat/Praat.exe`|
|WASS 源码|`D:/stereo-wave-height-runs/vieira2025-full-repro-20260916/sources/wass-src/wass-master`|
|wass_lowcost 原文件|`D:/stereo-wave-height-runs/vieira2025-full-repro-20260916/sources/wass_lowcost/wass_sync.py`|
|官方 gridding/plot CLI|科学 Python 同目录的 `wassgridsurface.exe`、`wassncplot.exe`|

本机 PySide6 6.11.2、wassgridsurface 0.11.4、wassncplot 2.5.3；不升级依赖。`examples/hometank004.yaml` 及指定四个 MP4 均存在。`examples/vieira_official.yaml` 为作者 TIFF 图像序列，不能伪造源视频 PTS。

## GUI → 现有入口 → 官方程序 → 文件

|GUI 功能|复用入口及实际执行|输入|输出|
|---|---|---|---|
|运行标定|`app.worker.run('calibrate')` → `pipeline.adapters.calibration.run` → `tools/vieira_intrinsics_from_raw.py` → OpenCV `findChessboardCornersSB`/`cornerSubPix`/`calibrateCamera`|左右标定视频、内角点列/行、格长、采样与 views 参数|`calibration/intrinsics_00/01.xml`、`distortion_00/01.xml`、`report.json`、WASS 配置|
|运行同步|`app.worker.run('sync')` → `pipeline.adapters.sync.run`；新壳仅替换 TLCC 调用目标为原文件执行适配器（见下节）|左右水面视频、官方音频窗口、工具路径、暂停时刻|`sync/sync.json`、`frames/cam0/1`、源帧整数 PTS/index/hash、Praat 原始输出|
|播放/暂停|QTimer 驱动现有 canonical OpenCV 解码显示（本机未装 Qt Multimedia，不新增依赖）；暂停使用现有 `tools.vieira_tlcc_sync.extract_source_frame`，不执行相关算法|视频、已记录官方 TLCC offset、requested time|canonical PNG、actual source PTS、index、delta_t；未取到身份显示 N/A|
|建立固定参考面|已有 `pipeline.run_pipeline.run_pipeline` 对用户暂停帧执行官方流程；读取官方 WASS plane 与官方 setup 定义的 grid Z=0，使用 `app.coordinates.bind/identity` 绑定|已完成标定、当前帧、原科学配置|原 `plane.txt`、`surface/config.mat`、P0 证书、绑定 reference JSON；无自行拟合|
|选择固定参考面|`app.core.reference_from_metadata` / `app.coordinates.require_match`|已有绑定 reference JSON、当前输入配置|保持原系数；不匹配显示 `REFERENCE_FRAME_MISMATCH`|
|解算当前暂停帧|`app.worker.run('reconstruct')` → 首次 `pipeline.run_pipeline`；有 reference 时 `app.fixed_run.run`|一个当前帧、标定配置、显式 fallback 设置、冻结 reference/setup|官方 workspace、mesh_cam.xyzC、mesh.ply、plane.txt、run_report.json|
|WASS 全流程|`pipeline.adapters.wass.run` → `wass_prepare.exe` → `wass_match.exe` → `wass_autocalibrate.exe` → `wass_prepare.exe` → `wass_stereo.exe`|官方图片对与配置|官方标定/匹配/点云/平面，不重写任何步骤|
|固定参考后的重建|`app.fixed_run.run` → prepare/stereo；复用已确认 K/D/R/T 与 setup，不重新配准|冻结官方坐标与当前源帧|新 mesh/grid/map，检查坐标身份|
|gridding|`pipeline.adapters.surface.run` 或 `app.fixed_run.run` → 官方 `wassgridsurface --action setup/grid`|官方点云、plane、P0 I12 输入契约、baseline 与已有 grid 参数|config.mat、coordinate_contract.json、gridded.nc|
|pixel map/官方绘图|相同 adapter → `wassncplot --savexyz --save-img --no-textoverlay --pxscale 1`|gridded.nc|`pixel/pixel_xyz/*.mat`、官方 PNG、已有 NPZ 格式转换|
|Measurement/Overlay|`app.core.load_result/measurement_image`、既有官方 map；颜色叠加仅显示数值|run、frame id、合法固定 reference|WASS undistorted cam0 与 map 共用光栅；raw 画面不查 H|
|Point Cloud|复用 `app.main.PointCloudView` / plyfile|官方 mesh.ply|显示已有顶点，抽样仅用于绘制，源 PLY 不改|
|Hover|复用 `app.core.hover`；结果加载时准备现有 XYZ/H|已生成数组、u/v|XYZ、H、timestamp、provenance；无数据 N/A，不做新科学计算|
|打开 HomeTank/Vieira 已有结果|同一结果读取模块，`app.coordinates.identity` 检查 P0 契约|run_report.json、frame id、已有或官方平面 reference|同一 Measurement/Point Cloud/Overlay/Hover；Vieira 单位 B 原样保留|

## 找到的重复科学实现与取舍

1. **OFFICIAL_TOOL_AVAILABLE / CURRENT_WRAPPER_REIMPLEMENTED**：`tools/vieira_tlcc_sync.py::extract_and_filter_audio/write_official_praat_script` 在仓库重新写了官方 FIR 与 Praat 文本。`src/synchronization/audio_sync.py` 另有 SciPy correlate 路径。新 GUI 不执行这些科学实现。旧文件原样保留。新子进程适配器直接 `runpy.run_path` 执行本机作者 `wass_sync.py`，只提供 `setup_sync` 配置、PCM 文件和配置好的 Praat 可执行路径；滤波系数、滤波和相关脚本生成均由作者原文件完成。

   原脚本是整体脚本而非 API，含 `/usr/bin/praat`、错误 Windows 分支、直接重命名源视频和基于帧数/VFR 重新编码部分。隔离目录仅放两份 FFmpeg PCM WAV；视频 glob 为空、camera_id 为空，所以不改源视频，也不执行旧帧重采样。仅对 Praat 的外部调用做 argv/Windows stdout 编码转换，拒绝未知外部命令。读取官方原始结果的全精度 offset，P0 I02 的现有 FFmpeg 帧提取与映射逻辑原样复用。此处是明确的 Windows/输入输出适配，不能称原脚本整体未经平台适配即正常运行。

2. **OFFICIAL_TOOL_AVAILABLE / CURRENT_WRAPPER_REIMPLEMENTED**：`pipeline.instantaneous_validation.schemas.reference_from_config` 的 `designated_static_water_frame` 分支自行 least-squares 拟合 grid。新 GUI 不调用这个拟合分支；官方 WASS 已输出 plane，wassgridsurface 已建立参考坐标，新 reference 绑定官方 grid 的 Z=0。用户选择现有 reference 时仅读取系数，不重新拟合。已有 `src/production_app.application.ReferenceService` 体现了官方 plane 路线，但其旧 setup 适配未保留全部新 P0 保护，所以新壳复用 P0 pipeline/coordinate 接口，不接入旧 service。

3. `src/reconstruction/`、`tools/reference_foundationstereo_trial.py`、LoFTR、OpenCV dense、手工点/旋转等旧实验路径包含自研或非本轮论文流程。保留，**不接入新 GUI**。不能因旧代码存在就宣称本轮重写算法。

4. 当前 `CommandRecorder` 及旧同步 wrapper 使用 `capture_output=True`，直到工具结束才写日志。新子进程仅换成实时流式 recorder，保留原 argv/退出码/日志格式和 StageFailure；GUI 使用单一 QProcess。旧文件不改。

5. 已有 `wass.run` 通过 fallback 配置决定切换，新壳在调用前要求 `allow_extrinsic_fallback=true`。新输入默认 false，修改输入使 reference/标定失效，不自动继承 HomeTank 参数。

## P0 保留与最小进程设计

- I01：只读取 WASS 去畸变测量图，完整范围缩放到 map 光栅；raw 视频不显示科学 hover。
- I02：原 `extract_source_frame/parse_source_frame` 不重写，显示真实 integer PTS/time_base 对应源帧；作者图像序列无 actual PTS。
- I03：播放、暂停帧及标定继续使用现有 canonical orientation；原视频预览不用于科学 hover，暂停后的测量输入由 P0 入口生成并显示。
- I12：原 plane_contract、证书、coordinate identity 和 fixed_run 拒绝策略保留，不自行修旋转/高度。
- 一个 QProcess、一个任务名、实时两路日志；Windows Job Object 持有进程树，取消/关闭终止树。finished、FailedToStart、crash、user terminate 均统一清空 current_process。
- 先建窗口并验证空闲关闭，再接文件选择和 runner，再接标定、同步、暂停、重建和结果。无队列/任务图/数据库/质量评分/P1/打包。

官方运行接口依据：[Qt QProcess](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QProcess.html)、[Windows Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)。科学接口依据上述本机已检查的作者原文件及仓库 adapter。
