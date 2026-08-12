# 相机几何模型

## 模型与依据

本文件定义单相机针孔投影和设备参数绑定。畸变在标定阶段估计并在使用针孔关系前校正；本文不实现算法。依据：[OpenCV calib3d](https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html)、[WASS 论文](https://www.dsi.unive.it/wass/papers/1-s2.0-S0098300417304302-main.pdf)。

三维点在相机坐标系中为 `P_c=(X,Y,Z)^T`，`X,Y,Z` 单位 m；像素坐标 `(u,v)` 单位 px：

$$
s\begin{bmatrix}u\\v\\1\end{bmatrix}=\mathbf K\begin{bmatrix}X\\Y\\Z\end{bmatrix},\quad s=Z,
\qquad
\mathbf K=\begin{bmatrix}f_x&0&c_x\\0&f_y&c_y\\0&0&1\end{bmatrix}.
$$

$$
u=f_x\frac{X}{Z}+c_x,\qquad v=f_y\frac{Y}{Z}+c_y.
$$

| 变量 | 含义 | 单位 |
|---|---|---|
| `X,Y,Z` | 相机坐标 | m |
| `u,v` | 像素坐标 | px |
| `fx,fy` | 水平、垂直像素焦距 | px |
| `cx,cy` | 主点坐标 | px |
| `K` | 内参矩阵 | 元素单位按本表 |
| `s` | 齐次比例因子；上述约定下为 `Z` | m |

世界点先按 `P_c=R P_w+t` 变换；`P_w,t` 单位 m，旋转矩阵 `R` 无量纲。

## 物理焦距与像素焦距

物理焦距 `f_mm`（mm）和像元间距 `p_x,p_y`（mm/px）满足

$$
f_x=\frac{f_{mm}}{p_x},\qquad f_y=\frac{f_{mm}}{p_y}.
$$

结果单位为 px，仅能作为名义初值；正式内参必须来自实际标定。

## 候选设备绑定

| 参数 | 当前值 | 单位 | 来源 | 状态 |
|---|---:|---|---|---|
| 相机 | MER2-503-36U3C | — | 厂商规格 | candidate |
| 分辨率 | 2448×2048 | px | 厂商规格 | candidate |
| `p_x,p_y` | 3.45 | µm/px | 厂商规格 | candidate |
| `f_mm` | 8.0 | mm | 项目候选规格；型号 UNKNOWN | candidate |
| `fx,fy,cx,cy` | UNKNOWN | px | 待标定 | UNKNOWN/TODO |

候选名义值为

$$
f_{x,nom}=f_{y,nom}=\frac{8.0\ \mathrm{mm}}{0.00345\ \mathrm{mm/px}}\approx2318.8\ \mathrm{px}.
$$

这不是标定结果，不得写入正式 WASS 内参。镜头真实焦距、畸变、对焦位置和两相机各自内参均为 `UNKNOWN/TODO`。配置见 [`candidate_system.yaml`](../../configs/equipment/candidate_system.yaml)，来源见 [参数登记表](../equipment_model/parameter_registry.md)。
