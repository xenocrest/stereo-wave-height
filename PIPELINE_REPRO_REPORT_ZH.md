# Vieira / WASS 双数据集最小 Pipeline 复现报告

## 1. 范围与结论

本轮停止继续开发 StereoWaveHeightSystem 桌面程序，新增独立的 YAML 驱动 Pipeline。所有第三方科学算法保持原样，修改数为 **0**。编排层仅负责文件 IO、命令调用、日志、hash、结果索引和只读可视化。

最终结论：

- `VIEIRA_OFFICIAL_SAMPLE_PASS`
- `HOMETANK_PIPELINE_PASS_WITH_EXTRINSIC_FALLBACK`
- `PIPELINE_DUAL_DATASET_PASS`

这三个状态表示软件复现链完整，不代表物理精度已经独立验证。

## 2. 官方方法映射

[WASS 官方 Getting Started](https://www.dais.unive.it/wass/documentation/getting_started.html)说明了 `prepare → match → autocalibrate → stereo`：match 建立跨相机特征对应，autocalibrate 用多帧匹配进行 SBA 外参优化，stereo 生成稠密点云并拟合平面。[官方 Quick-start Guide](https://www.dais.unive.it/wass/WASS_quickstart_guide.pdf)进一步规定 `wassgridsurface` 把点云对齐到共同 mean sea plane 并输出 NetCDF，`wassncplot` 把网格投影回图像并输出 pixel↔XYZ 映射。本 Pipeline 逐条调用这些程序，没有复制或改写它们的算法。

## 3. Vieira 作者样例

来源：[matheusdpv/wass_lowcost](https://github.com/matheusdpv/wass_lowcost)，固定提交 `688dfaf1d88f270cf3d7cd3db4b49369ebe52871`。输入是左右各 5 张原始 1920×1080 TIFF，作者给定 12 Hz 和同步关系；没有重新编码视频。

作者提供的四个 K/D XML 原样使用。公开样例没有 R/T，所以本次真实运行 5 个 workspace 的 WASS prepare、match、autocalibrate 和 stereo，随后运行 wassgridsurface 与 wassncplot。

正式成功运行：

`D:/stereo-wave-height-runs/pipeline/vieira_official/run_20260921_153629`

每帧官方 PLY 点数：

| 帧 | XYZ/PLY 点数 | 官方 pixel-grid 有效像素 | 单位 |
|---:|---:|---:|---|
| 0 | 642,811 | 1,226,678 | B |
| 1 | 691,248 | 1,240,177 | B |
| 2 | 672,826 | 1,238,531 | B |
| 3 | 642,139 | 1,211,386 | B |
| 4 | 620,321 | 1,226,799 | B |

总 XYZ/PLY 点数为 3,269,345。样例未公布实测 baseline，所以 B=1 只是归一化定义；所有界面与文件保留单位 `B`，没有伪造毫米值。

## 4. HomeTank_004

正式成功运行：

`D:/stereo-wave-height-runs/pipeline/hometank004/run_20260921_155245`

原始标定视频重新执行 OpenCV：LEFT RMS=4.197245 px，RIGHT RMS=5.522525 px。结果完整保存所有检测、选中帧、角点和 per-view error；这些较大的 RMS 不能被表述为高精度标定通过。

原始波浪视频重新执行 wass_lowcost TLCC：RIGHT−LEFT=−0.075070016 s；再按该关系提取连续三对同步帧。音频同步本身不等价于逐曝光硬件同步验证。

新 K/D 的 WASS prepare、match、autocalibrate 已真实执行并保留。由于 HomeTank 的已知布局在当前官方 WASS dense stereo 中不受支持，YAML 显式切换以下完整六文件 bundle：

`D:/stereo-wave-height-runs/HomeTank_004/wave-reconstruction-pipeline-20260824/wass_workspace/config`

程序同时切换完整 K/D/R/T，未把新 K/D 与旧 R/T 混用，未修改 T。当前官方二进制使用 YAML 中显式记录的兼容 stereo config。最终连续三帧均完成官方 stereo、surface、NetCDF 和像素映射：

| 帧 | XYZ/PLY 点数 | 官方 pixel-grid 有效像素 | 高度单位 |
|---:|---:|---:|---|
| 0 | 132,282 | 1,276,685 | m |
| 1 | 148,865 | 1,249,193 | m |
| 2 | 147,299 | 1,234,638 | m |

总 XYZ/PLY 点数为 428,446。网格高度范围分别约为 [−50.13,+29.03] mm、[−55.93,+28.22] mm、[−63.70,+19.94] mm；这是官方网格相对于本次参考面的计算范围，不是独立物理真值。

两次未通过尝试也原样保留：

- `run_20260921_154029`：历史 stereo config 含当前 WASS 1.11 不接受的 `RECTIFICATION_ALPHA`，状态 `FAILED_AT_STEREO_000000`；
- `run_20260921_154636`：前三帧成功，第四帧在官方 plane RANSAC 报 `0 best inliers`，状态 `FAILED_AT_STEREO_000003`。

没有为失败帧调 WASS 参数。正式 HomeTank 示例固定为连续三帧最小批次。

## 5. 统一性、审计与结果解释

两套数据调用同一个 `pipeline/run_pipeline.py`，差异只在 YAML：作者样例的同步/内参是 provided；HomeTank 从原始视频计算并显式使用 fallback。每次运行保存：

- 完整 YAML 快照；
- Git commit；
- 输入与工具 SHA256；
- 实际 argv、cwd、stdout、stderr、返回码和耗时；
- 标定、同步、WASS、surface、pixel 与 visualization 产物；
- 成功或 `FAILED_AT_<stage>` 状态。

高度遵循 `H=nᵀP+d`。在官方 wassgridsurface 对齐后的坐标中，`n=(0,0,1), d=0`，所以 `H=Z`。Hover 中当前有限像素全部标为 `OFFICIAL_GRID_ESTIMATE`；无数据像素保持 `NO_DATA`，没有声明为直接观测，也没有自研插值补全。

## 6. 未来 GoPro

`pipeline/config.example.yaml` 和 `run_gopro.ps1` 已提供。新数据只需复制 YAML 并更换原始标定视频、测量视频、棋盘规格与 baseline 路径；科学计算顺序及 Python 源码无需修改。新 GoPro 不继承 HomeTank fallback，必须重新标定和 autocalibrate。

