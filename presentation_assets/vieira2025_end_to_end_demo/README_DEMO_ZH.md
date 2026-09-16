# 冻结的五帧官方工具链演示

说明见 [顶层报告](../../DEMO_VIEIRA2025_END_TO_END_ZH.md)。

一键查看：在仓库根目录执行 `powershell -ExecutionPolicy Bypass -File scripts/run_vieira_demo.ps1`。
加 `-NoOpen` 只输出查询；加 `-Rebuild` 从原始视频重新同步、调用官方工具，结果进入新的独立目录，仍需人工检查 overlay。

完整本地文件在 `D:\stereo-wave-height-runs\vieira2025-end-to-end-demo-20260916\golden_004_demo`；[manifest](demo_manifest.json) 记录 SHA256、来源和日志索引。大文件不在 GitHub；这里保存了演示图片、审计结果和重算配置。

本例用了历史标定 fallback，新生成五帧点云和官方后处理，不是历史点云拼接。不改变 GUI 或严格科学轨道。

`overlay.png` 是中央水面展示遮罩；`overlay_full_official.png` 是未经遮罩的官方结果，含非水面范围，二者都保留。全部网格高度必须视为 DEMO_ONLY / NOT_PHYSICALLY_VALIDATED，finite 不等于直接测量，外推不等于可靠支撑。

`official_stereo_sparse_ransac.txt` 仅保存失败的 005 尝试，不被最终 004 配置或入口采用。
