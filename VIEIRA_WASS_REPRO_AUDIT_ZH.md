# Vieira/WASS 成熟方案复现：首轮审计与官方后处理实测

日期：2026-09-14

工作分支：`repro/vieira-wass-baseline`

起始提交：`2acf2408c94f3dcbe6ca154d9d3b1b864bde10de`

## 结论先行

本轮实现了零次 WASS 重算条件下的官方后处理闭环：历史 Classic WASS `mesh_cam.xyzC` 和逐帧 `plane.txt` 成功进入官方 `wassgridsurface 0.11.4`，生成五帧 NetCDF；随后官方 `wassncplot 2.5.3` 成功生成叠加图及图像像素到三维坐标的 `.mat` 映射。

但是，本轮结果只能判定为：

`TOOLCHAIN_CLOSURE_PASS_MEASUREMENT_VALIDITY_FAIL`

原因不是工具报错，而是输入证据不满足测量条件：HomeTank_004 的标定文件明确写着 `CALIBRATION_QUALITY_FAIL` 和 `approved_for_wass: false`；严格帧级同步未建立；被复用的五帧历史流水线没有执行 WASS `autocalibrate`；源点只占规则网格的 14.6%–24.3%。官方 DCT 对无观测区也会外推，最终全网格出现 -271.26 mm 到 +284.43 mm，并且官方叠加图没有落在正确水面区域。因此这些数值不得作为水面高度或 `<1 cm` 精度证据。

## A. Git 与本机环境

| 项目 | 实测结果 |
| --- | --- |
| 起始分支 | `main` |
| 起始 HEAD | `2acf2408c94f3dcbe6ca154d9d3b1b864bde10de` |
| 起始 workspace | clean |
| 最近提交 | `2acf240`、`45f7e60`、`cd0727e`、`af9547e`、`c283252` |
| 当前隔离分支 | `repro/vieira-wass-baseline` |
| Classic WASS | `D:\wass\dist\bin`，版本 `1.11_heads/master-0-g6b82aeb`，运行时 OpenCV 4.6.0 |
| WASS 源码副本 | `D:\wass_diagnostic`，官方 remote，HEAD `6b82aeb...`；该副本原先已有未提交修改，本轮未使用它构建或改动 |
| wasscli | 未安装为可执行命令；官方源码存在于 `D:\wass_diagnostic\cli\wasscli\wasscli.py` |
| wassgridsurface | `D:\stereo-wave-height-runs\wassgridsurface-0.11.4-venv`，版本 0.11.4 |
| wassncplot | 审计开始时不存在；按官方 PyPI 方式仅安装 2.5.3 到上述隔离 venv，未改系统 Python |
| FFmpeg | `D:\FormatFactory\ffmpeg.exe`，7.1 |
| ffprobe | `D:\lol\WeGameApps\rail_apps\DeltaForce(2001918)\icreate\recorder-release\ffprobe.exe` |
| 项目 Python | `D:\python\python.exe`，3.12.5 |
| 项目 OpenCV / NumPy / SciPy | 5.0.0 / 2.1.1 / 1.14.1 |

## B. 手机水槽数据审计

以下 CFR/VFR 只表示 `r_frame_rate` 与 `avg_frame_rate` 的容器元数据是否一致，不等于逐包 PTS 已完成严格证明。全部 14 个视频均有音轨。HomeTank_001–003 目录存在，但未检出 MP4。

路径前缀均为 `experiments/real_video/<数据集>/videos/`。

| 数据集 | 类型 | 相机 | 相对路径 | MiB | 分辨率 | 编码 | nominal/average fps | 时长 s | 帧数 | 元数据时基 |
| --- | --- | --- | --- | ---: | --- | --- | --- | ---: | ---: | --- |
| 004 | calibration | LEFT | `calibration/calibration_cam0_iQOO_Neo5S.mp4` | 305.2 | 1920×1080 | H.264 | 60/59.31 | 117.49 | 6968 | VFR |
| 004 | calibration | RIGHT | `calibration/calibration_cam1_iQOO_Z10_TurboPlus.mp4` | 103.0 | 1920×1080 | HEVC | 60/60.00 | 117.34 | 7040 | VFR |
| 004 | static | LEFT | `static/static_cam0_iQOO_Neo5S.mp4` | 142.3 | 1920×1080 | H.264 | 60/59.36 | 54.67 | 3245 | VFR |
| 004 | static | RIGHT | `static/static_cam1_iQOO_Z10_TurboPlus.mp4` | 47.9 | 1920×1080 | HEVC | 60/60.02 | 54.67 | 3281 | VFR |
| 004 | wave | LEFT | `wave/wave_cam0_iQOO_Neo5S.mp4` | 418.2 | 1920×1080 | H.264 | 60/59.29 | 161.24 | 9556 | VFR |
| 004 | wave | RIGHT | `wave/wave_cam1_iQOO_Z10_TurboPlus.mp4` | 141.5 | 1920×1080 | HEVC | 60/60.00 | 161.17 | 9670 | VFR |
| 005 | calibration | LEFT | `calibration/HomeTank_005_calibration_cam0_LEFT.mp4` | 304.8 | 1920×1080 | H.264 | 29.97/29.98 | 143.51 | 4302 | VFR |
| 005 | calibration | RIGHT | `calibration/HomeTank_005_calibration_cam1_RIGHT.mp4` | 123.9 | 1920×1080 | HEVC | 30/30.00 | 143.34 | 4300 | CFR |
| 005 | wave | LEFT | `wave/HomeTank_005_wave_cam0_LEFT.mp4` | 314.2 | 1920×1080 | H.264 | 29.97/29.97 | 121.01 | 3627 | VFR |
| 005 | wave | RIGHT | `wave/HomeTank_005_wave_cam1_RIGHT.mp4` | 104.4 | 1920×1080 | HEVC | 30/30.01 | 120.75 | 3623 | VFR |
| 006 | calibration | LEFT | `calibration/HomeTank_006_calibration_cam0_LEFT.mp4` | 815.7 | 3840×2160 | H.264 | 29.97/29.98 | 108.98 | 3267 | VFR |
| 006 | calibration | RIGHT | `calibration/HomeTank_006_calibration_cam1_RIGHT.mp4` | 263.0 | 3840×2160 | HEVC | 30/30.00 | 108.60 | 3258 | CFR |
| 006 | wave | LEFT | `wave/HomeTank_006_wave_cam0_LEFT.mp4` | 755.3 | 3840×2160 | H.264 | 29.97/29.97 | 100.94 | 3025 | VFR |
| 006 | wave | RIGHT | `wave/HomeTank_006_wave_cam1_RIGHT.mp4` | 244.8 | 3840×2160 | HEVC | 30/30.00 | 100.80 | 3024 | CFR |

数据级状态：

| 数据集 | 同步 | 标定 | WASS / mesh | PLY | pixel_xyz | reference / height | NetCDF / grid（本轮前） | WASS config |
| --- | --- | --- | ---: | ---: | ---: | --- | --- | --- |
| 004 | 有历史亮度事件与帧级报告；wave 为 `FRAME_LEVEL_SYNC_WARNING`，严格状态未建立 | 有；底层结果为质量失败、未批准 | 67 个 `mesh_cam.xyzC` | 102 | 25 | 有，均带诊断/验证限制 | 独立 `upstream_wassfast` 有 2 个 NC；Classic HomeTank 目录无 NC | 有，145 个相关配置文件 |
| 005 | 有特定请求的按需容差记录，但未找到覆盖全视频的通用官方 TLCC 序列 | 有；`DEMO_ONLY`、几何未验证 | 6 | 13 | 9 | 有演示 reference / height | 无 | 有，34 个相关配置文件 |
| 006 | `CANDIDATE_OFFSETS_NOT_VERIFIED` | 候选几何未验证、未批准 | 12 | 12 | 0 | 仅诊断尝试，不是有效高度 | 无 | 有，28 个相关配置文件 |

## C. 既有 WASS / XYZ / workspace 审计

1. HomeTank_004 的 `wave-reconstruction-pipeline-20260824` 是现有数据中最接近官方“序列目录”的产物：同一目录内有五个 `000000_wd` 至 `000004_wd`，每个都有 `mesh_cam.xyzC`、`plane.txt`、`P0cam.txt`、`P1cam.txt`、内参、图像和 stereo 配置；总点数 955,521。
2. 该流水线历史结果明确记录 `prepare → match → stereo`，但 `autocalibrate_run: false`，并采用了固定外参。这不是官方完整 Classic WASS 序列复现。
3. HomeTank_005 点云数量可观，但主要是多个彼此独立的单帧演示 workspace，没有可直接交给 `wassgridsurface` 的序列级 `planes.txt`，且标定仅供 demo。
4. HomeTank_006 有 12 个点云，但没有 pixel_xyz / NetCDF，标定和同步均未验证；视频中可见纹理被用户确认为槽底痕迹，也不适合作为面向海面的直接表面纹理证据。
5. `D:\stereo-wave-height-runs` 中确实存在大量合成/历史 `gridded.nc`；这证明官方 grid 工具以前运行过，但不能替代对真实 HomeTank 输入的本轮核验。

## D. 官方 Vieira + WASS 流程核验

### D1. 官方能力

官方链条是：

`同步双目帧 → wass_prepare → wass_match → wass_autocalibrate → wass_stereo → mesh_cam.xyzC + plane.txt → wassgridsurface → gridded.nc → wassncplot`

- `wass_prepare` 建工作目录并按内参去畸变。
- `wass_match` 做稀疏特征对应，估计本质矩阵及相机相对 R/T，并按极线一致性筛选。
- `wass_autocalibrate` 的输入不是单张图，而是 `output/workspaces.txt` 所列出的多个已 match workspace；官方 `wasscli.py` 把这些目录交给 SBA，共同优化外参，再写回各 workspace。
- `wass_stereo` 做稠密重建、点云滤波，并对每帧稳健拟合 `plane.txt`。
- `wasscli` 在完整序列 stereo 完成后，把每帧四个平面系数合成 `output/planes.txt`。
- `wassgridsurface` 的 setup 阶段读取 `planes.txt` 并取逐列平均作为公共 mean sea plane，应用实测 baseline 恢复尺度；grid 阶段把各点云变换到该公共平面坐标并插值为 NetCDF 时序表面。
- `wassncplot` 是独立官方工具，不是四个 Classic WASS 可执行文件之一；它读取 NetCDF 做原图叠加，并通过 `--savexyz` 导出图像像素到三维坐标映射。
- Vieira 的 `wass_lowcost` 公开代码主要负责消费级相机视频的音频 TLCC、VFR 重编码/抽帧与同步；它调用 FFmpeg、Praat、OpenCV，并不另写 WASS stereo 或 triangulation。

依据：[WASS 官方仓库](https://github.com/fbergama/wass)、[官方 wasscli 源码](https://raw.githubusercontent.com/fbergama/wass/master/cli/wasscli/wasscli.py)、[wassncplot 官方仓库](https://github.com/fbergama/wassncplot)、[wass_lowcost README](https://github.com/matheusdpv/wass_lowcost)、[公开同步源码](https://raw.githubusercontent.com/matheusdpv/wass_lowcost/main/wass_sync.py)、[Vieira et al. 2020 DOI](https://doi.org/10.3390/jmse8110831)。本机还保存了官方快速指南及 SHA-256：`BFB706ED711E2FC0E0FE021710FEAC23D976A73460A9ACBBEF3E6F31BA151AF4`。

### D2. 数学/物理对应

整流后视差为 `d = u_L - u_R`，理想平行模型深度为 `Z = fB/d`；一阶误差约为 `|δZ| ≈ Z²|δd|/(fB)`。未经良好同步、标定和极线对齐时，视差误差会被平方距离项放大。

WASS 的相机坐标 `Z` 不是水面高度。对单位法向量平面 `nᵀP + d₀ = 0`，有符号法向高度是 `η = nᵀP + d₀`。官方 gridding 不是逐帧任意减一个 reference，而是先由多帧 `plane.txt` 得到统一 mean plane，再把所有点云变换到同一 `(X,Y,η)` 坐标并乘 baseline 恢复物理尺度。

### D3. 旧项目推断或独立功能

- 历史 `external_static_reference_plane` 和自定义 reference-frame 相减不是本轮核实到的官方 mean-plane 流程。
- 历史 `pixel_xyz/*.npz` 是项目自建映射；官方存在对应能力，但载体是 `wassncplot --savexyz` 导出的 `.mat`。
- MLS、RBF、dense completion、GUI 全像素填充均是独立项目功能，不属于 Classic WASS / Vieira low-cost 同步代码，本轮没有使用。
- “输出每个像素就代表每个像素被双目观测”是错误推断。官方快速指南明确提醒 grid 会外推没有 3D 样本的区域，测量应关注中央可靠区域。

### D4. 仍不确定或未通过

- 现有任一 HomeTank 数据都没有同时满足“严格同步 + 质量合格标定 + 官方 autocalibrate + 可审计水面覆盖”。
- HomeTank_004 历史固定外参 workspace 与官方完整 autocalibrated workspace 是否数值等价，当前没有证据。
- 本轮 DCT 全网格、特别是无源点区域的高度不具备物理有效性。
- 独立物理误差 `<1 cm` 尚未建立，不能声明达到。

## E. 首个数据集选择

选择 **HomeTank_004 wave，20.0–20.4 s 的五帧历史序列**，而不是 HomeTank_005。

选择依据是“最少重算且最接近官方序列结构”：004 已有连续五个完整 WASS workdir、955,521 个真实 WASS 点、逐帧平面、投影矩阵、输入图、配置和历史同步说明；005 虽有多个高点数结果，但它们分散在独立单帧演示目录，缺少序列级 planes / mean-plane 输入；006 的标定、同步与表面纹理证据更弱。

本轮复用了全部已有 WASS XYZ，不执行 prepare/match/autocalibrate/stereo。仅在隔离输出目录建立指向冻结 workdir 的目录 junction，并按官方 `wasscli` 行为把五个既有 `plane.txt` 汇总成新的 `planes.txt`。原冻结产物未改写。

## F. 实际执行命令

核心命令如下；完整 stdout/stderr 位于运行目录的编号日志中。

```powershell
git status --short
git branch --show-current
git rev-parse HEAD
git log -5 --oneline

ffprobe -v error -show_entries stream=index,codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,nb_frames:format=duration,size -of json <video>

D:\wass\dist\bin\wass_prepare.exe --help
D:\wass\dist\bin\wass_match.exe --help
D:\wass\dist\bin\wass_autocalibrate.exe --help
D:\wass\dist\bin\wass_stereo.exe --help
D:\stereo-wave-height-runs\wassgridsurface-0.11.4-venv\Scripts\wassgridsurface.exe -h

D:\stereo-wave-height-runs\wassgridsurface-0.11.4-venv\Scripts\python.exe -m pip install wassncplot==2.5.3
D:\stereo-wave-height-runs\wassgridsurface-0.11.4-venv\Scripts\wassncplot.exe -h

wassgridsurface --action generateconfig <isolated-output> <gridding>
wassgridsurface --action setup <isolated-output> <gridding> --gridconfig <gridconfig> --baseline 0.06868471158474378 --fps 10 --stereo_image_idx 0
wassgridsurface --action grid <isolated-output> <gridding> --gridsetup <config.mat> --num_frames 5 --parallel 1 --stereo_image_idx 0
wassncplot <gridded.nc> <out> -f 0 -l 0 --savexyz --save-img --no-textoverlay
```

另用官方 `wassgridsurface.wass_utils.load_camera_mesh` 与 `align_on_sea_plane` 做只读范围和网格占用审计，没有重新实现点云解码或坐标变换。

## G. 实际运行结果

| 阶段 | 结果 | 实测 |
| --- | --- | --- |
| 视频/环境审计 | PASS | 14 个 MP4 全部由 ffprobe 读取 |
| WASS 重算 | 未执行 | 0 次 |
| 官方 mean-plane setup | PASS | 5 帧；mean plane `[-0.431373,-0.097584,0.896157,-5.224790]`；约 5.95 s |
| 官方 DCT grid | 程序 PASS | 5×256×256；约 17.49 s |
| 官方 NetCDF | PASS | 5,155,031 bytes；所有 327,680 个 Z 单元为有限数 |
| 官方 wassncplot | PASS | 5 张叠加图、5 张原图、5 个 pixel↔XYZ `.mat`；约 6.82 s |
| 测量有效性 | FAIL | 投影不落在正确水面；全格高度范围明显受外推影响 |

逐帧源点和规则格直接观测占用：

| 帧 | WASS 点数 | 直接有源点的 grid cells | 256² 占比 |
| --- | ---: | ---: | ---: |
| 000000 | 142,444 | 9,579 | 14.62% |
| 000001 | 221,307 | 15,930 | 24.31% |
| 000002 | 191,312 | 13,844 | 21.12% |
| 000003 | 201,904 | 14,518 | 22.15% |
| 000004 | 198,554 | 13,610 | 20.77% |

官方 NetCDF 的 `Z` 单位由该文件定义为毫米，范围为 -271.257 至 +284.431 mm，均值 -0.0436 mm。数值全覆盖来自 DCT 插值/外推，不等于真实观测全覆盖。官方 `.mat` 的 `px_2_3D` 形状为 `1350×2400×3`，结构上完成了像素映射；由于上游投影与高度未通过，映射只可作格式和调用链证据。

## H. 新产物路径

运行根目录：`D:\stereo-wave-height-runs\vieira-wass-repro-20260914`

- 视频清单：`video_audit.csv`
- 官方快速指南：`WASS_quickstart_guide.pdf`，提取文本为同目录 `.txt`
- 可复现配置：`HomeTank_004_wave_20s\gridding\gridconfig.txt`
- 公共平面输入：`HomeTank_004_wave_20s\output\planes.txt`
- 官方 grid 配置：`HomeTank_004_wave_20s\gridding\config.mat`
- 官方 NetCDF：`HomeTank_004_wave_20s\gridding\gridded.nc`
- 官方面积审查图：`HomeTank_004_wave_20s\gridding\area_grid.png`
- 官方首帧叠加：`HomeTank_004_wave_20s\wassncplot\00000000_grid.png`
- 官方首帧像素映射：`HomeTank_004_wave_20s\wassncplot\00000000.mat`
- 日志：根目录 `01_...log` 至 `10_...log`

仓库内轻量配置：`experiments/real_video/HomeTank_004/vieira_wass_repro_config.yaml`。

## I. 是否需要写代码

当前 **不需要新增核心代码，也不需要 adapter 脚本**。官方工具已经完成 mean-plane、NetCDF、可视化和 pixel↔XYZ 导出。此次仓库改动只有本报告和一份轻量 YAML；没有修改 WASS、stereo、triangulation、reference、MLS、dense 或 GUI。

真正缺少的是合格输入证据，不是缺少另一套算法。用新代码掩盖标定、同步、autocalibration 或覆盖问题会让结果更难审计。

## J. 唯一下一步

**用一组相机姿态固定、标定质量门通过、同步可证明的短真实水面序列，完整执行一次官方 `wasscli: prepare → match → autocalibrate → stereo`，再原样运行本轮已验证的 `wassgridsurface → wassncplot`。**

在这一步通过之前，不再扩展 GUI、dense completion 或替代 matcher，也不宣称高度精度。
