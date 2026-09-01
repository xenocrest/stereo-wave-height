# Real-world robustness audit

本审计以 `a531ea204662d3a340a2a4a45e52c923ec8b8047` 为起点。目标不是把不可观测量包装成算法输出，而是使用所有物理有效信息、记录适配决策，并在信息不足时明确降级。

| 层次 | 已有假设或行为 | 分类 | 本轮处理 |
|---|---|---|---|
| A 输入 | canonical 方向、显式视频角色、用户 ROI | ROBUST_ALREADY | 保留；新增亮度、纹理、模糊、clipping、glare、公共视场和 ROI 风险诊断 |
| B 标定 | mono K/D 只使用 bilateral 子集；bilateral 中心需覆盖左右完整 3×3 | REAL_WORLD_RISK / ADAPTATION_POSSIBLE | 拆为 LEFT_MONO、RIGHT_MONO、STEREO_BILATERAL；stereo 仅覆盖实际 overlap，固定 mono K/D 求 R/T |
| C 同步 | PTS、仿射映射、exact/warning/reject | ROBUST_ALREADY | 增加 `sync_residual/frame_period`；阈值仍由既有 policy 决定 |
| D 校正 | ROI 和 vertical residual 已存在但偏全局 | ADAPTATION_POSSIBLE | 新增 held-out median/RMS/P95/max、normalized RMS 和 3×3 spatial residual |
| E 匹配 | frozen WASS 参数，低纹理和左右光度差可能失败 | DATA_LIMITED | 只建立 scene-aware profile 建议；未经 A/B 不切 production |
| F 三角化 | WASS 官方实现、metric baseline | ROBUST_ALREADY | 不修改；新增 finite/depth/support health 设计 |
| G 过滤 | largest component 可能删除被 glare/遮挡分开的真实水面 | REAL_WORLD_RISK | 保持默认；新增所有 component 的 count/image/XYZ extent 诊断，`KEEP_VALID_COMPONENTS` 为实验项 |
| H 参考面 | 点数和 RMS 可通过，但窄带支持仍可能病态 | ADAPTATION_POSSIBLE | 增加 3×3 occupancy、anisotropy、弱空间支持 warning；不改变单帧 GUI |
| I dense | local MLS、3×P90、UNSUPPORTED 已阻止无约束全域外推 | ROBUST_ALREADY | 明确 `ESTIMATED_LOCAL` 语义、scene-local multiplier 与 extrapolation rejection provenance |
| J QA | 多处分散 PASS/FAIL | REAL_WORLD_RISK | 增加统一分层 quality status/reasons；几何失败优先于点数 |
| K runtime | 显式外部 WASS/FFmpeg、offline package | ROBUST_ALREADY | 本轮不改、不打包 |

## 可适应与不可辨识边界

有限/不对称 FOV、mono 数据不平衡、中等曝光差、局部 blur、非均匀支持、轻度同步残差和不规则 ROI 可诊断并适配或降级。完全无纹理/纯镜面且无对应、严重失步、无公共视场、移动 rig 且无 pose、超远距离亚像素视差属于物理不可辨识或需要额外硬件；软件不得静默补出测量。

## 分级落地

- `READY_TO_INTEGRATE`：split calibration、FIX_INTRINSIC stereo、overlap QA、scene diagnostics、normalized sync metric、quality/adaptation manifest、reference support confidence、component diagnostics、dense provenance。
- `EXPERIMENTAL_NOT_PROMOTED`：CLAHE/mean-std normalization、LOW_TEXTURE/HIGH_GLARE matcher profiles、多 component 保留。
- `FUTURE`：multi-frame reference、rolling-shutter correction、ego-motion compensation、water segmentation、基于真实验证更新 completion multiplier。
