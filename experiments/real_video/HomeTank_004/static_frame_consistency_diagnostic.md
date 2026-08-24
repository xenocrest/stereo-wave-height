# HomeTank_004 Static Frame Consistency Diagnostic

## 1. 实验目的与冻结边界

本实验用于分析真实双目系统跨帧重建误差来源，不针对手机设备优化。方法面向后续专业双目相机：在固定几何和算法条件下，把不稳定性分解为输入图像变化、匹配支持变化和固定几何不确定性。

本诊断只读取已存在的三个 static 工作目录，不重新运行 WASS。三帧使用相同 `K0/D0/K1/D1/R/T`、`alpha=0`、`CALIB_ZERO_DISPARITY` 和 WASS 配置；未运行 autocalibrate 或 wave，未修改标定、人工测量数据、RANSAC 或正式 WASS 参数。历史状态保持 `CALIBRATION_QUALITY_FAIL`、`STATIC_VALIDATION_FAIL` 和 `approved_for_wass=false`。

数据来源为仓库外冻结目录 `D:/stereo-wave-height-runs/HomeTank_004/static-full-calibration-valid-point-ransac-20260822`。完整数值见 [YAML result](static_frame_consistency_diagnostic.yaml)，固定外参与坐标状态的哈希证据见 [previous geometry diagnostic](static_frame_geometry_diagnostic.md)。

## 2. 方法

### 2.1 Rectified 图像

读取 WASS 每帧保存的 `stereo.jpg` rectified montage，并按其计算顺序拆分。WASS 已确认 auto-swap，因此 computational left 对应原始 cam1/right，computational right 对应原始 cam0/left。每幅灰度图统计 mean、standard deviation、min/max；16-bin 概率直方图差异采用 total-variation distance：

$$
D_{TV}(p,q)=\frac{1}{2}\sum_k|p_k-q_k|.
$$

该值为 0 表示直方图相同，1 表示无重叠。它描述全图成像分布变化，不证明 autofocus、EIS 或曝光中的某一个具体机制。

### 2.2 Common texture support

`precluster_depth.bin` 的有效字节平面是 WASS 三角化前后可追溯的有效视差/深度支持掩码。对任意两帧 $M_i,M_j$ 计算：

$$
Overlap_{ij}=\frac{|M_i\cap M_j|}{|M_i\cup M_j|}.
$$

这里只测量原始支持，不插值、不扩大掩码，也不改变任何正式输出。

### 2.3 Disparity、深度与平面

视差统计沿用冻结的 [disparity range audit](wass_disparity_range_audit.md)：它是 valid triangulated points 的 effective rectified disparity，不是未保存的 lossless SGBM float array。冻结 runtime 只保留 min/max-normalized PNG，不能可靠恢复绝对视差 histogram 或 min/max，因此这些字段明确为 `UNKNOWN/NOT_AVAILABLE_FROM_FROZEN_RUNTIME`，没有用显示图猜数值。

深度漂移定义为共同有效像素域上的：

$$
\Delta Z_i=Z_i-Z_{000000},
$$

并统计 signed mean、RMS 和 P95 absolute drift。另保留最终 XYZ 的 mean Z 变化，两种统计不能互相替代。

将已有 $z=ax+by+c$ 转换为统一隐式模型：

$$
Ax+By+Cz+D=0,
$$

记录单位法向量、相对相机 $+Z$ 轴的 tilt 和 signed plane offset。

## 3. Rectified 图像结果

| Frame | Computational left / cam1 mean ± std | Computational right / cam0 mean ± std |
|---|---:|---:|
| 000000 | 106.934 ± 49.777 | 126.708 ± 53.904 |
| 000001 | 111.801 ± 52.126 | 114.236 ± 52.204 |
| 000002 | 109.033 ± 50.524 | 113.045 ± 51.647 |

| Pair | Left/cam1 histogram TV | Right/cam0 histogram TV |
|---|---:|---:|
| 000000–000001 | 0.2030 | 0.4022 |
| 000000–000002 | 0.1357 | 0.4242 |
| 000001–000002 | 0.1164 | 0.0645 |

图像 000000 与后两帧之间存在明显亮度分布变化，尤其 computational right/original cam0 的 TV 超过 0.40。000001 与 000002 更接近。这证明输入图像并非跨帧光度恒定，但单凭全图统计不能确定变化来自自动曝光、焦距/EIS、场景内容还是它们的组合。

## 4. 匹配支持与 disparity

| Frame | Valid disparity count | Valid ratio | Mean d (px) | Median d (px) | P5 (px) | P95 (px) |
|---|---:|---:|---:|---:|---:|---:|
| 000000 | 216,874 | 10.4588% | 585.2716 | 639.5457 | 262.4985 | 640.5586 |
| 000001 | 133,968 | 6.4606% | 488.8168 | 629.6289 | 48.4831 | 640.5543 |
| 000002 | 141,950 | 6.8456% | 478.1076 | 627.5800 | 58.6234 | 640.5536 |

| Pair | Intersection | Union | Mask overlap / IoU |
|---|---:|---:|---:|
| 000000–000001 | 55,674 | 295,168 | 18.8618% |
| 000000–000002 | 57,062 | 301,762 | 18.9096% |
| 000001–000002 | 62,915 | 213,003 | 29.5371% |

所有帧 P95 都贴近 640 px 搜索上界，disparity saturation 迹象仍存在；同时 mean/P5 和有效数量大幅变化。两两 mask overlap 只有 18.9%–29.5%，直接证明 WASS 每帧使用的可观测区域不一致。扩大视差范围已经在前一受控实验中失败，因此这里不改变 matcher 配置。

## 5. 深度与平面稳定性

以 000000 为参考，最终 XYZ mean Z 分别变化 `+40.397 mm` 和 `-56.836 mm`。共同 precluster lattice 的结果如下；大 RMS/P95 由不一致匹配造成，不能解释为静水真实运动：

| Frame vs 000000 | Common pixels | Mean ΔZ (mm) | RMS ΔZ (mm) | P95 |ΔZ| (mm) |
|---|---:|---:|---:|---:|
| 000001 | 55,674 | -34.867 | 712.751 | 495.639 |
| 000002 | 57,062 | -27.577 | 693.343 | 299.068 |

| Frame | Normal $(A,B,C)$ | Tilt (deg) | Offset (m) | Plane residual RMS (mm) |
|---|---|---:|---:|---:|
| 000000 | (-0.417173, -0.071064, 0.906045) | 25.0357 | -0.359858 | 2.2491 |
| 000001 | (-0.322558, -0.034156, 0.945933) | 18.9269 | -0.366837 | 2.1611 |
| 000002 | (-0.505074, 0.033909, 0.862410) | 30.4118 | -0.345712 | 2.0065 |

最大法向夹角为 12.1664°，signed offset 范围为 21.126 mm。单帧 residual RMS 约 2 mm 只说明各自保留区域可拟合为平面，不能抵消跨帧法向、offset、支持域和 mean Z 的不一致。

## 6. 结论分类

最终分类：**`MIXED`，由 `IMAGE_VARIATION` 与 `MATCHING_INSTABILITY` 共同构成**。

证据排序：

1. `K/D/R/T`、rectification 和 WASS 配置跨帧相同，未发现 frame-dependent coordinate transform；
2. rectified 图像亮度直方图明显变化，尤其 000000 对后两帧的 cam0 TV 为 0.402–0.424；
3. disparity 支持率从 10.46% 变为 6.46%/6.85%，两两 IoU 低至约 0.189；
4. P95 持续贴近搜索上界，且低视差尾部、平面法向和深度同时变化。

因此当前跨帧漂移不是单一固定外参变化，也不能仅归为统一 disparity bias。标定质量门失败意味着 `GEOMETRIC_UNCERTAINTY` 仍存在于绝对测量链，但固定参数本身不能解释三帧不同的支持域；它不是本诊断确认的首要 frame-to-frame 驱动因素。

## 7. 工程用途与下一步

该方法可直接用于未来专业双目相机部署：冻结硬件同步、曝光、标定和 matcher 后，先验收 rectified 图像分布、mask IoU、disparity boundary margin、共同域深度漂移和 plane stability，再处理动态波面。

HomeTank_004 保持 `STATIC_VALIDATION_FAIL`，wave 仍禁止。下一步应采集或使用能够锁定曝光、焦距、防抖与硬件同步状态的专业相机输入，并为部署几何预留明确 disparity margin；这不是对特定手机型号增加补偿。
