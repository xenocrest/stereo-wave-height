# WASS 面向实验室人工波的尺度与硬件适配论证

## 1. 结论边界

WASS 的处理链并不把物理尺度固定为海上尺度，因此**原则上可用于水槽**；但 WASS 论文与官方默认配置主要针对约 10 m 工作距离、米级基线和海面纹理。本项目的 1 cm 目标只能表述为“在下述几何、同步、标定和验证条件下理论上可行”，不能表述为已经达到。

基线固定为 WASS `v_1.5`（commit `59f1b1c46c41a7d0baf85fc2b21e062eaf552feb`）与 `wassgridsurface 0.11.4`。不修改 WASS 源码；静水基准和验收均在其输出之后完成。

## 2. WASS 原始尺度与本项目候选尺度

| 项目 | WASS 论文示例/官方说明 | 本项目候选或约束 | 状态 |
|---|---:|---:|---|
| 工作距离/相机高度 | 12.5 m；默认参数说明约 10 m | 水槽实测值，尚未给定 | **TODO** |
| 基线 | 2.5 m；论文建议海上布置约 `B/Z=0.10` | 可调刚性基线，数值待几何预算和视场验证 | **TODO** |
| 相机 | 2456×2048，3.45 µm，5 mm，15 fps | **暂定/候选** MER2-503-36U3C：2448×2048，3.45 µm，约 8 mm，最高 36 fps | 镜头型号 **UNKNOWN** |
| 空间网格 | 论文示例 0.2 m | 依最短目标波长和点密度重设 | **TODO** |
| 目标波长 | WASS 典型应用约 0.2–50 m | 人工波范围未给定 | **TODO** |
| 高度指标 | 论文未给出本水槽的 1 cm 保证 | `H=Z-Z0`，RMSE 目标 ≤10 mm | 项目验收目标 |

WASS 示例数字来自其论文第 4 节；官方 dense-stereo 页面明确说默认参数针对约 5 MP、距海面约 10 m、近似平行光轴的系统，其他布置需要调参。[WASS 论文](https://www.dsi.unive.it/wass/papers/1-s2.0-S0098300417304302-main.pdf)，[官方 dense-stereo 配置](https://sites.google.com/unive.it/wass/software/wass/dense-stereo-configuration)

## 3. 双目几何与尺度推导

对已校正、近似平行的双目模型：

$
Z=\frac{f_{px}B}{d},\qquad d=\frac{f_{px}B}{Z}
$

其中：

- `Z`：相机到目标点的深度，单位 m；
- `B`：相机光心基线长度，单位 m；
- `f_px`：以像素表示的有效焦距，单位 px；
- `d`：校正图像中的视差，单位 px。

对视差作一阶误差传播：

$
\sigma_{Z,d}=\left|\frac{\partial Z}{\partial d}\right|\sigma_d
=\frac{Z^2}{f_{px}B}\sigma_d
=\frac{Z}{f_{px}r}\sigma_d,\quad r=\frac{B}{Z}
$

其中 `sigma_d` 是视差标准不确定度（px），`sigma_Z,d` 是仅由视差造成的深度标准不确定度（m），`r` 为无量纲基线/距离比。若给定这一项的允许误差 `epsilon_d`（m）：

$
B\geq\frac{Z^2\sigma_d}{f_{px}\epsilon_d},\qquad
r\geq\frac{Z\sigma_d}{f_{px}\epsilon_d}
$

这些式子来自针孔双目模型的明确数学推导，不是 WASS 的精度承诺。WASS 使用亚像素对应和三角化，但实际 `sigma_d` 必须在本系统上测量。[WASS 论文](https://www.dsi.unive.it/wass/papers/1-s2.0-S0098300417304302-main.pdf)

### 3.1 候选相机的名义计算

候选相机像元尺寸为 3.45 µm；若镜头真实焦距为 8.00 mm，则：

$
f_{px,nom}=\frac{8.00\ \mathrm{mm}}{0.00345\ \mathrm{mm/px}}=2318.8\ \mathrm{px}
$

这是薄透镜名义值。最终计算必须使用标定所得 `fx`、`fy`，不能以 2318.8 px 替代。相机官方规格为 2448×2048、全局快门、3.45 µm、最高 36 fps。[大恒 MER2-503-36U3C 官方页面](https://en.daheng-imaging.com/show-106-1991-1.html)

当 `r=B/Z=0.10` 时，名义视差 `d=f_px*r≈232 px`；当 `r=0.05` 时约 116 px。两者都在 WASS 默认 `MIN_DISPARITY=1`、`MAX_DISPARITY=640` 内，但这不等于匹配一定成功，仍需以校正后的视差直方图设置范围。

以下只取 `sigma_d=0.5 px` 作为**设计情景**，并非已测 WASS 性能：

| `Z` (m) | `sigma_Z,d`，`r=0.05` (mm) | `sigma_Z,d`，`r=0.10` (mm) | 为 `epsilon_d=5 mm` 所需 `B_min` (m) | 为 `epsilon_d=10 mm` 所需 `B_min` (m) |
|---:|---:|---:|---:|---:|
| 0.5 | 2.156 | 1.078 | 0.0108 | 0.0054 |
| 1.0 | 4.313 | 2.156 | 0.0431 | 0.0216 |
| 1.5 | 6.469 | 3.234 | 0.0970 | 0.0485 |
| 2.0 | 8.625 | 4.313 | 0.1725 | 0.0863 |
| 3.0 | 12.938 | 6.469 | 0.3881 | 0.1941 |

为了给总 10 mm 预算留出标定、静水基准、同步和网格误差，表中优先使用 `epsilon_d=5 mm` 列。由此，在 `r≈0.10` 且 `sigma_d≤0.5 px` 的假设下，视差项 ≤5 mm 要求 `Z≤2.32 m`。若 `Z=3 m`，需 `r≥0.129`，或把实测 `sigma_d` 降至约 0.386 px 以下。这些都是设计条件，尚未验证。

传感器名义宽度为 `2448 px × 3.45 µm = 8.4456 mm`。忽略畸变时，8 mm 镜头在距离 `Z` 的水平覆盖宽度约为 `Z×8.4456/8 = 1.056Z`；实际公共视场必须用实测内外参和校正 ROI 检查。

### 3.2 其他一阶尺度误差

由 `Z=f_px B/d`：

$
\frac{\delta Z}{Z}\approx\frac{\delta f_{px}}{f_{px}}+
\frac{\delta B}{B}-\frac{\delta d}{d}
$

`delta Z`、`delta B` 为 m，`delta f_px`、`delta d` 为 px；比值均无量纲。该式说明基线测量和焦距标定会造成尺度偏差。对相同几何下的 `H=Z-Z0`，共同尺度因子对绝对深度的偏差可部分抵消，但仍会按比例缩放波高，不能因此省略刚体尺度验证。

## 4. 候选硬件适配

### 4.1 已确认满足的接口条件

- 两台候选相机均可输出同步帧所需的全局快门图像，并支持外部触发输入；WASS 只消费已组织好的图像对，不控制相机。[大恒官方页面](https://en.daheng-imaging.com/show-106-1991-1.html)，[产品手册 PDF](https://www.daheng-imaging.com/uploadfile/2022/1008/20221008040932126.pdf)
- 分辨率接近 WASS 论文的 5 MP 示例，不构成格式上的硬性障碍。
- WASS `wass_prepare` 以 OpenCV `IMREAD_GRAYSCALE` 读取 `000000_c0.*`/`000000_c1.*` 等图像并产生校正 PNG，因此可在 WASS 之前做确定性的格式转换。[wass_prepare 源码](https://github.com/fbergama/wass/blob/v_1.5/src/wass_prepare/wass_prepare.cpp)
- 自定义内参通过 OpenCV YAML `intrinsics_00.xml`、`intrinsics_01.xml` 提供；外参由匹配/自动标定链求得并以尺度不定形式保存，物理基线再进入尺度恢复。[官方配置](https://sites.google.com/unive.it/wass/software/wass/configuration)，[wass_autocalibrate 源码](https://github.com/fbergama/wass/blob/v_1.5/src/wass_autocalibrate/wass_autocalibrate.cpp)

### 4.2 图像位深与组织

官方列出的该彩色型号像素格式为 `BayerRG8`、`BayerRG10`，像素位深为 8/10 bit；没有找到该型号 12/16 bit 输出的官方依据，因此标为 **不适用/UNKNOWN**，不能假定支持。

建议的非算法性输入准备为：

1. 两相机使用相同曝光、增益、gamma、白平衡策略，关闭会造成逐相机/逐帧漂移的自动项；具体 GenICam 节点名 **TODO**。
2. 对 BayerRG8/10 使用相同版本和参数去马赛克，再按固定黑电平/白电平线性映射为 8-bit 灰度；映射参数和饱和比例写入实验元数据。WASS 是否可直接、无损地处理任意 16-bit PNG/TIFF 为 **UNKNOWN/TODO**，本阶段不依赖该假设。
3. 输出无损 PNG，命名为同一帧号的 `000000_c0.png`、`000000_c1.png`；触发序号、设备时间戳、丢帧标志另存小型清单。
4. 严禁用“最近时间戳”静默拼对；任何帧号断裂、触发计数不一致均判为无效帧对。

灰度 8-bit 是当前最可控的复现输入策略，并非 WASS 论文证明 10-bit 无用。水面匹配仍需要可观测纹理；是否使用示踪粒子、投影纹理或其他成像条件属于实验设计 **TODO**。

### 4.3 尚无硬性不满足项，但有未关闭条件

当前公开规格没有显示硬性不兼容项。以下条件尚未确认，因此不能作采购结论：

- 约 8 mm 镜头的准确型号、畸变、MTF、工作距离和景深：**UNKNOWN/TODO**；
- 两机共用触发时的曝光起始偏差与抖动：官方未给数值，**UNKNOWN/TODO，必须实测**；
- 双 USB3 在 2448×2048、目标帧率下持续无丢帧：**TODO**；
- 36 fps 是否覆盖目标人工波最高频率：波频未给定，**TODO**；
- 基线刚度、热漂移、公共视场及 WASS 三角化角阈值能否同时满足：**TODO**。

## 5. 最大尺度风险

1. **透明/镜面水面的纹理与反射**可能使对应关系不稳定；这是比像素数更直接的风险，必须用匹配有效率、视差不确定度和空洞率实测。
2. WASS 默认 `TRIANG_MIN_ANGLE=20°`，而 `B/Z=0.10` 的小角近似会聚角约 `atan(0.10)=5.71°`。其源码语义和水槽几何必须用合成/刚体场景核验，默认值不可直接沿用。
3. 1 cm 是完整测量链目标；视差公式只覆盖一个误差分量。标定、尺度、静水参考、同步和网格化必须共同进入验收。

## 6. 来源

- [WASS `v_1.5` 源码](https://github.com/fbergama/wass/tree/v_1.5)
- [WASS 论文](https://www.dsi.unive.it/wass/papers/1-s2.0-S0098300417304302-main.pdf)
- [WASS 官方 dense-stereo 配置](https://sites.google.com/unive.it/wass/software/wass/dense-stereo-configuration)
- [大恒 MER2-503-36U3C 官方规格](https://en.daheng-imaging.com/show-106-1991-1.html)
- [大恒 MER2 系列产品手册](https://www.daheng-imaging.com/uploadfile/2022/1008/20221008040932126.pdf)
