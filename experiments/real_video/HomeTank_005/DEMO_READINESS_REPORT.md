# HomeTank_005 Demo Readiness Report

## System definition

“基于双目视频输入的按需单帧水面三维测量与展示系统”。

核心流程为：双目视频 → 自动公共视场 → 用户水面 ROI → 用户参考帧 → 按需单帧双目重建 → 相对参考面高度 → 可视化与导出。

## Capture and adaptive calibration

HomeTank_005 uses independent LEFT-only and RIGHT-only checkerboard observations plus synchronized bilateral observations. The final fit used 179 LEFT and 86 RIGHT detections; 63 bilateral pairs formed 17 independent pose groups and deterministic five-fold grouped cross-validation. Near-duplicate groups never cross train/validation folds.

Two bounded OpenCV models were compared: `k1,k2,p1,p2` with `k3=0`, and `k1,k2,p1,p2,k3`. The five-coefficient model had the lower grouped-CV error, but both models were unstable. The selected candidate has mono RMS 3.693/3.287 px, stereo RMS 3.694 px, symmetric epipolar RMS 3.708 px and baseline 0.093345 m.

The canonical decoder audit found and fixed an engineering error: OpenCV was auto-applying the LEFT 180° metadata before the QA code explicitly applied the same transform. After disabling decoder auto-orientation, relative rotation became 1.917° and full-sample rectified vertical RMS decreased from a catastrophic thousands-of-pixels result to 13.045 px. This is a real improvement over HomeTank_004 (vertical RMS 21.123 px and epipolar RMS 9.508 px), but it is not sufficient for trusted geometry.

Grouped-CV remains decisive: aggregate RMS is 10.122 px, worst-fold RMS 18.635 px, with focal relative range 29.32%, principal-point normalized range 32.31%, baseline relative range 32.16%, and distortion range 1.891. The classification is therefore:

`HOMETANK005_CALIBRATION_MODEL_LIMIT_REACHED`

The historical intake report remains unchanged. Full-sensor 3×3 coverage is now treated as a diagnostic warning, but operational validation still fails on measured geometry—not on the old coverage gate alone.

## Common FOV, reference, and measurement

No HomeTank_005 calibration package was approved, so no authoritative geometric common-FOV artifact was generated. Reference and measurement WASS were not run. No HomeTank_005 XYZ, plane, H, overlay, or dense map is presented.

This is intentional: publishing a height result from an unstable calibration would hide a known failure. The GUI can still load the videos and expose calibration QA. Its established common-FOV → ROI → reference → measurement workflow remains available for an approved calibration, and historical frozen HomeTank_004 artifacts remain available as an engineering-chain demonstration.

## Presentation scope

The demo may claim:

- real stereo-video intake, canonical orientation handling, and checkerboard QA;
- adaptive split calibration with grouped cross-validation and explicit model selection;
- automatic detection of calibration geometry that is not reliable enough for measurement;
- a complete offline interaction workflow for approved calibration packages;
- explicit `OBSERVED`, `ESTIMATED_LOCAL`, and `UNSUPPORTED` result semantics in historical validated workflow artifacts.

The demo must not claim:

- a trustworthy HomeTank_005 XYZ/H result;
- millimetre accuracy or validated physical wave-height accuracy;
- a HomeTank_005 common FOV derived from an approved calibration;
- production promotion of this calibration.

## Final state

- Calibration: `HOMETANK005_CALIBRATION_MODEL_LIMIT_REACHED`
- Demo: `DEMO_SYSTEM_READY_WITH_CALIBRATION_QA_LIMITATION`
- HomeTank_005 WASS executions: 0
- Reference/measurement: blocked before WASS by calibration geometry QA
- Re-recording recommendation: none; future work belongs to the calibration model and observability strategy.
- Windows package: rebuilt successfully; EXE launch, bundled WASS, FFmpeg and historical frozen resources passed smoke inspection. The HomeTank_005 QA artifact is bundled and remains measurement-blocking.
