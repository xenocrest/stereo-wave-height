# 离线基础桌面程序

此界面只组织并展示冻结的 `pipeline/` 科学流程；不修改 WASS、wass_lowcost、OpenCV 标定算法、wassgridsurface 或 wassncplot。

## 启动

在仓库根目录用已安装 PySide6 的科学环境运行：

```powershell
& 'D:\stereo-wave-height-runs\wassgridsurface-0.11.4-venv\Scripts\python.exe' -m app.main
```

可传项目 YAML：`python -m app.main examples/hometank004.yaml`。新项目在界面选择左右标定视频、填写棋盘参数和实际双目基线、选择左右测量视频；所有视频路径、输出路径及 fallback 由项目 YAML 管理，应用源码不含 HomeTank 路径。科学工具位置也在项目 YAML 中配置。

工作次序：打开/新建项目 → 标定 → TLCC 同步 → 暂停选择静水参考时刻（或导入已配准的固定平面）→ 暂停测量帧 → 解算 → 查看原图、WASS 点云、按官方像素↔XYZ 映射得到的叠加图及 hover 数值。当前帧的固定参考与待测帧进入**同一次**官方 gridding 运行，以避免跨运行的坐标系不一致。首次指定的静水帧应由用户核实为真正静水；程序不会自动识别静水。重新打开一个科学运行时可以在界面选择其 `run_report.json`。

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
