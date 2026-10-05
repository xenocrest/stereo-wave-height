# P0 软件正确性修复验收

验收日期：2026-10-05。状态：`P0_FIX_VALIDATION_COMPLETE_PENDING_HUMAN_REVIEW`。仅完成 I01 → I02 → I03 → I12；停止等待人工复核，未开始 P1。

稳定基线：`3330a393a1feae5b38f6c589cdde89af8b67d30f`；审计基线：`e41e8c825114bdfe42640038b4e3e3467fbf4455`。原 audit/ 全部保留且 Git diff 为空，未重解释或覆盖审计结论。科学输出独立保存在 `D:/stereo-wave-height-runs/reconstruction-quality-p0-20261001`，后缀沿用中断前工作目录，不表示所有验收均在 10 月 1 日完成。

## A–C：I01 与两组真实图像投影

I01 已修复：科学显示读取实际 WASS undistorted cam0，完整图像范围按官方 pixel map framebuffer 显示；XYZ、H、overlay、hover 共用同一光栅。RAW_CAMERA_IMAGE 独立保留，禁止其使用去畸变高度 hover、科学边界或科学 ROI。没有自行发明畸变转换。

下表前两列是同一旧网格与审计 1000 点人口，隔离 I01 显示修复；第三列是本轮**新科学运行**的另 1000 个随机有效映射点，不能将两种实验混作相同输入。单位均为 1920×1080 逻辑图像 px，map framebuffer 为 2400×1350，完整范围缩放 1.25 倍。median/max 均报告，保留 GPU raster 浮点残差。

|样例|原 raw 显示 median/max px|I01 去畸变显示，同旧点 median/max px|fresh P0 测量图 median/max px|
|---|---:|---:|---:|
|HomeTank21|4.720021 / 15.131014|0.001375 / 0.057256|0.001391 / 0.043371|
|HomeTank22|4.758433 / 15.211588|0.002207 / 0.722818|0.002037 / 0.332944|
|HomeTank23|4.534514 / 14.940417|0.001777 / 0.213406|0.001795 / 0.269002|
|Vieira0|1.135022 / 5.556848|0.015545 / 0.135078|0.014037 / 0.290599|

新结果每组 32 个真实 map XYZ 点分别投影到测量图、实际执行 MainWindow overlay/hover 并逐值核对 XYZ；measurement/overlay 各检查四角、四条边中心和图像中心，共 18 次索引一致检查。无数据点返回 NO_DATA，没有强行补点。raw 模式用禁止访问 core.hover 的负向检查。另有每组 1000 个**实际解码 WASS cloud 点**验证 I12 的原始几何链，不能把 map 浮点残差等同原始相机几何误差。

证据：[I01 报告](I01_FIX_REPORT_ZH.md)、[同旧点统计](evidence/I01_validation.json)、[fresh 投影/hover/export 完整记录](evidence/P0_final_measurements.json)、[HomeTank21 GUI](evidence/HomeTank21_P0_GUI.png)、[Vieira GUI](evidence/Vieira0_P0_GUI.png)。PNG 含实际程序画面；科学测量图与投影标记图也保存，不修改原始图像或科学 XYZ。

## D–E：I02、源帧 PTS 和同步残差

I02 已修复：FFmpeg `-copyts` 保留原始时间线；select 前后命名 showinfo 以**整数 ticks**唯一关联源 decoder frame index，实际秒数为 ticks×time_base。缺失/重复身份拒绝。请求为原 source PTS 时间线目标，选择第一个不早于目标的原帧；没有插帧或视频重编码。

TLCC_offset = −0.07507001632731439 s；残差定义 `right_source_pts − left_source_pts − TLCC_offset`，下表 ms = 残差秒×1000。frame index 为从原视频开始解码的 0 起始编号，左右 time_base 均 1/90000。

|request L s|L index / ticks / actual PTS s|R index / ticks / actual PTS s|delta_t ms|
|---|---|---|---:|
|21|1247 / 1890139 / 21.001544444444445|1256 / 1884050 / 20.933888888888887|+7.414460772|
|22|1307 / 1980109 / 22.00121111111111|1316 / 1974053 / 21.933922222222222|+7.781127438|
|23|1367 / 2070069 / 23.000766666666667|1376 / 2064055 / 22.933944444444446|+8.247794105|

旧 manifest 的 left actual 为 request+0.0089，right actual 实际是 request+TLCC，曾把输入 n=0 当选中源帧；新值绑定正确帧。新六张 PNG 与 I02 验证及审计原帧逐像素一致。整数 PTS 只增加审计打印时间精度，没有推翻审计约 +7.415/+7.781/+8.247 ms 的结论，也不能证明真实曝光完全同步。

保存 requested/actual source PTS/index/TLCC/residual、完整整数源身份、PNG hash 和提帧命令。视频 frame manifest 与 GUI export metadata 使用同一身份。可选 physical truth gate 必须有新源身份且 ticks/time_base/index/seconds 一致，旧字符串或篡改记录拒绝。Vieira 为官方 TIFF 序列，保存作者 source image pair/hash，时间明确为 `PROVIDED_SEQUENCE_NOMINAL_TIME`；其源视频 PTS 和残差为空，不伪造。

证据：[I02 报告](I02_FIX_REPORT_ZH.md)、[序列/validation 兼容补充](I02_SEQUENCE_EXPORT_ADDENDUM_ZH.md)、[重新运行 manifest](evidence/P0_regenerated_runs.json)。原残差仍约 7–8 ms，不声称同步物理误差消失。

## F–H：I03 与 fresh calibration

I03 已修复。唯一 `CANONICAL_CAMERA_IMAGE_ORIENTATION` 值是 `CONTAINER_DISPLAY_ORIENTATION_APPLIED_ONCE_V1`：按容器 display orientation 旋转一次，再进入 calibration、preview、measurement extraction 和 WASS input。OpenCV 显式开启 ORIENTATION_AUTO，FFmpeg 显式 autorotate。左原标定视频 metadata 180°、右为 0°。不交换 K 行列，不后补图像旋转。

fresh 标定重新完成，棋盘 6×9、0.020 m、5 Hz、50 views、minimum 12 未改变；选中图导出也使用同一约定。

|相机|旧 fresh RMS px|新 fresh RMS px|新完整棋盘检测数|选中数|
|---|---:|---:|---:|---:|
|左|4.19724464694886|4.149856500614477|230|50|
|右|5.522525225570181|5.522525225570181|328|50|

四个真实标定/测量视频的 OpenCV canonical decode 和 preview 完全一致，与 FFmpeg 第一源帧方向/尺寸一致。新 K/D 独立保存在 I03_fresh_intrinsics；没有与旧 R/T 混用。HomeTank 最终三个测量 run 的六文件 SHA256 全等历史完整 bundle，实际尺度仍 baseline 0.070 m。[I03 报告与矩阵/hash](I03_FIX_REPORT_ZH.md)；[fresh 数据](evidence/I03_fresh_calibration.json)。RMS 的变化不表示水面重建精度提升。

## I–K：I12 官方契约、刚体与实际点互逆

本地固定版本为 wassgridsurface 0.11.4。重新阅读 compute_sea_plane_RT、align_on_sea_plane_RT 和 `wassgridsurface.py::setup`；该版本不另有 setup.py。核对[官方 compute/align](https://raw.githubusercontent.com/fbergama/wass/master/gridding/wassgridsurface/wass_utils.py)与[官方 setup](https://raw.githubusercontent.com/fbergama/wass/master/gridding/wassgridsurface/wassgridsurface.py)；线上 master 0.14.0 不替代本机版本。

输入四元素 plane=[a,b,c,d]，方程 n·P+d=0，前三项法向必须单位长度。官方 R 最后一行是 n，T=[0,0,d]；align 先 R@P+T，再翻 Z，乘 baseline。setup 以 R.T 和 −R.T@T 作逆，再组合反向尺度/Z 翻转。因此多帧单位法向的均值若非单位长度，会使 R.T 不是真逆。

只在本项目 adapter 对**均值全部四项**除以同一法向长度，保持平面方程。原 workspace/plane.txt 不改，raw observations 单独保存。官方 CLI 输入重复 canonical mean 行并明确“不是独立观测”，避免单行 loadtxt 降维。官方 setup 输出矩阵不手改；零法向、非有限、a=b=0 的公式奇异输入拒绝。随后验 R、det、RTplane、Cam0/1toGrid 和 P0/1plane 公共公式及实际点互逆。

以下是**同一真实旧 WASS 点输入**的隔离前后实验，每帧 1000 点，保留旧 domain、N、baseline 与官方参数。统计人口与审计随机采样不同，原审计仍原样保留。B 为 WASS baseline-normalized 相机坐标单位；HomeTank 可乘 .070 转 m，Vieira 未知实测 baseline，不得改称 m/mm。

|样例|RᵀR−I Frobenius 前→后|det 前→后|camera→grid→camera max B 前→后|cam0 重投影 median/max px 前→后|
|---|---|---|---|---|
|HomeTank21|0.005643945572 → 1.577e−16|0.996009127813 → 1|0.0244522 → 1.831e−15|0.738130/1.833587 → 2.344e−13/7.626e−13|
|HomeTank22|同上|同上|0.0245755 → 1.831e−15|0.732406/2.536588 → 2.344e−13/7.626e−13|
|HomeTank23|同上|同上|0.0225500 → 9.992e−16|0.641573/1.905120 → 2.318e−13/5.684e−13|
|Vieira0|8.543169429e−6 → 1.926e−16|0.999993959067 → 1|0.000702259 → 1.628e−14|0.002627/0.005570 → 1.705e−13/6.915e−13|

完整两相机、4 个 HomeTank 和 5 个 Vieira 帧的误差见 [I12 数据](evidence/I12_validation.json)。最终重新执行科学阶段的 HomeTank 最大逆误差 ≤1.790e−15 B，Vieira0 ≤4.293e−14 B；最终 Vieira R 正交误差 6.354e−16、det 1.0000000000000004。这里接近机器精度的是坐标契约互逆，**不是物理测量精度**。[I12 报告](I12_FIX_REPORT_ZH.md)。

## L：旧 reference/cache 失效

新契约版本 `OFFICIAL_UNIT_PLANE_RIGID_GRID_V2` 参与 coordinate_frame_id、reference_plane_id、GUI project_input_identity 和 cache_key。缺旧证书、非刚体、hash 变化、旧版本或不一致身份均在 H 计算前拒绝 REFERENCE_FRAME_MISMATCH。旧 reference 不迁移/不复用系数。GUI 导入、fixed_run 和独立 reference/validation 消费路径全部同一规则；实际 provided physical plane 必须显式注册到新 frame，纯合成数学夹具不冒充官方 run。

HomeTank 先对保留真实旧 WASS plane observations 的新输入调用官方 setup/grid，得到新坐标；再 fresh 提取 20 秒并执行官方 prepare/stereo/grid，按 fresh 20 秒网格生成**一次**新内部 reference。随后 21/22/23 各自重新 prepare/stereo/grid/ncplot，复用相同新 setup 与这个 reference，不逐帧重新拟合。最后统一 factory 重新计算与已保存 reference 完全相等，没有收尾偷偷换系数。

新 HomeTank coordinate_frame_id：`7fa9b9f2e1b9c5943dfb052ecec728fdd53a5e414a9b9d08faab595c491b6abd`。

新 reference_plane_id：`designated_static_water_frame_OFFICIAL_UNIT_PLANE_RIGID_GRID_V2_d1bda89d641b01e1`。

reference n=(0.039674925870819756, −0.010125118707312277, 0.9991613394383851)，d=0.003360616869698453 m。源 actual t=20.00187777777778 s，source_frame_id=0。仅 INTERNAL_STATIC_REFERENCE，未作独立物理静水验证。[独立路径补充](I12_STANDALONE_REFERENCE_ADDENDUM_ZH.md)。

## M–N：新 HomeTank 与 Vieira 运行

四个 requested 样例均重新执行原官方科学阶段；HomeTank 还新解算 20 秒参考源。Vieira 使用原五对 TIFF、原 calibration config、原 area/N/baseline，完整新 match/autocalibrate/stereo/setup/grid/ncplot，不复用旧 mesh。程序报告 PASS 仅是既有执行状态，不作为科学支持充分的结论，I09 本轮未修改。

|新样例|过滤后官方 WASS 点数|有限官方 grid map 像素|NO_DATA 像素|H min / median / max（当前 finite 显示值）|
|---|---:|---:|---:|---|
|HomeTank21|146,818|954,468|2,285,532|−58.7156 / +0.8669 / +20.2200 mm|
|HomeTank22|107,272|933,469|2,306,531|−35.1928 / +0.0209 / +69.4649 mm|
|HomeTank23|127,965|948,940|2,291,060|−18.9980 / +0.1446 / +39.8048 mm|
|Vieira0|653,518|1,220,371|2,019,629|−0.921337 / +0.017436 / +1.675963 B|

direct stereo pixel provenance 仍为 0；source=2 仍是 OFFICIAL_GRID_ESTIMATE。I04/I05 未修，所以有限 grid 可包含池壁、标尺、岩石或外推，本表**不能解释成有效水面高度、物理波高或已通过真值验证**。HomeTank 水面可观测性尚未在本阶段作正式支持域验收，不宣称具备充分水面双目条件。官方随机阶段未设新 seed，不能据点数/H 变化归因科学质量改善。

GUI 切换 measurement/overlay/raw 与实际 hover 均验收；4 组均导出 49 个实际可用 pixel 的小显示矩形，以检查 CSV 数值/单位/ID与 PLY 原样 hash，不代表科学 mask，也没有修改 WASS 输入支持域。完整输出/日志保留在 final/；检查用小导出在 final/exports/。GUI 对 public sequence 通过现有绑定/接收接口检查，本轮未扩展其视频播放/菜单工作流。[完整运行 manifest](evidence/P0_regenerated_runs.json)、[检查记录](evidence/P0_final_measurements.json)。

## O–P：边界与停止

第三方源码修改：**否**。原审计 50 项 source guard + 安装包 14 项 hash 共 64 项重新计算，全部相同：[逐文件 hash](evidence/P0_third_party_unchanged.json)。没有修改 WASS、wass_lowcost、OpenCV、wassgridsurface、wassncplot 核心，没有自研 matcher/插值/平滑/AI segmentation，没有参数搜索或按视觉调高度。

开始 P1：**否**。没有改 I04/I05 support/mask、I06 确定性、I07/I08 reference/3D 展示、I09 状态语义或 I13 色标。截图中的连续彩色区域、逐帧色标与既有 READY 标签不构成新的科学认可。仅在人工复核 P0 后获得新继续指令，才进入下一阶段。

## Q：测试与失败记录

最终全量 pytest：`574 passed, 1 skipped, 25 warnings, 7 subtests passed in 41.78s`。[完整日志](evidence/P0_pytest_all.txt)。唯一 skip 为未配置 OPENCV_GOLDEN_DATA_DIR 的可选官方 OpenCV 图片集集成 gate；没有 skip 本轮 HomeTank/Vieira/P0 真实夹具。此前 unittest discover 476 tests、1 skip 通过；补修后最终以包含函数式测试的 pytest 全量为准。

各项单独验收：I01 4+20、I02 3+16、I03 2+20、I12 6+7+20；两个收口追加回归分别 I02 2 项、I12 7 项（含新 standalone 测试）通过。最后新科学运行另有 4×1000 map 投影、4×32 hover、4×18 边界、4×1000 WASS 两相机变换及原文件/hash检查。

开发中 validator 矩阵维度错误、offscreen OpenGL 无法创建 context、损坏 MAT 验 hash 顺序及 sequence export KeyError 均真实修正/记录；初始测试和检查日志保留，不删除失败目录，不以重复 WASS 随机试验挑结果。关闭测试 offscreen 环境后使用原官方 OpenGL renderer；GUI 截图由测试脚本加载系统中文字体，未改产品样式。

## R–U：Git 与交付

分支：[fix/reconstruction-quality](https://github.com/xenocrest/stereo-wave-height/tree/fix/reconstruction-quality)。四个要求的初始提交按顺序独立完成，收尾发现的元数据/绑定问题各自另追加同 Issue commit，未混入 P1。

|Issue|commit|内容|
|---|---|---|
|I01|38041356ad8543344d1fb71e82ff1c776a03c289|科学去畸变图、overlay/hover|
|I02|3aa0a68436a00a178ce82abb4becea8f1fa5f1d8|原始 integer PTS / decoder index|
|I03|5d0c7a4c845747f841e37e290b14905e77a5326b|统一 canonical orientation 与 fresh K/D|
|I12|24b3e10a92c938c206290a562b0b2cc266fe5b01|官方平面输入、刚体检查、版本失效|
|I02 收口|b300bc7|public sequence 导出及真实 PTS validation gate|
|I12 收口|552efad|独立 reference 消费路径也强制绑定|

四组新科学文件均产生于 24b3e10 的科学代码；后两项仅补强 metadata/reference 消费检查。官方 mesh/grid/XYZ、reference 系数和图像保持原样，没有为收尾检查重新启动随机科学阶段。最终另有验收报告/证据提交。

push 与 workspace clean 的最终原始检查见交付包 `FINAL_GIT_STATUS.txt`；收尾确认 origin 分支与本地 HEAD 相同、git status --porcelain 为空、audit diff 为空。本报告与全部 fixes/证据已推送的最终结果以该记录及本任务最终回报为准。
