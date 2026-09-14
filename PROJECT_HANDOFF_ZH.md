# 双目水面三维测量项目工作交接总览

> 交接基线：2026-09-14，主分支 `main`。本文统一说明项目目标、路线、数学模型、代码模块、数据成果、演示材料、已知边界、GitHub 备份和下一步建议。接手人应先读本文，再按文末索引进入专题材料。

## 1. 一句话说明项目

本项目研究如何从左右两台相机拍摄的同步水面图像中，利用双目几何恢复真实三维点，再以静水面为零基准计算水面相对高度，并最终形成按需单帧高度图和可展示结果。

当前产品定位不是实时逐帧重建，而是：

```text
双目视频输入
→ 用户选择一个时刻
→ 提取该时刻左右同步帧
→ 双目三维重建
→ XYZ 与像素对应
→ 静水参考面
→ 水面相对高度
→ 高度图、点云、统计和导出
```

目前已经建立完整数学与软件链，合成数据验证充分，真实视频中也确实多次生成了数万至十万量级 WASS XYZ 点云。但真实手机标定稳定性、透明/反光水面的可靠匹配、跨帧坐标一致性和独立物理精度验证仍未完成。因此项目当前属于“阶段性工程研究成果”，不能声称已经达到工业级或毫米级真实水面测量精度。

## 2. 项目路线及当前阶段

| 阶段 | 内容 | 状态 |
|---|---|---|
| Phase 1 | 理论模型与合成数据仿真验证 | 已完成 |
| Phase 2 | 真实双目系统标定、OpenCV→WASS 接口和真实 XYZ 重建 | 已完成首轮闭环 |
| Phase 3 | 视频输入的按需单帧水面三维测量 | 当前主线，后端已建立，真实稳定性待提高 |
| Phase 4 | 高度计算和独立物理误差验证 | 接口及两个验证案例已建立，结论仍有限 |
| Phase 5 | 结果展示软件 | 已有离线 GUI 和演示资产；当前 GUI 真实现场解算不够稳定 |
| Phase 6 | 专业同步双目相机工程迁移 | 尚未开始正式硬件实施 |
| Extension | 视频同步、长视频批处理和波浪时间序列 | 已有基础模块，暂非交付阻塞项 |

路线调整历史：项目最初侧重连续视频波高时间序列，随后根据 WASS 单帧约 25 秒的计算成本，调整为“视频承载输入、用户按需选择时刻、单帧解算”。连续视频工作没有删除，而是作为未来扩展保留。

## 3. 从视频到高度的核心数学链

### 3.1 相机成像

空间点齐次坐标为

$$
P_w=[X_w,Y_w,Z_w,1]^T,
$$

其像素投影满足

$$
s\begin{bmatrix}u\\v\\1\end{bmatrix}
=K[R\mid t]P_w,
$$

其中 $K$ 是相机内参，$R,t$ 是外参，$s$ 是齐次比例。畸变模型用径向和切向系数把理想归一化坐标映射到真实镜头像素。

### 3.2 双目标定与极线约束

标定通过最小化重投影误差求解参数：

$$
\min_{K,D,R,t}\sum_i\left\|p_i-\hat p_i(K,D,R,t)\right\|^2.
$$

同一空间点在左右图像中满足：

$$
x_R^T F x_L=0.
$$

极线校正把匹配搜索近似限制到同一图像行，减少二维搜索难度。

### 3.3 视差、深度与误差传播

校正后左右横坐标差为视差：

$$
d=u_L-u_R.
$$

平行双目近似下：

$$
Z=\frac{fB}{d},\qquad
X=\frac{(u-c_x)Z}{f_x},\qquad
Y=\frac{(v-c_y)Z}{f_y},
$$

其中 $B$ 是基线、$f$ 是焦距。视差误差对深度的近似影响为：

$$
|\delta Z|\approx\frac{Z^2}{fB}|\delta d|.
$$

这说明距离越远，深度误差增长越快；增大有效焦距或基线可以降低深度对像素误差的敏感度。

### 3.4 三角化与 WASS

一般相机几何下，对左右投影矩阵 $P_L,P_R$ 建立：

$$
x_L\times(P_LX)=0,\qquad x_R\times(P_RX)=0,
$$

组成线性方程 $AX=0$ 并用 SVD 求解三维点。WASS 在工程中完成特征匹配、稠密立体、三角化和点云输出；项目没有修改其核心匹配与三角化数学逻辑。

### 3.5 Pixel–XYZ 对应

每个有效三维点保存：

$$
(u_i,v_i)\longleftrightarrow(X_i,Y_i,Z_i).
$$

反向投影基本形式为：

$$
u=f_x\frac{X}{Z}+c_x,\qquad
v=f_y\frac{Y}{Z}+c_y.
$$

项目已修正历史 `mesh_cam.xyzC` 旋转矩阵多转置一次的问题，并在 HomeTank_005 的 98,438 点案例中证明全部点能够回投到有效像素域。

### 3.6 静水参考面与高度

静水参考面写为：

$$
n^TP+d=0,\qquad \|n\|=1.
$$

当前三维点 $P=[X,Y,Z]^T$ 到参考面的有符号法向距离为：

$$
H(P)=n^TP+d.
$$

在参考面与坐标轴平行的简化网格中，可写成 $H(x,y)=Z(x,y)-Z_0(x,y)$。正式实现优先使用平面法向距离定义。

标尺数据只用于独立验证，不进入 WASS、三角化、XYZ 或高度计算。

### 3.7 从稀疏观测到连续水面

局部 MLS 使用物理坐标拟合二次曲面：

$$
H(X,Y)=aX^2+bXY+cY^2+dX+eY+f,
$$

并用高斯距离权重求解：

$$
\min_\beta\sum_i w_i\left(H_i-\phi_i^T\beta\right)^2,
\qquad
w_i=\exp\left(-\frac{r_i^2}{2\sigma^2}\right).
$$

邻域点数不足、几何分布不可解或矩阵病态时返回 `UNSUPPORTED`，不强行生成数值。

全域演示模型采用“观测数据项 + 平滑项 + 曲率项”的正则化思想：

$$
E(H)=\sum_{i\in\Omega_o}w_i(H_i-H_i^{obs})^2
+\lambda_1\|\nabla H\|^2
+\lambda_2\|\nabla^2H\|^2.
$$

这里必须区分直接观测、局部估算、全域模型估算和不支持区域。100% 有限输出只表示软件生成了数值，不等于每个像素均被双目直接测量，也不等于高度准确。

### 3.8 波浪模型与时间序列

规则波模型：

$$
H(x,t)=A\sin(kx-\omega t+\phi),
\qquad k=\frac{2\pi}{\lambda},\quad \omega=2\pi f.
$$

复合波可表示为：

$$
H(x,y,t)=\sum_m A_m\sin(k_{xm}x+k_{ym}y-\omega_mt+\phi_m).
$$

视频时间对应采用仿射关系：

$$
t_R=a,t_L+b.
$$

同步模块只确定左右视频的时间对应，不参与 WASS、三角化或高度修正。

## 4. 已完成的主要软件模块

| 模块 | 位置 | 作用 |
|---|---|---|
| 合成双目仿真 | `src/simulation/` | 虚拟相机、纹理、平面/规则波/不规则波和真值数据 |
| 标定 | `src/calibration/` | 棋盘检测、单目/双目标定、质量门、空间覆盖选择和标定包 |
| WASS 适配 | `src/adapters/wass/` | 输入准备、运行绑定、参数与输出读取 |
| 三维重建 | `src/reconstruction/` | 单帧请求、WASS 管线、Pixel–XYZ、参考面、高度和备用模型接口 |
| 高度 | `src/height/`、`src/reference/` | 高度场与静水参考 |
| 空间补全 | `src/surface_completion/` | MLS、连续空洞验证、稠密图和正则全域模型 |
| 同步 | `src/synchronization/` | PTS、仿射时间模型、光源/音频事件与同步容差 |
| 性能与生产模式 | `src/performance/` | 阶段耗时、输出裁剪、批处理与恢复 |
| 验证 | `src/validation/` | 合成、真实视频、标尺、稳定性、误差与报告 |
| 离线应用 | `src/application/` | 视频加载、ROI、参考帧、按需解算、点云/高度图和导出 |

此外已对 NVIDIA Fast-FoundationStereo 做过隔离复现和 HomeTank_004/005 对照，但它没有替代正式 WASS 主线，也尚未形成经独立物理验证的真实水面高度结果。

## 5. 关键实验成果

### 5.1 合成数据

| 实验 | 主要结果 | 结论 |
|---|---|---|
| 投影—三角化闭环 | 平面/正弦三维 RMSE 约 $10^{-15}$ m | 几何实现闭环正确 |
| Case 0 静水 | 高度 RMSE 0.00446 mm，覆盖 100% | 零高度和共同有效域正确 |
| Case 1 +10 mm | mean 9.107 mm，RMSE 1.027 mm | 高度符号和尺度可恢复 |
| G0–G3 规则波 | RMSE 0.739–1.131 mm，波长 0.800 m，频率误差 0 | 理想条件下波形参数保持 |
| 三分量不规则波 | RMSE 2.368 mm，P95 4.672 mm | 可处理确定性复合波 |
| 基线实验 | 基线 0.15/0.20/0.25 m 时 RMSE 1.483/1.030/0.906 mm | 符合误差传播趋势 |

上述结果只证明理想成像和已知真值条件下的算法链，不代表真实手机视频精度。

### 5.2 HomeTank_004

- 完成真实视频接入、OpenCV 标定、WASS 运行、Pixel–XYZ、高度和 wave 输出。
- 标定结果暴露较大误差：stereo RMS 7.922 px、epipolar 9.508 px、vertical 21.123 px。
- 支持漏斗中，2,073,600 个公共像素最终 XYZ 约 6.520%，说明主要瓶颈是可靠匹配支持，而不是单纯文件输出。
- WASS 三帧性能：总耗时 29.204、23.555、23.174 s，平均约 25.31 s；match 平均约 11.55 s，是主要稳定耗时之一，stereo 后处理也占较大比例。
- 已完成 Static R0、Wave Case 1、Wave Case 2 的冻结结果、Pixel–XYZ、Phase 4 标尺接口及独立验证文档。
- 标尺严格保持独立，不进入重建。

### 5.3 空间补全

- 随机 hold-out：三个冻结帧 coverage 均约 99.76%–100%，RMSE 0.427–1.061 mm，分类 `SPATIAL_SURFACE_COMPLETION_PROMISING`。
- 连续空洞实验：四个由点间距推导的代表尺度总体 coverage 约 97%–100%，分类 `HOLE_COMPLETION_USABLE_FOR_DENSE_MVP`。
- 扩展空洞证明支持半径一旦超过既定门限，coverage 会降为 0；系统应保留 `UNSUPPORTED`，不能无限外推。
- 这些“真值”来自冻结 WASS observed H，只证明能重现已有 WASS 曲面，不是独立物理准确度验证。

### 5.4 HomeTank_005

- 完成 4K/30 FPS 数据 intake、视频元数据和采集 QA。
- Split calibration 使用 LEFT/RIGHT 单目全视场帧和双侧重叠帧分别约束内参与外参，平均指标优于 HomeTank_004：stereo RMS 3.694 px、epipolar 3.708 px、vertical 13.045 px，但最差折和参数稳定性仍不达可信测量 gate。
- 多次真实 WASS 成功：参考帧 101,548 XYZ；44.3345 s 测量 74,164 XYZ；68.5018 s 测量 117,450 XYZ；历史 48 s 测量约 98,438 XYZ。
- 98,438 点案例完成 Pixel–XYZ 闭环修正；117,450 点案例已制作“原图→像素支持→真实点云”三联展示。
- 历史参考/测量坐标不一致曾产生约 1 m 整体高度偏移，因此这些真实 XYZ 可以证明三维重建发生过，但相关高度不能用于物理精度声明。

### 5.5 HomeTank_006

- 完成新 4K 视频准备、棋盘尺寸和约 160 mm 采集距离信息确认。
- 固定大 ROI 的十帧 WASS 诊断从 0/10 XYZ 恢复到 10/10，但观测支持仍约 0%–1.11%。
- 曾出现的 91% ROI 覆盖统计因像素坐标约定问题已撤回，不得作为项目成果引用。
- 水槽底部纹理/折射路线不符合未来海面应用定位，未作为主线。

## 6. 当前可用于汇报的成果

### 6.1 技术报告

- [阶段性技术报告](PROJECT_PROGRESS_REPORT_ZH.md)：最适合正式汇报，按模型→实验→结果组织。
- [完整数学链](MATHEMATICAL_WORKFLOW.md)：从视频同步到高度和误差传播的公式说明。
- [通俗数学与数据流](PROJECT_MATH_AND_DATA_FLOW_ZH.md)：适合非专业听众。
- [项目宏观总览](PROJECT_OVERVIEW.md)：路线、研究结论和长期维护入口。

### 6.2 真实点云展示

- [最佳三联展示图](presentation_assets/real_water_point_cloud_best_case/REAL_WATER_POINT_CLOUD_BEST_COMPARISON.png)
- [最佳案例说明](presentation_assets/real_water_point_cloud_best_case/REAL_WATER_POINT_CLOUD_BEST_DEMO.md)
- [候选筛选依据](presentation_assets/real_water_point_cloud_best_case/candidate_selection.md)
- 完整 PLY：`presentation_assets/real_water_point_cloud_best_case/real_water_point_cloud_best.ply`

最佳案例是 HomeTank_005 的 68.5018 s measurement：117,450 个有限 XYZ 全部可投影回 1920×1080 图像，映射闭环最大误差 0.312 px。黄色点表示 WASS 实际三维支持，不是人工声明的全部水面。

### 6.3 软件演示

- 当前研发版：`StereoWaveHeightDemo.exe`，算法持续演进，但真实用户现场流程曾反复出现资源、参考绑定和后端运行问题，不建议作为唯一汇报保障。
- 独立历史演示版分支：`legacy/presentation-demo`，commit `8ad0719bdb798d1e1d7703cc3f8f769517ca0239`。
- Legacy 版只用于展示历史完整软件流程，数值未经科学验证，不应用于精度结论。

## 7. 已知问题和不可越过的结论边界

1. 真实手机标定仍不稳定；平均误差改善不等于外推可靠。
2. 透明、反光、低纹理水面造成双目匹配支持不足，不能归因于单一参数。
3. WASS 单帧可成功产生大量 XYZ，但不同帧的坐标一致性尚不稳定。
4. 局部 MLS 只允许在已验证支持半径内插值；远距离区域必须 `UNSUPPORTED`。
5. 全域演示模型的完整数值不能冒充直接观测或真实高度。
6. 真实物理 ground truth 尚不足，不能声称真实水面达到毫米级或 1 cm 级精度。
7. 当前 GUI 不宜继续优先修补；后续应先冻结可靠后端契约，再重建最小界面。
8. 海面工程路线不能依赖水槽底纹、已知槽深或水底折射纹理。

## 8. 建议接手后的技术路线

### P0：先建立可信的单帧测量基线

1. 使用硬件同步、固定焦距、固定曝光的专业双目相机。
2. 重新采集覆盖完整工作视场和距离范围的高质量标定数据。
3. 使用独立 hold-out 姿态验证 $K,D,R,T$ 稳定性，不只看训练 RMS。
4. 使用具有水面可追踪纹理且不依赖水底的受控实验，建立同帧物理真值。
5. 冻结一个 reference 和一个 measurement，先验证 XYZ、投影闭环和法向高度。

### P1：提高真实水面观测覆盖

1. 保留 WASS 为基线，与成熟立体模型做相同标定、相同帧、相同 ROI 的 A/B。
2. 把“直接观测覆盖率、错配率、空间分布”作为主要指标，而非只看总点数。
3. 在可靠观测上使用 support-gated MLS；超出支持范围保持 `UNSUPPORTED`。
4. 只有在独立真值证明趋势和幅值可信后，才允许构造全 ROI 高度图。

### P2：重新构建展示软件

后端先固定为无状态请求：输入标定、左右帧、ROI、参考 artifact，输出不可变结果目录。GUI 只负责选择文件、播放、提交任务和查看结果，不在界面层维护隐式 calibration/reference/session 绑定。

### P3：扩展动态测量

单帧稳定后，再引入硬件时间戳、批处理、断点恢复、波浪时间序列和频谱分析；不要直接回到全视频逐帧实时 WASS。

## 9. GitHub 备份状态

远程仓库：`git@github.com:xenocrest/stereo-wave-height.git`

| 内容 | GitHub 状态 |
|---|---|
| 主代码、测试、Markdown 文档 | 已在 `main` |
| HomeTank_004/005 关键 YAML、JSON、报告和小型图片 | 已在 `main` |
| 两套真实水面点云展示资产及完整 PLY | 已在 `main` |
| 当前交接文档 | 提交后位于 `main` |
| 独立 Legacy 演示代码 | 已在 `legacy/presentation-demo` |
| 原始大视频 | 未纳入 Git，需单独备份 |
| `D:\stereo-wave-height-runs` 历史运行目录 | 未完整纳入 Git，需单独备份 |
| `dist` / `dist_legacy` EXE | 通常不由 Git 跟踪，需单独备份或按脚本重建 |
| WASS 外部 runtime、FFmpeg、FoundationStereo 环境 | 不在 Git 仓库内，需单独记录/备份 |

必须另行复制的关键本机目录：

```text
D:\research\stereo-wave-height\experiments\real_video\HomeTank_004\videos
D:\research\stereo-wave-height\experiments\real_video\HomeTank_005\videos
D:\research\stereo-wave-height\experiments\real_video\HomeTank_006\videos
D:\stereo-wave-height-runs
D:\wass
D:\wass_diagnostic
D:\stereo-wave-height-runs\upstream_fast_foundationstereo
D:\research\stereo-wave-height\dist
D:\research\stereo-wave-height-legacy-demo\dist
```

GitHub 是代码、轻量实验结论和展示资产的备份，不是全部原始视频与运行缓存的替代品。

## 10. 接手环境与验证方法

推荐环境：Windows、Python 3.12、OpenCV、NumPy、SciPy、Matplotlib、PyYAML、pytest、WASS Windows runtime、FFmpeg。

基础检查：

```powershell
git clone git@github.com:xenocrest/stereo-wave-height.git
cd stereo-wave-height
$env:PYTHONPATH="$PWD;$PWD\src"
python -m compileall src
python -m pytest -q
git diff --check
```

注意：历史完整测试可能依赖未纳入 Git 的大文件或外部 WASS runtime。接手人应先运行纯单元测试，再按具体实验文档恢复外部数据路径。

## 11. 关键目录

```text
src/                         核心代码
tests/                       单元与回归测试
docs/mathematical_model/     数学模型专题
docs/simulation/             合成实验设计
docs/validation/             各阶段验证报告
docs/wass/                   WASS 集成、参数和运行边界
docs/system/                 软件架构与数据流
experiments/real_video/      真实数据集的轻量 metadata、配置和报告
presentation_assets/         可直接用于汇报的真实图像和点云成果
```

## 12. 文档阅读顺序

1. 本文：了解全局和接手边界。
2. `PROJECT_PROGRESS_REPORT_ZH.md`：按模型和实验准备正式汇报。
3. `MATHEMATICAL_WORKFLOW.md`：检查公式和从视频到高度的完整推导。
4. `PROJECT_OVERVIEW.md`：了解长期路线和历史阶段。
5. `presentation_assets/real_water_point_cloud_best_case/`：展示真实水面 WASS 点云证据。
6. 具体问题再进入 `docs/` 和 `experiments/real_video/` 对应报告。

## 13. 最终交接结论

项目已经完成从理论、合成真值、真实标定、WASS 三维点、Pixel–XYZ、参考高度、空间补全、性能分析到离线展示的完整研究链，并保留了可审计的成功和失败证据。最可靠的已完成结论是：双目数学链在合成数据上成立，真实视频已多次成功产生真实 WASS XYZ，空间补全能在有限支持范围内重现冻结 WASS 曲面。

尚未完成的核心结论是：任意真实水面像素的高度均准确、真实海面达到毫米/厘米级精度、或当前 GUI 可以稳定现场完成全流程。下一任接手人应以专业同步相机、严格标定和独立物理真值为中心推进，而不是继续对现有手机 GUI 做无限补丁。

