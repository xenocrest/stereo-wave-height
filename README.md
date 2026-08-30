# stereo-wave-height

基于 WASS（Waves Acquisition Stereo System）的双目水面三维形态与高度测量研究项目。最终产品定位为**双目视频输入的按需单帧测量与展示软件**：用户加载左右视频、选择目标时刻，系统提取该时刻的同步帧对并运行一次 WASS 解算。

```text
双目视频（left video + right video）
  → 用户播放、选择并暂停于目标时间 t
  → 同步帧提取 I_left(t), I_right(t)
  → WASS 三维重建 Z(x, y)
  → 坐标、尺度与质量字段适配
  → 静水参考 Z0(x, y)
  → 高度场 H(x, y) = Z(x, y) - Z0(x, y)
  → 误差指标与验收报告
```

近期研究目标是以专业双目相机完成单时刻水面三维测量和独立物理误差验证。这里的“1 cm 级”是待实验验证的验收目标，并非当前已经达到的性能声明。

项目路线、模型体系、Case 0/1/2 结果、结论边界和下一步工作的长期汇报入口见 [项目宏观汇报](PROJECT_OVERVIEW.md)。

当前新增：[双目系统参数设计模型](docs/stereo_system_design/disparity_depth_model.md)，用于指导未来专业双目相机选型和部署参数设计。

## 当前项目状态

当前阶段：**Phase 4：冻结单帧结果的独立物理误差验证**。Phase 3 的 Static/Wave R0 已完成并冻结，当前只允许在其下游接入人工标尺真值。

当前产品输入是左右双目视频，解算单位是一组目标时刻的同步帧。视频保留采集、回放和时刻选择能力；WASS 不随播放实时运行，只在用户发起按需任务后处理所选帧对。路线统一为：

```text
Phase 1  理论模型与合成数据仿真验证（已完成）
  → Phase 2  真实双目系统标定与 WASS 三维重建（已完成首轮闭环）
  → Phase 3  视频输入的按需单帧水面三维测量系统（当前主线）
  → Phase 4  高度计算与独立物理误差验证
  → Phase 5  结果展示软件
  → Phase 6  专业双目相机工程迁移

Extension: Wave video analysis
```

项目定位不是实时视频三维重建系统。视频同步用于确定左右时间对应关系，但不进入 WASS、XYZ 或高度计算；连续 wave、长时批处理与性能分析保留为未来动态测量 Extension。Production mode 当前服务单帧结果保存、按需任务管理和软件接口，并为后续批量扩展保留能力。

Phase 3 核心后端现已从路线设计进入实现：统一请求同时支持“已明确同步的左右图片”和“左右视频 + 用户目标时间”。视频模式使用实际 decoded PTS、显式 $t_R=a t_L+b$ 模型和帧周期质量门选择帧；质量门失败时在 WASS 前终止。HomeTank_004 仍只有粗同步，因此正确返回 `FRAME_LEVEL_SYNC_NOT_ESTABLISHED`，尚未形成单帧真实重建新结果。

HomeTank_004 已进一步完成全帧 PTS 亮度精化：static 仅匹配 2 个共同边沿，wave 匹配 5 个但事件残差 P95 为 13.291 ms（实际帧周期 16.656 ms）。两者仍不足以建立无歧义帧级映射，因此 WASS 质量门继续生效；下一步需要人工确认固定光源 ROI，或在专业系统使用硬触发/硬件时间戳。

在保留上述严格同步结论的同时，已用 $R_{-3}\ldots R_{+3}$ 共 14 组真实 WASS 重建建立按需工程容差：模型预测的 $R_0$ 为 `ACCEPTED`，相邻 ±1 帧为 `WARNING`，$|k|\ge2$ 为 `REJECTED`。正式 static/wave 样例均固定选择 $R_0$ 并完成 XYZ、pixel–XYZ 与 H(x,y)，但物理精度仍未验证。

Phase 3 正式 R0 结果现已完成纯观测分布 QA：raw range、P1–P99/P5–P95、尾部比例、像素空间连通性、support 边缘距离与异常 XYZ 范围均已冻结。Phase 4 首个独立物理验证样例已在不修改重建的前提下完成：冻结局部高度变化为 `-5.7672 mm`，独立标尺变化为 `+0.1 mm`，绝对差异为 `5.8672 mm`。但标尺变化远小于其约 `2.236 mm` 的描述性 RSS 不确定度，且 Wave 局部支持较稀疏，因此本样例不能建立物理精度结论。

Case 1 完整保留。Case 2 的用户尺值与点击已登记，五个冻结 artifact 哈希全部一致；但 canonical `(799,396)` 映射后距最近原始 pixel–XYZ 观测 `15.4946 px`，超过不可变的 `2 px` gate，且 ±1 px 九点全部失败。Case 2 因此分类为 `CASE2_PIXEL_XYZ_DISTANCE_GATE_FAIL`：不扩大搜索、不插值，也不用全局约 `-24.7 mm` 中位数代替尺旁局部值，物理误差保持未计算。

空间 MLS 已通过单点 hold-out 与连续空洞 `hole_2` 内部一致性验证。基于冻结 Case 2 的最小 dense pixel-wise height-map MVP 已完成，输出明确区分 `OBSERVED / ESTIMATED / UNSUPPORTED`；它只证明空间补全与像素输出链成立，不构成独立物理准确度验证。

按需单帧后端现已支持独立的 canonical-cam1 polygon water ROI，并在重建成功后自动调用 dense-height 阶段；`enabled=false` 保持原流程兼容。修正 runtime binding 后，HomeTank_004 Case 2 已从双目视频与目标时间自动完成 WASS、XYZ/H、pixel–XYZ 和三态 dense height 输出，状态为 `SINGLE_FRAME_DENSE_BACKEND_COMPLETED`；该后端现冻结用于下一阶段演示界面集成，物理精度警告仍保留。

在保留全部理想仿真成果和历史失败记录的基础上，最近完成了第一轮真实手机视频处理闭环：

1. **OpenCV 官方双目标定流程接入**
   - 完成双目标定并获得 `K/D/R/T`；
   - 完成标定结果的物理一致性验证；
   - 标定质量门仍为 `CALIBRATION_QUALITY_FAIL`，不能据此宣称实测精度达标。
2. **标定参数与人工测量核对**
   - OpenCV calibrated baseline：68.6847 mm；
   - manual measured baseline：70.0000 mm；
   - difference：1.3153 mm；relative error：1.879%；
   - 人工测量参数仅用于 physical sanity check，实际三维重建采用 OpenCV 标定结果。
3. **OpenCV → WASS 接口适配**
   - 完成标定参数格式转换、相机坐标约定统一和固定标定路径接入；
   - 固定标定 rectification 已闭环，未用人工 baseline 替代标定外参。
4. **手机双目静水三维重建**
   - 已接入 iQOO Neo5S（cam0/left）与 iQOO Z10 Turbo Plus（cam1/right）视频；
   - WASS 的 prepare、match、rectification、dense stereo、triangulation 和单帧静水面检测已跑通；
   - 当前瓶颈是跨帧静水深度稳定性不足，正式状态保持 `STATIC_VALIDATION_FAIL`。

当前主要原因证据为：近距离拍摄使有效视差接近 StereoSGBM 搜索范围上界，水面弱纹理造成匹配支持区域变化，手机 autofocus/EIS 等成像链变化仍待进一步确认。参数审计已证明盲目扩大 disparity 范围或单独调整 uniqueness/block size 不能恢复稳定静水基准。五帧 wave Extension 已运行，但不改变静水失败结论。

真实视频闭环已完成第一轮验证，当前进行面向后续专业双目系统的静水帧一致性分析。

真实视频解算流程现已进入闭环开发阶段：统一命令可从时间戳配对视频调用固定标定 WASS，并输出 XYZ、平面、相对静水参考的高度样本和机器可读结果；这仍是诊断闭环，不代表工程最终完成。

真实波浪视频解算阶段已经开始：HomeTank_004 的五帧 wave 时间序列已完成 WASS 与共享静水参考高度输出，但状态为 `WAVE_PIPELINE_COMPLETED_WITH_STATIC_WARNING`，不能解释为实测波高验收通过。

真实 wave 高度验证模块现已建立：它在共同物理观测域分别保留 raw 与分析性去漂移统计。HomeTank_004 可观察到候选时变信号，但受 97.233 mm 静水跨帧漂移及五帧短记录限制，状态保持 `WAVE_RESULT_NOT_VALIDATED`，不构成工程波高结论。

HomeTank_004 已登记固定竖直刻度尺作为独立物理参考，用于后续验证双目三维尺度、静水漂移和波高。当前缺少双相机共同刻度 ROI、端点与像素到 XYZ 的关联，状态为 `RULER_VALIDATION_INCOMPLETE_MANUAL_REFERENCE_REQUIRED`，尚未形成工程测量结论。

**标尺数据仅用于结果验证，不参与任何三维重建和高度计算流程。Ruler data is only used for independent validation and is not included in the reconstruction pipeline.** 它不进入 WASS、匹配、三角化、参考面生成或 `H(x,y)` 计算。

重建基础接口现已补齐：WASS `mesh_cam.xyzC` 通过每帧 `P0cam` 保存 rectified pixel–XYZ 对应，水面高度统一由三维点到参考平面的有符号正交距离计算。该流程只使用双目图像、标定和 WASS 输出；标尺保持完全独立的下游验证工具。

Wave 结果输出现已统一为物理 ROI 的逐帧 CSV 与机器可读 JSON，包含有效点数、均值、中位数、RMS、P5/P95、范围及不覆盖 raw 的漂移分析序列；独立标尺接口在无人工读数时明确返回 `MANUAL_REFERENCE_REQUIRED`。当前仅有五帧诊断子集，尚未证明长时间稳定或工程测量精度。

完整 161 s wave 全帧运行已完成资源与同步预检，但尚未执行：按现有实测产物模式预计至少 46.29 小时和约 726.83 GB，而预检时 D 盘仅余 65.05 GB；两路约 60 FPS 视频的完整时间映射也未验证。状态为 `BLOCKED_RESOURCE_AND_SYNCHRONIZATION_PREFLIGHT`，未用降采样或五帧结果冒充长时间完成。

当前进入工程化分析阶段：新增通用 WASS 分阶段性能剖析与基于光源变化的视频同步分析。HomeTank_004 三帧组件计时平均为 25.31 s/frame，主要瓶颈是 `match`，其次是 stereo 后处理；光源事件建立了 0.1 s 分辨率的粗时间关系，但尚未建立约 60 FPS 的逐帧精确同步。以上工具服务未来专业双目相机部署，不代表实时运行或工业同步已经实现。

WASS production mode 分析框架现已建立：支持显式 ROI capability 检查、诊断/生产输出保留策略、可恢复批次和结果合并。现有输出策略可将五帧保留量减少约 75.7%，但不会改变 WASS 计算；当前 WASS ROI 入口不能降低主要的 `match` 耗时。100 帧实跑因帧级同步尚未建立而未启动，不能宣称已经取得生产模式加速或结果一致性结论。

### 真实视频成果索引

| 内容 | 状态 | 文档 |
|---|---|---|
| OpenCV 双目标定 | 完成 | [HomeTank_004 calibration validation](experiments/real_video/HomeTank_004/calibration_validation.md) |
| 标定与人工测量验证 | 完成 | [HomeTank_004 calibration validation](experiments/real_video/HomeTank_004/calibration_validation.md) |
| OpenCV → WASS 接口 | 完成 | [Fixed-calibration rectification policy audit](experiments/real_video/HomeTank_004/fixed_calibration_rectification_policy_audit.md) |
| 静水三维重建 | 完成验证，跨帧未通过 | [Static validation summary](experiments/real_video/HomeTank_004/static_validation_summary.md) |
| StereoSGBM 分析 | 进行中 | [SGBM matching parameter audit](experiments/real_video/HomeTank_004/wass_sgbm_matching_parameter_audit.md) |
| Wave 高度与漂移验证 | 方法完成，结果未验证 | [Wave height validation](experiments/real_video/HomeTank_004/wave_height_validation.md) |
| 标尺独立物理验证 | 首个冻结样例完成，参考变化过小，精度未建立 | [Phase 4 validation](experiments/real_video/HomeTank_004/phase4_physical_validation.md) |
| Phase 4 Case 2 | 独立输入已登记；冻结重建在尺旁位置无 2 px 内观测 | [Case 2 validation](experiments/real_video/HomeTank_004/phase4_case2_physical_validation.md) |
| Pixel–XYZ 与平面法向高度 | 基础接口完成 | [HomeTank_004 result](experiments/real_video/HomeTank_004/pixel_xyz_height_result.md) |
| Wave CSV/JSON 与独立验证接口 | 输出完成，物理验证待人工参考 | [Final wave output](experiments/real_video/HomeTank_004/wave_height_final_report.md) |
| 长时间 wave 全帧验证 | 资源/同步预检阻塞 | [Accuracy validation report](experiments/real_video/HomeTank_004/wave_accuracy_validation_report.md) |
| WASS 性能剖析 | 三帧实测完成 | [Performance profile](experiments/real_video/HomeTank_004/wass_performance_profile.md) |
| 光源事件同步分析 | 粗同步完成，帧级未建立 | [Synchronization report](experiments/real_video/HomeTank_004/video_synchronization_report.md) |
| WASS production mode | 框架完成，100帧受同步门阻塞 | [Production mode analysis](experiments/real_video/HomeTank_004/wass_production_mode_analysis.md) |
| 按需单帧后端 | 接口完成，HomeTank_004 受帧级同步门阻塞 | [Single-frame backend validation](experiments/real_video/HomeTank_004/single_frame_backend_validation.md) |
| 帧级同步精化 | 全帧 PTS 已分析，证据仍不足 | [Frame-level synchronization](experiments/real_video/HomeTank_004/frame_level_synchronization.md) |
| 按需同步容差 | 14组WASS完成，R0正式样例闭环 | [Sync tolerance validation](experiments/real_video/HomeTank_004/sync_tolerance_validation.md) |
| 单帧高度分布QA | 完成并冻结Phase 4基线 | [Height QA](experiments/real_video/HomeTank_004/single_frame_height_qa.md) |

## 核心建模成果

老师/首次访问者可先查看 [核心建模成果总览](docs/MODEL_OVERVIEW.md)。其中集中说明并链接了当前已经建立的三类核心模型：

- [双目几何模型](docs/mathematical_model/stereo_reconstruction_model.md)：理想平行双目关系 $Z=f_{px}B/d$、坐标/单位和当前设备参数绑定；
- [水面高度模型](docs/mathematical_model/height_field_model.md)：最终高度定义 $H(x,y,t)=Z(x,y,t)-Z_0(x,y)$，以及静水参考和坐标一致性要求；
- [虚拟相机模型](docs/simulation/virtual_camera_model.md)：基于 MER2-503-36U3C、2448×2048、$3.45\ \mu\mathrm{m/px}$ 和 8 mm 候选镜头建立 `SIMULATION_NOMINAL` 针孔双目模型。

上述文档均明确区分 candidate / simulation assumption / UNKNOWN 与真实标定参数，避免把仿真参数误写成实测值。

## 当前进展

已完成：

- 虚拟双目相机理想几何可信性验证：投影、视差和整面三角化闭环达到机器精度，
  shared physical texture 已确认；该结论不等同于真实相机成像验证；

- 测量系统、坐标体系、数据接口和数学模型设计；
- WASS 上游版本、架构、处理链、输入输出与参数映射分析；
- WASS 输出适配、坐标变换、静水参考、高度计算和误差指标核心代码；
- 虚拟双目相机、水面真值模型及可复现合成立体影像生成；
- WASS 输入工作区适配、外部进程 runner 和显式 NetCDF 映射 parser 边界；
- Case 0 已通过 WASS 核心、官方 `wassgridsurface 0.11.4` 和规则网格高度闭环；
- Case 1 的 +10 mm 固定非零高度场景已通过：`ZGAP_PERCENTILE=99.5` 时 raw support 为 100%，H RMSE 约 1.03 mm、MAE 约 0.916 mm、最大误差约 1.65 mm；该参数仅冻结于当前理想仿真几何；
- Case 1 重复性验证完成：WASS `xyzC` 三轮逐帧 bitwise identical；gridder 文件哈希不同，但最大跨运行 Z 差异仅 0.020553 mm，分类为 B（Numerically deterministic）；
- Case 2 单组一维正弦规则波已完成双目输入至高度场闭环；原约 45° 相位差已定位为世界坐标与官方网格 x 原点相差 0.10 m，显式对齐后相位误差接近 0；
- G0--G3 四组规则波幅频组合全部通过，raw support 均为 100%，高度 RMSE 为 0.739--1.131 mm；
- 确定性不规则波原始 IRR-1 在自动标定阶段阻塞；冻结 AC-10D 子集适配后的 IRR-1A 完成全链并通过，RMSE 为 2.368 mm，同时保留原失败历史；
- 工作距离实验保留 D1=1.75 m FAIL、D0=2.00 m PASS、D2=2.50 m BLOCKED；固定 2.00 m 时 0.15/0.20/0.25 m 三组基线均 PASS；
- B--Z 交叉验证点 `(B=0.25 m, Z=2.50 m)` 通过并解除该点原有的平面拟合阻塞，但尚未形成完整部署参数图；
- Case 1 的原始 default-99 运行平均符号/偏差正确，但 RMSE 和最大误差未通过预注册门槛；该历史结果不被后续适配覆盖；
- Case 1 分层诊断确认：xyzC 平面差为 8.999 mm；升高帧原始点仅支持
  51.45% 网格单元，无支持 DCT 单元贡献超过 98% 平方误差；
- 支持损失已定位到 WASS 三角化后的 Z-gap 最大连通分量阶段（单步丢失
  58.57%）；已定义 raw observation support mask，支持域诊断 RMSE 为 1.279 mm；
- Z-gap 断带呈纵向条带；当前发布构建不保存 pre-cluster 浮点深度、阈值和
  完整组件标签，机制归因标记为 `OBSERVABILITY_LIMITATION`；
- 自动化测试覆盖后处理、仿真、WASS 接口、官方 NetCDF、Case 1 帧选择和误差诊断。

当前阶段边界与后续：

- 采购前核心理想仿真验证已完成；低成本真实视频第一轮闭环也已完成，当前使用 iQOO Neo5S（cam0/left）和 iQOO Z10 Turbo Plus（cam1/right）；
- 手机阶段当前进入静水匹配稳定性诊断，不设置 1 cm 验收门槛，也不改变历史仿真结论；
- 手机阶段通过后再采购并接入专业双目相机；最终 1 cm 目标只在真实标定、硬件同步和独立物理参考条件下验收；
- 当前仅验证了工作距离、基线的两个单因素切片和一个交叉点，尚未得到完整 `baseline × scene distance` 有效域或全局最优参数；
- WASS 锁定 `v_1.5` 基线的独立复现（当前成功运行的是本机 `1.11` 构建）；
- 工业相机实机接入、同步与标定；
- 水槽静水/人工波实验及独立参考对比；
- 1 cm 目标的实测验收。

统一主路线为：`Theory/Simulation -> Real Stereo Calibration/WASS -> Video-based On-demand Single-frame Measurement -> Independent Physical Validation -> Result Application -> Professional Stereo Migration`。真实视频是最终输入载体；连续 wave 时间序列仍作为扩展证据保留，见 [real-video feasibility validation](docs/real_video_validation/README.md)。

Case 0/1/2 是静水零场、固定非零高度和动态正弦规则波三个逐级验证场景，并非三种“波”。三级理想仿真已形成软件全链路闭环；详细结果见 [项目宏观汇报](PROJECT_OVERVIEW.md)。这不代表真实相机、水槽或海面已达到 1 cm：真实标定、同步、畸变、噪声、反光和振动等仍待验证。

## 仓库结构

- `docs/`：项目计划、系统设计、数学模型、数据规范、仿真方案和 WASS 集成分析；
- `src/`：本项目自有的仿真、适配、静水参考、高度解算与指标代码；
- `src/input/` 与 `src/synchronization/`：双目视频、播放器时刻选择、同步帧对象和时间映射边界；同步结果不进入重建数值计算；
- `src/application/`：未来最终桌面程序的 V0.x 骨架，不是手机专用 Demo；
- 离线桌面 Demo Stage 1 已可播放/暂停视频、选择时刻、异步调用冻结单帧 backend，并回载原图、高度图、状态图与历史测量记录；启动方式见 [Stage 1 报告](experiments/real_video/HomeTank_004/demo_gui_stage1.md)。
- Demo Stage 2 已补齐有效像素高度叠加、canonical pixel 的 XYZ/H/status 查询、原始 WASS 点云查看及安全的全部/选择性 Session 导出；MVP 主流程现已冻结，见 [Stage 2 报告](experiments/real_video/HomeTank_004/demo_gui_stage2.md)。
- Windows 离线演示现支持 PyInstaller `--onedir` 分发，无需系统 Python、网络或仓库工作目录；构建与启动见 [DEMO_RUN](DEMO_RUN.md) 和 [打包验证](experiments/real_video/HomeTank_004/demo_windows_packaging.md)。
- `configs/`：候选设备、仿真和实验配置模板；
- `tests/`：自动化测试；
- `experiments/`：可复现实验入口；当前包含 HomeTank_004 的小型配置、元数据和诊断报告，不包含原始 MP4 或大型重建产物；
- `external/WASS/`：WASS 外部依赖元数据，不包含 WASS 源码。

完整导航见 [文档索引](docs/README.md)，总体阶段安排见 [项目计划](docs/PROJECT_PLAN.md)。

## 快速验证

项目当前依赖 Python 3、NumPy 和 Pillow。仓库采用 `src/` 与顶层兼容导入并存的早期结构；在仓库根目录可按下列方式运行现有测试：

```powershell
$env:PYTHONPATH = "$PWD;$PWD\src"
python -m unittest discover -s tests -v
```

## WASS 依赖边界

WASS 上游仓库：<https://github.com/fbergama/wass>

- 本仓库不修改、复制或重新发布 WASS 源码；
- 锁定基线与本地检出方式见 [`external/WASS/README.md`](external/WASS/README.md)；
- WASS 本地检出、构建产物、原始视频、图像序列、点云和其他大型数据均不提交到 Git；
- 未经真实 WASS 输出和独立参考验证，不作实测精度声明。

## 项目原则

1. 优先严格复现 WASS，不自行替代其核心立体匹配与三维重建。
2. 理论可行性、合成验证和真实实验结论明确分层。
3. 坐标、单位、配置、软件版本和数据来源可追溯。
4. 未确认参数保留 `UNKNOWN/TODO`，不以假设冒充实测数据。
