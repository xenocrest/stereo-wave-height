# 新实验目录约定

```text
experiments/<experiment_id>/
  raw/calibration/left/     raw/calibration/right/
  raw/wave/left/            raw/wave/right/
  raw/truth/
  metadata/experiment.yaml
  metadata/sensor_layout.yaml
  metadata/truth_sync.yaml
  runs/
  validation/
```

原始文件只读备份并保留 hash。`experiment.yaml` 使用 `examples/gopro_experiment_template.yaml`；其中视频路径可指向上述目录内文件。每次 pipeline 写新 run 目录；真值验证输出写对应 run 的 `validation/`。当前 HomeTank/Vieira 历史结果保持原路径，不搬迁或覆盖。
