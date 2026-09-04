"""Build a small evidence report from completed, isolated real-video runs."""
from pathlib import Path
import json
import hashlib
import numpy as np
import cv2
import yaml


def main():
    root=Path('D:/stereo-wave-height-runs/HomeTank_006');out=Path('experiments/real_video/HomeTank_006')
    sources={}
    def load(name):
        p=root/name;b=p.read_bytes();sources[name]=dict(path=str(p),sha256=hashlib.sha256(b).hexdigest());return json.loads(b)
    scale=load('rig_features_metric/result.json')
    runs={k:load(f'{k}/result.json') for k in ['surface_chain_padded','surface_chain_full_search','surface_chain_raft','surface_chain_raft_centered']}
    transfer=load('capture_transfer/result.json');guided=load('guided_corners/result.json')
    residuals=[]
    for t in [1,2,3,10]:
        p=root/'surface_chain_raft_centered'/f'frame_{t:02d}_correspondences.npz'
        with np.load(p) as d:
            f=d['forward'];b=d['backward'];h,w=f.shape[1:];y,x=np.indices((h,w),dtype=np.float32)
            br=np.stack([cv2.remap(v,x+f[0],y+f[1],cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=float('nan')) for v in b])
            cycle=np.linalg.norm(f+br,axis=0);ok=np.isfinite(cycle)&(cycle<1.5)
            dry=np.zeros((h,w),bool);dry[50:250,700:900]=True
            row=dict(time_s=t)
            for label,m in [('dry_wall_diagnostic',dry),('water_candidate',d['left_roi'])]:
                v=f[1][ok&m];row[label]=dict(cycle_consistent_count=int(len(v)),vertical_p5_p50_p95_px=np.percentile(v,[5,50,95]).tolist() if len(v) else None)
            residuals.append(row)
    checkpoint=Path('D:/stereo-wave-height-runs/tooling/raft_large_C_T_SKHT_V2-ff5fadd5.pth')
    payload=dict(status='WORKFLOW_EXECUTED_MEASUREMENT_NOT_VALIDATED',full_pixel_goal_complete=False,
        gui_changed=False,wass_runs=0,source_videos_modified=False,
        metric_baseline_m=scale['baseline_m'],metric_baseline_spread_m=scale['baseline_spread_m'],scale_observations=scale['scale_observations'],
        guide_corner_validation={side:[r['independent_sb_comparison'] for r in rr if 'independent_sb_comparison' in r] for side,rr in guided['records'].items()},
        background_capture_transfer=transfer,model_vertical_residuals=residuals,
        runs={k:{'status':v['status'],'frames':v['frames'],'limitations':v['limitations']} for k,v in runs.items()},
        model=dict(name='torchvision RAFT C_T_SKHT_V2 (NOT RAFT-Stereo)',torch='2.7.1+cpu',torchvision='0.22.1',
            source='https://docs.pytorch.org/vision/main/models/generated/torchvision.models.optical_flow.raft_large.html',
            checkpoint_source='https://download.pytorch.org/models/raft_large_C_T_SKHT_V2-ff5fadd5.pth',
            checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
            limitation='Official general correspondence model, not validated here as water metrology'),
        external_information_required='Are visible white patterns attached to water surface or tank bottom?',sources=sources)
    (out/'continued_workflow_attempt.yaml').write_text(yaml.safe_dump(payload,allow_unicode=True,sort_keys=False),encoding='utf-8')
    lines=['# HomeTank_006：继续全流程执行与实际阻塞','',
        '状态：WORKFLOW_EXECUTED_MEASUREMENT_NOT_VALIDATED。已经实际运行新路线；不是仅列下一步计划，也不是逐像素准确高度已完成。GUI、原始视频、WASS 源码均未修改。','',
        '## 本轮实际工作','',
        '1. 用原始板面特征引导真实角点搜索，结合原图亚像素细化和黑白交替对比检查。与完整 SB 观测比较仍存在数像素至十余像素偏差；没有把这些预测种子直接认作真角点或批准标定。',
        '2. 在多个板面姿态下用真实 SIFT 双向匹配和官方 essential-matrix/recoverPose 检查几何，保留不同时间候选与留一姿态检查；没有依据波高结果选择几何。',
        f'3. 新外参的米制尺度重新由已确认的 160 mm 棋盘跨度求出：B = {scale["baseline_m"]:.9f} m；三个姿态的跨度尺度差 {scale["baseline_spread_m"]*1000:.3f} mm。它是标定推导量，不是人工测量 baseline，测量不确定度仍未知。',
        '4. 修复可选 SGBM 搜索画布边界：左右同加 padding 不改变 d=uL−uR；输出裁回原索引，Q 与 K 不变。真实源图支持、左右一致性、搜索端点和正深度检查仍保留。默认关闭，不改变现有 GUI 配置。',
        '5. 按原始图像坐标重新映射候选水面 ROI，排除把非公共左侧区域当作公共区域的问题。扩大搜索至全图可达范围的隔离实验也已实际运行，不是简单声称扩大即可成功。',
        '6. RAFT-Stereo 官方 checkpoint 的 Dropbox/Google Drive 下载失败，未假称运行该模型。另建仓库外 CPU 环境，实际运行 PyTorch 官方 torchvision RAFT 二维对应模型；它不是 RAFT-Stereo，也不是深度预测模型。',
        '7. 已做原始视图对应及 480 px 水平裁切重心对齐两种输入。恢复原坐标时 dL=−flowLx+480、dR=−flowRx−480；没有把裁切坐标当原始像素。',
        '', '## 已运行的参考与高度链','',
        '实际流程为视频解码 → 时间候选配对 → 固定候选几何校正 → 双向匹配 → 有效性检查 → XYZ → 首个静水帧候选平面 → H。',
        '高度公式 H=(n·P+D)/||n||，单位 m。第 1 秒是唯一参考候选，第 2、3 秒只验证，不重新置零；第 10 秒为波浪测试。',
        'SGBM 半分辨率实验已经产生点与高度，但静水原始 RMS 约 35–86 mm，且出现 1–75 m 的错误深度；不能用于演示。单帧平面内点 RMS 约 2.4 mm 不足以证明正确，原始错误保留，不用筛后指标覆盖。',
        '', '## 同一匹配模型的干区/候选水区对照','',
        '下表先要求完整二维正反对应误差 <1.5 px，再统计纵向差；尚未强行把纵向差归零。像素单位为 960×540 诊断图。干区是图像识别的墙面窗口，不用标尺刻度或水位。','',
        '| 时刻 s | 干区双向一致点 | 干区纵差中位数 px | 水区双向一致点 | 水区纵差中位数 px |',
        '|---:|---:|---:|---:|---:|']
    for row in residuals:
        a=row['dry_wall_diagnostic'];b=row['water_candidate']
        def median(v):return f'{v[1]:.3f}' if v else 'UNAVAILABLE'
        lines.append(f'| {row["time_s"]} | {a["cycle_consistent_count"]} | {median(a["vertical_p5_p50_p95_px"])} | {b["cycle_consistent_count"]} | {median(b["vertical_p5_p50_p95_px"])} |')
    lines += ['',
        '干区大部分对应能通过检查；候选水区静水纵差约 6–7 px，波浪帧没有通过完整双向检查的水区点。这不能靠把门限放宽或把纵差设为零变成正确的三维高度。',
        '这些结果不是“模型证明水质不好”。目前仍有几何残差、时间不确定度和成像对象身份三个因素；尚未把任何单一因素断言为唯一原因。',
        '', '## 真正需要用户确认的物理事实','',
        '白色纹理是在水面上漂浮，还是在槽底、经水折射后可见？若两者都有，水面上实际放置了什么？',
        '如果是表面标记，针孔双目对应模型才直接指向水面；如果是透过水观察槽底，直接三角化不等于水面重建，需要明确的折射成像模型与约束。这个物理身份不能从调参数得出，更不能把槽底点补成水面高度。',
        '因此没有使用 MLS/全域填充制造全像素 PASS，没有将本轮候选几何或参考面写入最终 EXE。用户已确认机位、角度、镜头、变焦未变化，不重复询问。','',
        '## 来源与复现','',
        '[小型结果及证据哈希](continued_workflow_attempt.yaml)。各 tools/hometank006_*.py 是隔离实验入口；torch/模型仅在 D:/stereo-wave-height-runs/tooling/raft-stereo-env 中使用，不新增默认 GUI 依赖。',
        '[RAFT-Stereo 官方源码及权重入口](https://github.com/princeton-vl/RAFT-Stereo)；[本轮实际运行的 torchvision RAFT](https://docs.pytorch.org/vision/main/models/generated/torchvision.models.optical_flow.raft_large.html)。',
        '注意历史已保存的 learned-run 元数据 pad_search_canvas=true 是当时传入的 SGBM policy 字段，不代表模型做了 SGBM padding；代码现已将该字段按实际后端区分。水平裁切偏移则是真正执行的输入映射。','']
    (out/'continued_workflow_attempt.md').write_text('\n'.join(lines),encoding='utf-8')


if __name__=='__main__':main()
