# 双目瞬时水面重建独立质量审计

完成状态：**INDEPENDENT_RECONSTRUCTION_QUALITY_AUDIT_COMPLETE**。

这只表示指定审计、证据记录与复现实验完成，不表示系统科学质量通过。审计基线为 `offline-basic-workflow-ready-v1` / `3330a393a1feae5b38f6c589cdde89af8b67d30f`，分支为 `audit/independent-reconstruction-quality`。正式 app、pipeline、validation 和第三方科学算法未修改。所有新增代码、报告、Git内证据均在 `audit/`；较大的科学诊断输出保存在 `D:/stereo-wave-height-runs/independent-quality-audit-20261001`。

## 核心判断

HomeTank_004 最终图与肉眼水面趋势不一致，首要已证实原因是**科学对象选错**：dense triangulation / z-gap 后、plane 前的点云已经主要覆盖池壁和标尺，而不是前景水面。21 s结果的147,349个过滤后点中，99,912个落在两个保守标注的明确非水面多边形中，至少67.8%；前景水域mask中仅11个点。22/23 s对应非水面点至少67.9%/66.0%，前景水域为0/0点。非水面结构已进入plane、setup和grid，不是仅污染最终显示。

随后默认DCT在不支持的区域生成完整有限网格，21/22/23 s分别有24.38%/31.28%/50.62%的格子位于输入点云XY凸包之外；原图overlay还有去畸变约定错位。内部reference、相机Z色彩、自动色阶和不等物理轴比例进一步干扰解释。**不能把这些结果当作该时刻真实水面P或H的已验证测量。** 这也不等于已经证明所有场景点几何错误：墙和标尺可能确实被重建为墙和标尺，只是被错误解释为水面。

四项SOFTWARE_BUG具有实测证据：原图/去畸变overlay与hover错位、actual PTS记录错误、fresh左标定旋转约定错误，以及官方平均plane输入契约导致Rpl非正交/回投影不互逆。前三项在项目实现，第四项在官方后处理输入契约/集成。没有发现实际workspace“新K/D+旧R/T”，也没有发现m/mm或baseline重复/遗漏应用。不能把全部问题归因于手机或RMS，也不能凭Vieira流程成功排除软件问题。

## 完整17项回答

| 问题 | 独立结论及证据 |
|---|---|
| 1. 为什么最终表面和肉眼趋势不一致？ | 非水面点主导科学输入；DCT空洞/外推把场景拟合成连续估计面；原图错位、reference和显示比例叠加误导。证据：`HomeTank21_preplane_vs_filtered.png`、`actual_XYZ_projection_and_support.json`、`HomeTank21_projection_check.png`。肉眼亮度/池底折射纹理不构成真实XYZ，因此只判断对象/支持域与软件错误，不虚构物理真值误差。 |
| 2. 最早哪个stage？ | **最早可以用保存的XYZ确认**是 dense triangulation 经z-gap保留后、plane之前，`mesh_full.ply`已有池壁/标尺形态；问题早于grid/reference/viewer。初始187,897点XYZ未由官方开关输出，不能精确声称第一条错误视差或z-gap之前每一点如何变化。 |
| 3. Vieira正对照正常吗？ | 流程和map内部投影自洽、海浪大尺度结构可见；但同一GUI也有raw/undistorted错位、岩石点、网格外推和PLY显示语义问题。**不是完全健康的科学正对照，不能据此免除integration/visualization责任。** 公共样例是同步TIFF，不能验证原始视频TLCC。 |
| 4. 有没有真实软件bug？ | 有：I01/I02/I03/I12，共4项；3项项目代码，1项官方后处理契约/集成。详见下列优先级表及完整问题登记表。 |
| 5. 坐标/单位/投影bug？ | 原图与map畸变坐标不一致，I01；冻结Rpl非正交导致真实点前向变换/回投影不互逆，I12。单位链未发现重复/遗漏。camera切换、u/v、row/col及map framebuffer比例已显式核对，没有发现转置/相机交换错误。 |
| 6. visualization误导？ | 原PLY是B单位相机坐标，颜色camera Z，不是固定metric坐标H；GUI不保证1:1:1；overlay逐帧2/98%自动色阶，无共享色条。真实比例图与明确10×图、固定H色阶图已输出。 |
| 7. pixel mapping错？ | `xyz[v,u]`与官方网格的内部投影自洽；但不等于原图对应正确。I01使raw hover/overlay错位；I12使原WASS点与对齐坐标回投影不一致。当前960,496等像素是OFFICIAL_GRID_ESTIMATE光栅，DIRECT_STEREO=0；并非同数量的独立立体观测。 |
| 8. calibration问题？ | fresh RMS4.197/5.523 px，视角/边缘覆盖不足，右单view最大21.319 px；左标定禁止180°自动旋转、测量默认自动旋转。50views各无重复，6×9/9×6为棋盘旋转等价，0.020 m数值处理正确；物理棋盘尺寸、焦距稳定性/ISP不能由现有容器元数据独立证实。没有按RMS删帧。 |
| 9. extrinsics实际来源？ | A/B/C实际K/D/R/T逐字节等于完整历史bundle，workspace K/R/T数值也相同；不存在本轮实际“新K/D+旧R/T”。历史bundle质量报告本身失败，完整性不等于有效性。fresh尝试有一次vertical-dominant T，也有水平占优T，不能把所有fresh尝试概括成vertical。fallback模式在尝试后主动切换，不仅在失败时切换。 |
| 10. sync selector还可优化？ | PTS识别/记录有必须修的软件bug。当前三对图像逐像素匹配原始候选帧后，各自右帧均为**固定当前实际左帧**的最近右帧，没有证明能更换右帧改善这三对；因此这三对为SYNC_LIMITED_BY_SOURCE_VIDEO。任意更换左帧也许可减残差，但改变用户选择的瞬间，不是本结论的固定左帧优化。 |
| 11. raw XYZ合理？ | 官方保留的preplane XYZ作为“场景结构”有可理解的墙/标尺分布；作为“瞬时水面”不合理。无独立高度真值不能判断这些墙点绝对几何精度。最初三角化云未保存，不能冒充raw无筛选全量云。 |
| 12. grid是主要失真源？ | 是后续的重要放大/补面来源，尤其外推和随机性；但不是首个原因，输入已非水面主导。相同cloud/setup的孤立grid三次固定格点Z跨度5.744 mm，独立证明DCT阶段贡献；不能全部归咎于plane RANSAC。 |
| 13. 池壁/标尺污染科学计算？ | 是，已影响保留点云、plane、setup/grid；显示ROI无法逆转。明确非水面计数只是两多边形保守下界，不是自动完整分割。 |
| 14. 官方mask能改善？ | 官方作用位置和内部left/right已核实，可限制triangulation。仅做一次同seed受控A/B：B保守水域mask使初始点降为1,867、preplane631、官方plane失败；没有B filtered/grid/overlay可比。没有证明此mask改善水面，也不能推断所有mask都失败。禁止继续换mask/调参把失败隐藏。 |
| 15. reference加剧错误？ | 固定内部候选n/d带约2.088°倾斜、3.7195 mm offset；21 s H−Z范围[-5.358,+2.991] mm，改变视觉趋势。但原XYZ/grid已经非水面主导，reference不是根因。identity正负例验证成立；身份一致不等于物理静水datum。未逐帧refit。 |
| 16. 现在可修哪些？ | 获准下一轮FIX后可修I01/I02/I03/I10/I13以及坐标契约I12、viewer I08、质量状态I09、支持域I05；可用现有数据检验I06随机性、I04官方mask/覆盖、I11标定诊断。此轮只定位与建议，未实施。 |
| 17. 哪些需新设备/数据？ | 曝光同步/滚动快门、audio-video latency、锁焦/防抖/ISP稳定性、完整标定覆盖、可靠水面纹理、独立静水datum和逐时刻逐位置高度真值必须新采集/实测。新采集不必全部等待购买GoPro；GoPro到货本身不能证明正确，也不保证透明水面可观测。 |

## 指定瞬时帧与同步证据

固定TLCC定义为 `offset = right_minus_left = -0.07507001632731439 s`。残差为 `delta_t = (right_source_PTS - left_source_PTS) - offset`。新鲜原始音频提取、同101tap 1000 Hz FIR、Praat 0–30 s重算完全复现该offset；交换两输入得到 +0.07507001632731376 s，符号正确。见 `independent_audio_tlcc.json`。

| request L / request R (s) | 历史记录 L / R (s) | 核实源帧 L / R（0起始） | 实际绝对源PTS L / R (s) | delta_t (ms) | 固定L的最近R |
|---|---|---|---|---|---|
| 21 / 20.924929984 | 21.0089 / 20.924929984 | 1247 / 1256 | 21.001544 / 20.933889 | +7.415016 | 当前1256 |
| 22 / 21.924929984 | 22.0089 / 21.924929984 | 1307 / 1316 | 22.001211 / 21.933922 | +7.781016 | 当前1316 |
| 23 / 22.924929984 | 23.0089 / 22.924929984 | 1367 / 1376 | 23.000767 / 22.933944 | +8.247016 | 当前1376 |

完整解码原视频时间线并在每相机6个邻近源帧中做RGB逐像素相等比较，唯一匹配原产物。源PTS按FFmpeg showinfo打印精度记录；这不是微秒级物理曝光同步保证。生产原命令 `-i video -ss requested -vf showinfo -frames:v 1` 的 `showinfo n=0` 是输出seek前的输入首帧，而当前regex取它并加request；提取PNG本身正确复现，actual PTS却错误。证据为 `sync_absolute_pts_and_frame_identity.json` 和 `production_pts_regex_reproduction.json`。没有伪造时间插值。

## 同一代码正对照与投影隔离

四结果均调用未改的 `app/core.load_result`、`core.hover`、`MainWindow._build_overlay` 和真实Qt `PointCloudView.show_ply`。不存在交接说明设想的app/services/ResultService目录；没有自行另写viewer替代实际实现。raw、undistorted、rectification、disparity、preplane、filtered、grid、overlay和真实比例输出见各 `*_stages.png`、`*_GUI_cloud.png`、`*_GUI_overlay.png` 和 `*_TRUE_SCALE_VIEW.png`。

| 数据/帧 | map自投影median (px) | GUI raw错位median / max (px) | 真实WASS点→官方对齐→P0plane回投影median / max (px) |
|---|---:|---:|---:|
| HomeTank21 | 0.001375 | 4.720 / 15.131 | 0.736812 / 1.848400 |
| HomeTank22 | 见HomeTank22.json，远小于raw错位 | 4.758 / 15.212 | 0.707056 / 2.563602 |
| HomeTank23 | 见HomeTank23.json，远小于raw错位 | 4.535 / 14.940 | 0.656334 / 1.961950 |
| Vieira0 | 见Vieira0.json，内部自洽 | 1.135 / 5.557 | 0.002606 / 0.005598 |

map自投影1000随机点比较实际pixel center、1.25 framebuffer比例，row=v/col=u。另每组32个**真实WASS点**逐点记录原P0cam投影、官方坐标、P0plane投影、map位置及查询XYZ；全云统计前向回投影误差。由于map来自规则网格，查询XYZ可以是不同的grid估计，不能要求它等于原始点、再将差值全部误称为索引bug。map的“内部自洽”也不能证明坐标对齐或raw overlay正确。

HomeTank冻结setup的 `Rpl^T Rpl−I` Frobenius范数0.00564394557、det0.9960091278、两个奇异值0.998002569；Vieira对应0.00000854317、det0.9999939591。官方setup平均plane系数未再次单位化，`compute_sea_plane_RT`需单位法向量，却用Rpl.T当逆，产生非刚体缩放。I12按用户投影不一致规则列P0；量级小于非水面主因，但必须修清楚再定义冻结坐标。

未发现最终row/column转置、cam0/cam1混淆、Z/H计算整体符号翻转。当前官方Z翻转、projection convention和有符号n/d按实际文件串联核查；3D相机视角和camera-Z配色会干扰肉眼判断。只有同一单位、轴比例、坐标与H定义下的图才可比较。

## 标定、外参、尺度与几何

实际使用bundle为 `D:/stereo-wave-height-runs/HomeTank_004/wave-reconstruction-pipeline-20260824/wass_workspace/config`。A/B/C六个K/D/R/T XML逐字节与历史相同，工作区K/R/T数值一致，证据 `calibration_bundle_provenance.json`。fresh标定仅是尝试记录，当前WASS科学矩阵为历史完整bundle。GUI仍把fresh RMS报告与active历史矩阵绑定展示，单独记I10。

| 诊断 | 左标定 | 右标定 |
|---|---:|---:|
| 内角点/格距/尺寸 | 6×9，0.020 m，1920×1080 | 同左 |
| 完整检测/选用view | 242 / 50 | 328 / 50 |
| 选中PNG重复hash | 0 | 0 |
| fresh RMS px | 4.19724465 | 5.52252523 |
| 单view min / median / max px | 3.063 / 3.892 / 7.408 | 2.689 / 4.260 / 21.319 |
| 角点凸包占图面积 | 47.647% | 50.151% |
| 最大角点x / 图宽 | 1413.344 / 1920 | 1503.268 / 1920 |
| 图像orientation metadata | 180° | 0° |

实际使用角点/帧编号、K/D、覆盖、Laplacian清晰度、姿态descriptor均在 `calibration_selection_and_orientation.json`。检测采用完整54角点与subpixel/diversity筛选；没有按误差删帧。6×9与9×6是棋盘旋转等价，不据此判定行列bug；square size以m建模，没有1000倍单位误用。物理格距未独立量尺复核。左较低清晰度和右极端单view误差是具体风险，不能仅从Laplacian值断言绝对模糊阈值/自动对焦变化。

历史 `experiments/real_video/HomeTank_004/calibration_result.yaml` 明确标记 `CALIBRATION_QUALITY_FAIL`、`approved_for_wass=false`；mono RMS4.3805/4.5253、stereo RMS7.9224、epipolar RMS9.5084。当前fallback具有来源，却没有因此成为高质量标定。

实际T=(-0.0588588027, 0.0125879387, -0.0330873805)，norm=0.0686847116；相对旋转约14.6527°。冻结origin fresh尝试T=(0.2319886,0.6939377,-0.6816391) vertical-dominant，官方拒绝vertical；另两fresh记录T≈(-0.93796,0.09572,-0.33326)、(-0.92248,0.01185,-0.38586)并非vertical-dominant，见 `fresh_extrinsics_attempts.json`。I03可以影响fresh几何，但不能证明它唯一导致vertical T。

WASS把T归一化成1 B，grid使用声明实测0.070 m一次恢复尺度；NetCDF数值×1000由ncplot/reader读回除1000，GUI显示H一次×1000为mm。没有发现重复baseline或m/mm转换。声明的实测baseline真实性未独立重测。Vieira公共样例保留B单位，不将其baseline=1误认作实测1 m。

对21 s**保留场景云**的相机深度p2/median/p98=0.221745/0.262196/0.319964 m；真实三角夹角9.915/12.153/14.054°。这是当前估计场景几何，不是独立已知水面工作距离。用理想平行模型 f=1540.820849 px、B=0.070 m、d=fB/Z，线性敏感度 |ΔZ|≈Z²|Δd|/(fB)：

| 深度m / 等效d px | 1 px深度变化mm | 0.5 px mm | 0.2 px mm |
|---|---:|---:|---:|
| 0.221745 / 486.403 | 0.455887 | 0.227943 | 0.091177 |
| 0.262196 / 411.362 | 0.637386 | 0.318693 | 0.127477 |
| 0.319964 / 337.093 | 0.949186 | 0.474593 | 0.189837 |

仅为视差几何敏感度，**不是系统真实误差**。实际姿态为汇聚/rectified变换，不能直接把此等效d当文件里的dense disparity。WASS `TRIANG_MIN_ANGLE=20`的源码proxy使用 `R*q+T`，并非本表按实际两光心计算的夹角；不能据“真实角<20°”断言所有点违反官方筛选。视差输出是缩放/彩色预览，未捏造数值全矩阵。

## stage、官方配置与grid

21 s官方日志最初三角化187,897点；z-gap最大连通分量后 `mesh_full.ply` 147,768点；plane后147,349点。官方 `SAVE_FULL_MESH`语义是**z-gap后、plane前**，不是最初未筛选raw XYZ；本轮不修改源码补导出。官方预览、plane、PLY、xyzC及日志均留存。HomeTank `*_stages.png`中所有时刻标注实际源PTS并保留历史错误记录；Vieira显示公共frame 0，不虚构视频时间。

HomeTank、Vieira公共配置与当前WASS `--genconfig`三套**全部有效参数**逐项diff在 `config_comparison.json`，三份逐字节原config保存在 `original_config_copies.zip`；Git内TXT仅去行末空白/结尾空行，来源与双hash见 `config_copy_provenance.json`，没有修改生产配置。有效差异只有：

| 参数 | default | HomeTank | Vieira |
|---|---|---|---|
| SAVE_AS_PLY | false | true | true |
| SAVE_FULL_MESH | false | true | false |
| USE_CUSTOM_STEREORECTIFY | false | true | false |

其余本轮所需WINSIZE/DENSE_*/MIN/MAX_DISPARITY、SPECKLE、UNIQUENESS、TRIANG_MIN_ANGLE、PLANE_*、ZGAP、DISPARITY_OFFSET、ROI/bbox/mask等有效值相同。不能把“官方默认”视作适合70 mm基线近距离透明水槽：plane RANSAC阈值1 B=70 mm、最大距离1.5 B=105 mm，容易纳入不同结构。MIN=1、MAX=640、DENSE_UNIQUENESS_RATIO=1、DENSE_SPECKLE_WINDOW_SIZE=-70等是实参，不凭名字自行改变。HomeTank custom rectify与Vieira不同，可作为未来受控对照，但本轮不调参。

冻结setup哈希 `5b68efa26b0b9228e031c5bf07e18a932023faf54af79a0d3270d62340782c07`，X范围[-0.1436420,+0.0591376] m，Y[0.1077038,0.3104834] m，side=0.202779636 m，N=256。域来自首帧场景点extent而非可靠水面域；adapter用median plane估extent，官方setup用mean plane，两者也需核验。另按实际安装CLI完成 `generateconfig → setup → area_grid inspection`，生成模板及 `HomeTank_setup_area_grid.png`；用户给的 `generategridconfig`不是此安装版本action名，第一次调用失败被保留，随后按实际help使用 `generateconfig`，没有假称两者一致。

| 帧 | filtered点 | 有点占格 / 65536 | 凸包外仍有限格 / 65536 | OFFICIAL_GRID_ESTIMATE pixels |
|---|---:|---:|---:|---:|
| HomeTank21 | 147349 | 18028 / 27.51% | 15977 / 24.38% | 960496 |
| HomeTank22 | 107268 | 12756 / 19.46% | 20499 / 31.28% | 914030 |
| HomeTank23 | 127965 | 14721 / 22.46% | 33176 / 50.62% | 951259 |
| Vieira0 当前固定坐标run | 649657 | 25789 / 39.35% | 15054 / 22.97% | 见Vieira0.json |

本轮Vieira 649,657点是所选run/frame的实际数，不用交接中的另一次676,880点替代。官方公共配置没有保存mesh_full，因此在独立复制workspace仅加官方 `SAVE_FULL_MESH=true`执行额外诊断，保存其preplane与同次filtered并投影比较；不把新随机plane结果冒充原始历史filtered。见 `Vieira_preplane_diagnostic.json` 和 `Vieira0_preplane_vs_filtered.png`。

当前默认DCT不是论文方法描述的线性插值。源码量化格点并随机处理碰撞、多次shuffle，torch随机初始化/Rprop，输出mask全1；没有自动物理支持域检测。21 s网格点最近观测距离median=4.079 mm、p98=58.104 mm、max=74.122 mm。有限数值、OFFICIAL_GRID_ESTIMATE标签和几乎百万pixel都不能替代观测支撑。

## 单次官方mask A/B

在实际undistorted图手绘保守可见水域footprint，不设计自动分割。cam0多边形(420,835),(1390,835),(1660,1035),(440,1035)；cam1(120,700),(1090,700),(1360,1030),(160,1030)。已核实HomeTank内部left=cam1/right=cam0，因此配置LEFT_MASK_IMAGE=water_cam1.png、RIGHT_MASK_IMAGE=water_cam0.png。mask原图、preview、配置和官方载入尺寸日志均保存。

A/B共享同prepared inputs、K/R/T、官方stereo参数和官方RANDOM_SEED=20261001；B只增加mask文件/两mask配置。没有改正式配置。A preplane147,768、filtered147,357，grid/overlay有输出；B initial triangulation1,867、z-gap631，plane RANSAC best inliers=0，官方阶段失败。B只有mesh_full，filtered/plane/grid/overlay为N/A，未绕过失败或补造平面。低覆盖下官方按整张image采样三点，也可能找不到可用三元组，不能把0 inliers直接解释为“所有水点非平面”。

结论：官方mask确实能作用于三角化对象，但**本次保守水域mask没有得到可用水面**；不能声称已经改善，更不能泛化为mask无效或所有水域无点。这一受控诊断不继续改mask或调参数求成功。

## 同输入三次与隔离grid三次

repeat1/2/3共享同prepared21 s帧、同stereo config hash和完全相同冻结setup；保持原默认RANDOM_SEED=-1。H在固定map pixel(u=1200,v=900)取当前固定reference，不是三个不同物理时刻，不取平均。

| run | preplane点 | filtered点 | H(1200,900) mm | Zgrid(row224,col224) mm |
|---|---:|---:|---:|---:|
| repeat1 | 147768 | 146607 | -8.897259 | +7.149847 |
| repeat2 | 147768 | 147026 | -3.879340 | -1.435602 |
| repeat3 | 147768 | 147374 | +1.959364 | -18.297642 |

固定H跨度10.856623 mm；固定格点Z跨度25.447489 mm，plane和grid均可能贡献。进一步只重复官方grid，mesh_cam.xyzC哈希始终 `0442e56ec8c503a771dd34d45923032423e864017e516f5b12c246e87334ddbd`，setup也完全相同，排除上游cloud变化：

| isolated grid run | Zgrid(224,224) mm |
|---|---:|
| 1 | -2.889348 |
| 2 | +2.854658 |
| 3 | +2.319359 |

跨度5.744006 mm，已证明grid单独不稳定。固定格点的XY由共享setup确定；边缘unsupported区尤其不能解释为瞬时波动。所有位置与全grid分布保存在 `repeat_and_mask_experiments.json`、`isolated_grid_repeats.json`，原science outputs未被平均。

## 固定reference与显示

当前reference n=(0.03380311447,-0.01361073223,0.99933582815)、d=0.0037194748 m来自20 s内部候选，画面可见手部；它不是独立物理静水基准。H=nᵀP+d按定义计算，21 s H−Z中位−0.641 mm、范围[-5.358,+2.991] mm。reference确实改变坡度/offset，但无法把墙/标尺云转成水面。

三个run calibration_id、extrinsics_id、coordinate_frame_id与reference匹配；分别改错三种ID的负例均在H前拒绝 `REFERENCE_FRAME_MISMATCH`。这验证身份机制，不能验证物理datum。不得逐帧重拟合reference、旋转云求水平外观、用平均态替代瞬时H。

`*_TRUE_SCALE_VIEW.png`使用固定官方坐标、物理轴box aspect按实际范围，为X/Y/Z 1:1:1；额外 `*_VERTICAL_EXAGGERATION_10X.png`明确标注10×。`HomeTank_fixed_color_scale_comparison.png`共享H[-40,+40] mm及colorbar，用来说明与GUI自动色阶的差别，范围不代表物理容许误差。原GUI截图由实际renderer生成，不改变显示行为。

READY只是process/artifacts/内部reference可用，`MainWindow._update_status`依据result是否非空； `_receive_reconstruction`摘要还使用成功字样。建议下一阶段INFO/WARN/BLOCK分层展示actual PTS/residual、RMS来源、fallback、原始点/支持域、OFFICIAL_GRID_ESTIMATE数量、内部reference与外推事实。质量阈值需要独立验证，不在此次审计随意制定或实现。

## 问题数量、优先级及修复风险

共15项独立问题；同一问题可有多个类别，以下数量**不相加**。每项完整的Issue、Category、Evidence、stage、file/function/config、scientific consequence、proposed fix及test、third-party modification、can test now、risk见 [ISSUE_REGISTER_ZH.md](ISSUE_REGISTER_ZH.md)，机器可读版本 `evidence/issue_registry.json`。

| 类别 | 数量 | ID |
|---|---:|---|
| SOFTWARE_BUG | 4 | I01 I02 I03 I12 |
| SOFTWARE_INTEGRATION | 2 | I09 I10 |
| OFFICIAL_CONFIG_USAGE | 1 | I04 |
| COORDINATE_TRANSFORM | 1 | I12 |
| CALIBRATION_IMPLEMENTATION | 1 | I03 |
| SYNC_IMPLEMENTATION | 1 | I02 |
| GRIDDING | 2 | I05 I06 |
| PIXEL_MAPPING | 1 | I01 |
| REFERENCE | 1 | I07 |
| VISUALIZATION | 3 | I01 I08 I13 |
| INPUT_DATA | 2 | I04 I11 |
| HARDWARE_LIMIT | 1 | I14 |
| UNRESOLVED | 1 | I15 |

| priority | ID及具体问题 | 下一阶段验证条件 |
|---|---|---|
| P0 | I01 raw/undistorted overlay/hover错位；I02实际PTS记录错；I04非水面科学输入；I12非刚体坐标/真实点回投影不一致 | 必须先保证空间、时间、对象和变换语义；I12虽数值影响较小，按用户投影不一致规则列P0。 |
| P1 | I03标定orientation；I05unsupported DCT域；I06随机H不稳定；I07内部datum；I08PLY/H显示语义；I09READY科学门控；I11标定覆盖/误差 | 现有数据可测试软件/可复现性与缺口；物理datum、充分覆盖须补采。 |
| P2 | I10 active矩阵与fresh RMS归属；I13自动色阶；I14源时间离散/曝光限制 | 来源绑定与颜色可修；实际曝光同步要独立实测。 |
| P3 | I15独立物理真值与透明水体界面未知 | 新独立瞬时真值才可解除；未证明物理精度不是未完成审计。 |

优先级依据科学正确性、直接证据和变更风险。建议后续在独立FIX分支先修I01/I02/I03/I12并冻结新的有效身份；然后处理对象/支持域及随机性，最后做显示状态和物理真值验证。每个修复需分别检验，不把“看起来更平”作为成功标准。无需修改第三方stereo算法；如果官方后处理接口仍无法正确/可重复，应明确上游问题，不偷偷patch第三方。

## 审计范围、证据链与限制

先阅读九份指定项目文档；再复核官方源码、文档、Vieira两论文及安装版本。方法与版本见 [OFFICIAL_METHOD_REVIEW_ZH.md](OFFICIAL_METHOD_REVIEW_ZH.md)；逐文件shape、unit、camera、coords、timestamp、工具来源见 [SCIENTIFIC_DATA_FLOW_AUDIT_ZH.md](SCIENTIFIC_DATA_FLOW_AUDIT_ZH.md)。审计方法不以历史成功状态替代测量。使用未改WASS 1.11_heads/master-0-g6b82aeb、wassgridsurface0.11.4、wassncplot2.5.3、OpenCV5.0.0。

证据目录 `D:/research/stereo-wave-height/audit/evidence` 包含原配置、JSON、render图、测试记录和SHA256 manifests。大输出在 `D:/stereo-wave-height-runs/independent-quality-audit-20261001`：三次stereo/grid、单次mask A/B、三次孤立grid、官方setup、Vieira额外preplane、邻近源帧、完整解码日志及独立音频； `external_evidence_manifest.json`列出全部文件哈希。原生产数据和配置未覆盖。

审计自己的早期日志命名有一次碰撞：isolated_grid导入共用recorder时覆盖了原stereo/grid试验的前4份顶层console日志和原command manifest。其余日志、所有workspace科学产物及WASS log.txt保留；没有丢失本报告计数/矩阵/H的产物证据。覆盖后的manifest保存为 `legacy_isolated_grid_commands.json`； `recovered_experiment_invocations.json`仅按实际执行脚本与保留case目录重建调用参数，明确标注“重建”，不捏造elapsed或缺失原stdout。recorder已改为每类manifest和唯一日志名。没有为了补日志重跑第二次mask A/B。详见README。这是审计记录限制，不计入项目15项问题。

官方初始全量XYZ和浮点全量disparity未由现有输出开关暴露；B mask失败没有后续结果；公共Vieira没有原始MP4；没有传感器高度真值、曝光/滚动快门或ISP实测。因此未声称精确定位首条错误匹配、确定真实水面绝对误差、证明全部mask无效或给硬件未知项一个虚假数值。

第三方保护核对50份已在历史run_report中记录的源码/工具哈希，变更数0；安装Python package源码另保存本轮hash清单，无既有baseline时不虚构前后比较。正式代码Git与稳定tag差异只允许audit/；测试实际产物、源帧身份、完整bundle、支持域、三次重复、projection、reference负例及第三方保护。测试只证实本报告事实/隔离，不判科学质量达标。

## 最终A–Y回报

| 字段 | 回报 |
|---|---|
| A | INDEPENDENT_RECONSTRUCTION_QUALITY_AUDIT_COMPLETE；仅审计完成 |
| B | 最早保存证据：dense triangulation/z-gap后的preplane云，plane前已非水面主导 |
| C | Vieira流程/内部map可工作，但同viewer也暴露integration/visualization问题；不能称完全正常的科学对照 |
| D/E/F/G/H/I/J/K/L | SOFTWARE_BUG4 / SOFTWARE_INTEGRATION2 / COORDINATE_TRANSFORM1 / CALIBRATION_IMPLEMENTATION1 / SYNC_IMPLEMENTATION1 / GRIDDING2 / PIXEL_MAPPING1 / REFERENCE1 / VISUALIZATION3 |
| M | INPUT_DATA2、HARDWARE_LIMIT1、UNRESOLVED1；详见I04/I11/I14/I15 |
| N | P0：I01 I02 I04 I12 |
| O | P1：I03 I05 I06 I07 I08 I09 I11 |
| P | 现有数据可进行下一轮空间/时间/旋转/坐标、provenance、viewer、支持域、随机性修复验证；未在此次实施 |
| Q | 充分标定、稳定拍摄模式、水面观测纹理、曝光/时空真值和物理reference要新采集；并非所有都必须等新设备购买 |
| R | 正式科学代码修改：否 |
| S | 第三方算法修改：否 |
| T | D:/research/stereo-wave-height/audit/INDEPENDENT_RECONSTRUCTION_QUALITY_AUDIT_ZH.md |
| U | D:/research/stereo-wave-height/audit/evidence 和 D:/stereo-wave-height-runs/independent-quality-audit-20261001 |
| V | audit/independent-reconstruction-quality |
| W/X/Y | 实际审计commit、push结果与clean状态写入交付outputs/DELIVERY.json，防止报告自包含commit哈希产生循环；Git完成后才宣布交付完成。 |
