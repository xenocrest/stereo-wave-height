"""Summarize existing evidence without rerunning calibration or reconstruction."""
from pathlib import Path
import hashlib
import json
import numpy as np
import yaml


def main():
    root=Path('D:/stereo-wave-height-runs/HomeTank_006')
    target=Path('experiments/real_video/HomeTank_006')
    sources={}
    def load(name):
        path=root/name;raw=path.read_bytes()
        sources[name]=dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest())
        return json.loads(raw)
    audio={k:load(f'audio_timing/{k}.json') for k in ['calibration','wave']}
    board=load('registered_board/observations.json')
    timing=load('board_timing/result.json')
    scene=load('static_geometry_no_ruler/result.json')
    disparity=load('disparity_validity/result.json')
    best=timing['best_diagnostic']
    result=dict(status='GEOMETRY_AND_TIMING_NOT_YET_VALIDATED',
        rig_unchanged=dict(value=True,source='USER_CONFIRMED_2026_09_04',
            scope='no movement, reclamping, angle, lens or zoom change'),
        board_registration={k:dict(complete_views=len(v),flips=sum(r['flipped'] for r in v)) for k,v in board['observations'].items()},
        audio=audio,calibration_timing=best,
        calibration_heldout_rms_px=float(np.sqrt(np.mean(np.square(best['heldout_epipolar_rms_px'])))),
        non_ruler_scene_geometry=scene,disparity_validity=disparity,
        sources=sources,calibration_approved=False,water_height_validated=False,
        no_reference_zeroing=True,no_gui_changes=True,no_wass_execution=True)
    (target/'geometry_timing_evidence.yaml').write_text(yaml.safe_dump(result,allow_unicode=True,sort_keys=False),encoding='utf-8')
    lines=['# HomeTank_006：固定机位、时间对应与视差有效性证据','',
        '本轮继续处理模型，不修改 GUI、不运行 WASS，不把诊断值当作水面高度。',
        '用户确认标定至波浪拍摄期间没有移动、重新夹持、角度、镜头或变焦变化；这是用户来源信息，不是对标定精度的独立证明。','',
        '## 角点身份和时间对应','',
        '- 检查 LEFT 7 个、RIGHT 6 个完整棋盘观测的黑白格极性，全部一致，未发现 180°角点编号翻转。只重排真实角点，不生成缺失角点。',
        '- 校准视频在 70、95、105 秒附近，用双向光流及实际图像角点细化追踪观测；使用真实 PTS，不按左右帧号直接匹配。',
        f'- 诊断最小值为 right-minus-left = {best["offset_s"]:.6f} s；三组姿态留一验证极线 RMS = {result["calibration_heldout_rms_px"]:.4f} 原始像素。相邻候选仍相近，只有三组姿态，不能据此宣布逐帧同步成功。',
        '- 音频校准/波浪候选约 -0.497/-0.225 s，窗口重复性较好，但相关系数未达到既定 0.6 门限，且音视频延迟未独立确认，状态均为 AUDIO_SYNC_NOT_ESTABLISHED。没有用音频修正高度。',
        '- 排除标尺区域后，静态背景匹配只有 6 对，未建立替代外参。含标尺特征的旧诊断候选不作为解算输入。','',
        '## 真实帧证明的视差有效性问题','',
        '同一未批准几何、相同名义时间、960×540 诊断分辨率，对比旧掩码与修正掩码。表中窗口是旧诊断窗口，不是已经确认的水面 ROI。','',
        '| 时间 s | 旧全图有效点 | 其中 d=255 点 | 旧窗口点 | 窗口 d=255 点 | 修正后全图点 |',
        '|---:|---:|---:|---:|---:|---:|']
    for r in disparity['frames']:
        lines.append(f'| {r["time_s"]:g} | {r["legacy_mask_count"]} | {r["legacy_endpoint_count"]} | {r["diagnostic_window_legacy_count"]} | {r["diagnostic_window_legacy_endpoint_count"]} | {r["corrected_mask_count"]} |')
    lines += ['',
        '旧窗口中约 61%–69% 的点恰好位于搜索上限。它们可能是被搜索区间截断的匹配，不能当作已验证深度。原来的集中深度不能直接证明存在水面平面。',
        '', '修复采用以下可追溯规则：','',
        '1. 左视差搜索区间为 [m, m+N−1]，右视差区间必须为 [−m−N+1, −m]。',
        '2. 查询 x_right = x_left − d_left，只有左右都为有效搜索内部值，且 |d_left+d_right| 不超过既定容差时，才保留。',
        '3. 校正映射的双线性采样范围和匹配窗口必须落在真实源图像内；排除填充背景，不改变像素几何。',
        '4. 重投影点须有限且位于校正相机前方。搜索端点返回缺失，不修改其数值、不自动扩大搜索、不填洞。',
        '',
        '修正后仍有十米甚至百米深度尾部。这证明左右一致性只是必要条件，不足以建立水面物理准确度；尚未用裁剪深度、重新置零或平滑掩盖这些错误。',
        '', '## 当前结论和下一步','',
        '已经排查角点编号问题，并修复备用解算器的观测有效性漏洞；标定/时间对应仍未达到可发布水面高度的条件。机位不变不等于几何已准确。',
        '下一步必须提高共同物理棋盘观测的几何约束并验证时间对应，再识别共同水面观测域。不能把背景/槽底点拟合出的平面命名为水面，也不能把未获支持区域补成“准确逐像素高度”。',
        '目标仍为有数学依据的逐水面像素高度；输出必须区分真实观测、经验证模型估计、无支持三类。当前不发布新的高度结果。','',
        '## 复现与结果','',
        '依次运行 tools/hometank006_audio_timing.py、tools/hometank006_register_board.py、tools/hometank006_board_timing.py、tools/hometank006_static_geometry.py、tools/hometank006_disparity_validity.py；设置 PYTHONPATH=src;tools。',
        '报告汇总：tools/hometank006_evidence_report.py。上述均为实验诊断工具，不改变冻结标定或 GUI 会话。',
        '小型结果及原始证据 SHA-256：[geometry_timing_evidence.yaml](geometry_timing_evidence.yaml)。图像、视频、点云仍在仓库外。','']
    (target/'geometry_timing_evidence.md').write_text('\n'.join(lines),encoding='utf-8')


if __name__=='__main__':main()
