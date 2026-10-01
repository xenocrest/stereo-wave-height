"""Publish the explicitly reviewed findings; no scientific processing."""
import json
from pathlib import Path
from collections import Counter

AUDIT = Path(__file__).resolve().parents[1]
FIELDS = ['id','priority','issue','categories','evidence','affected_stage','affected_file_function_config','scientific_consequence','proposed_fix_and_test','third_party_modification_required','can_test_now','risk']
ROWS = [
('I01','P0','带畸变原图与去畸变 pixel map 直接缩放叠加/hover', ['SOFTWARE_BUG','PIXEL_MAPPING','VISUALIZATION'],
 'evidence/HomeTank21.json、HomeTank21_projection_check.png、HomeTank21_GUI_overlay.png：1000点样本，原图错位median 4.720 px、max 15.131 px；同一问题也出现在Vieira。',
 'pixel map → raw overlay / raw hover', 'app/main.py: MainWindow._receive_reconstruction、_build_overlay、_hover；app/core.py: hover',
 '查询的H不对应用户看到的原图位置；细尺度趋势比较错位。',
 '统一显示为去畸变相机图，或显式双向畸变映射；用当前两套数据的真实XYZ、四角/边缘/中心和hover逐点验证，不仅验证map自投影。',
 '否；修项目显示/坐标适配。','是，现有两套数据。','中；涉及图像约定、ROI、导出位置的一致性。'),
('I02','P0','showinfo首帧被当成seek输出帧，actual PTS与残差记录错误', ['SOFTWARE_BUG','SYNC_IMPLEMENTATION'],
 'production_pts_regex_reproduction.json与sync_absolute_pts_and_frame_identity.json：原命令PNG逐像素一致；n=0是输入首帧，21 s左实际21.001544而非21.0089。',
 'raw video → extracted frame → timestamp / pair residual', 'tools/vieira_tlcc_sync.py: extract_frame；下游frame manifest/GUI时间',
 '瞬时量被绑定到错误时间，残差符号/数值失真；不能用当前manifest证明物理同步。',
 '按输出帧身份保存绝对源PTS和源帧索引；加入非零start PTS、VFR、两台视频帧间隔不同的真实回归；重新生成时间manifest，不插值伪同步。',
 '否；修项目提帧包装。','是。','中；时间缓存和历史结果标记需要迁移。'),
('I04','P0','官方默认全图输入使保留点云主要重建池壁/标尺，而不是水面', ['OFFICIAL_CONFIG_USAGE','INPUT_DATA'],
 'actual_XYZ_projection_and_support.json、HomeTank21_preplane_vs_filtered.png、HomeTank21_stages.png：21 s至少99912/147349点落在明确非水面两多边形；前景水域仅11点。',
 'dense stereo / triangulation / z-gap → plane → setup/grid', 'CURRENT_HOMETANK_CONFIG.txt: LEFT/RIGHT_MASK_IMAGE=none、TRIANG_BBOX全图、PLANE_RANSAC_THRESHOLD=1 B、PLANE_MAX_DISTANCE=1.5 B；GUI USER_RECTANGLE只限显示。',
 '大部分最终估计的科学对象错误；已进入plane/grid，不能靠最终裁图消除。',
 '先建立可检验的水面观测/有效域标准，再用官方mask/bbox限制三角化、检查实际覆盖和plane输入；只保留支持域。此轮单次保守mask失败，不把失败调成成功。',
 '否；已有官方mask/bbox足够做受控诊断。','是，可诊断对象/覆盖；可靠水面重建能否获得尚未证明。','高；透明水面下底部/折射纹理不能当表面，稀疏mask会使官方plane失败。'),
('I12','P0','冻结平均plane未归一化导致Rpl非正交，官方前向变换/回投影不互逆', ['SOFTWARE_BUG','COORDINATE_TRANSFORM'],
 'geometry_units_and_sensitivity.json、actual_XYZ_projection_and_support.json：||Rpl^T Rpl-I||F=0.00564395、det=0.99600913；21 s真实WASS点对齐后回投影median 0.736812 px、max 1.848400 px。',
 'plane → official setup transform → XYZ projection', 'wassgridsurface/wass_utils.py: compute_sea_plane_RT / align_on_sea_plane_RT；wassgridsurface/setup.py: mean plane、Cam0toGrid/P0plane（本地安装源码）',
 '冻结坐标含约0.2%非刚体缩放，Rpl.T不能充当精确逆；pixel内部自洽不能排除该错误。按用户规则，真实投影不一致列P0；量级次于I04。',
 '明确单位法向量输入契约，在获准FIX后验证官方接口/adapter归一化方案，证明R正交、forward/inverse和P0/P1对齐，再重建并重冻结所有identity/reference；不得只旋转显示。',
 '不必；可在项目adapter按官方契约处理输入，需验证。当前缺陷归属官方后处理输入契约/集成，不是新增自研stereo。','是，当前setup和真实点均可做数值验证。','高；坐标变更会使旧reference/缓存失效。'),
('I03','P1','左标定与测量提帧采用相反的180°旋转约定', ['SOFTWARE_BUG','CALIBRATION_IMPLEMENTATION'],
 'calibration_selection_and_orientation.json、left_calibration_orientation.png：左元数据180°，auto=rot180(native)逐像素相同；右0°。',
 'raw calibration video → fresh K/D → fresh extrinsics', 'tools/vieira_intrinsics_from_raw.py: run，CAP_PROP_ORIENTATION_AUTO=0；tools/vieira_tlcc_sync.py: FFmpeg默认autorotate',
 'fresh左K/D不属于测量左图约定；当前完整历史fallback绕开此路径，不能据此说所有当前点云由该bug直接造成。',
 '统一标定、预览和科学提帧的canonical orientation，记录约定；原帧不删减，重标定/重autocal并核对真实投影。',
 '否。','是，现有raw视频。','高；fresh几何变化要求更新身份和reference，不能与旧R/T混用。'),
('I05','P1','DCT全域有限网格掩盖空洞和凸包外外推，setup域并非水域', ['GRIDDING'],
 'HomeTank21.json、actual_XYZ_projection_and_support.json、HomeTank_setup_area_grid.png：256²格子，点占格27.51%；21/22/23凸包外有限格分别24.38%/31.28%/50.62%。',
 'cloud → setup extent → grid → pixel XYZ', 'pipeline/adapters/surface.py（域适配）；官方wassgridsurface gridding/DCT、gridconfig与冻结config.mat',
 '大片彩色像素是无直接数据支撑的模型估计；规则网格会将非水面场景和外推画成完整水面。',
 '官方setup area_grid人工检查并冻结真正测量域；保存占格、距离、凸包外标签，NO_DATA屏蔽不支持区；明确DCT与论文线性插值区别并受控比较，不能仅增加N。',
 '否；通过官方配置、项目支持域/provenance门控。','是。','中高；限制有效域后可用面积会明显缩小。'),
('I06','P1','同输入的plane与DCT随机性导致瞬时H明显不稳定', ['GRIDDING'],
 'repeat_and_mask_experiments.json：固定pixel(1200,900) H=-8.897/-3.879/+1.959 mm；isolated_grid_repeats.json：相同mesh_cam.xyzC与setup的Z(224,224)跨度5.744 mm。',
 'stereo plane filtering + DCT grid', 'CURRENT_HOMETANK_CONFIG.txt: RANDOM_SEED=-1；官方DCT随机碰撞重排、torch初始化/Rprop；audit脚本未修改算法。',
 '同一瞬间同一空间查询不能稳定复现；10.857 mm总跨度不能作为时间变化。',
 '在FIX中记录/冻结已有随机源，分别检查plane和grid；用相同哈希输入至少3次与支持域门控验证，保持逐次结果，不平均掩盖不稳定。',
 '不一定；已有RANDOM_SEED及外部可控随机源先验证，若官方接口仍不可控应上游反馈。','是。','中；确定性不等于科学正确，随机源可能跨进程/库。'),
('I07','P1','20 s内部reference来自污染估计面，不能当真实静水物理datum', ['REFERENCE'],
 'HomeTank21.json、reference_plane.json原件路径见data-flow：n=(0.0338031,-0.0136107,0.9993358)，d=3.7195 mm；H-Z范围约[-5.358,+2.991] mm。',
 'estimated XYZ → fixed n/d → H', 'app/core.py: reference_from_run、load_result；app/coordinates.py identity；INTERNAL_STATIC_REFERENCE',
 '内部倾斜/offset改变H视觉趋势；身份一致仅保证同坐标，不能证明该平面是静水面。',
 '保留固定n/d定义和清楚的内部基准标签，使用独立静水/已知平面验证未来datum；展示Z和H差异；禁止逐帧重拟合或为水平外观旋转。',
 '否。','内部差异/身份可现在测试；物理datum须新独立数据。','高；换reference会改变所有H定义。'),
('I08','P1','GUI原PLY的B/camera-Z显示与metric-grid/H混为同一表面', ['VISUALIZATION'],
 'HomeTank21_GUI_cloud.png、HomeTank21_TRUE_SCALE_VIEW.png、Vieira0_GUI_cloud.png；实际PointCloudView输出与诊断1:1:1比较。',
 'PLY → 3D viewer', 'app/main.py: PointCloudView.show_ply，原XYZ散点、颜色Z、默认axis aspect',
 '相机深度颜色不是H，默认轴比例和视角可能夸大/压缩水面形态；与overlay不能直接视觉互证。',
 '统一显示固定坐标metric XYZ，明确Z/H色义，物理轴1:1:1；若10×夸张必须明确标注；保留raw-WASS视图作为有单位/坐标标签的独立诊断。',
 '否。','是。','中；涉及输出语义和旧用户对图的解释。'),
('I09','P1','READY/摘要成功语言只检查流程，没有科学质量门控', ['SOFTWARE_INTEGRATION'],
 'app/main.py _update_status由result非空给READY；当前147349点/960496像素同时存在明确非水面主导证据。',
 'results → workflow state / ready summary', 'app/main.py: _update_status、_receive_reconstruction中的_ready_summary',
 '用户可能把过程闭环理解成瞬时水面科学可用。',
 'INFO说明artifact可读；WARN明确RMS/fallback/actual残差/内部reference/外推/水域覆盖；BLOCK用于identity失败、无有效支持、官方阶段失败或不满足已验证条件；阈值需实验验证后冻结。',
 '否。','是，现有真实失败/污染/identity负例。','中；不能凭任意阈值虚构质量保证。'),
('I11','P1','标定误差、工作区域覆盖与历史bundle有效性不足', ['INPUT_DATA'],
 'calibration_selection_and_orientation.json：50views各、无重复；fresh RMS4.1972/5.5225；右单view最大21.3189 px；角点凸包47.65%/50.15%；historical yaml明确CALIBRATION_QUALITY_FAIL。',
 'calibration capture → K/D validity → stereo geometry', 'HomeTank_004两标定MP4；历史calibration_result.yaml；历史bundle；tools/vieira_intrinsics_from_raw.py: select_diverse/run',
 '已声明的baseline/焦距不能证明近距离水域度量精度；工作图边缘映射受未充分约束的K/D影响。',
 '先解决I03再用所有原已选帧重算与逐view覆盖报告，禁止为降RMS自动删帧；检查棋盘物理尺寸/拍摄模式/焦距稳定性，新拍覆盖实际工作距离和图边缘的独立验证图。',
 '否。','现有帧可诊断；充分覆盖/物理尺寸/锁焦需补拍和实测。','高；低RMS不替代工作区域外推验证。'),
('I10','P2','GUI展示历史active K/D但RMS来自fresh calibration报告', ['SOFTWARE_INTEGRATION'],
 'calibration_bundle_provenance.json；app/fixed_run.py复制fallback矩阵时仍复制fresh report.json；core.calibration_matrices读取该报告RMS。',
 'active calibration provenance → GUI label', 'app/fixed_run.py: run；app/core.py: calibration_matrices；app/main.py: INTRINSICS_COMPUTED',
 '用户会将fresh质量数字错误归因到当前WASS使用的历史内参；不等于实际workspace新旧K/R混用。',
 '分别展示active bundle来源/hash/质量报告与fresh attempt来源/结果；逐项核对GUI与实际workspace K/D/R/T。',
 '否。','是。','低中；只修元数据绑定，不改科学矩阵。'),
('I13','P2','逐帧2/98%自动色阶、无统一H colorbar', ['VISUALIZATION'],
 'HomeTank_fixed_color_scale_comparison.png与三帧GUI_overlay.png；_build_overlay按本帧percentile决定颜色。',
 'H → color overlay', 'app/main.py: MainWindow._build_overlay',
 '同一H跨帧呈不同颜色，颜色趋势不能当瞬时高度趋势。',
 '固定有单位的共享色阶/色条，明确clipping与NO_DATA；用三真实帧同一H的颜色一致性验证。',
 '否。','是。','低；色阶范围必须透明。'),
('I14','P2','固定当前左帧的源时间离散限制，曝光/滚动快门未测', ['HARDWARE_LIMIT'],
 'sync_absolute_pts_and_frame_identity.json：左右源间隔约16.656/16.667 ms，三个右帧均是固定实际左帧的最近右帧，残差+7.415/+7.781/+8.247 ms。',
 'capture/exposure → instantaneous stereo', 'HomeTank_004两wave MP4；TLCC是audio time lag',
 'PTS最近不等于同时曝光；滚动读出与audio-video latency可产生无法由manifest证实/排除的瞬时偏差。',
 '当前报告真实PTS与残差并保留选择；未来锁定拍摄模式/同步事件、测量曝光和audio-video延迟，使用独立瞬时事件，不做合成时间插值。',
 '否。','PTS可现在测试；曝光/读出实测需新采集，不一定必须先买GoPro。','中；不能推断未知硬件误差幅度。'),
('I15','P3','没有独立瞬时高度真值，透明水体纹理对应的物理界面未确定', ['UNRESOLVED'],
 '现有数据没有独立高度传感器；水域mask B只留631个preplane点并官方plane失败；图像可见池底/反射/折射。',
 'observability / external metrology validation', 'HomeTank水域影像；docs/INSTANTANEOUS_GROUND_TRUTH_VALIDATION_SOP_ZH.md；mask_B诊断',
 '不能宣称墙/水点的绝对物理误差、真实水面形态或新设备必然解决；肉眼亮度/折射纹理不是三维真值。',
 '按既有SOP采集同步且空间注册的独立瞬时高度、已知平面/结构；逐时刻逐位置检验P与H，不用Hs/平均量替代。',
 '否。','证据缺口现在可确认；物理精度只能由新真值采集检验。','中高；真值同步和注册本身也要验证。'),
]

def main():
    issues=[dict(zip(FIELDS,row)) for row in ROWS]
    counts=Counter(c for row in issues for c in row['categories'])
    data={'status':'INDEPENDENT_RECONSTRUCTION_QUALITY_AUDIT_COMPLETE','count_semantics':'each issue counted once per assigned category; cross-category counts are not additive','unique_issues':len(issues),'category_counts':dict(sorted(counts.items())),'issues':issues}
    (AUDIT/'evidence/issue_registry.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines=['# 问题登记表','', '共15项独立问题。跨类别计数不相加；I12为官方后处理输入契约/集成缺陷，其余三个SOFTWARE_BUG位于项目包装/GUI。本轮均未修复。','']
    labels={'categories':'Category','evidence':'Evidence','affected_stage':'Affected stage','affected_file_function_config':'Affected file/function/config','scientific_consequence':'Scientific consequence','proposed_fix_and_test':'Proposed fix / How to test','third_party_modification_required':'Third-party modification required?','can_test_now':'Can test now?','risk':'Risk'}
    for i in issues:
        lines.extend([f"## {i['id']} · {i['priority']} · {i['issue']}",''])
        for field,label in labels.items():
            value=', '.join(i[field]) if isinstance(i[field],list) else i[field]
            lines.extend([f'**{label}**：{value}',''])
    (AUDIT/'ISSUE_REGISTER_ZH.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({'unique_issues':len(issues),'counts':dict(counts)},ensure_ascii=False))

if __name__=='__main__':main()
