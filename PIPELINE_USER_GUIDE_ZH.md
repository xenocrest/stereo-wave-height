# Vieira / WASS 最小复现 Pipeline 使用说明

## 1. 这条主线做什么

本项目现以“官方科学工具链的可重复编排”为主线，不再继续开发桌面 GUI。Python 代码负责读取 YAML、准备目录、调用官方程序、保存日志和展示结果；不实现 stereo matching、三角化、自动外参或水面插值。另设独立的固定参考面与瞬时真值比较层；指定静水帧的参考面拟合只定义外部零位，不回写 WASS 或官方网格。

固定顺序为：

`OpenCV 内参 → wass_lowcost TLCC 同步 → WASS prepare → match → autocalibrate → stereo → wassgridsurface → wassncplot → 只读可视化`

对应官方资料：

- [WASS Getting Started](https://www.dais.unive.it/wass/documentation/getting_started.html)
- [WASS 官方仓库](https://github.com/fbergama/wass)
- [WASS Quick-start Guide](https://www.dais.unive.it/wass/WASS_quickstart_guide.pdf)
- [wass_lowcost 作者仓库](https://github.com/matheusdpv/wass_lowcost)

第三方科学算法修改数：**0**。

## 2. 一键运行

在仓库根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\run_vieira_official.ps1
```

或：

```powershell
powershell -ExecutionPolicy Bypass -File .\run_hometank_demo.ps1
```

脚本只调用 `pipeline/run_pipeline.py` 和对应 YAML。每次运行都新建时间戳目录，不覆盖历史结果。官方工具失败时状态写为 `FAILED_AT_<stage>`，保存 traceback、命令、stdout、stderr、返回码和耗时后立即停止。

## 3. 两种输入

### 3.1 已同步图像序列

`examples/vieira_official.yaml` 使用作者公开的左右 TIFF。图片按原字节复制，不转成 MP4；同步状态为 `PROVIDED`。作者提供四个 K/D XML 和 matcher/stereo 配置，但没有 R/T，所以程序仍真实执行 WASS match 与 autocalibrate。

作者样例没有公布可核验的实测基线。配置中的 `baseline_m: 1` 仅定义基线归一化单位 B，结果显示 `H/B`，不得解释为米或毫米。

### 3.2 原始左右视频

`examples/hometank004.yaml` 从四个原始视频开始：

1. 对左右标定视频分别调用 OpenCV `findChessboardCornersSB`、`cornerSubPix`、`calibrateCamera`；
2. 对波浪视频调用 wass_lowcost 的 FFmpeg/Praat TLCC 流程；
3. 按时间戳提取新的同步帧；
4. 执行完整 WASS 外参尝试；
5. HomeTank 已知布局不适合当前官方 WASS dense stereo，因此 YAML 显式切换可追溯的完整历史 K/D/R/T bundle。新 K/D 不与旧 R/T 混用，T 不手改；
6. 对固定的连续三帧运行官方 stereo 和官方后处理。

HomeTank 的 fallback 位置：

`D:/stereo-wave-height-runs/HomeTank_004/wave-reconstruction-pipeline-20260824/wass_workspace/config`

与当前 WASS 1.11 兼容的 stereo 配置也在 YAML 中显式记录。失败的五帧尝试保留，第四帧在官方 WASS plane RANSAC 内以 `0 best inliers` 停止；没有为它调参或伪造输出。

## 4. 输出目录

每次运行位于：

```text
D:/stereo-wave-height-runs/pipeline/<project>/run_YYYYMMDD_HHMMSS/
```

主要内容：

```text
config_snapshot.yaml
calibration/              K/D、R/T、角点、RMS、report.json
sync/                     sync.json、左右同步帧
wass/                     官方 config、workspaces、autocal 尝试
reconstruction/           XYZC、PLY、诊断图
surface/                  plane.json、config.mat、gridded.nc
visualization/            overlay、高度图、点云和交互 HTML
pixel/pixel_xyz/           wassncplot 官方 MAT 映射
pixel/pixel_height/        H 数组和 provenance
logs/                     每条实际命令及 stdout/stderr
run_report.json            总状态、hash、版本、耗时、返回码
```

## 5. 高度和 Hover 的含义

WASS raw 点云的参考面形式为：

```text
H = nᵀP + d
```

`wassgridsurface` 将点云变换到官方 mean-sea-plane 坐标后，参考面为 `Z=0`，因此：

```text
n = (0,0,1), d = 0, H = Z
```

`pixel/pixel_height/*.npz` 保存 `xyz`、`height`、`source`、单位和公式。来源码严格区分：

- `0 = NO_DATA`
- `1 = DIRECT_STEREO`（预留；当前官方像素映射没有把稠密网格点声明为直接观测）
- `2 = OFFICIAL_GRID_ESTIMATE`

运行：

```powershell
D:\stereo-wave-height-runs\wassgridsurface-0.11.4-venv\Scripts\python.exe `
  .\pipeline\visualization\view_results.py <run_dir>
```

浏览器中的 Hover 显示 `(u,v)、X、Y、Z、H、source`。还可打开 `pipeline/notebooks/inspect_results.ipynb`，替换首个单元格里的 `RUN_DIR`。

## 6. 新 GoPro 数据

复制 `pipeline/config.example.yaml` 为 `examples/gopro_experiment_001.yaml`，只需填写：

- 左右标定视频；
- 左右测量视频；
- 棋盘格规格；
- 实测 baseline；
- 工具路径（如果安装位置变化）。

然后运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\run_gopro.ps1 .\examples\gopro_experiment_001.yaml
```

不需要修改 Python 源码。新 GoPro rig 不应继承 HomeTank fallback。

## 7. 结论边界

Pipeline PASS 表示输入、官方计算、产物和展示链能够重复执行，不等于独立物理精度验证通过。`wassncplot` 的有限像素是官方连续网格估计，不是“每个像素都有直接双目观测”。程序不填补 `NO_DATA`，不偷偷换参数，不用邻帧结果代替失败帧。

