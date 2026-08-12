# WASS 源码与架构分析

## 总体架构

WASS 是单用途可执行程序组成的流水线。每个同步帧对对应一个 `NNNNNN_wd/`；除 `wass_autocalibrate` 汇总多目录外，其余步骤按帧独立。WASSjs 负责队列、并行进程和 Web 状态，每个核心程序本身处理一个工作目录。[A1]

```text
cam0/cam1 + calibration/config
              │
        wass_prepare
              │ *_wd
        wass_match ─────┐
              └── wass_autocalibrate
                         │ ext_R/ext_T
                    wass_stereo
                         │ mesh_cam.xyzC + plane.txt
                  wassgridsurface
                         │ gridded.nc
```

## 源码目录职责

| 路径 | 职责 | 依赖/接口 | 来源 |
|---|---|---|---|
| `src/wass_prepare` | 去畸变、建工作目录、复制可用外参 | OpenCV、Boost | [A2] |
| `src/wass_match` | OpenSURF 特征、候选匹配、极线过滤和统计 | OpenCV、OpenSURF、incfg | [A3] |
| `src/wass_autocalibrate` | 汇总匹配、本质矩阵、姿态和 SBA | OpenCV、SBA、LAPACK/BLAS | [A4] |
| `src/wass_stereo` | 校正、稠密视差、三角化、过滤、平面和点云 | OpenCV 3.x、Boost、incfg | [A5] |
| `src/wass_lib` | 极线误差、三角化等共享逻辑 | OpenCV | [A6] |
| `WASSjs` | Node.js/Redis 控制器和 Web UI | 共享文件系统 | [A1]、[A7] |
| `Docker*` | Ubuntu 16.04 构建和三个数据卷 | Docker、OpenCV 3.4、Node 8 | [A8] |
| `matlab` | 读取压缩点云、按海面平面对齐和乘尺度 | MATLAB | [A9] |
| `master/gridding` | 点云插值、规则网格和 NetCDF | Python ≥3.9、PyTorch/SciPy/netCDF4 等 | [A10] |

## 坐标、尺度和静水面

自动标定源码最终把平移向量归一化，所以结构只有相对尺度。[A4] 论文示例用实测 2.5 m 基线乘回物理尺度，并把各帧平面参数汇总为平均海平面。[A11]

`wass_stereo` 每帧拟合 `plane.txt` 并用 `PLANE_MAX_DISTANCE` 过滤；它不是本项目的静水产品。[A5] 本项目固定：

$$
H(x,y,t)=Z(x,y,t)-Z_0(x,y).
$$

`Z0(x,y)` 应由独立静水序列经过相同标定、重建、尺度恢复、对齐、网格和掩膜流程得到。`wassgridsurface --force-zero-mean` 是对处理序列逐网格点减时间均值，是否等价于独立静水基准为 **否/不可默认**。[A10]

## 质量信息

- `wass_match` 的 `matcher_stats.csv` 保存过滤后匹配数和极线误差统计。[A3]
- `wass_autocalibrate` 记录结构重投影、初始和 SBA 后极线误差；总匹配少于 8 直接失败。[A4]
- `wass_stereo` 默认要求至少 100 个三角点进入平面估计，并拒绝重投影误差大于 1 px 的点。[A5]
- `stereo.jpg`、`disparity_coverage.jpg`、`disparity_final_scaled.png`、`graph_components.jpg` 是人工 QA 入口。[A1]

## 能力边界

- 自定义内参：支持 3×3 OpenCV XML；畸变文件缺失时按零畸变。[A2]
- 自定义外参：支持 3×3 R、3×1 T；可靠外参存在时可跳过 match/autocalibrate。[A1]、[A2]
- 双工业相机：只要导出 OpenCV 可读、成对、同尺寸灰度图，原则上可接入；所有厂商 RAW 直接支持为 **UNKNOWN**。[A2]
- 同步帧对：支持，但 WASS 不用帧间时间差，采集系统必须保证同步。[A1]
- 垂直双目：官方明确不支持；采用水平基线。[A12]

## 来源

- [A1] [official getting started](https://sites.google.com/unive.it/wass/software/wass/getting-started)
- [A2] [`wass_prepare.cpp`](https://github.com/fbergama/wass/blob/v_1.5/src/wass_prepare/wass_prepare.cpp)
- [A3] [`wass_match.cpp`](https://github.com/fbergama/wass/blob/v_1.5/src/wass_match/wass_match.cpp)
- [A4] [`wass_autocalibrate.cpp`](https://github.com/fbergama/wass/blob/v_1.5/src/wass_autocalibrate/wass_autocalibrate.cpp)
- [A5] [`wass_stereo.cpp`](https://github.com/fbergama/wass/blob/v_1.5/src/wass_stereo/wass_stereo.cpp)
- [A6] [`wass_lib`](https://github.com/fbergama/wass/tree/v_1.5/src/wass_lib)
- [A7] [`WASSjs/Wass.js`](https://github.com/fbergama/wass/blob/v_1.5/WASSjs/Wass.js)
- [A8] [v1.5 Dockerfile](https://github.com/fbergama/wass/blob/v_1.5/Dockerfile)
- [A9] [v1.5 MATLAB helpers](https://github.com/fbergama/wass/tree/v_1.5/matlab)
- [A10] [official gridding source](https://github.com/fbergama/wass/tree/master/gridding)
- [A11] [Bergamasco et al. 2017](https://www.dsi.unive.it/wass/papers/1-s2.0-S0098300417304302-main.pdf)
- [A12] [official stereo configuration](https://sites.google.com/unive.it/wass/software/wass/dense-stereo-configuration)
