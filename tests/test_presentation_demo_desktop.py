"""Native desktop-only frozen lookup checks. No reconstruction."""
import os
import sys
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import pytest
pytest.importorskip('PySide6')
from PySide6.QtWidgets import QApplication,QMessageBox
from PySide6.QtCore import QPointF
from PySide6.QtTest import QTest
import presentation_demo_desktop as desktop
import presentation_demo_data as data


def test_native_pages_frames_and_frozen_smoke():
    if not Path(data.manifest()['outputs']['root']).exists():
        pytest.skip('Local Golden large assets unavailable')
    record,root=desktop.load_settings()
    app=QApplication.instance() or QApplication([])
    window=desktop.DesktopWindow(record,root,dialogs=False)
    window.show()
    app.processEvents()
    result=desktop.smoke(window,record,root)
    assert result['status']=='PASS'
    assert result['frozen_hash_count']==299
    assert len(result['pages'])==8 and len(result['frames'])==5
    assert '浏览器' not in window.windowTitle()
    assert '−' not in desktop.query_text(window.current_view.mapping,1000,1050)
    for (u,v),expected in zip([(1000,1050),(1100,1000),(1000,1000)],[-10.598,.256,-5.612]):
        result=data.query(window.current_view.mapping,u,v)
        assert result['H_mm']==pytest.approx(expected,abs=.0005)
        assert result['Z_m']==float(window.current_view.mapping[v,u,2])
    assert '暂无有效' in desktop.query_text(window.current_view.mapping,10,8)
    window.close()


def test_scaled_mouse_origin_and_chinese_missing_file(tmp_path,monkeypatch):
    from PIL import Image
    import numpy as np
    app=QApplication.instance() or QApplication([])
    image=tmp_path/'small.png'
    Image.new('RGB',(40,30)).save(image)
    mapping=np.zeros((30,40,3),dtype=float)
    mapping[12,23]=[.1,.2,.03]
    view=desktop.PixelView(image,mapping)
    view.resize(800,600)
    view.show()
    app.processEvents()
    p=view.mapFromScene(QPointF(23.5,12.5))
    assert view.scene_pixel(p)==(23,12)
    desktop.test_mouse_move(view,p)
    app.processEvents()
    assert view.last_pixel==(23,12)
    assert '30.000' in desktop.query_text(mapping,23,12)
    view.close()
    record=data.manifest()
    errors=[]
    monkeypatch.setattr(QMessageBox,'warning',lambda parent,title,text:errors.append(text))
    broken=desktop.DesktopWindow(record,tmp_path,dialogs=True)
    assert broken.error and '文件缺失' in errors[0]
    broken.close()


def test_no_web_or_reconstruction_entry_imports():
    import ast
    source=Path(desktop.__file__).read_text(encoding='utf8')
    imports=[n.module for n in ast.walk(ast.parse(source)) if isinstance(n,ast.ImportFrom)]
    assert not any(n and ('streamlit' in n or 'plotly' in n or 'WebEngine' in n) for n in imports)
    assert 'subprocess' not in source and 'socket' not in source
