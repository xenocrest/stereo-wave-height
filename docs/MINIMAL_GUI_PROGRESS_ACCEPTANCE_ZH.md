# 极简 GUI 进度透明度验收

日期：2026-10-08。分支：`app/minimal-offline-wrapper`。基线：Stage1 `d8fabce`。状态：`MINIMAL_GUI_PROGRESS_TRANSPARENCY_COMPLETE`。

本轮只增加 progress/status/log visibility。科学算法、参数和 P1 未修改。`app/`、`pipeline/`、`src/`、第三方源码均无差异；标定工具只增加纯日志 instrumentation。没有提前停止扫描、改变采样、重新选帧、并行标定、缓存旧结果或新增科学计算。

## 极薄 stdout 协议

自有 wrapper 输出一行 `MINIMAL_PROGRESS <json>`，必需字段为 `stage`；可选字段为 `task`、`side`、`object`、`tool`、`current`、`total`、`unit`、`counts`、`elapsed_s`、`note`。例如测试用协议：

```text
MINIMAL_PROGRESS {"task":"calibrate","stage":"checkerboard_scan","side":"left","object":"input.mp4","current":4200,"total":7012,"unit":"frames","counts":{"sampled":354,"detections":149,"target_views":50}}
```

示例数字不充当人工验收数据。实际扫描统计见下表。GUI 接受跨 stdout chunk 的完整协议行；损坏的协议不会改变科学任务成功与否。原始 stdout/stderr，包括 STAGE 和协议行，继续显示并保存。

同一 `ProgressReader` 和顶部面板服务所有任务。LiveRecorder 在已有真实 STAGE 调用边界发事件，原始 stage 名保留在日志中。GUI 仅翻译显示名称，不建立任务队列、工作流引擎或依赖图。最多同时一个科学任务。

只有有限数值且 `0 <= current <= total`、`total > 0` 才显示百分比。扫描使用实际读取数 / 解码器报告帧数；保存视图使用实际保存数 / 实际选用数。OpenCV calibrateCamera、视图选择、FFmpeg/Praat、WASS、grid/ncplot、结果读取没有可靠总量，显示 busy mode 和说明，不按运行时间猜百分比。不会增加任意任务超时。

标定原循环每约 0.75 秒输出扫描计数，结束时强制输出最后值。`calibrateCamera` 前显示实际选用视图数和棋盘规格，返回后显示原始 RMS；K/D、命令及完整科研详情仍在日志和输出文件中。处理计数不被解读为测量质量。

结果读取事件覆盖 worker 的读取 XYZ/H、Measurement Image、结果序列化，以及 GUI 的读取 NPZ、准备 Overlay、读取 PLY、显示完成。快速阶段正常更新，不人为 sleep。任务完成、失败、终止后保留任务名、最后/失败/终止阶段、计数、总耗时、日志路径和真实根进程退出码。Windows Job 终止可能返回根进程 exit=0，状态仍按用户终止标志显示 USER_TERMINATED。

## 真实桌面专项验收

通过 Windows 原生桌面操作实际运行 HomeTank_004，不以 mock 替代。保留原 6×9 内角点、0.02 m 格长、5 Hz 采样、50 个目标视图、12 个最低视图、0.07 m 基线和 30 s TLCC 窗口。仅改变验收输出目录。

证据根目录：`D:/stereo-wave-height-runs/minimal-progress-acceptance-20261008`。`desktop_progress_steps.json` 保存真实顶部控件读数，PNG 保存画面，各任务 `console.log` 保存完整输出。正式仓库不提交原视频、大型科学产物或包含视频元数据的原始日志。

最终完整观察运行：`hometank004/gui/calibrate_20261008_172245_988349`，PROCESS_COMPLETE，277.2 s。另一次完整运行 `calibrate_20261008_171606_149481` 的左相机选择/标定/保存过程也通过桌面持续观察。

|相机|完整扫描帧数|实际采样数|完整棋盘候选|实际选用|扫描耗时|
|---|---:|---:|---:|---:|---:|
|左|6968 / 6968|581|230|50|133.687 s|
|右|7040 / 7040|587|328|50|119.585 s|

这里“扫描耗时”来自扫描事件的 elapsed_s，不包含视图选择、OpenCV 标定及结果保存。末次运行原始 RMS：left 4.149856500614477 / right 5.522525225570179 px。

实际桌面观察到：左扫描 → 左选择 → 左 OpenCV calibrateCamera → 左保存 → 右扫描 → 右选择 → 右 OpenCV calibrateCamera → 右保存 → 左右标定完成。右 OpenCV 阶段很短，快速控件观察在任务累计 267.5 s 捕获到该阶段、50 视图、6×9 棋盘及“该函数未提供可靠百分比”；紧随其后的截图已进入保存阶段，不把该截图冒称为标定画面。

|专项|真实操作和结果|
|---|---|
|扫描真实变化|左 2545/6968、213 采样、94 棋盘；右 5245/7040、438 采样、257 棋盘等控件读数均来自运行现场|
|中途终止|`calibrate_20261008_164652_532274`；左扫描 1633/6968、137 采样、90 棋盘时 USER_TERMINATED；30.1 s；进程树停止，读数保留|
|终止后重启|同一窗口再次点击标定，正常重新扫描并完成左右计算|
|忙碌关闭取消|真实关闭弹窗显示任务名和继续等待/终止并退出/取消；取消后原扫描继续更新|
|忙碌关闭退出|`calibrate_20261008_172808_842425`；实际点终止并退出，USER_TERMINATED；窗口关闭，CIM 检查科学子进程清空|
|视频同步|`sync_20261008_173303_655081`；27.6 s，PROCESS_COMPLETE；左右音频提取 → 作者音频滤波 → Praat TLCC → 同步偏移解析 → 实际源帧提取 → 最终摘要|
|当前帧重建|`reconstruct_20261008_173405_537513`；21 s 目标，51.7 s，PROCESS_COMPLETE，147251 PLY 顶点，Measurement Image 正常回载|

同步和重建的最终 offset 均为 -0.07507001632731439 s；21 s 帧 Left actual PTS 21.001544444 s / Right 20.933888889 s / residual 7.414460772 ms。偏移解析等极短阶段仍写入协议日志。

重建复用 Stage1 已有固定参考配置，reference ID `official_wass_plane_56952b7e095534b9`。实际官方阶段为 `fixed_prepare_000000` → `stereo_000000` → `wassgridsurface_grid` → `wassncplot`，然后结果读取和显示准备。固定路线未调用 match、autocalibrate 或 setup，因此没有显示这些未运行阶段。新参考任务仍沿用已有完整流程，各实际 STAGE 由同一 LiveRecorder 发事件，最后另发保存固定参考面事件。

实际失败或用户终止保留当前阶段；新任务重置进度。完成/终止后 current_process 清空，输入恢复、停止按钮关闭，没有残留 busy。未操作用户原有 Stage1 窗口。

## 科学回归与官方运行间波动

自动化冻结检查：去掉本轮纯进度节点后，标定 `detect`、`descriptor`、`select_diverse`、`object_points`、`save_matrix`、`run` 的 AST SHA256 与 Stage1 一致。既有数值参数、调用顺序和分支未改变。

真实左右标定的采样数、检测数、全部角点和选用帧与 Stage1 完全一致。K/D 并非逐位相等：首次新运行 left K 最大差 1.957e-10 px、D 4.511e-12；right K 4.387e-7 px、D 4.114e-9；RMS 差均在 3.553e-15 px 以内。独立对同一原始角点直接重复官方 cv2.calibrateCamera 3 次，不输出本协议，right K 本身范围 2.706e-6 px、D 1.837e-8。没有以输出 XML 哈希相等强制判断官方浮点计算。

同步 offset、实际源 PTS 和 residual 与 Stage1 完全一致；11 个可比科学输入文件（K/D/R/T、官方配置、固定 config.mat、源帧）SHA256 全部一致。

固定科学结果的接口回归：把新 GUI 的已有 science 结果交给原 Stage1 worker 的 view 入口读取，XYZ、H、source、Measurement Image 全数组完全相同，包括 NaN。已有冻结测试 fixture 全部通过。

新运行的 WASS 点云/plane/grid 与历史运行并非逐位相同。为核查，在临时目录从 `git archive d8fabce minimal_app` 提取原 Stage1 模块，使用同一输入重新运行。对照使用 PYTHONSAFEPATH 和明确的 PYTHONPATH 保证根进程及子进程均加载原模块；`stage1-control-no-progress` 日志中 MINIMAL_PROGRESS 行数为 0。原 Stage1 自身的复跑同样产生不同的 mesh、plane 和 Z/H；历史与原代码复跑公共有限 H 最大差 0.055090 m，历史与新 GUI 运行为 0.054864 m。这里明确保留运行间波动，不能据此声称当前 HomeTank 的物理结果准确，也不进行任何科学修正。

可比 NetCDF scale/count/time/workdir、X_grid、Y_grid、Kx/Ky、maskZ、cam0images/cam0masks 完全相同；Z 受官方运行间差异影响。完整回归数据在证据目录的 `calibration_regression.json`、`scientific_inputs_exact.json`、`frozen_view_exact.json`、`output_regression.json`、`stage1_repeat_comparison.json`、`stage1_control_comparison.json`。

第三方 P0 清单的 64 个源码文件重新计算 SHA256，改变数为 **0**。没有修改 WASS、OpenCV、TLCC 或 gridding 源码/算法，也未进行 P1。

## 测试

全量 pytest：**590 passed、1 skipped、25 warnings、7 subtests passed**，72.52 s。唯一 skip 为未配置外部 OpenCV golden dataset 的既有测试。最后一次纯显示文案/对象名称调整后再跑极简 GUI 测试：**16 passed**，4.30 s。`git diff --check` 通过。

覆盖真实 QProcess 分片 stdout、协议解析、不可靠分母拒绝、未知工作量 busy、终止/失败/完成后摘要、重启重置、Windows 子孙进程生命周期、关闭三种选择、既有固定参考及科学 AST 冻结。
