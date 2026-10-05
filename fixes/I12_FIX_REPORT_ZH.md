# I12 修复：官方单位平面与刚体变换契约

已重新阅读本机固定 wassgridsurface 0.11.4 的 `wass_utils.py` 和 `wassgridsurface.py::setup`（该版本 setup 函数不在独立 setup.py）。同时核对[官方 compute/align 源码](https://raw.githubusercontent.com/fbergama/wass/master/gridding/wassgridsurface/wass_utils.py)及[官方 setup 源码](https://raw.githubusercontent.com/fbergama/wass/master/gridding/wassgridsurface/wassgridsurface.py)。线上 master 是 0.14.0，不冒充本机版本；实际验收只运行本机 0.11.4，源码 hash 保留于原审计证据。

官方输入是四元素 `[a,b,c,d]`，平面方程 `aX+bY+cZ+d=0`，法向前三项必须满足 `a²+b²+c²=1`。`compute_sea_plane_RT` 的最后一行是 `[a,b,c]`，平移为 `[0,0,d]`；align 先 R@P+T，再翻转 Z，最后按 baseline 缩放。setup 用 `R.T`、`-R.T@T` 构造逆，再用同一个 Z 翻转与 baseline 的逆缩放构造 P0plane/P1plane、Cam0toGrid/Cam1toGrid。

旧 adapter 直接把多帧 WASS plane 的系数均值送给 CLI。单位法向的均值通常不再单位长度，故 Rpl 不是刚体，转置不是真逆。只缩放法向会改变 d 所定义的平面。本修复在项目 adapter 对原系数均值的**全部四项**除以同一法向长度，保持方程与原均值的零集合；未改每个 workspace/plane.txt。raw observations 保存为 planes_raw.txt；CLI planes.txt 明确为重复的 canonical mean 输入行（不是新观测），至少两行，避免官方 loadtxt 对单行降维导致 scalar mean。非有限、零/抵消法向、官方公式 a=b=0 奇异输入明确拒绝。自动 domain 的既有 median-plane 输入也遵守同一契约；支持域政策未新增。

setup 输出必须通过刚体、官方逆矩阵、两相机投影矩阵公式及真实点数值检查才能 grid。新 sidecar 绑定 config.mat hash，版本 `OFFICIAL_UNIT_PLANE_RIGID_GRID_V2` 加入 coordinate_frame_id、reference_plane_id、GUI 输入签名和 cache_key。缺失/旧版本/文件变化均拒绝；旧 reference 不迁移、不复用其系数。fixed_run 只复制经验证 setup 和证书，不改 setup 输出矩阵。

为隔离本修复，复制旧真实 WASS clouds 到新目录，保留 SHA256、相同 baseline、相同 domain/N/官方参数，再由原官方 setup/grid/ncplot 重建。没有改观察点、第三方源码或随机种子。每帧均匀取 1000 个**真实解码 WASS 点**，两相机均验证。统计与原审计随机采样人口不同，不能替换审计数值；下表是本次同点前后配对实验。

|数据/帧|正交误差 前→后|det 前→后|camera→grid→camera 最大 B 前→后|cam0 回投影 median/max px 前→后|
|---|---|---|---|---|
|HomeTank 21|0.005643945572 → 1.577e-16|0.996009127813 → 1|0.0244522 → 1.831e-15|0.738130/1.833587 → 2.344e-13/7.626e-13|
|HomeTank 22|同上|同上|0.0245755 → 1.831e-15|0.732406/2.536588 → 2.344e-13/7.626e-13|
|HomeTank 23|同上|同上|0.0225500 → 9.992e-16|0.641573/1.905120 → 2.318e-13/5.684e-13|
|Vieira 0|8.543169429e-6 → 1.926e-16|0.999993959067 → 1|0.000702259 → 1.628e-14|0.002627/0.005570 → 1.705e-13/6.915e-13|

完整 4 个 HomeTank + 5 个 Vieira 帧、cam1、forward matrix、原/新 plane/ID/hash 见 `evidence/I12_validation.json`。HomeTank 上述 B 误差可乘 0.070 转 m；Vieira 仍为 B，不能转物理 mm。新参考来自新坐标网格的指定帧，最终新 HomeTank 正式 reference 还会在全量测试后由 fresh 20s 单帧重新生成并固定。

单项新测试 6 项 + 坐标回归 7 项 + app 回归 20 项共 33/33 通过（I12_tests.txt）。旧正向结果夹具改为新官方 contract fixture；旧独立运行改为明确拒绝的负向回归。没有以 skip 掩盖旧坐标不兼容。初次证书篡改测试暴露了先解析损坏 MAT 才验 hash 的异常，现先验 hash 再解析；初始日志保留 I12_tests_initial.txt。开发过程一个验证矩阵的 3×4/4×4 形状错误已修正；一次测试 offscreen 环境导致官方 OpenGL context 创建失败，移除该测试环境变量后原渲染器正常，两次失败目录保留，不改第三方实现。

这些检查证明数据链几何一致，不证明 clouds 是水面。I04/I05/I06 与其他 P1 保持未修。
