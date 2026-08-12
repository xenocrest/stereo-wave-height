# 项目统一坐标与时间体系

## 1. 适用范围

本规范统一仿真、未来工业相机数据、WASS 重建输出和高度产品中的坐标、方向、单位与时间语义。任何文件若未声明坐标系标识、单位或时间基准，均不得进入正式处理链。

数学依据见 [相机几何模型](../mathematical_model/camera_geometry_model.md)、[双目重建模型](../mathematical_model/stereo_reconstruction_model.md) 和 [高度场模型](../mathematical_model/height_field_model.md)。

## 2. 图像坐标系

左右图分别使用 `I_L` 和 `I_R`：

- 坐标：`(u_L,v_L)`、`(u_R,v_R)`；
- 单位：pixel（记为 px）；
- 原点：零起始数组中左上角像素的中心，即 `(0,0)`；
- `+u`：图像向右；
- `+v`：图像向下；
- 像素索引必须为整数；亚像素匹配坐标可以为浮点数。

左右图必须分别保留自己的相机标识和内参，不得把同一个 `(u,v)` 当作同一条视线。经极线校正后，项目约定视差候选定义为 `d=u_L-u_R`（px），但正式符号仍须由 WASS 左右顺序和校正输出验证并写入元数据。

## 3. 相机坐标系

每台相机分别具有 `C_L`、`C_R` 坐标系，采用与 OpenCV 针孔模型一致的项目约定：

- 原点：相机光心；
- `+Z_c`：沿光轴指向相机前方；
- `+X_c`：从相机观察方向看向图像右侧；
- `+Y_c`：从相机观察方向看向图像下方；
- 坐标：`P_c=(X_c,Y_c,Z_c)^T`；
- 单位：m。

相机坐标系方向是数学接口约定，不等同于相机外壳机械轴；二者关系在缺少厂商机械图和实测时为 `UNKNOWN/TODO`。

## 4. 世界/水面坐标系

世界坐标系记为 `W`，点为 `P_w=(X_w,Y_w,Z_w)^T`，单位 m：

- `+Z_w`：竖直向上；
- `X_w,Y_w`：位于静水参考面的水平切平面内；
- `X_w × Y_w = Z_w`，构成右手系；
- `+X_w` 的现场方向、原点和控制点由每次部署元数据定义，当前为 `UNKNOWN/TODO`；
- `+Y_w` 由右手规则确定。

静水面是高度参考，但不强制把所有 `Z0(x,y)` 设为零。实际静水平均面可含空间变化：

$
H(x,y,t)=Z(x,y,t)-Z_0(x,y).
$

`Z`、`Z0`、`H` 单位均为 m。只有在经过记录的坐标变换后，才能把 WASS 重建坐标解释为世界高程。

## 5. 规则网格坐标

高度产品使用网格坐标 `(x_i,y_j)`：

- `x_i` 对应世界 `X_w`，单位 m；
- `y_j` 对应世界 `Y_w`，单位 m；
- 数组维序固定为 `[time_index, y_index, x_index]`；
- `Z[t,j,i]` 表示 `Z(x_i,y_j,t)`；
- `Z0[j,i]` 和 `H[t,j,i]` 必须使用同一 `x,y` 数组和坐标参考。

网格原点、范围、间距和尺寸当前均为 `UNKNOWN/TODO`，不得用数组索引代替物理坐标。

## 6. 坐标转换

世界到相机的外参定义为

$
\mathbf P_c=\mathbf R_{cw}\mathbf P_w+\mathbf T_{cw},
$

其中 `P_c,P_w,T_cw` 单位为 m，旋转矩阵 `R_cw` 无量纲。逆变换为

$
\mathbf P_w=\mathbf R_{cw}^{\mathsf T}(\mathbf P_c-\mathbf T_{cw}).
$

针孔投影为

$
s\begin{bmatrix}u\\v\\1\end{bmatrix}
=\mathbf K\begin{bmatrix}X_c\\Y_c\\Z_c\end{bmatrix},
\qquad
\mathbf K=\begin{bmatrix}f_x&0&c_x\\0&f_y&c_y\\0&0&1\end{bmatrix}.
$

`u,v,fx,fy,cx,cy` 单位为 px，`Xc,Yc,Zc,s` 单位为 m。每个变换必须记录源坐标系、目标坐标系、矩阵方向、长度单位、来源和状态；未知 `R,T` 使用 `null/UNKNOWN`，不得填单位阵或零向量冒充标定结果。

## 7. 时间体系

每帧必须包含：

- `frame_id`：帧对唯一标识，不含物理时间单位；
- `timestamp_ns`：整数纳秒计数，单位 ns；
- `time_reference`：例如 `simulation_epoch`、`device_clock`、`trigger_clock` 或 `UTC`；
- `timestamp_origin`：计数原点；若未知则为 `UNKNOWN`；
- `sync_offset_ns`：左右有效曝光时刻差，单位 ns；未测时为 `null/UNKNOWN`。

高度场时间 `t` 由 `timestamp_ns` 相对选定原点换算为 s。不得混用设备时钟、主机接收时钟和仿真时间。

## 8. 强制元数据

所有空间数据必须声明 `coordinate_system_id`、`axis_convention`、`length_unit`、`transform_id`；所有时间序列必须声明 `time_reference`、`timestamp_unit` 和帧配对规则。缺失任一字段时数据状态为 `invalid_metadata`。
