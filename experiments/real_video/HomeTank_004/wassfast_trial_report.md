# HomeTank_004：官方 WASSfast 实际隔离试验

日期：2026-09-04；Starting HEAD：`64e6b2fc6b5b65f8dcf01bc4138b15a3043868b8`。
结论：**官方程序跑完，但水面高度验证失败，不接入演示程序。**

## 输入和固定条件

先审查 004/005，再选择 004。004 有冻结静水原始 xyzC、plane.txt、相机矩阵和同步候选；
005 当前 demo_reference_artifact.yaml 标记几何未验证、LOW confidence、平面 RMS 29.923 mm。
本轮没有运行 005，不能从其历史成功状态推断本模型效果。

运行配置：[wassfast_trial_config.json](wassfast_trial_config.json)。

- 官方 WASSfast 1.6.3 CNN、原预训练权重、原模型实现。
- 同一官方样例 settings.cfg；没有参数搜索。
- 官方 wassgridsurface 0.11.4 的 `setup()` 生成 config.mat；只运行 setup，不运行 DCT。
- 同一冻结静水 R0 原始工作目录：`sync-tolerance-formal-r0-20260826/static`。
- 固定 OpenCV K/D/R/T，B=0.06868471158474378 m；不重新标定、调整基线或运行原 WASS 核心。
- 左图原始解码后 rotate180，右图 identity；1920×1080 灰度 PNG；不修改 MP4。
- Static：左侧 10.012256 秒起，8 对；Wave：左侧 20 秒起，8 对；各按 15 Hz 抽取。
- 右减左候选偏移：static −0.02018575 s；wave −0.0654055 s。
- 解码实际配对残差最大绝对值：static 25.597 ms；wave 23.117 ms。
  这是候选配对而非硬同步，实际 PTS 全部保存，不按相同帧号假定同步。

## 参考面与区域：不根据结果缩小

使用冻结原始 `plane.txt`，不是重新用当前波浪点拟合，也不把旧派生 reference YAML
与原始 xyzC 的坐标解释混用。原始归一化相机坐标平面：

```text
n = (-0.4143238255882800, -0.0712697942631352, 0.9073347695176148)
d = -5.244637806875186
n dot X_baseline_normalized + d = 0
```

官方 loader 加载冻结 xyzC 后，该平面残差 RMS=2.50897 mm。
此值只检查原始数据与原平面的关系，不代表整片真实水面精度。
官方 setup 生成 Rpl/Tpl；官方 WASSfast 应用旋转、平移、基线尺度和 Z 反向。
项目随后复用点到平面距离公式，**不是 camera Z，也没有每帧归零**。

预先从冻结图像选择较大的下部水槽候选区域（不是用户确认的语义水面 mask）：
cam1 canonical polygon=`[(80,700),(1240,680),(1450,1030),(100,1030)]`。
共 429,436 原图像素，占完整画面 **20.71%**。不读取标尺刻度，不以匹配结果调整 ROI。
ROI 通过固定标定射线与冻结参考面求交，仅用于确定网格范围，不作为新三维观测。

网格为该投影包围盒的同中心外接正方形，边长 0.3437553 m，256×256，
dx=dy=1.34806 mm。物理 ROI 内共有 14,008 个网格节点；不是 429,436 个独立观测。
按冻结几何计算，ROI 内仅 73.73% 网格节点在两相机内同时可见；没有因此缩小评价分母。
这是一项**模型预测可见性**，不能倒推出真实标定正确。

## 实际执行

外部根目录：`D:/stereo-wave-height-runs/upstream_wassfast/HomeTank_004_v1`。

```text
python -m wassfast static/input grid/config.mat config settings.cfg NONE CNN --batchsize 4 -n 7 -r 15 --nographics --savepts --saveCNNinput -dd static/observations -o static/output.nc
python -m wassfast wave/input grid/config.mat config settings.cfg AUTO CNN --batchsize 4 -n 7 -r 15 --nographics --savepts --saveCNNinput -dd wave/observations -o wave/output.nc
```

两次 return code=0，均保存 8 帧 NetCDF；原始观测文本也已保存。
结尾官方波浪统计报告提示 `Too few zero crossings found. Sequence too short? Aborting`。
这是短序列 Hs/周期统计不可用，不能把退出码 0 解读为统计与精度全部通过。
static 使用 NONE 传播方向，wave 使用上游 AUTO；默认无限水深仅作诊断运行，
本水槽的传播物理适用性未验证。没有把海面模型先验当成水槽真值。

## 数值结果

下列 coverage 分母是固定 ROI 的物理网格节点。有限 CNN 值是估计，不是实测。

| 项目 | Static，8 帧 | Wave，8 帧 |
| --- | ---: | ---: |
| 每帧保存原始三维点数，整个 grid 域的匹配输出 | 50–83 | 110–147 |
| 整个 256×256 grid 原始观测支持 | 0.0971% | 0.1917% |
| 整个 grid 有限估计比例 | 19.0481% | 24.8100% |
| 固定 ROI 原始观测支持 | **0.0696%** | **0.0357%** |
| 固定 ROI 有限估计比例 | **27.30%** | **22.56%** |
| ROI 原始点高度 RMS，相对冻结参考平面 | **120.47 mm** | **110.68 mm** |
| ROI CNN 估计高度 RMS，相对同一参考平面 | **122.31 mm** | **116.44 mm** |
| ROI CNN 高度范围 | −330.32…+143.44 mm | −420.38…+339.32 mm |

RMS 为高度相对基准的 RMS，不是对独立实测波高的 RMSE。
静水本应接近参考平面，当前大区域的百毫米级偏离不满足目标。
原始点阶段已出现同量级偏离，**不是只在 CNN 补全后才出现问题**。
本轮不能单独区分错误对应、标定/参考几何误差与观测对象混入各自占比；
不能把失败简单归咎为“水面质量差”，也不能认定换一个补全器即可解决。

关键结论：官方样例的 14.94% 原始网格支持 → 91.74% 有限估计，
不能迁移成“HomeTank_004 也有九成重建率”。当前大 ROI 观测约束不足，
并且几何一致性未通过；不继续强行补满、不缩 ROI 宣称通过。

## 产物、复现和下一步

项目新增的仅为外部官方工具的准备/读取/统计薄接口，不实现新匹配、三角化或补全模型。

```text
tools/prepare_wassfast_hometank004.py --config experiments/real_video/HomeTank_004/wassfast_trial_config.json
tools/report_upstream_wassfast.py --input <root>/wave/output.nc --config <root>/grid/config.mat --output <new-dir> --dataset-label HomeTank_004_wave
tools/analyze_wassfast_hometank_trial.py --root <root>
```

准备脚本用已安装的 wassgridsurface 环境执行（本次只补充 PyYAML 依赖）。
输出目录若已存在则拒绝准备，不覆盖冻结数据。读取/分析脚本使用 WASSfast 隔离环境。

外部证据：

- `input_manifest.json`：实际 PTS、输入图像 hash、冻结平面和标定 hash；
- `static/run.log`、`wave/run.log`：完整官方运行日志；
- `static/project_height/`、`wave/project_height/`：米制 H、有限估计 mask、原始支持 mask；
- `trial_summary.json`：每帧点数、ROI 支持和高度统计；
- `roi_and_wave_estimate.png`：实际 ROI 与该 ROI 估计范围，禁止当作测量成果图。

保留 CALIBRATION_QUALITY_FAIL、STATIC_VALIDATION_FAIL、approved_for_wass=false。
没有修改或重打包演示程序，没有产生可替换正式测量结果的高度图。
下一步应优先验证/改进前端对应与共同几何，不能继续仅依赖 CNN 填洞。

检查：466 tests passed、1 skipped、4 subtests passed；Python compile、JSON、
Markdown UTF-8/表格/代码围栏与本地链接、git diff --check 通过。
试验后重新计算冻结 calibration_result.yaml 和原始 plane.txt 的哈希，与运行前一致。
现有目录清单测试仅登记两个新增实验文件，历史失败状态检查未放宽。
