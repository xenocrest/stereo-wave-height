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

## 当前实际状态与下一步

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
