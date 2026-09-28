# 设备到货前准备状态

当前科学基线是 `pipeline/vieira-wass-reproduction` 的 `f942bb3b3b4b5ed15f8dd9c5b34944a94d28b845`：Vieira 官方样例完整通过；HomeTank_004 以明确记录的完整历史外参 fallback 通过。第三方科学算法未修改。

现在已经准备：固定参考面接口、按帧和时间保存的瞬时高度格式、独立真值 CSV/schema、相机与真值的时间偏移文件、传感器空间位置文件、逐点 `DeltaH` 判断、合成数据逻辑测试、采集前检查、GoPro 配置模板、采集和验证 SOP、已有六帧瞬时展示。入口见 [瞬时量定义](docs/INSTANTANEOUS_MEASUREMENT_SPEC_ZH.md)、[采集 SOP](docs/GOPRO_INSTANTANEOUS_CAPTURE_SOP_ZH.md) 和 [真值验证 SOP](docs/INSTANTANEOUS_GROUND_TRUTH_VALIDATION_SOP_ZH.md)。

设备到货后：安装并实测 baseline；录制标定、静水状态和波浪视频；部署独立真值传感器并实测其位置和相机时间偏移；填 YAML；通过预检；运行现有 pipeline 和逐点验证。未知值保持 `TBD_AFTER_HARDWARE_ARRIVAL`，不能用模板默认值冒充实测。

当前没有独立真实传感器数据，不能宣称瞬时高度真实误差已达到 `<10 mm`。历史 HomeTank 的 `EXTRINSIC_FALLBACK` 和 Vieira 样例的归一化单位 `B` 也不能当作这样的精度证据。已有历史图仅作瞬时形态展示，其零位是 WASS 内部对齐平面；未来正式验证必须使用明确的固定参考面和同一时空点的独立真值。

## 可直接使用的命令

在仓库根目录、已安装同基线 Python 依赖的环境中执行：

```powershell
python tools/preflight_check.py examples/gopro_experiment_template.yaml
python -m pipeline.instantaneous_validation.synthetic_validation_test
python tools/stereo_geometry_planner.py --baseline-mm 160 --focal-px 2000 --distance-mm 2000
python pipeline/run_pipeline.py experiments/<experiment_id>/metadata/experiment.yaml
python -m pipeline.instantaneous_validation.run_validation experiments/<experiment_id>/metadata/experiment.yaml <run_dir> <output_dir>
```

模板中的设备参数为待填写值，因此预检结果应为 `NOT_READY`。合成干跑报告写入 `D:/stereo-wave-height-runs/pre_hardware_dry_run/`，其数值真值是程序构造的。正式实验 YAML 填好后，`run_pipeline.py` 会在官方工具链完成后自动执行固定参考面和真值比较；单独的验证命令可用于重新检查已有 run。`export_stride: 1` 导出全像素 CSV，文件可能很大；抽样导出须保留 manifest 的实际步长。

## 本阶段验收记录（2026-09-28）

状态：`PRE_HARDWARE_INSTANTANEOUS_READY_PASS`，表示设备到货前的软件接口、验证逻辑与操作文件已备齐；不表示新硬件采集或真实精度已通过。

提交后的同一科学 Pipeline 重新运行：

- Vieira：`D:/stereo-wave-height-runs/pipeline/vieira_official/run_20260928_113344`，`VIEIRA_OFFICIAL_SAMPLE_PASS`，5 帧点数 649,657 / 702,869 / 679,470 / 707,275 / 711,415。
- HomeTank：`D:/stereo-wave-height-runs/pipeline/hometank004/run_20260928_113734`，`HOMETANK_PIPELINE_PASS_WITH_EXTRINSIC_FALLBACK`，3 帧点数 132,850 / 148,612 / 147,337。实际 LEFT 时间为 20.0089、20.5089、21.0089 s；相对音频 TLCC 映射，左右实际取帧时间残差每帧为 −8.9 ms。将来必须按预先设定的门限判断，而不能隐藏此残差。
- 两次 run 均记录科学代码提交 `85ab569d120ec5472de27371c9e086c82ac21afe`、`git_dirty=false`、第三方算法修改 `0`。WASS/wass_lowcost 源码 hash 与此前稳定运行一致。20 s 单帧的时间戳记录改动前后 PNG SHA256 完全一致。
- 从上述 run 分别生成的 3 张瞬时图位于 `D:/stereo-wave-height-runs/pre_hardware_instantaneous/vieira_final/` 和 `.../hometank004_final/`。HomeTank 图标记 `EXTRINSIC_FALLBACK`；两组图均注明历史内部参考面仅用于形态展示。
- 合成干跑：`D:/stereo-wave-height-runs/pre_hardware_dry_run/dry_run_report.json`，状态 `PRE_HARDWARE_DRY_RUN_PASS`；逐点示例 `+4.2 mm → PASS_LT_10MM`、`−12.0 mm → FAIL_GE_10MM`，这两个真值由测试程序构造。
- 新验证代码与原有全项目测试通过；GoPro 模板的预检显示未到货项目 `NOT_READY`，完整接口的模拟采集预检可返回 `READY_FOR_PIPELINE`。
