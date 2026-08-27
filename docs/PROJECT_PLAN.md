# stereo-wave-height 项目计划

## 1. 项目定位

`stereo-wave-height` 是独立的双目水面测量科研项目。项目以 WASS（Waves Acquisition Stereo System）为核心外部依赖，最终交付双目视频输入的按需单帧水面测量与展示软件。

项目最终目标为：

```text
左右双目视频
  → 用户选择目标时间 t
  → 提取同步图像 I_left(t), I_right(t)
  → 水面三维重建 Z(x,y)
  → 独立静水面参考 Z0(x,y)
  → 相对静水面高度 H(x,y)=Z(x,y)-Z0(x,y)
```

其中 `x,y` 是统一水槽或海面坐标系中的水平坐标，单位 m；`Z`、`Z0` 和 `H` 均为 m。时间维 `t` 属于 wave video Extension。当前近期目标是以专业双目相机完成单时刻水面三维测量及严格独立物理验证；约 1 cm 仍是待实测的目标，不是既有性能声明。

## 2. 总体技术路线

```text
Phase 1  理论模型与合成数据仿真验证
  → Phase 2  真实双目系统标定与 WASS 三维重建
  → Phase 3  视频输入的按需单帧水面三维测量系统（当前主线）
  → Phase 4  高度计算与独立物理误差验证
  → Phase 5  结果展示软件
  → Phase 6  专业双目相机工程迁移

Extension: Wave video analysis
```

路线中的“1 cm 级”是待验证目标，不是当前已达到的性能声明。理论误差预算、候选硬件条件和验收指标见 [WASS 水槽尺度适配论证](wass/lab_scale_adaptation.md) 与 [1 cm 误差预算](wass/one_cm_error_budget.md)。

统一产品路线为 `Theory/Simulation -> Real Stereo Calibration/WASS -> Video-based On-demand Single-frame Measurement -> Independent Physical Validation -> Result Application -> Professional Stereo Migration`。手机不是独立路线或最终设备，只提供历史真实输入验证。视频是最终输入载体；用户选择时刻后只解算对应的一组同步帧，不实时逐帧运行 WASS。

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

### Phase 3：视频输入的按需单帧水面三维测量系统（当前主线）

英文：Video-based on-demand single-frame stereo measurement system。

目标是加载左右视频，让用户播放并选择目标时间，提取对应同步帧对，再稳定转换为可追溯的 XYZ、水面形态和 `H(x,y)`。视频连续存在，但 WASS 只响应按需单帧任务，不要求实时处理。

主要任务：

- 定义 left/right video、用户目标时间、同步帧提取、标定版本、坐标、单位和质量元数据；
- 运行固定标定 WASS，输出 XYZ、pixel–XYZ 和有效支持；
- 建立独立参考水面并计算沿其法向的 `H(x,y)`；
- 输出点云、高度图、质量状态和机器可读结果；
- 对失败的匹配、尺度、平面或支持条件显式拒绝，不自动修正。

阶段出口：同一帧对可重复生成可审计结果；此出口不等于精度验收通过。

当前实现状态：request/result、decoded PTS 最近帧选择、帧周期同步质量门、canonical 图像输出以及既有 fixed-calibration pipeline 编排已经完成。HomeTank_004 的现有 10 Hz 粗同步不能通过帧级门，因此真实 WASS 样例在同步阶段停止；这不被伪装为 Phase 3 通过。

帧级精化状态：已使用全部 decoded-frame PTS 建立约 60 FPS 亮度序列，并分别拟合 static/wave 时钟关系。static 事件不足，wave 残差只达到 warning，故总体仍为 `FRAME_LEVEL_SYNC_NOT_ESTABLISHED`。保持下一阶段入口为“获得固定光源 ROI 的可验证事件证据，或换用硬件同步来源”。

工程容差状态：在不改变标定、WASS、平面或高度模型的条件下完成 static/wave 各 7 个右帧 offset。结果建立 `R0=ACCEPTED`、`±1=WARNING`、`|k|≥2=REJECTED` 的按需门，并已由 R0 完成两个正式后端样例。该门服务任务调度，不等同于严格同步或物理精度通过。

Phase 4 入口状态：正式 R0 的 raw/robust 高度分布、尾部、support edge、连通区域和 XYZ 关联已量化，并通过数组哈希冻结为独立验证基线。独立验证 workflow 已建立并强制单向依赖；cam1 的 Static 9.1 ± 1.0 mm 与 Wave 9.2 ± 2.0 mm 人工读数及“向上增大”方向已登记。当前为 `MANUAL_REFERENCE_LOCATION_REQUIRED`，等待用户在冻结 rectified cam1 参考图上点击两个水面线像素并填写像素不确定度。不得用后续标尺数据反向修改这组算法结果。

### 历史验证层 Phase 2-RV：采购前真实视频可行性门

该门位于理想仿真完成之后、专业设备采购之前，并与 Phase 2 的数据接入工作衔接；现作为已完成的历史真实输入验证层保留，不改变 Phase 3–6 主线顺序：

- 使用 iQOO Neo5S 作为 cam0/left、iQOO Z10 Turbo Plus 作为 cam1/right；
- 依次执行刚性纹理平面、静水、静态液位变化和人工波协议；
- 用公共闪光事件拟合文件时间轴偏移与漂移；
- 复用 WASS、坐标/尺度、网格、独立 `Z0`、`H`、QA 和可视化链；
- 只判断符号、趋势、结构和时间连续性是否合理，不以手机数据声明 1 cm 精度。

阶段出口：若真实视频链具有可解释结果，则进入专业相机采购；若阻塞，则保留失败阶段并修复通用接口问题，不添加手机专用核心算法。协议见 [真实视频验证域](real_video_validation/README.md)。

### Phase 4：高度计算与独立物理误差验证

目标是使用不参与解算的外部参考评价尺度和水面高度误差。

主要任务：

- 冻结重建输出后再登记标尺或其他独立参考；
- 使用人工标注位置查询冻结 pixel–XYZ/height 中已有观测，以局部中位数作验证读数并同时保留最近点、支持数和局部离散度；附近无观测时明确失败，不插值；
- 比较真实长度/高度与重建结果，报告 RMSE、MAE、偏差和最大误差；
- 禁止参考值进入 WASS、三角化、参考面或高度计算；
- 只有满足预注册门限才能声明精度目标通过。

阶段出口：形成独立、可追溯、无反馈泄漏的物理验收报告。

### Phase 5：结果展示软件

目标是以统一 JSON/点云/高度产品驱动最终软件：视频层加载左右视频；交互层提供播放、时间选择和暂停；计算层执行同步帧提取、标定加载、WASS、XYZ 和 Height；展示层提供三维表面、高度图、统计、QA 和导出。GUI 不与重建算法耦合，也不承诺实时处理。

### Phase 6：专业双目相机工程迁移

目标是接入专业相机、镜头、刚性基线和硬触发，采集带可靠时间对应的左右视频并复用 Phase 3–5 接口；重新完成标定、尺度、环境和独立物理验证。

### Extension：Wave video analysis

保留现有 wave、高度时间序列、长时批处理与性能模块，用于未来动态水面研究。视频同步是主产品选帧所需的时间映射边界，但其数值不进入 WASS、XYZ 或高度计算；连续 wave 分析仍为 Extension。Production mode 当前负责单帧结果保存、按需任务管理和软件接口，并保留未来批量能力。

标尺数据仅用于结果验证，不参与任何三维重建和高度计算流程。Ruler data is only used for independent validation and is not included in the reconstruction pipeline.

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
- Case 2 一维正弦规则波完成；原 +0.7853 rad 相位差已定位为世界/网格 x 原点相差 +0.10 m，显式对齐后相位误差为 -0.000111 rad，历史未对齐结果仍保留；
- G0--G3 四组规则波幅频组合全部通过，raw support 100%，高度 RMSE 为 0.739--1.131 mm；
- 原始不规则波 IRR-1 在自动标定阶段 FAIL/BLOCKED；冻结 AC-10D 适配后的 IRR-1A 通过，RMSE 2.368 mm、最大误差 8.732 mm，原失败不被覆盖；
- 工作距离 D1/D0/D2 分别为 FAIL/PASS/BLOCKED；固定 2.00 m 的基线 B1/B0/B2 全部 PASS；交叉点 XZ-1 `(B=0.25 m,Z=2.50 m)` PASS；
- **采购前核心理想仿真验证已完成。**现有部署证据只包含两个单因素切片和一个交叉点，不构成完整参数图或最优参数证明；
- **低成本真实视频第一轮闭环已完成，当前主线已调整为视频输入的按需单帧测量。**HomeTank_004 已完成视频采集、OpenCV 标定、固定参数 WASS、单帧静水平面和五帧 wave Extension；跨帧失败状态继续保留；
- HomeTank_002 的白底线格已完成补救尝试：半自动投影线格恢复在双相机多帧得到完整 9 x 6 / 54 点，故 `custom_planar_grid_recovery=PASS`；但仅 9 对完整视图、3 组独立姿态，且靶板部分姿态可见弯曲，单目/双目/极线质量均失败。K/D/R/T 已拒绝，状态仍为 `CALIBRATION_DATA_INSUFFICIENT`，未运行 WASS；
- 已将 HomeTank_002 教训固化为通用标定基础设施：录像前 Gate A 检查双侧 54/54 与画质，录像后 Gate B 基于图像几何去重独立姿态并检查位置/尺度/方向覆盖；
- HomeTank_003 已执行真实标定 Gate：0.5 s 全段抽样与一次 10 Hz 针对性补扫均得到 cam0 完整棋盘检测 0，故双侧候选和独立姿态均为 0；分类 `CALIBRATION_DATASET_INSUFFICIENT`、`approved_for_wass=false`，未求 K/D/R/T，static/wave 仅登记未处理；
- HomeTank_004 的 calibrated baseline 为 68.6847 mm，人工测量为 70.0000 mm，相差 1.3153 mm（1.879%）；人工值只作 physical sanity check，重建采用标定 `K/D/R/T`；
- HomeTank_004 已跑通 rectification、dense stereo、triangulation 和单帧静水面检测，但三帧静水基准不稳定，状态为 `STATIC_VALIDATION_FAIL`。disparity 范围与 SGBM uniqueness/block size 审计均未产生可批准的正式参数变更；
- 已确认 OpenCV XML、配置派生、xyzC 解码和 wassgridsurface 0.11.4 NetCDF 接口。

下一阶段按以下门控顺序推进：

- 视频播放器目标时间、同步帧提取、单帧结果 schema、质量门和展示接口冻结；
- 独立物理参考协议与误差报告冻结；
- 专业相机、镜头、硬触发、照明、安装与计算设备选型；
- 实机双目标定与同步验证；
- 静水、固定高度和人工规则波验证，并与独立物理参考比较；
- 真实环境单帧验证，重点处理反光、波纹、泡沫、纹理退化、振动与环境光；
- wave 视频、同步和长时运行仅在 Extension 中继续；
- 本地桌面软件工程化：设备配置、标定、WASS 编排、重建质检和数据导出；
- WASS 锁定 `v_1.5` 基线的独立构建复现；
- 工业相机实机接入与同步测量；
- 水槽静水和人工波实验；
- 1 cm 目标的实测达标声明。

桌面程序现在进入最终软件的 V0.x 原型期：当前支持视频输入结构和同步原型，后续逐步接入标定、WASS、`Z0/H`、三维/热图、点位波高、QA 与导出；它不是一次性的手机 GUI。

Case 0/1/2 分别是静水零场、固定非零高度和动态正弦规则波三级验证场景，并非三种波。连同 G0--G3、不规则波适配、距离/基线单因素及 B--Z 交叉点，它们已形成采购前核心理想仿真证据链。这些结果不等同于真实设备或真实水面验证，不能据此声称真实海面达到 1 cm。

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
- [采购前验证总表](validation/prepurchase_validation_matrix.md)
- [部署几何汇总](validation/deployment_geometry_summary.md)
- [阶段进展总结](progress/2026-08-13_2026-08-14_summary.md)
- [HomeTank_004 录制前软件准备](real_video_validation/final_mobile_capture_preparation.md)
- [HomeTank_004 静水验证总结](../experiments/real_video/HomeTank_004/static_validation_summary.md)
- [HomeTank_004 SGBM 参数审计](../experiments/real_video/HomeTank_004/wass_sgbm_matching_parameter_audit.md)
- [WASS 固定标定路径](wass/fixed_calibration_path.md)

维护要求：新进展必须回填到对应阶段和状态节点，禁止在文末追加彼此割裂的英文更新块。完整用户汇报 DOCX/Markdown 及大型原始/中间数据仅保存在本地，不进入 Git。
