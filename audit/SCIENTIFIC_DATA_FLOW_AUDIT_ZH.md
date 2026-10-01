# 科学数据流逐文件审计

基准代码：`3330a393a1feae5b38f6c589cdde89af8b67d30f`。审计分支：`audit/independent-reconstruction-quality`。本表的目标是已有“21.0089 s”结果；独立图像身份核查后，实际左源 PTS 为 **21.001544 s**，右为 **20.933889 s**。时间纠错只写诊断报告，未改历史产物。

## 目录与文件

`A = D:/stereo-wave-height-runs/fixed-coordinate-acceptance-20261001-final/Run_A/science`。

`W = A/wass/workspaces/000001_wd`。

每个文件的绝对路径、大小、shape/点数、SHA256和是否存在见 `evidence/artifact_manifest.json`；同时包含 22/23 s 和 Vieira 帧 0。不存在的前置点云仍保留缺失事实。

| stage | 路径/shape | 坐标、单位、相机 | 时间、工具、配置来源 |
|---|---|---|---|
| raw video L | `D:/research/stereo-wave-height/experiments/real_video/HomeTank_004/videos/wave/wave_cam0_iQOO_Neo5S.mp4`；1920×1080，90 kHz时间基 | 编码像素；旋转元数据 180° | 原视频 PTS；没有重编码 |
| raw video R | 同目录 `wave_cam1_iQOO_Z10_TurboPlus.mp4`；1920×1080 | 编码像素；cam1 | 原视频 PTS |
| audio sync | `A/sync/frames/crosscorrelate.praat`及两个 filtered WAV | 48 kHz双声道、101 tap 1000 Hz高通 | raw audio→FFmpeg→FIR→Praat；独立重提音频核对 offset −0.07507001632731439 s；交换输入后符号反转 |
| extracted cam0 | `A/sync/frames/cam0/000001.png`；1080×1920×3 | 原始带畸变、自动旋转后的 cam0 像素 | request 21.0 s，源帧 1247，实际 PTS 21.001544 s；历史记录 21.0089 是错误 |
| extracted cam1 | `A/sync/frames/cam1/000001.png`；1080×1920×3 | 原始带畸变 cam1 | request 20.924929984 s，源帧 1256，实际 PTS 20.933889 s |
| undistorted | `W/undistorted/00000000.png`、`00000001.png`；各1080×1920×3 | 去畸变 cam0/cam1；正式 K/D实际来自完整历史 bundle | 官方 prepare；与上述原始帧绑定 |
| rectified | `W/stereo.jpg`、`stereo_input.jpg`、`H0_rect.txt`、`H1_rect.txt` | 内部 left=cam1、right=cam0，rectified/cropped；预览可能缩放/拼接 | 官方 custom stereorectify；所有 shape 见 manifest；不把预览当原图 |
| disparity | `W/disparity_stereo_ouput.png`、`disparity_final_scaled.png`、`disparity_coverage.jpg` | 官方视差预览/缩放编码；不是可直接反算 d 的浮点全量矩阵 | 官方 SGBM，原 stereo config；未自行反演彩色预览 |
| initial triangulated | 官方日志 `187897 valid points found` | B单位的三维场景点 | mask默认为全有效；本版本未保存该阶段完整 XYZ，不能定位单点前后差异 |
| z-gap / pre-plane | `W/mesh_full.ply`；147,768点 | WASS实际相机坐标，B；已经过最大连通分量筛选 | 官方 SAVE_FULL_MESH；**不是 raw unfiltered triangulation** |
| filtered | `W/mesh.ply`、`mesh_cam.xyzC`；147,349点；解码3×147349 | 同一WASS相机坐标，B；使用实际 P0/P1与pose | plane RANSAC、refinement/crop 后；xyzC 由官方解码 |
| plane | `W/plane.txt`；4系数 | WASS B单位的场景拟合平面，d以B表示；不是独立静水面 | 本帧 refinement；日志记录其前后系数 |
| setup | `A/surface/config.mat`，Rpl/Tpl、Cam0toGrid/Cam1toGrid、P0/P1等 | 固定官方网格坐标，B=0.07 m；含官方Z翻转 | 原样复制 `D:/stereo-wave-height-runs/pipeline/hometank004_multiframe_acceptance/run_20260928/science/surface/config.mat`；hash `5b68efa26b0b9228e031c5bf07e18a932023faf54af79a0d3270d62340782c07` |
| regular grid | `A/surface/gridded.nc`；本帧256×256 | X/Y/Z在文件中×1000；读回为m；cam0undistorted image内嵌 | 官方 grid默认DCT，固定setup；本帧输出65536有限格子，只有18028有点落入 |
| pixel XYZ | `A/pixel/pixel_xyz/00000001.mat`；1350×2400×3 | 去畸变cam0光栅像素；XYZ为官方网格m；逻辑图1920×1080，framebuffer比例1.25 | 官方 wassncplot `--savexyz --save-img --pxscale 1`；实际pixel center需除1.25 |
| pixel NPZ | `A/pixel/pixel_height/00000001.npz` | 960496 finite OFFICIAL_GRID_ESTIMATE；DIRECT_STEREO=0；其他NO_DATA | adapter仅格式转换，未自建插值 |
| reference | `D:/stereo-wave-height-runs/fixed-coordinate-acceptance-20261001-final/reference_plane.json` | 固定n/d，m；内部20 s候选；不具独立物理基准 | 已存在的冻结reference，未逐帧重拟合；三类身份检查成功，负例拒绝 |
| H | `app/core.load_result`→`load_frame`→`ReferencePlane.height` | H=nᵀXYZ+d；m→显示mm一次×1000 | 同一固定n/d作用于当前帧；不做时间平均 |
| hover | `core.hover`读取`xyz[v,u]`和`H[v,u]` | row=v、col=u；单位和来源正确；GUI与原图之间只有缩放没有畸变转换 | `MainWindow._hover`因此查询原图时有空间错位 |
| overlay | `MainWindow._build_overlay` | 原始带畸变cam0缩放到2400×1350；叠加去畸变像素H，错位；2/98%逐帧色阶 | 同一renderer复核两数据集；没有修正式实现 |
| 3D GUI | `PointCloudView.show_ply` | 原WASS B坐标XYZ、颜色camera Z；不是m网格XYZ、不是H；默认轴比例 | 同一viewer显示两数据集；另输出TRUE_SCALE_VIEW与明确10X诊断图 |

## 实际标定与尺度

当前 A/B/C 每一份有效 K/D/R/T文件均与以下完整历史目录逐字节一致：

`D:/stereo-wave-height-runs/HomeTank_004/wave-reconstruction-pipeline-20260824/wass_workspace/config`。

`K_source=D_source=R_source=T_source`均为该目录对应文件。每个实际工作区 K/R/T也已数值核验。没有在实际 WASS工作区发现“新K/D+旧R/T”。但 GUI的calibration/report归属存在单独问题，见主报告。

WASS加载T时归一化为1 B；历史T norm=0.06868471158474378不直接决定XYZ单位。grid使用声明的实测baseline 0.070一次恢复m，ncplot读回文件×1000一次除1000；hover/export在m基础上一次×1000。未发现本轮m/mm重复应用。Vieira baseline=1定义B，不解释为实际m。

## 坐标/投影与可观测性限制

官方pixel map自洽并不证明 raw XYZ→grid→pixel整条链自洽。HomeTank冻结Rpl不严格正交，原WASS点前向对齐后回投影出现0.7368 px中位偏差；官方map内部的grid↔pixel自投影则约0.0014 px。两项必须分开。

99,912个21 s过滤后点落在人工标定的标尺及上部池壁区域（仅两个保守多边形，非完整分割）。前景水域诊断mask中仅11个过滤后点。21 s网格15,977个格子在全部输入云XY凸包外仍有有限值；这已证明外推，不只是空洞内插值。不能把65536或960496当水面观测数。

像素数量是renderer的光栅数量，不是新独立三维观测数量。源图分辨率、framebuffer比例、原图畸变约定、三维坐标变换、H参考面和来源标签是五个独立条件，任何一项不一致都不能拿hover当该原图位置的瞬时高度。
