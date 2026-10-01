# 离线基础桌面程序

此界面只组织并展示冻结的 `pipeline/` 科学流程；不修改 WASS、wass_lowcost、OpenCV 标定算法、wassgridsurface 或 wassncplot。

## 启动

在仓库根目录用已安装 PySide6 的科学环境运行：

```powershell
& 'D:\stereo-wave-height-runs\wassgridsurface-0.11.4-venv\Scripts\python.exe' -m app.main
```

可传项目 YAML：`python -m app.main examples/hometank004.yaml`。新项目在界面选择左右标定视频、填写棋盘参数和实际双目基线、选择左右测量视频；所有视频路径、输出路径及 fallback 由项目 YAML 管理，应用源码不含 HomeTank 路径。科学工具位置也在项目 YAML 中配置。

工作次序：打开/新建项目 → 标定 → TLCC 同步 → 暂停选择静水参考时刻（或导入已配准的固定平面）→ 暂停测量帧 → 解算 → 查看原图、WASS 点云、按官方像素↔XYZ 映射得到的叠加图及 hover 数值。首次指定的静水帧应由用户核实为真正静水；程序不会自动识别静水。重新打开一个科学运行时可以在界面选择其 `run_report.json`。

首次解算后显示参考候选的 n/d、源帧和时间，点击“确认并冻结参考面”才开放高度显示/导出；身份保存到项目 YAML 及项目旁的 reference_plane.json。随后待测帧允许独立运行：复用已冻结标定/外参和官方 config.mat，用官方 prepare/stereo 与 grid --gridsetup 重建，不重新 setup 或改变参考面。每次比较 calibration_id、extrinsics_id、coordinate_frame_id，未绑定或不一致则在 H 计算前拒绝 REFERENCE_FRAME_MISMATCH。原有批次缓存仍可使用；官方 stereo 失败仍真实报错。

“设置测量区域”提供可选矩形，默认 NONE；仅限制彩色叠加、hover 和 CSV 导出，不改变 WASS 输入、原始点云或算法。当前坐标映射尚不足以将 GUI 原图矩形严格转换成官方去畸变图 mask，所以不接入科学 ROI。几何公共区域明确显示 COMMON_REGION_NOT_AVAILABLE，不把它与用户测量区或高度可用区混称。[官方坐标核验](../docs/WASS_COMMON_REGION_COORDINATES_ZH.md)。

“导出当前帧结果”保存 current_frame.png、overlay.png、pointcloud.ply、instantaneous_height.csv 和 metadata.json。PLY 原样保留全部官方点，CSV 仅包含测量框内已有有限 XYZ/H 的像素，保留 OFFICIAL_GRID_ESTIMATE/NO_DATA 来源区别。原图与官方映射图可能尺寸不同，CSV 像素坐标属于官方映射图。切帧/播放/换输入会隐藏旧结果，不能导出 stale 高度。“检查工具链”只检查配置的运行环境及已安装工具，不下载或安装。

之前的多帧、ROI、导出及输入层验收见 [收尾记录](acceptance/hometank004_20260928/MULTIFRAME_READINESS.md)，其中跨运行限制描述的是该轮旧状态。固定坐标功能仍不代表任意新设备科学重建或物理准确度必定通过。

固定坐标 A/B/C 独立运行、身份负例和最终新输入验收见 [固定坐标闭环记录](acceptance/FIXED_COORDINATE_FRAME_20261001.md)。

如需复核已有运行，可使用：

```powershell
python -m app.main examples/hometank004.yaml --inspect-run D:\path\to\run_report.json --reference-time 20 --target-time 21
```

这只是查看已有官方结果，不算新重建。新重建须点击“解算当前暂停帧”，运行冻结的完整 pipeline。每次运行使用独立目录，保留官方输出、日志、所用视频帧及时间戳。科学子进程使用清理过的环境变量。

## 数据解释与限制

- 青色轮廓是**官方像素映射中实际具有有限 XYZ 的区域**，不是自动识别的水面，也不是“全部双目可见像素”。非水面结构仍可能出现。
- `OFFICIAL_GRID_ESTIMATE` 来自 wassgridsurface/wassncplot；不可称为直接双目观测。`NO_DATA` 不填值。当前冻结 pipeline 的直接像素来源计数为 0，因此 `DIRECT_STEREO` 可能不出现。
- HomeTank_004 示例明确启用完整历史 K/D/R/T bundle fallback；界面持续标为 `EXTRINSICS_FALLBACK`，不能说是当前棋盘重新算出的外参。
- 不同官方 setup 的坐标不能混用；只有实际冻结相同标定/外参/官方 setup 的独立运行才能复用平面。相机移动、重新标定或单位改变会导致身份不匹配；本版本不做跨不同标定坐标的注册。
- 官方结果可能包含池壁、尺子等非水面点；此界面不自行过滤、补洞或提升覆盖率，也不声明像素高度达到物理准确度验证。
- 公开视频样例没有度量基线（单位 `B`），不能转换为毫米；GUI hover 对它不会给出伪造的 `H_mm`。

## 运行检查

```powershell
& 'D:\stereo-wave-height-runs\wassgridsurface-0.11.4-venv\Scripts\python.exe' -m unittest tests.test_offline_basic_app tests.test_pipeline_vieira_wass tests.test_instantaneous_validation -v
```
