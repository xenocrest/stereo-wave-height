# 正式 V1 架构与算法边界

```text
用户
 ↓
presentation.py：PySide6 Widgets / QGraphicsView / QProcess
 ↓
application.py：Project / Calibration / Sync / Reference / Reconstruction / Export Services
 ↓
adapters.py：VideoSource / OpenCV / wass_lowcost / WASS / gridsurface / ncplot
 ↓
官方 OpenCV、FFmpeg、Praat、WASS CLI、wassgridsurface CLI、wassncplot CLI / WaveView API
 ↓
官方产物 → storage.py 校验/缓存 → GUI 数值与图像展示
```

模块在 `src/production_app/`。`domain.py` 定义项目与结果记录，`storage.py` 原子保存 JSON 与 SHA256 缓存校验，`worker.py` 是独立进程任务入口。UI 不含 stereo、三角测量、平面拟合、点云过滤或插值实现。

## 官方能力与平台适配

OpenCV：官方棋盘检测和 calibrateCamera；projectPoints 仅统计官方重投影误差。角点 N×2/N×1×2 的布局转换仅解决版本 IO 差异。

wass_lowcost：上游单文件入口存在重命名计数、Windows Praat 路径和 stdout 编码问题，且没有函数 API。因此适配器从未修改的原始文件读取 Praat 脚本生成/风噪 FIR 原始 AST 语句并执行，直接调用原脚本的 Praat TLCC。FFmpeg 路径、文件命名、子进程与编码由适配层负责。**不宣称原封不动运行了完整上游入口**，也没有另写相关算法。源码 SHA256 记录到 sync metadata。

WASS：外参阶段 prepare → match → autocalibrate；测量阶段官方固定 R/T prepare → stereo。历史示例内外参必须显式选择且保留来源；不修改 WASS 原生检查。

wassgridsurface：setup 使用官方输出平面，grid 使用同一固定 setup；官方已有插值/规则格网完全留在工具内。单参考帧的两条相同平面是文件形状适配，不是再拟合。

wassncplot：保留官方 CLI 的居中图/MAT，同时调用现有官方 WaveView API 渲染原 NetCDF Z，从而不把每帧序列 zmean 当作参考面。未改 renderer/projection/interpolation；PNG RGB/float 编码转换与 CLI 一致。

## 数据身份

标定身份由实际六个 XML 数值内容计算，而非 display ID。帧缓存键包含原视频 SHA256、同步、K/D/R/T、LEFT 实际时间戳、参考记录、米制基线、stereo 配置与工具 provenance。缓存产物逐个 SHA256 验证；失败目录保留，每次重试创建新 attempt。改变输入或标定使参考面失效，不借用另一帧结果。

## 高度坐标约定

WASS 原始平面为 nᵀP+d=0。官方 wassgridsurface 对齐后反转第三轴得到 upward Z，并按实测基线换为米。若原平面法向已归一化，官方高度等于 −B(nᵀP+d)；用向上法向 n_up=−n、d_up=−d 写成 H=B(n_upᵀP+d_up)。保存原始 plane，绝不改系数迎合图像。查询的是官方渲染映射中的参考面坐标 XYZ，H=Z×1000 mm；原相机 Z 只用于点云展示，不称作波高。

## 部署与安全

桌面 EXE 是 PyInstaller onedir；后台使用配置中的外部科学工具环境，worker 源码随正式软件带入 `production_source`。不使用浏览器、HTTP 或云服务。Qt 冻结路径不泄漏到外部科学环境。工具源码、可执行文件和原视频均只读；产物写在新项目目录。

WASS 官方有 TRIANG_BBOX / MASK 配置，但 GUI 坐标与官方去畸变坐标尚未完成本机全链验证，故 V1 不提供 ROI。非水面点不偷偷删除。黄金示例只能作为回归校验，生产适配器没有 Golden 数据后端。
