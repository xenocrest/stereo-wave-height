# 瞬时水面测量正式定义

项目的基本结果是指定时刻 `t_k` 的 `H(x,y,t_k)`。每个有效记录必须同时保存 `frame_id、timestamp、u、v、X、Y、Z、H、provenance、reference_plane_id`。多个帧不得平均后冒充一个瞬时帧。

WASS 在第 `k` 帧产生三维点 `P_i(t_k)=[X_i,Y_i,Z_i]^T`。固定参考面为 `Π_ref: n^T P+d=0`，`||n||=1`，法向朝上。瞬时有符号高度为 `H_i(t_k)=n^T P_i(t_k)+d`。XYZ 和 `d` 使用相同物理长度单位；导出 `H_mm` 时从米乘以 1000。Vieira 作者样例只有归一化基线单位 `B`，不能导出毫米高度，也不能用来做毫米真值比较。

`reference.mode=provided_physical_plane` 接收测量得到的 `n_x,n_y,n_z,d`；配置人必须先把平面转换到 `official_grid_m` 坐标系，并记录测量与配准证据。`reference.mode=designated_static_water_frame` 指定明确的静水帧 ID；程序对该帧官方网格有效 XYZ 以最小二乘建立一次平面，此后冻结同一个 `n,d`。这一参考面标为 `INTERNAL_STATIC_REFERENCE`，不构成独立真值。参考面不随帧变化。该平面拟合只定义外部比较的零位，不更改 WASS 或官方网格数据。

历史结果中的 WASS/wassgridsurface mean sea plane 是官方算法内部辅助坐标。旧结果展示注明 `WASS_INTERNAL_MEAN_PLANE_VISUALIZATION_ONLY`；不能把它称为独立测量的固定物理参考。旧 `pixel_height/*.npz` 保留原样，新的固定参考高度在独立验证层重新计算。

`provenance` 为 `DIRECT_STEREO`、`OFFICIAL_GRID_ESTIMATE`、`NO_DATA`。现有 `wassncplot` pixel↔XYZ 有效网格全部标为 `OFFICIAL_GRID_ESTIMATE`；不能称为逐像素直接双目测量。无数据高度写空值。`instantaneous_height.csv` 的 `export_stride=1` 才覆盖全像素；任何抽样导出都会在 manifest 记录步长。

时间以同步结果 `sync/sync.json` 的相机 LEFT 请求时间为准；实际容器取帧时间误差仍需设备实验核验。视觉与外部传感器采用另一个明确偏移：`t_camera=t_sensor+offset_ms/1000`。外部偏移未知时停止瞬时真实性判断。
