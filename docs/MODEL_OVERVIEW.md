# 核心建模成果总览

本页用于汇报和首次浏览仓库时快速定位当前已经建立并文档化的三类核心模型：**双目几何模型、水面高度模型、虚拟相机模型**。三类模型均服务于项目唯一目标：由双目图像经过 WASS 三维重建，得到相对静水面的水面高度场 `H(x,y,t)`。

## 1. 双目几何模型

文档：[`mathematical_model/stereo_reconstruction_model.md`](mathematical_model/stereo_reconstruction_model.md)

相关基础：[`mathematical_model/camera_geometry_model.md`](mathematical_model/camera_geometry_model.md)

核心关系（理想平行双目）：

\[
d=u_L-u_R,\qquad Z=\frac{f_{px}B}{d}.
\]

其中：

- `f_px`：像素焦距，单位 px；
- `B`：双目光心基线，单位 m；
- `d`：水平视差，单位 px；
- `Z`：轴向深度，单位 m。

本模型用于说明双目几何和设备参数之间的数理关系；实际匹配、自动标定和三角重建由 WASS 完成，本项目不实现替代算法。

当前候选设备名义参数与模型绑定：MER2-503-36U3C、2448×2048 px、3.45 µm/px、8 mm 候选镜头。实际标定焦距、最终基线和部署工作距离仍按状态管理，不以仿真假设冒充实测值。

## 2. 水面高度模型

文档：[`mathematical_model/height_field_model.md`](mathematical_model/height_field_model.md)

相关流程：[`mathematical_model/height_reconstruction_pipeline.md`](mathematical_model/height_reconstruction_pipeline.md)

动态水面高程：

\[
Z(x,y,t).
\]

独立静水参考：

\[
Z_0(x,y).
\]

最终项目输出：

\[
H(x,y,t)=Z(x,y,t)-Z_0(x,y).
\]

其中 `x,y` 为水平物理坐标（m），`t` 为时间，`Z、Z0、H` 均为 m。`Z` 与 `Z0` 必须具有相同坐标系、尺度、轴方向、规则网格和兼容有效掩膜。

该模型明确了 WASS 三维重建结果如何转换为项目需要的“相对静水面的水面高度”。

## 3. 虚拟相机模型

文档：[`simulation/virtual_camera_model.md`](simulation/virtual_camera_model.md)

候选设备参数来源：[`../configs/equipment/candidate_system.yaml`](../configs/equipment/candidate_system.yaml)

第一阶段采用理想针孔模型：

\[
\mathbf K_{sim}=\begin{bmatrix}
f_{nom}&0&c_x\\
0&f_{nom}&c_y\\
0&0&1
\end{bmatrix},
\qquad
f_{nom}=\frac{8.0\ \mathrm{mm}}{0.00345\ \mathrm{mm/px}}
\approx 2318.84\ \mathrm{px}.
\]

候选设备绑定：

- 图像尺寸：2448×2048 px；
- 像元间距：3.45 µm/px；
- 镜头名义焦距：8 mm；
- 名义像素焦距：约 2318.84 px，状态 `SIMULATION_NOMINAL`；
- 主点取图像中心仅为 `simulation_assumption`；
- 第一阶段畸变设为零，仅为理想仿真假设；
- baseline 和 working distance 为显式部署/仿真参数，不代表最终硬件值。

该模型用于依据候选设备的几何参数生成具有已知高度真值的虚拟双目观测。合成图像在理想几何关系上对应候选设备，但不等同于真实相机拍摄：当前不模拟真实水面反射、环境光变化、相机抖动和真实传感器噪声。

## 4. 三类模型在当前验证链中的关系

```text
候选设备参数
  ↓
虚拟相机模型
  ↓
具有已知 H_true 的虚拟双目图像
  ↓
WASS 双目三维重建
  ↓
Z(x,y,t)
  ↓
独立静水参考 Z0(x,y)
  ↓
水面高度模型 H(x,y,t)=Z-Z0
  ↓
与 H_true 比较并评价误差
```

当前 WASS 端到端状态和 Case 0/Case 1 验证结果见：

- [`validation/case0_static_water.md`](validation/case0_static_water.md)
- [`validation/case1_constant_height.md`](validation/case1_constant_height.md)
- [`validation/case1_error_diagnosis.md`](validation/case1_error_diagnosis.md)
- [`validation/case1_support_trace.md`](validation/case1_support_trace.md)

## 5. 当前结论边界

可以陈述：上述三类模型均已建立、文档化，并已有对应代码/端到端验证工作支撑。

不能陈述：真实设备已经完成标定或采购、真实水面实验已经完成、系统已经达到 1 cm 实测精度。当前的厘米级结论仍处于理想合成数据和 WASS 软件链验证阶段。
