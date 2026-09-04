"""Write small evidence report from actual isolated refractive experiments."""
import json
import hashlib
from pathlib import Path

ROOT=Path('D:/stereo-wave-height-runs/HomeTank_006')
OUT=Path('experiments/real_video/HomeTank_006')


def main():
    sources=[ROOT/'refraction_probe/result.json']+sorted(ROOT.glob('refractive_height_probe*/common_interface_result.json'))
    evidence={str(p):dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),result=json.loads(p.read_text())) for p in sources}
    summary=dict(status='STATIC_REFRACTIVE_CANDIDATES_DYNAMIC_HEIGHT_NOT_VALIDATED',
                 optical_texture='USER_CONFIRMED_TANK_BOTTOM_NO_SURFACE_MARKERS',
                 parallel_bottom='USER_SPECIFIED_MODEL_ASSUMPTION_NO_ADDITIONAL_VERIFICATION_REQUIRED',
                 gui_modified=False, wass_runs=0, calibration_modified=False,
                 full_pixel_goal_achieved=False, independent_physical_accuracy_pass=False,evidence=evidence)
    (OUT/'refractive_height_probe.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    lines=['# HomeTank_006：槽底纹理折射高度链实际试验','',
           '状态：**STATIC_REFRACTIVE_CANDIDATES_DYNAMIC_HEIGHT_NOT_VALIDATED**。本轮不是全像素高度成功交付。','',
           '用户确认：水面未放置标记，可见白色纹理为槽底痕迹。用户指定槽底与静水面平行为模型假设，不再单独验证。该假设已采用，但不等于相机几何、水深和动态结果已经被测量验证。','',
           '## 数学链与边界','',
           '图像像素 → 标定空气光线 → 静水界面交点 → Snell 折射光线 → 槽底标记位置；动态时追踪同一槽底标记，再用两台相机在同一候选水面点的 Snell 法向一致性反求高度。不是把槽底 XYZ 当水面，也不是从光流直接换算高度。','',
           '坐标为共同校正相机坐标，长度 m。n 为水指向空气的单位法向；静水面 n·X+c=0，平行槽底 n·X+c+d=0。相机中心 C、单位空气光线 v：','',
           '```text',
           'Q = C - (n·C+c)/(n·v) v',
           'eta = n_air/n_water; cos_i = -n·v',
           'w = eta v + (eta cos_i - sqrt(1-eta²(1-cos_i²))) n',
           'P_bottom = Q - d/(n·w) w',
           'dynamic candidate Q(h): n·Q(h)+c = h',
           'N_i(h) = normalize(n_air v_i - n_water w_i(h))',
           'h_candidate = argmin_h ||N_left(h)-N_right(h)||',
           '```','',
           '空气/水折射率采用 1/1.333（理想模型近似，不是本实验测量）。仅单次空气—水界面；不含槽壁透射或多路径。候选标定及同步不确定度仍保留；没有调 K/D/R/T。标准方法的关键前提是已知像素到三维背景点的对应；这里的背景由静水候选模型估计，所以动态输出只能是条件候选。','',
           '[Dynamic Refraction Stereo 原始方法与已知背景要求](https://www.research.autodesk.com/publications/dynamic-refraction-stereo/)。本实验是基于 Snell 公式的简化诊断，不冒称完整复现论文或通过其验收。','',
           '## 静水几何估计','',
           '固定每帧随机 seed=42，从有效双向二维对应抽 600 点，300 拟合、300 留出；不抹去纵向对应差。1/2/3 秒分别拟合水深 111.679/117.480/118.730 mm；相应留出光线闭合 RMS 为 0.000608/0.000664/0.000713 rad。这是模型内一致性，不是水深实测精度。','',
           '合并诊断估计 116.092 mm；将深度固定为其 0.5/1/2 倍重新拟合，留出闭合 RMS 为 0.002005/0.000676/0.003478 rad。具备一定区分能力，但比值/米混合参数化的 Jacobian 条件数约739，不能忽略几何误差敏感性。','',
           '实际高度参考只使用第1秒的拟合（111.679 mm）；第2、3秒没有参与该参考估计。合并诊断没有被用于高度参考。','',
           '## 公共水面域不是两张槽底 ROI 的像素交集','',
           '必须将 LEFT 空气光线与参考水面交点投影到 RIGHT，检查两边槽底对应是否存在。原 LEFT 候选图像区域 82,070 px，当前模型的公共界面域仅16,969 px（20.68%）；这不是完整水槽或4K全像素覆盖。仅在这个域内抽200个查询点；其余区域仍未支持，不能用样本200/200伪称整个ROI100%。','',
           '第1秒同图恒等输入为数值自检，200/200，RMS约0.000294 mm，不是准确度证明。早期直接在整片槽底图像ROI查询的失败统计另存于各目录 result.json，没有覆盖。','',
           '## 独立时刻实际结果','',
           '表中高度和RMS单位mm；RMS是候选高度对静水参考的RMS，波浪行不是对真值的RMSE。1°法向一致性仅为诊断门限，并不保证高度准确。','',
           '| 对应方法/时间候选 | 时刻 s | 可查询域 px | 支持/查询 | 高度中位数 mm | 高度 RMS mm |',
           '|---|---:|---:|---:|---:|---:|']
    for p in sources[1:]:
        r=json.loads(p.read_text())
        for f in r['frames']:
            if f['time_s']==1:continue
            if '_t' in p.parent.name and f['time_s'] in [2,3]:continue
            h=f.get('height_median_m');rms=f.get('height_rms_m')
            lines.append(f"| {p.parent.name} | {f['time_s']} | {f['available_query_domain_pixels']} | {f['conditional_candidates']}/{f['query_count']} | {h*1000:.3f} | {rms*1000:.3f} |" if h is not None else
                         f"| {p.parent.name} | {f['time_s']} | {f['available_query_domain_pixels']} | {f['conditional_candidates']}/{f['query_count']} | UNKNOWN | UNKNOWN |")
    lines += ['',
              'RAFT与[OpenCV官方DIS](https://docs.opencv.org/4.x/de/d4f/classcv_1_1DISOpticalFlow.html)都只负责槽底标记的图像对应，不生成米制高度。原时差约−0.0775s为几何/音频组合候选；−0.225s仅为已有音频候选的隔离复查，没有按高度结果批准同步。所有失败保留。','',
              '## 结果判断与下一步','',
              '- 静水公共域的跨帧候选有进展：RAFT第2/3秒RMS约0.240/0.226mm，但法向残差近最小值范围对应约6.7mm高度跨度；小静水RMS不能代替绝对精度或可辨识度。',
              '- 第6秒DIS可以形成条件高度候选，中位数约1.29mm；尚未独立确认此时真实波幅，不能据此宣称波浪验证成功。',
              '- 第8秒0/200；第10秒原时间候选0/200（RAFT无左侧对应），音频时间候选仅12/200且高度约−95mm，接近搜索下边缘。此结果不接受、不用于演示，不能只凭法向一致就承认正确。',
              '- 额外实际运行DIS短步跟踪：6秒之后每0.1秒跟踪槽底标记，逐步双向检查，不做高度时序插值。LEFT在6/8/10秒剩73793/476/0条轨迹，RIGHT剩38982/8730/0；没有用丢失轨迹填充高度。详细记录保存在仓库外 refractive_height_probe_dis_chain/tracking.json。',
              '- 当前瓶颈为动态槽底对应、时间/几何不确定度及局部反演歧义。不是“槽底平行假设未验证”，也不是把问题推给水质。下一阶段必须解决这些观测/反演约束，不能以MLS填充或置零代替。',
              '- GUI保持冻结；没有WASS运行，没有改标定、参考数值去迎合波高，没有标尺输入，没有全域补值。',
              '', '## 复现与文件','',
              '```powershell', "$env:PYTHONPATH='src;tools'",
              'D:/python/python.exe tools/hometank006_refraction_probe.py',
              'D:/python/python.exe tools/hometank006_refractive_height_probe.py --correspondence dis',
              'D:/python/python.exe tools/hometank006_refractive_height_probe.py --correspondence dis --target-time 8 --right-offset -0.225',
              '```','',
              'RAFT首次运行使用仓库外已安装torch环境；诊断图/NPZ在 D:/stereo-wave-height-runs/HomeTank_006/，不提交大型数据。数值、输入证据哈希及全部运行摘要见[结果JSON](refractive_height_probe.json)。',
              '新增5项数理/边界测试；全套442 passed、1 skipped、4 subtests passed，另有既有NetCDF依赖二进制警告（本链不调用）。','']
    (OUT/'refractive_height_probe.md').write_text('\n'.join(lines),encoding='utf-8')


if __name__=='__main__':main()
