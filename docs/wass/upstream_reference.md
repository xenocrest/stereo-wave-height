# WASS 上游、版本与许可证基线

调查日期：2026-08-08。

## 已确认结论

| 项目 | 结论 | 复现决策 | 来源 |
|---|---|---|---|
| 主要上游 | 官方项目页指向 `fbergama/wass` | 只从该仓库取源码，不复制到本项目 | [U1]、[U2] |
| 许可证 | 仓库为 GPL-3.0；`COPYING` 是 GPL v3，源码头声明 GPL v3 或更高版本 | 外部进程方式使用；分发时另做 GPL 合规审查 | [U3]、[U4] |
| 默认分支 | `master`；调查时 HEAD 为 `a554f46623703cc03e92ccfa7b7b4fc29f307027`（2026-08-07） | 不用移动分支作为复现锁定点 | [U1]、[U5] |
| 可见 tag | 只有 `v_1.5`，commit `59f1b1c46c41a7d0baf85fc2b21e062eaf552feb`（2019-05-21） | **核心流水线首选复现基线** | [U6]、[U7] |
| GitHub Release | 没有 GitHub Release | `v_1.5` 是唯一公开 tag；“作者正式稳定版”为 **UNKNOWN** | [U8] |
| 子模块 | `v_1.5` 锁定 `incfg` commit `baf309e2336421b015f6a400b0f058de1112c181` | 必须初始化并核验 SHA | [U9]、[U10] |
| 网格工具 | `wassgridsurface` PyPI 最新已发布版 `0.11.4`（2025-11-14，Python ≥3.9，Beta） | 首轮后处理锁定 `0.11.4` | [U11] |
| 网格开发版 | WASS `master/gridding` 源码声明 `0.13.1` | 只用于源码理解，不直接复现 | [U12] |
| 当前 CLI | `wasscli` 推荐 Prepare → Match → Autocalibrate → Stereo | 可后续评估；首轮按 v1.5 二进制接口 | [U13] |

## 锁定组合

```text
WASS tag:          v_1.5
WASS commit:       59f1b1c46c41a7d0baf85fc2b21e062eaf552feb
incfg submodule:   baf309e2336421b015f6a400b0f058de1112c181
wassgridsurface:   0.11.4 (PyPI)
```

这是一套可审计基线，不是厘米级性能背书。v1.5 Dockerfile 固定 Ubuntu 16.04、Node.js 8 和 OpenCV 3.4；当前是否能原样构建为 **UNKNOWN/TODO**。[U14]

## 原始目标与 1 cm 水槽目标的差异

论文把立体海浪成像典型波长范围描述为约 0.2–50 m；示例使用 2456×2048 的 5 MP 相机、2.5 m 基线、约 12.5 m 相机高度和 0.2 m 网格。[U15] 官方默认参数面向约 5 MP、离水面约 10 m 的海上装置。[U16]

- 水槽工作距离、基线、视场和视差区间更小，不能照搬默认 disparity/offset/window。
- 1 cm 目标比论文 0.2 m 网格细一个数量级以上；可达性取决于相机几何、亚像素视差误差、同步、纹理和标定。
- 自动外参只恢复到尺度；必须用实测基线恢复物理单位。[U15]
- 论文建议海上基线/距离比约 0.10，同时指出增大该比值改善深度量化但降低匹配一致性；水槽需重新做误差预算。[U15]
- 平面和点云过滤阈值在尺度恢复前后的单位必须实证，不能猜测。[U17]

## 来源

- [U1] [WASS repository](https://github.com/fbergama/wass)
- [U2] [WASS official page](https://sites.google.com/unive.it/wass/home)
- [U3] [v1.5 COPYING](https://github.com/fbergama/wass/blob/v_1.5/COPYING)
- [U4] [v1.5 wass_stereo source](https://github.com/fbergama/wass/blob/v_1.5/src/wass_stereo/wass_stereo.cpp)
- [U5] [master commits](https://github.com/fbergama/wass/commits/master/)
- [U6] [tags](https://github.com/fbergama/wass/tags)
- [U7] [v1.5 commit](https://github.com/fbergama/wass/commit/59f1b1c46c41a7d0baf85fc2b21e062eaf552feb)
- [U8] [releases](https://github.com/fbergama/wass/releases)
- [U9] [v1.5 `.gitmodules`](https://github.com/fbergama/wass/blob/v_1.5/.gitmodules)
- [U10] [incfg locked commit](https://github.com/fbergama/incfg/commit/baf309e2336421b015f6a400b0f058de1112c181)
- [U11] [wassgridsurface 0.11.4](https://pypi.org/project/wassgridsurface/0.11.4/)
- [U12] [gridding development source](https://github.com/fbergama/wass/tree/master/gridding)
- [U13] [wasscli](https://pypi.org/project/wasscli/)
- [U14] [v1.5 Dockerfile](https://github.com/fbergama/wass/blob/v_1.5/Dockerfile)
- [U15] [Bergamasco et al. 2017](https://www.dsi.unive.it/wass/papers/1-s2.0-S0098300417304302-main.pdf)
- [U16] [official stereo configuration](https://sites.google.com/unive.it/wass/software/wass/dense-stereo-configuration)
- [U17] [v1.5 stereo parameters](https://github.com/fbergama/wass/blob/v_1.5/src/wass_stereo/wass_stereo.cpp)
