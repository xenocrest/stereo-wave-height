# WASS 原始输出与适配规范

## 1. 规范层次

本规范区分三层：

1. **WASS 原始文件**：由锁定 WASS/WASS gridder 直接产生，原样保存；
2. **解析记录**：适配器对已确认格式的字段映射，带来源和版本；
3. **项目标准输出**：转换到统一世界坐标和 m 后的点/网格接口。

第三层字段是本项目契约，不能反向声称为 WASS 原生字段。来源依据：[WASS pipeline 分析](../wass/pipeline_analysis.md)、[WASS 输入输出分析](../wass/input_output_spec.md) 和 [标准重建输出](reconstruction_output_spec.md)。

## 2. 已确认的 WASS 原始产物

| 原始产物 | 已确认用途 | 来源状态 |
|---|---|---|
| `mesh_cam.xyzC` | 压缩相机坐标点云，后处理首选之一 | WASS 文档/加载源码确认；内部量化和物理单位需实测核验 |
| `mesh_cam.xyzbin` | 非压缩 float32 相机坐标点云 | WASS `v_1.5` 源码确认 |
| `mesh.ply` | 可选调试点云 | WASS 文档/源码确认，不保证默认生成 |
| `P0cam.txt`,`P1cam.txt` | 投影矩阵 | WASS 源码确认 |
| `Cam*_poseR/T.txt` | 相机位姿 | WASS 文档/源码确认 |
| `plane.txt` | 单帧平面参数 | WASS 源码确认；物理尺度语义需核验 |
| `ext_R.xml`,`ext_T.xml`,`H.xml` | 外参与单应 | match/autocalibrate 源码确认 |
| `matcher_stats.csv` | 匹配数量/极线统计 | matcher 源码确认 |
| `wass_stereo_log.txt` | 点数、过滤和运行日志 | WASS 输出确认 |
| `gridded.nc` | `wassgridsurface` 网格输出 | gridder 确认；0.11.4 精确字段兼容性 UNKNOWN/TODO |

视差图和诊断 JPG/PNG 属于质量辅助产物，不作为标准高度接口。

## 3. 点云适配接口

WASS 原始点记录如何编码必须由对应版本解析器确认。适配完成且尺度/坐标闸门通过后，项目标准点为：

| 字段 | 类型 | 单位 | 来源 |
|---|---|---|---|
| `X,Y,Z` | float | m | WASS 点云经已记录尺度和坐标变换 |
| `timestamp_ns` | int64 | ns | 双目帧 manifest，不假设嵌入点云 |
| `frame_id` | string | — | WASS workdir 与输入帧映射 |
| `valid` | boolean | — | 解析、范围和变换状态 |
| `source_file` | path | — | 原始 WASS 点云 |
| `source_coordinate_system` | string | — | 通常为相机/重建坐标；具体值需确认 |
| `source_length_unit` | enum | — | 未确认时 `UNKNOWN` |
| `transform_id` | string/null | — | 到世界坐标的变换引用 |

`timestamp_ns` 是项目关联字段，不假定 WASS 原始每点含 timestamp。原始点云单位未核验时，`X,Y,Z` 只能保留源数值和 `source_length_unit=UNKNOWN`，不得标为 m。

## 4. 网格适配接口

开发版 gridder 源码显示可能包含 `Z`、`maskZ`、`X_grid/Y_grid`、`time`、`scale` 和 meta 组，但锁定的 `wassgridsurface 0.11.4` 是否完全一致为 `UNKNOWN/TODO`。首轮必须使用 `ncdump -h`、版本源码和已知尺度交叉验证。

通过验证后映射为：

| 字段 | 形状 | 单位 | 语义 |
|---|---|---|---|
| `Z` | `[T,Ny,Nx]` | m | 世界坐标动态高程 `Z(x,y,t)` |
| `x` | `[Nx]` | m | 世界 `Xw` 网格 |
| `y` | `[Ny]` | m | 世界 `Yw` 网格 |
| `timestamp_ns` | `[T]` | ns | 与输入 manifest 对齐 |
| `mask` | `[T,Ny,Nx]` | boolean | `true` 为有效 |

无效网格值使用 `NaN` 且 `mask=false`。数组维序由项目固定为 `[time,y,x]`；若原始 NetCDF 顺序不同，适配器必须显式转置并记录 mapping，不能按变量名猜测。

## 5. 必需元数据

每个适配输出必须包含：

| 元数据 | 要求 |
|---|---|
| `wass_version`,`wass_commit` | 锁定运行版本 |
| `wass_binary_sha256` | 实际二进制哈希 |
| `configuration_sha256` | matcher/stereo/grid 配置哈希 |
| `calibration_id` | 输入标定引用 |
| `coordinate_system_id` | 当前输出坐标系 |
| `source_coordinate_system` | 原始 WASS 坐标语义 |
| `source_length_unit` | m/mm/normalized/UNKNOWN |
| `scale_factor`,`scale_source` | 未恢复时 `null/UNKNOWN` |
| `transform_id` | 到世界坐标的变换；未定义时 null |
| `frame_id`,`timestamp_ns`,`time_reference` | 输入帧和时间关联 |
| `parser_version` | 解析器/schema 版本 |
| `source_sha256` | 原始文件哈希 |

## 6. UNKNOWN 处理

- 不确认字段名：不解析，并登记 `unsupported_or_unknown_field`；
- 不确认单位：保留原数值但禁止物理高度输出；
- 不确认坐标方向：禁止转换为 `Xw,Yw,Zw`；
- 不确认版本差异：保存原始头信息并停止该适配路径；
- 不确认时间：`timestamp_ns=null`，该帧不得进入动态高度序列。

未知内容不使用零、单位阵、文件顺序或经验常数替代。

## 7. 与高度链的边界

本规范只把 WASS 结果转换成标准点云或 `Z(x,y,t)`。`Z0`、`H` 和验证指标不是 WASS 原始输出，由 [高度解算管线](../mathematical_model/height_reconstruction_pipeline.md) 负责。
