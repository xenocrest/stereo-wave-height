# 部署几何模型

## 输入与输出

本模型在水槽尺寸未确定时，用变量描述理论视场、视差和深度灵敏度，不固定基线或工作距离。

| 输入 | 含义 | 单位 | 当前状态 |
|---|---|---|---|
| `B` | 光心基线 | m | UNKNOWN/TODO |
| `Z` | 工作距离 | m | UNKNOWN/TODO，部署变量 |
| `f_mm` | 物理焦距 | mm | 8 mm candidate |
| `f_px` | 标定像素焦距 | px | UNKNOWN/TODO |
| `N_x,N_y` | 有效图像宽高 | px | 2448、2048 candidate |
| `p_x,p_y` | 像元间距 | mm/px | 0.00345 candidate |
| `sigma_d` | 视差标准不确定度 | px | UNKNOWN/TODO |

输出是部署筛选用的理论能力，不是实测性能。

## 视场变化

针孔、目标平面垂直光轴且忽略畸变时，传感器尺寸与距离 `Z` 处的视场为

$$
S_x=N_xp_x,\quad S_y=N_yp_y,
\qquad
W(Z)=Z\frac{S_x}{f_{mm}},\quad V(Z)=Z\frac{S_y}{f_{mm}}.
$$

`S_x,S_y,f_mm` 单位 mm；`W,V,Z` 使用同一长度单位（本项目用 m）。视场随 `Z` 线性增加。实际可测范围是左右有效视场交集，还受基线、姿态、校正 ROI 和遮挡限制。由于 `Z=null`，不输出固定视场。

## 深度能力

$$
d(Z)=\frac{f_{px}B}{Z},
\qquad
\sigma_{Z,d}=\frac{Z^2}{f_{px}B}\sigma_d.
$$

`d,f_px,sigma_d` 为 px，`B,Z,sigma_Z,d` 为 m。工作距离增加时视差按 `1/Z` 减小，视差引起的深度不确定度按 `Z²` 增大。增大基线可能减少公共视场或增加遮挡，不能仅按误差式选取。

依据：[OpenCV calib3d](https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html)、[WASS 论文](https://www.dsi.unive.it/wass/papers/1-s2.0-S0098300417304302-main.pdf)；误差式为对深度关系的一阶传播。

## 部署决策接口

输入标定 `f_px`、场地允许的 `Z` 区间和候选 `B`，检查视场、WASS 视差范围和三角化几何；再用实测 `sigma_d` 与完整误差预算判断 1 cm 条件。实测通过后才能把 `B`、`Z` 改为 `confirmed`。

水槽尺寸、目标覆盖范围、安装姿态、公共视场、最终镜头和 `sigma_d` 均为 `UNKNOWN/TODO`。
