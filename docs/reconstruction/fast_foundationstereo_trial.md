# 成熟稠密双目模型的实际对照：Fast-FoundationStereo

日期：2026-09-05。Starting HEAD：`bca4495ecf5b6a58a240a0a8f54414f8bc354212`。

结论：`DENSE_MODEL_CANDIDATE_NOT_ALL_PIXEL_ACCURACY_VALIDATED`。
本轮确实运行了官方模型，不是方案设计或只检查模型能否导入。GUI、EXE、WASS、标定、历史参考面全部未改。

## 1. 为什么选择这条路线

上一轮 WASSfast 官方样例复现成功，但 HomeTank_004 的原始对应支持和高度仍不合格。
本轮不继续调 WASSfast 的阈值，也不自行开发匹配网络，改用
[NVIDIA 官方 Fast-FoundationStereo](https://github.com/NVlabs/Fast-FoundationStereo)
进行独立对照。其[论文](https://arxiv.org/abs/2512.11130)和官方接口明确要求输入为校正后的左右图像，输出为稠密视差。
它不是水面专用真值生成器；有限输出不等于物理正确。

官方源码版本：`a290ba04c1b3ad1ec41a33974a157b2917b624d4`，由下载 ZIP 的 commit comment 确认。
ZIP SHA256：`a4c6d49c2d2a7e8fe4de37099c00aa268fe463d08ca57128b2dbddaba39c90b4`。
权重取自 [NVIDIA c-fast-foundationstereo](https://huggingface.co/nvidia/c-fast-foundationstereo)，
SHA256：`7aee85948373da62b0503c2542507129a3e7cab9d97d10e6790d89512a7db214`，与发布者 LFS digest 一致。
源码许可为研究用途的 NVIDIA Source Code License；权重另有 NVIDIA Open Model Agreement。
本轮仅隔离研究，未将源码或权重分发进演示包，不能直接认定已经取得最终商业分发许可。

## 2. 几何链与明确依据

1. 冻结的 OpenCV 标定定义为 `X_cam1 = R X_cam0 + T_m`。
2. 使用 OpenCV `stereoRectify` 和 `initUndistortRectifyMap`，不修改 K/D/R/T。
3. 使用官方网络的 RGB、padding、AMP、8 次迭代及 `pytorch1` cost-volume 路径。
4. 左右交换并水平翻转再推理，获得右视图视差；还原翻转后进行左右一致性诊断。
5. 使用 OpenCV Q 与相同校正旋转恢复右相机米制 XYZ。
6. 高度通过独立参考平面的有符号正交距离得到，不使用 camera Z 充当高度。

对于当前零视差校正矩阵：

$$
d=u_L-u_R,\qquad Z_r=\frac{f_rB}{d},\qquad
X_{1r}=\frac{(u_R-c_x)Z_r}{f_r},\quad
Y_{1r}=\frac{(v_R-c_y)Z_r}{f_r}.
$$

$$
P_1=R_1^T P_{1r},\qquad H=\frac{n^TP_1+c}{\|n\|}.
$$

这里 `R1` 是本轮文件内的右相机校正旋转；参考面法向朝向位于平面上方的相机一侧。
未独立测量重力方向，因此不宣称已验证绝对竖直轴。
右相机原点换算另用 OpenCV `triangulatePoints` 做了数学单元测试。

[OpenCV 官方说明](https://docs.opencv.org/3.4.4/d9/d0c/group__calib3d.html)规定：
alpha=0 会放大并裁去无效边界，alpha=1 保留源图视场并允许黑边。
本轮隔离试验使用 alpha=1、CALIB_ZERO_DISPARITY，正式配置保持不变。
在 HomeTank_004 的 960×540 输出上，alpha=0 的焦距为 5048.842 px，
0.4 m 距离对应视差约 866.946 px；alpha=1 焦距为 351.670 px，同距离约 60.386 px。
这是输出投影策略的差别，不是更改镜头焦距或标定值；不能把 alpha=1 单独解释为匹配问题已经解决。

## 3. 运行环境与确切兼容问题

隔离目录：`D:/stereo-wave-height-runs/upstream_fast_foundationstereo/`。
Python 3.12，torch 2.6.0+cu124，torchvision 0.21.0+cu124，timm 1.0.15，OpenCV 5.0.0.93，RTX 4050 Laptop 6 GB。

实际遇到并保留的失败：

- 官方商业权重缺少 `args.normalize`，首次 forward 报 `ConfigAttributeError: Missing key normalize`。
  包装层只补齐官方 `scripts/make_plugin_onnx.py:123` 和 GWC 函数均使用的默认值 True，未训练或改权重。
- 第二次因 Windows 环境没有 Triton 编译后端失败。
  使用 PyTorch 支持的 `TORCHDYNAMO_DISABLE=1` 执行原始 eager 运算；未改网络算子，也未静默吞错。
- 上游 demo 包含 Linux shell 文件操作和交互窗口。本项目包装层替代的仅是这些输入输出动作，保留原始浮点视差，不裁掉负值或进行点云去噪。

已完成 32 次成功方向推理：两个桌面官方样例、12 个 HomeTank 帧对的正反方向、3 个海面帧对的正反方向。
960×540 热运行单方向网络耗时约 0.43～0.44 s；这**不是**视频解码到最终报告的整条链耗时。
海面 960×804 单方向热运行约 2.73～2.76 s。WASS 新运行 0，标定实验 0。

## 4. 预先固定的范围、时间和统计口径

HomeTank_004 使用上一轮同一批解码图像，静水约 10.012 s、波浪约 20 s，各选索引 0、3、7。
HomeTank_005 使用历史演示参考窗口约 9 s、波浪约 20 s，各选 0、3、7。
005 的参考窗口不是新确认的静水采集；原有同步候选及标定失败/未验证状态全部保留。
输入 hash、实际解码时间、矩阵保存在各 `inputs/preparation.json`。

004 canonical cam1 polygon：`[(80,700),(1240,680),(1450,1030),(100,1030)]`。
005 polygon：`[(80,720),(1160,720),(1400,1030),(80,1030)]`。
005 有 373511 个原图 ROI 像素，占 1920×1080 整图约 18.0%；不是“整幅视频 97.5% 已被测量”。
它是推理前依据画面确定的较大下部水槽候选区域，未根据成功点重新裁剪，也未独立确认每个特征来自水面。

一致性定义：`abs(d_R(u,v) - d_L(u+d_R(u,v),v)) <= 1 px`，且两边投影均在有效图像中。
1 px 是诊断阈值，不是工业精度门限；同时保存 2 px 结果，未据此挑选更好成绩。
原图像素与校正图像像素的面积权重不同，两个口径的比例分别报告。

| 输入 | 校正图候选 ROI 的左右一致性通过率（三帧） |
| --- | --- |
| 004 静水 | 53.09%、66.56%、60.05% |
| 004 波浪 | 1.77%、5.60%、0.026% |
| 005 历史参考窗口 | 54.71%、61.95%、56.34% |
| 005 波浪 | 14.61%、21.88%、31.34% |

全部帧的网络浮点输出有限率为 100%，但显然不能据此宣称全部对应正确。

## 5. 参考面不能混用

直接使用旧 WASS 参考面时，004 参考帧高度出现约 +80 mm 偏移，005 约 -550 mm。
旧面与新模型参考窗口共同一致区域拟合面的无向法向差分别为 49.97°、35.80°。
这证明当前两套恢复结果/参考面不能无条件拼接；**尚不能仅凭角度把原因全部归结为旧面选错或新模型正确**。

另存同模型参考分析：仅使用三个参考帧共同左右一致区域，复用项目已有正交最小二乘平面函数。
004 使用 13601 个共同像素、005 使用 12611 个共同像素，每个像素有三个参考时刻的点。
所有波浪点均不参与参考拟合，不逐帧置零，不覆盖旧参考面。
参考拟合 RMS 分别为 1.126 mm、2.672 mm；这是拟合残差，不是水面准确度。

005 原图输出采用官方建议的最近邻视差重采样，并使用**各原图查询像素自己的校正射线**恢复 XYZ/H，
不是把热图拉伸贴到 ROI。模型本身仍在 960×540 推理，1920×1080 导出不代表新增独立观测。

| 005 波浪时刻 | 原图估算覆盖率 | 原图一致性通过率 | 原图 H 中位数 | 原图 H 范围 |
| --- | --- | --- | --- | --- |
| 20.000 s | 97.55% | 10.34% | -12.92 mm | -49.46～6.49 mm |
| 20.200 s | 97.55% | 21.71% | -14.26 mm | -58.43～5.18 mm |
| 20.467 s | 97.55% | 21.17% | -0.55 mm | -39.11～12.55 mm |

剩余 2.45% 为投影/有效域不足，保持 NaN。未按高度大小剔除离群点；每帧均保留原始预测及一致性掩码。
这里只得到厘米量级的候选变化，尚无证据证明其真实波浪趋势与人眼一致。
尤其透明区域可能匹配到水下可见结构，不能仅因平面残差小就将其命名为已验证水面。

## 6. 同模型的真实海面检查

复用已下载的官方 WASSfast 样例，使用发布的 B=3.323 m、外参、平均海面与物理网格范围，未重新估计参数。
选第 0、25、49 帧。ROI 是官方物理区域投影，200198 个校正像素，占 960×804 图像约 25.94%，不是事后挑成功区域。

| 帧 | 左右一致性覆盖 | 一致区域 H P5/P95 | 对已有 WASSfast 曲面的 MAE | 空间相关系数 |
| --- | --- | --- | --- | --- |
| 0 | 92.74% | -0.451 / 0.564 m | 0.093 m | 0.683 |
| 25 | 92.66% | -0.397 / 0.648 m | 0.070 m | 0.847 |
| 49 | 83.25% | -0.381 / 0.596 m | 0.105 m | 0.744 |

对照仅在相同物理 XY 位置读取已有 WASSfast 网格，不反馈到重建。WASSfast 不是独立真值。
即使通过 1 px 检查，仍有约 -6.78～5.87 m 的离群高度；未删除后宣称通过。
远距离下同一视差误差对应更大深度误差：`delta_Z ≈ Z² delta_d/(f B)`。
因此必须另做物理误差预算，不能把一个像素的一致性统一当成可靠波高门限。

## 7. 决策与下一项有依据的工作

保留 Fast-FoundationStereo 作为成熟稠密候选，不再死磕 HomeTank WASSfast 参数。
官方海面已有较高对应一致性和曲面相关性，说明路线值得继续；HomeTank_005 的低一致性与目标表面身份仍未解决。
下一步应先在固定数据上验证可靠区域的真实波峰/波谷趋势，再决定是否接入现有空间补全；不再直接把不一致预测输入补全器放大错误。
对于模型明确无法验证的像素，保留估算/未支持区别，而不是随机或人为赋高。
当前**没有**达到“每个水面像素都准确且趋势已验证”，没有替换冻结演示程序。

## 8. 可复现入口与文件

- [输入准备](../../tools/prepare_foundationstereo_trial.py)
- [官方网络无界面调用](../../tools/run_official_fast_foundationstereo.py)
- [坐标及一致性分析](../../tools/analyze_foundationstereo_trial.py)
- [独立参考窗口及原图导出](../../tools/reference_foundationstereo_trial.py)
- [官方海面检查](../../tools/check_foundationstereo_sea.py)
- [005 配置](../../experiments/real_video/HomeTank_005/foundationstereo_trial_config.json)
- [机器可读结果](../../experiments/real_video/HomeTank_005/foundationstereo_trial_result.json)

按 prepare → run → analyze → reference 顺序执行各脚本的 `--help` 所列参数；输出目录必须是新目录。
run 使用隔离 venv，设置 `TORCHDYNAMO_DISABLE=1`；reference 使用主 Python 并设置 `PYTHONPATH=src`。
max-disp=192、迭代=8，所有试验保持一致；输出视差可能因迭代修正超过 192，原值保留。

实际完整输出根：`D:/stereo-wave-height-runs/upstream_fast_foundationstereo/`。
004：`HomeTank_004_inputs_v2`、`HomeTank_004_predictions_v3`、`HomeTank_004_analysis_v1`、`HomeTank_004_independent_reference_v1`。
005：`HomeTank_005_inputs_v1`、`HomeTank_005_predictions_v1`、`HomeTank_005_analysis_v1`、`HomeTank_005_independent_reference_v2`。
海面：`sea_inputs_v1`、`sea_predictions_v1`。
可视对照：`HomeTank_005_comparison.png`。权重、视频、大型数组、图片未提交 Git。

检查：3 项针对性几何测试通过；全套 469 passed、1 skipped、4 subtests passed。
compile、JSON 解析、Markdown UTF-8/链接/公式/表格及 `git diff --check` 通过。
下载 ZIP 内全部源码文件与运行目录逐字节一致，未修改上游算法。

参考面的物理定义依据 [WASS 论文](https://www.dsi.unive.it/wass/papers/1-s2.0-S0098300417304302-main.pdf)
及[公开海面数据论文](https://pmc.ncbi.nlm.nih.gov/articles/PMC7228941/)。独立参考、匹配正确性和目标表面身份是不同条件，不能互相代替。
