"""Offline read-only Golden Demo v1 presentation. No computation controls."""
from pathlib import Path
import streamlit as st
import plotly.graph_objects as go
from presentation_demo_data import (ASSETS, AssetError, require, manifest, frame_paths,
                                    point_cloud, height_grid, pixel_mapping, query)

st.set_page_config(page_title='Stereo Wave Height Demo', layout='wide')
st.title('Stereo Wave Height Demo')
st.caption('双目水面三维测量演示系统 · Golden Demo v1 · READ ONLY')
st.warning('DEMO ONLY · NOT PHYSICALLY VALIDATED · Physical accuracy not yet validated')
PAGES = ['首页','双目输入','流程展示','3D Point Cloud','Height Map','Image Overlay','Pixel Query','Conclusion']
page = st.sidebar.radio('汇报页面', PAGES)
st.sidebar.warning('DEMO ONLY\n\nNOT PHYSICALLY VALIDATED')
index = st.sidebar.selectbox('Frame index', list(range(5)))

cached_cloud = st.cache_data(point_cloud)
cached_grid = st.cache_data(height_grid)
cached_mapping = st.cache_data(pixel_mapping)


def render():
    record = manifest()
    root = record['outputs']['root']
    if not Path(root).is_dir():
        st.warning(f'Golden Demo asset missing: {root}')
    paths = frame_paths(root,index)
    metrics = record['frame_metrics'][index]
    if page=='首页':
        st.header('HomeTank_004 · 5-frame Golden Demo')
        a,b,c = st.columns(3)
        a.metric('WASS XYZ points', '681,678')
        b.metric('Direct/source grid support', '18.93%–20.55%')
        c.metric('Official stereo', '5 / 5 PASS')
        st.success('END_TO_END_DEMO_PASS')
        st.write('真实双目视频 → 官方 WASS 点云 → 公共平面 → 官方水面网格 → 图像叠加 → 像素高度查询')
        st.info('只读取冻结产物。source support 是网格占格率，不是整个水面图像的直接测量率。')
        st.image(str(require(ASSETS/'overlay.png')), caption='冻结中央水面展示窗口；INTERPOLATED / ESTIMATED')
    elif page=='双目输入':
        a,b = st.columns(2)
        a.image(str(require(paths['left'])),caption=f'LEFT · frame {index}')
        b.image(str(require(paths['right'])),caption=f'RIGHT · frame {index}')
        st.write('Source LEFT:',record['source_left_video'])
        st.write('Source RIGHT:',record['source_right_video'])
        st.write('Sync method:',record['sync']['method'])
        st.write('Right − left time lag (s):',record['sync']['lag_seconds'])
        st.caption('只读；不重新同步。音频 TLCC 未独立证明曝光级同步。')
    elif page=='流程展示':
        st.write('Stereo Video → Sync → Calibration → WASS Stereo → XYZ / Mesh → Mean Plane → Grid → NetCDF → Overlay → Pixel ↔ XYZ / Height')
        st.table([{'阶段':name,'状态':status} for name,status in [
            ('Stereo Video','FROZEN RAW INPUT'),('Sync','NEW TLCC; FROZEN'),
            ('Calibration / Extrinsics','DEMO FALLBACK · TRACEABLE HISTORICAL K/D/R/T'),
            ('Prepare / Match','5/5 PASS'),('Autocalibrate','EXECUTED; OUTPUT NOT USED'),
            ('WASS Stereo','5/5 PASS'),('XYZ / Mesh','PASS'),('Mean Plane','PASS'),
            ('Grid / NetCDF','PASS; INTERPOLATED / ESTIMATED'),('Overlay','PASS'),('Pixel ↔ XYZ / Height','PASS')]])
        st.caption('新 autocalibrate 输出保留但未采用；最终使用来源明确的历史外参。Strict Track A 仍然阻塞。')
    elif page=='3D Point Cloud':
        xyz,total = cached_cloud(str(paths['ply']))
        st.write(f'Frame {index}: {total:,} original points; {len(xyz):,} display points')
        st.info('DISPLAY-ONLY DOWNSAMPLING · Original reconstruction unchanged')
        fig = go.Figure(go.Scatter3d(x=xyz[:,0],y=xyz[:,1],z=xyz[:,2],mode='markers',
            marker=dict(size=1,color=xyz[:,2],colorscale='Viridis'),name='Frozen WASS source points'))
        fig.update_layout(height=620,scene=dict(aspectmode='data',xaxis_title='X (WASS baseline units)',
            yaxis_title='Y (WASS baseline units)',zaxis_title='Z (WASS baseline units)'))
        st.plotly_chart(fig)
        st.caption('PLY 原始 WASS 相机坐标；不是公共平面高度坐标。允许旋转、缩放和平移。')
    elif page=='Height Map':
        x,y,z = cached_grid(str(require(Path(root)/'gridding/gridded.nc')),index)
        fig = go.Figure(go.Heatmap(x=x[0,:],y=y[:,0],z=z,colorscale='RdBu',colorbar=dict(title='η (mm)')))
        fig.update_layout(height=580,xaxis_title='X (mm)',yaxis_title='Y (mm)',title=f'Frozen official η(x,y), frame {index}')
        st.plotly_chart(fig)
        st.table([{'区域':'Direct/source occupied grid','比例 %':metrics['source_supported_grid_percent']},
                  {'区域':'Interpolated / estimated inside hull','比例 %':metrics['interpolated_inside_hull_percent']},
                  {'区域':'Extrapolated outside hull','比例 %':metrics['extrapolated_outside_hull_percent']}])
        st.caption('直接读取 NetCDF，单位 mm；不做 UI 高度修正。100% finite 不代表 100% 观测。只有区域级统计，没有逐格支撑掩码。')
    elif page=='Image Overlay':
        st.image(str(require(paths['overlay'])),caption=f'Frozen official wassncplot overlay · frame {index} · INTERPOLATED / ESTIMATED')
        st.info('未重新生成 overlay。官方全幅范围含非水面；不能把墙、尺子上的网格当成水面测量。')
        if index==0:
            st.image(str(require(ASSETS/'overlay.png')),caption='冻结的中央水面展示遮罩（只改变可见范围，未改变数值）')
    elif page=='Pixel Query':
        st.image(str(require(paths['image'])),caption='Official rendered image coordinates: origin top-left; u right, v down; NOT original video pixel coordinates')
        mapping = cached_mapping(str(paths['mat']))
        st.write(f'Image size: {mapping.shape[1]} × {mapping.shape[0]}')
        a,b = st.columns(2)
        u = int(a.number_input('u',value=1000,step=1))
        v = int(b.number_input('v',value=1050,step=1))
        result = query(mapping,u,v)
        st.write(result)
        st.caption('X/Y/Z 单位 m；H 为官方渲染公共平面高度，单位 mm。有效值来自官方网格，不判作 DIRECT；逐像素 direct/extrapolated 支撑类别 UNKNOWN。')
    else:
        a,b = st.columns(2)
        a.subheader('当前已经证明')
        a.write('真实双目视频可进入 WASS；可生成真实 XYZ、公共水面网格、NetCDF、图像叠加及 Pixel ↔ XYZ/height 查询；五帧端到端工程样例可运行。')
        b.subheader('当前尚未证明')
        b.write('厘米级精度、真实波高绝对正确、全水面直接观测、严格无 fallback Vieira 复现、人眼趋势或跨帧稳定性验证。')
        st.info('下一步规划：GoPro HERO9 的可靠原始标定、曝光同步、基线尺度与独立物理验证。本 UI 不包含 GoPro 输入开发。')


try:
    render()
except AssetError as error:
    st.error(str(error))
except Exception as error:
    st.error(f'Golden Demo asset could not be loaded: {type(error).__name__}: {error}')
