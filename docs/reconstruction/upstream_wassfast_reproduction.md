# 官方 WASSfast 隔离复现记录

日期：2026-09-04。起始 HEAD：`0159cea661e6f9f40fafc5c0dcaca21b21fde4ab`。

## 目的与边界

先复现现有开源海面重建方法，再评估接入项目；不继续自研匹配或水槽底部折射主线。
本次不修改 GUI/EXE、标定、原始 WASS、既有实验结果。
WASSfast 是待验证候选，不因有论文就视为适配当前数据或满足逐像素准确度要求。

## 上游与方法

- [官方仓库及复现说明](https://gitlab.com/fibe/wassfast)。
- [官方发布包 WASSfast 1.6.3](https://pypi.org/project/wassfast/1.6.3/)。
- [Physics-driven CNN 论文](https://www.mdpi.com/2072-4292/13/18/3780)。
- [官方样例](https://www.dais.unive.it/wass/wassfast_testdata_256.7z)。

选择官方推荐 CNN 路径：官方稀疏双目观测、三角化、共同平面坐标与尺度变换、规则网格、
相邻时刻波动传播和预训练稀疏 CNN。不是把一般单目深度图当成物理高度。
也不是直接把项目 xyzC 送入网络：官方完整程序自带稀疏观测生成流程。

已检查发布包 `cnn/wavenet_models.py:create_model_with_prediction`：
输入为三个时刻的稀疏网格与四通道复数相位因子；NaN 表示缺失。
官方示例采用 256×256 物理网格，不等同于每个原始 4K 像素都有独立测量。
网络输出是估计值，必须与实际观测支持区分。

## 隔离环境

外部目录：`D:/stereo-wave-height-runs/upstream_wassfast/`。
Python 3.12.5，专用 venv，不污染现有程序环境。

默认 `pip install wassfast==1.6.3` 在 Windows 失败：
`nvidia-nccl-cu12<3.0,>=2.25.1` 无对应发行包；来自 `tensorflow[and-cuda]==2.20`。
替代仅为同版 TensorFlow CPU 运行依赖，不改网络、权重或数值算法。

```powershell
python -m venv <isolated>/venv
<isolated>/venv/Scripts/python -m pip install --no-deps wassfast==1.6.3
<isolated>/venv/Scripts/python -m pip install tensorflow==2.20 numpy matplotlib netcdf4 pyopengl scipy opencv-python tqdm glfw mako py7zr
<isolated>/venv/Scripts/python tools/check_upstream_wassfast.py --output <isolated>/network_contract.json
```

这里的检查仅载入官方架构和两组官方 H5 权重，执行人工零输入的形状/有限值检查。
**不是官方海面样例复现，不是物理验证，更不是 HomeTank 重建成功。**
脚本拒绝覆盖输出；权重哈希、环境版本及执行时间写入结果 JSON。

## 接口风险：必须验证，不能猜测

发布包 `_wassfast.py` 将相机点转换到平面坐标并乘 baseline，Z 翻向；
CNN 路径使用批次统计量归一化及反归一化，不能脱离该处理直接解释网络输出单位。
`netcdfoutput.py` 的维度是 `Z(count,X,Y)`，不能直接认作项目的 `Z(time,y,x)`。
`X_grid/Y_grid/Z` 属性声明毫米，`scale` 声明米。

发现值得单独核对的上游接口问题：CNN 保存 `Z` 时乘 1000，而可选 `Zinput`
反归一化后未同样乘 1000，二者属性却均声明毫米。接入前必须用真实样例数值验证，
不能仅信属性自动混用；本轮不补丁上游。

## 第一轮环境验证（历史记录）

安装完成，`python -m wassfast --help` 退出码 0。官方网络契约检查 PASS：

| 项目 | 实际结果 |
| --- | --- |
| 运行设备 | CPU |
| TensorFlow / Keras | 2.20.0 / 3.15.1 |
| NumPy / OpenCV | 2.5.2 / 5.0.0.93 |
| 网络及权重加载 | 1.853 s |
| 单次网络前向调用（非完整重建） | 0.205 s |
| 输出形状 / 有限值数量 | 1×256×256×1 / 65,536 |
| 人工零输入输出范围 | −0.00396498 至 +0.02036925（网络单位，不是米） |

零输入输出并非严格零，因此不能从有限输出或覆盖率推断准确度。
完整结果在仓库外 `D:/stereo-wave-height-runs/upstream_wassfast/network_contract.json`。
两组权重 SHA256：

- `2021-06-30_16-48-27.h5`：`8205bba4fae8291ad63c2c1178129331704b2a4055c2003a4ee1ac6288e86205`。
- `2021-07-01_12-00-44_3.h5`：`2b3607bc210515f182c729e7389fbe7a25f5361484db8ea57a19ee9dc3608edc`。

官方样例大小 122,583,502 字节，服务端支持 Range。
本机下载尝试 300 秒仅收到 1,487,935 字节后超时；别名域名与有限 Range 探测同样缓慢。
因此样例尚未完整取得，未运行官方完整海面处理，未生成任何本项目新高度结果。
后续下载必须断点续传，不能把不完整压缩包当输入。
已检查官方 `synthetic/wassdatagen.py`：它仍需要外部 NetCDF/HDF5 输入，
不是可以无数据直接复现的替代小样例，因此没有自行造数据冒充官方复现。

下一步依次为：官方网络运行检查 → 官方原始样例及其配置完整复现 →
核对坐标/单位/观测支持 → 少量项目帧同域比较。
只在证据支持时接入现有后端；不重新包装演示程序，不宣称已解决全水面高度。

## 第二轮：官方样例完整闭环已执行

继续任务起始 HEAD：`37f86ded3f728a36e5a6275ff286a2947e54b819`。
使用 requests 的四连接分块下载解决了下载阻塞；每块检查 HTTP 206、Content-Range、
ETag 和长度，合并后成功解压。完整档案 SHA256：
`cec7ebc72a4ceb89d9784b2843094891acb52bdc52ffe6350e1335e578ed146c`。
没有伪造缺失样例或用自造图像替换。

执行样例脚本中的全部数值参数，仅将旧模块入口改为发布包的 `python -m wassfast`。

```powershell
python -m wassfast ./input ./config256.mat ./config ./settings.cfg RLTB CNN --batchsize 16 -n 49 -r 15.0 --debug_stats --nographics -o <isolated>/official_output.nc
```

第一轮 return code=0。随后增加官方 `--savepts --saveCNNinput -dd <isolated>/official_observations`
再次执行，return code=0，输出 `official_observable.nc`。这些仅增加诊断保存，不改变参数。
上游对点云有随机排列，第二轮数值与第一轮有小差异；没有选最优结果。
正式统计来自第二轮。未执行原 WASS 核心程序、未运行标定或修改模型。

| 项目 | 实际结果 |
| --- | --- |
| 官方左右图像数 | 各 50 张 |
| 图像尺寸 | 2456×2058 |
| 生成高度帧数 | 50；该版本 `-n 49` 实际包含 0…49 |
| 网格 | 256×256；dx=dy=0.352941 m |
| X/Y范围 | X=−45…45 m；Y=−115…−25 m |
| 样例基线 | 3.323 m，来自官方 config256.mat，不是本项目硬件参数 |
| 原始观测网格平均支持率 | 14.9382%（逐帧 14.6927%…15.1367%） |
| CNN 有限估计平均比例 | 91.7367%（逐帧 91.6321%…91.8137%） |
| 相对官方平面高度范围 | −0.938343…+0.972388 m |
| 独立物理精度 | NOT_VALIDATED；样例未提供本轮可用的独立高度真值 |
| HomeTank_006 同模型运行 | NOT_RUN；不能将官方海面结果归给水槽视频 |

原始观测支持率由官方 `Zinput` 的有限位置统计，仅使用 mask、不读取其有争议的数值单位。
有限估计比例不是测量成功率；缺失的约 8.26% 仍保留 NaN，不强填。
这也说明官方 CNN 本身不是保证“任何 ROI 全像素都有可靠高度”的接口。

### 已处理的输出接口问题

1. 官方 CNN 的 `X_grid` 沿列变化、`Y_grid` 沿行变化，尽管维度名为 `(X,Y)`。
   项目读取器检查真实坐标数组可分离性及单调性，保留实际 `[time,y,x]` 排列，不盲目转置。
2. 官方 `workdir` 在每批重置为 0…15；不能拿它作为全局帧 ID。
   输出使用独立 output_index 和原有相对时间，保留原始 workdir 供审计。
3. 样例脚本用 `-r 15.0` 覆盖文件名时间间隔；本轮照官方复现，记录为相对时间，
   不将它认定为本项目视频的同步结果。
4. CNN 输出的 `maskZ` 未填充，不能当作有效 mask。
   使用 finite_estimate_mask，并单独保存 raw_support_mask。
5. `Z` 毫米除以 1000 得米；检查版本、单位、baseline、平面矩阵、网格范围。
   非匹配配置明确报错，未经验证版本不自动兼容。

项目薄适配器：`src/adapters/wassfast/output.py`。
复用既有 `reconstruction.height.height_from_plane`：

```text
P_plane = (X_grid, Y_grid, Z_official)
H = (n dot P_plane + D) / norm(n)
n = (0,0,1), D = 0 in the official plane-aligned coordinate system
```

这里 Z 已是官方平面变换后的垂直分量，**不是 camera Z**。
没有对每帧重新拟合或重新置零，也没有标尺参与解算。

```powershell
$env:PYTHONPATH='<repo>/src'
python tools/report_upstream_wassfast.py --input <isolated>/official_observable.nc --config <sample>/config256.mat --output <new-output-directory>
```

实际结果路径：

- `D:/stereo-wave-height-runs/upstream_wassfast/project_height_v2/result.json`
- `D:/stereo-wave-height-runs/upstream_wassfast/project_height_v2/height_estimates.npz`
- `D:/stereo-wave-height-runs/upstream_wassfast/project_height_v2/support_and_estimate.png`
- 原始运行日志 `official_run.log`、`official_observable.log` 位于 isolated 目录。

### HomeTank_006 接入关口：不能通过复制配置绕过

检查现有 `rig_features_metric/result.json`：
`approved_for_reconstruction=false`，基线 0.115797906 m，状态仍为候选尺度。
已有 fixed-ROI 记录的同步也是 audio candidate，不是 verified frame sync。
没有发现该实验可直接复用的官方 `config.mat` 水面参考坐标配置。

这不是重新归咎于水面质量。缺少的是可确认的**观测对象与水面参考几何**：
现有记录已确认部分纹理是槽底，墙面/标尺点不能作为水面控制点。
WASSfast 的 `Cam2SeaH` 在匹配前就需要共同水面参考平面；任取墙面拟合平面、
搬用官方海面平面或旧水槽平面，均会把错误几何包装成完整高度。
因此本轮没有这样接入 HomeTank_006，也没有宣称用户视频目标已完成。

可复用成果已经是官方模型到项目高度文件的真实闭环。后续只有建立可信的当前数据
水面观测/参考几何，或使用带标定与参考的真实海面双目数据，才能推进可靠的物理验证。
更换匹配模型可作为观测能力对照，但不能直接证明匹配到的槽底就是水面。

### 检查

新增 3 项读取器测试：物理轴/尺度与未知支持、未知单位拒绝、错误网格方向拒绝。
全部测试：466 passed、1 skipped、4 subtests passed。
Windows NetCDF 在中文临时路径下创建测试文件失败；改用 ASCII 的隔离 pytest basetemp 后通过，
未修改算法或吞掉异常。真实运行及所有大型结果都位于仓库外。
