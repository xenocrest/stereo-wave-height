# 文档索引

本索引按“项目汇报所需信息”组织仓库文档。建议首次阅读依次查看核心建模成果、系统路线、当前验证结果和验收边界。

## 0. 核心建模成果（汇报入口）

如果需要快速核对汇报中提到的“**双目几何模型、水面高度模型、虚拟相机模型**”，请先查看：

- [核心建模成果总览](MODEL_OVERVIEW.md)：集中说明三类模型的公式、参数来源、用途和当前状态；
- [双目几何模型](mathematical_model/stereo_reconstruction_model.md)：$Z=f_{px}B/d$、双目坐标/单位和设备参数绑定；
- [水面高度模型](mathematical_model/height_field_model.md)：$H(x,y,t)=Z(x,y,t)-Z_0(x,y)$、静水参考和统一坐标要求；
- [虚拟相机模型](simulation/virtual_camera_model.md)：基于候选设备参数建立的 `SIMULATION_NOMINAL` 针孔双目模型。

这些文档是当前汇报中“已完成建模”的直接证据入口。

## 1. 项目定位与计划

- [项目概述](project_overview.md)：目标、范围和预期产出；
- [项目计划](PROJECT_PLAN.md)：阶段路线、项目原则和当前状态；
- [研究方向](research_direction.md)：核心研究问题和近期路线。

## 2. 系统与数据流

- [双目测波系统总体设计](system/stereo_measurement_system_design.md)：端到端系统架构；
- [数据流设计](system/data_flow_design.md)：各阶段输入输出、单位闸门与数据谱系；
- [统一坐标与时间体系](data_model/coordinate_system.md)：图像、相机、世界和规则网格坐标定义；
- [双目图像数据集规范](data_model/stereo_image_dataset_spec.md)；
- [WASS 原始输出与适配规范](data_model/wass_output_spec.md)；
- [三维重建与高度输出接口](data_model/reconstruction_output_spec.md)；
- [实验元数据规范](data_model/experiment_metadata_spec.md)。

## 3. 数学模型与误差

- [相机几何模型](mathematical_model/camera_geometry_model.md)；
- [部署几何模型](mathematical_model/deployment_geometry_model.md)；
- [双目重建模型](mathematical_model/stereo_reconstruction_model.md)；
- [水面模型](mathematical_model/water_surface_model.md)与[高度场模型](mathematical_model/height_field_model.md)；
- [高度定义](mathematical_model/height_definition.md)；
- [WASS 输出后的高度解算管线](mathematical_model/height_reconstruction_pipeline.md)；
- [误差传播模型](mathematical_model/error_propagation_model.md)与[误差分析](mathematical_model/error_analysis.md)。

## 4. 无实体设备仿真

- [仿真验证计划](simulation/simulation_validation_plan.md)；
- [验收标准](simulation/acceptance_criteria.md)；
- [虚拟相机模型](simulation/virtual_camera_model.md)；
- [合成水面模型](simulation/synthetic_surface_models.md)；
- [合成立体影像生成](simulation/synthetic_image_generation.md)。

当前仿真用于隔离并验证几何、符号、尺度、接口和数据谱系问题。它在数学几何关系上绑定候选设备参数，但不等同于真实水面成像；真实反射、光照变化、相机抖动和真实传感器噪声尚未纳入。

## 5. WASS 复现与集成

- [上游基线与证据](wass/upstream_reference.md)；
- [源码与架构分析](wass/architecture_analysis.md)；
- [完整处理链分析](wass/pipeline_analysis.md)；
- [输入输出规范](wass/input_output_spec.md)；
- [集成架构](wass/wass_integration_architecture.md)；
- [参数映射](wass/wass_parameter_mapping.md)；
- [本机运行时绑定](wass/local_runtime_binding.md)；
- [端到端验证记录](wass/end_to_end_validation.md)；
- [官方 wassgridsurface 集成](wass/wassgridsurface_integration.md)；
- [静水参考集成](wass/static_water_reference_integration.md)；
- [1 cm 误差预算与验收条件](wass/one_cm_error_budget.md)。

## 6. 当前验证结果

- [Case 0 静水验证](validation/case0_static_water.md)：已完成虚拟双目 → WASS → 官方网格化 → `Z0` → `H` 的正式闭环；
- [Case 1 固定高度验证](validation/case1_constant_height.md)：+0.010 m 非零高度端到端运行完成，但未通过预注册 RMSE / 最大误差门限；
- [Case 1 误差根因诊断](validation/case1_error_diagnosis.md)：定位全网格误差主要来自无原始支持区域上的 DCT 全域重建；
- [Case 1 支持追踪](validation/case1_support_trace.md)：支持损失已定位到 WASS 三角化后的 Z-gap 最大连通分量阶段。

## 7. 当前汇报边界

可以陈述：

- 双目几何模型、水面高度模型、虚拟相机模型已经建立并文档化；
- 基于候选设备参数的虚拟双目图像链已经实现；
- 本机 WASS 核心与官方 `wassgridsurface 0.11.4` 已实际跑通；
- Case 0 已正式闭环；Case 1 已完成端到端运行并开展误差根因分析。

不能陈述：

- 候选硬件已经最终定型或采购；
- 真实水槽/真实海浪实验已经完成；
- 系统已经达到 1 cm 实测精度；
- Case 1 已通过验收（当前尚未通过）。
