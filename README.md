# stereo-wave-height

基于 WASS（Waves Acquisition Stereo System）的双目水面三维重建与高度场解算研究项目。项目以同步双目影像为输入，将 WASS 重建结果转换为统一坐标系中的水面高程，并以独立静水参考计算相对高度：

```text
同步双目影像
  → WASS 三维重建 Z(x, y, t)
  → 坐标、尺度与质量字段适配
  → 静水参考 Z0(x, y)
  → 高度场 H(x, y, t) = Z(x, y, t) - Z0(x, y)
  → 误差指标与验收报告
```

近期研究目标是在实验室人工波条件下验证厘米级高度解算。这里的“1 cm 级”是待实验验证的验收目标，并非当前已经达到的性能声明。

项目路线、模型体系、Case 0/1/2 结果、结论边界和下一步工作的长期汇报入口见 [项目宏观汇报](PROJECT_OVERVIEW.md)。

## 核心建模成果

老师/首次访问者可先查看 [核心建模成果总览](docs/MODEL_OVERVIEW.md)。其中集中说明并链接了当前已经建立的三类核心模型：

- [双目几何模型](docs/mathematical_model/stereo_reconstruction_model.md)：理想平行双目关系 $Z=f_{px}B/d$、坐标/单位和当前设备参数绑定；
- [水面高度模型](docs/mathematical_model/height_field_model.md)：最终高度定义 $H(x,y,t)=Z(x,y,t)-Z_0(x,y)$，以及静水参考和坐标一致性要求；
- [虚拟相机模型](docs/simulation/virtual_camera_model.md)：基于 MER2-503-36U3C、2448×2048、$3.45\ \mu\mathrm{m/px}$ 和 8 mm 候选镜头建立 `SIMULATION_NOMINAL` 针孔双目模型。

上述文档均明确区分 candidate / simulation assumption / UNKNOWN 与真实标定参数，避免把仿真参数误写成实测值。

## 当前进展

已完成：

- 虚拟双目相机理想几何可信性验证：投影、视差和整面三角化闭环达到机器精度，
  shared physical texture 已确认；该结论不等同于真实相机成像验证；

- 测量系统、坐标体系、数据接口和数学模型设计；
- WASS 上游版本、架构、处理链、输入输出与参数映射分析；
- WASS 输出适配、坐标变换、静水参考、高度计算和误差指标核心代码；
- 虚拟双目相机、水面真值模型及可复现合成立体影像生成；
- WASS 输入工作区适配、外部进程 runner 和显式 NetCDF 映射 parser 边界；
- Case 0 已通过 WASS 核心、官方 `wassgridsurface 0.11.4` 和规则网格高度闭环；
- Case 1 的 +10 mm 固定非零高度场景已通过：`ZGAP_PERCENTILE=99.5` 时 raw support 为 100%，H RMSE 约 1.03 mm、MAE 约 0.916 mm、最大误差约 1.65 mm；该参数仅冻结于当前理想仿真几何；
- Case 1 重复性验证完成：WASS `xyzC` 三轮逐帧 bitwise identical；gridder 文件哈希不同，但最大跨运行 Z 差异仅 0.020553 mm，分类为 B（Numerically deterministic）；
- Case 2 单组一维正弦规则波已完成双目输入至高度场闭环：raw support 100%，高度 RMSE 5.3968 mm 并通过冻结门限；包裹相位误差 +0.7853 rad（约 45°）仍是未解决诊断项；
- Case 1 的原始 default-99 运行平均符号/偏差正确，但 RMSE 和最大误差未通过预注册门槛；该历史结果不被后续适配覆盖；
- Case 1 分层诊断确认：xyzC 平面差为 8.999 mm；升高帧原始点仅支持
  51.45% 网格单元，无支持 DCT 单元贡献超过 98% 平方误差；
- 支持损失已定位到 WASS 三角化后的 Z-gap 最大连通分量阶段（单步丢失
  58.57%）；已定义 raw observation support mask，支持域诊断 RMSE 为 1.279 mm；
- Z-gap 断带呈纵向条带；当前发布构建不保存 pre-cluster 浮点深度、阈值和
  完整组件标签，机制归因标记为 `OBSERVABILITY_LIMITATION`；
- 自动化测试覆盖后处理、仿真、WASS 接口、官方 NetCDF、Case 1 帧选择和误差诊断。

尚未完成：

- Case 2 相位、坐标原点与时间零点对齐诊断；
- `baseline × scene distance` 部署参数空间验证；
- WASS 锁定 `v_1.5` 基线的独立复现（当前成功运行的是本机 `1.11` 构建）；
- 工业相机实机接入、同步与标定；
- 水槽静水/人工波实验及独立参考对比；
- 1 cm 目标的实测验收。

Case 0/1/2 是静水零场、固定非零高度和动态正弦规则波三个逐级验证场景，并非三种“波”。三级理想仿真已形成软件全链路闭环；详细结果见 [项目宏观汇报](PROJECT_OVERVIEW.md)。这不代表真实相机、水槽或海面已达到 1 cm：真实标定、同步、畸变、噪声、反光和振动等仍待验证。

## 仓库结构

- `docs/`：项目计划、系统设计、数学模型、数据规范、仿真方案和 WASS 集成分析；
- `src/`：本项目自有的仿真、适配、静水参考、高度解算与指标代码；
- `configs/`：候选设备、仿真和实验配置模板；
- `tests/`：自动化测试；
- `experiments/`：预留的可复现实验入口，目前不包含实验结果；
- `external/WASS/`：WASS 外部依赖元数据，不包含 WASS 源码。

完整导航见 [文档索引](docs/README.md)，总体阶段安排见 [项目计划](docs/PROJECT_PLAN.md)。

## 快速验证

项目当前依赖 Python 3、NumPy 和 Pillow。仓库采用 `src/` 与顶层兼容导入并存的早期结构；在仓库根目录可按下列方式运行现有测试：

```powershell
$env:PYTHONPATH = "$PWD;$PWD\src"
python -m unittest discover -s tests -v
```

## WASS 依赖边界

WASS 上游仓库：<https://github.com/fbergama/wass>

- 本仓库不修改、复制或重新发布 WASS 源码；
- 锁定基线与本地检出方式见 [`external/WASS/README.md`](external/WASS/README.md)；
- WASS 本地检出、构建产物、原始视频、图像序列、点云和其他大型数据均不提交到 Git；
- 未经真实 WASS 输出和独立参考验证，不作实测精度声明。

## 项目原则

1. 优先严格复现 WASS，不自行替代其核心立体匹配与三维重建。
2. 理论可行性、合成验证和真实实验结论明确分层。
3. 坐标、单位、配置、软件版本和数据来源可追溯。
4. 未确认参数保留 `UNKNOWN/TODO`，不以假设冒充实测数据。
## Latest validation status (2026-08-13)

The pre-purchase controlled regular-wave matrix is complete. Four ideal
synthetic groups spanning 10--30 mm amplitude and 0.5--1.0 Hz all passed the
frozen height/support gates through real WASS and official wassgridsurface.
This is software-chain evidence only, not a real-device 1 cm claim. See the
[comparison report](docs/validation/sinusoidal_wave_parameter_comparison.md)
and [validation matrix](docs/validation/prepurchase_validation_matrix.md).
