# WASS 输出后的高度解算管线

## 1. 范围

本管线从已经由 WASS 产生的三维结果开始，不包含 stereo matching、三角测量或点云重建。数学定义继承 [统一坐标体系](../data_model/coordinate_system.md)、[高度场模型](height_field_model.md) 和 [误差传播模型](error_propagation_model.md)。

输入目标为 WASS 点云或网格，最终输出为

\[
H(x,y,t)=Z(x,y,t)-Z_0(x,y).
\]

`x,y` 为世界水平坐标（m），`t` 为相对时间（s），`Z,Z0,H` 单位均为 m。

## 2. 管线阶段

```text
Raw WASS Reconstruction
  → Parse with versioned adapter
  → Validate scale and source coordinates
  → Transform to world coordinates
  → Map to common grid Z(x,y,t)
  → Align frame time
  → Build/load static reference Z0(x,y)
  → Apply joint validity mask
  → H(x,y,t)=Z-Z0
  → Validation metrics and provenance
```

### 2.1 输出解析

按照 [WASS 输出规范](../data_model/wass_output_spec.md) 读取已确认格式。解析阶段不得插值缺失点、猜测长度单位或改变坐标方向。原始文件、哈希、WASS 版本和配置必须保留。

### 2.2 坐标与尺度转换

WASS 源坐标点 `P_r` 到世界点 `P_w` 使用已登记变换：

\[
\mathbf P_w=s\mathbf R_{wr}\mathbf P_r+\mathbf T_{wr}.
\]

`P_w,T_wr` 单位为 m；`P_r` 的单位由源格式声明；若 `P_r` 为归一化坐标，则尺度 `s` 具有 m/源单位；旋转矩阵 `R_wr` 无量纲。`s,R,T` 任一为 `UNKNOWN` 时停止物理高度输出。

变换后必须确认 `+Zw` 向上。不能通过查看波形后选择符号；方向由控制点、静水法向和外参元数据预先确定。

### 2.3 网格映射

点云映射到项目共同网格：

\[
Z_{tji}=Z(x_i,y_j,t).
\]

`x_i,y_j,Z` 单位为 m，数组维序为 `[time,y,x]`。网格范围、间距、插值/聚合方法及过滤阈值当前为 `UNKNOWN/TODO`，必须作为带版本配置选择，不能在本文件固定。

若直接采用经验证的 `wassgridsurface` 网格，仍需检查源维序、单位、mask 和坐标变换。若项目以后实现纯格式性的网格映射，它不得重建 WASS 未提供的双目几何信息。

### 2.4 时间同步

每个 `Z` 帧由 `frame_id` 关联 `timestamp_ns` 和 `time_reference`。高度时间为

\[
t_q=(timestamp\_ns_q-timestamp\_ns_0)\times10^{-9}\ \mathrm{s}.
\]

`timestamp_ns` 单位为 ns，`t_q` 为 s。左右同步在进入 WASS 前验收；后处理不得用插值时间掩盖无效帧对。静水 `Z0` 不携带动态时间轴，但必须保存其采集时间范围和标定/部署状态。

### 2.5 静水参考

静水参考定义为未来独立静水实验在共同网格上的结果：

\[
Z_0(x_i,y_j).
\]

其具体来源、采集时长、样本选择、平均/稳健估计或平面约束方法当前均为 `UNKNOWN/TODO`。本项目只规定 reference 接口必须提供：

- `Z0[Ny,Nx]`（m）；
- `Z0_mask[Ny,Nx]`（boolean）；
- 坐标/网格 ID；
- 样本数和不确定度；
- calibration、deployment 和生成配置引用；
- 来源时间范围与 provenance。

不允许默认 `Z0=0`，也不允许使用动态序列逐帧均值替代独立静水实验，除非未来方案明确论证并预注册。

### 2.6 高度计算

联合有效掩膜为

\[
M_H(t,j,i)=M_Z(t,j,i)\land M_{Z0}(j,i).
\]

当 `M_H=true` 时：

\[
H(t,j,i)=Z(t,j,i)-Z_0(j,i).
\]

当 `M_H=false` 时，`H=NaN`。不得使用零填充、最近邻填洞或静水值冒充有效高度。若 `+Zw` 向上，`H>0` 表示高于静水平均面。

## 3. 后处理模拟测试

本测试**不模拟 WASS 算法**，只构造符合标准 WASS 适配输出接口的受控输入。

### 测试输入

- 已知源坐标点/网格 `Z_source(x,y,t)`；
- 已知坐标变换和尺度；
- 已知 mask 与 `timestamp_ns`；
- 已知静水参考 `Z0_true(x,y)`；
- 已知高度 `H_true(x,y,t)`，且 `Z_true=Z0_true+H_true`。

### 被测阶段

```text
standardized simulated WASS output
  → coordinate transform
  → grid mapping interface
  → time association
  → static reference interface
  → height calculation
  → metrics
```

不生成双目图像、不提供真值视差、不调用自研匹配或三角化。测试报告名称必须包含 `post_wass_pipeline`，并明确其评价对象不是 WASS 重建精度。

### 必测情形

1. 恒定 `Z0` 与 `H=0`，验证零高度和 mask；
2. 空间变化 `Z0(x,y)` 与已知正/负常量高度，验证静水相减和符号；
3. 已知刚体变换，验证坐标方向和尺度；
4. 已知时间序列，验证 frame/timestamp 排序；
5. 含 NaN/空洞输入，验证无效值传播；
6. 一维/二维解析 `H_true`，验证网格和指标计算。

## 4. 验收指标

误差只在 truth 与计算结果的共同有效样本集合 `V` 上计算：

\[
e_i=H_{calc,i}-H_{true,i},
\]

\[
RMSE=\sqrt{\frac{1}{|V|}\sum_{i\in V}e_i^2},\qquad
MAE=\frac{1}{|V|}\sum_{i\in V}|e_i|,
\]

\[
E_{max}=\max_{i\in V}|e_i|,
\qquad
coverage=\frac{N_{valid}}{N_{eligible}},
\qquad
hole\_rate=1-coverage.
\]

`e`、RMSE、MAE、`Emax` 单位为 m；coverage 和 hole rate 无量纲。指标继承 [仿真验收标准](../simulation/acceptance_criteria.md) 的定义，但本测试的评价对象仅为 WASS 输出后的坐标、参考、高度和指标链。

必须另外通过布尔检查：坐标轴方向正确、高度正负正确、时间顺序正确、NaN/mask 一致、provenance 完整。任何布尔检查失败即不通过。

## 5. 验收声明限制

后处理测试通过只能说明：给定符合接口的三维输入时，项目坐标统一、静水参考接口、高度相减和指标计算满足数值要求。它不能说明 WASS 匹配/重建通过，不能说明真实设备达到 1 cm，也不能替代 [无设备 WASS 端到端仿真计划](../simulation/simulation_validation_plan.md)。

## 6. 当前 UNKNOWN/TODO

- 静水实验采集方案和 `Z0` 估计方法；
- WASS 原始输出单位/坐标的首轮运行核验；
- 网格映射方法和参数；
- 实体数据同步阈值；
- 真实实验参考仪器和后处理验收阈值。
