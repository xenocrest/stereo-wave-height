# WASS 输入输出规范

## 数据目录

官方样例语义如下，数据不得提交到本仓库：[I1]

```text
dataset/
├── input/
│   ├── cam0/000000_<timestamp>_01.tif
│   └── cam1/000000_<timestamp>_02.tif
├── config/
│   ├── intrinsics_00.xml
│   ├── intrinsics_01.xml
│   ├── distortion_00.xml
│   ├── distortion_01.xml
│   ├── ext_R.xml              # 可选
│   ├── ext_T.xml              # 可选
│   ├── matcher_config.txt
│   └── stereo_config.txt
└── output/                    # 运行时生成
```

## 图像输入

| 字段 | 规范 | 状态/来源 |
|---|---|---|
| 帧配对 | 左右同序号成对 | 已确认：[I1] |
| 样例 | TIFF；6 位序号、13 位时间戳、相机号 | 已确认：[I1] |
| 核心读取 | OpenCV 灰度读取 | 已确认：[I2] |
| 尺寸 | 左右一致；网格工具可从去畸变图推断或用 `-Iw/-Ih` | 已确认：[I2]、[I3] |
| 工业相机 RAW/Bayer | 先导出无损 TIFF/PNG | 直接支持 **UNKNOWN/TODO** |
| 同步 | 帧对独立处理，不做时差校正 | 已确认：[I1]；阈值 **TODO** |
| 纹理/曝光 | 非朗伯、反光和低纹理会破坏匹配 | 已确认：[I4] |

## 标定文件

- `intrinsics_00/01.xml`：3×3 内参。[I5]
- `distortion_00/01.xml`：5 参数畸变；缺失时源码使用零畸变。[I2]
- `ext_R.xml`、`ext_T.xml`：可选 3×3 R 和 3×1 T；形状有效时复制到工作目录。[I2]
- XML 容器应以官方样例为模板。第三方 OpenCV XML 节点兼容性 **TODO**。[I2]

## 控制器配置

`settings.json` 定义二进制路径、HTTP 端口、`num_frames_to_match` 和 prepare/match/stereo 并行数。[I5]

| `worksession.json` 键 | 含义 | 来源 |
|---|---|---|
| `cam0_datadir`, `cam1_datadir` | 左右图目录 | [I5] |
| `workdir` | 输出根目录 | [I5] |
| `confdir` | 标定/算法配置目录 | [I5] |
| `savediskspace` | 删除部分中间产物 | [I5]、[I6] |
| `keepimages` | 保留高分辨率去畸变图 | [I5] |
| `zipoutput` | 压缩工作目录；旧控制器 Windows 路径不压缩 | [I5]、[I6] |
| `match_config_file`, `dense_stereo_config_file` | 算法配置文件名 | [I5] |
| `seq_start`, `seq_end` | 处理序号范围 | [I5] |

`matcher_config.txt` 和 `stereo_config.txt` 必须由锁定二进制的 `--genconfig` 生成，再受控调参，避免文档/二进制漂移。[I7]、[I8]

水槽重点核对：disparity min/max/offset、window、dense scale、plane RANSAC/distance、median/morphology/Z-gap、left-right 和点云保存选项。默认海上值不是 1 cm 验收值。[I8]、[I9]

## 每帧主要输出

| 文件 | 内容/用途 | 来源 |
|---|---|---|
| `undistorted/00000000.png`, `00000001.png` | 去畸变图 | [I2] |
| `matches.txt` | 左右像点 | [I7] |
| `matcher_stats.csv` | 匹配数和极线误差统计 | [I7] |
| `ext_R.xml`, `ext_T.xml`, `H.xml` | 外参/单应 | [I10] |
| `disparity_*`, `stereo*.jpg`, `graph_components.jpg` | 视差、覆盖、极线和连通域 QA | [I1] |
| `P0cam.txt`, `P1cam.txt` | 投影矩阵 | [I9] |
| `Cam*_poseR/T.txt` | 相机位姿 | [I1]、[I9] |
| `plane.txt` | 单帧拟合平面 4 参数 | [I9] |
| `mesh_cam.xyzC` | 16 bit 压缩相机坐标点云，后处理首选 | [I1]、[I11] |
| `mesh_cam.xyzbin` | 非压缩 float32 点云 | [I9]、[I11] |
| `mesh.ply` | 可选调试点云，不是推荐主格式 | [I1] |
| `wass_stereo_log.txt` | 点数、过滤和误差日志 | [I1] |

## 网格与 NetCDF

`wassgridsurface` 搜索 `*_wd`，读取压缩点云和矩阵，结合平均平面、baseline、区域与网格配置生成 `config.mat` 和 `gridded.nc`。[I3]

当前开发源码中的 NetCDF 变量包括 `Z(count,X,Y)`、`maskZ`、`X_grid/Y_grid`、`Kx/Ky`、`time`、`workdir`、`scale`、可选 `inputpoints` 与图像/掩膜；meta 组含内参、投影和相机到网格变换。[I12] 源码标注 XYZ grid 为 millimeter，但 baseline 与 `*1000` 转换需要实测验证；0.11.4 与开发源码字段是否完全一致为 **UNKNOWN/TODO**。首个结果必须用 `ncdump -h` 和已知尺度靶核验。[I3]、[I12]

## 本项目输出契约

- 经尺度验证的 `Z(x,y,t)`；
- 独立静水序列的 `Z0(x,y)`；
- `H(x,y,t)=Z(x,y,t)-Z0(x,y)`；
- 有效掩膜、静水标准差/样本数、WASS 点数和误差；
- WASS/submodule/gridder 版本、配置/标定哈希和基线单位。

`H/Z0` 是本项目科学定义，不声称为 v1.5 原生格式。

## 来源

- [I1] [getting started](https://sites.google.com/unive.it/wass/software/wass/getting-started)
- [I2] [`wass_prepare.cpp`](https://github.com/fbergama/wass/blob/v_1.5/src/wass_prepare/wass_prepare.cpp)
- [I3] [`wassgridsurface.py`](https://github.com/fbergama/wass/blob/master/gridding/wassgridsurface/wassgridsurface.py)
- [I4] [WASS paper](https://www.dsi.unive.it/wass/papers/1-s2.0-S0098300417304302-main.pdf)
- [I5] [configuration](https://sites.google.com/unive.it/wass/software/wass/configuration)
- [I6] [`WASSjs/Wass.js`](https://github.com/fbergama/wass/blob/v_1.5/WASSjs/Wass.js)
- [I7] [`wass_match.cpp`](https://github.com/fbergama/wass/blob/v_1.5/src/wass_match/wass_match.cpp)
- [I8] [stereo configuration](https://sites.google.com/unive.it/wass/software/wass/dense-stereo-configuration)
- [I9] [`wass_stereo.cpp`](https://github.com/fbergama/wass/blob/v_1.5/src/wass_stereo/wass_stereo.cpp)
- [I10] [`wass_autocalibrate.cpp`](https://github.com/fbergama/wass/blob/v_1.5/src/wass_autocalibrate/wass_autocalibrate.cpp)
- [I11] [`load_camera_mesh.m`](https://github.com/fbergama/wass/blob/v_1.5/matlab/load_camera_mesh.m)
- [I12] [`netcdfoutput.py`](https://github.com/fbergama/wass/blob/master/gridding/wassgridsurface/netcdfoutput.py)
