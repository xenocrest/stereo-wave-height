"""Native hover indexing frozen rendered pixels. No interpolation."""
import base64
import numpy as np
import plotly.graph_objects as go
from presentation_demo_data import require


def hover_lookup(mapping):
    valid = np.isfinite(mapping).all(2)&~np.all(np.isclose(mapping,0),2)&~np.all(np.isclose(mapping,1),2)
    xy = (mapping[:,:,:2]*1000).astype(np.float32)
    z = (mapping[:,:,2]*1000).astype(np.float32)
    xy[~valid] = np.nan
    z[~valid] = np.nan
    return xy,z,valid


def hover_figure(image,mapping):
    from PIL import Image
    with Image.open(require(image)) as original:
        width,height = original.size
    if mapping.shape!=(height,width,3):
        raise ValueError('底图与对应帧 MAT 尺寸不一致；停止查询以避免错位')
    xy,z,valid = hover_lookup(mapping)
    source = 'data:image/png;base64,'+base64.b64encode(require(image).read_bytes()).decode('ascii')
    fig = go.Figure(go.Image(source=source,x0=0,y0=0,dx=1,dy=1,hoverinfo='skip'))
    invisible = [[0,'rgba(0,0,0,0)'],[1,'rgba(0,0,0,0)']]
    fig.add_trace(go.Heatmap(z=z,customdata=xy,x0=0,dx=1,y0=0,dy=1,colorscale=invisible,showscale=False,hoverongaps=False,zsmooth=False,
        hovertemplate='像素坐标：(%{x:.0f}, %{y:.0f})<br>X：%{customdata[0]:.3f} mm<br>Y：%{customdata[1]:.3f} mm<br>Z：%{z:.3f} mm<br><b>相对平均水面高度：%{z:+.3f} mm</b><br>数据来源：未知（官方规则网格估计）<extra></extra>'))
    fig.add_trace(go.Heatmap(z=np.where(valid,np.nan,1).astype(np.float32),x0=0,dx=1,y0=0,dy=1,colorscale=invisible,showscale=False,hoverongaps=False,zsmooth=False,
        hovertemplate='像素坐标：(%{x:.0f}, %{y:.0f})<br><b>该像素暂无有效三维高度数据</b><br>数据来源：无有效数据<extra></extra>'))
    fig.update_layout(height=680,margin=dict(l=35,r=10,t=10,b=35),hovermode='closest',hoverlabel=dict(bgcolor='white',font_size=15),showlegend=False,
        xaxis=dict(title='原尺寸图像像素 u',range=[-.5,width-.5],constrain='domain'),
        yaxis=dict(title='原尺寸图像像素 v',range=[height-.5,-.5],scaleanchor='x',scaleratio=1))
    return fig
