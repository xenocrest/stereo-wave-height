# Real-world generalization principles

1. Model adapts to data; user is not expected to create laboratory-perfect input.
2. 使用所有物理有效信息，包括只在单侧相机完整观测的标定板。
3. 绝不静默推断无支持测量；`UNSUPPORTED` 是正式结果。
4. 优先可观测 diagnostics，而不是固定场景假设。
5. 自适应策略必须 deterministic、reproducible、explainable，禁止隐藏调参。
6. 测量值与 confidence 分离；低 confidence 不改写测量值。
7. 每个自动决策保留输入、理由、配置和 provenance。
8. 标定依据 held-out geometry、spatial residual、parameter stability 和 plausibility，不只看 training RMS。
9. 硬件和物理不可辨识限制必须显式报告。
10. 手机阶段的改进必须能迁移到专业双目、室外水面和海面系统。
