# 官方方法与实际版本复核

本轮先读指定九份项目文档，再核对外部原始方法与本地科学源码，随后检查项目实现。历史验收只是待核验线索。未改正式科学代码或第三方算法。项目实际服务在 `app/core.py`，并不存在交接说明中的 `app/services/ResultService`；本轮正对照调用的是实际 `core.load_result`、`core.hover`、`MainWindow._build_overlay` 和 `PointCloudView.show_ply`。

## 原始方法

- [Vieira 2020，DOI 10.3390/jmse8110831](https://doi.org/10.3390/jmse8110831)：阅读了[论文正文](https://pdfs.semanticscholar.org/545f/b1222eb819f89fd9fd3224bbf5a178aa5b87.pdf)的方法部分。该研究用手机、音频 TLCC、Matlab 内参标定及 WASS 外参；单一长期平均平面用于坐标对齐。其统计验证不能替代本项目指定时刻的独立高度验证。
- [Vieira 2025，DOI 10.1016/j.coastaleng.2024.104694](https://doi.org/10.1016/j.coastaleng.2024.104694)：读取本地完整 PDF，核对第 2–4 页方法与第 4 页 Fig.1。论文用约 50 个棋盘姿态、OpenCV 内参、WASS 外参、音频同步；海面点云对齐后做规则网格处理。论文中的线性插值与当前软件默认 DCT 处理不能视为同一算法。
- [wass_lowcost 作者仓库](https://github.com/matheusdpv/wass_lowcost)：核对冻结 `wass_sync.py`、`README.md` 与项目 Praat/FIR 包装。公开样例是同步 TIFF，并非完整原始视频。作者代码包含视频重编码分支，当前项目采用原始视频直接提帧；必须独立核对实际 PTS。

论文与作者配置说明科学思路；本轮当前行为由以下安装版本与冻结源码决定，而非猜测网络 master。

## WASS 语义

[官方 Getting started](https://www.dais.unive.it/wass/documentation/getting_started.html)和[stereo 配置说明](https://www.dais.unive.it/wass/documentation/stereo.html)与本地 `src/wass_prepare/wass_prepare.cpp`、`src/wass_stereo/wass_stereo.cpp`、`PovMesh.cpp`交叉核对：

1. prepare 在原始图像上应用 K/D，保存完整尺寸去畸变图与内参；不是 rectification。
2. match 建立稀疏对应；autocalibrate 估计相对姿态。执行成功不证明姿态正确。
3. stereo 将 T 归一化到单位基线，可能交换内部 left/right，同时改写相机 P/pose 的对应。HomeTank 实际 internal left=cam1、right=cam0，输出 P0/P1 仍须按文件核对。
4. dense disparity 经去噪/形态操作、unrectify、mask/bbox、三角化，然后 z-gap 连通分量筛选。
5. `SAVE_FULL_MESH` 在 **z-gap 筛选之后、plane 筛选之前**保存 `mesh_full.ply`。它不是全部未经筛选的三角化点。官方现有输出没有保存本轮最初 187,897 点的完整 XYZ；不能把后续文件改名冒充它。
6. plane RANSAC 与 refinement 可包含任何保留场景结构。此处没有自动水面语义识别。
7. `mesh_cam.xyzC`用于官方后处理；PLY用于诊断。两者单位为归一化基线 B，相机坐标 Z 不是水面 H。
8. `LEFT_MASK_IMAGE`/`RIGHT_MASK_IMAGE`在实际内部左右去畸变坐标上检查；不是原图、不是 rectified 像素、也不限制 matcher。已核对本地第 1031–1093、1219–1265 行。尺寸错误可能仅告警，所以 A/B 必须核对日志确实加载。
9. `TRIANG_MIN_ANGLE`虽然被命名为 ray angle，本地第 1258–1263 行实际使用 `normalize(R*q+T)` 的单位深度端点代理量。不能把该阈值直接当作最终点的真实两相机夹角；本轮另由实际相机中心计算真实夹角，未改变该官方规则。

## wassgridsurface / wassncplot

[wassgridsurface 0.11.4 官方流程](https://pypi.org/project/wassgridsurface/0.11.4/)要求生成配置、setup、检查 `area_grid.png` 再 grid。安装版 CLI 的真实 action 是 `generateconfig`，网页/旧 README 的 `generategridconfig`在本轮实际返回参数错误。失败记录保留，按安装版帮助继续复核，没有修改工具。

本地源码要点：

- `wassgridsurface.py:648–652` 对输入 planes 做系数 `nanmean`；`wass_utils.compute_sea_plane_RT`使用单位法向公式；setup 使用 `Rpl.T`作为逆。平均后的法向未经重新归一化，会违反该公式前提。
- 官方对齐为 `Q = B * S * (Rpl * P + Tpl)`，`S=diag(1,1,-1)`。z 翻转属于官方约定；不能自行再翻转。
- 当前 CLI 默认 `algorithm=DCT`；网格先量化并随机选择同格点，再 DCT 正则化。`DCTInterpolator.py:121`返回全 1 mask，故整个指定矩形可得到有限值，包括没有观测约束的边缘。
- NetCDF 的 X/Y/Z 数字按 1000 存储，声明 millimeter；官方 ncplot 读回时除 1000。若 baseline 只是 B=1，文件原生 meter/mm 标签也只是数值格式，不能获得独立米制尺度。项目 NPZ/viewer 保留 B 是必要的。
- [wassncplot](https://pypi.org/project/wassncplot/)保存的是网格经三角形光栅化后的去畸变相机像素 XYZ。`wassncplot2.py`选择 NetCDF 的 `stereo_image_index`与 P0/P1；本轮是 cam0。framebuffer 的 1.25 倍尺寸必须由实际 shape 核验，不是相机图像扩大了视野。
- 没有调用逐帧 zeromean，没有额外网格裁剪、点云对齐或参考拟合来改善外观。

源码路径与 hash 见 `evidence/installed_scientific_package_source_hashes.json`、`evidence/third_party_unchanged_guard.json`。科学工具版本为 WASS `1.11_heads/master-0-g6b82aeb`、wassgridsurface `0.11.4`、wassncplot `2.5.3`；使用配置和默认参数的逐项比较见 `evidence/config_comparison.json`。
