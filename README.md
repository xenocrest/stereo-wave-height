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

## 当前进展

已完成：

- 测量系统、坐标体系、数据接口和数学模型设计；
- WASS 上游版本、架构、处理链、输入输出与参数映射分析；
- WASS 输出适配、坐标变换、静水参考、高度计算和误差指标核心代码；
- 虚拟双目相机、水面真值模型及可复现合成立体影像生成；
- WASS 输入工作区适配、外部进程 runner 和显式 NetCDF 映射 parser 边界；
- 本机 WASS 四阶段 Case 0 静水仿真核心重建成功并生成尺度已核验的 `mesh_cam.xyzC`；
- 43 项自动化测试，覆盖后处理、虚拟双目、合成影像、WASS 输入和运行时/输出格式。

尚未完成：

- `wassgridsurface/gridded.nc` 接入及 Case 0 规则网格高度产品；
- WASS 锁定 `v_1.5` 基线的独立复现（当前成功运行的是本机 `1.11` 构建）；
- 工业相机实机接入、同步与标定；
- 水槽静水/人工波实验及独立参考对比；
- 1 cm 目标的实测验收。

Case 0 已通过本机 WASS 的 prepare、match、autocalibrate 和 stereo，结果与限制见 [Case 0 静水验证](docs/validation/case0_static_water.md)。规则网格 H 仍等待 `wassgridsurface/gridded.nc`；该仿真结果不等同于真实设备或真实水面的精度验证。

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
