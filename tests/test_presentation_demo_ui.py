"""Frozen-data UI regression: no WASS, no numerical artifact writes."""
import sys
from pathlib import Path
import numpy as np
import pytest

TOOLS = Path(__file__).resolve().parents[1]/'tools'
sys.path.insert(0,str(TOOLS))
import presentation_demo_data as data


def test_query_bounds_sentinels_and_provenance():
    mapping = np.array([[[.1,.2,.003],[0,0,0],[1,1,1]]])
    result = data.query(mapping,0,0)
    assert result['H_mm']==3
    assert result['provenance']=='UNKNOWN'
    assert result['estimate_method']=='OFFICIAL_RENDERED_DCT_GRID'
    assert data.query(mapping,1,0)['provenance']=='UNSUPPORTED'
    assert data.query(mapping,2,0)['provenance']=='UNSUPPORTED'
    with pytest.raises(data.AssetError,match='outside image'):
        data.query(mapping,-1,0)
    with pytest.raises(data.AssetError,match='asset missing'):
        data.require(TOOLS/'NOT_PRESENT.nc')


def test_frozen_loaders_and_unchanged_payload():
    record = data.manifest()
    root = Path(record['outputs']['root'])
    if not root.exists():
        pytest.skip('Golden large assets only present on demo computer')
    assert data.verify_frozen(record)==299
    for i in range(5):
        paths = data.frame_paths(root,i)
        for path in paths.values():
            data.require(path)
        xyz,total = data.point_cloud(paths['ply'])
        assert total==record['frame_metrics'][i]['source_points']
        assert len(xyz)<=25000 and np.isfinite(xyz).all()
        x,y,z = data.height_grid(root/'gridding/gridded.nc',i)
        assert x.shape==y.shape==z.shape==(256,256)
        mapping = data.pixel_mapping(paths['mat'])
        assert mapping.shape==(1350,2400,3)
        assert data.query(mapping,1000,1050)['provenance']=='UNKNOWN'
    assert data.verify_frozen(record)==299


def test_streamlit_pages_frames_and_graceful_error(monkeypatch):
    from streamlit.testing.v1 import AppTest
    record = data.manifest()
    if not Path(record['outputs']['root']).exists():
        pytest.skip('Golden large assets only present on demo computer')
    app = AppTest.from_file(str(TOOLS/'presentation_demo_ui.py'),default_timeout=30).run()
    assert not app.exception and not app.error
    for page in ['双目输入','流程展示','3D Point Cloud','Height Map','Image Overlay','Pixel Query','Conclusion']:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception and not app.error, page
    app.sidebar.radio[0].set_value('双目输入').run()
    for i in range(5):
        app.sidebar.selectbox[0].set_value(i).run()
        assert not app.exception and not app.error
    app.sidebar.radio[0].set_value('Pixel Query').run()
    app.number_input[0].set_value(-1).run()
    assert not app.exception and 'outside image' in app.error[0].value
    monkeypatch.setattr(data,'manifest',lambda:dict(record,outputs={'root':str(TOOLS/'NOT_PRESENT')}))
    broken = AppTest.from_file(str(TOOLS/'presentation_demo_ui.py'),default_timeout=30).run()
    broken.sidebar.radio[0].set_value('双目输入').run()
    assert not broken.exception and 'Golden Demo asset missing:' in broken.error[0].value
    assert data.verify_frozen(record)==299
