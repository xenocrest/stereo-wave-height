# stereo-wave-height 项目计划

## 1. 项目定位

`stereo-wave-height` 是独立的双目测波科研项目。项目以 WASS（Waves Acquisition Stereo System）为核心外部依赖，建立从同步双目影像到可追溯水面高度场的完整研究与验证体系。

项目最终目标为：

```text
同步双目图像
  → 水面三维重建 Z(x,y,t)
  → 独立静水面参考 Z0(x,y)
  → 相对静水面高度 H(x,y,t)=Z(x,y,t)-Z0(x,y)
```

其中 `x,y` 是统一水槽或海面坐标系中的水平坐标，单位 m；`t` 是时间，单位 s；`Z`、`Z0` 和 `H` 均为 m。当前近期目标是在实验室人工波条件下验证约 1 cm 级高度解算，长期目标是扩展到真实海浪场景。

## 2. 总体技术路线

```text
建立并验证 WASS 外部引擎集成链
  → 静水、固定高度、动态正弦波三级理想仿真闭环
  → 关闭相位/坐标/时间对齐问题
  → 扫描 baseline × scene distance 部署参数
  → 采购并接入实验室双工业相机同步数据
  → 水槽静水与人工波 1 cm 级高度验证
  → 配置、质量控制和数据流程工程化
  → 真实海浪环境扩展与再验证
```

路线中的“1 cm 级”是待验证目标，不是当前已达到的性能声明。理论误差预算、候选硬件条件和验收指标见 [WASS 水槽尺度适配论证](wass/lab_scale_adaptation.md) 与 [1 cm 误差预算](wass/one_cm_error_budget.md)。

## 3. 阶段任务

### Phase 1：项目初始化与理论体系建立

目标是建立独立、可追溯的科研仓库和统一的数学语言。

主要任务：

- 初始化私有 GitHub 仓库和项目目录；
- 明确项目边界、数据纪律和外部依赖管理方式；
- 定义相机几何、双目重建、水面模型和误差传播；
- 统一高度定义为 `H(x,y,t)=Z(x,y,t)-Z0(x,y)`；
- 锁定 WASS 上游、版本、许可证和复现基线；
- 完成 WASS 架构、处理链、输入输出及水槽尺度适配分析。

阶段出口：理论定义无歧义，WASS 版本可追溯，系统设计和复现计划经过文档审查。

### Phase 2：WASS 复现与实验数据接入

目标是在不修改 WASS 上游源码的前提下，跑通其标准处理链并接入小规模实验数据。

主要任务：

- 在隔离的 Linux/Docker 或经确认的兼容环境中构建锁定版本；
- 使用小型样例验证 `wass_prepare → wass_match → wass_autocalibrate → wass_stereo → wassgridsurface`；
- 建立候选双工业相机的同步采集、帧配对和元数据规范；
- 将 Bayer 8/10 bit 数据以固定、可追溯方式转换为 WASS 输入；
- 输入自定义内参，恢复物理尺度并验证坐标方向；
- 冻结首轮配置、运行日志和质量指标。

阶段出口：小型数据端到端重建成功，输入、配置、版本和输出可复现；尚不要求达到 1 cm。

### Phase 3：水槽人工波高度验证

目标是在实验室水槽内完成厘米级高度目标的端到端验证。

主要任务：

- 确定工作距离、焦距、基线、共同视场、帧率和曝光；
- 验证标定重投影误差、同步误差、刚体尺度和静水平面度；
- 采集独立静水序列并建立 `Z0(x,y)`；
- 重建规则人工波得到 `Z(x,y,t)`，计算 `H(x,y,t)`；
- 与独立波高或位移参考比较，统计 RMSE、偏差、最大误差、空洞率和匹配有效率；
- 在独立验证集上判定是否达到 1 cm 级目标。

阶段出口：形成可审计的实验报告。只有满足预先冻结的验收标准，才能声明达到目标。

### Phase 4：工程化和真实海浪扩展

目标是在实验室验证基础上提高稳定性、自动化程度和环境适应性，并迁移到真实海浪。

主要任务：

- 工程化配置管理、批处理、失败检测、质量报告和数据谱系；
- 建立标定漂移、同步、存储、计算资源和现场操作规范；
- 评估更大工作距离、基线、视场、风浪纹理、反光和环境光变化；
- 按真实海浪尺度重新建立误差预算与参数配置，不能直接沿用水槽结论；
- 通过现场独立参考数据重新验证精度、覆盖率和鲁棒性。

阶段出口：形成面向真实海况的可部署测量流程，以及明确适用范围和失效边界。

## 4. 项目原则

1. **WASS 优先。** 优先严格复现 WASS，不原创替代其核心立体匹配和三维重建算法。
2. **数学依据。** 所有模型、坐标变换、误差预算和验收指标均需有 WASS 源码、论文、官方资料或明确数学推导支撑；未确认内容标记 `UNKNOWN/TODO`。
3. **数据可追溯。** 每次实验记录相机、镜头、标定、触发、配置、软件版本、输入清单、质量指标和输出关联；大型原始数据不进入 Git。
4. **项目隔离。** 本项目不与旧 `lanhung/wave-height` 项目混合，不复制其代码、数据或未验证结论。
5. **外部依赖只读。** WASS 作为外部依赖记录和调用，不修改或复制其上游源码。
6. **验证先于宣称。** 理论可行性、模拟结果和实测精度必须明确区分。

## 5. 当前状态

截至当前仓库版本，已完成：

- GitHub 仓库初始化及项目结构建立；
- WASS 上游、许可证与复现版本锁定；
- WASS 架构、处理链、输入输出和复现环境分析；
- WASS 面向实验室水槽尺度的适配分析；
- 1 cm 目标的理论误差预算和第一阶段验收条件；
- 静水面参考作为 WASS 后处理的集成设计；
- WASS 输出标准化适配、坐标变换、静水参考、高度计算和误差指标核心代码；
- 理想虚拟双目相机、水面真值模型与可复现合成立体影像生成；
- WASS 输入工作区适配、外部进程 runner、显式 NetCDF 映射 parser 及其自动化测试；
- 本机已有 WASS runtime 定位、版本/哈希绑定和四程序健康检查；
- Case 0 静水仿真的 WASS 核心、官方网格和标准高度链正式闭环；
- Case 1 的 default-99 历史基线未达预注册门槛；后续单因素扫描在当前仿真几何冻结 `ZGAP_PERCENTILE=99.5`，raw support 达到 100%，H RMSE 约 1.03 mm、MAE 约 0.916 mm、最大误差约 1.65 mm，Case 1 已通过；
- Case 1 分层误差诊断完成：真值严格为 10 mm，xyzC 平面恢复为 8.999 mm；
  升高帧只有 51.45% 网格单元具有原始点支持，官方 DCT 的无支持区域贡献
  超过 98% 平方误差；
- Case 1 支持损失已定位到 WASS 三角化后的 Z-gap 最大连通分量提取：升高帧
  在此单步丢失 58.57% 点。项目已定义 raw observation support mask 作为后续
  预注册物理有效域；具体垂直断带机制仍受既有可观测性限制；
- 已完成运行版 Z-gap 数学规则与断带形态审计；当前发行构建没有官方
  pre-cluster 浮点深度、阈值与完整标签输出，机制归因门选择 D（观测能力
  不足）。raw/grid/eligible 三层有效域规范已建立，不追溯修改原验收结论；
- 已审计本机包、运行提交、master、v1.5--v1.11 与相关历史分支，确认
  `NO_OFFICIAL_OBSERVABILITY_INTERFACE`：Debug 构建不会启用被源码注释的
  pre-cluster 导出，`SAVE_FULL_MESH` 又位于 cluster 之后。下一步需向上游
  请求正式诊断接口，禁止自行 patch；
- Case 1 重复性验证完成：WASS `xyzC` 三轮逐帧 bitwise identical；gridder 文件哈希不同，但最大 Z 波动 0.020553 mm，非确定性来自 0.11.4 未固定的 `torch.rand` 与 NumPy permutation/shuffle，分类 B（Numerically deterministic）；
- Case 2 一维正弦规则波完成：$A=10\ \mathrm{mm}$、$\lambda=0.80\ \mathrm{m}$、$f=0.50\ \mathrm{Hz}$、$\phi=0$，2 静水 + 10 动态帧，raw support 100%；bias -0.2606 mm、RMSE 5.3968 mm、MAE 4.7505 mm、最大误差 10.1320 mm，预注册高度门限通过；$A_{calc}=9.6930\ \mathrm{mm}$（-3.0695%）、$\lambda_{calc}=0.8000\ \mathrm{m}$、$f_{calc}=0.5000\ \mathrm{Hz}$；包裹相位误差 +0.7853 rad 仍未解决；
- 已确认 OpenCV XML、配置派生、xyzC 解码和 wassgridsurface 0.11.4 NetCDF 接口。

当前尚未完成：

- Case 2 相位、坐标原点和时间零点对齐诊断；
- `baseline × scene distance` 等部署参数空间验证；
- WASS 锁定 `v_1.5` 基线的独立构建复现；
- 工业相机实机接入与同步测量；
- 水槽静水和人工波实验；
- 1 cm 目标的实测达标声明。

Case 0/1/2 分别是静水零场、固定非零高度和动态正弦规则波三级验证场景，并非三种波。它们已在本机 WASS `1.11` 和官方 gridder 0.11.4 上形成设备采购前的软件全链路闭环。这些理想仿真不等同于真实设备或真实水面验证，不能据此声称真实海面达到 1 cm。

## 6. 文档导航

- [完整文档索引](README.md)
- [项目概述](project_overview.md)
- [研究方向](research_direction.md)
- [双目测波系统总体设计](system/stereo_measurement_system_design.md)
- [WASS 复现计划](wass/reproduction_plan.md)
- [WASS 端到端集成验证](wass/end_to_end_validation.md)
- [Case 0 静水验证](validation/case0_static_water.md)
- [Case 1 固定高度验证](validation/case1_constant_height.md)
- [Case 1 误差根因诊断](validation/case1_error_diagnosis.md)
- [Case 1 重建支持追踪](validation/case1_support_trace.md)
- [Case 1 Z-gap 连通分量分析](validation/case1_zgap_component_analysis.md)
- [WASS cluster 可观测性审计](validation/wass_cluster_observability.md)
- [WASS 隔离诊断构建](validation/wass_diagnostic_build.md)：精确源码基线与只读观测补丁已建立，但首次构建使用 OpenCV 4.10，而正式版为 4.6；Case 0/1 `xyzC` 哈希均不一致，诊断数据已禁用，`OBSERVABILITY_LIMITATION` 尚未解除，Case 2 继续禁止。
- [WASS 构建环境复现审计](validation/wass_build_reproducibility.md)：确认正式版为 x64 Release、14.28 linker 和自定义模块化 OpenCV 4.6；精确 v142 小版本及原 OpenCV 开发树未恢复，clean upstream 构建未执行，状态为 `BUILD_ENVIRONMENT_NOT_REPRODUCED`。
- [物理有效测量域规范](data_model/measurement_valid_domain.md)
- [WASS 参数映射](wass/wass_parameter_mapping.md)
- [静水参考集成](wass/static_water_reference_integration.md)
- [数学模型](mathematical_model/height_definition.md)
- [Case 1 Z-gap 单因素适配](validation/case1_zgap_parameter_sweep.md)

Case 1 最新状态：已完成只改变 `ZGAP_PERCENTILE` 的受控扫描。99 到 99.5
之间出现明确连通性跃迁，升高帧保留率由 41.43% 增至 99.89%，原始支持域
RMSE 未恶化。结论分类为 A，99.5 是当前冻结仿真几何下有依据的候选适配值；
原始 default-99 失败结论和 `OBSERVABILITY_LIMITATION` 均保留；后续重复性门通过后已按独立任务进入 Case 2。

Case 1 重复性门已完成：正式 WASS stereo 三轮输出逐帧 bitwise identical；固定
xyzC 的官方 DCT 五轮虽受未设种子的 PyTorch/NumPy 初始化影响而非位级一致，
但最大 Z 波动仅 0.0206 mm，H RMSE 跨轮范围为 1.0262--1.0274 mm，结论分类
为 B（numerically deterministic）。`ZGAP_PERCENTILE=99.5` 现冻结于该仿真
Case 1；Case 1 已结束，随后已在独立任务中完成 Case 2。

Case 1 现正式完成。Case 2 已使用单组一维正弦波完成端到端验证：10 mm 波幅、
0.80 m 波长、0.50 Hz、10 个动态帧加2个独立静水帧。raw support 为100%，
高度 RMSE 5.397 mm、MAE 4.751 mm、最大误差10.132 mm，均通过冻结门限；
波幅恢复误差为 -3.07%，波长和频率恢复到离散真值。相位存在0.785 rad偏移，
已登记为后续独立坐标/相位诊断项，未据此调参或修改本次结果。

Case 2 相位诊断已关闭：`+0.7853 rad` 来自世界真值 x 与冻结官方网格
x 的原点相差 `+0.10 m`，在 `lambda=0.80 m` 下恰为 `pi/4`。使用显式
`x_world=x_grid+0.10 m` 后，相位误差为 `-0.000111 rad`，参考对齐 RMSE
为0.8617 mm。修复仅更正项目评价坐标，不修改 WASS、gridder 或历史结果。

虚拟双目几何可信性验证已通过：参数到内参的映射、独立理论投影、多深度视差、
点集及平面/正弦整面三角化闭环均达到机器精度门限；shared physical texture
调用链已确认。该结论只覆盖理想针孔几何，真实光学与标定误差仍需实机验证。
## 2026-08-13 controlled regular-wave matrix

The pre-purchase G0--G3 kinematic sinusoidal matrix is complete. With all
geometry, WASS, grid and acceptance settings frozen, amplitudes 10/30 mm and
frequencies 0.5/1.0 Hz all passed. Raw support was 100%; height RMSE ranged
0.739--1.131 mm and maximum error 2.099--3.672 mm. This confirms stability only
for the ideal synthetic parameter rectangle, not real equipment or water.
See [the comparison report](validation/sinusoidal_wave_parameter_comparison.md)
and [long-term matrix](validation/prepurchase_validation_matrix.md).
