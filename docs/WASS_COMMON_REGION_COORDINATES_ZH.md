# WASS 公共区域、bbox 与 mask 的实际坐标语义

核验日期：2026-10-01。此记录不修改第三方算法，也不把 GUI 矩形传入 WASS。

## 1. 实际版本与依据

- 实际程序：`D:/wass/dist/bin/wass_stereo.exe`，版本 `1.11_heads/master-0-g6b82aeb`。
- 本地源码根目录：`D:/stereo-wave-height-runs/vieira2025-full-repro-20260916/sources/wass-src/wass-master`。
- 主文件：`src/wass_stereo/wass_stereo.cpp`。下面行号对应本地冻结副本，不保证当前网络 master 行号相同。
- [官方 stereo 文档](https://www.dsi.unive.it/wass/documentation/stereo.html)说明自动左右检测及交换；[官方源码仓库](https://github.com/fbergama/wass)用于交叉核验。具体 mask 结论以本地版本源码为准。

## 2. 配置项在哪里生效

| 配置项 | 本地定义 | 实际作用 |
|---|---|---|
| TRIANG_BBOX_TOP/LEFT/RIGHT/BOTTOM | 1031–1034 | `triangulate()` 内限制内部 left 相机的去畸变图像坐标 |
| LEFT_MASK_IMAGE | 1035，1057–1068 | workspace 相对路径，灰度读取，尺寸必须等于内部 left 图像，值 >0.5 为有效 |
| RIGHT_MASK_IMAGE | 1036，1077–1087 | 同理，作用于内部 right 相机 |

1047–1054：四个 bbox 数值必须全部非负才启用；否则使用整图默认边界。1240 附近用严格不等式排除边界点。

393–396：内部 left/right 的初始图像来自 `workspace/undistorted/00000000.png` 和 `00000001.png`，而不是原始带畸变视频帧。

1219–1254：视差匹配位置先 `env.unrectify()` 从 rectified 图映射回去畸变图的 pi/qi，再检查图像范围、bbox、左右 mask。之后才继续三角测量的角度等检查。mask **不是作用于原始视频像素或 rectified 像素，也不在 matcher 中屏蔽特征或限制 dense matching 计算范围**；它在三角测量阶段决定候选是否跳过。

1057–1093：mask 默认全有效；尺寸错误或文件缺失仅记录 `not found or invalid image`，并没有在该处严格终止。另有 `DISCARD_BURNED_AREAS` 根据去畸变图值 >254 排除饱和区域。这是官方图像质量规则，不是几何公共区域。

474 附近及官方文档：算法可以自动交换内部左右。LEFT/RIGHT 不可未经核验就解释为 GUI 导入的 cam0/cam1。GUI 原图框还涉及 prepare 的尺寸/内参缩放、去畸变与相机交换，因此本轮不将框生成科学 mask。

## 3. 三类区域不能混同

1. COMMON_STEREO_REGION：左右相机在指定三维场景/深度与坐标约定下共同有效的可见域。
2. MEASUREMENT_REGION：用户希望研究的矩形；不证明双目可见，不证明真实水面。
3. HEIGHT_AVAILABLE_REGION：当前官方 pixel map 中具有有限 XYZ/H 的输出像素；包含 OFFICIAL_GRID_ESTIMATE，不代表直接 stereo support。

undistortion validity 只说明单相机重映射可用；把两幅不同相机图像的同坐标 mask 相交不证明它们看的是同一三维点。WASS 自己的 rectified matching ROI 也不能直接当成原始图上的严格水面公共可见 mask。三角测量成功点只能证明这些点得到输出，不能证明所有未成功点不在公共视野。

当前冻结 WASS/pipeline 没有向 GUI 暴露符合上述完整语义、并绑定标定/尺寸/坐标系的独立公共 mask。因此**不生成近似框**：

`Common Stereo Region: NOT_AVAILABLE (COMMON_REGION_NOT_AVAILABLE)`

显示、hover、导出 metadata 使用同一状态。已有青色轮廓仍只表示 HEIGHT_AVAILABLE_REGION；紫色框仍只表示 MEASUREMENT_REGION。此处理符合 V1 本轮验收允许的诚实不可用分支。

## 4. 固定参考面为何还要固定官方网格 setup

[wassgridsurface 0.11.4 官方用法](https://pypi.org/project/wassgridsurface/0.11.4/)明确提供 `grid --gridsetup config.mat`。

本地 `Lib/site-packages/wassgridsurface/wassgridsurface.py`：setup（55–230 行）保存 Rpl/Tpl、CAM_BASELINE、Cam0toGrid/Cam1toGrid 及 P0/P1；grid（233 行起，尤其 313 行）读取指定 setup 并调用官方 `align_on_sea_plane_RT`，没有重新 setup。独立 setup 则在 648–652 行根据本次 planes 取 mean plane，不能只因 K/D/R/T 相同就宣称网格坐标相同。

本轮 Adapter 对后续独立运行复用完全冻结的标定六文件及原始官方 config.mat；新建 workspace，执行官方 prepare/stereo/grid/savexyz。在 grid 前检查 workspace P0/P1、K0/K1 相同，不进行 ICP、自动旋转/平移或重新估计 offset。首次流水线原封不动，pipeline 源码修改为 0。

coordinate_frame_id 是标定身份、外参身份、上述实际官方坐标变换/投影数值及单位约定的 SHA256，不包含 run 路径。不同独立目录可具有相同坐标身份；任一身份不一致或缺失时，在调用冻结 H=nᵀP+d 之前拒绝并显示 REFERENCE_FRAME_MISMATCH。
