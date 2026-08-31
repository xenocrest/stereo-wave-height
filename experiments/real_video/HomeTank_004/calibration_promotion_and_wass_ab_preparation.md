# Calibration promotion and WASS support A/B preparation

状态：`CALIBRATION_PROMOTION_PIPELINE_READY`、`WASS_SUPPORT_AB_EVALUATION_READY`。GUI 保持 `DEMO_UI_FROZEN`。本轮 WASS executions = 0，calibration experiments = 0。

## 原子 package

每套标定位于独立目录，包含 `opencv_calibration.yaml/json`、`manifest.yaml` 和 `wass_fixed/` 下六个 OpenCV XML。manifest 记录 calibration ID、创建时间、左右采集源 identity、training/held-out IDs、9×6/20 mm checkerboard、原始 K/D、R/T/baseline、QA 指标及所有文件 SHA-256。视频不复制，也不做全视频 hash。

导出复用项目既有 OpenCV XML writer。生成后立即读回 K0/D0/K1/D1/R/T，以 absolute tolerance `1e-12` 与 package 内 OpenCV source 比较，并验证 manifest hash。任何差异返回 `CALIBRATION_WASS_EXPORT_MISMATCH`，不能批准 WASS A/B。

## 生命周期与 registry

生命周期为 `CANDIDATE → APPROVED_FOR_WASS_AB → PROMOTED_PRODUCTION_CALIBRATION`。第一步要求 calibration gate 和 package consistency 同时 PASS；第二步还要求未来 support A/B recommendation 为 `PROMOTE`。candidate 不能直接成为 production。

`calibrations/calibration_registry.yaml` 当前指向 `HomeTank_004_frozen_calibration_v1`。package 保留不变，切换和回滚只修改 pointer，历史 package 不覆盖、不删除。旧数值未重新计算；其历史 held-out 指标明确记为 unavailable。

## Future WASS A/B

NEW config 由 package root 展开并记录 calibration ID、package content hash 和 OLD baseline ID，不允许手工拼接不同 package 的 YAML/XML。WASS A/B 必须锁定视频、28.8007667 s 目标、左右帧 identity、同步模型/残差、rectification、matcher/stereo hashes、post-filter 和 water ROI；唯一变量是 K/D/R/T。

只读 evaluator 比较 triangulated/final XYZ、pixel-XYZ、ROI direct observed count/percent、common-FOV coverage、XYZ extent、largest component（若提供）、support bbox、固定 10×10 ROI occupancy、plane/geometry QA 与 runtime，并输出 OLD/NEW/overlay support maps。geometry regression 强制 `KEEP_OLD`；点数和空间覆盖均改善且 QA 稳定才推荐 `PROMOTE`；单一维度改善为 `REVIEW`。

## 明日最短 workflow

1. capture QA PASS 后完成正式 calibration 和相同 held-out comparison。
2. `python -m calibration.artifacts build ...` 创建 package 并自动 round-trip。
3. `python -m calibration.artifacts approve-ab ...` 仅在 gate PASS 时批准。
4. `python -m calibration.artifacts future-config ...` 生成 package-bound NEW WASS config。
5. 只运行一次 NEW WASS；OLD 复用 frozen result。
6. `python -m calibration.wass_support_ab ...` 自动 A/B。
7. 仅 recommendation 为 `PROMOTE` 时显式运行 `python -m calibration.artifacts promote ...`；发现问题可用 `rollback` 恢复旧 pointer。

OLD-vs-OLD metadata identity 自检结果为 `WASS_AB_NO_MATERIAL_IMPROVEMENT / KEEP_OLD`，证明 evaluator 不会把相同结果误判为提升。
