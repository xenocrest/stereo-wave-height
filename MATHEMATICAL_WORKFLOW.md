# 从双目视频到逐像素波浪高度：完整数学链路

本文是 `stereo-wave-height` 的顶层数学入口，说明如何从左右双目视频逐步得到公共水面区域内每个像素的三维位置和相对静水高度。所有长度统一使用 m，图像坐标使用 px，时间使用 s。算法实现可以采用 WASS 或其他经过验证的双目后端，但几何关系、坐标约定、质量门和高度定义不能改变。

## 1. 最终问题与输出

左右相机记录视频

$$
V_L(t),\qquad V_R(t).
$$

对于用户选择的时刻 $t$，系统需要在右相机的公共水面区域 $\Omega$ 内，为每个像素 $p=(u,v)$ 输出

$$
\mathbf P(p,t)=[X(p,t),Y(p,t),Z(p,t)]^T
$$

和相对于独立静水参考面的有符号高度

$$
H(p,t).
$$

最终数据必须同时记录来源：直接双目观测 `DIRECT_STEREO`，或受真实观测约束的连续水面估计 `VARIATIONAL_ESTIMATE`。来源标签不同，但单位和高度定义相同。

## 2. 视频时间同步与同步帧提取

设左视频时刻为 $t_L$，右视频时钟与左视频之间采用显式仿射模型

$$
t_R=a t_L+b,
$$

其中 $a$ 为时钟速率比（无量纲），$b$ 为时间偏移（s）。目标时刻 $t$ 对应的帧对为

$$
I_L=V_L(t),\qquad I_R=V_R(at+b).
$$

实际解码使用视频 PTS，而不是假定左右帧号相同。左右曝光残差为

$$
\epsilon_t=t_R^{\mathrm{decoded}}-(at_L^{\mathrm{decoded}}+b).
$$

若水面法向速度为 $v_n$，同步误差导致的一阶高度误差约为

$$
|\Delta H_{sync}|\approx |v_n|\,|\epsilon_t|.
$$

因此同步质量必须进入误差预算；未来专业系统优先采用硬件触发或共同硬件时间戳。

## 3. 相机标定模型

三维世界点 $\mathbf P_w$ 到相机 $i$ 的坐标变换为

$$
\mathbf P_{c_i}=\mathbf R_i\mathbf P_w+\mathbf t_i.
$$

去畸变后的针孔投影为

$$
s_i
\begin{bmatrix}u_i\\v_i\\1\end{bmatrix}
=
\mathbf K_i
\begin{bmatrix}X_i\\Y_i\\Z_i\end{bmatrix},
\qquad
\mathbf K_i=
\begin{bmatrix}
f_{x_i}&0&c_{x_i}\\
0&f_{y_i}&c_{y_i}\\
0&0&1
\end{bmatrix}.
$$

OpenCV 双目标定外参采用

$$
\mathbf P_R=\mathbf R\mathbf P_L+\mathbf T,
$$

基线为

$$
B=\|\mathbf T\|.
$$

畸变参数 $\mathbf D_i$ 只通过已声明的相机模型进行校正，不得把未知畸变设为真实零值。标定必须通过留出视图、极线误差、参数稳定性和物理基线检查；仅有较小训练 RMS 不足以证明工作域有效。

## 4. 极线校正与公共有效视场

由 $\mathbf K_0,\mathbf D_0,\mathbf K_1,\mathbf D_1,\mathbf R,\mathbf T$ 计算校正旋转与投影矩阵

$$
(\mathbf R_0',\mathbf R_1',\mathbf P_0',\mathbf P_1',\mathbf Q)
=\operatorname{stereoRectify}(\cdots).
$$

校正映射将原图变为 $I_L',I_R'$。理想对应点满足

$$
v_L'\approx v_R'.
$$

左右校正图中均有合法原图来源的像素掩膜分别为 $M_L,M_R$，双目公共有效域为

$$
M_{common}=M_L\cap M_R.
$$

用户水面 ROI 必须位于 $M_{common}$ 内。裁剪只改变计算/显示范围，不能改变内外参或图像几何。

## 5. 稠密对应与视差

同一水面点在校正图中的水平视差定义为

$$
d(u,v)=u_L'-u_R'.
$$

项目允许两条观测后端：

1. WASS：负责其官方匹配、筛选和三维重建；
2. 标定驱动的备用稠密双目后端：使用 OpenCV `StereoSGBM` 计算左右视差。

备用后端必须计算双向视差并执行左右一致性：

$$
\left|d_L(u,v)+d_R(u-d_L(u,v),v)\right|\leq\tau_{LR}.
$$

此外，视差必须有限且位于预先声明的搜索区间。不能为了全覆盖而把不一致视差当作真实观测。

## 6. 从视差到米制三维点

在理想平行双目中，校正焦距 $f$（px）、基线 $B$（m）、视差 $d$（px）和轴向深度 $Z$（m）满足

$$
Z=\frac{fB}{d}.
$$

相机坐标为

$$
X=\frac{(u-c_x)Z}{f_x},\qquad
Y=\frac{(v-c_y)Z}{f_y}.
$$

一般校正模型使用齐次重投影矩阵 $\mathbf Q$：

$$
\begin{bmatrix}X_h\\Y_h\\Z_h\\W_h\end{bmatrix}
=
\mathbf Q
\begin{bmatrix}u\\v\\d\\1\end{bmatrix},
\qquad
\mathbf P=\frac{1}{W_h}[X_h,Y_h,Z_h]^T.
$$

只要 $\mathbf T$ 使用 m，所得 XYZ 即为 m。WASS 原始结果必须经过其官方尺度恢复并记录坐标变换；不能根据“看起来合理”猜单位或轴方向。

## 7. pixel–XYZ 对应

每个通过质量门的直接观测保存

$$
(u,v)\longleftrightarrow(X,Y,Z).
$$

该对应必须说明像素属于原始图、canonical 图还是校正图。若需要在原图像素查询三维点，必须通过已保存的去畸变/校正映射转换，不能把不同像素坐标系直接混用。

## 8. 静水参考面与高度定义

若静水面采用一般平面

$$
\Pi_0:\quad A X+B Y+C Z+D=0,
$$

其单位法向量为

$$
\hat{\mathbf n}=\frac{[A,B,C]^T}{\sqrt{A^2+B^2+C^2}}.
$$

三维点 $\mathbf P$ 相对于静水参考面的有符号正交高度为

$$
H(\mathbf P)=\frac{A X+B Y+C Z+D}{\sqrt{A^2+B^2+C^2}}.
$$

正方向由项目世界坐标的竖直向上方向确定。不能直接把 camera $Z$ 当作水面高度。

若静水参考不是平面而是同一规则网格上的空间参考场，则

$$
H(x,y,t)=Z(x,y,t)-Z_0(x,y).
$$

两种表达本质一致：前者使用参考平面的法向坐标，后者使用已对齐世界坐标中的竖直高程差。参考帧与测量帧必须共享标定、尺度、坐标系和刚体变换。

## 9. 从稀疏可靠观测到ROI每个像素高度

直接双目可能在反射、遮挡或低对比区域留下缺口。项目目标仍是对水面 ROI 每个像素输出高度，因此在直接观测之外求解一个由观测锚定的连续水面。

首先将每个图像像素的标定射线与静水参考面相交，得到该像素在参考面上的物理坐标 $(x_p,y_p)$（m）。相邻关系按物理距离而非像素距离构造。设直接观测高度为 $h_{obs}$，权重为 $W$，物理邻接梯度算子为 $B_g$，则求解

$$
h^*=\underset{h}{\operatorname{argmin}}\;
\left\|W^{1/2}(h-h_{obs})\right\|_2^2
+\lambda\left\|B_g h\right\|_2^2
+\mu\left\|B_g^T B_g h\right\|_2^2.
$$

三项依次表示：服从真实双目高度、限制不合理的一阶起伏、限制不合理的曲率。实现先从观测拟合低阶物理基面，再只对残差场正则化，以避免把合法整体坡度错误压成常数。

每个 ROI 连通分量必须含直接双目锚点；否则方程虽可能有数值解，却没有测量依据，必须失败。求解后直接观测值原样恢复，不能被平滑项修改。这样每个像素都有高度，同时仍能区分直接测量与模型估计。

## 10. 波浪时间序列

对多个同步时刻重复上述单帧流程，得到

$$
H(x,y,t_k),\qquad k=0,1,\ldots,N-1.
$$

给定物理测量区域 $\Omega_m$，空间平均高度为

$$
\bar H(t)=\frac{1}{|\Omega_m|}\int_{\Omega_m}H(x,y,t)\,\mathrm dA.
$$

离散实现必须使用有效物理面积权重。常用统计包括

$$
H_{rms}=\sqrt{\frac1N\sum_{k=0}^{N-1}(\bar H(t_k)-\overline H)^2},
$$

以及峰峰值

$$
H_{pp}=\max_k\bar H(t_k)-\min_k\bar H(t_k).
$$

低频漂移分析结果必须与原始高度并列保存，不能覆盖原始测量。

## 11. 深度和高度误差传播

由 $Z=fB/d$，一阶微分为

$$
\frac{\partial Z}{\partial f}=\frac{Z}{f},\qquad
\frac{\partial Z}{\partial B}=\frac{Z}{B},\qquad
\frac{\partial Z}{\partial d}=-\frac{Z}{d}.
$$

独立小误差近似下

$$
\sigma_Z^2\approx
\left(\frac{Z}{f}\sigma_f\right)^2+
\left(\frac{Z}{B}\sigma_B\right)^2+
\left(\frac{Z}{d}\sigma_d\right)^2+
\sigma_{cal}^2+
\sigma_{sync}^2.
$$

参考相减后的高度不确定度为

$$
\sigma_H^2=\sigma_Z^2+\sigma_{Z_0}^2-2\operatorname{Cov}(Z,Z_0).
$$

因此增加视差搜索范围不能自动提高精度；标定、同步和对应误差必须共同受控。

## 12. 质量门、物理合理性与独立验证

逐像素高度输出至少必须通过：

- 标定留出极线误差和参数稳定性；
- 左右同步误差；
- 视差范围与左右一致性；
- 三维点有限性、尺度和坐标方向；
- 水面观测锚点覆盖与连通性；
- 变分求解的数据残差；
- 静水零场、已知高度和平面稳定性；
- 独立标尺或其他物理参考的误差评价。

独立标尺只用于最终比较

$$
e_H=H_{reconstructed}-H_{reference},
$$

以及 RMSE、MAE、最大绝对误差和偏差；它不进入标定、匹配、三角化、参考面或高度求解。

## 13. 当前实现边界

截至 2026-09-03，项目已实现 WASS 主后端、标定驱动的 OpenCV 稠密双目备用后端，以及与后端无关的观测锚定全像素高度求解器。解析真值测试已通过，但 HomeTank_005 当前标定为 `CALIBRATION_OPERATIONAL_DOMAIN_FAIL`，备用后端在冻结帧上也只得到 0.1300% 的严格左右一致观测，不能据此声称真实高度正确。

因此当前工程重点是提高可观测性与标定工作域质量，并在相同真值/物理参考下比较 WASS 与备用后端。最终目标不变：在通过质量门的双目公共水面 ROI 中，为每个像素输出有物理单位、明确参考、可追溯来源和可验证误差的高度。

## 14. 详细文档索引

- [相机几何模型](docs/mathematical_model/camera_geometry_model.md)
- [双目重建模型](docs/mathematical_model/stereo_reconstruction_model.md)
- [高度场模型](docs/mathematical_model/height_field_model.md)
- [误差传播模型](docs/mathematical_model/error_propagation_model.md)
- [统一坐标系](docs/data_model/coordinate_system.md)
- [双后端与全像素求解](docs/reconstruction/dual_stereo_backend_model.md)
- [WASS集成架构](docs/wass/wass_integration_architecture.md)

