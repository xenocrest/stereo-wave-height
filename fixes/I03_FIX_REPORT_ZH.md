# I03 修复：唯一相机图像方向约定

唯一约定为 `CONTAINER_DISPLAY_ORIENTATION_APPLIED_ONCE_V1`：先按容器 display orientation 旋转一次，再进行标定、预览、测量提帧和 WASS prepare。OpenCV 显式打开 ORIENTATION_AUTO；FFmpeg 显式 autorotate。无法启用约定时拒绝读取，不依赖后端默认值。不交换 K 的行列，不事后旋转去畸变图。

原左标定视频 metadata 为 180°，旧 fresh 标定显式关闭方向应用，而测量视频由 FFmpeg 应用方向。本次按统一约定重新检测角点、选择 50 个视图并执行原 OpenCV 标定；右视频 metadata 为 0°。棋盘 6×9、格长 0.020 m、5 Hz、50 views、至少 12 views 均未改变。

|相机|旧 fresh RMS px|新 fresh RMS px|完整棋盘检测数|选中数|
|---|---:|---:|---:|---:|
|左|4.19724464694886|4.149856500614477|230|50|
|右|5.522525225570181|5.522525225570181|328|50|

数值变化不是水面精度改善证明。新 K/D、选中帧编号和 SHA256 见 `evidence/I03_fresh_calibration.json`；完整角点、选中图像与标定日志在 `D:/stereo-wave-height-runs/reconstruction-quality-p0-20261001/I03_fresh_intrinsics`。新 K/D 未估计或搭配历史 R/T；实际 HomeTank fallback 保持完整历史 K/D/R/T bundle。

两项回归覆盖后端方向显式设置、不能启用时拒绝，以及四个真实标定/测量视频：OpenCV canonical decode 与 GUI preview 逐像素一致，FFmpeg 原帧 index=0，尺寸和方向一致；两种解码器的 RGB 舍入差以均值 <2 灰度验收。测试 2/2 通过；现有 app 回归 20/20 通过。证据见 `I03_tests.txt` 与 `I03_app_regression.txt`。

未修改第三方代码；未调整科学参数、matcher、reference、support 或随机种子。
