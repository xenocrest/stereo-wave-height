# 双目水面三维测量系统 V1：实现与验收报告

起点：`demo/presentation-desktop` / `9499c9ce72b8acce2d18379c663996fb15db69b2`。新分支：`app/production-workflow-v1`。原演示 EXE、源代码与 Golden Demo 不覆盖。

## 范围和实现

新建/保存/打开项目、四路视频输入/元数据、OpenCV 候选棋盘帧/勾选/内参、WASS 外参尝试/显式历史标定加载、官方 TLCC、官方参考面、播放/暂停/seek/逐帧、固定外参当前帧 WASS 任务、官方格网和映射、2D 叠加/3D 点云、真实鼠标 hover、SHA256 缓存、官方文件导出与详细任务日志。

本版本不含 ROI、实时重建、全视频批处理、语义分割、新 stereo、新平面拟合或新插值。非水面点保留。不存在 FoundationStereo 或旧 GUI 降级后端。

## 本机工具

| 工具 | 实际版本/入口 |
|---|---|
| Python | 3.12.5，外部科学工具环境 |
| PySide6 / PyInstaller | 6.11.2 / 6.22.3 |
| OpenCV Python | 5.0.0，findChessboardCornersSB / calibrateCamera |
| WASS | 1.11_heads/master-0-g6b82aeb，内部 OpenCV 4.6.0 |
| wass_lowcost | 官方源码快照；以原文件 SHA256 标识，原始 TLCC/Praat/FIR 代码不改 |
| wassgridsurface | 0.11.4，setup / grid |
| wassncplot | 2.5.3，CLI / WaveView 现有 API |
| FFmpeg / Praat | 本机已有程序；完整版本文本与二进制 SHA256 见项目 TOOLCHAIN_PROVENANCE / sync metadata |

官方参考：[OpenCV 棋盘检测与标定](https://docs.opencv.org/4.12.0/d9/d0c/group__calib3d.html)、[wass_lowcost](https://github.com/matheusdpv/wass_lowcost)、[WASS](https://github.com/fbergama/wass)、[wassgridsurface](https://pypi.org/project/wassgridsurface/)、[wassncplot](https://pypi.org/project/wassncplot/)。

同步的上游入口不是完整原封不动执行：它缺少 callable API，Windows 路径/解码和文件重命名控制存在问题。适配器执行未修改源码中的原始 Praat 生成/FIR AST 块，再调用原 Praat TLCC；不另写相关算法。这个平台适配边界在架构文档中详细说明。

## 实际计算和历史 Fallback

独立服务验收在新的 `production-workflow-v1-projects/acceptance-20260917` 目录执行，不读取 Golden workspace。桌面验收另从示例入口创建 `HomeTank_004_example`，导入四路原始视频。原始标定视频均匀抽帧，全成功角点输入 OpenCV 标定；保存新 K/D、每视图误差和全部来源。EXE 实际检测获得 LEFT 18 / RIGHT 16 个有效帧，官方标定 RMS 分别 6.029846 / 6.376490 px；误差偏大，未声明标定可靠或物理精度通过。棋盘按 6×9 旋转方向、20 mm 输入，不改变物理格子尺寸。

从原音轨新执行官方 TLCC，得到 RIGHT−LEFT = −0.075 s（上游毫秒舍入）。三帧 prepare/match/autocalibrate 实际执行。新外参后的 stereo 出现官方 `Vertical stereo not supported`，未绕过检查。显式加载历史完整 K/D/R/T，保存来源实验、报告/commit、六文件 SHA256、尺寸和未物理验证标记，不拼接新旧几何。

输入适配曾错误关闭视频 display rotation，造成 LEFT 倒置而 RIGHT 正常，已经统一由 OpenCV/FFmpeg 遵循容器旋转信息。定位依据：新提取 LEFT 与既有已成功流程的源图像经过 180° 旋转后逐像素相同；RIGHT 本来逐像素相同。仅用于对照排错，未把旧图片当新输入。

显式历史内外参下，20 s 新参考帧 stereo / setup 以及 20.1、20.2 s 新当前帧 prepare/stereo/grid/ncplot/WaveView 已产生真实新产物。参考面使用本次新 `plane.txt`，不是历史 reference fallback。每帧共享固定官方 setup，不按当前帧重新归零。

官方 CLI 会减去 NetCDF zmean，另存“居中约定”产物；固定参考面查询使用官方 WaveView API 直接渲染原 NetCDF Z。当前本机 DPI 下官方映射为 2400×1350，原官方图像 1920×1080；按官方 CLI 已有显示处理 resize 图像至同尺寸，映射数值不缩放/改写。示例查询 (1000,1050) 约 −3.324 mm，为官方格网估计，不是独立实测精度证据。

## 自动测试与保护

- 针对性：16 passed，覆盖项目、视频 metadata/seek/同步抽帧、棋盘检测、K/D/误差、失败日志、官方命令、同步代码调用/offset、参考身份/来源、帧身份/缓存、导出、播放/暂停/逐帧/按钮状态、无需点击的 mouseMove、resize/zoom/显示比例映射、外部任务使用可写项目工作目录。
- 全回归：500 passed、1 skipped、4 subtests passed、25 个已有 NumPy/NetCDF 弃用警告，最终界面事件修复后 27.83 s。
- 第三方源码前后 SHA256 一致；Golden Demo 299 项冻结哈希一致。
- PyInstaller onedir 已实际构建，Qt 系统 ICU 同名冲突按已确认的部署规则处理；工具 dist-info 版本 metadata 随包补齐。
- 最终 EXE 实际暴露的 Windows 工作目录问题已修复：QProcess 明确使用可写项目目录，不继承 Codex 的 WindowsApps 目录。时间轴处理 valueChanged；另提供精确 LEFT 帧输入。这些均为任务/界面适配，不改变官方算法。

## 最终 EXE 桌面验收

结论：`PRODUCTION_WORKFLOW_V1_PASS`，限定为本机 HomeTank_004、显式历史完整标定的工程工作流验收，不是全新标定物理准确度验收。

验收通过 Windows 桌面实际操作最终 EXE 完成，而不是仅调用函数 smoke。示例项目位于 `D:/stereo-wave-height-runs/production-workflow-v1-projects/HomeTank_004_example`。新建/保存/打开项目也通过实际原生文件对话框验证，另建空项目 `gui_project_controls_20260917`，再打开已计算的示例项目。

| 桌面步骤 | 实际结果 |
|---|---|
| 四路原始视频导入、候选检测、OpenCV 标定、矩阵显示 | PASS；LEFT 18 / RIGHT 16 帧，新 K/D 与 RMS 真实保存和显示 |
| 原音轨 TLCC 同步 | PASS；新 offset −0.075 s |
| 新内参 WASS prepare/match/autocalibrate | 实际执行，官方返回成功；后续新外参参考帧 stereo 原生失败，完整失败日志保留 |
| 显式加载历史完整 K/D/R/T | PASS；用户按钮触发，红色来源/未验证提示，不修改任何 XML 数值 |
| 建立本次新官方参考面 | PASS；LEFT 20 s / RIGHT 19.925 s，新 WASS plane → 官方 setup，未加载历史 reference |
| 播放、暂停、精确逐帧浏览 | PASS；最终选择 LEFT 帧 1196，实际 PTS 20.159644444 s，RIGHT 目标 20.084644444 s / 浏览帧 1205 |
| 点击重建当前帧 | PASS；本次新 prepare/stereo/grid/ncplot/API 映射，146075 个官方 PLY 点，非 Golden/邻帧产物 |
| 官方原图/固定参考高度叠加 | PASS；本帧官方图像与映射均为 2400×1350；非水面结构原样保留 |
| 无需点击的 hover | PASS；鼠标移动到有效像素，界面真实显示当前帧 u/v/XYZ/H，并标注官方网格估计 |
| 点云窗口、旋转、缩放 | PASS；146075 原始点，29215 点仅用于显示，原始点云不删改 |
| 原生文件夹对话框导出 | PASS；XYZ/PLY/NC/MAT/图像、当前显示截图、manifest 和阶段日志实际存在；主要产物导出前后 SHA256 全一致 |

本次桌面新参考任务：`jobs/075ca1a29ea24daab4ea76509d5a5e99`。当前帧任务：`jobs/4f0d4f48b94d41cb9e7727b8185e6737`。本帧缓存身份：`2b76fdbdfe5480149819c1c878718b14eb365355565260e45314d2c852e2d8cf`，独立 attempt：`0cfe05e90ea34d22a41dc8bce4d6178a`。

当前帧记录的六个外部阶段 return code 全为 0，耗时合计约 21.22 s；该时间不包含进程启动、官方 API 渲染和 GUI 加载，不能宣称总 GUI 延迟为 21.22 s。

实际 hover 核对：像素 (980,1120) 对应参考坐标 XYZ≈(−99.560,297.152,−0.190) mm，H≈−0.190 mm；另一次移动查询 (1076,1085)，H≈−21.299 mm。直接读取本帧 `reference_pixel_xyz.mat`，与界面三位小数显示一致。数字只是官方内部格网输出的读取一致性证明，不是尺子验证，也不证明这些位置是水面。

实际导出目录：`D:/stereo-wave-height-runs/production-workflow-v1-projects/HomeTank_004_example/exports/gui_frame_01`。官方点云、NetCDF、映射和左右输入等八项主要产物已逐项哈希核对。提交前再次核对第三方核心 60 个文件、Golden 299 个文件，差异均为 0；原演示分支仍为起点 commit。

EXE：`D:\research\stereo-wave-height\dist\StereoWaveHeightSystem\StereoWaveHeightSystem.exe`。

## 不能据此证明的事项

本机离线部署仍依赖配置中外部工具环境，尚不是任意 Windows 电脑免配置发行版。项目输出路径要求 ASCII；大视频只引用路径，但首导入需读取 SHA256。当前同步入口要求有效前 30 s 音轨。参考数据是否静水由用户负责；外参 return 0 不代表物理正确。不能证明厘米级物理精度、全像素直接观测、任意帧支持、所有网格均为真实水面、波浪趋势与人眼一致，或 GoPro 已完成实际验收。

## 项目管理修复（2026-09-17）

修复基线 `2edbb51db006e923c44e081606c8f890a8e690b9`，分支 `bugfix/project-management-flow`。本轮不改变科学适配器或标定、同步、参考、重建的算法逻辑。

根因：初始状态栏文字只在启动时设置，set_project 没有更新它，因此真实项目已经打开仍显示“请新建或打开项目”。四个视频标签只来自活动 Project.videos；无项目分支不显示视频，既不是硬编码预填，也不是 Golden。用户已有的 HomeTank_004/project.json 确实包含四路视频。不能从陈旧提示推断 current_project 为空。保存按钮信号已连接，原 handler 有项目时实际写磁盘却无反馈，无项目时则静默返回。

修复：单一 self.project 状态（active_project/current_project 为只读同源入口）；中文项目名称/目录对话框；真实 workspace 子目录；统一 ProjectService/ProjectStore 新建、打开、保存和另存；明确当前项目/保存成功提示；无项目保存中文 warning；无项目导航禁用，缺输入阶段明确前置条件；保存/关闭恢复工作页、帧编号、显示模式和界面参数。另存保留视频与科学产物的原始引用，记录 source project 哈希，不修改科学数值。详细操作异常写 application_errors.log。

本轮自动验收：20 项针对性通过；完整 504 passed、1 skipped、4 subtests passed、25 个已有弃用警告，25.19 s。旧实验目录清单测试允许两种本地 GUI 运行记录，其余注册输入约束不变；用户原有两文件保留且不发布入 Git。

最终 EXE 项目管理桌面验收：`PROJECT_MANAGEMENT_GUI_PASS`。实际操作最终 `dist/StereoWaveHeightSystem/StereoWaveHeightSystem.exe`，完成用户 TEST 1–8：空启动不预填视频；中文新建 `HomeTank004_Test` 至 `D:/stereo-wave-height-runs/manual-ui-test`，磁盘创建 project.json、来源记录及 workspace 五类子目录；逐项导入四路 HomeTank_004 原始视频；点击页面保存按钮，状态明确显示“项目已保存”；关闭并重新启动 EXE，经文件菜单打开刚保存的 project.json，四路路径及 metadata 全部恢复；进入相机标定页，棋盘检测按钮已启用；无项目时文件菜单保存实际弹出中文前置条件提示。本轮不点击标定或 WASS 执行按钮。

另外实际验收文件菜单“项目另存为”：新项目 `HomeTank004_Test_copy` 写入 `D:/stereo-wave-height-runs/manual-ui-test-copy`，状态显示“项目已另存为”，原项目未删除。磁盘逐字段核对四路视频及 metadata 与原项目一致；来源项目路径和 SHA256 保留在 workflow.saved_from_project。自动测试另覆盖标定、同步、参考、帧缓存引用和 workflow 参数的保存/打开一致性；这些科学产物维持原始引用，不复制或改写数值。
