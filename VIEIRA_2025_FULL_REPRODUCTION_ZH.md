# Vieira 2025 原始数据全流程独立复现报告

状态：`BLOCKED_AT_OFFICIAL_WASS_STEREO`  
日期：2026-09-16  
全新运行目录：`D:\stereo-wave-height-runs\vieira2025-full-repro-20260916`

## 1. 结论先行

本轮从原始棋盘视频、原始波浪视频和原始音轨重新开始，没有读取旧 K/D、旧 R/T、旧同步、旧 WASS workspace、旧 match、旧 XYZ、旧参考面、旧 pixel-XYZ、旧高度或旧 `gridded.nc`。

实际完成了：

1. Vieira 2025 原文、`wass_lowcost` 和 WASS 官方资料核验；
2. HomeTank_004/005/006 原始标定素材审计；
3. HomeTank_004 与 005 的 OpenCV 单相机内参重算；
4. HomeTank_004 原始音轨的官方 Praat TLCC；
5. 两批各 20 对新同步帧的 WASS `prepare → match → autocalibrate`；
6. 对全部 workspace 真正调用官方 `wass_stereo`。

最终没有得到新的 XYZ。两批 autocalibration 都把物理上应以水平分量为主的基线估计成竖直分量为主，官方 `wass_stereo` 对 40 次调用均在 `Vertical stereo not supported` 停止。因此 `wassgridsurface`、`gridded.nc`、`wassncplot` 和 pixel↔XYZ 均未运行。继续这些后处理只能以伪造/替换外参为前提，违反本任务约束。

这不是一次“成功的 Vieira 全复现”，而是一次从原始数据开始、在官方 stereo 门禁处得到可复核失败证据的独立复现尝试。

## 2. 方法核验

权威来源：

- Vieira et al. (2025), *Nearshore space-time ocean wave observation using low-cost video cameras*, DOI: [10.1016/j.coastaleng.2024.104694](https://doi.org/10.1016/j.coastaleng.2024.104694)。本轮保存的开放获取原文 SHA-256 为 `08AE2259DFBDE33A503315BE830DBE4C53E3E752E9874ED2241AF274B7A7EF41`。
- [`matheusdpv/wass_lowcost`](https://github.com/matheusdpv/wass_lowcost)，核验时 `main=688dfaf1d88f270cf3d7cd3db4b49369ebe52871`。
- [`fbergama/wass`](https://github.com/fbergama/wass)，核验时 `master=dcd57115fb416dca1b49a994d5292295c0d19494`。
- 本机官方 WASS 二进制：`1.11_heads/master-0-g6b82aeb`，OpenCV 4.6.0。

论文第 2.3 节明确给出：

- 内参：OpenCV camera calibration，约 50 张不同距离、不同角度的棋盘图像；
- 同步：音频 time-lagged cross-correlation（TLCC）；
- 外参：WASS auto-calibration；
- 重建：WASS stereo；
- 表面：WASS 点云之后再做规则网格化，插值网格不等于直接测量支持。

`wass_lowcost` 的公开脚本进一步确认了实现细节：48 kHz 双声道 PCM、101 tap/1000 Hz FIR 高通、Praat `Cross-correlate: "peak 0.99", "zero"` 和 `Sinc70` 峰值定位。WASS 官方链路为 `prepare → match → autocalibrate → stereo`；官方文档要求相机并排、光轴近似平行。

## 3. 原始数据审计

以下“帧数”为容器/解码器报告值，不是历史导出图片数。

| 数据集 | 原始标定 LEFT / RIGHT | 分辨率 | 标称 fps | 帧数 LEFT / RIGHT | 原始音轨 | 与 wave 相机模式 | 完整棋盘快速检测 |
|---|---|---:|---:|---:|---|---|---:|
| HomeTank_004 | `videos/calibration/calibration_cam0_iQOO_Neo5S.mp4` / `calibration_cam1_iQOO_Z10_TurboPlus.mp4` | 1920×1080 | 60 / 60 | 6968 / 7040 | 48 kHz stereo | 同分辨率、同标称帧率；LEFT 有 VFR 痕迹 | 96 / 132（2 Hz 审计） |
| HomeTank_005 | `videos/calibration/HomeTank_005_calibration_cam0_LEFT.mp4` / `...cam1_RIGHT.mp4` | 1920×1080 | 29.97 / 30 | 4302 / 4300 | 48 kHz stereo | 同分辨率、同标称帧率；LEFT 有 VFR 痕迹 | 75 / 38（2 Hz 审计） |
| HomeTank_006 | `videos/calibration/HomeTank_006_calibration_cam0_LEFT.mp4` / `...cam1_RIGHT.mp4` | 3840×2160 | 29.97 / 30 | 3267 / 3258 | 48 kHz stereo | 同分辨率、同标称帧率；LEFT 有 VFR 痕迹 | 2 / 1（2 Hz 审计） |

棋盘物理记录为 9×6 内角点、20 mm 格长。HomeTank_006 的标准完整棋盘观测数量远低于 OpenCV 标定所需，不能用于本轮内参。004/005 的棋盘都主要位于画面中部，边缘/角落覆盖不足；视频容器不记录可验证的逐帧焦距、变焦或 autofocus 状态，因此只能记为未决风险，不能假称“固定焦距已验证”。

HomeTank_005 更清晰，但正式求解后左右主点分别漂到 `cx=520.45 px` 与 `cx=1414.14 px`，说明中部窄覆盖导致内参退化。HomeTank_004 的左右焦距和主点更一致、完整检测更多，且有独立记录的 70 mm 物理基线，因此选 004 继续官方链路。

## 4. 全新 OpenCV 内参

实现只调用 OpenCV `findChessboardCornersSB`、`cornerSubPix` 和 `calibrateCamera`。从原始视频以 5 Hz 均匀抽样，先保留所有完整 9×6 检测，再按棋盘中心、尺度、方向和透视变化做确定性最远点选择；不使用重投影误差选帧，不人为删除“难看”视图。

| 数据集 / 相机 | 完整检测 | 入模视图 | RMS (px) | fx / fy (px) | cx / cy (px) | 单视图最大 RMS (px) |
|---|---:|---:|---:|---:|---:|---:|
| 004 LEFT | 242 | 50 | 4.1595 | 1522.607 / 1522.069 | 982.122 / 636.661 | 7.470 |
| 004 RIGHT | 328 | 50 | 5.3870 | 1559.587 / 1527.371 | 1106.865 / 582.690 | 21.257 |
| 005 LEFT（排除候选） | 179 | 50 | 4.3026 | 2323.819 / 2189.724 | 520.453 / 408.856 | 5.780 |
| 005 RIGHT（排除候选） | 87 | 50 | 3.5741 | 2262.015 / 2113.052 | 1414.142 / 553.109 | 6.677 |

004 的 RMS 仍然很高。原始画面显示棋盘为手工涂黑、边界不规则且板面可能弯曲；同时视图覆盖集中。这些是针孔模型输入不足的直接证据，报告保留该风险，没有用固定主点、人工删帧或旧 K/D 把结果“修漂亮”。

## 5. 全新 TLCC 同步

HomeTank_004 原始波浪视频：

- LEFT：`wave_cam0_iQOO_Neo5S.mp4`，1920×1080，名义 60 fps，平均约 59.29 fps，9556 帧；
- RIGHT：`wave_cam1_iQOO_Z10_TurboPlus.mp4`，1920×1080，名义 60 fps，平均约 60 fps，9670 帧；
- 两边均有 48 kHz 双声道音轨。

Praat TLCC 在 0–30 s 音频窗得到：

```text
tau = -0.07507001632731439 s
tau × 60 = -4.5042009796 nominal frames
```

Praat 定义 `cross_corr(left,right)(tau)=∫left(t)right(t+tau)dt`，所以新帧对应采用：

```text
t_right = t_left + tau
```

本轮分别生成 10–19.5 s 静水/标尺段和 90–99.5 s 起波段，每段 2 Hz、20 对无损 PNG。每一对的左右请求时间写入各自 `sync_result.json`。没有使用历史 frame lag 或历史导出帧。

## 6. WASS 官方执行结果

### 6.1 静水/标尺段（10–19.5 s）

- 新 workspace：20；
- `prepare`：20/20 成功；
- `match`：20/20 成功；
- autocalibration 载入：774 matches；
- Essential RANSAC：646 inliers；
- triangulation：646 positive-depth points；
- SBA 后 epipolar error：`0.504368 ± 0.442165 px`；
- 新外参单位平移：`T=[0.0678609, 0.5851330, -0.8080930]`，`||T||=1`；
- `stereo`：0/20 成功，全部报 `Vertical stereo not supported`。

### 6.2 实际起波段（90–99.5 s）

- 新 workspace：20；
- `prepare`：20/20 成功；
- `match`：20/20 成功；
- autocalibration 完成；
- triangulation：438 positive-depth points；
- SBA 后 epipolar error：`0.599527 ± 0.554371 px`；
- 新外参单位平移：`T=[0.0556037, 0.9167248, -0.3956311]`，`||T||=1`；
- `stereo`：0/20 成功，全部报 `Vertical stereo not supported`。

两批均已真正运行 autocalibrate，且都没有读取或复制旧 `ext_R.xml/ext_T.xml`。第二批排除了“只因选到静水标尺段”的解释，但基线方向仍然错误。官方匹配图显示保留下来的特征主要落在标尺、水槽壁、边界及槽底纹理，而不是形成足够三维约束的可追踪波面结构；再叠加高 RMS 内参，Essential 分解得到低像素残差但物理方向错误的外参。这正是只看 epipolar error 会漏掉的几何退化。

## 7. 停止条件与未执行步骤

官方 `wass_stereo` 明确拒绝竖直主导的外参。若继续，只能采取以下被任务禁止的行为之一：

- 人工把 T 改成水平；
- 复制旧 R/T；
- 旋转/置换坐标来掩盖错误的物理基线；
- 绕过官方门禁或重写 stereo；
- 在没有新 XYZ 时伪造 plane/grid/mapping。

因此以下项目均为 `NOT_RUN_NO_NEW_XYZ`：

- 每帧 XYZ / finite / positive-depth / spatial support 统计；
- mean sea plane；
- `wassgridsurface` / `gridded.nc`；
- `wassncplot` / savexyz；
- pixel↔XYZ 闭环；
- overlay、高度范围、direct support 与 DCT grid 分离评价；
- 跨帧公共坐标稳定性；
- 历史 pipeline 与 Vieira full reproduction 比较。

历史比较被有意跳过，因为用户要求只有完整新流程跑完以后才允许比较。本轮没有达到该前提。

## 8. 现有资料缺少什么

按照针孔模型和 Vieira/WASS 官方假设，要可靠完成全链路，现有原始资料缺少：

1. 覆盖全画幅、不同距离/角度、刚性平整且几何准确的左右相机原始棋盘观测；
2. 可验证的固定焦距/固定变焦状态；
3. 能让 WASS autocalibration 恢复水平主导基线的非退化共同特征观测。

HomeTank_006 虽为 4K，但标准完整棋盘几乎不可检测；HomeTank_005 的内参因窄覆盖退化且没有本轮可采用的独立物理基线；HomeTank_004 有物理基线和最多完整检测，但棋盘几何/覆盖质量不足，WASS autocalibration 连续两批给出不兼容的基线方向。

结论不是“可以从旧资料可靠恢复，只差调参”，而是：在不借用旧标定、不篡改外参、不重写 WASS 的约束下，现有原始资料不足以完成 Vieira 2025 全流程并产生可信的新高度结果。

## 9. 新产物位置

所有运行产物均位于：

```text
D:\stereo-wave-height-runs\vieira2025-full-repro-20260916\
├── sources\                 论文、官方源码快照、Praat
├── audit\                   三组原始标定 QA 与时间轴图像
├── calibration\             全新检测、50 视图、角点、RMS、K/D、WASS XML
├── sync\                    TLCC 音频、Praat 脚本、同步帧、逐帧时间映射
└── wass\                    两批全新 workspaces、match、autocalibration、stereo 日志
```

复现包装脚本：

- `tools/vieira_intrinsics_from_raw.py`
- `tools/vieira_tlcc_sync.py`
- `tools/vieira_wass_full_run.py`

这些脚本只负责调用 OpenCV、FFmpeg、Praat 和未修改的 WASS 官方二进制并记录 provenance；没有实现替代 stereo、MLS、FoundationStereo、人工高度或 GUI。
