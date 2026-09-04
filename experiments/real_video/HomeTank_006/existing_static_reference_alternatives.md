# 无法补拍条件下：现有静水数据的独立对应检查

用户确认不能在原机位补拍无水槽底，本轮不再以该输入为前提。Starting HEAD：0588fa3。复用波浪视频开头第1、2、3秒静水；不修改相机标定、原视频、105mm约测输入或GUI，不重跑WASS，不使用标尺。

## 实际运行的替代路线

1. 在既有960×540校正图水域内，用OpenCV SIFT建立左右双向Lowe ratio 0.75匹配，不施加不适用于折射底点的针孔极线约束。
2. 再从原始4K视频提取对应静水帧，使用像素中心一致的4倍K/P变换重新校正。SIFT contrastThreshold固定0.01，保留弱底纹；不改变WASS或标定。水域mask最近邻放大。候选RIGHT时间偏移-0.0775s，仅静水使用，尚非独立确认的同步。
3. 将前三秒匹配联合起来，128 native像素空间块划分训练/留出；不按照几何残差挑点。用原Snell静水/平行槽底模型拟合n、c，固定depth=0.105m，水折射率1.333为近似。
4. 使用现成的Kornia LoFTR indoor_new做另一条二维匹配检查，再送入同一折射模型。网络只产生像素对应和置信度，绝不直接产生高度。依据：[Kornia官方接口](https://kornia.readthedocs.io/en/stable/feature.html)、[LoFTR作者实现](https://github.com/zju3dv/LoFTR)。这不是该模型已在水面测量上获验证的声明。

## 结果

| 方法 | 第1秒匹配数 | 第2秒匹配数 | 第3秒匹配数 | 折射几何检查 |
|---|---:|---:|---:|---|
| 960×540 SIFT | 描述子不足 | 描述子不足 | 描述子不足 | 不拟合 |
| 原始4K SIFT | 7 | 8 | 6 | 联合10训练/11留出；留出光线闭合RMS 0.133331rad，拒绝作为替代参考 |
| LoFTR二维匹配 | 20 | 16 | 10 | 前两帧留出闭合RMS 0.003829/0.003962rad；第三帧不足16个匹配，不拟合 |

4K SIFT左右关键点数分别623/1299、640/1404、617/1346。关键点多不等于可靠双目对应多。联合拟合收敛也不等于几何正确，因此没有采用明显不闭合的参考。

LoFTR对两个水域bbox各自缩放至640宽、8倍数高，保留精确坐标逆变换，并用水域mask约束匹配。32个诊断像素空间块分割训练/留出。前两帧n分别(-0.364143,-0.892301,-0.266833)、(-0.347922,-0.815152,-0.463117)，c为0.172774/0.199193m，仍有明显静水参考差异。未证明比现有RAFT参考更可靠，不据此计算或展示新的波浪高度。

## 可复现文件及依赖

```powershell
$env:PYTHONPATH='src;tools'
D:/python/python.exe tools/hometank006_static_feature_refraction.py --native-resolution --output D:/stereo-wave-height-runs/HomeTank_006/reproduce_native_reference
D:/stereo-wave-height-runs/tooling/raft-stereo-env/Scripts/python.exe tools/hometank006_loftr_reference.py --checkpoint D:/stereo-wave-height-runs/tooling/loftr_indoor_ds_new_mirror.ckpt --output D:/stereo-wave-height-runs/HomeTank_006/reproduce_loftr_reference
```

Kornia0.8.1、torch2.7.1仅位于已有仓库外试验环境，未加入GUI依赖。模型来自kornia/loftr公开权重，官方服务器下载超时、HF直连失败后经hf-mirror取回；SHA256与镜像返回的该仓库LFS对象一致：`be9ff88b323ec27889114719f668ae41aff7034b56a4c4acbd46b8b180b87ed3`。这是一致性校验，不是独立数字签名验证。代码拒绝其他hash，采用torch weights_only加载。首次运行遇到Kornia mask resize不支持bool，输入mask改为0/1 float32后，实际完成三帧；未修改第三方源码。

结果和匹配点保存在仓库外：

- `D:/stereo-wave-height-runs/HomeTank_006/static_sift_refraction/result.json`
- `D:/stereo-wave-height-runs/HomeTank_006/static_sift_refraction_native/result.json`
- `D:/stereo-wave-height-runs/HomeTank_006/static_sift_refraction_native_pooled/result.json`
- `D:/stereo-wave-height-runs/HomeTank_006/static_loftr_reference/result.json`

没有覆盖旧结果，没有全像素补高，没有假设局部均值为零。所有高度目标仍未完成；本轮排除了直接用这两套未经验证的新匹配替换参考的做法，不代表现有数据上的全部其他方法都不可能。
