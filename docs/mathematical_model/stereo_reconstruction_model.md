# 双目重建模型

## 理论边界与依据

本文件描述已标定、去畸变并完成极线校正的理想平行双目关系。一般姿态由投影矩阵三角化；WASS 负责实际匹配、自动标定、校正和重建，本项目不实现替代算法。依据：[OpenCV calib3d](https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html)、[WASS 论文](https://www.dsi.unive.it/wass/papers/1-s2.0-S0098300417304302-main.pdf)、[WASS `v_1.5`](https://github.com/fbergama/wass/tree/v_1.5)。

左右对应点为 $(u_L,v_L)$、$(u_R,v_R)$（px），视差为

$$
d=u_L-u_R,
$$

实际符号须由左右顺序和 WASS 校正输出确认。理想平行双目深度为

$$
Z=\frac{f_{px}B}{d}.
$$

| 变量 | 含义 | 单位 |
|---|---|---|
| $Z$ | 轴向深度 | m |
| $f_{px}$ | 校正投影矩阵中的像素焦距 | px |
| $B$ | 光心基线 | m |
| $d$ | 水平视差 | px |

单位关系为 $\mathrm{px}\times\mathrm{m}/\mathrm{px}=\mathrm{m}$。左校正相机坐标为

$$
X=\frac{(u_L-c_x)Z}{f_x},\qquad Y=\frac{(v_L-c_y)Z}{f_y},
$$

其中 $X,Y,Z$ 为 m，其余变量为 px。该关系是 WASS 重建的基础理论之一，不是对其实现细节或精度的完整描述。

## 当前参数绑定

| 参数 | 当前值 | 单位 | 状态 |
|---|---:|---|---|
| `f_px` | 正式值 UNKNOWN；候选名义值约 2318.8 | px | UNKNOWN/TODO |
| `B` | UNKNOWN | m | 待设计与实测 |
| `Z` | UNKNOWN | m | 部署变量 |
| `d` | UNKNOWN | px | 由几何和重建确定 |

当前不能给出固定深度范围或精度。使用条件包括同步曝光、正确标定、已校正图像、有效非零视差和可追溯尺度。误差见 [error_propagation_model.md](error_propagation_model.md)。
