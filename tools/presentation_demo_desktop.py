"""Native Qt read-only presentation. No browser/server/reconstruction imports."""
import json
import math
from pathlib import Path
import sys
import numpy as np
from PySide6.QtCore import Qt,QPointF,QEvent
from PySide6.QtGui import QPixmap,QPainter,QFont,QMouseEvent
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,
    QLabel,QListWidget,QComboBox,QGraphicsView,QGraphicsScene,QMessageBox,QToolTip,QSpinBox)
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
import matplotlib
import presentation_demo_data as data

matplotlib.rcParams['font.sans-serif']=['Microsoft YaHei','SimHei','DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus']=False
PAGES=['项目概览','双目输入','处理流程','三维点云','水面高度图','原图叠加','像素高度查询','结果与验证边界']


def query_text(mapping,u,v):
    result=data.query(mapping,u,v)
    if result['provenance']=='UNSUPPORTED':
        return f'像素坐标：({u}, {v})\n该像素暂无有效三维高度数据\n数据来源：无有效数据'
    return (f'像素坐标：({u}, {v})\nX：{result["X_m"]*1000:.3f} mm\n'
            f'Y：{result["Y_m"]*1000:.3f} mm\nZ：{result["Z_m"]*1000:.3f} mm\n'
            f'相对平均水面高度：{result["H_mm"]:+.3f} mm\n数据来源：未知（官方规则网格估计）')


class PixelView(QGraphicsView):
    def __init__(self,path,mapping=None,status=None):
        super().__init__()
        pixmap=QPixmap(str(data.require(path)))
        if pixmap.isNull():
            raise data.AssetError(f'图像无法读取：{path}')
        if mapping is not None and mapping.shape!=(pixmap.height(),pixmap.width(),3):
            raise data.AssetError('图像与对应帧 MAT 尺寸不一致，停止查询')
        self.mapping=mapping
        self.status=status
        self.last_pixel=None
        scene=QGraphicsScene(self)
        self.setScene(scene)
        self.item=scene.addPixmap(pixmap)
        scene.setSceneRect(self.item.boundingRect())
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setMinimumHeight(180)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        self.fitInView(self.item,Qt.AspectRatioMode.KeepAspectRatio)

    def scene_pixel(self,position):
        p=self.mapToScene(position)
        u,v=math.floor(p.x()),math.floor(p.y())
        if not self.sceneRect().contains(p):
            return None
        return u,v

    def mouseMoveEvent(self,event):
        pixel=self.scene_pixel(event.position().toPoint())
        if self.mapping is not None and pixel is not None:
            self.last_pixel=pixel
            text=query_text(self.mapping,*pixel)
            QToolTip.showText(event.globalPosition().toPoint(),text,self)
            if self.status is not None:
                self.status.setText(text.replace('\n','   '))
        else:
            QToolTip.hideText()
        super().mouseMoveEvent(event)

    def wheelEvent(self,event):
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        factor=1.2 if event.angleDelta().y()>0 else 1/1.2
        self.scale(factor,factor)


def label(text):
    widget=QLabel(text)
    widget.setWordWrap(True)
    widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return widget


class DesktopWindow(QMainWindow):
    def __init__(self,record,root,dialogs=True):
        super().__init__()
        self.record=record
        self.root=Path(root)
        self.dialogs=dialogs
        self.error=None
        self.current_view=None
        self.setWindowTitle('双目水面三维测量演示系统')
        self.resize(1380,920)
        central=QWidget()
        self.setCentralWidget(central)
        vertical=QVBoxLayout(central)
        title=label('双目水面三维测量演示系统')
        title.setStyleSheet('font-size:26px;font-weight:bold')
        vertical.addWidget(title)
        vertical.addWidget(label('基于 Vieira 2025 / WASS 的端到端工程可行性演示'))
        warning=label('演示版本：尚未完成物理精度验证\n当前结果用于验证工程链路和可视化能力，不代表已经达到厘米级波高测量精度。')
        warning.setStyleSheet('background:#fff2cc;padding:12px;color:#725900')
        vertical.addWidget(warning)
        horizontal=QHBoxLayout()
        vertical.addLayout(horizontal,1)
        left=QVBoxLayout()
        horizontal.addLayout(left)
        self.navigation=QListWidget()
        self.navigation.addItems(PAGES)
        self.navigation.setFixedWidth(190)
        left.addWidget(self.navigation)
        left.addWidget(label('当前帧'))
        self.frame=QComboBox()
        self.frame.addItems([f'第{i+1}帧' for i in range(5)])
        left.addWidget(self.frame)
        self.body=QWidget()
        self.content=QVBoxLayout(self.body)
        horizontal.addWidget(self.body,1)
        self.navigation.currentRowChanged.connect(self.render)
        self.frame.currentIndexChanged.connect(self.render)
        self.navigation.setCurrentRow(0)

    def clear(self):
        self.current_view=None
        while self.content.count():
            widget=self.content.takeAt(0).widget()
            if widget is not None:
                widget.deleteLater()

    def image(self,path,mapping=None):
        status=label('将鼠标移到图像上，无需点击，即可显示对应像素的三维高度。') if mapping is not None else None
        view=PixelView(path,mapping,status)
        self.content.addWidget(view,1)
        if status is not None:
            self.content.addWidget(status)
            self.current_view=view
        return view

    def render(self,*unused):
        self.clear()
        self.error=None
        index=self.frame.currentIndex()
        page=PAGES[max(0,self.navigation.currentRow())]
        paths=data.frame_paths(self.root,index)
        metrics=self.record['frame_metrics'][index]
        self.content.addWidget(label(f'{page} · HomeTank_004 · 第{index+1}帧'))
        try:
            if page=='项目概览':
                self.content.addWidget(label('冻结样例：5 帧\nWASS XYZ：681,678 点\n端到端工程流程：已跑通\n物理精度：尚未验证\n黄金样例：冻结\n直接双目来源点网格占格率：18.93%–20.55%（不是全幅水面图像覆盖率）'))
                self.image(paths['overlay'])
            elif page=='双目输入':
                row=QWidget()
                layout=QHBoxLayout(row)
                for key,title in [('left','左相机 cam0'),('right','右相机 cam1')]:
                    column=QWidget()
                    col=QVBoxLayout(column)
                    col.addWidget(label(title))
                    col.addWidget(PixelView(paths[key]),1)
                    layout.addWidget(column)
                self.content.addWidget(row,1)
                self.content.addWidget(label('同步状态：冻结音频互相关同步帧；未独立验证曝光同步。'))
            elif page=='处理流程':
                self.content.addWidget(label('双目视频\n↓\n时间同步\n↓\n相机标定（演示备用参数，来源可追溯的历史 K/D/R/T）\n↓\nWASS 双目重建\n↓\n三维点云 / 网格\n↓\n平均水面基准\n↓\n规则水面网格\n↓\nNetCDF 数据\n↓\n原图叠加\n↓\n像素 → XYZ → 高度\n\n状态：五帧已完成；尚未完成物理验证。新自动外参已执行但未采用。'))
            elif page=='三维点云':
                xyz,total=data.point_cloud(paths['ply'],30000)
                self.content.addWidget(label(f'三维水面点云：原始点数 {total:,}；显示点数 {len(xyz):,}\n仅对显示点进行抽样，原始 WASS 重建结果未改变。鼠标拖动可旋转，滚轮可缩放。'))
                figure=Figure()
                ax=figure.add_subplot(111,projection='3d')
                ax.scatter(xyz[:,0],xyz[:,1],xyz[:,2],s=.5,c=xyz[:,2],cmap='viridis')
                ax.set(xlabel='X（基线单位）',ylabel='Y（基线单位）',zlabel='Z（基线单位）')
                canvas=FigureCanvasQTAgg(figure)
                def zoom(event):
                    factor=.85 if event.button=='up' else 1/.85
                    for get,setter in [(ax.get_xlim3d,ax.set_xlim3d),(ax.get_ylim3d,ax.set_ylim3d),(ax.get_zlim3d,ax.set_zlim3d)]:
                        lo,hi=get()
                        center=(lo+hi)/2
                        setter(center+(lo-center)*factor,center+(hi-center)*factor)
                    canvas.draw_idle()
                canvas.mpl_connect('scroll_event',zoom)
                self.content.addWidget(canvas,1)
                self.content.addWidget(label('冻结 PLY 为 WASS 相机坐标，点云包含未经水面分类的来源点；不等于平均水面高度。'))
            elif page=='水面高度图':
                x,y,z=data.height_grid(self.root/'gridding/gridded.nc',index)
                figure=Figure(layout='constrained')
                ax=figure.add_subplot(111)
                mesh=ax.pcolormesh(x,y,z,cmap='RdBu',shading='auto')
                ax.set(xlabel='X（mm）',ylabel='Y（mm）',title='水面相对高度图')
                figure.colorbar(mesh,ax=ax,label='相对平均水面高度 / mm')
                self.content.addWidget(FigureCanvasQTAgg(figure),1)
                self.content.addWidget(label(f"直接双目来源点占格：{metrics['source_supported_grid_percent']:.2f}%\n凸包内插值 / 估计：{metrics['interpolated_inside_hull_percent']:.2f}%；凸包外外推 / 估计：{metrics['extrapolated_outside_hull_percent']:.2f}%\n规则网格 100% 有数值不代表 100% 由双目直接观测；无逐格支撑分类。"))
            elif page in ('原图叠加','像素高度查询'):
                self.content.addWidget(label('查询坐标：WASS 去畸变计算左图 cam0，2400×1350。不是原始视频坐标，也不是右图 cam1。滚轮缩放，拖动平移。'))
                mapping=data.pixel_mapping(paths['mat'])
                self.image(paths['overlay'] if page=='原图叠加' else paths['image'],mapping)
                self.content.addWidget(label('XYZ 为平均水面坐标；Z 与 H 一致。来源方法为官方规则网格估计，逐像素支撑类别未知。背景不补值；全幅叠加含非水面范围。'))
            else:
                self.content.addWidget(label('当前已经证明\n真实双目视频可以进入 WASS；可以生成真实 XYZ、规则水面网格、NetCDF、原图叠加及像素高度查询；固定五帧工程链路可运行。\n\n当前尚未证明\n厘米级精度；真实波高绝对正确；全水面均为直接观测；严格无备用参数的 Vieira 2025 复现；人眼趋势与跨帧稳定性。\n\n下一步：可靠原始标定、曝光同步、基线和独立物理验证。'))
        except Exception as error:
            self.error=str(error)
            self.content.addWidget(label(f'冻结演示文件读取失败：{error}'))
            if self.dialogs:
                QMessageBox.warning(self,'演示文件不可用',str(error))


def load_settings():
    if getattr(sys,'frozen',False):
        bundle=Path(sys._MEIPASS)
        data.ASSETS=bundle/'presentation_assets/vieira2025_end_to_end_demo'
        config=Path(sys.executable).parent/'config/presentation_demo.json'
    else:
        config=Path(__file__).resolve().parents[1]/'config/presentation_demo.json'
    settings=json.loads(data.require(config).read_text(encoding='utf8'))
    root=Path(settings['golden_demo_root'])
    if not root.is_dir():
        raise data.AssetError(f'未找到 Golden Demo 数据目录\n{root}')
    return data.manifest(),root


def test_mouse_move(view,point):
    # Deterministic Qt input for offscreen regression; physical EXE verified separately.
    event=QMouseEvent(QEvent.Type.MouseMove,QPointF(point),QPointF(view.viewport().mapToGlobal(point)),
                      Qt.MouseButton.NoButton,Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(view.viewport(),event)
    QApplication.processEvents()


def smoke(window,record,root):
    from PySide6.QtTest import QTest
    checks={'pages':[],'frames':[],'spot_checks':[]}
    for i,page in enumerate(PAGES):
        window.navigation.setCurrentRow(i)
        QApplication.processEvents()
        assert window.error is None,window.error
        checks['pages'].append(page)
    window.navigation.setCurrentRow(6)
    for i in range(5):
        window.frame.setCurrentIndex(i)
        QApplication.processEvents()
        assert window.error is None,window.error
        view=window.current_view
        scene=QPointF(1000.5,1050.5)
        point=view.mapFromScene(scene)
        # Display event tests use the exact viewport->scene result, never screen pixels.
        actual=view.scene_pixel(point)
        test_mouse_move(view,point)
        QApplication.processEvents()
        assert view.last_pixel==actual
        checks['frames'].append({'index':i,'hover_pixel':actual,'text':query_text(view.mapping,*actual)})
    window.frame.setCurrentIndex(0)
    QApplication.processEvents()
    mapping=window.current_view.mapping
    for u,v in [(1000,1050),(1100,1000),(1000,1000)]:
        result=data.query(mapping,u,v)
        checks['spot_checks'].append(result)
    checks['frozen_hash_count']=data.verify_frozen(dict(record,outputs=dict(record['outputs'],root=str(root))))
    checks.update(status='PASS',wass_executions=0,browser_used=False,http_server_used=False)
    return checks


def main():
    smoke_path=None
    if '--smoke-report' in sys.argv:
        smoke_path=Path(sys.argv[sys.argv.index('--smoke-report')+1])
        import os
        os.environ['QT_QPA_PLATFORM']='offscreen'
    app=QApplication(sys.argv)
    app.setFont(QFont('Microsoft YaHei',11))
    try:
        record,root=load_settings()
        window=DesktopWindow(record,root,dialogs=smoke_path is None)
        window.show()
        if smoke_path is not None:
            QApplication.processEvents()
            try:
                result=smoke(window,record,root)
            except Exception as error:
                result={'status':'FAIL','error':str(error)}
            smoke_path.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf8')
            return 0 if result['status']=='PASS' else 1
    except Exception as error:
        QMessageBox.critical(None,'演示数据不可用',str(error))
        return 1
    return app.exec()


if __name__=='__main__':
    raise SystemExit(main())
