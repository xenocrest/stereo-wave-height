# 真实水面单帧与对应 WASS 三维点云

本目录展示项目历史真实手机双目视频实验中，同一时刻真实水面图像与 WASS 生成三维点云的对应结果。

- 数据集：HomeTank_005
- 角色：波浪 measurement 帧
- 用户请求时间：44.334500 s
- 实际解码时间：LEFT 44.330556 s，RIGHT 44.334500 s
- 帧标识：LEFT `pts_3989750`，RIGHT `pts_3990105`
- 标定：HomeTank_005_demo_only_v1
- 有限 XYZ 数量：74,164 / 74,164
- 对应图像：`real_water_frame_RIGHT.png`
- 完整点云：`real_water_point_cloud.ply`
- 静态点云图：`real_water_point_cloud.png`
- 汇报对照图：`REAL_WATER_POINT_CLOUD_COMPARISON.png`

图像、PLY 和运行 metadata 来自同一个导出记录 `session_20260903-112457/measurement_44.335s`。结果文件同时记录了同一组视频、标定、请求时间、左右实际时间、左右帧 ID 和 74,164 个 XYZ 点，因此不是将任意图片和任意点云拼接在一起。

静态点云图仅为显示速度采用确定性抽样，并按原始 Z/depth 着色；完整 PLY 没有删点、缩放或修改。

该历史运行的 reference/measurement coordinate frame 后续被发现存在整体偏移，因此其 height 数值不用于物理精度展示。本目录中的 XYZ 点云确实来自该真实双目帧的 WASS 重建，只用于证明真实水面三维重建阶段已经成功发生过。

