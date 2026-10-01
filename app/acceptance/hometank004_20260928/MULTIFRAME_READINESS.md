# 离线基础程序：多帧与新输入层收尾验收

科学运行日期：2026-09-28；中断后收尾及真实窗口验收：2026-10-01。
Starting HEAD：`6eea658825fa3f6657dae5872f5feb4118fd5d03`。
分支：`app/offline-basic-workflow`。本轮不打包 EXE，不修改 pipeline 或第三方科学算法。

## A. 结论与未通过的边界

**同次官方批次内的多帧桌面流程及新视频输入层通过。尚不宣称 `OFFLINE_BASIC_WORKFLOW_READY_FOR_NEW_INPUT_PASS` 全面成立。**

原因不是缺少界面按钮，而是固定科学能力边界：

1. 固定参考面只对同次官方 gridding 运行中的帧有效；尚未证明独立运行之间的坐标注册。已经冻结的项目不会自动重新拟合参考面，也不会把旧平面直接套到下一独立运行。未处理时刻明确拒绝，不伪造结果。
2. 冻结输出没有单独的 COMMON_STEREO_REGION 几何掩码。界面如实显示 UNKNOWN，而不是将具有高度的区域假装成双目公共区域。
3. 新输入层通过不等于新设备标定、同步和重建必定成功，更不等于物理高度准确度通过。

在“不得修改冻结科学流程”的授权范围内完成了下面的收尾；不创建暗示全面通过的 ready tag。

## B–D. 三个真实待测时刻

独立新运行目录：
`D:/stereo-wave-height-runs/pipeline/hometank004_multiframe_acceptance/run_20260928/science`。

[运行配置](multiframe_config.yaml) 使用同一 HomeTank_004 原始输入、未改变重建参数；从 20 s 起，1 Hz，共 4 帧。实际运行 `app.worker reconstruct`，调用冻结流水线完成标定、TLCC、WASS prepare/match/autocalibrate/stereo、官方 gridding 与 pixel mapping。状态为 `HOMETANK_PIPELINE_PASS_WITH_EXTRINSIC_FALLBACK`。

20.008900 s 的第 0 帧为参考候选，下面三个帧是真实 WASS 输出，不是复制同一帧。10 月 1 日真实 GUI 在 21/22/23 s 暂停、点击“解算当前暂停帧”，读取该已完成批次的缓存，再检查各自原图、点云、叠加及 hover。**这些点击不算再次执行 WASS**。之前的新批次运行才是科学执行证据。

| frame_id | 左实际 PTS（s） | 右实际 PTS（s） | 同步配对残差（ms） | 原始 WASS PLY 点数 | 官方映射有效像素数 |
|---:|---:|---:|---:|---:|---:|
| 1 | 21.008900 | 20.924929984 | -8.900 | 147,347 | 955,300 |
| 2 | 22.008900 | 21.924929984 | -8.900 | 106,949 | 930,940 |
| 3 | 23.008900 | 22.924929984 | -8.900 | 127,957 | 953,695 |

映射大小来自输出：2400×1350，共 3,240,000 像素；程序不写死此尺寸。上述计数不是纯水面点数，也不是直接三角测量像素覆盖率。TLCC 右减左音轨偏移为 `-0.07507001632731439 s`；残差已扣除此偏移。

三帧共同参考 ID：`INTERNAL_STATIC_REFERENCE_e51ef801fa932e1e`。

## E. 实际鼠标查询

以下是 10 月 1 日真实窗口鼠标查询文本中的官方网格坐标，不是仅调用函数的截图替代：

| 帧 | 查询映射像素 (u,v) | XYZ（m，显示精度） | H（mm） | 来源 |
|---:|---|---|---:|---|
| 1 | (1048,680) | (-0.10610, 0.17991, 0.00487) | 2.63 | OFFICIAL_GRID_ESTIMATE |
| 2 | (960,680) | (-0.12460, 0.19281, -0.01075) | -13.85 | OFFICIAL_GRID_ESTIMATE |
| 3 | (952,680) | (-0.12367, 0.18531, -0.00190) | -4.84 | OFFICIAL_GRID_ESTIMATE |

每帧另查无数据点：帧 1 `(108,1186)`、帧 2/3 `(102,1186)` 均显示 `H: N/A / Source: NO_DATA`，不填高度。图像缩放随窗口尺寸改变，因此同一屏幕坐标不必对应同一源像素；界面同时显示源图像与映射像素坐标。未设置测量框时显示 Measurement Region: IN；几何公共区为 UNKNOWN。

## F–G. 三种区域与官方 ROI 调查

- **COMMON_STEREO_REGION**：满足双目几何可见性的公共区域。当前冻结输出没有独立掩码；不从点云覆盖率推导它。
- **MEASUREMENT_REGION**：用户手工矩形。默认 NONE；设置后记录 USER_RECTANGLE 与归一化矩形，仅限制叠加/hover/CSV。矩形外显示 OUT/N/A；清除恢复完整显示。
- **HEIGHT_AVAILABLE_REGION**：当前帧官方映射具有有限 XYZ/H 且来源非零的像素。青色轮廓指它，不是 COMMON_STEREO_REGION，不是自动水面识别。

本地官方 `wass_stereo` 版本 `1.11_heads/master-0-g6b82aeb`。检查其原始 `src/wass_stereo/wass_stereo.cpp`：1031–1036 行已有 `TRIANG_BBOX_TOP/LEFT/RIGHT/BOTTOM` 和 `LEFT_MASK_IMAGE/RIGHT_MASK_IMAGE`。1219–1250 行先 `unrectify` 回到 prepare 产生的去畸变相机图坐标，再检查 bbox 和黑白 mask。mask 路径相对于 workspace；当前运行还存在官方左右交换。因此 GUI 原始图上的矩形不能直接当作这些 mask，当前未接入科学输入。

源仓库：[官方 WASS](https://github.com/fbergama/wass)；[官方 stereo 文档](https://www.dsi.unive.it/wass/documentation/stereo.html)。本轮的坐标判断以本地冻结版本源码为准，没有修改它。

## H–I. 参考面与外参

流程：暂停选择候选 → 预览 → 同次官方运行 → 读取冻结 reference adapter 的 n/d → 用户确认冻结 → 保存到项目 YAML。确认前不开放相对高度叠加/导出；确认后各帧使用同一对象/ID。

本次 n=`(0.03447669639565173, -0.01783873817835036, 0.9992462843692971)`，d=`0.0046305357434224615`，来源帧 0，左实际时间 20.008900 s，坐标 `official_wass_grid_m`。这是 INTERNAL_STATIC_REFERENCE；未独立验证静水或物理真值。**未新增平面拟合算法，也未修改冻结高度定义。**

项目保存 coefficients、ID、源运行、标定身份和输入绑定。重开时核验同一视频对及实际 K/D/R/T 身份，恢复冻结参考；改输入会清除旧绑定。不同参考面/不同系数/不同来源运行不能覆盖已冻结项目。仍支持 plane.json 导入，PROVIDED_PHYSICAL_REFERENCE 必须具有明确的源运行坐标注册。

新棋盘内参执行记录 RMS 左 4.197245 px、右 5.523 px；HomeTank 示例在官方外参尝试后显式使用完整历史 K/D/R/T bundle。界面、导出始终标明 EXTRINSICS_FALLBACK，不宣称新外参通过。实际 active calibration identity 为 `9184852a01ab183ed9e839e92c834935503ab91e5d4cfab2c98803553a68d5c7`。

## J–N. 泛化、状态和三视图

`app/*.py` 中 HomeTank 路径/固定 2400×1350 业务逻辑命中：0。批次帧数从项目/GUI 输入读取，不再写死 3。默认空项目没有视频路径或 HomeTank fallback，allow_extrinsic_fallback=false；有 fallback 时必须同时显式允许并给出可追溯路径。

真实点击“新建空项目”保存 `EMPTY_NEW_PROJECT.yaml`，四个标定/测量路径初始为空、旧参考/结果清空。随后输入 HomeTank_006 左右路径并保存，真实窗口显示两幅 4K 图像，seek 到 5 s，播放推进至 6.254 s 后暂停。没有对 005/006 进行科学重建或调参。

输入层读取/左右提帧/Qt 播放暂停与 seek 回归测试：

| 数据 | 左分辨率 | 解码报告 fps | 帧数 | 时长（s） |
|---|---|---:|---:|---:|
| HomeTank_004 | 1920×1080 | 59.288709 | 9556 | 161.1774 |
| HomeTank_005 | 1920×1080 | 29.972691 | 3627 | 121.010156 |
| HomeTank_006 | 3840×2160 | 29.971109 | 3025 | 100.930533 |

切帧/播放/换输入隐藏旧 XYZ/H/map，并标 STALE；即使只切一步也不能保留旧查询。重建尚未完成不能导出旧帧。三个视图共用当前 frame/timestamp/reference/calibration 摘要。官方 PLY 展示做均匀抽样以限制绘图负载，但导出的 PLY 不删点；它是原始 WASS 坐标，不是已对齐、度量缩放后的 CSV 网格坐标。

三帧视图快照由 `app.capture_acceptance` 从真实 Qt 视图保存；另有上述独立鼠标控件验收。这些快照不能单独当作新 WASS 执行证据：

| t | 原图 | 点云 | 叠加 |
|---|---|---|---|
| 21 s | [原图](frame_21/raw.png) | [点云](frame_21/cloud.png) | [叠加](frame_21/overlay.png) |
| 22 s | [原图](frame_22/raw.png) | [点云](frame_22/cloud.png) | [叠加](frame_22/overlay.png) |
| 23 s | [原图](frame_23/raw.png) | [点云](frame_23/cloud.png) | [叠加](frame_23/overlay.png) |

## O. 真实 GUI 导出

点击导出并选择目录：`D:/stereo-wave-height-runs/offline_acceptance_20261001/export_frame3`。
五个文件均实际存在：current_frame.png、overlay.png、pointcloud.ply、instantaneous_height.csv、metadata.json。第 3 帧矩形内已有高度 49,732 行；CSV 含表头共 49,733 行，整帧 mapped count 953,695，二者明确分开。CSV 无凭空补点。

原始和导出 PLY 的 SHA256 同为 `d8fd487c6aa2ecbf503acfe15de5a4ad7fd5366c6a08c38583f23d1941510483`。metadata 包括双目实际时间、同步残差/偏移、标定 ID/来源、参考 ID/来源、点数、像素数、ROI 和源科学目录。当前导出实现也显式记录原图/映射尺寸与各自坐标单位，不把原始 PLY 当作 metric grid XYZ。

## 工具链与失败行为

在配置的 Python 环境检查，而不是借用另一个 Python 的版本：Python 3.12.5、OpenCV 5.0.0.93、FFmpeg 7.1、Praat 7.0.02、WASS 1.11、wassgridsurface 0.11.4、wassncplot 2.5.3 均 READY。WASS 检查 prepare/match/autocalibrate/stereo 四个可执行文件。无下载安装。

标定/同步/重建错误展示 CALIBRATION_FAILED / SYNC_FAILED / RECONSTRUCTION_FAILED；官方 autocalibration 错误另标 EXTRINSICS_FAILED，并读取源日志阶段。没有 GUI 为了继续而偷偷启用 HomeTank fallback。

## P–U. 检查与备份

- 第三方科学算法修改：0；pipeline 修改：0；EXE 打包：否。
- 完整 pytest：549 passed、1 skipped、4 subtests passed；25 项既有弃用警告。
- README 指定 unittest discovery：454 项，OK，1 skipped。首次 pytest 收集因未设置 src 导入路径失败；按项目 README 设置 PYTHONPATH 后完整通过，未改测试来规避。
- 最终界面/导出针对性 pytest：20 passed；git diff --check 通过。
- 最终完整日志本地保留：`D:/stereo-wave-height-runs/offline_acceptance_20261001/pytest_full_final.log`，`full_tests.log`。
- 代码、运行配置、此记录及三帧 Qt 快照提交到当前分支。大型科学输出保持独立本地目录，没有覆盖或混用历史结果。
- Git commit/push/工作区结果以交付时真实 Git 检查为准；不把它写成科学准确度 PASS。

## 复核命令

```powershell
$env:PYTHONPATH = "$PWD;$PWD\src"
& 'D:\stereo-wave-height-runs\wassgridsurface-0.11.4-venv\Scripts\python.exe' -m pytest -q
& 'D:\stereo-wave-height-runs\wassgridsurface-0.11.4-venv\Scripts\python.exe' -m app.main app/acceptance/hometank004_20260928/multiframe_config.yaml --inspect-run D:/stereo-wave-height-runs/pipeline/hometank004_multiframe_acceptance/run_20260928/science/run_report.json --reference-time 20 --target-time 21
```

确认参考面后，暂停到 22 或 23 s，点击解算以读取本批次缓存。若想保留项目绑定，请先把示例 YAML 复制到自己的项目目录；确认会保存所选项目 YAML。新设备不需要改 Python 源码，但必须提供匹配的原始标定/测量视频、真实棋盘尺寸/基线，并接受官方流程可能真实失败。
