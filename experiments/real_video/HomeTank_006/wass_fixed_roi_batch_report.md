# HomeTank_006：固定大范围 ROI 的 WASS 多帧诊断

Starting HEAD：`c4c8d7557f5dbe8a6a75bcc2905eab78acada611`。

## 固定输入与解释边界

本次不是旧海面成功样例。实际使用 HomeTank_006 原始 3840×2160 wave 视频；cam0 显式旋转 180°，cam1 不旋转，保留解码 PTS，未改视频。预先锁定左侧 1、2、3、6、10、20、35、50、65、80 s 共十帧，所有失败均计入。

固定候选几何 `rig_features_metric/result.json`，B=0.11579790568065551 m；此尺度来自历史棋盘跨度计算，不是新测量，不改变 K/D/R/T，也未批准标定。右侧时间候选为左侧 -0.225 s，来自已有音频候选，**不是已验证帧同步**。这些前提的不确定性仍保留。

以输入图像内容预先选定 canonical RIGHT 大多边形，覆盖下方主要可见区域，绕开部分标尺/边缘。坐标见[冻结批次配置](wass_fixed_roi_batch.yaml)。面积 **2,770,130 pixel，占全幅33.3976%**。它是分析者固定的诊断 ROI，不冒充用户已确认框选，也不声称完成严格水面分割。分母是整个多边形，不按点云凸包缩小，不排除失败区域；本轮也不裁去非公共像素，因此与“已裁公共 FOV 后的百分比”不能混比。预览在仓库外各帧 `fixed_roi.jpg`。

已知白色纹理主要为槽底，故下面统计的是 **XYZ 在固定画面范围的观测支持**，不是已确认水面支持。不得将槽底三维点交给补全器并标记水面高度成功。

## 真实失败与受控修复

基线使用既有 fixed-calibration runtime 和配置：prepare、match 后恢复固定 R/T；不运行 autocalibrate。十帧均在 stereo 校正失败，退出码 `3221226505`。

准确日志顺序：

```text
OpenCV rectification policy: alpha=0, flags=1024
the epipole lies inside the image plane
OpenCV ... !_src.empty() in cv::cvtColor
```

不是到了匹配后“几乎无点”，而是该批基线在匹配前就失败。现有 native 源码 `rectify()` 在零 ROI 返回 false，主流程没有检查这个返回值便继续处理空图，引发原生终止。未 patch WASS。

在完全相同的预处理图片、K/D/R/T、matcher、stereo 其他项和 ROI 上，仅将 `RECTIFICATION_ALPHA` 改为 `-1`，复用 prepare/match 结果后重跑 stereo。它是 [OpenCV 官方定义的默认缩放](https://docs.opencv.org/4.8.0/d9/d0c/group__calib3d.html)，不是缩放实际相机内参或人工改 baseline。项目配置模型现在明确允许 -1；默认仍为1，不自动升级既有 GUI 配置。

Python OpenCV 5.0 离线检查在 alpha=0 时一侧 ROI 为零，校正焦距约51695 px；alpha=-1 时约2964.86 px且两侧 ROI 非零。**最终以 native OpenCV 4.6 实际运行成功为依据**，不以 Python 结果代替 EXE 验证。

## 多帧实际结果

最终十帧统计见[小型结果 YAML](wass_fixed_roi_batch_result.yaml)。基线与受控复测全部保留，完整 stdout/stderr、命令、配置与原始点云在仓库外：

- `D:/stereo-wave-height-runs/HomeTank_006/wass_fixed_roi_batch_v1`
- `D:/stereo-wave-height-runs/HomeTank_006/wass_fixed_roi_alpha_auto_v1`

| 左侧时刻 s | 三角化有效点 | 最大连通块 | 最终 XYZ | 固定 ROI 观测支持率 |
| --- | ---: | ---: | ---: | ---: |
| 1 | 316823 | 60660 | 60660 | 0.7580% |
| 2 | 319348 | 49746 | 49746 | 0% |
| 3 | 323362 | 57511 | 57509 | 0.7477% |
| 6 | 403694 | 65156 | 65156 | 0.9796% |
| 10 | 510005 | 109168 | 109168 | 0% |
| 20 | 512817 | 122741 | 122741 | 0% |
| 35 | 375495 | 49778 | 49778 | 0% |
| 50 | 422534 | 119747 | 119747 | 0.0274% |
| 65 | 421135 | 137085 | 137085 | 0% |
| 80 | 335737 | 72185 | 72185 | 1.1123% |

流程生成 XYZ：0/10 → 10/10。**固定 ROI 支持中位数仅0.01368%**；五帧为零。大范围观测问题未解决。最大分量只保留三角化点的13.26%～32.55%；三角化本身在实际3840×1487 stereo栅格中也只占约5.55%～8.98%，不能说只剩一个后处理问题。平均 native stereo耗时79.62 s，不能宣称实时。

零支持表示输出点的 canonical RIGHT 投影未在固定 ROI 内满足0.75 px关联，不表示程序没有输出任何点；必须区别程序成功与测量区域成功。

## ROI 在 WASS 原生筛选前生效的两帧对照

再选已预先包含的静水候选1 s、波浪10 s作探索性对照，不作为独立验收。保持 alpha=-1，增加原生 `LEFT_MASK_IMAGE`：源码确认自动交换后 computational-left 是输入 RIGHT，且此掩码在 `triangulate()` 中按**去畸变、未校正**坐标读取。使用原始 K1/D1 将同一 canonical ROI 映射为去畸变掩码，不改图像或匹配算法。与上一组相比只增加该掩码。

| 左侧时刻 | 无掩码 ROI 支持 | 加掩码 ROI 支持 | 加掩码三角化点 | 加掩码最终点 | stereo耗时 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 s | 0.7580% | 0.7579% | 58,839 | 49,368 | 21.88 s |
| 10 s | 0% | 0.6026% | 57,860 | 43,115 | 21.56 s |

两帧均生成 XYZ。掩码使最大分量分别保留83.90%和74.52%的 ROI 内三角化点，但**这不是整个水面覆盖率**。它能避免部分背景主分量争夺，不能制造本来缺失的对应；总体支持仍不足1%。没有扩大0.75 native pixel邻近观测关联门，也没有用插值提高该指标。

这说明至少存在两个独立问题：原校正策略造成确定性流程失败；校正恢复后，前段有效三角化稀疏且全图最大分量选择丢掉许多点。只处理连通分量选择不足以恢复大区域水面。未隔离完的原因包括候选标定误差、时间误差和水面/透射背景混合，不能把它们全部归因于水面质量，也不能声称仅换匹配器已解决。

## 像素定义更正

从本机 native 源码确认：`P0cam.txt` 写自 `computeP()`，并非 `rec_P1`；三角化先 `unrectify()`，`triangulate.hpp` 求出的点在 computational-left 相机坐标中。故本次直接将 XYZ 投到实际 RIGHT 相机，再使用原始 K1/D1恢复 canonical 像素。若没有交换，则先施加固定 R 和 baseline-normalized T。

此前海面试验把 `P0cam` 当成 rectified 投影，其91.17%不能继续作为已核实的图像 ROI 支持结论；已在[历史报告](../../../docs/validation/ocean_observation_completion.md)标记更正，保留原数组，并禁止旧工具无提示再次输出该结论。当前十帧统计不依赖旧 frozen pixel–XYZ 或该海面例子。

## 复现

```powershell
$env:PYTHONPATH='src;tools'
D:/python/python.exe tools/wass_fixed_roi_batch.py --config experiments/real_video/HomeTank_006/wass_fixed_roi_batch.yaml
D:/python/python.exe tools/wass_fixed_roi_batch.py --replay-from D:/stereo-wave-height-runs/HomeTank_006/wass_fixed_roi_batch_v1 --output D:/stereo-wave-height-runs/HomeTank_006/wass_fixed_roi_alpha_auto_v1 --alpha -1
D:/python/python.exe tools/wass_fixed_roi_batch.py --replay-from D:/stereo-wave-height-runs/HomeTank_006/wass_fixed_roi_batch_v1 --output D:/stereo-wave-height-runs/HomeTank_006/wass_fixed_roi_native_mask_probe_v1 --alpha -1 --roi-mask --frames 000000 000004
```

输出目录必须不存在；重做应另选路径。普通单元测试不启动 WASS。

## 结论和下一步

当前结论是 `WASS_PROCESS_RECOVERY_NOT_WATER_MEASUREMENT_SUCCESS`。未运行高度补全、未输出波高、未修改 GUI/EXE，未改变历史失败与标定审批。下一步优先对固定范围的对应和几何残差定位，验证输入像素确实来自水面；本轮没有足够证据把缺少99%观测的区域推广为可信全像素高度。全像素和正确趋势仍为目标，但不能用填色代替证据。

测试：460 passed、1 skipped、4 subtests passed，保留1条既有 NetCDF ABI警告；新增测试覆盖缺失计数不伪造、RIGHT相机投影/交换约定、alpha=-1显式配置与旧默认兼容。实际运行10次prepare、10次match、22次stereo（10次基线、10次策略复测、2次掩码对照），没有autocalibrate、新标定实验或参数网格搜索。
