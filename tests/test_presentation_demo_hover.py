"""Exact display lookup, missing-pixel gates and five-frame MAT comparison."""
import sys
from pathlib import Path
import numpy as np
import pytest
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from presentation_demo_data import manifest,frame_paths,pixel_mapping,query,verify_frozen
from presentation_demo_hover import hover_lookup,hover_figure


def test_original_pixel_axes_missing_and_no_nearest_fill(tmp_path):
    m = np.zeros((3,4,3),dtype=np.float32)
    m[1,2]=[.123,.456,.007]
    m[2,1]=[.321,.654,-.008]
    m[0,1]=np.nan
    xy,z,valid = hover_lookup(m)
    assert valid[1,2] and valid[2,1]
    assert z[1,2]==pytest.approx(7) and z[2,1]==pytest.approx(-8)
    assert not valid[0,1] and np.isnan(z[0,1])
    assert not valid[1,1] and np.isnan(z[1,1])  # adjacent known point is NOT copied
    image = tmp_path/'image.png'
    Image.new('RGB',(4,3)).save(image)
    figure = hover_figure(image,m)
    assert list(figure.layout.xaxis.range)==[-.5,3.5]
    assert list(figure.layout.yaxis.range)==[2.5,-.5]
    assert figure.data[1].x0==figure.data[1].y0==0
    assert figure.data[1].dx==figure.data[1].dy==1
    assert '相对平均水面高度' in figure.data[1].hovertemplate
    assert '暂无有效三维高度数据' in figure.data[2].hovertemplate
    assert not figure.data[1].hoverongaps
    assert figure.data[1].zsmooth is False


def test_five_frame_spot_checks_and_camera_convention():
    record = manifest()
    root = Path(record['outputs']['root'])
    if not root.exists():
        pytest.skip('Local Golden large assets unavailable')
    for i in range(5):
        paths = frame_paths(root,i)
        assert paths['mat'].name==f'{i:08d}.mat'
        # Frozen official configuration explicitly selected stereo_image_idx 0.
        assert '--stereo_image_idx 0' in (root/'logs/setup.log').read_text(encoding='utf8').splitlines()[0]
        m = pixel_mapping(paths['mat'])
        assert m.shape==(1350,2400,3)
        xy,z,valid = hover_lookup(m)
        for u,v in [(1000,1050),(1100,1000),(1000,1000)]:
            assert valid[v,u]
            original = query(m,u,v)
            np.testing.assert_allclose(np.r_[xy[v,u],z[v,u]],m[v,u].astype(float)*1000,rtol=0,atol=0.0001)
            assert z[v,u]==pytest.approx(original['H_mm'],abs=.0001)
            assert original['u']==u and original['v']==v
    assert verify_frozen(record)==299
