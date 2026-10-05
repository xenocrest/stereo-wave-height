# I12 补充验收：独立 validation/reference 路径

收尾检查发现 GUI 已拒绝旧 reference，但独立 `reference_from_config` 仍可读取实际旧官方网格并按旧系数计算 H。该路径也必须满足 I12 的“所有 reference 失效”要求。现实际 run 只要包含官方 config.mat，就在拟合/计算 H 前核对同一 setup 证书、坐标身份和单位；静态参考采用相同 bind 方法生成新 ID；provided physical plane 必须显式绑定当前 coordinate_frame_id 与 coordinate_contract。不能盲目沿用旧系数。没有官方 setup 的纯合成数学单元夹具仍是通用 plane 定义。

GUI core 委托给此统一 reference factory，ID 算法与先前 I12 完全相同，未再次拟合最终已冻结参考、未改任何科学点或 H 系数。新增回归证明：实际旧 run 被拒绝、新静态 reference 与 GUI factory 完全相同、新 physical plane 缺绑定时拒绝、显式注册后匹配。测试 7 项 I12 回归通过，见 `evidence/I12_standalone_reference_tests.txt`。实际 fresh 20s 已保存参考另做相等性检查；没有重新启动官方随机阶段。

本追加 commit 仅 I12 reference 契约收口，未实现 I07 参考展示改进或 P1。
