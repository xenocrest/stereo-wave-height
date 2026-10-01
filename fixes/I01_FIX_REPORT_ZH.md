# I01 修复：原图与去畸变测量坐标隔离

科学显示默认使用实际WASS workspace的`undistorted/00000000.png`，完整extent按官方map framebuffer尺寸显示。measurement与overlay共享同一光栅，hover直接读取同一(u,v)，不再将raw位置按缩放当作undistorted位置。缺失官方图或aspect/crop不一致时报错，不回退raw。

单独`RAW_CAMERA_IMAGE`模式保留原相机图，关闭H hover、科学边界和测量ROI；`UNDISTORTED_MEASUREMENT_VIEW`明确使用去畸变图。当前ROI仍仅控制显示/查询/导出，未实施I04科学mask。导出另存measurement_frame.png并记录raw/measurement/overlay坐标语义。

对未改的HomeTank21/22/23与Vieira原科学产物，raw错位median分别4.720/4.758/4.535/1.135 px；改为measurement后同1000个map样本的内部投影median分别0.001375/0.002207/0.001777/0.015545 px。数值来自同一原map投影位置，实际renderer已换成对应官方图；I01不改变任何XYZ。真实WASS点→grid的I12误差仍单独保留，不能把map内部误差当作I12已修。

`tests/test_p0_measurement_view.py`覆盖四角、四边中点、中心、raw禁用、缺图/aspect拒绝、真实两数据集overlay背景和hover XYZ一致。`fixes/scripts/validate_i01.py`输出实际renderer前后图及`evidence/I01_validation.json`。最终四项修复完成后的真实新运行再统一验证camera→grid投影。

未修改第三方源码。未开始支持域、mask、随机性、reference显示或3D比例等后续P1工作。
