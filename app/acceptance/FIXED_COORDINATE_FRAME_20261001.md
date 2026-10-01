# 固定坐标系与公共区域闭环验收

Starting HEAD：`0e2af54a6726625d75e2556abc65c6548722fa32`。
分支：`app/offline-basic-workflow`。日期：2026-10-01。

## A. 本轮结论

`OFFLINE_BASIC_WORKFLOW_READY_FOR_NEW_INPUT_PASS` **成立，限于本轮定义的软件流程验收**。

它不代表任意新视频科学重建必定成功、不代表所有像素具有高度、不代表独立物理准确度通过。公共几何 mask 使用任务明确允许的 NOT_AVAILABLE 分支。非水面结构仍可能出现在官方输出中。

## B–C. 跨独立运行固定 reference

独立根目录：`D:/stereo-wave-height-runs/fixed-coordinate-acceptance-20261001-final`。
三个工作目录分别为 `Run_A/science`、`Run_B/science`、`Run_C/science`，均新建官方 workspace，未复制旧 mesh/XYZ/map。每次由独立 `app.worker` 子进程执行 TLCC、官方 prepare/stereo、grid、savexyz；B 启动前 A 子进程已结束，C 启动前 B 子进程已结束。不是一个进程里的内存缓存。

A 在 20/21 s 重建两个新帧，用既有冻结 reference adapter 从 A 的 20.0089 s 候选建立内部参考，保存 JSON 并冻结。B/C 分别从该 JSON 加载同一 n/d。没有新增平面拟合、ICP、自动配准、手动 offset/scale/clip。

科学坐标 setup 的明确来源：前轮可追溯官方运行 `pipeline/hometank004_multiframe_acceptance/run_20260928/science/surface/config.mat`。本轮允许复用已冻结坐标定义，不是从原始数据独立标定复现任务。A/B/C 均使用原样官方 setup 及同一完整 K/D/R/T，不再运行 setup/autocalibration。首次新项目仍走原封不动的完整 pipeline；确认冻结后才转入独立当前帧 adapter。

setup SHA256（源文件、A、B、C 完全一致）：
`5b68efa26b0b9228e031c5bf07e18a932023faf54af79a0d3270d62340782c07`。

共同身份：

- calibration_id：`9184852a01ab183ed9e839e92c834935503ab91e5d4cfab2c98803553a68d5c7`
- extrinsics_id：`91f1a9745ae307e464d048f1d5a4789ea826e12b448404589334c83139f496f8`
- coordinate_frame_id：`77736f79d64a1a7be300954e43f3ded47d9d5511f82f7fabb93986e4cd178310`
- reference_plane_id：`INTERNAL_STATIC_REFERENCE_11588c60c5ed3119`

coordinate_frame_id 使用实际 K/D/R/T 身份、外参 hash、官方 Rpl/Tpl、CAM_BASELINE、Cam0toGrid/Cam1toGrid、双相机投影与 K、单位/约定的 SHA256；不使用 run 路径或项目名。grid 前核验新 workspace P0/P1 和 K0/K1，确保相机交换/坐标约定未改变。

reference_plane.json 保存要求的三个身份、平面 ID、n/d、source、frame_id、timestamp，以及原 schema 的 normal/mode/source_run 字段。项目确认会同时保存 YAML 和旁边 JSON。重建帧 metadata 与导出 metadata 保存三个身份；身份缺失/不一致时不得计算 H。

## D. 负例

分别改变 calibration_id、extrinsics_id、coordinate_frame_id：三组均抛 `REFERENCE_FRAME_MISMATCH`。测试明确断言冻结 `load_frame`（其中执行 H=nᵀP+d）从未被调用，而不是算完后才隐藏。

GUI 负例明确显示 `Reference status: FRAME_MISMATCH / H: N/A`，移除旧 result，不能继续 hover/export。没有删除严格校验。

## E–G、I. 公共区域与三类 region

详见 [官方坐标核验](../../docs/WASS_COMMON_REGION_COORDINATES_ZH.md)。WASS 实际版本 `1.11_heads/master-0-g6b82aeb`；bbox/mask 在 triangulate 阶段检查内部左右相机去畸变坐标，rectified 候选先 unrectify；mask 必须等于内部对应图尺寸，路径相对 workspace。不是原始图裁剪，也不影响 matcher。

没有可直接读取、符合完整几何语义并已注册到 GUI 原图的官方公共 mask，所以不生成近似 mask/框。界面、hover 和导出统一 `COMMON_REGION_NOT_AVAILABLE / NOT_AVAILABLE`。

MEASUREMENT_REGION 继续是可选 USER_RECTANGLE，仅限制展示/查询/CSV。HEIGHT_AVAILABLE_REGION 只根据当前官方映射的有限 XYZ/H 及非零来源计算。青色边界不是公共区域；官方网格估计不是直接测量覆盖率。

## H. 三帧回归

| 独立运行 | 实际左时间（s） | frame_id | WASS PLY 点数 | 映射有效像素 | hover 示例 H（mm） |
|---|---:|---:|---:|---:|---:|
| A | 21.008900 | 1 | 147,349 | 960,496 | -2.070565 |
| B | 22.008900 | 0 | 107,268 | 914,030 | 3.458439 |
| C | 23.008900 | 0 | 127,965 | 951,259 | 3.721627 |

三个示例查询像素不同，不能作为同点时间序列。官方随机处理会使重复运行计数/数值略有变化，本轮不更改其随机逻辑。

旧三帧加载回归通过；新 A/B/C 逐个加载同一已冻结项目，raw/cloud/overlay、有值查询/NO_DATA、五文件 export 均通过 Qt 回归。PLY 导出 hash 与源 PLY 一致，CSV/metadata 带同一冻结坐标身份。仍明确 EXTRINSICS_FALLBACK，未改历史外参事实。

另用 computer-use 检查实际独立窗口：从项目磁盘恢复 A 的 reference，打开 C 的 run_report，在 23.0089 s 显示 MATCHED、四个 ID、NOT_AVAILABLE；实际点击叠加，画面显示官方网格输出。此查看不算再次运行 WASS。

## J–L. 新输入演练与算法边界

实际点击新建空项目，保存 `EMPTY_NEW_PROJECT.yaml`：四个视频路径为空、没有 HomeTank fallback/reference/result、allow_extrinsic_fallback=false。随后用户输入方式填写另一组 HomeTank_005 的左右标定视频及波浪视频，保存；实际窗口预览双图、播放时间推进、暂停至 3.036 s、点击参考候选，状态 CANDIDATE。

未同步点击重建，真实提示“请先完成左右视频同步”，不冒用旧结果。标定/重建调度接口回归测试通过，读取的是这四个新路径；调度测试隔离外部执行，**没有宣称 005 标定/WASS 科学 PASS**。本轮不为新输入测试额外跑标定或调参。

业务源码 HomeTank/固定 2400×1350 路径硬编码：0。例子与测试 fixture 中的真实数据路径不属于业务硬编码。

第三方科学算法修改：0；pipeline 科学代码修改：0；高度定义修改：0；EXE 打包：否；新增 GUI 架构：否。

## M–P. 测试和备份

- 针对性：27 passed，3 subtests passed。
- 最终完整 pytest：556 passed、1 skipped、7 subtests passed、25 项既有 warnings，39.44 s。
- 最终日志：独立根目录的 `full_tests_final.log`。git diff --check 通过。
- 首次 A 尝试的官方科学步骤完成，但 adapter 写帧 metadata 时尚未生成 run_report，导致 FileNotFoundError；已修正写入顺序。失败目录保留，最终另建 `...-final`，未覆盖或隐瞒失败。
- Git 提交/推送与工作区最终检查见交付回报。仅全部通过后创建 `offline-basic-workflow-ready-v1`；其含义是软件流程就绪，不是物理精度标签。

## 复现命令（会真实新建并执行官方科学工具）

```powershell
$env:PYTHONPATH = "$PWD;$PWD\src"
python -m app.validate_fixed_runs --config app/acceptance/hometank004_20260928/multiframe_config.yaml --source-run D:/stereo-wave-height-runs/pipeline/hometank004_multiframe_acceptance/run_20260928/science --output D:/stereo-wave-height-runs/fixed-coordinate-NEW-RUN --reference-time 20 --times 21 22 23
```

output 必须是尚不存在的目录；不会覆盖旧科学结果。需要使用项目配置的科学 Python。`reference_plane.json`、acceptance.json、每次 worker.log、独立 science/workspace/logs 都保留在该目录。
