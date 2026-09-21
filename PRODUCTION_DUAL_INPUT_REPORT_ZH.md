# 正式 V1：视频 / 作者图像序列双输入集成记录

起点：`bugfix/project-management-flow` / `0d564528550e30623352bb141bfe5ab05b6ff8e6`。开发分支：`app/production-workflow-v1-dual-input`。原正式分支、旧演示版本、Golden Demo 与用户原项目文件保留。

## 架构与算法边界

同一个正式 Qt 桌面程序支持 StereoVideoSource 与 StereoImageSequenceSource。输入适配器只做文件 IO、配对、metadata、seek 与原图复制；所有数据共用官方 prepare / match / autocalibrate / stereo、wassgridsurface、wassncplot / WaveView 以及当前帧映射读取和导出服务。

没有实现新 stereo、三角化、平面拟合、插值、高度修正、语义筛选或 ROI。阶段状态统一记录 NOT_READY / COMPUTED / PROVIDED / FALLBACK / FAILED；失败保留真实官方命令、workspace、返回码和日志，不伪造结果。

## 作者样例来源

[wass_lowcost 官方仓库](https://github.com/matheusdpv/wass_lowcost)，固定提交 `688dfaf1d88f270cf3d7cd3db4b49369ebe52871`。从固定提交的 raw 文件下载 README、config 与左右各 5 张 TIFF，未重新编码为 MP4。原始下载目录：

`D:/stereo-wave-height-runs/vieira-official-sample-20260918-source/wass_lowcost-688dfaf1d88f270cf3d7cd3db4b49369ebe52871/`

实际图像为 1920×1080；作者 README 标称 12 Hz（其文字 1080×720 与实际文件尺寸不一致，程序以实际文件为准）。作者已经同步，sync=PROVIDED，不执行 TLCC。作者 config 中四个 K/D XML 原样复制；该提交没有 R/T，外参通过程序实际运行官方 WASS 五帧 prepare → match → autocalibrate 获取，不冒称作者提供。

作者未公开样例的实测基线。B=1 **仅定义基线归一化单位**：GUI 显示 X/B、Y/B、Z/B、H/B，不给出伪造的毫米高度。官方 NetCDF 默认的 mm 标签没有修改；使用此样例导出必须结合 manifest 的 `reference.units=baseline` 解释，不能声称这些是毫米实测值。参考采用选定样例帧的官方 WASS plane → 官方 setup，不认定该海面帧是静水。

## HomeTank 崩溃 A/B

用户 EXE 实际日志：

`D:/stereo-wave-height-runs/production-workflow-v1-projects/HomeTank_004_example/requests/c5bcd3cc9bb3405ea7421f1c88c10f4b.log`

其 reference workspace：`jobs/e7d31f2e41894e689d0fed9d6dbd8b9b/reference/workspaces/000000_wd`；stereo config：`jobs/40bbad73a88544a5b9c42b05c7cb442c/config/stereo_config.txt`。普通 PowerShell 原样运行同一个 WASS binary、配置及 workspace，同样失败，返回 −1073740791；GUI 返回 3221226505。二者都是 **0xC0000409**。

原始官方日志先报 `Vertical stereo not supported`，继而 OpenCV 4.6 `!_src.empty()` / `cv::cvtColor` 断言；竖向 rectification 没有正常生成图像，后续调用触发原生崩溃。依据 [WASS 官方 dense stereo 文档](https://www.dais.unive.it/wass/documentation/stereo.html)，这类竖向双目布局不受支持。结论仅限这条复现命令：**不是 A 成功 / B 失败的 GUI-only 环境问题**，不能靠 DLL 调整保证该数据外参可用。没有修改 WASS 检查、R/T 或标定算法。

仍按 [PyInstaller 官方外部程序指导](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html#launching-external-programs-from-the-frozen-application) 实现清洁环境：进程创建期间清除冻结程序 DLL 搜索目录，剔除 bundle PATH 和 Qt/PyInstaller 变量，随后恢复 GUI DLL 设置；QProcess 与 subprocess 都指定明确工作目录。启动时有超时限制的工具链检查报告实际路径、状态、版本/检测输出。wasscli 为交互菜单，使用模块导入及版本探测，不能假装其有 `--version` 接口。

## 验收记录

双项目使用同一个最终 EXE、同一个 V1 主窗口验收，作者样例与 HomeTank 原始视频流程均已完成最终包验收。结论为 **PRODUCTION_WORKFLOW_V1_DUAL_DATASET_PASS**；这是正式软件流程通过，不是物理精度验证通过。

已完成的真实 GUI 检查：作者样例项目实际生成五帧匹配/autocalibration、新参考面、第二张原图的当前帧官方重建与格网/NetCDF/叠加。该帧 PLY 点数 632,660；鼠标实际查询像素 (963,658)，H/B=−0.588661。没有加载旧点云或 Golden Demo。该次任务目录分别为 `jobs/25245f672fd247088046d7dc62a32db1`（外参）、`jobs/58dfedd341b84fcd944962409f8450b5`（参考）及 `jobs/a9e4b75808f649a0b9e5aed23ecd9a92`（当前帧）。

最新最终包于 2026-09-18 11:42 构建完成。旧验收窗口均已正常关闭，仅启动一个新 V1 主窗口（2165510），后续 3D 与目录选择是该主窗口的子窗口，不是第二个程序实例。最新包实际重建第三对作者 TIFF（LEFT/RIGHT 时间 0.166666667 s），任务 `jobs/71b29afde7924489bcb7e6848ed175ea`，产生 **615,305 个官方点**。官方格网、NetCDF、CLI 居中叠加及当前参考坐标的 WaveView 图像/映射均成功；GUI 实际切换高度叠加并查询像素 (1113,670)，显示 H/B=−0.659684，来源明确为官方网格估计。

在正式 GUI 打开 3D 点云，显示官方总点数 615,305、仅为绘制抽样 29,333 点，原始点云未改变；随后通过正式 GUI 导出至 `Vieira_Official_GoPro_Sample/exports/gui-20260918`，包含原 TIFF、XYZ、PLY、NetCDF、两套官方叠加和映射、manifest 与任务日志。作者样例最终包结果：**VIEIRA_OFFICIAL_SAMPLE_APP_PASS**。

### HomeTank 原始视频阶段

在同一最终 EXE 切换至 `HomeTank_004_example`，项目记录包含左右原始标定视频、左右原始波浪视频。重用项目内由原标定视频通过官方角点检测产生的输入角点记录（18 张 LEFT、16 张 RIGHT，全部采用，不按 RMS 挑帧），而非重新检测相同原图；最终 GUI 实际重新执行 OpenCV calibration，任务 `jobs/52fbed110fe84c97b4da94fb1e717bb1`，LEFT RMS=6.029846494 px、RIGHT RMS=6.376489998 px。这不是高精度标定通过声明。

随后从原波浪视频音轨重新运行官方 TLCC/Praat，任务 `jobs/69a9024437b447a8a9efb7f89d6f3d4c`，窗口 0–30 s、作者风噪滤波开启，RIGHT−LEFT=−0.075 s，sync=COMPUTED。按原 PTS 抽帧；音轨同步不代表逐曝光时间已验证。

最终 GUI 实际执行三帧 prepare → match → autocalibrate，任务 `jobs/e2cccedab1914341bd547cf0ece2caf2`，官方命令返回 0，T=[0.142305397,0.964834378,−0.221006327]、‖T‖=1。这是官方计算完成，不等于外参可靠；布局仍以竖直分量为主，结合上面的原命令 A/B 失败记录，不继续调官方算法。随后用户可见的“加载示例历史内外参（显式 Fallback）”实际加载完整六个 XML，任务 `jobs/2ecf849431ad4f2a9202edb1a4aaea71`，内参与外参均标记 FALLBACK，**没有把新 K/D 与旧 R/T 混用**。来源：`D:/stereo-wave-height-runs/HomeTank_004/wave-reconstruction-pipeline-20260824/wass_workspace/config`；六个源/复制文件 SHA256 保留在项目 provenance。新 OpenCV 和 WASS 外参任务不删除。使用已有官方 stereo config，不修改其模型逻辑；SAVE_AS_PLY 仅启用官方输出。

在同一最终 EXE 中，使用 LEFT 20.000 s / RIGHT 19.925 s 建立新参考面，任务 `jobs/a8970189b85e421d9402f9f342c75535`，实际完成官方 WASS stereo 与 wassgridsurface setup；参考平面为 [−0.015512125, −0.745314463, 0.666532613, −3.057903728]，基线 0.07 m。该帧没有被证明是严格静水，因此仅作为当前软件流程参考，不作为物理精度声明。

当前帧使用 LEFT 20.159644444 s / RIGHT 20.084644444 s，任务 `jobs/942610b64c0449a4b4bba0cb7c39ac18`。官方 WASS 产生 **146,073 个点**，随后官方 wassgridsurface、NetCDF、wassncplot / WaveView 映射与叠加均完成。GUI 实际打开点云窗口，显示抽样 29,215 点且不修改原点云；在官方图像像素 (1180,848) 查询得到 X=−83.413 mm、Y=210.722 mm、Z=5.584 mm、H=+5.584 mm，界面明确标注其来源为官方网格估计而非直接观测。官方结果可能包含池壁、尺子等非水面结构，程序未加入自研 ROI、筛选或修正。

结果已通过正式导出服务写入 `D:/stereo-wave-height-runs/production-workflow-v1-projects/HomeTank_004_example/exports/gui-dual-20260918`，包含左右当前帧、XYZ、PLY、NetCDF、两套官方映射/叠加、manifest 与完整任务日志。HomeTank 最终包结果：**HOMETANK_APP_PASS_WITH_EXTRINSIC_FALLBACK**。

## 回归与保护

最后全套测试：509 passed、1 skipped、4 subtests passed，25 个已有 NumPy 弃用警告；耗时 27.34 s。输入/状态/环境针对性回归 25 passed。图像序列时间精度、外参可选起始范围、单位文字及上游变化清除下游状态仅属 IO/UI，针对性回归再次 25 passed。git diff --check 通过。

第三方源代码基线 60 文件 SHA256：修改 0。Golden Demo 冻结 payload 299 文件 SHA256：修改 0。用户原 `experiments/real_video/HomeTank_004/project.json` 与 `TOOLCHAIN_PROVENANCE.json` 哈希保持原值。不把软件流程成功称为严格物理精度验证；官方网格估计不等同于每个像素直接双目测量。
