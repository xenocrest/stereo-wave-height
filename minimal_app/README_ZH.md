# 极简离线 WASS 演示

双击仓库根目录 `run_minimal_offline.cmd`。也可使用现有科学 Python：

```powershell
cd D:\research\stereo-wave-height
& 'D:\stereo-wave-height-runs\wassgridsurface-0.11.4-venv\Scripts\python.exe' -m minimal_app.main
```

初始四个输入为空，fallback 未允许。点击“打开配置”可选择 `examples/hometank004.yaml`（该配置明确允许历史完整标定 bundle）或自己的 YAML。工具路径、标定 views、WASS/grid 参数沿用该 YAML；新视频不自动继承 HomeTank 参数。

1. 选择左右标定视频与左右水面视频，输入棋盘内角点列/行、格长、基线和输出目录。
2. 点击“运行标定”；完成后“运行同步”。顶部始终显示任务、真实阶段、处理对象、计数、耗时和状态，底部实时显示原始两路日志。
3. “载入左右视频”后播放/暂停或拖动时间。点击“读取当前暂停帧”由 P0 入口生成 canonical 源帧，显示 actual PTS/delta_t。播放中的近似预览不冒充源帧时间。
4. 在用户指定参考时刻点击“用当前暂停帧建立参考面”。官方 WASS/官方 grid 完成后冻结其 Z=0 平面与坐标身份；不自行拟合静水面，不保证这个时刻物理上静水。reference JSON 位于本次任务目录。
5. 暂停到测量时刻，“解算当前暂停帧”。复用已有 fixed_run，官方 prepare/stereo/grid/ncplot 生成新结果；固定 K/D/R/T/setup/reference 不自动变更。
6. “结果”区域包含 Measurement Image、3D Point Cloud、Overlay。hover 仅读取已有 XYZ/H；无数据 N/A。测量图是 WASS 去畸变图，原视频无 H hover。
7. “打开已有结果”选择 `run_report.json` 和现有 frame id。HomeTank 与 Vieira 使用同一读取模块；没有独立 reference 时查看官方 grid Z=0，**不替换当前用于后续重建的 reference**。Vieira B 单位不转换成 m/mm。

随时可“终止当前任务”。结束、失败、崩溃或终止后 current_process 清空并恢复按钮。运行中关闭窗口可选择“继续等待 / 终止任务并退出 / 取消”。Windows kernel Job Object 负责子孙进程；绑定完成前 worker 等待 stdin 启动握手，防止子进程脱离。

标定面板区分左/右相机的完整视频扫描、选择视图、OpenCV calibrateCamera、保存视图和 K/D。扫描百分比来自实际已读取帧数 / 解码器报告总帧数；保存视图百分比来自实际已保存数 / 选用数。扫描日志约每 0.75 秒输出一次，扫描结束强制输出最终计数。未知或失真的分母不显示百分比。

OpenCV calibrateCamera、Praat TLCC、当前 FFmpeg 调用、WASS 和 gridding 未提供可靠总工作量，显示 busy 进度条、真实阶段、耗时与原始日志。不会按时间估算百分比，也不设置人为超时。完成、失败、用户终止后保留最终阶段、计数、状态、日志路径和退出码，直到下一个任务开始。科学计数仅描述处理过程，不代表标定或水面测量质量。

统一协议和真实桌面验收见 [进度透明度验收](../docs/MINIMAL_GUI_PROGRESS_ACCEPTANCE_ZH.md)。协议只用于自有 wrapper 的 stdout，官方 stdout/stderr 原样保留；不改变数值计算、循环顺序或科学参数。

运行输出不写入仓库：使用配置 output_root/project/gui/任务_时间。每次生成独立 `project.yaml`、完整 `console.log`、已有工具日志、成功时 `result.json`。失败/取消目录保留用于查看，程序不自动换帧、调参、补点、重试或改 reference。

本 GUI 是 Windows 本机外壳，不打包 EXE。旧 app/ 原样保留。科学调用与发现的旧实现见 `docs/MINIMAL_GUI_CALL_MAP_ZH.md`。本轮不进行任何 P1 科学优化。
