from pathlib import Path
import cv2
import numpy as np
import pytest
from production_app.storage import ProjectStore, identity, ResultCache, write_json, digest
from production_app.adapters import VideoSourceAdapter, load_matrix, save_matrix
from production_app.adapters import OfficialRunner,ToolFailure,WassAdapter,OpenCVCalibrationAdapter,WassLowcostAdapter
from production_app.application import extract_pair,ReconstructionService,ReferenceService,ExportService
import json
import sys


def video(tmp_path):
    p = tmp_path / 'input.avi'
    writer = cv2.VideoWriter(str(p), cv2.VideoWriter_fourcc(*'MJPG'), 10, (64, 48))
    for i in range(10):
        writer.write(np.full((48, 64, 3), i*20, np.uint8))
    writer.release()
    return p


def test_project_create_save_open(tmp_path):
    store = ProjectStore()
    p = store.create(tmp_path, '中文项目')
    p.videos['left'] = '/video/reference-only.mp4'
    store.save(p)
    assert store.open(tmp_path/'project.json').record() == p.record()
    assert not (tmp_path/'reference-only.mp4').exists()
    with pytest.raises(ValueError):
        store.create(tmp_path, '覆盖')


def test_video_metadata_seek(tmp_path):
    v = VideoSourceAdapter(video(tmp_path))
    assert v.metadata()['frame_count'] == 10
    assert v.seek(4).shape == (48, 64, 3)
    assert abs(v.seek(4).mean()-80) < 3
    with pytest.raises(ValueError):
        v.seek(10)
    v.close()


def test_matrix_unicode_and_identity(tmp_path):
    p = tmp_path/'中文.xml'
    save_matrix(p, np.eye(3))
    assert np.array_equal(load_matrix(p), np.eye(3))
    assert identity({'frame':1}) != identity({'frame':2})


def test_cache_does_not_reuse_changed_file(tmp_path):
    p = ProjectStore().create(tmp_path, 'cache')
    f = tmp_path/'output.txt'
    f.write_text('official result')
    p.frames['key'] = {'output_hashes':{str(f):digest(f)}}
    assert ResultCache().lookup(p, 'key')
    f.write_text('changed')
    assert ResultCache().lookup(p, 'key') is None


def test_runner_failure_keeps_exact_log(tmp_path):
    runner=OfficialRunner(tmp_path,lambda s:None)
    with pytest.raises(ToolFailure,match='exact failure'):
        runner.run('failure',[sys.executable,'-c','import sys;print("exact failure");sys.exit(3)'])
    assert runner.calls[0]['returncode']==3
    assert 'exact failure' in (tmp_path/'failure.log').read_text()


def test_wass_commands_and_success_contract(tmp_path):
    class Recorder:
        def __init__(self):self.commands=[]
        def run(self,name,argv):self.commands.append(list(map(str,argv)))
    r=Recorder();w=WassAdapter({'wass_bin':'official'},r)
    w.prepare('config',tmp_path,'left.png','right.png');w.match('config',tmp_path);w.autocalibrate('list.txt')
    assert '--c0' in r.commands[0] and '--c1' in r.commands[0]
    assert r.commands[2][-1]=='list.txt'
    with pytest.raises(ToolFailure,match='未生成'):w.stereo('config',tmp_path)
    (tmp_path/'mesh_cam.xyzC').write_bytes(b'official output')
    w.stereo('config',tmp_path)


def test_extract_pair_applies_saved_offset(tmp_path,monkeypatch):
    p=ProjectStore().create(tmp_path/'project','sync')
    p.sync={'right_minus_left_s':.075}
    p.videos={f'measurement_{c}':{'path':str(video(tmp_path))} for c in ['left','right']}
    seen=[]
    def extract(self,t,file,ffmpeg,runner):
        seen.append(t);Path(file).write_bytes(b'frame')
    monkeypatch.setattr(VideoSourceAdapter,'extract',extract)
    l,r,lt,rt=extract_pair(p,{'ffmpeg':'ffmpeg'},None,tmp_path/'pair',.3)
    assert seen==pytest.approx([.3,.375]) and l.exists() and r.exists()


def test_calibration_detection_and_failure(tmp_path):
    data=OpenCVCalibrationAdapter().detect(video(tmp_path),tmp_path/'detected',[6,9],2,3,lambda s:None)
    assert len(data['records'])==3
    assert all(Path(r['preview']).exists() for r in data['records'])
    with pytest.raises(ValueError,match='至少需要10'):
        OpenCVCalibrationAdapter().calibrate(tmp_path/'detected/detections.json',tmp_path/'cal',.02)


def test_opencv_calibration_outputs(tmp_path):
    points=np.zeros((54,3),np.float32);points[:,:2]=np.mgrid[0:6,0:9].T.reshape(-1,2)*.02
    K=np.array([[700,0,320],[0,710,240],[0,0,1.]],float)
    records=[]
    for i in range(12):
        corners,_=cv2.projectPoints(points,np.array([.03*i,.01*i,.02*i]),np.array([-.04,.002*i,.55+.02*i]),K,np.zeros(5))
        records.append(dict(index=i,found=True,corners=corners.reshape(-1,2).tolist()))
    source=tmp_path/'source.mp4';source.write_bytes(b'raw')
    write_json(tmp_path/'detections.json',dict(records=records,pattern=[6,9],image_size_wh=[640,480],source_video=str(source)))
    result=OpenCVCalibrationAdapter().calibrate(tmp_path/'detections.json',tmp_path/'cal',.02)
    assert result['rms']<.01 and len(result['per_view_rms'])==12
    assert load_matrix(tmp_path/'cal/intrinsics.xml').shape==(3,3)
    assert result['source_sha256']==digest(source)


def test_tlcc_original_blocks_execution(tmp_path):
    upstream=tmp_path/'upstream';upstream.mkdir()
    (upstream/'wass_sync.py').write_text("import os\nif not os.path.isfile(pathname+'crosscorrelate.praat'):\n open(pathname+'crosscorrelate.praat','w').write('official script')\nfor wav_file in wav_list:\n if audio_wind_filter=='on':\n  pass\n",encoding='utf-8')
    praat=tmp_path/'praat';praat.write_bytes(b'praat')
    l=tmp_path/'l';r=tmp_path/'r';l.write_bytes(b'left');r.write_bytes(b'right')
    class Runner:
        def run(self,name,argv,**kw):
            if name=='TLCC_Praat':return '-0.075070\n'
            Path(argv[-1]).write_bytes(b'audio');return ''
    result=WassLowcostAdapter().run(str(l),str(r),tmp_path/'sync',dict(wass_lowcost=str(upstream),ffmpeg='ffmpeg',praat=str(praat)),Runner())
    assert result['right_minus_left_s']==-.075
    assert result['upstream_sha256']==digest(upstream/'wass_sync.py')


def test_reference_identity_and_provenance(tmp_path,monkeypatch):
    p=ProjectStore().create(tmp_path/'p','ref');p.calibration={'directory':str(tmp_path)}
    setup=tmp_path/'config.mat';setup.write_bytes(b'official reference')
    write_json(tmp_path/'ref.json',dict(calibration_identity='same',setup=str(setup),setup_hash=digest(setup),provenance={'method':'official'}))
    monkeypatch.setattr('production_app.application.calibration_identity',lambda cfg:'same')
    service=ReferenceService(p,{})
    assert service.load_existing(tmp_path/'ref.json')['provenance']['method']=='official'
    monkeypatch.setattr('production_app.application.calibration_identity',lambda cfg:'different')
    with pytest.raises(ValueError,match='几何不同'):service.load_existing(tmp_path/'ref.json')


def test_current_identity_export_and_no_overwrite(tmp_path,monkeypatch):
    p=ProjectStore().create(tmp_path/'p','identity');p.calibration={'directory':str(tmp_path)}
    (tmp_path/'stereo_config.txt').write_text('official')
    monkeypatch.setattr('production_app.application.calibration_identity',lambda cfg:'geometry')
    s=ReconstructionService(p,{})
    assert s.job.exists() and s.key(1,.07)!=s.key(2,.07)
    f=tmp_path/'mapping.mat';f.write_bytes(b'current frame')
    result={'files':{'mapping':str(f)},'left_time_s':2}
    ExportService().run(result,tmp_path/'export')
    assert (tmp_path/'export/mapping.mat').read_bytes()==f.read_bytes()
    with pytest.raises(ValueError,match='必须为空'):ExportService().run(result,tmp_path/'export')


@pytest.mark.parametrize('dpi',[1,2])
def test_gui_hover_resize_zoom_and_pixel_source(tmp_path,monkeypatch,dpi):
    monkeypatch.setenv('QT_QPA_PLATFORM','offscreen')
    from production_app.presentation import QApplication,QPointF,ImageView,label,query,ProductionWindow
    app=QApplication.instance() or QApplication([])
    mapping=np.zeros((48,64,3));mapping[20,30]=[.1,.2,.003]
    assert query(mapping,30,20)['H_mm']==pytest.approx(3)
    assert query(mapping,0,0)['source']=='NONE' and query(mapping,-1,0)['source']=='NONE'
    view=ImageView(label(''));view.resize(800*dpi,600*dpi);view.show()
    view.display(np.zeros((48,64,3),np.uint8),mapping);app.processEvents()
    for size in [(900,700),(1200,800)]:
        view.resize(*size);view.scale(1.2,1.2);app.processEvents()
        point=view.mapFromScene(QPointF(30.5,20.5))
        assert view.scene_pixel(point)==(30,20)
    view.close()
    w=ProductionWindow({},tmp_path);assert w.navigation.count()==5;w.close()


def test_playback_step_button_and_true_mouse_hover(tmp_path,monkeypatch):
    monkeypatch.setenv('QT_QPA_PLATFORM','offscreen')
    from production_app.presentation import QApplication,ProductionWindow,QPointF,ImageView,label
    from PySide6.QtTest import QTest
    from PySide6.QtCore import QPoint
    app=QApplication.instance() or QApplication([])
    raw=video(tmp_path);v=VideoSourceAdapter(raw);meta=v.metadata();v.close();meta['sha256']=digest(raw)
    p=ProjectStore().create(tmp_path/'p','playback')
    p.videos={'measurement_left':meta,'measurement_right':meta};p.sync={'right_minus_left_s':0,'method':'test fixture'}
    w=ProductionWindow({},tmp_path);w.set_project(p);w.navigation.setCurrentRow(3);w.show();app.processEvents()
    w.timeline.setValue(4);assert w.frame_index==4 and not w.reconstruct_button.isEnabled()
    w.frame_selector.setValue(3);assert w.frame_index==3 and w.timeline.value()==3
    w.timeline.setValue(4)
    w.next_frame();assert w.frame_index==5
    p.reference={'baseline_m':.07};p.calibration={'extrinsics':{'R':[]}}
    w.play_pause();assert w.timer.isActive() and not w.reconstruct_button.isEnabled()
    w.play_pause();assert not w.timer.isActive() and w.reconstruct_button.isEnabled()
    w.navigation.setCurrentRow(4);assert not w.timer.isActive();w.close()
    view=ImageView(label(''));view.resize(800,600);view.show()
    mapping=np.zeros((48,64,3));mapping[20,30]=[.1,.2,.003]
    view.display(np.zeros((48,64,3),np.uint8),mapping);app.processEvents()
    QTest.mouseMove(view.viewport(),view.mapFromScene(QPointF(30.5,20.5)));app.processEvents()
    assert view.last_query['H_mm']==pytest.approx(3)
    view.close()


def test_worker_uses_writable_project_directory(tmp_path,monkeypatch):
    monkeypatch.setenv('QT_QPA_PLATFORM','offscreen')
    from production_app.presentation import QApplication,ProductionWindow
    app=QApplication.instance() or QApplication([])
    p=ProjectStore().create(tmp_path/'p','worker')
    w=ProductionWindow({'python':'missing-test-python'},tmp_path)
    w.set_project(p)
    w.job('sync',{})
    assert w.process.workingDirectory()==p.directory
    w.process.waitForFinished(100)
    w.close()


@pytest.fixture
def project_ui(tmp_path,monkeypatch):
    monkeypatch.setenv('QT_QPA_PLATFORM','offscreen')
    from production_app import presentation as ui
    from production_app.application import ProjectService
    monkeypatch.setattr('production_app.application.provenance',lambda tools:{'test_toolchain':'unchanged'})
    app=ui.QApplication.instance() or ui.QApplication([])
    window=ui.ProductionWindow({'project_root':str(tmp_path/'projects')},tmp_path)
    warnings=[]
    monkeypatch.setattr(ui.QMessageBox,'warning',lambda *a:warnings.append(a[2]))
    yield window,app,warnings,ui,ProjectService
    window.close()


def dialog_values(monkeypatch,ui,name,directory):
    def accept(dialog):
        dialog.name.setText(name);dialog.directory.setText(str(directory))
        return ui.QDialog.DialogCode.Accepted
    monkeypatch.setattr(ui.ProjectDialog,'exec',accept)


def test_startup_and_save_without_project_feedback(project_ui):
    w,app,warnings,ui,_=project_ui
    assert w.project is w.active_project is w.current_project is None
    assert w.task_status.text()=='尚未创建或打开项目'
    assert not any(item.text().endswith('.mp4') for item in w.findChildren(ui.QLabel))
    assert all(not(w.navigation.item(i).flags()&ui.Qt.ItemFlag.ItemIsEnabled) for i in range(1,5))
    save=next(a for a in w.menuBar().actions()[0].menu().actions() if a.text()=='保存项目')
    save.trigger()
    assert warnings and '新建项目' in warnings[-1] and '打开已有项目' in warnings[-1]
    w.save_project_as();assert len(warnings)==2


def test_new_save_open_workflow_and_workspace(project_ui,tmp_path,monkeypatch):
    w,app,warnings,ui,service=project_ui
    root=tmp_path/'new'
    dialog_values(monkeypatch,ui,'新项目',root)
    w.new_project()
    assert w.current_project is w.active_project is w.project
    assert (root/'project.json').exists() and '当前项目：' in w.task_status.text()
    for name in ('calibration','sync','reference','frames','logs'):
        assert (root/'workspace'/name).is_dir()
    w.navigation.setCurrentRow(1)
    assert any('请先导入左右标定视频' in q.text() for q in w.findChildren(ui.QLabel))
    w.cols.setValue(8)
    w.navigation.setCurrentRow(0)
    button=next(b for b in w.findChildren(ui.QPushButton) if b.text()=='保存项目')
    button.click()
    saved=ProjectStore().open(root/'project.json')
    assert saved.workflow['cols']==8 and '项目已保存：' in w.task_status.text()
    assert saved.toolchain=={'test_toolchain':'unchanged'}
    monkeypatch.setattr(ui.QFileDialog,'getOpenFileName',lambda *a:(str(root/'project.json'),''))
    w.open_project()
    assert w.project.record()==saved.record()
    assert '当前项目：' in w.task_status.text() and not warnings


def test_save_as_preserves_four_video_metadata_and_science_references(project_ui,tmp_path,monkeypatch):
    w,app,warnings,ui,service=project_ui
    original=ProjectStore().create(tmp_path/'original','original')
    raw=video(tmp_path);v=VideoSourceAdapter(raw);meta=v.metadata();v.close()
    meta['sha256']=digest(raw)
    original.videos={k:dict(meta) for k in ['calibration_left','calibration_right','measurement_left','measurement_right']}
    original.sync={'right_minus_left_s':0,'method':'saved official fixture'}
    # Keep artifact references unmodified; this test performs no science call.
    original.reference={'setup':'official/config.mat','baseline_m':.07,'provenance':{'method':'official'}}
    original.frames={'official_frame':{'files':{'mapping':'official/current.mat'}}}
    original.toolchain={'official_source_hash':'same'}
    ProjectStore().save(original)
    w.set_project(original)
    w.navigation.setCurrentRow(1);w.cols.setValue(6)
    w.save_project()
    dialog_values(monkeypatch,ui,'copied',tmp_path/'copied')
    w.save_project_as()
    assert w.project.directory==str((tmp_path/'copied').resolve())
    assert '项目已另存为' in w.task_status.text()
    copied=ProjectStore().open(tmp_path/'copied/project.json')
    for name in ['videos','sync','reference','frames','toolchain']:
        assert getattr(copied,name)==getattr(original,name)
    assert copied.workflow['cols']==6
    assert copied.workflow['saved_from_project']['sha256']==digest(tmp_path/'original/project.json')
    assert not (tmp_path/'copied/input.avi').exists()
    assert all(w.navigation.item(i).flags()&ui.Qt.ItemFlag.ItemIsEnabled for i in range(1,5))
    w.close()
    reopened=ui.ProductionWindow({},tmp_path);reopened.set_project(copied)
    assert len(reopened.project.videos)==4 and reopened.cols.value()==6
    assert reopened.navigation.currentRow()==1
    reopened.close()
    assert not warnings


def test_example_is_real_project_not_prefill(project_ui,tmp_path,monkeypatch):
    w,app,warnings,ui,service=project_ui
    from production_app.application import ProjectService
    w.tools['example']={k:f'raw/{k}.mp4' for k in ['calibration_left','calibration_right','measurement_left','measurement_right']}
    def input_fixture(self,p,key,path):
        p.videos[key]={'path':path,'width':1920,'height':1080,'fps':30,'frame_count':60,
                       'duration_s':2,'has_audio':True,'codec_fourcc':1}
        self.store.save(p)
    monkeypatch.setattr(ProjectService,'input',input_fixture)
    assert not w.project
    w.example()
    path=Path(w.tools['project_root'])/'HomeTank_004_example/project.json'
    assert path.is_file() and len(ProjectStore().open(path).videos)==4
    assert w.project is w.active_project and '当前项目：' in w.task_status.text()
    w.save_project();assert '项目已保存：' in w.task_status.text()
    w.navigation.setCurrentRow(1)
    detection=next(b for b in w.findChildren(ui.QPushButton) if b.text()=='抽帧与官方棋盘检测')
    assert detection.isEnabled()
    assert not warnings
