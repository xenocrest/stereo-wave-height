HomeTank_005 原始视频放置规则

1. 保留手机原始文件；只允许重命名，不转码。
2. 不裁剪、不改帧率、不改分辨率、不重新导出。
3. 不做视频防抖后处理，不改变 rotation metadata。
4. cam0 = LEFT，cam1 = RIGHT。
5. calibration 与 wave 阶段的两台手机身份必须保持一致。
6. HomeTank_005 不含独立 static 视频。
7. reference frame 由用户随后从 wave video 中选择。

目标文件名（保留各原始扩展名）：

videos\calibration\HomeTank_005_calibration_cam0_LEFT.<original_ext>
videos\calibration\HomeTank_005_calibration_cam1_RIGHT.<original_ext>
videos\wave\HomeTank_005_wave_cam0_LEFT.<original_ext>
videos\wave\HomeTank_005_wave_cam1_RIGHT.<original_ext>
