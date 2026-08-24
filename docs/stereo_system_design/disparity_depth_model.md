# 双目视差与深度分辨率工程设计模型

## 1. 目的与边界

本模块用于未来专业双目相机的 baseline、工作距离、rectified 像素焦距、视差搜索范围和理论深度分辨率设计。它是理想平行双目的一阶工程计算工具，不配置或修改 WASS，也不把理论灵敏度解释为实测精度。

HomeTank_004 手机实验仅用于验证双目系统设计模型和完整处理链，不用于形成最终工程参数，也不在本文中进行手机专项调参。

## 2. 数学模型

理想校正双目中的深度关系为：

$$
Z=\frac{fB}{d},
$$

等价的视差关系为：

$$
d=\frac{fB}{Z}.
$$

变量与单位如下：

| 变量 | 物理意义 | 单位 | 约束 |
|---|---|---|---|
| $Z$ | 沿校正相机光轴的目标深度/工作距离 | m | $Z>0$ |
| $f$ | 校正后投影矩阵对应的像素焦距 | px | $f>0$ |
| $B$ | 两相机投影中心之间的基线长度 | m | $B>0$ |
| $d$ | 同名点在校正左右图中的水平视差 | px | $d>0$ |

由 $Z=fB/d$ 对 $d$ 求导，一阶误差幅值为：

$$
|\Delta Z|=\frac{Z^2}{fB}|\Delta d|.
$$

其中 $|\Delta d|$ 的单位为 px，$|\Delta Z|$ 的单位为 m。该式只描述局部视差不确定度传播；标定误差、同步误差、匹配离群、畸变残差、反光和振动必须另行进入完整误差预算。数学关系与项目已有的[双目重建模型](../mathematical_model/stereo_reconstruction_model.md)和[误差传播模型](../mathematical_model/error_propagation_model.md)一致。

## 3. 工具接口与工程意义

实现位于 `src/stereo_analysis/`：

- `expected_disparity(B, f, Z)`：计算名义视差；
- `depth_from_disparity(B, f, d)`：计算理想深度；
- `analyze_disparity_design(...)`：给定名义深度和可选的近/远深度范围，输出视差范围；
- `depth_resolution(...)`：计算指定视差不确定度对应的一阶深度误差。

所有公开参数名显式带有 `_m`、`_px` 或 `_mm` 单位后缀。工具不会猜测单位或把 mm 自动换成 m。若没有给定近/远部署范围，`depth_range_m=(Z,Z)`，所得 `disparity_range_px` 只是名义点；只有部署方明确给出物理深度范围后，才可用于设计实际 matcher 搜索范围。

`recommended_disparity_center_px` 定义为理想视差区间上下界的算术中点。它便于比较候选几何，但不是自动生成的 WASS/SGBM 参数，也未包含实现所需的安全裕量、16 px 对齐或离群范围。

工程上：增大 $B$ 或 $f$ 会增大同一深度的视差并降低一阶深度灵敏度；增大 $Z$ 会减小视差，并使深度误差按 $Z^2$ 增长。最终设计还必须同时检查公共视场、遮挡、标定可行性、纹理、同步和算法有效域。

## 4. Case 1：HomeTank_004 模型验证输入

| 参数 | 数值 | 单位 | 来源 | 状态 |
|---|---:|---|---|---|
| baseline $B$ | 0.0686847 | m | HomeTank_004 OpenCV 标定结果 | `CALIBRATED_INPUT_WITH_FAILED_QUALITY_GATE` |
| rectified focal length $f$ | 3255.98 | px | alpha-zero rectification 审计 | `RECTIFICATION_OUTPUT` |
| example distance $Z$ | 0.4 | m | 本任务给定的模块输入示例 | `MODEL_EXAMPLE_INPUT`，不是 HomeTank 实测距离 |

模型输出为：

$$
d_{model}=\frac{3255.98\times0.0686847}{0.4}=559.090\ \mathrm{px}.
$$

因为没有为该案例提供独立确认的近/远深度范围，工具返回 `depth_range_m=[0.4,0.4]`、`disparity_range_px=[559.090,559.090]` 和同值的设计中心；这不是对真实场景视差范围的声明。

现有 [HomeTank_004 disparity range audit](../../experiments/real_video/HomeTank_004/wass_disparity_range_audit.md) 记录的 WASS 有效视差如下：

| Static frame | Mean (px) | Median (px) | P5 (px) | P95 (px) |
|---|---:|---:|---:|---:|
| 000000 | 585.272 | 639.546 | 262.498 | 640.559 |
| 000001 | 488.817 | 629.629 | 48.483 | 640.554 |
| 000002 | 478.108 | 627.580 | 58.623 | 640.554 |

559.090 px 落在实际有效视差的宽分布内，但各帧中位数和 P95 接近 640 px 搜索边界。模型输入的 0.4 m 不是实测逐点深度，而 WASS 统计覆盖多个空间表面和变化的匹配支持，因此二者不能被当作逐点残差，也不能据此修改手机 WASS 参数。此案例只验证公式、单位和设计工具能够连接到已有可追溯数据。

## 5. Case 2：未来工业相机设计示例

| 参数 | 数值 | 单位 | 来源 | 状态 |
|---|---:|---|---|---|
| baseline $B$ | 0.25 | m | 本任务给定示例 | `DESIGN_EXAMPLE` |
| focal length $f$ | 3000 | px | 本任务给定示例 | `DESIGN_EXAMPLE` |
| nominal distance $Z$ | 2.0 | m | 本任务给定示例 | `DESIGN_EXAMPLE` |
| disparity uncertainty $|\Delta d|$ | 0.1 | px | 本任务给定误差示例 | `DESIGN_EXAMPLE` |

输出为：

$$
d=375.000\ \mathrm{px},
$$

$$
|\Delta Z|=0.0005333\ \mathrm{m}=0.5333\ \mathrm{mm}.
$$

未提供部署深度区间，所以当前视差范围为名义单点 `[375,375] px`，不能当作 matcher 的完整搜索范围。0.5333 mm 是理想一阶视差贡献，不是工业相机系统已经能够达到的精度。

## 6. 专业系统设计流程

未来专业双目相机选型时，应把实际候选传感器/镜头标定得到的 rectified $f$、可调 $B$、明确的最近/最远 $Z$ 和有依据的 $\Delta d$ 输入本工具，形成候选几何表。随后联合检查：

1. 全部署深度范围的最小/最大视差是否落入算法有效范围并保留裕量；
2. 公共视场和遮挡是否满足水面测量域；
3. 一阶 $|\Delta Z|$ 是否低于分配给视差项的误差预算；
4. 标定、同步、结构刚度、成像和水面光学误差加入后，总预算是否仍满足目标；
5. 最终参数是否经静水、刚体尺度和人工波独立实测验收。

因此，本工具服务于参数设计与排除不合理组合，不能替代 WASS、标定或物理验收。
