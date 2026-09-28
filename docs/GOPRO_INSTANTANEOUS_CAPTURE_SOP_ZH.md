# GoPro 双目瞬时水面实验采集 SOP

本 SOP 只规定操作顺序；未到货设备的型号、镜头、工作距离和帧率均为 `TBD_AFTER_HARDWARE_ARRIVAL`。每一步的原始记录与操作者、日期一起保存。

1. **A 相机安装**：固定 LEFT/RIGHT，记录镜头模式、分辨率、帧率、曝光、对焦及防抖设置。标定至波浪拍摄期间保持相机相对位姿和镜头模式不变。
2. **B baseline**：实测两相机参考中心间距，记录方法、重复测量和单位；填 `camera.nominal_baseline_mm` 与一致的 `surface.baseline_m`。实际数值 `TBD_AFTER_HARDWARE_ARRIVAL`。
3. **C 标定板采集**：实测棋盘内角点行列与方格边长；左右相机以测量时相同模式录制多个距离、倾角和画面位置的棋盘。保存原视频。
4. **D 标定检查**：运行采集前检查和 OpenCV 标定；核对角点数、覆盖范围、每视图误差与 RMS，保存全部记录。不得为了某个波浪结果随意剔帧或改参数。
5. **E 静水参考**：拍摄明确静水状态，记录对应输入视频时间与将来采用的 `reference_frame_id`。若使用独立实测参考面，记录其测量和坐标变换。参考面在后续所有帧固定。
6. **F 传感器布设**：独立真值传感器安装在水面测点；标定其量程、零位、采样频率、质量标志。具体型号 `TBD_AFTER_HARDWARE_ARRIVAL`。
7. **G 空间位置**：按 [空间配准方法](GROUND_TRUTH_SPATIAL_REGISTRATION_ZH.md) 测出每个传感器点的视觉世界坐标，填写 `sensor_layout.yaml`。
8. **H 跨系统时间事件**：在相机画面和真值记录中制造共同可识别事件，测定相机与传感器时间偏移及来源，填 `truth_sync.yaml`。双 GoPro 的 TLCC 不代替这一步。
9. **I 波浪拍摄**：同时采集左右视频与独立真值。保存原始时间戳；记录相机是否移动、暂停、换电、变焦或改变设置。
10. **J 备份**：按 [实验目录](EXPERIMENT_DATA_LAYOUT_ZH.md) 保存原始文件，计算 hash，至少保留一份独立备份。
11. **K 配置**：复制 `examples/gopro_experiment_template.yaml`，替换所有 `TBD_AFTER_HARDWARE_ARRIVAL`，填写视频、棋盘、baseline、参考面、真值文件、门限。门限在查看真值偏差前确定。
12. **L 执行**：先运行 `python tools/preflight_check.py <experiment.yaml>`，确认 `READY_FOR_PIPELINE`；再执行 `python pipeline/run_pipeline.py <experiment.yaml>`。保存 run report、官方命令和日志。
13. **M 逐点验证**：选择明确的帧 `t_k`，根据独立传感器样本与空间门限计算每个点的 `Hvision、Htrue、DeltaH`，逐时刻读报告。只有对应时空点通过 gate，才报告其单点 `<10 mm` 或未通过。

有任一步缺失，就把该项写为未完成；不以人工调整高度代替采集证据。
