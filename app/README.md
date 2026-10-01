# 离线基础桌面程序

此界面只组织并展示冻结的 `pipeline/` 科学流程；不修改 WASS、wass_lowcost、OpenCV 标定算法、wassgridsurface 或 wassncplot。

## 启动

在仓库根目录用已安装 PySide6 的科学环境运行：

```powershell
& 'D:\stereo-wave-height-runs\wassgridsurface-0.11.4-venv\Scripts\python.exe' -m app.main
```

可传项目 YAML：`python -m app.main examples/hometank004.yaml`。新项目在界面选择左右标定视频、填写棋盘参数和实际双目基线、选择左右测量视频；所有视频路径、输出路径及 fallback 由项目 YAML 管理，应用源码不含 HomeTank 路径。科学工具位置也在项目 YAML 中配置。

工作次序：打开/新建项目 → 标定 → TLCC 同步 → 暂停选择静水参考时刻（或导入已配准的固定平面）→ 暂停测量帧 → 解算 → 查看原图、WASS 点云、按官方像素↔XYZ 映射得到的叠加图及 hover 数值。当前帧的固定参考与待测帧进入**同一次**官方 gridding 运行，以避免跨运行的坐标系不一致。首次指定的静水帧应由用户核实为真正静水；程序不会自动识别静水。重新打开一个科学运行时可以在界面选择其 `run_report.json`。

首次解算后显示参考候选的 n/d、源帧和时间，点击“确认并冻结参考面”才开放高度显示/导出；确认信息保存到项目 YAML，重新打开项目时核验输入及实际 K/D/R/T 身份并恢复，不能自动换面。导入的物理参考必须说明来源科学运行及其坐标注册。冻结后只可查询该官方运行中已处理的帧。首次解算前可设“同次官方运行帧数”，在参考时刻与当前暂停时刻之间均匀取这一批帧；这不是任意后续时刻都能独立解算并沿用旧平面的承诺。

“设置测量区域”提供可选矩形，默认 NONE；仅限制彩色叠加、hover 和 CSV 导出，不改变 WASS 输入、原始点云或算法。当前坐标映射尚不足以将 GUI 原图矩形严格转换成官方去畸变图 mask，所以不接入科学 ROI。程序分别标注几何公共区域（COMMON_STEREO_REGION，当前 UNKNOWN）、用户测量区和当前帧具有输出的区域，不把三者混称。

“导出当前帧结果”保存 current_frame.png、overlay.png、pointcloud.ply、instantaneous_height.csv 和 metadata.json。PLY 原样保留全部官方点，CSV 仅包含测量框内已有有限 XYZ/H 的像素，保留 OFFICIAL_GRID_ESTIMATE/NO_DATA 来源区别。原图与官方映射图可能尺寸不同，CSV 像素坐标属于官方映射图。切帧/播放/换输入会隐藏旧结果，不能导出 stale 高度。“检查工具链”只检查配置的运行环境及已安装工具，不下载或安装。

多帧、ROI、导出及新输入层验收见 [2026-10-01 收尾记录](acceptance/hometank004_20260928/MULTIFRAME_READINESS.md)。尚未证明跨独立官方运行的永久参考面注册，不能把输入层通过称为任意新设备科学重建通过。

如需复核已有运行，可使用：

```powershell
python -m app.main examples/hometank004.yaml --inspect-run D:\path\to\run_report.json --reference-time 20 --target-time 21
```

这只是查看已有官方结果，不算新重建。新重建须点击“解算当前暂停帧”，运行冻结的完整 pipeline。每次运行使用独立目录，保留官方输出、日志、所用视频帧及时间戳。科学子进程使用清理过的环境变量。

## 数据解释与限制

- 青色轮廓是**官方像素映射中实际具有有限 XYZ 的区域**，不是自动识别的水面，也不是“全部双目可见像素”。非水面结构仍可能出现。
- `OFFICIAL_GRID_ESTIMATE` 来自 wassgridsurface/wassncplot；不可称为直接双目观测。`NO_DATA` 不填值。当前冻结 pipeline 的直接像素来源计数为 0，因此 `DIRECT_STEREO` 可能不出现。
- HomeTank_004 示例明确启用完整历史 K/D/R/T bundle fallback；界面持续标为 `EXTRINSICS_FALLBACK`，不能说是当前棋盘重新算出的外参。
- 官方 gridding 会建立运行内的对齐坐标。用户所选静水参考只在**同一运行**的帧间复用。应用拒绝跨独立运行直接套用该内部参考面。新设备需要可追溯的物理参考和坐标注册才能证明跨运行长期固定参考成立。
- 官方结果可能包含池壁、尺子等非水面点；此界面不自行过滤、补洞或提升覆盖率，也不声明像素高度达到物理准确度验证。
- 公开视频样例没有度量基线（单位 `B`），不能转换为毫米；GUI hover 对它不会给出伪造的 `H_mm`。

## 运行检查

```powershell
& 'D:\stereo-wave-height-runs\wassgridsurface-0.11.4-venv\Scripts\python.exe' -m unittest tests.test_offline_basic_app tests.test_pipeline_vieira_wass tests.test_instantaneous_validation -v
```
