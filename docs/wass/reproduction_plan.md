# WASS 复现与实验室适配计划

## 边界

目标是在不改变 WASS 核心算法的前提下，验证双工业相机水槽处理链能否达到约 1 cm 高度误差。上游源码只读；不创建匹配算法、不下载完整数据集、不在当前 Windows 项目环境安装旧编译栈。[R1]

$$H(x,y,t)=Z(x,y,t)-Z_0(x,y).$$

## 环境建议

v1.5 Dockerfile基于 Ubuntu 16.04，固定 OpenCV 3.4.0 和 Node.js 8，并需要 Boost、LAPACK/BLAS、SBA/incfg、Redis。官方说明 OpenCV 4.x 移除旧 C API 后部分代码无法直接编译，推荐 Docker。[R2]、[R3]

后续应在独立 Linux VM、Docker 或 WSL2 中最小构建，挂载只读输入/配置和可写输出；**本次不构建**。旧镜像源能否原样成功为 **UNKNOWN/TODO**。如需兼容补丁，必须在外部构建层记录，不能改上游检出。[R2]

Windows 原生旧说明依赖 Visual Studio 2015、OpenCV、Boost、CLAPACK 和历史二进制，其在现代 Windows 的可用性/可信性 **UNKNOWN**，不作为首选。[R3]

`wassgridsurface==0.11.4` 使用独立 Python ≥3.9 环境；与旧核心容器分离以避免 OpenCV/Python 冲突。[R4]

## 阶段计划

### A. 冻结版本

1. 外部检出 v1.5，核对 WASS 和 incfg SHA。
2. 记录镜像、编译器、依赖和配置哈希。
3. 用锁定二进制生成 matcher/stereo 配置。
4. 不下载 WASS_TEST；先用两对小图做 I/O smoke test。

### B. 工业相机 I/O 与同步

1. 硬触发采集 10–20 对静态靶帧。
2. 导出无损 8 bit TIFF/PNG；单独验证 12/16 bit 转换。
3. 检查计数、时间戳、尺寸、曝光、饱和、模糊和触发抖动。
4. 只跑 prepare，核对去畸变和左右顺序。

通过标准：零丢帧/错配、全部可读；同步阈值按最大水面速度推导，当前 **TODO**。[R5]

### C. 标定和尺度闭环

1. 在实际工作距离/焦距标定内参与畸变。
2. 对比 metric 外部标定 R/T 与 WASS up-to-scale R/T。
3. 用已知长度/平面确认方向、左右和 baseline 只乘一次。
4. 多日期重复标定评估稳定性。

`ext_T` 已为米制时 wassgridsurface 的 `--baseline` 应取 1 还是实测值为 **UNKNOWN/TODO**，必须用尺度靶实证，禁止猜测。[R6]

### D. 静态平面闭环

1. 漫反射刚性平面运行完整核心链。
2. 调整水槽 disparity、offset、window 和 plane 阈值。
3. 检查匹配/SBA误差、覆盖、重投影、点数和平面残差。
4. 网格化后用已知平面验证 NetCDF 单位、法向和尺度。

### E. 静水 `Z0`

1. 保持相机、焦距、标定和光照不变，采集静水同步长序列。
2. 使用与动态波相同配置生成 `Z_static`。
3. 质量过滤后计算每像素 `Z0`、标准差、样本数和掩膜。
4. 验证 `H_static=Z_static-Z0` 均值近 0 且误差达标。

`--force-zero-mean` 只作对照，不替代独立静水序列。[R7]

### F. 人工规则波

1. 从小幅、低频、非破碎波开始。
2. 与独立波高计在配准位置比较幅值、相位、偏差和 RMSE。
3. 逐步扩展幅值、频率、坡度和照明，记录覆盖与失败模式。
4. 达标后才处理长序列。

## 1 cm 验收框架

报告高度 bias、MAE、RMSE、95% 绝对误差，波幅/相位误差，有效覆盖、点数、极线/重投影误差，网格间距与边缘误差，以及标定、基线和同步的不确定度。

“厘米级”究竟指 RMSE、95% 误差还是偏差 ≤1 cm 尚未指定，标为 **UNKNOWN/TODO**，不得选择最宽松定义。[R8]

## 主要适配问题

| 优先级 | 问题 | 判断/验证 |
|---|---|---|
| P0 | unit-scale 与 baseline | 重复乘会比例错误；已知长度靶验证 |
| P0 | 相机几何能否达到 1 cm | 先做误差预算，再静态靶实测 |
| P0 | 独立 `Z0` 稳定性 | 静水长序列、重复日、方差图 |
| P0 | 左右同步 | WASS 不校正；硬触发测量 |
| P1 | 反光/透明/低纹理 | 受控照明/示踪对比，不改算法 |
| P1 | 默认海上参数 | 静态平面逐项调参并留记录 |
| P1 | `planes.txt` 生成 | v1.5 未确认一键路径，保留 TODO |
| P1 | gridder 0.11.4 兼容 | 单帧、`ncdump -h`、尺度靶 |
| P2 | 老旧构建栈 | 隔离最小构建并保存日志 |
| P2 | 垂直双目 | 不支持，采用水平基线 |

## 存储纪律

- 浅克隆固定 tag；不把 WASS 源码纳入本仓库。
- 未经明确需要不下载测试/海上长序列。
- 视频、图像序列、点云、NetCDF、镜像层和缓存不提交。
- 只提交小型配置、清单、哈希、指标和图表。

## 实验室 1 cm 适配入口

在环境冻结与相机 I/O 阶段之间增加只使用小样本的“几何与误差预算闸门”：

1. 按 [lab_scale_adaptation.md](lab_scale_adaptation.md) 记录实际工作距离、标定焦距、基线、公共视场和预期视差，证明视差误差分量满足预算后再采集动态序列。
2. 按 [wass_parameter_mapping.md](wass_parameter_mapping.md) 从 WASS `v_1.5` 默认值建立配置，优先重设视差范围、三角化角、物理边界和网格尺度；扫参只使用固定的小型训练序列。
3. 按 [static_water_reference_integration.md](static_water_reference_integration.md) 采集独立静水序列，在 WASS 输出后构建 `Z0(x,y)`，不修改 WASS 核心算法。
4. 按 [one_cm_error_budget.md](one_cm_error_budget.md) 在未参与调参的刚体、静水和动态序列上验收。理论误差条件不能替代端到端测量。

候选设备 MER2-503-36U3C、约 8 mm 镜头、硬触发和可调刚性基线均保持“暂定/候选”状态；镜头型号、同步抖动、目标波频及双 USB3 持续吞吐仍为 **UNKNOWN/TODO**。

## 来源

- [R1] [official page](https://sites.google.com/unive.it/wass/home)
- [R2] [v1.5 Dockerfile](https://github.com/fbergama/wass/blob/v_1.5/Dockerfile)
- [R3] [installation](https://sites.google.com/unive.it/wass/software/wass/installing)
- [R4] [wassgridsurface 0.11.4](https://pypi.org/project/wassgridsurface/0.11.4/)
- [R5] [getting started](https://sites.google.com/unive.it/wass/software/wass/getting-started)
- [R6] [`wass_autocalibrate.cpp`](https://github.com/fbergama/wass/blob/v_1.5/src/wass_autocalibrate/wass_autocalibrate.cpp)
- [R7] [`wassgridsurface.py`](https://github.com/fbergama/wass/blob/master/gridding/wassgridsurface/wassgridsurface.py)
- [R8] [WASS paper](https://www.dsi.unive.it/wass/papers/1-s2.0-S0098300417304302-main.pdf)
