# 成熟稠密模型：高度趋势接入前检查

本轮从 `11dc948d65aa6bb1c89dc34c2b4a6275d38f41f9` 继续，复用上一轮全部原始预测。
没有重跑 WASS、重新标定、调模型参数、改变 ROI、改变参考面或修改冻结演示程序。
结论：`HEIGHT_TREND_NOT_INDEPENDENTLY_VALIDATED`，不应将本次输出升级为可信全像素水面测量。

## 方法与数学含义

使用 [NVIDIA 官方 Fast-FoundationStereo](https://github.com/NVlabs/Fast-FoundationStereo) 的双向预测，
沿用上一轮 1 px 左右一致性诊断门限，不调整门限以增加覆盖。
校正后同一右像素对应左坐标 `u_left = u_right + d_right`。
在该左坐标采样反向视差，分别通过原有 OpenCV Q 和固定右相机参考面计算高度，比较两者。
这不是两个独立物理传感器，误差一致仍可能共同错误。

固定相机射线下，零主点差的水平校正模型满足：

\[
P(d)=q/d,\qquad H(d)=\frac{n\cdot q/d+c}{\|n\|},\qquad
\left|\frac{\partial H}{\partial d}\right|=
\frac{|H-c/\|n\||}{d}.
\]

这里 q 由固定像素、Q 和右相机旋转确定，长度单位为 m。导数是每像素视差误差的高度敏感度，
不是实测误差界。高度始终为点到独立参考窗口拟合平面的有符号距离，不是直接 camera Z。

跨帧只在三个有效掩码的交集上比较 `H_i-H_0`，避免不同有效区域的均值假装成波浪变化。
这是固定图像射线比较，不是同一世界 XY 的欧拉高度序列；不能直接据此宣称波谱或真实趋势通过。
依据：[OpenCV 校正与三维重投影](https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html)、
[WASS 水面重建论文](https://www.dsi.unive.it/wass/papers/1-s2.0-S0098300417304302-main.pdf)。

## 实际结果

百分比以此前预先指定的**校正后 ROI**为分母，不是全图，不与原图重采样覆盖混用。
两个后续时刻均相对各窗口第一帧，间隔约 0.2 s、0.467 s；短窗口不足以证明长期稳定。

| 数据 | 参考窗口共同支持率 | 参考变化 RMS（mm） | 波浪共同支持率 | 波浪变化 RMS（mm） |
| --- | ---: | --- | ---: | --- |
| HomeTank_004 | 50.033% | 1.453 / 0.586 | 0% | 无共同支持，null |
| HomeTank_005 | 36.467% | 0.972 / 1.025 | 0.847%（293 点） | 4.687 / 1.342 |

005 波浪三帧分别通过左右一致性的比例为 14.609%、21.876%、31.337%，但共同位置仅 0.847%。
005 通过该门限的点，其左右重算高度差 RMS 为 1.014、1.422、0.990 mm；
1 px 视差的高度敏感度 P95 分别为 3.222、3.335、2.150 mm/px。
这些是经过一致性门限选出的点的诊断统计，不是全 ROI 物理精度。

因此，上一轮原图 ROI 97.55% 有数值不能解释为 97.55% 的水面趋势可靠。
新增结果没有抹除上一轮任何预测，也没有通过时域平滑或空间补全隐藏不一致。

## 独立验证证据检查

现有 [004 Case 1](../../experiments/real_video/HomeTank_004/phase4_physical_validation.yaml)
独立标尺变化为 0.1 mm，描述性不确定度约 2.236 mm；
[004 Case 2](../../experiments/real_video/HomeTank_004/phase4_case2_physical_validation.yaml)
变化为 0.5 mm，不确定度约 1.414 mm。
它们既不能有力区分正负趋势，也不能移用于 005 的其他时间、像素或标定。
本次没有把上述标尺读数输入匹配、参考面或高度计算。

仍未解决：标定质量、时间对应、匹配目标是否确为水面，而不是可见底部或反射物。
这些是不同条件；不能通过更密集网络输出或者更低平面残差互相替代。

## 接入决策与下一步范围

保持演示版冻结。当前候选不满足用户要求的全域正确趋势，不执行“有数值即接入”。
不继续调 Fast-FoundationStereo 的参数，也不向不一致高度上叠加补全模型。
若继续离线候选比较，优先核验同作者官方高精度 FoundationStereo 的部署条件并复用同一固定输入，
不重做框选、不改变标定、不挑成功时刻；它仍必须通过相同检查，而非凭模型名保证成功。
若独立物理信号不可辨识，结果保持未验证，不把该不足归因于某一种相机型号。

## 文件与复现

- [审计脚本](../../tools/audit_foundationstereo_height_stability.py)：`--help` 列出输入路径，输出路径必须不存在。
- [004 结果](../../experiments/real_video/HomeTank_004/foundationstereo_height_stability.json)
- [005 结果](../../experiments/real_video/HomeTank_005/foundationstereo_height_stability.json)
- [最小回归测试](../../tests/test_foundationstereo_height_stability.py)

所有读取的几何、参考面、预测和分析数组 SHA256 均写入结果，原始数据只读。
