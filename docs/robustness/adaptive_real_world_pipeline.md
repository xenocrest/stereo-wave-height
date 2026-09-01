# Adaptive real-world stereo pipeline

## 已集成架构

标定数据被拆成三个不必相同的集合：LEFT 完整检测用于 `K0/D0`，RIGHT 完整检测用于 `K1/D1`，同步 bilateral overlap 子集只用于固定 K/D 的 `R/T`。旧 bilateral-only 路径保留作为 comparison，不再是首选工程模型。

单帧输入在 WASS 前生成 scene diagnostics；它只记录亮度、对比度、clipping、glare proxy、texture、blur、左右差异、common-FOV/ROI、normalized sync、motion/rolling-shutter 风险。当前 frozen WASS matcher 不自动改变。建议 profile 和光度归一化写入 adaptation manifest，但均为 `EXPERIMENTAL_NOT_PROMOTED`。

输出质量采用 `VALID`、`VALID_WITH_WARNING`、`INSUFFICIENT_SUPPORT`、`GEOMETRY_UNRELIABLE`、`CALIBRATION_UNRELIABLE`、`SYNC_UNRELIABLE`、`REFERENCE_UNRELIABLE`、`PHOTOMETRIC_RISK`、`TEXTURE_LIMITED`、`UNSUPPORTED`。自动决策与警告均进入 `adaptation_manifest`。

## HomeTank_004 calibration-only A/B

既有 artifacts 含 LEFT 233、RIGHT 328 个完整检测与 192 个 bilateral pair，即至少 41 个 LEFT 和 136 个 RIGHT 完整单侧检测未被 bilateral-only mono 流程使用。独立 mono 的全图 3×3 occupancy 都只有 3/9；stereo 在自身观测 overlap 归一化后为 6/9，因此旧数据的主要问题仍是 mono sensor coverage，不是要求 stereo 覆盖两幅完整图像。

| 指标 | OLD bilateral-only | NEW split mono/FIX_INTRINSIC |
|---|---:|---:|
| LEFT mono RMS (px) | 4.3805 | 4.2264 |
| RIGHT mono RMS (px) | 4.5253 | 5.8452 |
| stereo RMS (px) | 7.9224 | 8.8060 |
| epipolar RMS (px) | 9.5084 | 11.4397 |
| held-out vertical median/RMS/P95/max (px) | 20.3907 / 39.4829 / 83.1450 / 151.3597 | 82.9336 / 165.9011 / 350.3399 / 868.5747 |
| baseline (m) | 0.0686847 | 0.0729656 |

第二次 deterministic resample 得到 LEFT/RIGHT mono RMS 4.2768/5.6560 px、stereo RMS 7.7784 px、epipolar RMS 9.7507 px、baseline 0.0749580 m；两次 split run 的 focal relative range 1.084%、principal normalized range 2.901%、baseline relative range 2.694%。简单 magnitude plausibility 未触发，但 held-out spatial rectification 明显失败，不能 promotion。

结论为 `OLD_VIDEO_STILL_INSUFFICIENT`。新模型修正了信息来源和不现实 capture gate，却不会创造旧视频缺失的 sensor-edge 信息；后续新视频仍有必要。WASS execution 为 0，calibration experiment 为 2。

## 后续边界

- Matcher profiles、photometric normalization、多 component retention：需要真实/合成 deterministic A/B，当前不启用。
- Multi-frame reference：schema 已预留，GUI 仍保持 single-frame reference。
- Moving rig：必须估计 ego-motion 或使用 IMU/pose。
- Rolling shutter：当前只诊断；专业 global-shutter 硬同步系统优先。
