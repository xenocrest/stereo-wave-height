# WASS 完整处理链分析

核心链保持 WASS 原算法：输入/标定 → `wass_prepare` →（外参未知时）`wass_match` → `wass_autocalibrate` → `wass_stereo` → `wassgridsurface`。[P1]、[P2]

## 0. 输入与同步

| 项目 | 内容 |
|---|---|
| 输入 | `cam0/`、`cam1/` 成对图像；样例名为 `<6位序号>_<13位时间戳>_<2位相机号>.tif`。[P1] |
| 输出 | 可配对帧列表；不改变原始图。 |
| 配置 | `worksession.json`: `cam0_datadir`、`cam1_datadir`、`seq_start/end`。[P3] |
| 依赖 | 相机 SDK 负责采集/导出；WASS 核心以 OpenCV 灰度读取。[P4] |
| 关键参数 | 曝光、增益、帧率、硬触发和左右时间差不在 WASS 配置内。 |
| 失败/指标 | 丢帧、错配、尺寸/转换不一致、运动模糊、饱和；同步阈值 **UNKNOWN/TODO：按最大水面速度和 1 cm 预算计算**。 |

工业相机原则上可用；先导出无损 TIFF/PNG。Bayer 和 12/16 bit 转换行为必须以最小样例验证，不能假定与 8 bit 样例一致。[P4]

## 1. 相机标定

| 项目 | 内容 |
|---|---|
| 输入 | 每台相机标定图；可选已知双目外参；实测基线。[P3] |
| 输出 | `intrinsics_00/01.xml`（3×3）、`distortion_00/01.xml`（5 参数）；可选 `ext_R.xml`（3×3）、`ext_T.xml`（3×1）。[P3] |
| 配置 | 文件置于 `confdir`。[P3] |
| 依赖 | 旧文档建议 Bouguet MATLAB 工具；现代工具能否无损替代需用 XML 和重投影结果验证。[P3] |
| 关键参数 | 焦距、主点、畸变、左右顺序、外参方向、基线长度与单位。 |
| 失败/指标 | 单目标定重投影、极线误差、覆盖和重复性；厘米级阈值 **TODO**。 |

有效自定义外参会由 prepare 复制，可跳过 match/autocalibrate。[P1]、[P4] 自动外参只给单位尺度，必须用实测基线恢复米制尺度。[P5]

## 2. `wass_prepare`

| 项目 | 内容 |
|---|---|
| 输入 | `--workdir --calibdir --c0 --c1`、图像、内参与可选畸变/外参。[P4] |
| 输出 | `*_wd/undistorted/00000000.png`、`00000001.png`、工作内参和可选外参。[P4] |
| 配置 | 无算法配置；WASSjs 从 `worksession.json` 传路径。[P3] |
| 依赖 | OpenCV、Boost.Program_options/Filesystem。[P4] |
| 关键参数 | 左右顺序、标定对应关系、工作目录必须不存在。 |
| 失败/指标 | 参数/内参缺失、非法标定目录、目录已存在、无法创建目录；畸变缺失按零畸变。源码对图像读取失败缺少完整防护，运行前必须预检。[P4] |

## 3. `wass_match`（外参未知时）

| 项目 | 内容 |
|---|---|
| 输入 | `wass_match <matcher_config> <workdir>`；去畸变图和内参。[P6] |
| 输出 | `matches.txt`、`matcher_stats.csv`、匹配/特征图、初始 `ext_R/T.xml`。[P6] |
| 配置 | `matcher_config.txt`，用 `--genconfig` 生成。[P7] |
| 依赖 | OpenSURF、OpenCV、incfg、wass_lib。[P6] |
| 关键参数 | 最大特征数 2000、lambda 1e-5、population 0.7、最小组 5、轮数 20、最大极线距离 0.5 px；另有 Hessian/层/八度/特征间距。[P6]、[P7] |
| 失败/指标 | 配置/图像不可读、匹配过少/集中；用 `matcher_stats.csv` 的匹配数和极线误差统计验收。项目阈值 **TODO**。 |

## 4. `wass_autocalibrate`（外参未知时）

| 项目 | 内容 |
|---|---|
| 输入 | `wass_autocalibrate <workdirs_file>`；各目录的 `matches.txt` 和内参。[P8] |
| 输出 | 所有工作目录的 `ext_R.xml`、单位尺度 `ext_T.xml`、`H.xml`。[P8] |
| 配置 | 无独立配置；`num_frames_to_match` 限制匹配帧数。[P3] |
| 依赖 | OpenCV、SBA、LAPACK/BLAS、Boost。[P8]、[P9] |
| 关键参数 | 总匹配至少 8；LMEDS 本质矩阵；源码阈值约 2 px；T 最终单位化。[P8] |
| 失败/指标 | 匹配 <8、点在相机后、文件无效；SBA 不改善平均极线误差时回退。记录结构重投影和 SBA 前后极线误差。[P8] |

## 5. `wass_stereo`

| 项目 | 内容 |
|---|---|
| 输入 | `wass_stereo <stereo_config> <workdir>`；图、内参和外参。[P10] |
| 输出 | `mesh_cam.xyzC/xyzbin`、可选 PLY、`plane.txt`、投影/位姿、视差/覆盖诊断和日志。[P1]、[P10] |
| 配置 | `stereo_config.txt`，用 `--genconfig` 生成。[P10] |
| 依赖 | OpenCV 3.x、Boost、incfg、wass_lib；实验光流不作首轮基线。[P9]、[P10] |
| 关键参数 | min/max disparity、offset、window、dense scale、plane distance；中值/形态学、Z-gap、左右检测、平面 RANSAC。[P10]、[P11] |
| 失败/指标 | 外参/图像/配置无效、极点入图、点数 <100、平面失败、保存失败；检查极线同行、覆盖率、重投影、点数、连通域和平面残差。[P1]、[P10] |

水槽必须重新确定视差区间和阈值；`PLANE_MAX_DISTANCE` 应大于预期波幅，但设置前必须确认坐标是否已恢复物理尺度。[P11]

## 6. 平面汇总与 `wassgridsurface`

| 项目 | 内容 |
|---|---|
| 输入 | `*_wd`、`mesh_cam.xyzC`、相机矩阵、根目录 `planes.txt`、`--baseline`。[P2] |
| 输出 | `gridconfig.txt`、`area_grid.png`、`config.mat`、诊断图、`gridded.nc`。[P2] |
| 配置 | 区域中心/大小、Nx/Ny；baseline、fps、图像尺寸、插值、掩膜、子采样、随机种子。[P2] |
| 依赖 | Python ≥3.9、PyTorch、SciPy、NumPy、OpenCV、netCDF4、h5py 等。[P12] |
| 关键参数 | area、grid size、baseline、DCT/IDW/LinearND、random seed、force-zero-mean。[P2] |
| 失败/指标 | 无帧/平面/点云/矩阵、尺寸未知、网格出覆盖区、掩膜过低或插值孔洞；比较散点-网格残差。[P2] |

v1.5 如何把每帧 `plane.txt` 汇总成 `planes.txt`，旧核心文档未确认一键命令，标为 **UNKNOWN/TODO**。论文采用逐帧平面参数平均，但实现必须处理法向同向、归一化和异常帧，不能盲目平均。[P5]

## 7. 本项目高度

确认单位、法向和尺度后：

$$H(x,y,t)=Z(x,y,t)-Z_0(x,y).$$

用独立静水序列估计 `Z0`，保存样本数、标准差、有效率和掩膜。`--force-zero-mean` 只能做对照，不能未经验证替代静水平均面。

## 来源

- [P1] [getting started](https://sites.google.com/unive.it/wass/software/wass/getting-started)
- [P2] [`wassgridsurface.py`](https://github.com/fbergama/wass/blob/master/gridding/wassgridsurface/wassgridsurface.py)
- [P3] [configuration](https://sites.google.com/unive.it/wass/software/wass/configuration)
- [P4] [`wass_prepare.cpp`](https://github.com/fbergama/wass/blob/v_1.5/src/wass_prepare/wass_prepare.cpp)
- [P5] [WASS paper](https://www.dsi.unive.it/wass/papers/1-s2.0-S0098300417304302-main.pdf)
- [P6] [`wass_match.cpp`](https://github.com/fbergama/wass/blob/v_1.5/src/wass_match/wass_match.cpp)
- [P7] [matcher configuration](https://sites.google.com/unive.it/wass/software/wass/matcher-configuration)
- [P8] [`wass_autocalibrate.cpp`](https://github.com/fbergama/wass/blob/v_1.5/src/wass_autocalibrate/wass_autocalibrate.cpp)
- [P9] [v1.5 CMake](https://github.com/fbergama/wass/blob/v_1.5/src/CMakeLists.txt)
- [P10] [`wass_stereo.cpp`](https://github.com/fbergama/wass/blob/v_1.5/src/wass_stereo/wass_stereo.cpp)
- [P11] [stereo configuration](https://sites.google.com/unive.it/wass/software/wass/dense-stereo-configuration)
- [P12] [gridding metadata](https://github.com/fbergama/wass/blob/master/gridding/pyproject.toml)
