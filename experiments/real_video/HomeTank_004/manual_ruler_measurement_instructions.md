# HomeTank_004 Phase 4 人工标尺读数说明

状态：`MANUAL_REFERENCE_REQUIRED`

请只查看冻结的正式 R0 图像，不要调整同步、标定、WASS、参考平面或高度结果。

## 需要查看的时刻

| 场景 | 正式目标时刻 |
|---|---:|
| Static R0 | 10.012256 s |
| Wave R0 | 20.000000 s |

## 每个时刻需要填写

在 [ruler_measurement.yaml](ruler_measurement.yaml) 中填写：

1. 选择一个能清楚读取水面线的相机画面：`cam0` 或 `cam1`。Static 与 Wave 必须使用同一相机和同一刻度方向。
2. 水面线标尺读数，单位 mm。
3. 读数不确定度，单位 mm，例如人工判断为 ±0.5 mm 时填写 `0.5`。
4. 水面线所在像素 `(u_px, v_px)`，以及人工定位不确定度，单位 pixel。
5. 标尺数值增大方向与算法正高度的关系：`INCREASES_WITH_POSITIVE_HEIGHT` 或 `DECREASES_WITH_POSITIVE_HEIGHT`。

不要把未知量填写为 `0`；未知时保持 `null`。当前不预选 `cam0` 或 `cam1`，因为尚无人工确认哪个正式 R0 画面能清晰读尺。系统不会自动识别刻度，也不会猜测水位。

## 比较方式

标尺变化量先按已填写的刻度方向转换为算法参考平面法向的正高度。算法端只查询人工水面线像素附近已经存在的 pixel–XYZ/height 观测，不插值生成点。正式局部读数采用局部中位数，同时保留最近点高度、点数、像素距离和局部离散度。

距离门、局部半径和最少点数当前保持 `null`，需在取得人工像素不确定度并检查冻结结果采样密度后确定。若附近没有观测，必须返回 `NO_VALID_RECONSTRUCTION_NEAR_REFERENCE`。
