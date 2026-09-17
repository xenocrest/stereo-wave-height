"""Qt Widgets UI. No scientific solver, segmentation or surface fitting."""
import json
import math
from pathlib import Path
import sys
import uuid
import traceback
import cv2
import numpy as np
from scipy.io import loadmat
from plyfile import PlyData
from PySide6.QtCore import Qt,QTimer,QProcess,QProcessEnvironment,QPointF
from PySide6.QtGui import QImage,QPixmap,QFont,QAction
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QLabel,
    QListWidget,QPushButton,QFileDialog,QLineEdit,QSpinBox,QDoubleSpinBox,QSlider,QComboBox,
    QGraphicsView,QGraphicsScene,QMessageBox,QTableWidget,QTableWidgetItem,QToolTip,QSplitter,QPlainTextEdit,QScrollArea,
    QDialog,QDialogButtonBox,QFormLayout)
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
import matplotlib
from .application import ProjectService,CalibrationService,ExportService,frame_identity
from .storage import ProjectStore,write_json,ResultCache
from .adapters import VideoAdapter,load_matrix

matplotlib.rcParams['font.sans-serif']=['Microsoft YaHei','SimHei','DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus']=False
STAGES=['项目与数据','相机标定','参考面','视频测量','结果与导出']


def query(mapping,u,v):
    if mapping is None or not (0<=v<mapping.shape[0] and 0<=u<mapping.shape[1]):
        return dict(source='NONE',u=u,v=v)
    xyz=np.asarray(mapping[v,u],float)
    if not np.isfinite(xyz).all() or np.all(xyz==0) or np.all(xyz==1):
        return dict(source='NONE',u=u,v=v)
    return dict(source='OFFICIAL_GRID_ESTIMATE',u=u,v=v,XYZ_mm=(xyz*1000).tolist(),H_mm=float(xyz[2]*1000))


class ImageView(QGraphicsView):
    def __init__(self,status):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.item=self.scene().addPixmap(QPixmap())
        self.mapping=None
        self.last_query=None
        self.status=status
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.setMinimumHeight(220)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

    def display(self,image,mapping=None):
        if isinstance(image,np.ndarray):
            if image.ndim==2:
                q=QImage(image.data,image.shape[1],image.shape[0],image.strides[0],QImage.Format.Format_Grayscale8).copy()
            else:
                rgb=cv2.cvtColor(image,cv2.COLOR_BGR2RGB)
                q=QImage(rgb.data,rgb.shape[1],rgb.shape[0],rgb.strides[0],QImage.Format.Format_RGB888).copy()
            pix=QPixmap.fromImage(q)
        else:
            pix=QPixmap(str(image))
        if pix.isNull():
            raise ValueError('图像读取失败')
        if mapping is not None and mapping.shape != (pix.height(),pix.width(),3):
            raise ValueError('当前帧图像与官方映射尺寸不同，停止查询')
        changed=self.item.pixmap().size()!=pix.size()
        self.item.setPixmap(pix)
        self.scene().setSceneRect(self.item.boundingRect())
        self.mapping=mapping
        if changed:
            self.fitInView(self.item,Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        self.fitInView(self.item,Qt.AspectRatioMode.KeepAspectRatio)

    def scene_pixel(self,point):
        p=self.mapToScene(point)
        return math.floor(p.x()),math.floor(p.y())

    def mouseMoveEvent(self,event):
        u,v=self.scene_pixel(event.position().toPoint())
        r=query(self.mapping,u,v)
        self.last_query=r
        if r['source']=='NONE':
            text=f'像素：({u}, {v})\n该像素暂无直接三维高度数据'
            if self.mapping is None:
                text+='\n请切换本帧官方结果画面查询'
        else:
            x,y,z=r['XYZ_mm']
            text=f'官方图像像素：({u}, {v})\nX={x:.3f} mm\nY={y:.3f} mm\nZ={z:.3f} mm\nH={r["H_mm"]:+.3f} mm\n数据来源：官方水面网格估计（不是直接双目观测）'
        self.status.setText(text)
        if self.mapping is not None:
            QToolTip.showText(event.globalPosition().toPoint(),text,self)
        super().mouseMoveEvent(event)

    def wheelEvent(self,event):
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        scale=1.2 if event.angleDelta().y()>0 else 1/1.2
        self.scale(scale,scale)


def label(text):
    q=QLabel(text)
    q.setWordWrap(True)
    q.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return q


class ProjectDialog(QDialog):
    """Project metadata only; no scientific settings or calculations."""
    def __init__(self, parent, title, suggested_name=''):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(650,180)
        form=QFormLayout(self)
        self.name=QLineEdit(suggested_name)
        self.directory=QLineEdit()
        form.addRow('项目名称',self.name)
        path_row=QWidget();row=QHBoxLayout(path_row);row.setContentsMargins(0,0,0,0)
        row.addWidget(self.directory)
        browse=QPushButton('选择目录…');row.addWidget(browse)
        browse.clicked.connect(self.browse)
        form.addRow('项目目录（英文路径）',path_row)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText('确定')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('取消')
        buttons.accepted.connect(self.validate);buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def browse(self):
        path=QFileDialog.getExistingDirectory(self,'选择项目目录')
        if path:self.directory.setText(path)

    def validate(self):
        if not self.name.text().strip() or not self.directory.text().strip():
            QMessageBox.warning(self,'项目信息不完整','请输入项目名称和项目目录。');return
        self.accept()


class ProductionWindow(QMainWindow):
    def __init__(self,tools,source_root):
        super().__init__()
        self.tools=tools
        self.source_root=str(source_root)
        self.project=None
        self.current_result=None
        self.process=None
        self.sources={}
        self.timer=QTimer(self)
        self.timer.timeout.connect(self.next_frame)
        self.setWindowTitle('双目水面三维测量系统 V1')
        self.resize(1350,900)
        central=QWidget()
        self.setCentralWidget(central)
        vertical=QVBoxLayout(central)
        self.notice=label('未完成物理精度验证。当前三维结果为 WASS 官方输出，可能包含非水面结构；V1 未提供 ROI。')
        vertical.addWidget(self.notice)
        split=QSplitter()
        vertical.addWidget(split,1)
        self.navigation=QListWidget()
        self.navigation.addItems(STAGES)
        self.navigation.setMaximumWidth(180)
        split.addWidget(self.navigation)
        self.body=QWidget()
        self.content=QVBoxLayout(self.body)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(self.body)
        split.addWidget(scroll)
        self.task_status=label('尚未创建或打开项目')
        vertical.addWidget(self.task_status)
        self.navigation.currentRowChanged.connect(self.render)
        for name in ['文件','项目','标定','参考面','测量','结果','帮助']:
            self.menuBar().addMenu(name)
        file_menu=self.menuBar().actions()[0].menu()
        for title,call in [('新建项目',self.new_project),('打开项目',self.open_project),('保存项目',self.save_project),('项目另存为…',self.save_project_as),('打开 HomeTank_004 示例项目',self.example)]:
            action=QAction(title,self)
            action.triggered.connect(lambda checked=False,fn=call:self.guard(fn))
            file_menu.addAction(action)
        for index,page in [(1,0),(2,1),(3,2),(4,3),(5,4)]:
            action=QAction('进入'+STAGES[page],self)
            action.triggered.connect(lambda checked=False,p=page:self.navigation.setCurrentRow(p))
            self.menuBar().actions()[index].menu().addAction(action)
        help_action=QAction('操作说明',self)
        help_action.triggered.connect(lambda:QMessageBox.information(self,'操作说明',
            '项目与数据 → 标定 → 视频测量页同步 → 标定页外参 → 参考面 → 视频测量重建 → 结果导出。\n详细说明见程序目录 USER_GUIDE_ZH.md。官方算法失败时不会切换算法或伪造结果。'))
        self.menuBar().actions()[6].menu().addAction(help_action)
        self.navigation.setCurrentRow(0)

    def guard(self,fn):
        try:
            return fn()
        except Exception as error:
            root=Path(self.project.directory)/'workspace/logs' if self.project else Path(self.tools.get('project_root',self.source_root))
            root.mkdir(parents=True,exist_ok=True)
            with (root/'application_errors.log').open('a',encoding='utf-8') as log:
                log.write(traceback.format_exc()+'\n')
            self.task_status.setText('操作失败：'+str(error)[:160])
            QMessageBox.warning(self,'操作失败',f'{type(error).__name__}: {error}')

    def button(self,text,fn,enabled=True):
        b=QPushButton(text)
        b.setEnabled(enabled and not self.busy())
        b.clicked.connect(lambda:self.guard(fn))
        return b

    def busy(self):
        return self.process is not None and self.process.state()!=QProcess.ProcessState.NotRunning

    def new_project(self):
        if self.busy():raise ValueError('后台任务进行中，请等待结束后切换项目。')
        dialog=ProjectDialog(self,'新建项目')
        if dialog.exec()==QDialog.DialogCode.Accepted:
            self.set_project(ProjectService(self.tools).create(dialog.directory.text().strip(),dialog.name.text().strip()))

    def open_project(self):
        filename,_=QFileDialog.getOpenFileName(self,'打开项目','','项目 (*.json)')
        if filename:
            self.set_project(ProjectService(self.tools).open(filename))

    def save_project(self):
        if not self.require_project():return
        if self.busy():raise ValueError('后台任务进行中，请等待结束后保存项目。')
        self.capture_workflow()
        ProjectService(self.tools).save(self.project)
        self.task_status.setText('项目已保存：'+str(Path(self.project.directory)/'project.json'))

    def require_project(self):
        if self.project is not None:return True
        message='当前尚未创建或打开项目。\n请选择：\n1. 新建项目\n2. 打开已有项目\n3. 将当前数据另存为新项目（需先有活动项目数据）'
        self.task_status.setText('尚未创建或打开项目')
        QMessageBox.warning(self,'尚未打开项目',message)
        return False

    @property
    def current_project(self):
        return self.project

    @property
    def active_project(self):
        return self.project

    def capture_workflow(self, page=None):
        if not self.project:return
        state=self.project.workflow
        state.update(navigation=self.navigation.currentRow(),left_frame=getattr(self,'frame_index',0),
                     mode=getattr(self,'mode_index',0))
        fields={1:['cols','rows','square','interval','candidate_limit','ext_time'],
                2:['ref_time','baseline','center_x','center_y','area_size']}
        page=self.navigation.currentRow() if page is None else page
        for field in fields.get(page,[]):
            widget=getattr(self,field,None)
            if widget is not None:state[field]=widget.value()

    def save_project_as(self):
        if not self.require_project():return
        if self.busy():raise ValueError('后台任务进行中，请等待结束后另存项目。')
        dialog=ProjectDialog(self,'项目另存为',self.project.name+'_copy')
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        self.capture_workflow()
        ProjectService(self.tools).save(self.project)
        copied=ProjectService(self.tools).save_as(self.project,dialog.directory.text().strip(),dialog.name.text().strip())
        self.set_project(copied)
        self.task_status.setText('项目已另存为：'+str(Path(copied.directory)/'project.json'))

    def set_project(self,project):
        if self.busy():raise ValueError('后台任务进行中，请等待结束后切换项目。')
        self.timer.stop()
        for v in self.sources.values():
            v.close()
        self.sources={}
        self.current_result=None
        self.project=project
        self.rendered_project=None
        self.frame_index=project.workflow.get('left_frame',0)
        self.mode_index=project.workflow.get('mode',0)
        self.navigation.blockSignals(True)
        self.navigation.setCurrentRow(project.workflow.get('navigation',0))
        self.navigation.blockSignals(False)
        self.render()
        if self.navigation.currentRow()==3 and project.sync and all(k in project.videos for k in ['measurement_left','measurement_right']):
            mode=self.mode_index
            self.guard(lambda:self.seek(self.frame_index))
            if self.current_result and mode in (1,2,3):self.mode.setCurrentIndex(mode)
        self.task_status.setText('当前项目：'+project.directory)

    def example(self):
        path=Path(self.tools['project_root'])/'HomeTank_004_example'
        if (path/'project.json').exists():
            self.set_project(ProjectService(self.tools).open(path/'project.json'))
            return
        p=ProjectService(self.tools).create(path,'HomeTank_004 示例')
        for key in ['calibration_left','calibration_right','measurement_left','measurement_right']:
            ProjectService(self.tools).input(p,key,self.tools['example'][key])
        self.set_project(p)

    def choose_video(self,key):
        path,_=QFileDialog.getOpenFileName(self,'选择视频','','视频 (*.mp4 *.MP4 *.mov *.avi *.mkv)')
        if path:
            ProjectService(self.tools).input(self.project,key,path)
            self.set_project(self.project)

    def job(self,action,args):
        if not self.require_project():return
        if self.busy():raise ValueError('已有后台任务正在进行，请等待结束。')
        self.capture_workflow()
        ProjectService(self.tools).save(self.project)
        self.timer.stop()
        request=Path(self.project.directory)/'requests'/f'{uuid.uuid4().hex}.json'
        write_json(request,dict(project=str(Path(self.project.directory)/'project.json'),action=action,
                                tools=self.tools,args=args))
        self.request=request
        self.process=QProcess(self)
        # A desktop launcher may inherit a protected WindowsApps directory.
        # Official tools and their temporary files use the writable project.
        self.process.setWorkingDirectory(self.project.directory)
        env=QProcessEnvironment.systemEnvironment()
        env.insert('PYTHONPATH',self.source_root)
        env.insert('PYTHONUTF8','1')
        # Frozen Qt paths must not leak into external official scientific tools.
        for key in ['QT_PLUGIN_PATH','QT_QPA_PLATFORM_PLUGIN_PATH','QT_QPA_PLATFORM']:
            env.remove(key)
        self.process.setProcessEnvironment(env)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.progress)
        self.process.finished.connect(self.completed)
        self.process.errorOccurred.connect(self.process_error)
        self.process.start(self.tools['python'],['-m','production_app.worker','--request',str(request)])
        self.task_status.setText('任务已启动：'+action)
        self.render()

    def progress(self):
        text=bytes(self.process.readAllStandardOutput()).decode('utf-8',errors='replace')
        with self.request.with_suffix('.log').open('a',encoding='utf-8') as f:
            f.write(text)
        lines=text.strip().splitlines()
        if lines:
            self.task_status.setText(lines[-1][:220])

    def process_error(self,error):
        self.task_status.setText('后台任务无法启动：'+self.process.errorString())

    def completed(self,code,status):
        result_path=self.request.with_suffix('.result.json')
        self.project=ProjectStore().open(Path(self.project.directory)/'project.json')
        if result_path.exists():
            result=json.loads(result_path.read_text(encoding='utf-8'))
            if result['status']=='PASS':
                if result['action']=='reconstruct':
                    self.current_result=result['result']
                    self.mode_index=1
                self.task_status.setText('任务完成：'+result['action'])
            else:
                self.task_status.setText('官方流程失败：'+result['error'][:160])
                QMessageBox.warning(self,'官方流程失败',result['error'][:700]+'\n详细日志：'+result['job'])
        else:
            QMessageBox.warning(self,'后台任务失败',f'返回值 {code}。详细日志：{self.request.with_suffix(".log")}')
        self.render()

    def clear(self):
        self.image_view=None
        while self.content.count():
            w=self.content.takeAt(0).widget()
            if w:
                w.deleteLater()

    def render(self,*args):
        if self.project is not None and getattr(self,'rendered_project',None) is self.project:
            self.capture_workflow(getattr(self,'rendered_page',None))
        if self.navigation.currentRow()!=3:
            self.timer.stop()
        self.clear()
        p=self.project
        self.rendered_project=p
        self.rendered_page=self.navigation.currentRow()
        for index in range(1,self.navigation.count()):
            item=self.navigation.item(index)
            item.setFlags((item.flags()|Qt.ItemFlag.ItemIsEnabled) if p else (item.flags()&~Qt.ItemFlag.ItemIsEnabled))
        self.content.addWidget(label(STAGES[max(0,self.navigation.currentRow())]))
        if not p:
            self.content.addWidget(label('尚未创建或打开项目。请先新建项目、打开已有项目或明确打开示例项目。'))
            for text,fn in [('新建项目',self.new_project),('打开项目',self.open_project),('打开 HomeTank_004 示例项目',self.example)]:
                self.content.addWidget(self.button(text,fn))
            self.content.addStretch()
            return
        if p.calibration.get('fallback'):
            self.notice.setText('当前示例使用历史可追溯内外参，仅用于软件/工程流程展示，不代表物理精度验证通过。WASS 官方结果可能包含非水面结构；V1 无 ROI。')
            self.notice.setStyleSheet('color:#b00020')
        else:
            self.notice.setText('未完成物理精度验证。WASS 官方结果可能包含非水面结构；V1 未提供 ROI。')
            self.notice.setStyleSheet('')
        page=self.navigation.currentRow()
        if page==0:
            self.content.addWidget(label(f'项目：{p.name}\n目录：{p.directory}'))
            for key,title in [('calibration_left','LEFT 标定视频'),('calibration_right','RIGHT 标定视频'),
                              ('measurement_left','LEFT 测量视频'),('measurement_right','RIGHT 测量视频')]:
                self.content.addWidget(self.button('导入 '+title,lambda k=key:self.choose_video(k)))
                v=p.videos.get(key)
                if v:
                    self.content.addWidget(label(f'{v["path"]}\n{v["width"]}×{v["height"]}；{v["fps"]:.3f} FPS；{v["frame_count"]} 帧；{v["duration_s"]:.2f} s；音轨：{v["has_audio"]}；FOURCC：{v["codec_fourcc"]}'))
            self.content.addWidget(self.button('保存项目',self.save_project))
        elif page==1:
            if not all(k in p.videos for k in ['calibration_left','calibration_right']):
                self.content.addWidget(label('请先导入左右标定视频。'))
            row=QWidget(); layout=QHBoxLayout(row)
            pattern=self.tools.get('example',{}).get('pattern',[9,6])
            self.cols=QSpinBox();self.cols.setRange(2,30);self.cols.setValue(pattern[0])
            self.rows=QSpinBox();self.rows.setRange(2,30);self.rows.setValue(pattern[1])
            self.square=QDoubleSpinBox();self.square.setRange(.1,1000);self.square.setValue(20)
            self.interval=QSpinBox();self.interval.setRange(1,100000);self.interval.setValue(60)
            self.candidate_limit=QSpinBox();self.candidate_limit.setRange(10,10000);self.candidate_limit.setValue(120)
            for title,w in [('内角点列',self.cols),('行',self.rows),('格边长 mm',self.square),('抽帧间隔',self.interval)]:
                layout.addWidget(label(title));layout.addWidget(w)
            self.content.addWidget(row)
            self.content.addWidget(label('最多候选帧数'));self.content.addWidget(self.candidate_limit)
            self.content.addWidget(self.button('抽帧与官方棋盘检测',lambda:self.job('detect',dict(pattern=[self.cols.value(),self.rows.value()],interval=self.interval.value(),max_candidates=self.candidate_limit.value())),all(k in p.videos for k in ['calibration_left','calibration_right'])))
            candidate=Path(p.directory)/'candidate_frames.json'
            self.candidate_table=QTableWidget(0,4)
            self.candidate_table.setHorizontalHeaderLabels(['相机','帧编号','采用','检测预览路径'])
            if candidate.exists():
                candidates=json.loads(candidate.read_text(encoding='utf-8'))
                for camera,d in candidates.items():
                    for r in d['records']:
                        if not r['found']:
                            continue
                        n=self.candidate_table.rowCount();self.candidate_table.insertRow(n)
                        for c,value in [(0,camera),(1,str(r['index'])),(3,r['preview'])]:
                            self.candidate_table.setItem(n,c,QTableWidgetItem(value))
                        check=QTableWidgetItem();check.setCheckState(Qt.CheckState.Checked)
                        self.candidate_table.setItem(n,2,check)
                self.candidate_table.cellDoubleClicked.connect(lambda r,c:self.preview_candidate(r))
                self.content.addWidget(self.candidate_table,1)
                self.content.addWidget(label('双击候选行显示棋盘检测预览；勾选采用帧，不按 RMS 自动挑选。'))
            self.content.addWidget(self.button('运行 OpenCV 官方标定',self.calibrate,candidate.exists()))
            self.ext_time=QDoubleSpinBox();self.ext_time.setRange(0,100000);self.ext_time.setDecimals(3)
            self.ext_time.setValue(self.tools.get('example',{}).get('known_time_s',0))
            for field in ['cols','rows','square','interval','candidate_limit','ext_time']:
                if field in p.workflow:getattr(self,field).setValue(p.workflow[field])
            self.content.addWidget(label('外参匹配起始 LEFT 时间 s（连续三帧，间隔 0.1 s）'))
            self.content.addWidget(self.ext_time)
            self.content.addWidget(self.button('尝试 WASS 官方双目外参',lambda:self.job('extrinsics',dict(start_s=self.ext_time.value(),count=3)),bool(p.calibration and p.sync)))
            self.content.addWidget(self.button('加载已有可追溯 K/D/R/T',self.load_calibration))
            self.content.addWidget(self.button('加载示例历史内外参（显式 Fallback）',self.load_example_calibration))
            if p.calibration:
                cfg=Path(p.calibration['directory'])
                text=''
                for camera,index in [('LEFT',0),('RIGHT',1)]:
                    K=load_matrix(cfg/f'intrinsics_0{index}.xml');D=load_matrix(cfg/f'distortion_0{index}.xml')
                    info=(p.calibration.get('intrinsics') or {}).get(camera.lower(),{})
                    text+=f'{camera}\nK=\n{np.array2string(K,precision=5)}\nD={D.ravel()}\nRMS={info.get("rms","历史记录见来源报告")}；采用帧={len(info.get("selected_frames",[]))}\n'
                ext=p.calibration.get('extrinsics')
                if ext:
                    text+=f'R=\n{np.asarray(ext["R"])}\nT={ext["T"]}\n||T||={ext["translation_norm"]}（尺度约定见 provenance）'
                display=QPlainTextEdit(text);display.setReadOnly(True);display.setMinimumHeight(250)
                self.content.addWidget(display)
        elif page==2:
            ready=bool(p.sync and p.calibration.get('extrinsics'))
            if not ready:self.content.addWidget(label('请先导入测量视频、完成同步并获得有效双目外参。'))
            self.ref_time=QDoubleSpinBox();self.ref_time.setRange(0,100000);self.ref_time.setDecimals(3)
            self.ref_time.setValue(self.tools.get('example',{}).get('known_time_s',0))
            self.baseline=QDoubleSpinBox();self.baseline.setRange(.001,1000);self.baseline.setDecimals(6)
            self.baseline.setValue(getattr(self,'baseline_value',self.tools.get('example',{}).get('baseline_m',1)))
            self.center_x=QDoubleSpinBox();self.center_y=QDoubleSpinBox();self.area_size=QDoubleSpinBox()
            for w in [self.center_x,self.center_y]:
                w.setRange(-10000,10000);w.setDecimals(6)
            self.center_x.setValue(-.03);self.center_y.setValue(.22)
            self.area_size.setRange(.001,10000);self.area_size.setDecimals(6);self.area_size.setValue(.24)
            for field in ['ref_time','baseline','center_x','center_y','area_size']:
                if field in p.workflow:getattr(self,field).setValue(p.workflow[field])
            for title,w in [('参考 LEFT 时间 s',self.ref_time),('实测基线 m（不可凭结果调尺度）',self.baseline),
                            ('官方网格中心 X/m',self.center_x),('中心 Y/m',self.center_y),('面积边长 m',self.area_size)]:
                self.content.addWidget(label(title));self.content.addWidget(w)
            self.content.addWidget(label('参考时刻由用户选择，不自动认定为静水。网格范围为官方配置，不是水面 ROI；示例默认参数不适用于任意新相机。'))
            self.content.addWidget(self.button('官方重建参考帧并建立参考面',self.establish_reference,ready))
            self.content.addWidget(self.button('加载本软件已保存的官方参考面',self.load_reference, bool(p.calibration)))
            if p.reference:
                display=QPlainTextEdit('参考面：'+json.dumps(p.reference,ensure_ascii=False,indent=2));display.setReadOnly(True)
                self.content.addWidget(display)
        elif page==3:
            if not all(k in p.videos for k in ['measurement_left','measurement_right']):
                self.content.addWidget(label('请先导入左右测量视频。'))
            elif not p.sync:self.content.addWidget(label('请先运行左右视频同步。'))
            elif not p.reference:self.content.addWidget(label('请先建立参考水面，再重建当前帧。'))
            self.content.addWidget(self.button('运行 wass_lowcost 官方 TLCC 同步',lambda:self.job('sync',dict(window_end=30,wind_filter=True)),all(k in p.videos for k in ['measurement_left','measurement_right'])))
            if p.sync:
                self.content.addWidget(label(f'同步 offset：RIGHT−LEFT={p.sync["right_minus_left_s"]:+.3f} s；方法：{p.sync["method"]}；音频同步不等于曝光同步。'))
            self.point_info=label('鼠标移入本帧官方画面查询 XYZ/H。')
            images=QWidget();layout=QHBoxLayout(images)
            self.image_view=ImageView(self.point_info)
            layout.addWidget(self.image_view,1);layout.addWidget(self.point_info)
            self.content.addWidget(images,1)
            controls=QWidget();row=QHBoxLayout(controls)
            row.addWidget(self.button('上一帧',lambda:self.seek(self.frame_index-1),bool(p.sync)))
            self.play_button=self.button('暂停' if self.timer.isActive() else '播放',self.play_pause,bool(p.sync))
            row.addWidget(self.play_button)
            row.addWidget(self.button('下一帧',self.next_frame,bool(p.sync)))
            self.timeline=QSlider(Qt.Orientation.Horizontal)
            self.timeline.setRange(0,max(0,p.videos.get('measurement_left',{}).get('frame_count',1)-1))
            self.timeline.setValue(getattr(self,'frame_index',0));self.timeline.valueChanged.connect(lambda v:self.guard(lambda:self.seek(v)))
            row.addWidget(self.timeline,1)
            row.addWidget(label('LEFT 帧'))
            self.frame_selector=QSpinBox()
            self.frame_selector.setRange(0,self.timeline.maximum())
            self.frame_selector.setValue(getattr(self,'frame_index',0))
            self.frame_selector.setKeyboardTracking(False)
            self.frame_selector.valueChanged.connect(lambda v:self.guard(lambda:self.seek(v)))
            row.addWidget(self.frame_selector)
            self.content.addWidget(controls)
            self.time_text=label('');self.content.addWidget(self.time_text)
            self.mode=QComboBox();self.mode.addItems(['原始 LEFT/RIGHT 浏览（无映射）','本帧官方参考坐标原图（可查询）','本帧官方参考面高度叠加（可查询）','本帧官方 CLI 叠加（居中约定）'])
            self.mode.setCurrentIndex(getattr(self,'mode_index',0))
            self.mode.currentIndexChanged.connect(self.display_current)
            self.content.addWidget(self.mode)
            self.reconstruct_button=self.button('重建当前帧（官方 WASS）',lambda:self.job('reconstruct',dict(left_time=self.current_time(),baseline_m=p.reference.get('baseline_m'))),bool(p.sync and p.reference and p.calibration.get('extrinsics') and not self.timer.isActive()))
            self.content.addWidget(self.reconstruct_button)
            self.guard(self.display_current)
        else:
            if not self.current_result:self.content.addWidget(label('当前帧尚无成功官方结果，请先在视频测量页重建。'))
            self.content.addWidget(self.button('查看当前帧 3D 点云',self.cloud,bool(self.current_result)))
            self.content.addWidget(self.button('导出当前帧官方结果',self.export,bool(self.current_result)))
            self.content.addWidget(self.button('查看详细任务日志',self.logs))
            if self.current_result:
                self.content.addWidget(label(json.dumps(self.current_result,ensure_ascii=False,indent=2)[:3500]))
        if page not in (1,3):
            self.content.addStretch()

    def preview_candidate(self,row):
        path=self.candidate_table.item(row,3).text()
        w=QWidget(self,Qt.WindowType.Window);w.setWindowTitle('官方棋盘检测预览');w.resize(1000,700)
        layout=QVBoxLayout(w);view=ImageView(label(''));layout.addWidget(view);view.display(path);w.show()
        self.preview_window=w

    def calibrate(self):
        selected={'left':[],'right':[]}
        for row in range(self.candidate_table.rowCount()):
            if self.candidate_table.item(row,2).checkState()==Qt.CheckState.Checked:
                selected[self.candidate_table.item(row,0).text()].append(int(self.candidate_table.item(row,1).text()))
        self.job('calibrate',dict(square_m=self.square.value()/1000,selected=selected))

    def load_example_calibration(self):
        e=self.tools['example']
        self.job('load_calibration',dict(source=e['historical_calibration'],provenance_record=dict(
            experiment=e['source_experiment'],commit_report=e['source_commit_report'],
            stereo_config=e.get('stereo_config'),image_size_wh=e['image_size_wh'],label='示例/Fallback，历史可追溯内外参')))

    def load_calibration(self):
        directory=QFileDialog.getExistingDirectory(self,'选择包含 WASS 标定 XML 与 provenance.json 的目录')
        if directory:
            record=json.loads((Path(directory)/'provenance.json').read_text(encoding='utf-8'))
            if not all(record.get(k) for k in ['experiment','commit_report','image_size_wh']):
                raise ValueError('缺少可追溯实验、commit/report 或图像尺寸 image_size_wh')
            self.job('load_calibration',dict(source=directory,provenance_record=record))

    def establish_reference(self):
        self.baseline_value=self.baseline.value()
        self.job('reference',dict(left_time=self.ref_time.value(),baseline_m=self.baseline_value,
                                 area=[self.center_x.value(),self.center_y.value(),self.area_size.value(),256]))

    def load_reference(self):
        path,_=QFileDialog.getOpenFileName(self,'选择已保存的官方 reference.json','','参考结果 (*.json)')
        if path:
            self.job('load_reference',dict(path=path))

    def current_time(self):
        if not self.project:
            return 0
        source=self.sources.get('left')
        if source and getattr(source,'last_index',None)==getattr(self,'frame_index',0):
            return source.last_time_s
        return getattr(self,'frame_index',0)/self.project.videos.get('measurement_left',{}).get('fps',1)

    def play_pause(self):
        if self.timer.isActive():
            self.timer.stop()
        else:
            self.timer.start(max(1,round(1000/self.project.videos['measurement_left']['fps'])))
        self.play_button.setText('暂停' if self.timer.isActive() else '播放')
        self.reconstruct_button.setEnabled(bool(self.project.reference and not self.timer.isActive() and not self.busy()))

    def seek(self,index,check_cache=True):
        self.timer.stop()
        self.frame_index=max(0,min(index,self.project.videos['measurement_left']['frame_count']-1))
        self.current_result=None
        self.mode_index=0
        if self.navigation.currentRow()==3:
            self.mode.setCurrentIndex(0)
            for control in [self.timeline,self.frame_selector]:
                control.blockSignals(True)
                control.setValue(self.frame_index)
                control.blockSignals(False)
            self.play_button.setText('播放')
            self.reconstruct_button.setEnabled(bool(self.project.reference and not self.busy()))
            self.display_current()
            if check_cache and self.project.reference:
                key=frame_identity(self.project,self.current_time(),self.project.reference['baseline_m'])
                cached=ResultCache().lookup(self.project,key)
                if cached:
                    self.current_result=cached;self.mode.setCurrentIndex(1)
                    self.task_status.setText('已读取当前帧自身缓存；未重新运行 WASS。')

    def next_frame(self):
        playing=self.timer.isActive()
        previous=getattr(self,'frame_index',0)
        self.seek(previous+1,check_cache=not playing)
        if playing and self.frame_index>previous:
            self.play_pause()

    def display_current(self,*args):
        if self.image_view is None or not self.project.sync:
            return
        self.mode_index=self.mode.currentIndex()
        result=self.current_result
        t=self.current_time();right=t+self.project.sync['right_minus_left_s']
        right_idx=round(right*self.project.videos['measurement_right']['fps'])
        self.time_text.setText(f'LEFT 时间 {t:.3f} s；LEFT 帧 {self.frame_index}；RIGHT 对应帧约 {right_idx}；RIGHT 时间 {right:.3f} s（VFR 索引近似，重建按原 PTS 抽帧）')
        if self.mode_index and result:
            mapping=None
            if self.mode_index in (1,2):
                mapping=loadmat(result['files']['mapping'],variable_names=['px_2_3D'])['px_2_3D']
            key={1:'image',2:'overlay',3:'official_centered_overlay'}[self.mode_index]
            self.image_view.display(result['files'][key],mapping)
            return
        if self.mode_index:
            self.point_info.setText('当前帧尚无成功官方结果，不显示其他帧或 Golden Demo。')
        if right<0:
            self.point_info.setText('当前时刻没有同步 RIGHT 帧，请向后浏览。')
            return
        frames=[]
        for camera in ['left','right']:
            if camera not in self.sources:
                self.sources[camera]=VideoAdapter(self.project.videos['measurement_'+camera]['path'])
            if camera=='left':
                frames.append(self.sources[camera].seek(self.frame_index))
                t=self.current_time();right=t+self.project.sync['right_minus_left_s']
                if right<0:
                    self.point_info.setText('当前时刻没有同步 RIGHT 帧，请向后浏览。');return
            else:
                if right>=self.sources[camera].count/self.sources[camera].fps:
                    self.timer.stop();self.point_info.setText('同步视频已结束。');return
                frames.append(self.sources[camera].seek_time(right))
                right_idx=self.sources[camera].last_index
        self.time_text.setText(f'LEFT 时间 {t:.6f} s；LEFT 帧 {self.frame_index}；RIGHT 帧 {right_idx}；RIGHT 目标时间 {right:.6f} s（按原视频时间戳）')
        # Side-by-side preview only; never fed into WASS or queried as pixels.
        height=min(f.shape[0] for f in frames)
        preview=[cv2.resize(f,(round(f.shape[1]*height/f.shape[0]),height)) for f in frames]
        self.image_view.display(np.hstack(preview))

    def cloud(self):
        p=self.current_result['files']['ply']
        vertices=PlyData.read(p)['vertex'].data
        xyz=np.column_stack([vertices[n] for n in ('x','y','z')])
        shown=xyz[::max(1,int(np.ceil(len(xyz)/30000)))]
        fig=Figure();ax=fig.add_subplot(111,projection='3d')
        ax.scatter(*shown.T,c=shown[:,2],s=.8)
        ax.set_xlabel('X（WASS 坐标）');ax.set_ylabel('Y');ax.set_zlabel('Z（非波高）')
        def zoom(event):
            factor=.8 if event.button=='up' else 1.25
            for get,setter in [(ax.get_xlim3d,ax.set_xlim3d),(ax.get_ylim3d,ax.set_ylim3d),(ax.get_zlim3d,ax.set_zlim3d)]:
                lo,hi=get();center=(lo+hi)/2;half=(hi-lo)*factor/2;setter(center-half,center+half)
            event.canvas.draw_idle()
        fig.canvas.mpl_connect('scroll_event',zoom)
        w=QWidget(self,Qt.WindowType.Window);w.setWindowTitle('当前帧官方 WASS 点云');w.resize(1000,750)
        layout=QVBoxLayout(w)
        layout.addWidget(label(f'官方点数 {len(xyz)}；显示 {len(shown)}。仅对显示数据抽样，原始 WASS 重建结果未修改。可能包含非水面结构。'))
        canvas=FigureCanvasQTAgg(fig);canvas.mpl_connect('scroll_event',zoom);layout.addWidget(canvas)
        w.show();self.cloud_window=w

    def export(self):
        path=QFileDialog.getExistingDirectory(self,'选择空目录导出当前帧结果')
        if path:
            ExportService().run(self.current_result,path)
            if self.image_view is not None:
                self.image_view.grab().save(str(Path(path)/'current_display.png'))
            else:
                self.grab().save(str(Path(path)/'current_display.png'))
            self.task_status.setText('已导出：'+path)

    def logs(self):
        path=Path(self.project.directory)/'jobs'
        w=QWidget(self,Qt.WindowType.Window);w.setWindowTitle('详细任务日志');w.resize(1100,700);layout=QVBoxLayout(w)
        layout.addWidget(label(str(path)))
        files=sorted(path.rglob('*.log'),key=lambda p:p.stat().st_mtime,reverse=True)
        chooser=QComboBox();chooser.addItems([str(f.relative_to(path)) for f in files]);layout.addWidget(chooser)
        editor=QPlainTextEdit();editor.setReadOnly(True);layout.addWidget(editor)
        def read(index):
            if files:
                editor.setPlainText(files[index].read_text(encoding='utf-8',errors='replace'))
        chooser.currentIndexChanged.connect(read);read(0)
        w.show();self.log_window=w

    def closeEvent(self,event):
        if self.busy():
            QMessageBox.information(self,'任务进行中','请等待官方任务结束后关闭，避免留下不完整结果。')
            event.ignore();return
        self.timer.stop()
        if self.project:
            self.capture_workflow()
            try:ProjectService(self.tools).save(self.project)
            except Exception as error:
                QMessageBox.warning(self,'项目保存失败',str(error));event.ignore();return
        for v in self.sources.values():
            v.close()
        event.accept()


def settings():
    if getattr(sys,'frozen',False):
        root=Path(sys._MEIPASS)/'production_source'
        config=Path(sys.executable).parent/'config/production_toolchain.json'
    else:
        root=Path(__file__).resolve().parents[1]
        config=root.parent/'config/production_toolchain.json'
    return json.loads(config.read_text(encoding='utf-8')),root


def main():
    app=QApplication(sys.argv);app.setFont(QFont('Microsoft YaHei',10))
    try:
        tools,root=settings()
        w=ProductionWindow(tools,root);w.show()
    except Exception as error:
        QMessageBox.critical(None,'启动失败',str(error));return 1
    return app.exec()
