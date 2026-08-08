# 相机几何模型

对相机 $i\in\{L,R\}$，三维点 $\mathbf{X}_w$ 的齐次像点满足

$$s_i\tilde{\mathbf{x}}_i=\mathbf{K}_i[\mathbf{R}_i\mid\mathbf{t}_i]\tilde{\mathbf{X}}_w.$$

$\mathbf{K}_i$ 为内参矩阵，$\mathbf{R}_i,\mathbf{t}_i$ 描述世界坐标到相机坐标的变换。实际成像还需使用径向和切向畸变模型；进入立体匹配前应完成去畸变与极线校正。

坐标系、长度单位、左右相机顺序和外参变换方向必须写入配置，防止尺度或高度符号歧义。
