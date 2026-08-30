# Stereo Wave Height Offline Demo

## Development mode

```powershell
$env:PYTHONPATH="$PWD;$PWD\src"
python -m application
```

## 打包模式

打开 `dist\StereoWaveHeightDemo`，双击 `StereoWaveHeightDemo.exe`。

1. 选择标定方式：导入已有 YAML，或选择 LEFT/RIGHT 标定视频现场计算。
2. 标定完成后，选择 LEFT/RIGHT 水面测量视频。
3. 进入视频测量，播放并暂停到目标时刻。
4. 点击“解算当前暂停帧”（约 30 秒）。
5. 查看高度叠加、像素结果和点云，结束时导出会话。

程序完全在本地运行，不需要网络。请保持整个分发目录完整；WASS 和 FFmpeg 位于 `runtime\`。分发包不包含 HomeTank_004 原始视频。
