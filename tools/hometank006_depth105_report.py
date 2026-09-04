"""Freeze compact real-run evidence for the user-provided 105 mm water depth."""
from pathlib import Path
import json
import hashlib
import numpy as np

ROOT=Path('D:/stereo-wave-height-runs/HomeTank_006')
OUT=Path('experiments/real_video/HomeTank_006')


def main():
    model=ROOT/'refraction_probe_depth_105mm/result.json'
    sha=hashlib.sha256(model.read_bytes()).hexdigest()
    ray=ROOT/f'refractive_height_probe_dis_t10_offset-0.225_reference_{sha[:12]}/physical_entry_result.json'
    photo=ROOT/'photometric_refraction_105mm/masked_continuous_sampler_result.json'
    records={key:dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),result=json.loads(p.read_text()))
             for key,p in [('reference_model',model),('ray_normal_inverse',ray),('photometric_inverse',photo)]}
    result=dict(status='DEPTH_CONSTRAINED_RECONSTRUCTION_NOT_PHYSICALLY_VALIDATED',
        water_depth=dict(value=.105,unit='m',source='USER_REPORTED_APPROXIMATE',uncertainty=None),
        plane_parallel='USER_SPECIFIED_ASSUMPTION',full_pixel_height_goal_achieved=False,
        calibration_modified=False,gui_modified=False,wass_runs=0,records=records)
    (OUT/'depth105_reconstruction.json').write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    lines=['# HomeTank_006：105 mm 静水深度约束后的实际重算','',
        '状态：DEPTH_CONSTRAINED_RECONSTRUCTION_NOT_PHYSICALLY_VALIDATED。全水面逐像素准确高度目标尚未达到。','',
        '## 用户物理输入','',
        '静水深度采用0.105m，来源USER_REPORTED_APPROXIMATE；误差范围UNKNOWN，不把“约105mm”写成无误差测量。槽底与静水面平行按用户指定假设使用，不再核验。K/D/R/T、基线和历史结果未改。高度不是先算后乘比例，而是用105mm重新建立折射光线路径和槽底几何。','',
        '## 1. 固定水深重建静水模型','',
        '相机空气光线与候选水面相交，经Snell定律折射到固定平行槽底。固定d=0.105m，只拟合平面方向与位置；第一秒作为高度参考，第二、三秒单独检验，不参与参考。','',
        '第一秒平面 n·X+c=0，n=(-0.454151,-0.756366,-0.470805)，c=0.221510350m。坐标系为共同校正相机坐标，n朝空气。300点拟合/300点留出，留出光线闭合RMS=0.000618266rad；这不是高度实测误差。','',
        '## 2. 原折射法向反演的复算','',
        '模型公共界面域18300px，原LEFT候选区域82070px；并非整个4K水面已经有效。seed42固定抽200查询点。','',
        '| 时刻 s | 候选/查询 | 高度中位数 mm | 高度RMS mm |',
        '|---:|---:|---:|---:|']
    for f in records['ray_normal_inverse']['result']['frames']:
        h=f.get('height_median_m');rms=f.get('height_rms_m')
        lines.append(f"| {f['time_s']} | {f['conditional_candidates']}/{f['query_count']} | {1000*h:.6f} | {1000*rms:.6f} |" if h is not None else
                     f"| {f['time_s']} | {f['conditional_candidates']}/{f['query_count']} | UNKNOWN | UNKNOWN |")
    lines += ['', '第一秒恒等输入不是精度验证。第二、三秒是内部静水一致性；第10秒仍无通过物理入射及法向一致性检查的候选。105mm输入没有解决全部动态对应问题。','',
        '## 3. 新隔离试验：直接光度折射反演','',
        '为绕开长时间特征轨迹丢失，用局部水面平面（高度h及两个斜率）直接预测同一时刻两张图像。仅8个17×17小区域，不是全图补值。每片棋盘式分为训练/留出像素，seed42固定位置。','',
        '流程：当前像素空气光线 → 与局部动态平面相交E → Snell折射到固定槽底B → 通过静水折射模型把B反投影至第一秒参考图 → 预测像素亮度 → 与当前左右图像同时比较。仅每片一个加性亮度偏移作为图像噪声参数，不修改高度或视频。','',
        '静水逆投影不是把槽底按针孔投影。相机到静水面法向距离a、底点平面方向距离ρ时，求空气入射角θ：','',
        '```text',
        'ρ = a tan(θ) + d [sin(θ)/n_water] / sqrt(1-[sin(θ)/n_water]²)',
        'h,N -> dynamic ray intersection E -> refracted bottom B',
        'min sum_train ||I_current_i(project_i(E))-I_reference_i(refractive_project_i(B))-bias_i||²',
        '```','',
        '空气/水折射率1/1.333为理想近似。源/目标采样均受水区掩码约束，禁止把槽壁或标尺纹理纳入拟合。用连续双线性灰度采样消除OpenCV remap 1/32px查表量化对数值求导的影响；这里插值的是亮度，不是高度。','',
        '高度初值0、±0.2d；高度搜索界限±0.9d、两个斜率各±1为隔离模型范围，不是验收范围。使用soft-L1鲁棒损失。不同初值的解和各自残差全部保留，不依据“高度看起来好”选择结果。','',
        '| 时刻 s | 8片候选高度RMS mm | 最小高度 mm | 最大高度 mm | 留出亮度RMS中位数（0–1） |',
        '|---:|---:|---:|---:|---:|']
    for f in records['photometric_inverse']['result']['frames']:
        hs=np.array([p['height_m'] for p in f['patches']])*1000
        costs=[p['heldout_intensity_rms'] for p in f['patches']]
        lines.append(f"| {f['time_s']} | {np.sqrt(np.mean(hs**2)):.6f} | {hs.min():.6f} | {hs.max():.6f} | {np.median(costs):.6f} |")
    lines += ['',
        '上述波浪行只是拟合候选，不是测量结果；静水RMS也不是独立物理准确度。候选已有非零值，但波浪留出亮度残差明显高于静水，且多初值存在不同局部解。不能据“厘米量级”就认定正确。局部平面还没有形成经过可积性检验的全水面连续高度场。','',
        '## 当前结论与边界','',
        '105mm物理约束已落盘、已实际用于重算，无待确认水深阻塞。保留两条真实失败/候选记录。动态槽底对应可靠性、同步不确定度、光度模型误差及反演多解性仍待解决；不把剩余问题归为“水深没提供”或“平行假设没验证”。','',
        'GUI、WASS和标定文件均保持冻结；没有用标尺验证值参与重建，没有将不可靠候选送入演示，没有填造全像素高度。','',
        '## 复现与检查','',
        '```powershell',"$env:PYTHONPATH='src;tools'",
        'D:/python/python.exe tools/hometank006_refraction_probe.py --water-depth-mm 105 --source-note USER_REPORTED_APPROXIMATE_STATIC_WATER_DEPTH_2026_09_04',
        'D:/python/python.exe tools/hometank006_refractive_height_probe.py --correspondence dis --right-offset -0.225 --reference-model D:/stereo-wave-height-runs/HomeTank_006/refraction_probe_depth_105mm/result.json',
        'D:/python/python.exe tools/hometank006_photometric_refraction.py','```','',
        '[结果与来源哈希](depth105_reconstruction.json)。大数据、诊断缓存与完整日志仅在 D:/stereo-wave-height-runs/HomeTank_006/。','',
        '新增静水折射逆投影像素往返、倾斜动态平面/固定底面、亚像素亮度连续性三项测试。物理基础沿用[折射链报告](refractive_height_probe.md)中Snell定律及原始文献；本局部光度试验不声称完整复现某篇算法或已经验证精度。','']
    (OUT/'depth105_reconstruction.md').write_text('\n'.join(lines),encoding='utf-8')


if __name__=='__main__':main()
