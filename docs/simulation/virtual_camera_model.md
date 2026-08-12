# 虚拟双目相机模型

## 1. 参数来源分层

虚拟相机必须读取或逐字段对应 [`candidate_system.yaml`](../../configs/equipment/candidate_system.yaml)。本轮采用：

| 参数 | 值 | 单位 | 来源 | 状态 |
|---|---:|---|---|---|
| 图像宽高 | 2448×2048 | px | MER2-503-36U3C 厂商规格 | candidate |
| 像元间距 | 3.45 | $\mu\mathrm{m/px}$ | 厂商规格 | candidate |
| 物理焦距 | 8.0 | mm | 项目镜头候选 | candidate |
| 名义 $f_x=f_y$ | 2318.8405797 | px | $8.0/0.00345$ | `SIMULATION_NOMINAL` |
| 基线 $B$ | UNKNOWN | m | 参数扫描 | deployment_variable |
| 工作距离 $Z$ | UNKNOWN | m | 参数扫描 | deployment_variable |

`SIMULATION_NOMINAL` 不等于 `CALIBRATED`。实际相机内参仍为 `UNKNOWN/TODO`。

## 2. 理想针孔内参假设

第一阶段使用

$$
\mathbf K_{sim}=\begin{bmatrix}
f_{nom}&0&c_x\\
0&f_{nom}&c_y\\
0&0&1
\end{bmatrix},
\qquad
f_{nom}=\frac{8.0\ \mathrm{mm}}{0.00345\ \mathrm{mm/px}}.
$$

采用零起始像素索引时，为构造对称理想相机，可假定

$$
c_x=\frac{2448-1}{2}=1223.5\ \mathrm{px},\qquad
c_y=\frac{2048-1}{2}=1023.5\ \mathrm{px}.
$$

主点取图像中心仅为 `simulation_assumption`，不是设备真实主点。若以后获得标定结果，应新增 calibrated 配置，不能覆盖名义真值的来源标签。

## 3. 虚拟双目外参

理想扫描阶段使用平行光轴、相同内参的两相机。以双目中点坐标系表示：

$$
\mathbf C_L=(-B/2,0,0)^{\mathsf T},\qquad
\mathbf C_R=(B/2,0,0)^{\mathsf T},
$$

其中相机中心 $C_L,C_R$ 和 $B$ 单位为 m，光轴均沿 $+Z$。$B$ 由每次扫描配置提供，默认 `null`；这一定义不决定最终实体基线。

三维点 $P_c=(X,Y,Z)^{\mathsf T}$ 的理想投影为

$$
u=f_xX/Z+c_x,\qquad v=f_yY/Z+c_y.
$$

左右对应点的视差满足 $d=f_{px}B/Z$。模型依据见 [相机几何](../mathematical_model/camera_geometry_model.md) 和 [双目重建](../mathematical_model/stereo_reconstruction_model.md)。

## 4. 畸变、噪声和曝光

真实畸变系数未知。第一阶段设置

$$
(k_1,k_2,p_1,p_2,k_3)=(0,0,0,0,0),
$$

全部无量纲，状态为 `ideal_simulation_assumption`，不代表 MER2-503-36U3C 与候选镜头的真实畸变为零。

第一阶段噪声、运动模糊和左右曝光差均关闭，以隔离几何链错误。后续 distorted/noisy 接口保留参数槽，但任何非零系数、噪声分布或曝光差必须具有来源；不得凭空伪造“真实相机噪声”。

## 5. 从水面到合成影像

每个相机像素通过 $K_{sim}$ 生成世界射线，求射线与解析水面 $Z_{true}(x,y,t)$ 的交点；按 [合成水面模型](synthetic_surface_models.md) 的统一表面纹理采样灰度，并进行可见性处理。输出为无损 8-bit 灰度 PNG；8 bit 是仿真—WASS 接口设计值，不是对真实 RAW 动态范围的声明。

### 几何单元测试输出

可输出投影点、解析对应、真值视差和真值深度，用于验证投影与公式自洽，报告名称必须包含 `geometry_unit`。

### WASS 端到端输入

只输出左右合成图像、名义内参/零畸变文件、时间/帧清单和 WASS 配置。truth 目录与 WASS input 目录物理分离；WASS 不得读取真值视差、点云或高度。

## 6. 公共视场和部署扫描

在同高、平行轴且目标为距离 $Z$ 的平面这一理想条件下，单目水平覆盖宽度

$$
W=Z\frac{N_xp_x}{f_{mm}},
$$

理想水平公共覆盖近似为

$$
W_{common}=\max(0,W-B).
$$

$W,W_{common},Z,B$ 单位 m，$N_x$ 为 px，$p_x$ 为 mm/px，$f_{mm}$ 为 mm。该式只用于第一阶段平行相机扫描；起伏水面、遮挡、畸变 ROI 和非平行姿态需通过投影可见性实际计算。

参数模板见 [`baseline_template.yaml`](../../configs/simulation/baseline_template.yaml)。
