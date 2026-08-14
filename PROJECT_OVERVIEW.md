# stereo-wave-height 项目宏观汇报与持续更新入口

> 文档定位：本页面向项目汇报、阶段复盘和新成员快速理解，集中说明“为什么做、怎样做、已经做到什么、还不能证明什么、下一步做什么”。详细推导、配置和逐帧证据仍以链接的专项文档为准。后续每完成一个关键模型、验证、硬件或实测节点，都应更新本页末尾记录。

## 1. 项目目标

本项目希望建立一套可追溯的双目水面三维重建与高度场解算流程。系统以同步双目图像为输入，调用外部双目重建引擎 WASS 得到水面三维高程，再用独立静水参考计算相对水面高度：

$$
H(x,y,t)=Z(x,y,t)-Z_0(x,y).
$$

其中，`Z(x,y,t)` 是动态水面高程，`Z0(x,y)` 是同一坐标、尺度和网格上的独立静水参考，`H(x,y,t)` 是项目最终关心的相对静水面高度场，长度单位统一为 m。

近期目标是在实验室人工波条件下验证约 1 cm 级高度解算；长期目标是在重新设计部署几何、误差预算并完成现场独立验证后扩展到真实海面。这里的“1 cm 级”目前是验收目标和理想仿真软件链结论，**不是实物系统已经达到的精度声明**。

总体工作路线为：

```text
统一数学、坐标和数据规范
  -> 锁定并复现外部 WASS 处理链
  -> 建立候选设备约束下的理想虚拟双目仿真
  -> 用已知真值逐级关闭 Case 0/1/2
  -> 关闭相位、坐标与时间对齐诊断
  -> 扫描 baseline x scene distance 等部署参数空间
  -> 采购并标定真实设备，验证同步与静水 Z0
  -> 水槽静水和人工波实验，与独立参考比较
  -> 按真实海面尺度重建误差预算并开展现场验证
```

阶段计划详见 [项目计划](docs/PROJECT_PLAN.md)，核心模型的快速导航见 [建模成果总览](docs/MODEL_OVERVIEW.md)。

## 2. 为什么采用双目、WASS 和静水参考

### 2.1 双目测量

同一水面点在左右相机中的像素位置不同。理想平行双目下，视差 `d`、像素焦距 `f_px`、基线 `B` 和深度 `Z` 满足：

$$
Z=\frac{f_{px}B}{d}.
$$

因此，同步双目图像可以在不接触水面的情况下恢复具有物理尺度的三维表面。基线越大通常越有利于深度敏感度，但也会减小公共视场、增加遮挡和匹配难度；工作距离越大，同一视差误差引起的深度误差通常越大。这正是后续必须联合扫描 baseline 与 scene distance，而不能只挑一个参数的原因。

### 2.2 WASS 的角色与边界

WASS（Waves Acquisition Stereo System）是本项目调用的**外部双目匹配、自动标定和三角重建引擎**。标准链包括 `prepare -> match -> autocalibrate -> stereo`，规则网格由官方配套工具 `wassgridsurface` 生成。

本项目没有开发 WASS 的核心算法，也不声称是在证明“WASS 本身正确”。本项目验证的是：在明确的候选几何和已知真值仿真条件下，WASS 的真实输出经过本项目的尺度恢复、坐标适配、规则网格、静水参考和误差评价后，能否形成自洽、可复现的水面高度产品。现有验证没有修改 WASS 或 `wassgridsurface` 源码。

### 2.3 为什么使用 `H=Z-Z0`

绝对三维高程包含相机姿态、坐标原点、安装高度和静态水面形状。项目真正关心的是相对于静水面的波动。使用独立静水序列形成 `Z0(x,y)`，再从动态 `Z(x,y,t)` 中相减，可以消去共同的静态几何分量，同时保留波面变化。

该相减只有在 `Z` 与 `Z0` 共用坐标系、尺度、轴方向、规则网格和兼容有效域时才有意义。动态帧不能参与自身的 `Z0`，否则会把被测波动泄漏到参考中。详细定义见 [高度场模型](docs/mathematical_model/height_field_model.md) 和 [高度重建流程](docs/mathematical_model/height_reconstruction_pipeline.md)。

## 3. 候选设备与当前仿真参数边界

当前设备登记并非采购确认：

| 项目 | 当前值 | 状态与含义 |
|---|---:|---|
| 候选相机 | MER2-503-36U3C | `candidate`，尚未采购/实物核验 |
| 分辨率 | 2448 x 2048 px | 候选设备规格 |
| 像元尺寸 | 3.45 um/px | 候选设备规格 |
| 快门 | global | 候选设备规格 |
| 输出位深 | 8、10 bit | 候选设备规格；当前合成输入为 mono8 PNG |
| 候选镜头焦距 | 8.0 mm | `candidate`，厂商和准确型号仍为 UNKNOWN |
| 名义像素焦距 | 2318.8405797 px | `SIMULATION_NOMINAL`，由 8 mm / 0.00345 mm 推导，不是标定值 |
| 主点 | (1223.5, 1023.5) px | 图像中心的理想仿真假设 |
| 畸变 | 全零 | 理想针孔假设，不代表真实镜头 |
| 当前验证基线 | 0.20 m | `SIMULATION_TEST_PARAMETER`，不是最终硬件选择 |
| 当前验证工作距离 | 2.00 m | `SIMULATION_TEST_PARAMETER`，不是最终部署值 |

真实 `fx/fy/cx/cy`、镜头畸变、最终基线、工作距离、水槽尺寸、同步误差和目标水面条件下的视差不确定度仍为 UNKNOWN/TODO。权威状态表见 [设备与部署参数登记表](docs/equipment_model/parameter_registry.md) 及机器可读配置 [candidate_system.yaml](configs/equipment/candidate_system.yaml)。

**重要边界：**当前仿真图像只在理想针孔几何、分辨率、像元尺寸和名义焦距上与候选设备模型一致；它们不等同于真实相机照片。当前没有模拟真实畸变、传感器噪声、标定误差、同步误差、相机抖动、水面反射/折射、环境光变化或真实纹理失效。

在真实运行中，距离 $Z$ 是由同步双目图像的视差和标定几何重建得到的结果。表中的 working distance 只用于仿真场景定义、设备选型与性能分析，不是运行时要求用户预先输入的“海浪距离”。

## 4. 已建立的模型、接口与坐标体系

项目已把核心概念拆成可单独审查、又能在端到端链中衔接的模型。

| 模型/规范 | 解决的问题 | 详细文档 |
|---|---|---|
| 双目几何模型 | 视差、焦距、基线与深度的关系；尺度和单位 | [stereo_reconstruction_model.md](docs/mathematical_model/stereo_reconstruction_model.md) |
| 相机几何模型 | 内参、外参、投影、畸变和坐标变换 | [camera_geometry_model.md](docs/mathematical_model/camera_geometry_model.md) |
| 水面/高度模型 | `Z`、独立 `Z0` 与最终 `H=Z-Z0` | [water_surface_model.md](docs/mathematical_model/water_surface_model.md)、[height_field_model.md](docs/mathematical_model/height_field_model.md) |
| 部署几何模型 | 基线、工作距离、视场、重叠与观测角的联合约束 | [deployment_geometry_model.md](docs/mathematical_model/deployment_geometry_model.md) |
| 误差传播模型 | 视差、焦距、基线、标定、同步和静水参考误差如何进入高度结果 | [error_propagation_model.md](docs/mathematical_model/error_propagation_model.md)、[error_analysis.md](docs/mathematical_model/error_analysis.md) |
| 虚拟相机模型 | 候选参数约束下的理想针孔双目投影和合成观测 | [virtual_camera_model.md](docs/simulation/virtual_camera_model.md) |
| 合成水面模型 | Case 0--3 的解析真值定义 | [synthetic_surface_models.md](docs/simulation/synthetic_surface_models.md) |
| 坐标系统 | 相机、WASS、平面对齐世界坐标、轴方向和尺度转换 | [coordinate_system.md](docs/data_model/coordinate_system.md) |
| 双目输入接口 | 帧配对、时间戳、图像与元数据约束 | [stereo_image_dataset_spec.md](docs/data_model/stereo_image_dataset_spec.md) |
| WASS/重建输出接口 | 原始输出保留、标准点、规则网格、单位、mask 和 provenance | [wass_output_spec.md](docs/data_model/wass_output_spec.md)、[reconstruction_output_spec.md](docs/data_model/reconstruction_output_spec.md) |
| 有效测量域 | raw/grid/eligible 三层支持定义，避免 DCT 填充值冒充真实观测 | [measurement_valid_domain.md](docs/data_model/measurement_valid_domain.md) |

规则网格约定为 `[time,y,x]`，`x/y/Z/Z0/H` 使用 m，时间戳与帧号需保留。WASS 原始坐标先通过有记录的刚体变换和显式基线尺度映射到统一坐标，不能只通过翻图或“看起来正确”决定轴方向。

## 5. 设备购买前的仿真验证方法

虚拟相机本身已先通过几何可信性验证：候选参数到内参的映射、独立理论投影、
多深度视差以及点集、平面和正弦面的三角化闭环均达到机器精度门限；shared
physical texture 调用链也已确认。这是后续多场景仿真的前提证据，但不代表真实
光学等价。详见 [虚拟双目几何验证](docs/validation/virtual_stereo_geometry_validation.md)。

仿真的核心价值是拥有严格已知的 `H_true`，并且不把真值泄漏给 WASS：

```text
已知 H_true(x,y,t) 和 Z0,true(x,y)
  -> 得到 Z_true=Z0,true+H_true
  -> 虚拟左右针孔相机分别成像
  -> 生成 WASS 可接受的双目 PNG、标定与配置
  -> WASS prepare/match/autocalibrate/stereo
  -> 真实三角化输出 xyzC
  -> wassgridsurface 生成统一规则网格 Z_calc
  -> 仅由独立静水重建帧计算 Z0,calc
  -> H_calc=Z_calc-Z0,calc
  -> 在预先定义的共同有效域与 H_true 比较
```

真值视差、真值点云和真值高度不会进入 WASS 的 input/config/workdir。评价指标包括 signed bias、RMSE、MAE、最大绝对误差、raw support、有效覆盖和空洞率；Case 2 还报告振幅、波长、频率和相位。方法与门限见 [仿真验证计划](docs/simulation/simulation_validation_plan.md) 和 [验收标准](docs/simulation/acceptance_criteria.md)。

## 6. 三个逐级仿真场景的结果

这里的三个场景是“静水、固定非零高度、动态正弦规则波”，并非三种真实波型。它们逐级回答零面、非零尺度、时变周期水面能否穿过完整软件链。

### 6.1 Case 0：静水面

**目的。**验证零水面、物理尺度、坐标/网格、静水参考和 `H=Z-Z0` 基础链。

**条件。**2 帧独立记录的静态仿真帧，`H_true=0 m`；候选几何为 2448 x 2048 px、3.45 um/px、8 mm 名义镜头，仿真基线 0.20 m、工作距离 2.00 m；真值表面覆盖 `x=[-0.9,0.9] m`、`y=[-0.8,0.8] m`。WASS runtime 为 `1.11_heads/master-0-g6b82aeb`，官方 `wassgridsurface==0.11.4`。

**状态与结果。**`prepare`、`match`、`autocalibrate`、`stereo` 和官方规则网格均成功；两帧各得到 4,313,574 个 filtered points。规则网格为 `[2,160,160]`、间距 0.010 m。有限网格覆盖 100%，空洞率 0%。

| 指标 | 结果 |
|---|---:|
| H RMSE | 0.0044625 mm |
| H MAE | 0.0035310 mm |
| H 最大绝对误差 | 0.0122764 mm |
| 对真值零高程的 aligned Z RMSE | 0.5541094 mm |
| 2.00 m 平面距离估计误差 | -0.7515314 mm |

**结论与边界。**Case 0 已通过 WASS 核心和官方规则网格高度闭环。极小的 H 时间误差主要反映两帧理想静态重建和 DCT 数值重复性，不能解释为真实相机抗噪能力。详见 [Case 0 报告](docs/validation/case0_static_water.md)。

### 6.2 Case 1：+10 mm 固定高度

**目的。**验证一个已知、非零且符号为正的整体水面位移能否经过完整链恢复。

**条件。**统一 4 帧序列：2 帧静水（0、0.2 s）只用于 `Z0`，2 帧升高面（0.4、0.6 s），`H_true=+0.010 m`；基线 0.20 m、工作距离 2.00 m；静水和升高帧共用一次 WASS 自标定、平面变换、尺度和规则网格。

**原始默认配置。**`ZGAP_PERCENTILE=99` 时所有程序返回 0，但升高帧在最大连通分量阶段只保留 1,794,468 / 4,331,598 点（41.4274%），raw supported grid 为 51.4492%。原冻结运行的 mean H 为 8.8890 mm、bias -1.1110 mm、RMSE 11.0795 mm、MAE 5.6566 mm、最大误差 75.4659 mm。因此默认 99 的原始 Case 1 **保留为验收失败历史基线**，不能被后续适配覆盖。

**单因素 ZGAP 适配。**在不改变输入、matcher/autocalibration、基线、距离、网格、DCT 和验收门限的情况下，仅扫描 `ZGAP_PERCENTILE`。99 到 99.5 之间出现明确的连通支持跃迁：

| ZGAP | 升高帧保留率 | raw support | mean H | bias | RMSE | MAE | 最大误差 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 99 | 41.4274% | 51.4492% | 8.9186 mm | -1.0814 mm | 1.2491 mm（supported） | 1.1007 mm | 6.5992 mm |
| 99.5 | 99.8904% | 100% | 9.1073 mm | -0.8927 mm | 1.0266 mm | 0.9158 mm | 1.6413 mm |
| 99.9 | 99.9998% | 100% | 9.1061 mm | -0.8939 mm | 1.0269 mm | 0.9162 mm | 1.6454 mm |

99.5 是已测试值中跨过支持跃迁的最低值；99.9 几乎不再改善误差。因此 99.5 已冻结为**当前理想近场 Case 1 几何的适配值**，不是 WASS 通用推荐、真实设备参数或全局最优值。适配后 Case 1 作为理想仿真验证完成。详见 [原始 Case 1](docs/validation/case1_constant_height.md)、[ZGAP 单因素扫描](docs/validation/case1_zgap_parameter_sweep.md)。

**重复性：分类 B（Numerically deterministic）。**冻结 99.5 后，WASS stereo 三次输出逐帧 bitwise identical；官方 DCT gridder 五次生成的 `gridded.nc` 和 `config.mat` 文件哈希均不同，但坐标、尺度、mask 和帧序一致。五组 Z 数组的最大跨运行差异为 0.020553 mm，最大平均绝对差 0.003222 mm，最大 `RMSE(delta Z)` 0.004372 mm；高度 RMSE 仅在 1.026197--1.027406 mm 之间变化，最大误差指标跨度 0.005466 mm。

因此文件哈希不同不等于科学结果不稳定：该数值波动远低于毫米/厘米项目尺度，不会改变验收结论。分类为 **B: Numerically deterministic**，而不是 bitwise deterministic。详细证据见 [Case 1 重复性报告](docs/validation/case1_repeatability.md)。

### 6.3 Case 2：一维正弦规则波

**目的。**首次验证真正随时间变化的规则水面，包括高度场、振幅、空间周期和时间频率。

**真值与采样。**

$$
H_{true}(x,t)=A\sin(kx-\omega t+\phi),
$$

其中 `A=0.010 m`、`lambda=0.80 m`、`f=0.50 Hz`、`phi=0 rad`。160 x 160 网格间距 0.01 m，1.60 m 周期采样长度正好容纳 2 个波长，即 80 点/波长；5 Hz 采样下每个 2 s 周期有 10 点。数据共 12 帧：2 帧独立静水只用于 `Z0`，10 帧动态波覆盖一个完整周期。基线 0.20 m、工作距离 2.00 m、`ZGAP_PERCENTILE=99.5`，官方 gridder 0.11.4 DCT、单并行。

**WASS 状态与支持。**全部 12 帧的 `prepare`、`match`、`autocalibrate`、`stereo` 和 gridder 均返回 0。动态帧三角化点数为 4,331,598--4,337,716，最大连通分量保留率 99.9215%--99.9892%；每一帧的 raw observation support、validation eligible domain 和 finite coverage 均为 100%，空洞率 0%。

| 指标 | 结果 |
|---|---:|
| signed height bias | -0.2606 mm |
| height RMSE | 5.3968 mm |
| height MAE | 4.7505 mm |
| 最大绝对高度误差 | 10.1320 mm |
| 恢复振幅 | 9.6930 mm |
| 振幅误差 | -0.3070 mm（-3.0695%） |
| 恢复波长 | 0.8000 m；误差 <1e-12 m |
| 恢复频率 | 0.5000 Hz；误差 0 Hz |
| 包裹相位误差 | +0.7853 rad（44.99 deg） |

冻结门限为 RMSE <=10 mm、MAE <=10 mm、最大误差 <=30 mm，三项均通过，因此 Case 2 **通过预注册的高度场验收**。波参数误差在首轮为报告项，没有在看到结果后新增门限。

**相位诊断已关闭。**约 45 deg 偏移来自世界真值 x 与官方网格 x 的原点差。冻结网格中心为 `-0.10 m`，因此本次映射为 `x_world=x_grid+0.10 m`；参考对齐后相位误差为 `-0.000111 rad`。WASS、gridder 和 H 均未修改。详见 [相位诊断](docs/validation/case2_phase_alignment_diagnosis.md)。

## 7. 当前已经证明什么

在当前冻结的理想合成几何和软件版本范围内，项目已经证明：

- 可以从解析真值水面生成不向 WASS 泄漏真值的虚拟双目图像，并跑通真实 WASS 与官方 `wassgridsurface`；
- WASS 原始三维输出可以被正确解析、显式恢复尺度、统一坐标和映射到规则网格；
- 独立静水 `Z0` 与 `H=Z-Z0` 流程可以恢复静水零场和固定 +10 mm 高度；
- Case 1 的默认 ZGAP=99 失败已定位到支持损失，并通过受控单因素研究得到当前几何的 99.5 适配值；
- 99.5 链虽不是文件级 bitwise deterministic，但属于数值确定的重复性分类 B，其波动不会影响毫米/厘米尺度结论；
- 一组一维正弦规则波的振幅、波长、频率和高度场通过既定高度验收，完整动态链已建立；
- 仿真、配置、坐标、数据接口、验收和外部依赖边界均已形成可追溯文档与自动化测试。

## 8. 当前尚未证明什么

项目尚未证明：

- 候选相机和镜头已经采购、完成实物核验或标定；
- 0.20 m 基线、2.00 m 工作距离或 ZGAP=99.5 是最终部署参数或可泛化最优值；
- 合成图像等同于真实照片，或当前结果覆盖噪声、畸变、同步、反射、折射、眩光、振动和纹理退化；
- 未来真实设备数据已经建立并验证世界坐标到输出网格的物理配准；Case 2
  仿真运行的原点映射已关闭，但不能替代实机配准；
- 多组振幅/波长/频率、二维交叉波、复杂海谱、破碎波或真实海面已经通过；
- 真实水槽或海面高度达到 1 cm 精度；
- WASS 算法由本项目开发，或这些实验是在独立证明 WASS 算法本身普遍正确。

## 9. 下一步工作

建议按以下门控顺序推进：

1. **部署参数空间验证。**预注册并扫描 `baseline x scene distance`，同时检查公共视场、视差范围、三角化角度、raw support、误差和失效点；必要时再加入焦距、视场和波参数维度。单次仿真的 0.20 m x 2.00 m 不能替代参数空间结论。
2. **形成采购依据并采购设备。**结合候选设备规格、接口、同步方案、镜头准确型号、机械刚度、数据吞吐和参数扫描结果冻结物料清单。
3. **真实标定与同步验证。**分别标定两机内参/畸变，测量外参和真实基线，验证硬件触发、曝光时间、帧配对、时钟和漂移。
4. **真实静水 `Z0`。**在固定部署下采集独立静水序列，检查平面度、空间稳定性、时间重复性、有效域和环境光变化。
5. **人工波实验。**从已知固定高度/规则波开始，引入独立位移或波高参考，预注册 ROI 和门限，报告 bias、RMSE、MAE、max、覆盖及失败帧。
6. **扩展到真实海面。**按更大距离、风浪纹理、反光、遮挡、平台振动和环境变化重新建立误差预算及部署方案，并用现场独立参考重新验证；水槽结论不能直接外推。

## 10. 后续更新记录与维护规则

### 维护规则

- 本文件是项目长期宏观入口；专项文档保存完整推导、配置、日志和逐次证据，本页保存经审查后的摘要与链接。
- 每完成一个关键模型、仿真验证、参数冻结、硬件采购/标定、同步验证、水槽实验或海面实测节点，都必须在对应章节更新状态，并在下方追加一条记录。
- 每条记录至少包含日期、Git commit、完成事项、关键数值/结论、结论边界和专项文档链接。
- 失败、未解决诊断和历史基线不得被后续成功结果删除或改写；应说明“原结论”和“后续适配结论”的关系。
- `candidate`、`SIMULATION_NOMINAL`、`SIMULATION_TEST_PARAMETER`、`confirmed` 和 `UNKNOWN/TODO` 必须严格区分；未知值不得猜测。
- 所有精度声明必须注明是几何单元测试、理想仿真、真实水槽还是现场海面；不得跨层外推。
- 若数据或算法表现仅数值可重复而非文件哈希一致，必须同时报告数值波动和重复性分类。
- WASS 始终标注为外部引擎；若未来修改其源码或更换版本，必须单独记录来源、差异、版本与重新验证范围。
- 后续新增或修改公式必须遵守 [Markdown 公式书写规范](docs/FORMULA_STYLE_GUIDE.md)，并在提交前检查 GitHub 公式渲染，避免乱码或定界符再次损坏。

### 更新记录

| 日期 | Git commit | 里程碑 | 摘要 |
|---|---|---|---|
| 2026-08-11 | 见专项历史 | Case 0 闭环 | 静水通过 WASS 核心与官方规则网格；理想仿真，不代表真实设备精度。 |
| 2026-08-12 | `8b33bb9` | Case 1 重复性关闭 | ZGAP=99.5 冻结于当前仿真几何；分类 B，最大跨运行 Z 差异 0.020553 mm。 |
| 2026-08-12 | `b44fe57` | Case 2 高度验收通过 | RMSE 5.3968 mm；波长和频率正确恢复；约 45 deg 相位偏移保留为未解决诊断项。 |
## 2026-08-13 procurement-preparation update

Four controlled ideal-synthetic sinusoidal groups now close the regular-wave
software matrix: A=10/30 mm crossed with f=0.5/1.0 Hz at fixed wavelength
0.80 m. All groups retained 100% raw grid support and passed the frozen height
gates; RMSE was 0.739--1.131 mm. This result is limited to the virtual pinhole
chain and does not establish real-camera, real-water, or physical wave accuracy.
Details: [controlled comparison](docs/validation/sinusoidal_wave_parameter_comparison.md).
## 2026-08-13 deterministic irregular-wave result

IRR-1 froze a 10 s, three-component continuous surface and 52-frame dataset.
WASS prepare and match completed for every frame, but autocalibration repeatedly
failed after successful SBA during homography acceptance. The fail-fast protocol
therefore prevented stereo, gridding and height claims. IRR-1 remains blocked;
deployment distance scanning is not yet authorized. Details are in the
[IRR-1 validation report](docs/validation/irregular_wave_validation.md).
## 2026-08-13 IRR-1A autocalibration adaptation

The original 52-frame joint-autocalibration failure remains recorded. A bounded,
deterministic subset diagnosis showed the result depends on strict SBA error
improvement and match composition, not a simple frame-count ceiling. The frozen
10-dynamic-frame, full-window calibration was applied through WASS's per-workdir
interface to all 52 frames. IRR-1A then passed with 2.368 mm RMSE, 8.732 mm
maximum error and at least 99.996% raw support. Scene-distance validation may
now be designed without erasing the historical failure.

## 2026-08-14 scene-distance result

At fixed B=0.20 m and all other frozen factors, the 2.00 m reference passes
the ideal-synthetic chain. The 1.75 m case fails minimum raw-support coverage
despite passing height-error gates, and the 2.50 m case fails fast during WASS
stereo plane fitting. This does not select a final working distance or establish
real-camera performance. See the
[controlled distance report](docs/validation/scene_distance_validation.md).

## 2026-08-14 baseline result

At fixed 2.00 m scene distance, the 0.15, 0.20, and 0.25 m ideal-synthetic
baselines all passed frozen gates with 100% raw support. Height RMSE was 1.483,
1.030, and 0.906 mm respectively. This is a tested one-dimensional slice, not
selection of a final optimum or real-camera proof. See the
[baseline report](docs/validation/baseline_validation.md) and
[deployment geometry summary](docs/validation/deployment_geometry_summary.md).

## 2026-08-14 baseline-distance cross-check

The single authorized `(B=0.25 m,Z=2.50 m)` point passed the complete ideal
synthetic chain: minimum raw support 99.988%, RMSE 1.551 mm, and maximum error
8.306 mm. Unlike the old `(0.20 m,2.50 m)` case, every plane fit succeeded.
This is direct bounded evidence of baseline-distance coupling, not a complete
deployment map. See the
[cross-check report](docs/validation/baseline_distance_crosscheck.md).

## 2026-08-13 to 2026-08-14 work summary

The pre-purchase ideal-simulation campaign is now closed. It covers the Case 2
phase diagnosis, virtual-stereo geometry, the G0--G3 regular-wave matrix,
IRR-1/IRR-1A, the D1/D0/D2 distance slice, the B1/B0/B2 baseline slice, and the
single XZ-1 baseline-distance cross-check. PASS, FAIL, and BLOCKED results are
retained as separate evidence; XZ-1 removes the former D2 plane-fit blocker only
for `(B=0.25 m,Z=2.50 m)` and does not establish a complete deployment region.

The engineering target is a locally deployable desktop application for camera
configuration, calibration, WASS execution, reconstruction review, quality
control, and data export. A web page or mini-program is no longer the planned
delivery form. The complete management report in DOCX/Markdown is a local-only
deliverable and must not be added to this repository. See the
[two-day summary](docs/progress/2026-08-13_2026-08-14_summary.md).
