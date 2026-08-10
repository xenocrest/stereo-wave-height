# 实验元数据规范

## 1. 目的

每次仿真、静水、标定或动态波面运行都必须具有唯一 `experiment_id` 和冻结元数据。元数据描述数据从哪里来、如何处理、处于哪个坐标/时间系统，以及能否用于科学结论。未确认值使用 `null`，状态使用 `UNKNOWN/TODO`。

模板见 [`experiment_template.yaml`](../../configs/experiment/experiment_template.yaml)。

## 2. 标识与环境

| 字段 | 要求 |
|---|---|
| `experiment_id` | 全局唯一字符串；生成规则在实现前为 TODO |
| `experiment_type` | `simulation`、`calibration`、`static_water`、`dynamic_wave` 等枚举 |
| `environment` | 仿真/实验室/现场及位置；未知为 null |
| `created_at` | ISO 8601 时间并带时区 |
| `operator` | 人员或自动流程标识 |
| `parent_experiment_id` | 静水/动态或标定关联；无则 null |

## 3. Hardware

必须记录：

- 左右相机型号、序列号、角色、采购/候选状态；
- 镜头型号、焦距、光圈、对焦状态及来源；
- 光心基线 `baseline_m`（m）及测量不确定度；
- 工作距离 `working_distance_m`（m）及定义；
- 分辨率（px）、像元尺寸（µm/px）、像素格式和位深（bit）；
- 触发源、曝光语义和同步误差（ns）。

候选配置可引用 `configs/equipment/candidate_system.yaml`，但不得把 candidate 自动升级为 confirmed。当前基线、工作距离和实体同步误差均为 `UNKNOWN/TODO`。

## 4. Calibration

| 字段 | 单位/语义 |
|---|---|
| `calibration_id` | 唯一标识 |
| `intrinsic_left/right` | 文件路径、哈希、`K` 和畸变模型引用 |
| `extrinsic` | `R,T` 文件/记录及变换方向 |
| `length_unit` | 标定平移和尺度单位 |
| `reprojection_rmse_px` | px |
| `reprojection_max_px` | px |
| `calibration_target` | 靶标来源、尺寸、单位和不确定度 |
| `status` | `SIMULATION_NOMINAL`、`CALIBRATED` 或 `UNKNOWN` |

仿真图像中心主点和零畸变只能标为 simulation assumption；不能标为真实标定。

## 5. Software

必须记录：

- WASS tag、commit、构建环境和二进制哈希；
- `wassgridsurface` 版本；
- 本项目 Git commit；
- matcher、stereo、网格和项目配置文件路径及 SHA-256；
- 操作系统、容器镜像/依赖锁定标识；
- 命令或工作流标识，敏感凭据不得写入元数据。

## 6. Data

输入和输出均使用 manifest：

| 字段 | 含义 |
|---|---|
| `role` | raw input、normalized input、WASS output、height product、report 等 |
| `path` | 相对数据根目录路径 |
| `sha256` | 内容校验 |
| `size_bytes` | 字节数 |
| `format` | PNG、TIFF、CSV、NetCDF 等 |
| `schema_version` | 对应数据接口版本 |
| `source` | 相机、仿真模型、WASS 或项目后处理 |
| `status` | valid、invalid、UNKNOWN |

大型文件保存在外部数据存储，Git 只保存小型 manifest、配置和报告。

## 7. Validation

至少记录：

| 指标 | 单位 |
|---|---|
| `rmse` | m |
| `mae` | m |
| `maximum_absolute_error` | m |
| `coverage` | dimensionless ratio，范围 `[0,1]` |
| `hole_rate` | dimensionless ratio，范围 `[0,1]` |
| `static_plane_rmse` | m |
| `scale_error` | dimensionless ratio |
| `valid_point_count` | count |

每个指标同时记录 reference、ROI、样本数、mask 规则、阈值、是否通过和验收规范版本。没有真值/参考时数值保持 `null/UNKNOWN`，不能填零。

## 8. Provenance 与冻结

元数据在运行前冻结计划字段，运行后只追加结果字段。任何修改必须产生新版本并记录父版本、修改原因、时间和操作者。所有路径均相对于明确的数据根目录，所有单位采用本规范，不允许依赖文件名推断物理意义。
