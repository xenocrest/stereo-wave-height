# stereo-wave-height 项目宏观汇报与持续更新入口

> 文档定位：本页面面向项目汇报、阶段复盘和新成员快速理解，集中说明“为什么做、怎样做、已经做到什么、还不能证明什么、下一步做什么”。详细推导、配置和逐帧证据仍以链接的专项文档为准。后续进展必须整合回对应章节，不在文末追加游离总结。

## 1. 项目目标

本项目希望建立一套可追溯的双目水面三维形态与高度测量流程。最终产品以左右双目视频为输入；用户在软件中播放视频并选择目标时间，系统提取该时刻的同步帧对，调用 WASS 完成一次单帧三维解算，再用独立参考水面计算相对高度：

面向真实环境的标定与 QA 采用“左右 mono 各自利用完整有效观测、bilateral overlap 仅求固定内参的 stereo R/T”的信息分工，并记录 scene diagnostics、quality reasons 与所有自适应决策。无物理支持区域始终保持 `UNSUPPORTED`；手机阶段形成的策略必须可迁移至专业双目和海面系统。

$$
H(x,y)=Z(x,y)-Z_0(x,y).
$$

其中，`Z(x,y)` 是被测时刻的水面高程，`Z0(x,y)` 是同一坐标、尺度和网格上的独立参考水面，`H(x,y)` 是项目最终关心的相对水面高度场，长度单位统一为 m。带时间维的 `Z(x,y,t)` 与 `H(x,y,t)` 保留给 Wave video analysis Extension。

近期目标是以专业双目相机完成单时刻水面测量和独立物理误差验证；长期再扩展动态与真实海面。这里的“1 cm 级”目前是验收目标和理想仿真软件链结论，**不是实物系统已经达到的精度声明**。

项目当前路线已调整为：

```text
Phase 1  理论模型与合成数据仿真验证（已完成）
  -> Phase 2  真实双目系统标定与 WASS 三维重建（已完成首轮闭环）
  -> Phase 3  视频输入的按需单帧水面三维测量系统（当前主线）
  -> Phase 4  高度计算与独立物理误差验证
  -> Phase 5  结果展示软件
  -> Phase 6  专业双目相机工程迁移

Extension: Wave video analysis
```

项目最终工程形式是 `专业双目相机采集左右视频 -> 软件加载与播放 -> 用户选择时间 t -> 提取 I_left(t)/I_right(t) -> 标定参数 -> WASS/XYZ -> pixel–XYZ -> H(x,y) -> 点云/高度图/统计展示`。视频是最终输入载体，但计算单位是用户选择的一组同步帧，不是实时逐帧重建。

阶段调整不删除任何已有工作。同步模块为播放器选择的左右时刻建立对应关系，但不参与 WASS、三角化或高度计算；wave、长时批处理和性能模块继续作为动态测量 Extension。Production mode 服务单帧结果保存、任务状态与软件接口，并保留未来批量能力。

Phase 3 的核心后端已经实现两种统一入口：明确同步的 image pair，以及 left/right video + target time。后者读取 decoded PTS，使用有来源和置信度的 $t_R=a t_L+b$ 模型选择最近帧，并以实际帧周期建立质量门；只有通过后才进入既有 fixed-calibration WASS pipeline。HomeTank_004 在 20.0 s 的最近 PTS 残差虽为 -1.345 ms，但同步模型仍仅来自 10 Hz 粗光源事件，因此状态严格保持 `FRAME_LEVEL_SYNC_NOT_ESTABLISHED`，WASS 未运行。

随后完成的逐帧 PTS 精化没有掩盖阻塞：static 只有 2 个匹配事件；wave 的 5 个匹配事件仅达到 `FRAME_LEVEL_SYNC_WARNING`，P95 残差为 13.291 ms，相对于 16.656 ms 帧周期仍不足以构成可靠帧级证据。两个测试时刻均在 WASS 前停止。固定光源 ROI 的人工确认或未来硬件同步是下一项输入条件，而不是通过修改重建参数规避。

进一步的 14 组受控 WASS 敏感性实验建立了独立的按需工程门，并未覆盖严格同步历史：$R_0$ 接受、±1 帧警告、$|k|\ge2$ 拒绝。正式选择规则永远取时间模型预测的 $R_0$，不得按重建效果选优。HomeTank_004 的 static 和 wave R0 均已通过现有 video-mode backend 输出 XYZ、pixel–XYZ 与 H(x,y)，状态仍带同步警告且 `PHYSICAL_ACCURACY_NOT_ESTABLISHED`。

在任何标尺数据进入前，正式 R0 高度数组已完成只读 QA 并以哈希冻结。Static 的 +54.135 mm raw max 来自小比例、靠近 support 边缘的正尾部；Wave 分布主要呈整体负偏置，但未据此解释物理波高。Phase 4 首个单向独立验证样例已完成：只查询人工确认位置附近的冻结 pixel–XYZ，不插值、不反馈调参。局部 stereo 变化为 `-5.7672 mm`，独立标尺变化为 `+0.1 mm`，绝对差异 `5.8672 mm`；但参考变化远小于人工读尺不确定度，故流程完成而物理精度仍未建立。

为提高独立验证判别力，Case 2 由用户仅依据画面可读性选定 `candidate_02`，并在人工数据进入前冻结一次正式 WASS 输出。用户随后登记 Static/Wave `9.1/9.6 mm` 与 canonical 点击 `(798,414)/(799,396)`；五项 artifact 哈希均保持一致。Case 2 Wave 点击映射准确，但距最近冻结观测 `15.4946 px`，超过既定 2 px gate，±1 px 九点也全部失败，因此分类为 `CASE2_PIXEL_XYZ_DISTANCE_GATE_FAIL`。没有扩大 gate、插值或用全局高度替代局部测量，物理误差无法计算；Case 1 仍未覆盖。

阶段计划详见 [项目计划](docs/PROJECT_PLAN.md)，核心模型的快速导航见 [建模成果总览](docs/MODEL_OVERVIEW.md)。

当前新增：[双目系统参数设计模型](docs/stereo_system_design/disparity_depth_model.md)，用于指导未来专业双目相机选型和部署参数设计。

真实视频闭环已完成第一轮验证，当前进行面向后续专业双目系统的静水帧一致性分析。

真实视频解算流程已进入闭环开发阶段，当前统一入口能够编排视频抽帧、固定标定 WASS、XYZ/PLY、静水参考高度样本和 JSON 报告；HomeTank_004 只用于诊断验证，静水稳定性失败和工业精度未建立的结论保持不变。

真实 wave 视频阶段已经启动并完成首个五帧时间序列软件闭环；所有高度使用同一 static frame 000000 参考面，运行状态为 `WAVE_PIPELINE_COMPLETED_WITH_STATIC_WARNING`，静水稳定性失败、候选同步和未建立工业精度的限制继续保留。

波高与稳定性评价接口已经建立，能够在明确的共同物理观测域输出 raw 时间序列、RMS、peak-to-peak 和分析性去均值结果，并在记录不足时拒绝生成显著波高。HomeTank_004 的五帧结果呈现候选时变信号，但 43.530 mm 的波形均值变化不能与 97.233 mm 静水漂移分离，因此正式状态为 `WAVE_RESULT_NOT_VALIDATED`，后续仍需稳定静水基准、长时间同步序列和独立物理参考。

HomeTank_004 画面中的固定竖直刻度尺已纳入独立物理参考体系。Phase 4 正式比较采用人工 Static/Wave 水面线读数差与相同正方向下的重建局部平面法向高度；没有使用 camera Z 或全局高度均值。首个样例的人工读数、像素、不确定度和刻度方向均已登记并完成比较，但 0.1 mm 的参考变化不足以约束毫米级准确度，因此不宣称工程测量完成。

标尺边界固定为：**标尺数据仅用于结果验证，不参与任何三维重建和高度计算流程。Ruler data is only used for independent validation and is not included in the reconstruction pipeline.** 它不能向 WASS、XYZ、参考平面或高度结果反馈参数。

通用重建输出进一步保存 WASS rectified computational camera 像素与米制 XYZ 的投影对应，并将高度计算独立为点到参考平面的有符号正交距离模块。HomeTank_004 五帧共验证 955,521 组对应，重算高度与既有结果差异为 0 m。标尺数据没有进入该链，只在下游承担独立物理验证。

Wave 展示接口现已形成统一 CSV/JSON：每帧保留物理 ROI、时间戳、有效点数、均值、中位数、RMS、P5/P95 和极值，同时并列保存 raw 与显式窗口的分析性漂移序列。独立标尺读数采用单独 YAML 输入；当前为空，因此验证状态为 `MANUAL_REFERENCE_REQUIRED`。现有 5 帧只覆盖 0.4 s，不能作为稳定长时间波高或工程精度结论。

完整 HomeTank_004 wave 全帧执行已做容量与同步预检：9,556 帧按真实5帧运行测得的产物比例预计至少需要 46.29 小时和约 726.83 GB，预检时 D 盘可用约65.05 GB；两路不同平均帧率的全序列时间映射也尚未验证。因此长时间执行状态明确冻结为 `BLOCKED_RESOURCE_AND_SYNCHRONIZATION_PREFLIGHT`，并新增无缺口批次规划接口；没有降采样、后台失控运行或伪造长时间指标。

工程化诊断现已加入 WASS 分阶段计时和光源事件同步接口。HomeTank_004 固定三帧的组件总耗时平均为 25.31 s/frame：`match` 平均 11.55 s，是主要稳定瓶颈；Z-gap、离群点和平面阶段组成的 stereo 后处理平均 8.31 s，且造成主要帧间波动。两路 wave 视频的 10 Hz 亮度序列匹配到 10 个同极性事件，得到 $t_{right}-t_{left}=0.000$ s、残差 RMS 0.0548 s；这只建立粗时间关系，约 60 FPS 的帧级对应仍为 `SYNC_NOT_ESTABLISHED`。性能与同步分析均不改变 WASS、标定或高度结果，也不构成实时或工业性能声明。

Production mode 工程框架进一步把 ROI capability、输出保留和批次恢复显式化。现有 WASS mask/triangulation bbox 不作用于主要的 `match` 阶段，且当前没有人工注册的双相机水面 ROI，因此没有伪造 ROI 加速对比。保留 height、pixel–XYZ、metric XYZ 与结果文件并在验证 checkpoint 后裁剪重复/诊断产物，可把五帧保留量减少约75.7%，但组件总耗时估计只从25.311降至25.085 s/frame。100帧容量预检通过，执行仍因帧级同步未建立而阻塞；所以目前只有可测试的批处理/合并框架，没有生产加速或重建一致性实测结论。

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

## 7. 扩展波形与采购前验证矩阵

### 7.1 G0--G3 规则波幅频组合

在冻结波长 0.80 m、基线 0.20 m、工作距离 2.00 m 及其余处理条件后，组合测试幅值 10/30 mm 与频率 0.5/1.0 Hz。四组 raw support 均为 100%，高度 RMSE 为 0.739--1.131 mm，最大误差为 2.099--3.672 mm，全部通过冻结门限。该结论只覆盖已测试的理想合成幅频矩形，不代表真实设备或真实水面性能。详见 [规则波参数对比](docs/validation/sinusoidal_wave_parameter_comparison.md)。

### 7.2 确定性不规则波与自动标定适配

IRR-1 使用三组不同幅值、波长、频率和相位的正弦分量叠加，冻结为 2 帧静水加 50 帧动态水面。原始 52 帧联合自动标定在 SBA 后的单应性验收路径稳定失败，因此原始 IRR-1 保持 **FAIL/BLOCKED**，且没有生成 stereo、网格或高度指标。

源码与子集诊断表明，失败与 SBA 后严格误差改进条件及匹配组成有关，不是简单的帧数上限。冻结覆盖完整时间窗且不含静水重复帧的 AC-10D 子集后，IRR-1A 完成全部 52 帧处理：RMSE 2.368 mm、MAE 1.882 mm、最大误差 8.732 mm、raw support 不低于 99.996%，结论为 **PASS**。适配成功不覆盖原始失败历史。详见 [不规则波验证](docs/validation/irregular_wave_validation.md) 和 [自动标定诊断](docs/validation/irregular_wave_autocalibration_diagnosis.md)。

## 8. 部署几何：工作距离、基线与交叉验证

冻结其他因素后，单因素和交叉结果如下：

| 实验 | 基线 B | 距离 Z | 历史状态 | 主要证据 |
|---|---:|---:|---|---|
| D1 | 0.20 m | 1.75 m | FAIL | 高度误差通过，但最小 raw support 仅 71.758%，未过覆盖门限 |
| D0/B0 | 0.20 m | 2.00 m | PASS | raw support 100%，RMSE 1.030 mm |
| D2 | 0.20 m | 2.50 m | BLOCKED | stereo 平面拟合阻塞；未生成网格和高度指标 |
| B1 | 0.15 m | 2.00 m | PASS | raw support 100%，RMSE 1.483 mm |
| B2 | 0.25 m | 2.00 m | PASS | raw support 100%，RMSE 0.906 mm |
| XZ-1 | 0.25 m | 2.50 m | PASS | 最小 raw support 99.988%，RMSE 1.551 mm；解除该点原平面拟合阻塞 |

理论上 $d=f_{px}B/Z$，视差误差引起的深度敏感度近似为：

$$
\left|\frac{\partial Z}{\partial d}\right|=\frac{Z^2}{f_{px}B}.
$$

因此工作距离与基线需要联合设计。现有证据是两个一维切片加一个交叉点，不是完整 $(B,Z)$ 有效域，也不能证明保持 $B/Z$ 不变必然成功或 0.25 m 为最优基线。详见 [部署几何汇总](docs/validation/deployment_geometry_summary.md)。至此，采购前核心理想仿真验证按既定范围完成。

## 9. HomeTank_004 真实视频实验总结

HomeTank_004 使用 iQOO Neo5S（cam0/left）和 iQOO Z10 Turbo Plus（cam1/right）作为低成本双目视频输入。六段 calibration/static/wave 视频已在同一 rig setup 下完成采集；calibration、static 单帧重建和五帧 wave 扩展闭环均已执行，完整长时 wave 仍受资源与帧级同步门阻塞。

已经完成：

- 真实视频输入检查和时间戳配对；
- OpenCV 官方单目/双目标定，获得 `K/D/R/T`；
- 标定 baseline 68.6847 mm 与人工 baseline 70.0000 mm 的 physical sanity comparison；
- OpenCV → WASS 固定标定参数格式和坐标约定适配；
- WASS rectification、dense stereo、triangulation 与单帧静水面恢复；
- disparity 范围与 StereoSGBM uniqueness/block size 的受控诊断。

当前瓶颈是 **StereoSGBM 匹配稳定性**。三帧均能形成约 2.0--2.25 mm RMS 的单帧平面，但原冻结配置下平均 Z 跨帧变化约 97.23 mm、最大平面法向差约 12.17 deg。有效视差靠近 640 px 搜索上界；扩大范围会增加错误匹配，调整 uniqueness/block size 虽能缩小波动，却只保留靠近边界的窄支持区域，尚不能建立可靠静水参考。

因此 `CALIBRATION_QUALITY_FAIL`、`STATIC_VALIDATION_FAIL` 和 `approved_for_wass=false` 均保持。五帧 wave 只证明扩展软件链闭环，不改变这些质量门。单帧主线下一步转向专业双目相机与独立物理验证；动态视频问题继续在 Extension 中保留。详细证据见 [HomeTank_004 static summary](experiments/real_video/HomeTank_004/static_validation_summary.md) 和 [SGBM audit](experiments/real_video/HomeTank_004/wass_sgbm_matching_parameter_audit.md)。

冻结 WASS 点的空间 MLS 已完成单点 hold-out 和连续空洞 `hole_2` 验证，并建立首个 canonical cam1 像素级高度图 MVP。输出保留 `OBSERVED / ESTIMATED / UNSUPPORTED` 三态和保守水面 ROI；该结果是 WASS 曲面内部一致性与展示链验证，不替代独立物理误差验证。

单帧后端已加入可选 polygon water ROI 与自动 dense-height 调用，且关闭时保持原行为。使用已验证的 policy-capable runtime 后，Case 2 新 smoke run 已从视频输入和目标时间自动生成 XYZ/H、pixel–XYZ、dense NPZ、高度图、状态图与统一结果，分类为 `SINGLE_FRAME_DENSE_BACKEND_COMPLETED`。后端已冻结用于演示层集成；这不改变同步与物理精度警告。

## 10. 当前已经证明什么

在当前冻结的理想合成几何和软件版本范围内，项目已经证明：

- 可以从解析真值水面生成不向 WASS 泄漏真值的虚拟双目图像，并跑通真实 WASS 与官方 `wassgridsurface`；
- WASS 原始三维输出可以被正确解析、显式恢复尺度、统一坐标和映射到规则网格；
- 独立静水 `Z0` 与 `H=Z-Z0` 流程可以恢复静水零场和固定 +10 mm 高度；
- Case 1 的默认 ZGAP=99 失败已定位到支持损失，并通过受控单因素研究得到当前几何的 99.5 适配值；
- 99.5 链虽不是文件级 bitwise deterministic，但属于数值确定的重复性分类 B，其波动不会影响毫米/厘米尺度结论；
- 一组一维正弦规则波的振幅、波长、频率和高度场通过既定高度验收，完整动态链已建立；
- G0--G3 四组规则波、适配后的确定性不规则波均在冻结理想合成条件下通过；
- 工作距离和基线存在需要联合设计的耦合关系；已保留距离实验的 FAIL/PASS/BLOCKED 与交叉点 PASS 证据；
- 仿真、配置、坐标、数据接口、验收和外部依赖边界均已形成可追溯文档与自动化测试。

## 11. 当前尚未证明什么

项目尚未证明：

- 候选工业相机和镜头已经采购、完成实物核验或标定；
- 0.20 m 基线、2.00 m 工作距离或 ZGAP=99.5 是最终部署参数或可泛化最优值；
- 合成图像等同于真实照片，或当前结果覆盖噪声、畸变、同步、反射、折射、眩光、振动和纹理退化；
- 未来专业工业相机数据已经建立并验证世界坐标到输出网格的物理配准；Case 2
  仿真运行的原点映射已关闭，但不能替代实机配准；
- 二维交叉波、复杂海谱、破碎波或真实海面已经通过；
- 当前有限部署几何实验已经覆盖完整有效域，或已确定全局最优基线与工作距离；
- HomeTank_004 的手机静水跨帧稳定性已经通过，或真实水槽/海面高度达到 1 cm 精度；
- WASS 算法由本项目开发，或这些实验是在独立证明 WASS 算法本身普遍正确。

## 12. 真实视频验证、专业设备与桌面工程化

建议按以下门控顺序推进：

1. **按需单帧测量主线。**加载左右视频，由用户选择目标时间并提取同步帧对，再完成固定标定 WASS、XYZ、pixel–XYZ、水面高度和质量报告；不实时逐帧运行 WASS。
2. **独立物理验证。**标尺或其他参考只在重建结束后比较误差，不参与解算。
3. **设备迁移。**确认专业相机、镜头、硬件同步、照明、安装和计算设备的准确型号与接口，并复用同一帧对接口。
4. **实机双目标定。**完成内参、畸变、外参、真实基线、硬件触发、帧配对和漂移验证。
5. **静水与人工波。**建立独立静水 `Z0`，从静水、固定高度和规则人工波逐级验证，并与独立物理参考比较；最终 1 cm 目标只在此专业设备阶段正式验收。
6. **真实环境扩展。**评估水面反光、折射、泡沫、纹理退化、环境光、振动和更大距离，重新建立误差预算与部署边界。
7. **结果展示软件。**建设未来最终 `.exe`：视频层负责左右视频，交互层负责播放、时间选择和暂停，计算层负责同步帧提取、标定、WASS、XYZ 和 Height，展示层负责点云、高度图、统计与误差结果。该程序不是手机专用 Demo，也不以实时处理为承诺。

离线桌面 Demo Stage 1 已完成最小闭环：加载现有标定、选择双目视频、播放/暂停并选取时刻、异步调用冻结单帧 backend、显示原始帧/高度图/状态图和保留历史测量。叠加、逐像素查询、点云交互和选择性导出留待 Stage 2。

Demo Stage 2 已完成透明高度叠加、canonical-cam1 pixel 的只读 XYZ/H/status 查询、原始 WASS 点云查看和安全 Session 导出。由此第一版离线演示 MVP 闭环并冻结；后续仅处理 coverage、precision、UX、visualization、robustness 与 packaging，不改变 MVP 数值主流程。

离线演示的高度基准现由用户选择：用户可在任意暂停帧运行一次既有单帧 WASS，以当前 water ROI 内的有效 XYZ 拟合固定参考面；之后的解算、overlay、hover、历史记录和导出均绑定该 reference ID。标定、视频对或 ROI 改变会使参考面失效，且参考帧不要求是静水状态。

Windows 演示分发已采用 PyInstaller `--onedir` 完成验证：GUI 与 Python backend 由同一 EXE 分派，WASS/FFmpeg 作为随目录携带的外部 runtime，运行不依赖系统 Python、网络、`PYTHONPATH` 或仓库 cwd。分发二进制不进入 Git，构建脚本和路径适配保持可追溯。

演示输入工作流现采用中文分步引导：先选择导入已有 YAML 标定结果或由左右标定视频调用既有 OpenCV 标定后端，再导入明确标记 LEFT/RIGHT 的水面测量视频，最后进入播放、暂停、单帧解算和结果查看；普通用户无需接触内部配置路径。

演示运行时已完成阻断性健壮性修复：WASS 非 UTF-8 日志不再把成功重建误判为失败，目标时刻失败时仅按固定顺序尝试 ±2 个完整同步时刻；播放预览使用后台 latest-frame 解码，不改变暂停后的精确 PTS/sync 解算。

项目主路线为：`Theory/Simulation -> Real Stereo Calibration/WASS -> Video-based On-demand Single-frame Measurement -> Independent Physical Validation -> Result Application -> Professional Stereo Migration`。Wave video analysis 是 Extension；真实视频层不会回写或覆盖既有仿真历史。详细协议见 [真实视频验证](docs/real_video_validation/README.md)。

完整用户汇报 DOCX/Markdown 仅保存在本地，不进入本仓库；大型 PNG、原始双目图像、`xyzC`、NetCDF 和 WASS 运行目录同样不得提交。

## 13. 文档维护规则

### 维护规则

- 本文件是项目长期宏观入口；专项文档保存完整推导、配置、日志和逐次证据，本页保存经审查后的摘要与链接。
- 每完成一个关键节点，必须把结论整合到其所属章节，并同步更新专项证据文档；禁止在文末连续追加“Latest update”“Recent work”“Summary”等游离总结。
- 失败、未解决诊断和历史基线不得被后续成功结果删除或改写；应说明“原结论”和“后续适配结论”的关系。
- `candidate`、`SIMULATION_NOMINAL`、`SIMULATION_TEST_PARAMETER`、`confirmed` 和 `UNKNOWN/TODO` 必须严格区分；未知值不得猜测。
- 所有精度声明必须注明是几何单元测试、理想仿真、真实水槽还是现场海面；不得跨层外推。
- 若数据或算法表现仅数值可重复而非文件哈希一致，必须同时报告数值波动和重复性分类。
- WASS 始终标注为外部引擎；若未来修改其源码或更换版本，必须单独记录来源、差异、版本与重新验证范围。
- 后续新增或修改公式必须遵守 [Markdown 公式书写规范](docs/FORMULA_STYLE_GUIDE.md)，并在提交前检查 GitHub 公式渲染，避免乱码或定界符再次损坏。
