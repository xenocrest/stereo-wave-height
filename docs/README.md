# 文档索引

本索引按“项目汇报所需信息”组织仓库文档。建议首次阅读依次查看项目定位、系统路线、当前实现和验收边界。

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

当前仿真用于隔离并验证几何、符号、尺度、接口和数据谱系问题，不代表真实水面成像条件，也不代表 WASS 端到端重建已经完成。

## 5. WASS 复现与集成

- [上游基线与证据](wass/upstream_reference.md)；
- [源码与架构分析](wass/architecture_analysis.md)；
- [完整处理链分析](wass/pipeline_analysis.md)；
- [输入输出规范](wass/input_output_spec.md)；
- [集成架构](wass/wass_integration_architecture.md)；
- [参数映射](wass/wass_parameter_mapping.md)；
- [复现与实验室适配计划](wass/reproduction_plan.md)；
- [实验室尺度适配论证](wass/lab_scale_adaptation.md)；
- [静水参考集成](wass/static_water_reference_integration.md)；
- [1 cm 误差预算与验收条件](wass/one_cm_error_budget.md)。

## 6. 当前汇报边界

可以陈述：系统与数学定义已经建立；WASS 集成边界和输出适配已经设计并部分编码；理想虚拟双目与合成立体影像链已有自动化测试。

不能陈述：WASS 已在本机完整跑通；候选硬件已经定型；真实水槽实验已经完成；系统已达到 1 cm 实测精度。

