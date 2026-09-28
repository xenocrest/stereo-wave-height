# 独立真值瞬时验证 SOP

双目链和独立传感器链分别采集、处理、锁定结果。真值不参与 K/D/R/T 标定修正、WASS 参数调整、参考面修改、高度 offset 或后处理补偿。两条链只在最终验证汇合。

1. 锁定视觉 `run_report.json`、输入 hash、参考面 ID、`instantaneous_height.csv` 或原始 NPZ、`sync.json`。
2. 锁定传感器原始记录、仪器标定、`ground_truth.csv`、`sensor_layout.yaml`、`truth_sync.yaml`。`ground_truth.csv` 依照 `examples/ground_truth_schema.yaml`，质量标志为 `GOOD` 的记录才可匹配。
3. 确认高度 datum 相同。H 输入需同一 `reference_plane_id`；Z 输入需同一坐标系，程序再按固定参考面换算。
4. 先检查视觉帧的 `ACTUAL_DECODED_PTS` 和左右双目实际帧时间残差；缺少实际 PTS 或残差超过预设 `max_stereo_time_difference_ms` 时拒绝物理验证。对每个合格视觉帧和传感器，再做时间最近真实样本匹配：`t_gt_corrected=t_gt+offset_ms/1000`；`|delta_t_ms|` 超过配置门限，输出 `TIME_NOT_ALIGNED`，停止该点高度比较。不进行隐藏时间插值。
5. 在相同物理坐标系寻找最近官方网格视觉点，记录实际 `x/y` 与距离；超出空间门限输出 `SPACE_NOT_ALIGNED`。
6. 仅对时空、datum 均满足且有数据的点计算 `DeltaH_mm=H_vision_mm-H_true_mm` 和绝对值。逐时刻×传感器输出 `PASS_LT_10MM` 或 `FAIL_GE_10MM`，等于 10 mm 属于 FAIL。
7. 报告保留 `DIRECT_STEREO`、`OFFICIAL_GRID_ESTIMATE`、`NO_DATA` 来源。官方 pixel grid 估计不可写成直接双目观测。保留未匹配行与原因，不把失败行删掉。
8. 每个 `t_k` 展示单独高度图、传感器点位与单点 `DeltaH`；不将多个时刻或测点求平均后当主要结论。

目前仓库没有独立真实传感器数据。`examples/pre_hardware_dry_run` 的真值为程序自行构造，仅能证明匹配与计算逻辑，不能证明物理误差小于 10 mm。
