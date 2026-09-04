# HomeTank_006：实测结果接入演示程序

本次接入的是已完成十帧 WASS 复测的**只读结果展示**，不是实时重新解算，也不是可靠全像素波高功能。既有标定、参考面、解算按钮与会话数据不变；没有把 alpha=-1 自动覆盖到其他实验或旧 GUI 测量配置。

## 查看

打开 `D:/research/stereo-wave-height/dist/StereoWaveHeightDemo/StereoWaveHeightDemo.exe`，默认进入“最新实测结果（只读）”。不需要加载视频或参考面，可选择十个原始时刻，切换“原始 RIGHT 画面”和“真实重建点与 ROI”。

黄色为预先固定、未经用户确认的诊断 ROI；绿色为真实 WASS XYZ 的 canonical RIGHT 投影，含 ROI 外点，不代表已验证水面或高度。ROI 分母为原生图像的2,770,130像素，预览缩小不改变支持率。所有零支持帧保留；不根据当前选择的 GUI ROI 重算或冒充结果。

数据依据：[十帧结果](wass_fixed_roi_batch_result.yaml)和[诊断报告](wass_fixed_roi_batch_report.md)。页面保留解码时间、整帧 XYZ 数量、固定 ROI 支持率和实际耗时；明确显示高度暂不可用。没有使用槽底折射或人工高度。

## 复现与资源

```powershell
$env:PYTHONPATH='src;tools'
D:/python/python.exe tools/export_observation_review.py --result experiments/real_video/HomeTank_006/wass_fixed_roi_batch_result.yaml --output resources/wass_observation_review
./tools/build_demo_windows.ps1 -PythonExe D:/python/python.exe
```

生成目录须不存在，禁止覆盖。源文件读取后生成20张小型预览和1个JSON清单，总计2,201,728字节；每张预览有SHA256校验，清单记录源结果哈希。构建脚本将其复制到EXE旁的resources，不依赖用户机器的旧运行绝对路径。原视频、点云、预览和截图不提交Git；资源缺失或损坏明确报错，不调用历史fallback或WASS。

## 验证

- 463 passed、1 skipped、4 subtests passed；保留既有1条NetCDF ABI警告。
- 新增测试：零支持保留、资源篡改拒绝、禁止冒充高度、真实Tk控件换帧与只读性。
- 最终打包EXE实际启动，默认结果页显示成功；实际点击原始图/支持图和下一帧，确认从000000切换到000001，支持率从0.7580%变为0.0000%，图像同步切换。
- 截图在 `D:/stereo-wave-height-runs/HomeTank_006/demo_observation_review/`；这只是新结果页验收，不代表重新验收原有实时测量全链。
- 本轮WASS执行0次、标定实验0次。Python compile和git diff检查通过。

原实时测量页仍保留。当前不能保证该页在HomeTank_006上产生正确波高；新的成果仅在独立只读页展示，防止未经验证的数据污染参考面或测量记录。
