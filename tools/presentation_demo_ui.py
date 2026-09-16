"""中文只读黄金样例；悬停仅在浏览器执行。"""
from pathlib import Path
import streamlit as st
import plotly.graph_objects as go
from presentation_demo_data import AssetError,require,manifest,frame_paths,point_cloud,height_grid,pixel_mapping,query
from presentation_demo_hover import hover_figure

st.set_page_config(page_title='双目水面三维测量演示系统',layout='wide')
st.markdown('<style>[data-testid="stToolbar"],[data-testid="stElementToolbar"],a[data-testid="stHeaderActionElements"]{display:none} footer{display:none}</style>',unsafe_allow_html=True)
st.title('双目水面三维测量演示系统')
st.caption('基于 Vieira 2025 / WASS 的端到端工程可行性演示 · 黄金样例第一版 · 只读')
st.warning('⚠ 演示版本：尚未完成物理精度验证')
st.caption('当前结果用于验证工程链路和可视化能力，不代表已经达到厘米级波高测量精度。')
PAGES = ['项目概览','双目输入','处理流程','三维点云','水面高度图','原图叠加','像素高度查询','结果与验证边界']
page = st.sidebar.radio('汇报页面',PAGES)
st.sidebar.warning('演示版本：尚未完成物理精度验证')
index = st.sidebar.selectbox('当前帧',list(range(5)),format_func=lambda i:f'第{i+1}帧')
cached_cloud = st.cache_data(point_cloud,max_entries=5)
cached_grid = st.cache_data(height_grid,max_entries=5)
cached_mapping = st.cache_data(pixel_mapping,max_entries=1)
CHART = dict(displayModeBar=False,scrollZoom=True)


def show_hover(paths):
    st.write('将鼠标移动到水面图像上，可直接查看对应像素的三维坐标和相对水面高度。无需点击。')
    st.caption('底图与 MAT 均为官方去畸变计算左图 cam0 的原尺寸渲染坐标（2400×1350），不是右图 cam1，也不是原视频坐标。网页缩放不改变像素坐标。')
    mapping = cached_mapping(str(paths['mat']))
    background = paths['overlay'] if page=='原图叠加' else paths['image']
    st.plotly_chart(hover_figure(background,mapping),config=CHART,key=f'hover-{index}-{page}',on_select='ignore')
    st.caption('XYZ 为平均水面坐标，单位 mm；Z 和相对平均水面高度一致。已有官方渲染值未修正；逐像素直接观测/插值/外推支撑来源未知。无数据处不补值。')
    return mapping


def render():
    record = manifest()
    root = Path(record['outputs']['root'])
    if not root.is_dir():
        st.warning(f'黄金演示文件缺失：{root}')
    paths = frame_paths(root,index)
    metrics = record['frame_metrics'][index]
    if page=='项目概览':
        st.header('HomeTank_004 · 五帧黄金演示样例')
        a,b,c = st.columns(3)
        a.metric('WASS 三维点总数','681,678')
        b.metric('直接双目观测覆盖率（网格占格）','18.93%–20.55%')
        c.metric('官方双目重建','5 / 5 已完成')
        st.success('端到端工程流程：已跑通（END_TO_END_DEMO_PASS）')
        st.info('只读取冻结产物。上述覆盖率是来源点的网格占格率，不是整个水面图像的直接测量率。')
        st.image(str(require(paths['overlay'])),caption='冻结官方叠加图：含插值、估计及非水面范围')
    elif page=='双目输入':
        a,b = st.columns(2)
        a.image(str(require(paths['left'])),caption=f'左相机 cam0 · 第{index+1}帧')
        b.image(str(require(paths['right'])),caption=f'右相机 cam1 · 第{index+1}帧')
        st.write('左相机原始视频：',record['source_left_video'])
        st.write('右相机原始视频：',record['source_right_video'])
        st.write('时间同步：音轨高通滤波后，使用 Praat 互相关峰值确定左右时差。')
        st.write('右时间减左时间（秒）：',record['sync']['lag_seconds'])
        st.caption('只读，不重新同步。音频同步未独立证明曝光级同步。')
    elif page=='处理流程':
        st.write('双目视频 ↓ 时间同步 ↓ 相机标定 ↓ WASS 双目重建 ↓ 三维点云 / 网格 ↓ 平均水面基准 ↓ 规则水面网格 ↓ NetCDF 数据 ↓ 原图叠加 ↓ 像素 → XYZ → 高度')
        stages = [('双目视频','已完成：原始输入已冻结'),('时间同步','已完成：同步帧已冻结'),('相机标定 / 外参','备用参数：来源可追溯的历史 K/D/R/T'),('图像准备 / 特征匹配','五帧已完成'),('自动外参估计','已执行，输出未采用'),('WASS 双目重建','五帧已完成'),('三维点云 / 网格','已完成'),('平均水面基准','已完成'),('规则网格 / NetCDF','已完成：包含插值及估计'),('原图叠加','已完成'),('像素 → XYZ → 高度','已完成')]
        st.table([{'阶段':name,'状态':state} for name,state in stages])
        st.info('演示备用内外参（来源可追溯的历史 K/D/R/T）。物理精度未验证；严格科学复现仍然阻塞。')
    elif page=='三维点云':
        st.header('三维水面点云')
        xyz,total = cached_cloud(str(paths['ply']))
        st.write(f'当前第{index+1}帧：原始点数 {total:,}；显示点数 {len(xyz):,}')
        st.info('仅对显示点进行抽样；原始 WASS 重建结果未改变。')
        fig = go.Figure(go.Scatter3d(x=xyz[:,0],y=xyz[:,1],z=xyz[:,2],mode='markers',marker=dict(size=1,color=xyz[:,2],colorscale='Viridis'),name='冻结 WASS 来源点',hovertemplate='X：%{x:.3f}<br>Y：%{y:.3f}<br>Z：%{z:.3f}<extra></extra>'))
        fig.update_layout(height=620,scene=dict(aspectmode='data',xaxis_title='X（基线单位）',yaxis_title='Y（基线单位）',zaxis_title='Z（基线单位）'))
        st.plotly_chart(fig,config=CHART)
        st.caption('PLY 是 WASS 相机坐标，不是平均水面高度坐标。可旋转、缩放、平移；点云包含未经水面分类的来源点。')
    elif page=='水面高度图':
        st.header('水面相对高度图')
        x,y,z = cached_grid(str(root/'gridding/gridded.nc'),index)
        fig = go.Figure(go.Heatmap(x=x[0,:],y=y[:,0],z=z,colorscale='RdBu',colorbar=dict(title='相对平均水面高度 / mm'),hovertemplate='X：%{x:.3f} mm<br>Y：%{y:.3f} mm<br>相对高度：%{z:+.3f} mm<extra></extra>'))
        fig.update_layout(height=580,xaxis_title='X（mm）',yaxis_title='Y（mm）')
        st.plotly_chart(fig,config=CHART)
        st.table([{'区域':'直接双目观测来源点占格','比例 %':metrics['source_supported_grid_percent']},{'区域':'凸包内插值 / 估计','比例 %':metrics['interpolated_inside_hull_percent']},{'区域':'凸包外外推 / 估计','比例 %':metrics['extrapolated_outside_hull_percent']}])
        st.caption('直接读取 NetCDF，单位 mm，不修正高度。规则网格 100% 有数值不代表 100% 由双目直接观测。只有区域级统计，没有逐格支撑掩码。')
    elif page=='原图叠加':
        st.header('三维水面结果叠加到原始图像')
        show_hover(paths)
        st.info('官方原始叠加图含非水面范围；墙、尺子上的网格不能当成水面测量。没有重新计算叠加。')
    elif page=='像素高度查询':
        st.header('像素高度查询')
        mapping = show_hover(paths)
        with st.expander('精确像素查询（备用）'):
            a,b = st.columns(2)
            u = int(a.number_input('像素 u',value=1000,step=1))
            v = int(b.number_input('像素 v',value=1050,step=1))
            result = query(mapping,u,v)
            st.write(f'像素坐标：({u}, {v})')
            if result['provenance']=='UNSUPPORTED':
                st.info('该像素暂无有效三维高度数据')
            else:
                st.write(f"X：{result['X_m']*1000:.3f} mm；Y：{result['Y_m']*1000:.3f} mm；Z：{result['Z_m']*1000:.3f} mm")
                st.write(f"相对平均水面高度：{result['H_mm']:+.3f} mm")
                st.caption('数据来源：未知（官方规则网格估计）')
    else:
        a,b = st.columns(2)
        a.subheader('当前已经证明')
        a.write('真实双目视频可进入 WASS；可生成真实 XYZ、公共水面网格、NetCDF、原图叠加及像素高度查询；五帧端到端工程样例可运行。')
        b.subheader('当前尚未证明')
        b.write('厘米级精度、真实波高绝对正确、全水面直接观测、严格无备用参数的 Vieira 复现、人眼趋势或跨帧稳定性验证。')
        st.info('下一步规划：GoPro HERO9 的可靠原始标定、曝光同步、基线尺度与独立物理验证。本界面不包含新相机输入开发。')


try:
    render()
except AssetError as error:
    st.error(str(error))
except Exception as error:
    st.error(f'黄金演示文件读取失败：{error}')
