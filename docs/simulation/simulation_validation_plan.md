# 无实体设备双目测波仿真验证计划

## 1. 目标与非目标

目标是在无实体设备条件下验证：解析水面、针孔投影、合成双目输入、WASS 标准重建、静水参考和高度评价之间的数学及软件接口是否自洽。

本轮只完成设计、配置模板和验收定义；不大量编码、不生成图像/视频/大型数据、不修改 WASS、不选择最终基线，也不声明真实水面达到 1 cm。

## 2. 完整仿真链

```text
解析 H_true(x,y,t) 与 Z0,true(x,y)
  → 世界水面 Z_true=Z0,true+H_true
  → 左右虚拟针孔相机投影与可见性
  → 同一数学纹理生成合成左右灰度图
  → WASS 可接受的帧对、名义内参、零畸变和配置
  → wass_prepare
  → wass_match
  → wass_autocalibrate
  → wass_stereo
  → wassgridsurface / 统一世界网格
  → Z_calc(x,y,t)
  → 独立 Case 0 静水序列形成 Z0,calc(x,y)
  → H_calc=Z_calc-Z0,calc
  → 在共同有效 ROI 与 H_true 比较
```

真值水面见 [synthetic_surface_models.md](synthetic_surface_models.md)，相机见 [virtual_camera_model.md](virtual_camera_model.md)，指标见 [acceptance_criteria.md](acceptance_criteria.md)。

## 3. 两条验证路径

### 3.1 几何单元测试

项目生成三维点、左右解析投影和真值对应，使用项目数学关系检查投影、视差—深度、单位与坐标符号。该路径不评价 WASS，也不能作为项目最终重建结果。输出必须标记 `geometry_unit`。

### 3.2 WASS 端到端验证

项目只生成：

- 左右合成 8-bit 灰度 PNG；
- 帧号、时间和配对清单；
- `SIMULATION_NOMINAL` 内参与理想零畸变文件；
- WASS matcher/stereo 配置；
- 每次扫描的已知仿真基线，用于 WASS 输出的物理尺度恢复。

WASS 必须执行 prepare、match、autocalibrate 和 stereo；规则网格由锁定的 `wassgridsurface` 处理。真值视差、真值点云、`H_true` 不进入 WASS input/confdir/workdir。评价程序只在 WASS 完成后读取 truth 和计算结果。

仿真中的已知 `B` 是单次扫描真值，不代表最终实体基线。WASS 接口依据见 [输入输出规范](../wass/input_output_spec.md)。

## 4. 四级场景执行顺序

1. **Case 0 静水平面**：建立 `Z0,calc`，检查零面、尺度、坐标和数值误差；
2. **Case 1 固定高度平面**：分别使用正负 `Delta H`，检查绝对尺度与符号；
3. **Case 2 一维正弦波**：检查振幅、空间起伏、相位传播和时间序列；
4. **Case 3 二维规则波**：用两个非平行解析分量检查完整二维高度场。

前一 Case 未通过时不得以后一 Case 的局部成功掩盖失败。本阶段不加入复杂海谱、破碎波、折射或真实反光。

## 5. B/Z 部署参数扫描

基线 `B`（m）和工作距离 `Z`（m）均从 [`baseline_template.yaml`](../../configs/simulation/baseline_template.yaml) 读取；模板值为 `null`，待每次研究前预注册扫描集合。本计划不选择最终数值。

每个 `(B,Z)` 点计算：

$
d=\frac{f_{px}B}{Z},
$

$
\left|\frac{\partial Z}{\partial d}\right|=\frac{Z^2}{f_{px}B},
$

$
\sigma_{d,max}^{(1cm)}=\frac{0.01f_{px}B}{Z^2}.
$

`d`、`f_px`、允许视差标准误差 `sigma_d,max` 单位 px；`B,Z` 为 m；深度敏感度为 m/px。最后一式把全部 0.01 m 分配给视差项，只是理论上限，完整系统还需为标定、尺度、静水、同步和网格误差留预算。

同时报告理想公共视场、真值可见比例、WASS 有效比例和空洞率。参数选择必须联合考虑视差范围、公共视场与三角化质量，而不是只优化一个公式。

## 6. 数据与目录边界

建议运行时目录（全部由 `.gitignore` 排除的大型内容）为：

```text
run_<id>/
├── truth/          # H_true、Z_true、解析对应；WASS 不可读
├── input/cam0/     # 合成左图
├── input/cam1/     # 合成右图
├── config/         # 名义内参、零畸变、WASS 配置
├── work/           # WASS 工作目录
├── calculated/     # Z_calc、Z0,calc、H_calc
└── report/         # 小型指标、配置哈希和清单
```

仓库只提交配置模板、轻量指标模式和文档，不提交运行图像、点云、网格或 NetCDF。

## 7. 建议软件模块边界（仅设计）

| 建议模块 | 职责 | 禁止事项 |
|---|---|---|
| `src/simulation/surface_truth` | 解析 Case 0–3 与真值清单 | 不生成无公式的视觉波面 |
| `src/simulation/camera_projection` | 针孔投影、射线、水面交点和可见性 | 不实现立体匹配 |
| `src/simulation/stereo_scene` | 统一纹理、左右渲染、帧组织 | 不读取 WASS 结果调真值 |
| `src/adapters/wass_input` | 转换为 WASS 文件/配置边界 | 不改 WASS 源码 |
| `src/height/static_reference` | 由独立静水重建构造 `Z0,calc` | 不用真值替代重建静水面 |
| `src/height/height_field` | 计算 `H_calc=Z_calc-Z0,calc` | 不替代 WASS 三维重建 |
| `src/validation/metrics` | RMSE、MAE、max、有效率和空洞率 | 不事后选择 ROI |
| `src/validation/geometry_checks` | 几何单元测试与坐标检查 | 不把单元测试冒充端到端结果 |

本轮不创建这些代码目录，避免把接口设计误写成已实现功能。

## 8. 预先设计的测试

| 测试 | 输入 | 核心断言 |
|---|---|---|
| pinhole projection consistency | 解析三维点与 `K_sim` | 投影/反投影在数值阈值内一致 |
| disparity-depth consistency | 配置 `B,Z,f_px` | `d=f_pxB/Z` 与反算深度一致 |
| static-water zero test | Case 0 | `H_calc` 静水平面 RMSE 达标 |
| known-height sign test | 正负 Case 1 | 尺度和高度符号正确 |
| sinusoidal-wave reconstruction | Case 2 | RMSE、振幅和传播方向达标 |
| two-dimensional direction test | Case 3 | 两个非平行波矢方向正确 |
| unit consistency test | mm、µm、px、m 输入 | 单位换算和输出量纲正确 |
| config parameter provenance test | YAML 与设备登记表 | 每个数值有 source/status/unit，UNKNOWN 为 null |
| truth isolation test | 运行目录权限/清单 | WASS 输入不含 truth disparity/point cloud/height |

## 9. 实施闸门

只有文档审查通过、B/Z 扫描集合和场景参数预注册、WASS 环境复现完成后，才开始最小实现。每级 Case 先运行几何单元测试，再运行 WASS 端到端；全部指标按 [验收标准](acceptance_criteria.md) 报告。
