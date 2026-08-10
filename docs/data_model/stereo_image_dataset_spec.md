# 双目图像数据集规范

## 1. 统一目录

仿真和未来真实设备使用同一逻辑结构：

```text
dataset/
├── left/                    # 左相机帧
├── right/                   # 右相机帧
├── calibration/             # 内参、畸变、外参与尺度记录
└── metadata/
    ├── dataset.yaml         # 数据集级来源、坐标、时钟和格式
    ├── frames.csv           # 一行一个双目帧对
    └── checksums.sha256     # 输入文件校验
```

大型图像数据不提交 Git。WASS 工作目录可由适配步骤生成，但不能反向修改原始数据集。

## 2. 帧对记录

`metadata/frames.csv` 至少包含：

| 字段 | 类型 | 单位 | 含义 |
|---|---|---|---|
| `frame_id` | string | — | 数据集内唯一、稳定的帧对 ID |
| `timestamp_ns` | int64 | ns | 该帧对的有效曝光时间 |
| `time_reference` | string | — | 仿真、设备、触发或 UTC 时钟域 |
| `left_image` | relative path | — | `left/` 下图像路径 |
| `right_image` | relative path | — | `right/` 下图像路径 |
| `left_timestamp_ns` | int64/null | ns | 左相机有效曝光时间；UNKNOWN 时为空 |
| `right_timestamp_ns` | int64/null | ns | 右相机有效曝光时间；UNKNOWN 时为空 |
| `sync_offset_ns` | int64/null | ns | `right-left`；未测时为空并标 UNKNOWN |
| `pair_status` | enum | — | `valid`、`invalid` 或 `UNKNOWN` |

`frame_id` 只用于身份和排序，不能作为时间替代品。左右缺帧不得通过“最近文件名”静默配对。

## 3. 图像层次与格式

### 原始/采集层

- 真实设备优先保存厂商 SDK 无损输出或无损 TIFF/PNG，并记录像素格式；
- 仿真保存由数学模型生成的无损图像；
- 不允许有损 JPEG 作为科学主输入；调试预览必须与主输入分离。

### WASS 规范化输入层

当前复现设计使用无损 8-bit 灰度 PNG，并生成符合 WASS 帧命名/目录要求的副本或链接。RAW/Bayer 到灰度的算法、版本、黑白电平和缩放必须记录，规范化结果不能覆盖原始数据。

WASS 实际接口依据见 [WASS 输入输出规范](../wass/input_output_spec.md)。

## 4. 数据集级图像字段

| 字段 | 要求 |
|---|---|
| `width_px,height_px` | 正整数，单位 px；左右必须声明，是否相同需校验 |
| `bit_depth` | 单通道有效位深，单位 bit |
| `pixel_format` | 如 `BayerRG8`、`BayerRG10`、`Mono8`、`Gray8`；不能只写“RAW” |
| `color_model` | `bayer`、`grayscale`、`rgb` 或明确枚举 |
| `encoding` | PNG/TIFF 等无损编码 |
| `camera_id` | 与标定文件和左右角色绑定 |
| `source_type` | `simulation` 或 `physical_camera` |
| `source_status` | `simulation_truth`、`candidate`、`confirmed` 或 `UNKNOWN` |

## 5. 当前候选设备映射

| 参数 | 当前值 | 单位 | 来源 | 状态 |
|---|---:|---|---|---|
| 相机型号 | MER2-503-36U3C | — | 设备候选配置 | candidate，未声明已采购 |
| 分辨率 | 2448×2048 | px | 厂商规格记录 | candidate |
| 像元间距 | 3.45 | µm/px | 厂商规格记录 | candidate |
| 像素格式 | BayerRG8/BayerRG10 | bit | 厂商规格记录 | candidate |

仿真可以使用同样的分辨率和名义内参，但 `source_type=simulation`；未来实体数据使用 `source_type=physical_camera`。相同尺寸不代表相同来源或同一标定。

## 6. 同步要求

- 左右图必须对应同一个触发事件或明确的仿真时刻；
- 曝光起始/中心时刻定义必须写入 `timestamp_semantics`；
- 时钟域、时间原点、时间戳单位和同步偏差必须明确；
- 当前实体相机同步偏差阈值为 `UNKNOWN/TODO`，不能伪填零；
- 仿真理想同步可设 `sync_offset_ns=0`，但状态必须为 `ideal_simulation_assumption`；
- 超过验收阈值、丢帧或来源不明的帧对标记 `invalid`，不得进入 WASS 主处理集合。

## 7. 标定关联

`calibration/` 中每组内参、畸变和外参必须具有 `calibration_id`。`dataset.yaml` 记录左右 `camera_id → calibration_id` 映射、图像尺寸、裁剪/缩放历史和单位。仿真名义内参标为 `SIMULATION_NOMINAL`，不能标为 `CALIBRATED`。
