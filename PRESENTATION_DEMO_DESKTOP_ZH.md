# 原生 Windows 桌面汇报程序

## 最简单的启动方式

双击 `D:\research\stereo-wave-height\dist\StereoWaveHeightDemo\StereoWaveHeightDemo.exe`。

直接出现“双目水面三维测量演示系统”窗口，默认进入“项目概览”。没有终端窗口、浏览器、WebView、Streamlit 服务或网络需求。保留整个 onedir 文件夹，不要只复制单个 EXE。

桌面程序使用 PySide6 Essentials 6.11.2（Qt Widgets），原生 QGraphicsView 图像及鼠标查询，Matplotlib Qt 画布展示三维点云和 NetCDF 高度图，PyInstaller 6.22.3 `--onedir --windowed` 打包。没有把大型点云或 MAT 塞进 EXE；仅打包读取依赖和原始 manifest。

开发入口：`python tools/presentation_demo_desktop.py`；[开发启动脚本](scripts/run_vieira_demo_desktop.ps1)。
[构建脚本](scripts/build_vieira_demo_desktop.ps1) 在独立目录构建，不覆盖旧包。构建依赖见 [requirements_presentation_desktop.txt](scripts/requirements_presentation_desktop.txt)。

## 数据目录与错误提示

默认读取：`D:\stereo-wave-height-runs\vieira2025-end-to-end-demo-20260916\golden_004_demo`。
EXE 旁 `config/presentation_demo.json` 保存唯一的数据目录设置。开发态设置：[presentation_demo.json](config/presentation_demo.json)。不需要用户选文件或改参数。

冻结目录不存在时，以中文 QMessageBox 显示“未找到 Golden Demo 数据目录”及完整路径。单个文件缺失/格式错误时显示中文错误，不显示 Python traceback。普通展示不写回任何源文件，缓存和画布仅在内存。

## 八页演示顺序（3–5 分钟）

| 页面 | 内容 |
| --- | --- |
| 项目概览 | HomeTank_004、五帧、681,678 XYZ、工程流程已跑通、黄金样例已冻结、物理精度未验证 |
| 双目输入 | 左 cam0 与右 cam1 同步帧并排；全局第1–5帧切换 |
| 处理流程 | 双目输入到像素高度的连续流程，标明历史备用内外参 |
| 三维点云 | 原生 Matplotlib 三维旋转、滚轮缩放；每帧最多约30,000显示点 |
| 水面高度图 | 直接读取 gridded.nc，单位 mm；各帧真实来源占格、插值、外推比例 |
| 原图叠加 | 显示五份冻结官方 wassncplot 结果，并支持原生悬停 |
| 像素高度查询 | 不点击即可显示 u/v、XYZ、相对平均水面高度和来源说明 |
| 结果与验证边界 | 工程可行性与尚未完成的物理精度验证分开 |

所有页面保留“演示版本：尚未完成物理精度验证”；图例、说明、状态均中文。仅显示抽样不改变原始 WASS 重建；点云含未经水面分类的来源点，不能把所有点当成水面观测。

## 原生鼠标悬停

QGraphicsView → mapToScene → 图像整数像素 → 冻结 MAT[v,u]。图片保持纵横比，窗口缩放、滚轮放大和拖动平移后仍返回图像像素，不是屏幕像素。

坐标沿用已审计的 **WASS 去畸变计算左图 cam0、2400×1350**。不是原视频坐标，也不是 RIGHT/cam1。五帧使用同一全局帧索引分别加载图像、MAT、PLY、NetCDF 和统计，没有跨帧串用。

XYZ 直接来自冻结 MAT，单位 m，显示乘1000为 mm。MAT 为平均水面坐标，H_mm=1000×MAT_Z；Z 与 H 一致不是重新置零。UI 不做高度修正、插值、最近邻补洞或三角化。

有效像素旁显示中文浮窗，底部也同步显示。NaN、0/1官方背景 sentinel 显示“该像素暂无有效三维高度数据”，不输出0或邻近高度。来源显示“未知（官方规则网格估计）”，不猜成直接观测。规则网格100%有数值不代表100%直接观测；网格来源占格率约18.93%–20.55%不是全幅水面覆盖率。

## 三个核验点（第一帧，单位 mm）

| 像素 | X | Y | Z（读取 MAT） | H |
| --- | ---: | ---: | ---: | ---: |
| 1000,1050 | −110.563 | 272.334 | −10.598 | −10.598 |
| 1100,1000 | −88.713 | 246.750 | +0.256 | +0.256 |
| 1000,1000 | −108.221 | 252.700 | −5.612 | −5.612 |

## 冻结边界

起点：`demo/presentation-ui-hover` / `c1581d40f077c99c61aa4137ba8e9ce7637da336`。
Golden Demo v1 的299文件及算法、K/D/R/T、同步、XYZ、平面、NetCDF、MAT和高度继续冻结。WASS executions=0，标定实验=0。物理数值不因桌面迁移而修改。

能证明真实双目视频进入官方工程流程并产生XYZ、网格、NetCDF、叠加及已有像素查询；不能证明厘米级精度、真实波高绝对正确、全水面直接观测或严格无备用参数的Vieira复现。[工程报告](DEMO_VIEIRA2025_END_TO_END_ZH.md) 的边界保持不变。

原生桌面版现在是汇报主版本。旧 [网页启动脚本](scripts/run_vieira_demo_ui.ps1) 和 [网页说明](PRESENTATION_DEMO_UI_ZH.md) 保留作历史备用，不由桌面 EXE 调用。

## 测试记录

开发态针对性3项通过；全套484 passed、1 skipped、4 subtests passed。测试覆盖八页、五帧、原生鼠标事件、缩放后坐标、MAT/PLY/NetCDF、三点XYZ/H、中文缺文件弹窗、无Web入口和299项哈希。

复现测试需设置 `PYTHONPATH=src;tools`，并给 pytest 指定独立英文 `--basetemp` 目录：现有 netCDF4 测试写入中文临时路径会报 PermissionError，与桌面程序只读加载无关。最终完整复跑为484 passed、1 skipped、25 warnings、4 subtests passed。

2026-09-17 最终 EXE 已实际启动并完成八页导航、五帧切换及无需点击的鼠标悬停验收。五帧均显示真实 MAT 的 XYZ/H；查询坐标随鼠标变化。另以最终 EXE 的离屏 Qt 事件检查重复验证五帧、三个核验点与299个冻结哈希，结果 PASS。自动检查不替代上述可见窗口验收。

运行进程检查：没有 TCP 连接/监听或 UDP 端点；PE subsystem=2（Windows GUI）。没有打开浏览器、HTTP服务或终端。PyInstaller 构建通过。报告：`D:\stereo-wave-height-runs\desktop_packaged_smoke_final.json`。

修复了一项实际打包故障：依赖收集误带入 ICU 78 的 `icuuc.dll`，遮蔽 Windows 系统同名 ICU 库，但缺少 Qt 所需的 `ucnv_open` 等导出，导致 QtCore 无法加载。构建脚本仅排除这一个冲突文件，并部署一致的 Qt MSVC 运行库；没有修改算法或系统设置。旧 EXE 目录保存在 `dist\StereoWaveHeightDemo_legacy_backup_20260916`，旧网页代码也未删除。
