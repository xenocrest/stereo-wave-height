# Real-world sea-surface risks

标签含义：`DETECTABLE` 可从输入或输出识别；`ADAPTABLE` 可采取可审计策略；`QA_ONLY` 只能警告/拒绝；`REQUIRES_HARDWARE` 需要额外硬件；`PHYSICALLY_LIMITED` 缺少可恢复信息。

| 风险 | 分类 | 当前处理边界 |
|---|---|---|
| Low texture | DETECTABLE / QA_ONLY / PHYSICALLY_LIMITED | gradient/local texture 识别；不可把 flat-patch 高相关当真值 |
| Repetitive capillary patterns | DETECTABLE / QA_ONLY | 需要 uniqueness、LR consistency 等 WASS 可观测量；当前 profile 仅实验性 |
| Specular reflection | DETECTABLE / QA_ONLY / PHYSICALLY_LIMITED | highlight proxy；无稳定对应处必须 unsupported |
| Sun glitter | DETECTABLE / ADAPTABLE / QA_ONLY | clipping/glare map；保守光度归一化需 A/B |
| Whitecaps / breaking waves | DETECTABLE / QA_ONLY | 多 component 合法性诊断；不能强制平面 |
| Foam | DETECTABLE / ADAPTABLE | 纹理可能增强也可能重复，按 confidence 处理 |
| Moving shadows | DETECTABLE / ADAPTABLE | 左右光度差与时间变化诊断 |
| Camera vibration | DETECTABLE / QA_ONLY | global-motion proxy；固定参考面可能失效 |
| Platform motion | REQUIRES_HARDWARE / PHYSICALLY_LIMITED | 需要 ego-motion 或 IMU/pose |
| Rolling shutter | DETECTABLE / QA_ONLY / REQUIRES_HARDWARE | metadata+motion 风险；本轮不校正 |
| Long-range small disparity | DETECTABLE / PHYSICALLY_LIMITED | geometry-informed disparity/error budget；受像素分辨率限制 |
| Atmospheric haze | DETECTABLE / QA_ONLY | contrast/texture 下降可见，无法恢复消失的对应 |
| Spray/droplets on lens | DETECTABLE / QA_ONLY | 局部强边/模糊/遮挡风险；需清洁或防护 |
| Partial occlusion | DETECTABLE / ADAPTABLE | support/component map；遮挡区 unsupported |
| Different exposure | DETECTABLE / ADAPTABLE | brightness/contrast mismatch；归一化需 deterministic A/B |
| Autofocus changes | DETECTABLE / QA_ONLY | sharpness及 calibration identity 风险；需锁焦或重标定 |
| Non-synchronous cameras | DETECTABLE / ADAPTABLE / QA_ONLY | PTS normalized residual；严重时拒绝 |
| Limited overlap | DETECTABLE / ADAPTABLE / PHYSICALLY_LIMITED | overlap-aware calibration；无 overlap 不可恢复 |
| Large baseline | DETECTABLE / ADAPTABLE | geometry disparity range与遮挡风险；不无限扩大搜索 |
| Dynamic ROI | DETECTABLE / ADAPTABLE | ROI identity/provenance；改变会使 reference stale |
| Horizon/background intrusion | DETECTABLE / QA_ONLY | ROI contamination proxy；不自动删除用户数据 |
| Rapidly changing waves | DETECTABLE / QA_ONLY / REQUIRES_HARDWARE | normalized sync+motion；需要硬同步/短曝光 |

固定平台下当前 reference plane 模型成立。移动平台下必须先把每一帧变换到共同 pose；否则相机运动会被误解释为水面高度。专业系统优先 global-shutter、硬触发与外部 pose/IMU。
