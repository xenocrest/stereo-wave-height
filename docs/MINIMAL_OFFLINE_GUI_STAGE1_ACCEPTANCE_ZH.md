# 极简离线 GUI 第一阶段验收

日期：2026-10-08。本阶段仅证明 GUI 外壳可调用现有科学工作流，不证明 HomeTank 水面有效或测量准确。科学算法、参数优化、P1 均不在本轮范围内。

## 交付范围

基线为 `fix/reconstruction-quality@f4c8ead`，新分支 `app/minimal-offline-wrapper`。启动入口为仓库根目录 `run_minimal_offline.cmd`，模块入口 `python -m minimal_app.main`。初始输入为空；新视频不自动继承 HomeTank fallback。

正式代码新增 7 个文件：6 个 Python 文件及 1 个 CMD。另有 1 个测试模块、README、调用盘点和本验收记录。

|文件|职责|
|---|---|
|minimal_app/__init__.py|包标识|
|minimal_app/main.py|输入、参数、播放暂停、单任务界面、关闭确认|
|minimal_app/runner.py|单一 QProcess、实时两路日志、Windows 进程树生命周期|
|minimal_app/worker.py|调用既有入口、流式命令 I/O、读取官方参考及结果|
|minimal_app/tlcc.py|执行原作者 wass_sync.py；只适配 WAV 输入、Windows Praat 路径与 stdout|
|minimal_app/viewer.py|复用 P0 测量图、点云、Overlay 与 hover|
|run_minimal_offline.cmd|使用已安装科学环境启动 GUI|

完整工具、输入、输出和旧代码盘点见 `MINIMAL_GUI_CALL_MAP_ZH.md`，该文档先于 GUI 实现创建。标定调用现有 OpenCV wrapper；同步执行作者原 `wass_sync.py` 与 Praat；重建调用官方 WASS prepare/match/autocalibrate/stereo，固定坐标后复用 prepare/stereo；gridding/plot 调用官方 wassgridsurface/wassncplot。无新拟合、相关、立体匹配、网格或高度算法。旧复制的 FIR/Praat 生成与 least-squares reference 路径已在盘点中明确标识，新 GUI 不执行它们。

第三方修改为 0；P0 清单 64 个文件重新计算 SHA256 均一致。旧 app/、pipeline/、tools/、src/、audit/、fixes/ 相对 f4c8ead 无差异。I01 去畸变光栅、I02 实际源 PTS、I03 canonical orientation、I12 官方坐标契约与拒绝机制均复用原接口。

## 真实桌面操作

通过 Windows 桌面 GUI 实际点击文件选择、任务按钮、播放暂停、结果标签页、关闭对话框和鼠标查询。以下不是 pytest 的替代描述。

证据根目录：`D:/stereo-wave-height-runs/minimal-offline-acceptance-20261008`；`desktop_steps.json` 保存操作与窗口树，`desktop_*.png` 保存截图；各任务的 `console.log` 保留完整 stdout/stderr。正式仓库不提交原视频、点云、网格及带视频 GPS 的原始日志。

|操作|实测结果|
|---|---|
|四份视频选择|四个原生文件对话框均选入用户指定文件|
|标定|calibrate_20261008_151147_021963；PROCESS_COMPLETE，263.2s；原 OpenCV RMS left 4.149856500614472 / right 5.522525225570178 px|
|同步|sync_20261008_151641_861810；PROCESS_COMPLETE，26.6s；官方 offset -0.07507001632731439s|
|播放/暂停|左右画面播放推进后暂停；P0 源帧读取单独运行，显示 requested / actual PTS / delta_t；近似播放不显示有效源帧身份|
|20s 源帧|Left 20.00187777777778s；Right 19.933866666666667s；delta 7.058905216ms|
|20s 固定参考|reference_20261008_152152_654126；PROCESS_COMPLETE，77.1s；官方全流程及 grid/ncplot 完成；132,908 PLY 顶点|
|21s 当前帧解算|reconstruct_20261008_153228_140365；PROCESS_COMPLETE，50.4s；147,422 PLY 顶点；Left 21.001544444s / Right 20.933888889s / delta 7.414460772ms|
|同一 reference|两次结果 reference JSON 完全一致；ID official_wass_plane_56952b7e095534b9；官方 config.mat 逐字节一致，SHA256 9b2ab06870b62ed86a7055f5f1e130f00c5401b6673f9d42b610b58fc9a0bd38|
|HomeTank 显示|Measurement Image、3D Point Cloud、Overlay 均可切换；u1469/v780 在 20s 读 H4.5123mm，21s 读 H6.9458mm，与 NPZ 一致；u77/v123 NO_DATA 显示 N/A|
|Vieira 同一查看器|打开 reconstruction-quality-p0-20261001/final/Vieira/run_report.json，frame0，5.0s 完成；653,518 顶点；同三个显示标签页；u1276/v508 H0.3926892 B，不伪造 m/mm 或视频实际 PTS|

HomeTank 沿用显式允许的历史完整标定 bundle，界面显示 EXTRINSICS_FALLBACK；未自动换帧、改 WASS/grid 参数、换参考或提高科学评分。参考为官方坐标中 Z=0，physically_validated=false。原工具的 texture/DPI 警告保留在日志中。

## 任务、失败、关闭与恢复

界面顶部显示具体任务名、PROCESS_RUNNING/PROCESS_COMPLETE/PROCESS_FAILED/USER_TERMINATED 与耗时。底部实时追加 stdout/stderr，结束后完整记录仍在独立输出目录。一个 QProcess 管理 worker；worker 在 Windows Job Object 绑定前等待 stdin RUN，取消或关闭 Job 时结束整棵子孙进程树。

真实桌面已验证：运行中取消同步后空闲，再次同步成功；不存在 FFmpeg 路径导致 PROCESS_FAILED 后按钮恢复，同一窗口更换正确配置后标定/同步/参考/重建成功；空闲关闭成功；运行中关闭显示具体任务及“继续等待 / 终止任务并退出 / 取消”；继续等待/取消关闭均继续运行；选择终止退出窗口消失、科学子进程无残留。完整后代取消和 crash/FailedToStart 恢复另由自动测试覆盖。

旧 GUI 另行启动，HomeTank 120s 任务用于延长输入读取等待，不用于科学调参。再次点击同步实际弹出“已有任务正在运行”；关闭窗口实际弹出“请等待当前科学工具结束后再关闭程序”，没有终止入口，需外部 taskkill /T 清理本次测试树。截图为 desktop_legacy_busy.png / desktop_legacy_close.png。此实测复现了用户无法取消/退出的等待现象；没有证明科学任务永久死锁或所有历史触发原因。旧 GUI 保留原样，新入口以显式终止和统一状态清理解决已测路径。

最终源码重新启动后完成 Vieira 与 HomeTank 同一查看器验证。时间输入框失焦只更新近似预览，不先抢占随后点击的任务；读取实际源帧由暂停/显式读帧入口执行，时间变更立即隐藏旧结果及 PTS。

## 自动验证与 Git

最终源码全套 pytest：**585 passed, 1 skipped, 25 warnings, 7 subtests passed，48.47s**。新增测试 11 个，覆盖实时双通道、结束后重启、FailedToStart/非法命令/非零退出、crash、立即取消、子孙进程树、关闭选择、输入绑定、结果读取异常、旧帧失效、时间编辑不抢占、官方 reference 不拟合。唯一 skip 为原 OPENCV_GOLDEN_DATA_DIR 未设置；HomeTank/Vieira 上述桌面验收均已实际执行。

测试使用既有科学 Python、PYTHONPATH=仓库及 src、QT_QPA_PLATFORM=offscreen，TEMP/TMP/basetemp 为 D 盘 ASCII 路径，满足旧工具路径契约。pytest-final-source.txt 为最终全套测试日志。output_checks.json / third_party_hashes.json 为独立输出与第三方一致性证据。

提交前检查 staged diff --check，确认只新增上述外壳/文档/测试文件；随后提交并推送 app/minimal-offline-wrapper，最终 commit、远端 SHA 与 clean 状态记于交付报告。
