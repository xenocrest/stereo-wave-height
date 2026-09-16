# Golden Demo v1 只读汇报程序

## 一键启动

在 Windows PowerShell 执行：

```powershell
powershell -ExecutionPolicy Bypass -File D:\research\stereo-wave-height\scripts\run_vieira_demo_ui.ps1
```

程序检查 Python 和依赖，默认加载固定样例，打开浏览器；地址为 `http://localhost:8501`。不需要选文件或改参数。关闭运行它的 PowerShell 可停止服务。若端口已被占用，先关闭之前的演示服务，不要并行启动两份。

依赖已安装在 `D:\stereo-wave-height-runs\wassgridsurface-0.11.4-venv`：Python、Streamlit 1.64.0、Plotly 7.1.0、plyfile 1.1.5、SciPy、NetCDF4、NumPy。依赖清单：[requirements_presentation_ui.txt](scripts/requirements_presentation_ui.txt)。安装后展示不需要互联网，服务只监听本机 127.0.0.1，关闭 Streamlit 使用统计。

只读入口：[run_vieira_demo_ui.ps1](scripts/run_vieira_demo_ui.ps1)。旧 `run_vieira_demo.ps1 -Rebuild` 属于计算工具，不在本 UI 中调用；本 UI 无任何计算或重建按钮。

## 八页内容与推荐顺序（3–5 分钟）

| 顺序 | 页面 | 现场讲解重点 |
| --- | --- | --- |
| 1 | 首页 | HomeTank_004 五帧黄金样例，新 XYZ 共 681,678；仅证明工程链路 |
| 2 | 双目输入 | LEFT/RIGHT 并排，侧栏切换帧 0–4；说明原视频与 TLCC 时间对应 |
| 3 | 流程展示 | 视频→同步→标定→WASS→XYZ→公共平面→网格→NetCDF→叠加→查询 |
| 4 | 3D Point Cloud | 旋转、缩放、平移；每帧最多约 25,000 点仅用于显示 |
| 5 | Height Map | 直接读取官方 NetCDF 的 η(x,y)，单位 mm；同时说明支撑与估算比例 |
| 6 | Image Overlay | 切换五帧官方已生成叠加图；完整官方图包含非水面，明确指出边界 |
| 7 | Pixel Query | 输入 u=1000、v=1050，查看 XYZ 与公共平面高度；不支持图像点击，以输入框避免额外依赖 |
| 8 | Conclusion | 能证明与不能证明分开；最后介绍 GoPro HERO9 严格验证的后续计划 |

所有页面及侧栏均显示 **DEMO ONLY / NOT PHYSICALLY VALIDATED**。首页包含 END_TO_END_DEMO_PASS 和 source 网格占格率约 18.93%–20.55%，不是水面图像直接测量率。

点云读取冻结的官方 PLY 相机坐标，轴单位为 WASS baseline units，不当作公共平面高度。显示抽稀为确定性步长取样，标注 DISPLAY-ONLY DOWNSAMPLING / Original reconstruction unchanged。原点云、颜色和算法结果不写回。

高度图直接读取冻结 NetCDF 的毫米数组，不修正高度。source、凸包内插值和凸包外外推百分比直接读取已有审计统计；没有新生成 support 掩码或新插值。100% finite 网格不能说成 100% 直接测量。

Overlay 页展示五份完整官方输出，均不重新计算；第一帧另显示此前冻结的中央水面展示遮罩。全幅叠加延伸到墙、尺子等非水面，不能把这些部分说成真实水面成果。

像素查询使用 **官方渲染图像的 2400×1350 坐标**，不是原视频或左右输入图的像素坐标；原点左上，u 向右、v 向下。读取已有 savexyz MAT，XYZ 单位 m，H=1000×MAT 的 Z（mm）。MAT Z 已使用官方 wassncplot 渲染约定：NetCDF Z/1000 减官方 meta.zmean；UI 不再置零或改偏置。

有效值标明 OFFICIAL_RENDERED_DCT_GRID，但逐像素直接观测/插值/外推类别无法可靠区分，provenance 显示 **UNKNOWN**，不猜测 DIRECT。背景或官方 0/1 sentinel 返回 UNSUPPORTED，不返回伪造高度。越界输入或缺文件显示简短错误和具体路径，不显示 Python traceback。

## 冻结规则与 fallback

基线：`demo/vieira2025-end-to-end`，commit `7224ef1366b574fcd8f478d6ecba1c4550822be3`。

Golden Demo v1：`D:\stereo-wave-height-runs\vieira2025-end-to-end-demo-20260916\golden_004_demo`。
[manifest](presentation_assets/vieira2025_end_to_end_demo/demo_manifest.json) 记录 299 个冻结文件的 SHA256。UI 仅以只读方式加载 PLY/MAT/NetCDF/图片，缓存保存在内存；不会改 K/D、R/T、sync、XYZ、mesh、plane、grid、pixel XYZ 或 height，也不会运行 WASS。

该样例使用来源明确的历史 K/D/R/T（DEMO FALLBACK / TRACEABLE HISTORICAL K/D/R/T），新执行的 autocalibrate 输出保留但未采用。当前不是完整无 fallback 的 Vieira 科学复现。详情：[端到端报告](DEMO_VIEIRA2025_END_TO_END_ZH.md)。严格科学 Track A 保持原结论。

GitHub 保存 UI、文档、小图和 manifest；大文件依然在本机冻结目录，不宣称大文件已上传。缺少本地文件时程序给出 exact path；小图首页仍可查看。

## 官方工具核验（2026-09-16）

- [wass_lowcost 官方仓库](https://github.com/matheusdpv/wass_lowcost) 提供 setup_sync.py、wass_sync.py、同步说明及样例，不提供本次八页式独立汇报 GUI。
- [WASS 官方项目](https://github.com/fbergama/wass) 是重建计算流程；历史 [WASSjs 官方安装说明](https://www.dsi.unive.it/wass/documentation/install.html) 提供浏览器工作流服务配置，但本次未安装或运行 WASSjs，也没有把它宣称为完整点云/高度/查询汇报界面。
- [wasscli 官方说明](https://pypi.org/project/wasscli/) 定义为交互式命令行，自动化 Prepare→Match→Autocalibrate→Stereo，不是汇报 GUI。
- [wassncplot 官方仓库](https://github.com/fbergama/wassncplot) 将 WASS/网格 NetCDF 三维结果渲染叠加到图像，支持保存图像与 savexyz。本 UI 展示它已有的输出，不修改第三方项目或渲染结果。

因此本次只新增最薄 Python + Streamlit + Plotly 展示层，没有 Qt、Electron、React 或新算法。

## 结论与下一步

可证明：真实输入可生成 WASS XYZ、公共网格、NetCDF、叠加图及像素查询；固定五帧工程演示可运行。

不可证明：厘米级精度、绝对波高正确、全水面直接观测、严格无 fallback Vieira 复现、人眼趋势已验证。

下一步 GoPro HERO9 严格复现需可靠标定、同步、基线和独立物理误差验证。仅作为最后一页规划，不在本次开发范围。

验证包含八页启动/切换、五帧读取、PLY/NetCDF/MAT、有效/越界像素、UNKNOWN/UNSUPPORTED provenance、缺文件友好提示，以及 UI 操作前后 299 个冻结文件哈希一致。没有校准实验或 WASS 执行。

本次结果：针对性测试 3 passed；全套 479 passed、1 skipped、4 subtests passed。实际 Streamlit 服务启动成功，localhost 健康检查返回 ok；Python compile、Markdown UTF-8/本地链接和 git diff 检查通过。冻结资产及已有算法文件相对基线无 Git 差异。
