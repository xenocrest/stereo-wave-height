# I02 补充验收：官方图片序列导出时间身份

fresh Vieira 的 GUI 投影/hover 验收通过后，导出暴露原 adapter 固定索引视频 `frame_mapping` 的 KeyError。官方 sequence manifest 为 `frames`，没有视频 PTS。只补齐本项目导出 adapter 的 provided 分支：按 index 找原 source image pair，保存源路径/hash；时间标为 `PROVIDED_SEQUENCE_NOMINAL_TIME`，视频源 PTS/frame index/TLCC/residual 均为空。B 单位 H_native 保留，H_mm 为空。

新回归真实执行导出并检查非零 index、图片身份、名义时间、没有伪造视频 PTS 和 B/mm 边界。另检查可选独立传感器 validation 路径：旧 gate 只接受旧字符串 ACTUAL_DECODED_PTS，会误拒本轮新真实 PTS；现 gate 要求 ABSOLUTE_SOURCE_PTS_COPYTS 且左右整数 ticks/time_base、index、实际秒数一致，明确拒绝旧或篡改身份。没有改同步残差阈值或传感器比较算法。两项新回归通过，见 `evidence/I02_sequence_export_tests.txt`。这是 I02 元数据链兼容补修，独立追加 commit，不混入四个原修复 commit；不改新生成的 WASS/NetCDF/XYZ/reference/图像，也不重新启动随机科学阶段。全量测试在该 adapter 补修后再次运行；最终 GUI/hover/export 再次验收。原失败检查日志保留 `P0_inspection_initial_log.txt`。

未新增科学算法或进入 P1；官方图片序列不是带有真实曝光 PTS 的视频样本。
