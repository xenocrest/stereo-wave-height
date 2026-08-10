# 三维重建与高度输出接口

## 1. 责任边界

WASS 负责图像准备、匹配、自动标定、稠密双目和三维重建；本项目不替代其核心算法。本项目负责：

- 读取并登记 WASS 原始输出；
- 验证/恢复物理尺度并转换到统一世界坐标；
- 构建规则网格 `Z(x,y,t)`；
- 由独立静水序列构建 `Z0(x,y)`；
- 计算 `H=Z-Z0`、质量掩膜和验收指标。

WASS 具体文件格式见 [WASS 输入输出规范](../wass/input_output_spec.md)。原始 WASS 单位、坐标或版本字段未验证时保持 `UNKNOWN/TODO`，不得直接标为 m 或世界高程。

## 2. 原始输出层

原始层按 WASS 版本原样保存并登记：点云/网格文件、投影矩阵、相机姿态、平面、日志、视差与质量图。至少记录：

- `wass_version`、commit 和配置哈希；
- 原始文件路径与 SHA-256；
- `source_coordinate_system`；
- `source_length_unit`；
- 物理尺度恢复方法与状态；
- 帧号和时间关联。

不得覆盖、重排或删除原始输出后再称其为 WASS 原始结果。

## 3. 标准点接口

完成尺度和坐标转换后，每个标准点至少具有：

| 字段 | 类型 | 单位 | 含义 |
|---|---|---|---|
| `frame_id` | string | — | 对应双目帧对 |
| `timestamp_ns` | int64 | ns | 有效曝光时间 |
| `time_reference` | string | — | 时间基准 |
| `point_id` | int/string | — | 帧内唯一标识 |
| `X` | float | m | 世界坐标 `Xw` |
| `Y` | float | m | 世界坐标 `Yw` |
| `Z` | float | m | 世界坐标 `Zw`，向上为正 |
| `valid` | boolean | — | 点是否有效 |
| `source_coordinate_system` | string | — | 原始 WASS 坐标标识 |
| `transform_id` | string | — | 原始到世界坐标的变换记录 |
| `quality` | structured | 各指标自带单位 | 重投影、匹配或过滤质量 |

无效点的 `X,Y,Z` 必须为 IEEE `NaN`，且 `valid=false`。不能用 `0`、极大值或静水高度代替无效点。

## 4. 规则网格接口

统一网格包含：

| 变量 | 数组形状 | 单位 | 含义 |
|---|---|---|---|
| `time` | `[T]` | s | 相对声明时间原点 |
| `timestamp_ns` | `[T]` | ns | 原始精确时间戳 |
| `x` | `[Nx]` | m | 世界 `Xw` 坐标 |
| `y` | `[Ny]` | m | 世界 `Yw` 坐标 |
| `Z` | `[T,Ny,Nx]` | m | 动态水面高程 |
| `valid_mask` | `[T,Ny,Nx]` | boolean | `true` 表示 `Z` 有效 |
| `Z0` | `[Ny,Nx]` | m | 静水平均参考 |
| `Z0_mask` | `[Ny,Nx]` | boolean | 静水参考有效性 |
| `H` | `[T,Ny,Nx]` | m | 相对静水高度 |
| `H_mask` | `[T,Ny,Nx]` | boolean | `valid_mask AND Z0_mask` |

数组维序固定为 `[time,y,x]`。所有 mask 为真时数值必须有限；mask 为假时对应浮点值必须为 `NaN`。

## 5. 静水与高度计算

静水参考和动态水面必须共享坐标、尺度、网格及兼容标定：

\[
H(x_i,y_j,t)=Z(x_i,y_j,t)-Z_0(x_i,y_j).
\]

`H,Z,Z0` 单位为 m。`H>0` 表示高于静水平均面。静水参考的样本数、标准差、时间范围、生成配置和质量掩膜必须随 `Z0` 保存。流程依据见 [静水参考集成](../wass/static_water_reference_integration.md)。

## 6. 坐标与尺度适配

从 WASS 坐标 `P_r` 到世界坐标 `P_w` 的变换必须通过 `transform_id` 引用，记录矩阵方向、单位和尺度来源。未经验证时：

- `scale_factor=null`；
- `source_length_unit=UNKNOWN`；
- 标准点/网格状态为 `not_physical_scale`；
- 禁止输出标称单位 m 的科学高度产品。

## 7. 质量字段

每帧至少报告点数、有效率、空洞率、坐标变换状态和 WASS 成功/失败状态。验证数据集还应报告 RMSE、MAE、最大绝对误差和覆盖率；指标公式与门槛引用 [仿真验收标准](../simulation/acceptance_criteria.md) 或对应真实实验的预注册标准。

## 8. 文件建议

轻量点表可使用带 schema 的 Parquet/CSV；规则网格可使用 NetCDF。具体编码器、压缩和缺失值元数据在实现前为 `UNKNOWN/TODO`。无论格式如何，字段名称、单位、维序、mask 和 provenance 不得省略。
