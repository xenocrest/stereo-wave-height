# 深度与高度误差传播模型

## 目的与依据

本模型把设备、标定和匹配不确定度传递到深度 `Z`，供后续判断 1 cm 目标，不代表已经达标。依据为 `Z=f_pxB/d` 和 [JCGM 100:2008（GUM）](https://www.bipm.org/documents/20126/2071204/JCGM_100_2008_E.pdf) 的一阶不确定度传播；几何背景见 [WASS 论文](https://www.dsi.unive.it/wass/papers/1-s2.0-S0098300417304302-main.pdf)。

## 深度灵敏度

$$
Z(f_{px},B,d)=\frac{f_{px}B}{d},
$$

其中 `Z,B` 为 m，`f_px,d` 为 px。偏导为

$$
\frac{\partial Z}{\partial f_{px}}=\frac{B}{d}=\frac{Z}{f_{px}},\quad
\frac{\partial Z}{\partial B}=\frac{f_{px}}{d}=\frac{Z}{B},\quad
\frac{\partial Z}{\partial d}=-\frac{f_{px}B}{d^2}=-\frac{Z}{d}.
$$

偏导单位依次为 m/px、无量纲和 m/px。

若输入为小量、零均值且相互独立：

$$
\sigma_Z^2\approx
\left(\frac{B}{d}\right)^2\sigma_f^2+
\left(\frac{f_{px}}{d}\right)^2\sigma_B^2+
\left(\frac{f_{px}B}{d^2}\right)^2\sigma_d^2+
\sigma_{cal}^2.
$$

| 变量 | 含义 | 单位 |
|---|---|---|
| `sigma_Z` | 深度标准不确定度 | m |
| `sigma_f` | 像素焦距标准不确定度 | px |
| `sigma_B` | 基线标准不确定度 | m |
| `sigma_d` | 视差标准不确定度 | px |
| `sigma_cal` | 其余内外参的等效深度不确定度 | m |

相对形式为

$$
\left(\frac{\sigma_Z}{Z}\right)^2\approx
\left(\frac{\sigma_f}{f_{px}}\right)^2+
\left(\frac{\sigma_B}{B}\right)^2+
\left(\frac{\sigma_d}{d}\right)^2+
\left(\frac{\sigma_{cal}}{Z}\right)^2.
$$

输入相关时必须使用 `sigma_Z²≈J Sigma J^T`；`J` 是上述偏导行向量，`Sigma` 为输入协方差矩阵，元素单位为对应变量单位的乘积，不能直接使用独立 RSS。

焦距项包含内参估计和成像尺度变化；基线项包含尺度恢复和支架漂移；视差项受纹理、反射、遮挡和校正残差影响；其余标定项须通过重复标定、留出检查点和刚体重建实测，不得无依据赋值。

## 高度误差

由 `H=Z-Z0`：

$$
\sigma_H^2=\sigma_Z^2+\sigma_{Z0}^2-2\operatorname{Cov}(Z,Z_0).
$$

`sigma_H,sigma_Z,sigma_Z0` 为 m，协方差为 m²。只有动态与静水随机误差独立时协方差才为零；共用标定和尺度误差需保留或端到端验证。

判断 1 cm 需要标定 `f_px,sigma_f`、实测 `B,sigma_B`、部署 `Z`、水面条件下 `sigma_d`、`sigma_cal`、`sigma_Z0` 以及同步和网格误差。当前这些不确定度及 `B,Z` 均为 `UNKNOWN/TODO`，不能得出已达标结论。项目预算见 [one_cm_error_budget.md](../wass/one_cm_error_budget.md)。
