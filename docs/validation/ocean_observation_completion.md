# 面向海面的 WASS 观测与逐像素补全

## 目标与路线

WASS 是主重建后端。双目同步、标定、视差、三角化仍属于原重建链；本次只修改其后处理模型，不改 WASS、标定或 GUI。历史水槽折射研究保留，但槽底纹理和已知水深不再作为工程主线输入。HomeTank_006 可见底纹不能被自动认定为水面观测。

要求同时考察两件事：真实 WASS 水面支持足够，而不是只有少数点；空间补全后公共水面 ROI 每个像素有高度，且经过留出验证仍保持曲面趋势。单纯得到有限数组不代表这两项都通过。

## 数学与像素对应

米制水面点 P 相对独立、固定参考平面 n·P+c=0 的高度为：

$$
H(P)=\frac{n\cdot P+c}{\lVert n\rVert}.
$$

参考法向必须统一朝上，不能每个 wave 帧重新置零；相机 Z 不能直接冒充水面高度。WASS 投影矩阵将原始相机点投到对应的 rectified 像素；canonical 输出必须经已有标定映射取得这些像素，不能把 XYZ 包围盒拉伸成用户 ROI。

新模式使用已有标定射线与参考平面交点作为每个像素的物理坐标 (x,y)，这是用于邻域距离的**参考平面足迹近似**，不是完整非平面 ray-surface 交点反演。最终域固定为 `water_roi & safe_common_mask`。

先以观测高度拟合一次基平面 p，仅作数值去趋势，最后加回，不改变参考零点。记 q=H-p，B 为按相邻参考平面物理距离加权的四邻接差分矩阵，L=BᵀB。求解：

$$
\min_q\;\lambda\lVert Bq\rVert^2+\mu\lVert Lq\rVert^2,
\qquad q_i=H_i^{obs}-p_i\quad(i\in O).
$$

这是离散图正则化，不宣称是面积一致的连续双调和离散化。权重依赖米制坐标与采样尺度；默认沿用已有模型权重，本轮不搜索最优值。新 `hard` 模式将原始观测作为严格边界约束，未知值在该约束下共同求解。旧 `soft_legacy` 保持兼容，避免更改历史结果。修复了旧的“先软拟合再覆盖观测点”可能使邻域估计与最终观测不一致的问题。

输出区分观测关联和模型估计。无水面观测、低于调用方显式覆盖门、无锚点连通域、病态支持或未知物理坐标均拒绝，不能为了填满图强行生成水面。`observation_subject=WATER_SURFACE` 是上游对观测来源的声明，**不是程序自动识别水面**。30% 仅是本次诊断入口的明确门限，不是已验证工程标准。

## 接口

现有 `surface_completion.dense_map.build_dense_map` 新增可选模式：

```yaml
completion_strategy: ocean_observation_anchored
observation_subject: WATER_SURFACE
ocean_policy:
  minimum_observed_ratio: 0.30  # 本次诊断门，不是正式验收阈值
# frozen.common_fov_npz 必须提供同一 canonical 像素域的 safe_common_mask。
# 其余 frozen、projection、reference_plane、water_roi 字段沿用已有契约。
```

未改标尺、视频、标定、WASS 或参考平面数值。标尺仍只用于独立验证。本轮未更改 EXE，也不把诊断样例提升为当前用户视频测量结果。

## 真实海面数据来源

只读复用 `D:/WASS_DATA/work/mesh_cam.xyzC`，结合 `P0cam.txt`、`plane.txt` 和 `D:/WASS_DATA/baseline.txt`。实际查看了海面输入图片及 `stereo.jpg`，选择 computational-left rectified 半开矩形 `[900,500,2300,1450]`，避开平台、黑边与地平线；这是预选海面子区域，**不是全图或完整公共 FOV**。

历史 WASS 日志显示三角化有效点 2,761,170、最大分量/最终点 2,538,928。分量保留率约 91.95%，不是像素覆盖率，也不是本轮提升了 WASS 成功率。无新 WASS 运行。

源 xyzC SHA256：`90c75a81c592c7c1cc210058b0cb48abf13ebb9705c8f18a1d819c146b99e528`。分析前后核对源文件不变。尺度取历史 `baseline.txt=3.0 m`，**未独立核验该尺度的计量正确性**。法向符号沿用官方 plane 对齐的向上约定。

本次参考是同帧官方拟合平面，故结果仅为**相对该平面的空间形态**，不是独立静水基准下的实际波浪高度。不得把此样例接入 wave 测量后声称已经满足独立静水要求。

## 实验与结果

以原生像素步长 1 评价 1400×950 个位置。最近投影 XYZ 距离不超过 0.75 native pixel 才关联观测；该关联不是精确稠密视差栅格。全部缺口由新硬约束模型补全。另按预先固定的 8×8 像素块 `(row_block+col_block)%7==0` 隐藏观测，排除所有共享的隐藏 XYZ 后重新求解，比较恢复高度与 WASS 被隐藏观测高度。没有按误差删点或缩小评价域。

最终复验结果（原分辨率，不按结果选优）：

| 指标 | 数值 |
| --- | ---: |
| 评价像素 | 1,330,000 |
| 原始 XYZ 邻近观测关联覆盖 | 91.1746% |
| 补全后有限值覆盖 | 100% |
| 留出测试位置 | 173,525 |
| 排除共享隐藏 XYZ 后保留支持位置 | 1,036,441 |
| 留出 MAE | 8.7366 mm |
| 留出 RMSE | 18.6315 mm |
| 留出 P95 绝对误差 | 28.9583 mm |
| 留出最大绝对误差 | 496.4275 mm |
| 留出高度相关系数 | 0.995706 |
| 读取、投影、完整及留出两次求解时间（不含保存） | 24.81 s |

所有误差均是内部 WASS 曲面重现误差，**不是与真实海面独立仪器比较的误差**。整体趋势保留有证据，但约 0.50 m 最大局部误差说明不能声称每个像素都准确，不能只报相关系数。1 pixel 与此前 4 pixel 步长的留出块物理大小不同，不能把二者指标作为算法优劣对比。

结论：`OCEAN_WASS_COMPLETION_INTERNAL_TREND_PROMISING`。原分辨率所选海面范围已完整输出，主要趋势与原 WASS 曲面一致；真实物理精度、多场景原始支持提升、完整公共水面域和最终 EXE 验收均未完成。未修改或覆盖历史水槽失败结论。

结果文件：`D:/stereo-wave-height-runs/ocean_wass_completion_native_v2/result.json`；数组：同目录 `height_maps.npz`。自动化测试：454 passed、1 skipped、4 subtests passed；既有 NetCDF 二进制兼容警告 1 条，未涉及本模型。

## 复现

```powershell
$env:PYTHONPATH='src;tools'
D:/python/python.exe tools/evaluate_ocean_wass_completion.py --workdir D:/WASS_DATA/work --baseline-file D:/WASS_DATA/baseline.txt --roi 900 500 2300 1450 --stride 1 --output D:/stereo-wave-height-runs/ocean_wass_completion_native_v2
```

输出目录必须不存在，避免覆盖。数组在仓库外，含原始观测、补全、来源掩码与留出结果。`result.json` 记录参数、尺度来源、哈希及误差。本轮合成测试验证已知波形趋势、原始锚点不变、错误来源/稀疏支持拒绝、ROI 不拉伸和现有 artifact 接口兼容。

## 工程边界

- WASS 观测自身错了，严格锚定会保留这个错误；空间补全不能纠正错误三角化。
- 相关性高只能证明形态一致性，不能证明真实波形正确。局部大离群必须保留并报告。
- 全像素输出目标不降低；但低支持/不确定来源不能被悄悄转换成“测量成功”。还需在真实海面多帧、独立参考和完整公共水面范围上验证。
- 当前完成模型与现有 dense artifact 接口，不是完成 GUI 的最终海面测量验收。旧 GUI/fallback 不因此获得新的可信度声明。
