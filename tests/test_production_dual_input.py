"""IO/state/process isolation contracts, never replacement scientific models."""
from pathlib import Path
import json
import os
import sys
import cv2
import numpy as np
import pytest
from production_app.storage import ProjectStore,digest
from production_app.application import ProjectService,extract_pair,SyncService,CalibrationService
from production_app.sources import StereoImageSequenceSource,sequence_records
from production_app.environment import ProcessEnvironmentAdapter,ExternalToolRunner


def sequence(tmp_path):
    for camera in ('left','right'):
        root=tmp_path/camera;root.mkdir()
        for i in range(4):
            cv2.imencode('.jpg',np.full((48,64,3),i*20,np.uint8))[1].tofile(str(root/f'{i:06d}.jpg'))
    return tmp_path/'left',tmp_path/'right'


def test_sequence_extract_is_exact_copy_and_no_ffmpeg_or_tlcc(tmp_path):
    left,right=sequence(tmp_path)
    p=ProjectStore().create(tmp_path/'p','sample')
    ProjectService({}).image_sequence(p,left,right,12,{'source':'author repository'})
    assert p.source_type=='stereo_image_sequence' and p.sync['status']=='PROVIDED'
    l,r,lt,rt=extract_pair(p,{'ffmpeg':'must not run'},None,tmp_path/'pair',2/12)
    assert l.suffix==r.suffix=='.jpg' and lt==rt==2/12
    assert digest(l)==digest(left/'000002.jpg')
    assert digest(r)==digest(right/'000002.jpg')
    assert SyncService(p,{}).run()['status']=='PROVIDED'
    restored=ProjectStore().open(tmp_path/'p/project.json')
    assert restored.record()==p.record()


def test_sequence_mismatch_changed_original_and_nonframe_time_rejected(tmp_path):
    left,right=sequence(tmp_path)
    records=sequence_records(left,right,12)
    source=StereoImageSequenceSource(records['measurement_left'])
    assert source.seek(3).shape==(48,64,3)
    with pytest.raises(ValueError,match='不能插值'):
        source.seek_time(.1)
    original=(left/'000000.jpg').read_bytes()
    (left/'000000.jpg').write_bytes(b'changed')
    with pytest.raises(ValueError,match='校验失败'):source.seek(0)
    (left/'000000.jpg').write_bytes(original)
    (right/'000003.jpg').rename(right/'000004.jpg')
    with pytest.raises(ValueError,match='帧名/数量'):sequence_records(left,right,12)


def test_process_environment_strips_bundle_paths_only(tmp_path):
    bundle=tmp_path/'bundle';external=tmp_path/'official'
    original={'PATH':os.pathsep.join([str(bundle),str(bundle/'cv2'),str(external)]),
              'QT_PLUGIN_PATH':'bad','QT_QPA_PLATFORM':'offscreen','_PYI_APPLICATION_HOME_DIR':'bad',
              'PYTHONHOME':'bad','SystemRoot':'Windows','UNRELATED':'keep'}
    clean=ProcessEnvironmentAdapter.clean(original,bundle)
    assert clean['PATH']==str(external)
    assert clean['SystemRoot']=='Windows' and clean['UNRELATED']=='keep'
    assert all(k not in clean for k in ['QT_PLUGIN_PATH','QT_QPA_PLATFORM','_PYI_APPLICATION_HOME_DIR','PYTHONHOME'])
    assert original['QT_PLUGIN_PATH']=='bad'
    p=ExternalToolRunner.run([sys.executable,'-c','import cv2;print(cv2.__version__)'],timeout=15)
    assert p.returncode==0


def test_provided_intrinsics_keep_exact_xml_and_no_fake_extrinsics(tmp_path,monkeypatch):
    from production_app.adapters import save_matrix
    cfg=tmp_path/'author';cfg.mkdir()
    for i in (0,1):
        save_matrix(cfg/f'intrinsics_0{i}.xml',np.eye(3))
        save_matrix(cfg/f'distortion_0{i}.xml',np.zeros((5,1)))
    p=ProjectStore().create(tmp_path/'p','official')
    p.reference={'old':'reference'}
    p.stages.update(reference='COMPUTED',height='COMPUTED')
    s=CalibrationService(p,{})
    def generate(out):
        (out/'stereo_config.txt').write_text('# defaults')
    monkeypatch.setattr(s,'official_config',generate)
    result=s.load_provided(cfg,dict(source='author',image_size_wh=[64,48]))
    assert result['status']=='PROVIDED' and not result['fallback']
    assert result['extrinsics'] is None and p.stages['extrinsics']=='NOT_READY'
    assert not p.reference and p.stages['reference']==p.stages['height']=='NOT_READY'
    for original in cfg.glob('*.xml'):
        assert digest(original)==digest(Path(result['directory'])/original.name)


def test_sequence_gui_playback_uses_images_and_provided_sync(tmp_path,monkeypatch):
    monkeypatch.setenv('QT_QPA_PLATFORM','offscreen')
    from production_app.presentation import QApplication,ProductionWindow,QPushButton,QLabel
    app=QApplication.instance() or QApplication([])
    left,right=sequence(tmp_path)
    p=ProjectStore().create(tmp_path/'p','images')
    ProjectService({}).image_sequence(p,left,right,12,{'source':'official'})
    w=ProductionWindow({},tmp_path);w.set_project(p);w.navigation.setCurrentRow(3)
    w.frame_selector.setValue(2)
    assert w.frame_index==2 and isinstance(w.sources['left'],StereoImageSequenceSource)
    assert not any('TLCC' in b.text() for b in w.findChildren(QPushButton))
    assert any('PROVIDED' in label.text() for label in w.findChildren(QLabel))
    w.next_frame();assert w.frame_index==3
    w.close()
