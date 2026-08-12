# 设备与部署参数登记表

## 状态规则

- `confirmed`：来源和实物/标定状态均已核验，可进入正式实验配置；
- `candidate`：候选设备或项目暂定规格，尚未采购、标定或最终确认；
- `UNKNOWN`：没有可接受的确定值，配置中必须使用 `null`；后续动作标记 `TODO`。

机器可读配置见 [`configs/equipment/candidate_system.yaml`](../../configs/equipment/candidate_system.yaml)。数值、单位、来源和状态必须同时更新，禁止只修改文档或只修改 YAML。

## 当前登记

| 参数名称 | 数值 | 单位 | 来源 | 状态 |
|---|---:|---|---|---|
| `camera.model` | MER2-503-36U3C | — | [大恒图像厂商规格](https://en.daheng-imaging.com/show-106-1991-1.html) | candidate |
| `camera.resolution.width` | 2448 | px | 厂商规格 | candidate |
| `camera.resolution.height` | 2048 | px | 厂商规格 | candidate |
| `camera.pixel_size` | 3.45 | µm/px | 厂商规格 | candidate |
| `camera.shutter` | global | — | 厂商规格 | candidate |
| `camera.bit_depth` | 8、10 | bit | 厂商规格（BayerRG8/BayerRG10） | candidate |
| `lens.focal_length` | 8.0 | mm | 用户给定的项目候选规格；厂商和型号 UNKNOWN | candidate |
| `stereo.baseline` | UNKNOWN (`null`) | m | 尚未设计/实测 | UNKNOWN/TODO |
| `stereo.working_distance` | UNKNOWN (`null`) | m | 部署变量，尚未确定 | UNKNOWN/TODO |
| `deployment.target_distance` | UNKNOWN (`null`) | m | 部署条件未确定 | UNKNOWN/TODO |
| `deployment.water_tank_size` | UNKNOWN | m | 实验条件未确定；不写入固定值 | UNKNOWN/TODO |
| `calibration.fx,fy,cx,cy` | UNKNOWN | px | 待两相机分别标定 | UNKNOWN/TODO |
| `stereo.disparity_uncertainty` | UNKNOWN | px | 待在目标水面成像条件下实测 | UNKNOWN/TODO |

## 派生量登记规则

派生量必须同时记录公式和输入版本。例如候选名义像素焦距

$
f_{px,nom}=\frac{8.0\ \mathrm{mm}}{0.00345\ \mathrm{mm/px}}\approx2318.8\ \mathrm{px}
$

只能标为 `candidate/derived`，不能替代标定的 `fx,fy`。任何涉及基线、工作距离或水槽尺寸的派生量，在输入为 `UNKNOWN` 时也保持 `UNKNOWN`。

## 确认流程

1. 保存厂商数据页、设备序列号和镜头准确型号；
2. 在最终分辨率、焦距、对焦和光圈下标定两台相机；
3. 设计并实测光心基线和部署工作距离；
4. 以刚体尺度、重投影误差和重复测量验证；
5. 通过后将对应值及来源更新为 `confirmed`。
