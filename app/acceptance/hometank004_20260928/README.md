# HomeTank_004 离线桌面基础流程验收记录

日期：2026-09-28。科学基线：`bbbb74daa8a47109bfdffb75d6afff48a9776d02`；第三方科学算法源码修改：0。

## 输入与实际科学运行

- 标定左：`experiments/real_video/HomeTank_004/videos/calibration/calibration_cam0_iQOO_Neo5S.mp4`
- 标定右：`experiments/real_video/HomeTank_004/videos/calibration/calibration_cam1_iQOO_Z10_TurboPlus.mp4`
- 测量左：`experiments/real_video/HomeTank_004/videos/wave/wave_cam0_iQOO_Neo5S.mp4`
- 测量右：`experiments/real_video/HomeTank_004/videos/wave/wave_cam1_iQOO_Z10_TurboPlus.mp4`
- 从实际 GUI 的“解算当前暂停帧”按钮启动并完成的新科学输出：`D:/stereo-wave-height-runs/pipeline/hometank004/gui/reconstruct_20260928_161723_995729/science/`。此前另有同一适配器的命令行验证运行 `reconstruct_20260928_120926_674766/science/`；以下数字均取 GUI 启动的新运行。
- 冻结流水线状态：`HOMETANK_PIPELINE_PASS_WITH_EXTRINSIC_FALLBACK`。
- 当前棋盘视频重新计算内参；50 对左右视图，RMS 左 4.197 px、右 5.523 px。WASS 尝试外参自标定后，HomeTank YAML 显式启用**完整历史 K/D/R/T bundle**；不能报告为新外参计算成功。
- TLCC 右减左音轨偏移 `-0.075070016 s`。待测帧左实际 PTS `21.008900 s`，右实际 PTS `20.924929984 s`，配对残差 `-8.9 ms`。
- 参考候选：20.000 s（实际左帧 20.0089 s）的同一运行第 0 帧。依据冻结 `reference_from_config` 得到 `INTERNAL_STATIC_REFERENCE_b68553339016dbdd`；它是**内部指定静水参考假设**，没有独立物理基准验证。该画面中可见手部，不能断言是真正的无扰动静水。
- 待测：第 2 帧，21.0089 s；原始 WASS PLY 点 147,422；官方 gridded pixel↔XYZ 有效像素 1,211,401 / 3,240,000。此覆盖率是官方**网格估计**，不是直接双目点覆盖率，更不是水面覆盖率。

## 真实界面检查

已实际打开 Python/PySide6 窗口，通过窗口控件选择暂停时刻、选择参考候选、调用标定、调用 TLCC 同步、点击“解算当前暂停帧”并等待新科学运行完成；界面显示 `Calibration: FALLBACK / Sync: READY / Reference: READY / Reconstruction: READY`。已检查原图、WASS 点云、叠加、有效区域边界及 3 处悬停数值。三视图快照取自该新运行：

- [原始水面](raw.png)
- [WASS 三维点云](cloud.png)
- [官方像素↔XYZ 对齐的高度叠加](overlay.png)

悬停值（官方映射像素坐标，固定内部参考面）：

| (u,v) | H | 来源 |
|---|---:|---|
| (864,669) | -2.96 mm | OFFICIAL_GRID_ESTIMATE |
| (1652,744) | 2.56 mm | OFFICIAL_GRID_ESTIMATE |
| (143,1130) | N/A | NO_DATA |

本次没有 `DIRECT_STEREO` 像素；冻结 pipeline 在像素图中仅标记官方 gridding 映射估计与无数据。悬停绝不把网格估计说成直接观测。

## 必须保留的边界

截图显示叠加区域包含池壁及标尺，因此不能称为“水面区域已自动识别”或“水面每个像素均有真实高度”。青色边界只显示官方 pixel↔XYZ 输出的有限值支持区域。当前软件没有自己裁剪、分割、插值或修正科学输出。

跨独立运行的 `wassgridsurface` 对齐坐标未获证实一致：由某一运行静水帧拟合的参考面不能直接复用到另一运行。桌面程序仅在同一次运行的多个帧间冻结并复用该内部参考面，其他情况明确拒绝。新 GoPro 数据尚未到货，不能把“仅换视频即可成功”写为已验证事实。
