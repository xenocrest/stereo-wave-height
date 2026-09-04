# HomeTank_006：新一轮高清双目采集

状态：NOT_CAPTURED / NOT_PROCESSED。目录已准备；没有读取视频、执行标定或运行重建。

## 原始文件放置

根目录：`D:\research\stereo-wave-height\experiments\real_video\HomeTank_006\`

| 类型 | cam0 = LEFT | cam1 = RIGHT |
| --- | --- | --- |
| 标定 | videos/calibration/HomeTank_006_calibration_cam0_LEFT.mp4 | videos/calibration/HomeTank_006_calibration_cam1_RIGHT.mp4 |
| 静水 | videos/static/HomeTank_006_static_cam0_LEFT.mp4 | videos/static/HomeTank_006_static_cam1_RIGHT.mp4 |
| 波浪 | videos/wave/HomeTank_006_wave_cam0_LEFT.mp4 | videos/wave/HomeTank_006_wave_cam1_RIGHT.mp4 |

不要创建空 MP4 占位。保留手机原始文件，只重命名；若原始扩展名不同，保留原扩展名并更新 manifest，不要转码。视频不提交 Git。

## 今天采集时必须注意

- 计划规格为两台均 4K / 60 FPS，实际规格待读取，不能把计划当测量结果。
- 先录短样本检查清晰度；全部六段使用同一固定安装、同一镜头、同一视频模式，期间不移动、不重新夹持、不变焦。
- 尽可能固定对焦、曝光、白平衡，关闭可关闭的电子防抖、HDR及自动镜头切换；记录无法关闭的功能。
- 棋盘必须平整，覆盖公共画面的中心、边缘、四角；多种距离和倾斜姿态，每次停稳。实际内角点数和方格边长需要重新确认，不能直接套旧值。
- 请额外录一对独立静水视频：水完全静止后录制，保留与 wave 相同安装。它用于独立高度零面，不用每个波浪帧自我置零。
- 每组视频开始和结束保留两台均可见的清晰同步事件；不要用相同帧号假设同步。
- 标尺可以保留供独立验证，但不参与标定外参替换、重建或高度修正。

## 大视频准备与验收边界

现有预览只保留最新一帧，不整段加载。此次修正高帧率预览按源 FPS 计时，并限制 RGB 转换/发布频率；原始像素尺寸和解算输入不变。仍需解码源视频，不承诺两路4K60实时流畅；尚未打包新 EXE。

数据到位后先检查编码、真实时间戳、旋转、清晰度、同步、棋盘覆盖和公共水面，再标定。旧标定和旧参考面不移植至本实验。当前预览 FPS 计时不等于精确同步；可变帧率必须另行使用原始 PTS 检查。

目标是公共水面逐像素高度，不能用填满图像替代准确度。直接观测和模型估计必须分别标记；无依据区域不得伪造高度。准确性须以静水稳定性、重投影检查和独立参考误差验证。
