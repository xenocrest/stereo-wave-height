# I02 修复：原始源帧身份和绝对PTS

原错误将showinfo的输入n=0时间加到request，未识别输出PNG对应帧。现改为`-copyts`保留原时间线，在select前后分别记录官方FFmpeg showinfo；以选中输出的整数PTS在select前日志中唯一匹配原decoder frame index。实际秒数用`PTS ticks × time_base`计算，不用打印四舍五入的pts_time，不加request。缺失/重复身份报错。没有fps过滤、重新编码视频或插帧。

请求定义为原始source PTS时间线上目标，选首个大于等于目标的原帧。TLCC仍用原Praat/FIR流程，残差定义为`right_source_pts-left_source_pts-TLCC_offset`。schema2.0同时保存requested、左右actual source PTS、整数ticks/time_base、0起始frame index、offset、residual、PNG hash、提帧命令和身份日志；同步→load_frame→GUI frame manifest→export metadata保持绑定。

| request L | L source frame / PTS s | R source frame / PTS s | delta_t ms |
|---|---|---|---:|
|21|1247 / 21.001544444444445|1256 / 20.933888888888887|+7.414460772|
|22|1307 / 22.00121111111111|1316 / 21.933922222222222|+7.781127438|
|23|1367 / 23.000766666666667|1376 / 22.933944444444446|+8.247794105|

新提取PNG与独立审计的原PNG逐像素相等、源帧index完全相同。审计曾按pts_time打印精度给出约+7.415/+7.781/+8.247 ms；本次整数ticks增加数值精度，不改变其“旧manifest错误、当前固定左帧最近右帧”的结论。TLCC=-0.07507001632731439 s再次复现。

证据`evidence/I02_validation.json`；完整提帧日志/音频/PNG在`D:/stereo-wave-height-runs/reconstruction-quality-p0-20261001/I02_sync`。新回归包括输入n=0与选中n=0区分、整数time_base精度、身份缺失/重复拒绝、真实FFmpeg非零start PTS + VFR + PNG逐像素身份。保留API extract_frame返回实际PTS，新增extract_source_frame返回完整身份。

未修改wass_lowcost或FFmpeg源码；未改变TLCC算法。此证据不证明实际曝光同步。正式旧结果不覆盖，后续I12还将使旧reference/cache失效。
