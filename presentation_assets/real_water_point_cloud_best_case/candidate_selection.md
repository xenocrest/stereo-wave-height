# 真实水面 WASS 点云展示案例筛选

所有预览均使用原始 XYZ、相同的确定性抽样方式、物理比例坐标轴和 oblique / top-ish / side-ish 三种观察视角。视觉分级只用于选择汇报图片，不是精度评价。

| Candidate | Dataset | Role | Time | XYZ | Mapping available | Visual quality | Final |
|---|---|---:|---:|---:|---|---|---|
| A | HomeTank_005 | Measurement | 44.3345 s | 74,164 | per-point pixel↔XYZ | POOR | No |
| B | HomeTank_005 | Reference | 8.574578 s | 101,548 | per-point pixel↔XYZ | POOR | No |
| C | HomeTank_005 | Measurement | 68.501800 s | 117,450 | per-point pixel↔XYZ | GOOD | **Yes** |
| D | HomeTank_005 | Measurement | 48.001267 s | 98,438 | per-point pixel↔XYZ | ACCEPTABLE | No |

Candidate C 的主体连续性最好，脱离主体的离散点较少，同时保存了原始左右帧、PLY、逐点 pixel↔XYZ、运行请求和结果 metadata。全部 117,450 个点都可以映射回 1920×1080 的 canonical RIGHT/cam1 图像，因此选择为汇报案例。

原 44.3345 s 案例仍保留在 `presentation_assets/real_water_point_cloud/`，分类为 `REAL_WASS_RESULT_BUT_POOR_PRESENTATION_QUALITY`：它是真实 WASS 结果，但主体结构视觉不够自然、离散结构明显，不再作为最佳汇报代表图。

“最佳案例”仅表示更适合可视化说明，并不构成点云几何精度更高的独立证据。

