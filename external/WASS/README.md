# WASS 外部依赖

WASS 是本项目的核心外部依赖，其主要上游仓库为：

<https://github.com/fbergama/wass>

源码分析与复现决策见 [`docs/wass/upstream_reference.md`](../../docs/wass/upstream_reference.md) 和 [`docs/wass/reproduction_plan.md`](../../docs/wass/reproduction_plan.md)。

## 管理规则

- 不将 WASS 源码复制或直接提交到本仓库。
- 不在本项目中修改 WASS 源码；需要变更时应在独立分支或 fork 中处理。
- 实验必须记录所用 WASS 的版本标签或提交哈希、构建环境和运行参数。
- 本目录默认忽略除本说明外的所有内容，可供本地检出或挂载 WASS。

## 当前复现基线

```text
WASS tag:          v_1.5
WASS commit:       59f1b1c46c41a7d0baf85fc2b21e062eaf552feb
incfg submodule:   baf309e2336421b015f6a400b0f058de1112c181
wassgridsurface:   0.11.4 (PyPI)
license:           GPL-3.0 / 源码头为 GPL-3.0-or-later
```

`v_1.5` 是调查时上游唯一可见 tag，但没有 GitHub Release；“作者正式稳定版”仍为 UNKNOWN。该组合只用于可重复复现，不表示已达到 1 cm 精度。

## 本地安装示例

在不纳入版本控制的前提下，可执行：

```bash
git clone https://github.com/fbergama/wass.git external/WASS/source
git -C external/WASS/source checkout v_1.5
git -C external/WASS/source submodule update --init
```

不要在当前 Windows 项目环境直接安装旧依赖。优先使用独立 Linux/Docker 环境做最小复现，并保存镜像、依赖和配置哈希。未经明确需要，不下载 WASS 测试数据或海上长序列。
