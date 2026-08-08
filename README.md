# stereo-wave-height

基于 WASS（Waves Acquisition Stereo System）框架，实现双目海浪像素级高度解算。

## 项目目标

本项目面向双目海浪影像，研究从相机标定、立体匹配、三维重建到水面高度定义与误差评估的完整方法。WASS 仅作为外部依赖使用，本仓库不修改或复制其源码。

## 目录结构

- `docs/`：项目设计、研究方向和数学模型文档。
- `src/`：本项目实现代码。
- `experiments/`：可复现实验脚本与轻量结果说明。
- `configs/`：相机、重建和实验配置模板。
- `tests/`：自动化测试。
- `external/WASS/`：WASS 外部依赖说明；不纳入其源码。

## WASS 依赖

WASS 上游仓库：<https://github.com/fbergama/wass>

依赖的具体版本应在 `external/WASS/README.md` 中锁定。原始视频、图像序列、点云及其他大型数据均不得提交到 Git。

## 当前状态

项目处于初始化阶段，现阶段重点是明确测量系统、数学模型、数据接口和可验证的误差指标。
