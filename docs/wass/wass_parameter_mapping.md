# WASS 水槽参数映射

## 1. 使用方法

本表以 WASS `v_1.5` 源码默认配置为唯一基线。状态含义：**沿用作首轮基线**表示先保持上游默认值；**必须重设**表示物理尺度或水槽 ROI 改变后不能照搬；**UNKNOWN/TODO** 表示需要本机数据或运行验证；**不启用**表示不属于严格复现基线。

参数名和值来自 WASS `v_1.5` 源码及官方配置说明。[matcher 源码](https://github.com/fbergama/wass/blob/v_1.5/src/wass_match/wass_match.cpp)，[FeatureSet 源码](https://github.com/fbergama/wass/blob/v_1.5/src/wass_match/FeatureSet.cpp)，[stereo 源码](https://github.com/fbergama/wass/blob/v_1.5/src/wass_stereo/wass_stereo.cpp)，[官方配置](https://sites.google.com/unive.it/wass/software/wass/configuration)

## 2. 相机标定与稀疏匹配

| 类别/参数 | WASS `v_1.5` 默认/接口 | 本项目水槽设置 | 状态与依据 |
|---|---|---|---|
| 内参 | `intrinsics_00.xml`、`intrinsics_01.xml`，OpenCV YAML | 最终焦距、光圈、工作距离下分别标定 `K` 和畸变 | **必须重设** |
| 外参 | `wass_match` 初值；`wass_autocalibrate` 聚合 | 使用同步纹理帧运行原流程；安装改变后重做 | **必须重设** |
| 物理尺度 | 自动标定平移归一化；已知基线恢复尺度 | 实测光心基线，并以刚体长度交叉验证 | **必须重设** |
| `FEATURE_MIN_DISTANCE` | 10 px | 首轮 10 px；复核空间分布 | **沿用作首轮基线** |
| `FEATURE_HESSIAN_THRESHOLD` | `0.0001` | 首轮默认；固定验证集上评估特征数 | **UNKNOWN/TODO** |
| `FEATURE_N_OCTAVES` | 4 | 4 | **沿用作首轮基线** |
| `FEATURE_N_LAYERS` | 4 | 4 | **沿用作首轮基线** |
| `FEATURE_INIT_SAMPLES` | 1 | 1 | **沿用作首轮基线** |
| `NUM_FEATURES_PER_IMAGE` | 2000 | 首轮 2000；检查全视场覆盖 | **UNKNOWN/TODO** |
| `MATCHER_LAMBDA` | `1e-5` | 首轮默认 | **沿用作首轮基线** |
| `MATCHER_POPULATION_THRESHOLD` | 0.7 | 首轮默认，以保留率/极线残差评估 | **UNKNOWN/TODO** |
| `MATCHER_MIN_GROUP_SIZE` | 5 | 5 | **沿用作首轮基线** |
| `MATCHER_MAX_ROUNDS` | 20 | 20 | **沿用作首轮基线** |
| `MATCHER_MAX_EPI_DISTANCE` | 0.5 px | 首轮 0.5 px；证据支持时才调整 | **沿用作验收基线** |

内参格式和目录组织见 [input_output_spec.md](input_output_spec.md)。

## 3. Dense stereo 与三角化

| 参数 | WASS `v_1.5` 默认 | 水槽建议 | 状态/质量检查 |
|---|---:|---|---|
| `MIN_DISPARITY` | 1 px | 由 `d=f_pxB/Z` 在近/远水面加裕量计算 | **必须重设** |
| `MAX_DISPARITY` | 640 px | 同上；实现的数值约束需运行验证 | **必须重设** |
| `WINSIZE` | 13 px | 首轮默认；水面物理支持区约 `13Z/f_px` m | **UNKNOWN/TODO** |
| `DENSE_SCALE` | 1.0 | 1.0，保留原分辨率 | **沿用** |
| `DISPARITY_OFFSET` | 0 px | 首轮 0；校正后视差越界时先查几何 | **UNKNOWN/TODO**；源码称正值把右图右移，需目视验证符号 |
| `DISP_DILATE_STEPS` | 1 | 首轮默认 | **UNKNOWN/TODO** |
| `DISP_EROSION_STEPS` | 2 | 首轮默认 | **UNKNOWN/TODO** |
| `MEDIAN_FILTER_WSIZE` | 0 | 0 | **沿用**；启用会改变小尺度峰值 |
| `DENSE_P1_MULT` | 2 | 首轮默认 | **UNKNOWN/TODO** |
| `DENSE_P2_MULT` | 64 | 首轮默认 | **UNKNOWN/TODO**；过大会平滑波形 |
| `DENSE_UNIQUENESS_RATIO` | 1 | 首轮默认 | **UNKNOWN/TODO** |
| `DENSE_DISP12MAXDIFF` | -1 | 首轮默认 | **UNKNOWN/TODO**；先确认负值语义 |
| `DENSE_PREFILTER_CAP` | 60 | 首轮默认 | **UNKNOWN/TODO** |
| `DENSE_SPECKLE_RANGE` | 16 | 首轮默认 | **UNKNOWN/TODO** |
| `DENSE_SPECKLE_WINDOW_SIZE` | -70 | 首轮默认 | **UNKNOWN/TODO**；特殊负值语义需验证 |
| `DENSE_DISPARITY_BIGGEST_COMPONENT_THRESHOLD` | 0 | 首轮默认 | **UNKNOWN/TODO** |
| `TRIANG_MIN_ANGLE` | 20° | 按实际 `B/Z` 和源码角度定义重设 | **必须核验/很可能重设**；`B/Z=0.10` 时几何角约 5.71° |
| `TRIANG_*_MIN/MAX` | -1（禁用边界） | 水槽共同视场物理边界；坐标/单位先确认 | **必须重设或明确禁用** |

官方说明 dense 默认值针对约 5 MP、距海面约 10 m 的系统，水槽不能全部照搬。[官方 dense-stereo 配置](https://sites.google.com/unive.it/wass/software/wass/dense-stereo-configuration)

## 4. 平面、过滤和输出

| 参数/阶段 | WASS 默认 | 水槽建议 | 状态 |
|---|---:|---|---|
| `PLANE_RANSAC_ROUNDS` | 400 | 首轮默认；记录内点率和重复性 | **沿用作首轮基线** |
| `PLANE_RANSAC_THRESHOLD` | 1.0 | 先验证是在归一化还是已尺度空间 | **UNKNOWN/TODO，禁止直接按 1 m 解读** |
| `PLANE_REFINE_X/Y_MIN/MAX` | ±9999 | 必要时限制到可靠水面 ROI | **必须按场景评估** |
| `PLANE_MAX_DISTANCE` | 1.5 | 确认单位/尺度后按波高和异常点设置 | **必须重设或证明可沿用** |
| `ZGAP_PERCENTILE` | 99.0 | 首轮默认；检查是否删除真实峰谷 | **UNKNOWN/TODO** |
| `MIN_TRIANGULATED_POINTS` | 100 | 仅作运行最低条件，不作厘米级质量门槛 | **沿用运行门槛** |
| `SAVE_INPUT_SCALE` | 0.3 | 首轮默认；精确影响以源码确认 | **沿用作首轮基线** |
| `SAVE_FULL_MESH` | false | false；仅小样本诊断开启 | **沿用** |
| `SAVE_COMPRESSED` | true | true | **沿用** |
| `SAVE_AS_PLY` | false | false；仅小样本诊断开启 | **沿用** |
| `USE_CUSTOM_STEREORECTIFY` | false | false | **沿用** |
| `DISABLE_RECTIFY_ROI` | false | false；保存实际有效 ROI | **沿用** |
| 光流实验参数 | 实验性 | 不启用 | **不启用** |

## 5. `wassgridsurface` 映射

`wassgridsurface 0.11.4` 将重建输出插值到规则网格并可导出 NetCDF。[PyPI 0.11.4](https://pypi.org/project/wassgridsurface/0.11.4/)，[gridding 源码](https://github.com/fbergama/wass/blob/master/gridding/wassgridsurface/wassgridsurface.py)

| 内容 | 原始语境 | 本项目设置 | 状态 |
|---|---|---|---|
| 网格范围 | 由数据/参数定义 | 静水与动态序列的共同有效 ROI | **必须重设** |
| 网格分辨率 | 论文海上示例 0.2 m | 若最短波长为 `lambda_min` (m)，采样必要条件 `Delta_x,Delta_y≤lambda_min/2`；且不超出点密度支持 | **必须重设；lambda_min TODO** |
| 网格尺寸 | 海上尺度 | `N_x≈L_x/Delta_x`、`N_y≈L_y/Delta_y`，长度单位 m | **必须重设** |
| 平面拟合/去趋势 | WASS 坐标与 gridding 流程 | 仅用于坐标/静水参考，不得删除真实长波 | **必须验证** |
| 过滤 | 可选配置/后处理 | 阈值以 mm 和格点数记录并做敏感性分析 | **UNKNOWN/TODO** |

网格变细不会创造信息或自动提高高度精度。最终选值应联合报告点密度、空洞率、最短波长与 `H` 误差。

## 6. 最小调参顺序

1. 冻结成像、同步、内参和刚性安装；
2. 用几何公式设视差范围，核验 `TRIANG_MIN_ANGLE`；
3. 在刚体与静水小样本上调匹配/稠密参数；
4. 冻结重建后再选择网格和过滤；
5. 用未参与调参的序列执行 [one_cm_error_budget.md](one_cm_error_budget.md) 验收。

每次实验保存完整配置、WASS commit、环境与质量指标；不修改上游源码。
