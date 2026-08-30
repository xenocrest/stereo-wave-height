# Demo Input Workflow Redesign

Classification: `DEMO_INPUT_WORKFLOW_REDESIGN_COMPLETED`

## Before

标定结果、标定视频和正式测量视频原先平铺显示，按钮名称含糊，首次使用者难以判断当前应提供什么文件。

## Guided workflow

1. **相机标定**：二选一——导入已有 YAML 双目标定结果，或选择 LEFT/RIGHT 标定视频并调用既有 OpenCV 官方标定后端。
2. **导入双目测量视频**：仅在标定就绪后启用，左右水面视频与标定视频分区显示。
3. **播放并选择测量时刻**：播放、时间轴、暂停和当前帧解算保持原行为。
4. **查看与导出结果**：高度叠加、状态、像素 XYZ/H、点云、历史和 Session 导出保持原行为。

当前实际支持的标定结果是项目 YAML（`.yaml`、`.yml`）。当前本地视频选择策略与 FFmpeg 读取路径一致，开放 MP4、MOV、AVI、MKV 和 M4V。现场标定要求用户明确输入棋盘格横向/纵向内部角点和单格尺寸（mm）；HomeTank_004 的 9×6、20 mm 仅作为可见且可修改的初值。

## Smoke

- 路径 A：HomeTank_004 已有 YAML 加载、K/D/R/T/baseline/QA 显示、左右 wave 视频准备、既有完成结果加载、overlay/hover/history 通过。
- 路径 B：HomeTank_004 左右标定视频经 24 个配对采样时刻检测到 9 组有效视图，既有 OpenCV `calibrateCamera/stereoCalibrate/stereoRectify` 调用链完成，生成临时结果并在 GUI 显示；该 smoke 不重新评价或替换历史标定结果。
- WASS 执行次数：0。

本轮仅改变 GUI 引导、输入状态和标定视频编排层。WASS、同步、XYZ、高度、pixel–XYZ、MLS、ROI 和 dense policy 均未修改。
