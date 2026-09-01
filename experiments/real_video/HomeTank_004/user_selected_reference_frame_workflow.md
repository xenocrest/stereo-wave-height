# User-selected reference-frame workflow

状态：`USER_SELECTED_REFERENCE_FRAME_WORKFLOW_COMPLETED`。

离线演示流程现为：导入双目测量视频 → 设置 water ROI → 播放/暂停/seek → 设置当前帧为参考帧 → 后台复用现有 single-frame WASS → 在 ROI 内直接观测 XYZ 上拟合参考面 → seek 到测量帧 → 使用固定参考面计算 H → overlay、hover、点云与导出。

参考帧不要求是静水状态。参考面为用户所选帧有效水面点的最佳拟合平面 `aX+bY+cZ+d=0`；高度定义为 `H=(aX+bY+cZ+d)/sqrt(a²+b²+c²)`，即当前点到用户参考面的有符号法向距离。参考帧自身显示的是相对拟合平面的残差，不会被强制写成全零。

每次成功 reference solve 保存独立 `reference_<id>.yaml`，记录 requested/actual timestamp、fallback offset、左右 frame IDs、sync residual、calibration ID/package hash、video-pair ID、canonical convention、ROI/ROI ID、plane、RMS、support count、XYZ extent 与创建时间。session pointer 仅在新 reference 成功后切换，旧 artifact 和旧 measurement 的 reference ID 保留。

更换 calibration、左右视频或 ROI 会使 active reference stale。measurement backend 同时验证 finite plane、calibration、video pair、ROI 和 canonical convention，不一致返回 `REFERENCE_ARTIFACT_INCOMPATIBLE`。没有 active reference 时 GUI 禁止正式 H 解算。

最小 artifact 复用 smoke 验证了 reference serialization → compatibility gate → fixed-plane signed height → session/export metadata。随后仅执行 1 次 packaged reference WASS smoke：requested time 为 29.4654055 s，实际左帧时间为 29.465178 s，左右同步残差为 1.0055 ms，生成 35,459 个 XYZ/ROI 支持点以及 `REFERENCE_PLANE_READY` artifact；参考面 RMS 为 0.8881 mm。没有执行新的 measurement WASS。Windows onedir 包已重新构建并通过离线启动 smoke；backend 仍使用同一 `--backend-single-frame` 入口。
