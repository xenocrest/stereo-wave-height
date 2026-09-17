"""Application services: project identity, CLI orchestration, no new models."""
import importlib.metadata
import json
from pathlib import Path
import shutil
import uuid
import numpy as np
from .storage import ProjectStore, ResultCache, digest, identity, write_json
from .adapters import (OfficialRunner, VideoAdapter, OpenCVCalibrationAdapter, WassLowcostAdapter,
                       WassAdapter, WassGridSurfaceAdapter, WassNcPlotAdapter, load_matrix)


def source_snapshot(tools):
    files = []
    for directory in [Path(tools['wass_source']), Path(tools['wass_lowcost'])]:
        files.extend(p for p in directory.rglob('*') if p.is_file() and p.suffix in ('.cpp','.hpp','.h','.py'))
    site = Path(tools['python']).parents[1]/'Lib/site-packages'
    for name in ['wassgridsurface','wassncplot']:
        files.extend((site/name).rglob('*.py'))
    return {str(p):digest(p) for p in sorted(files)}


def provenance(tools):
    import cv2
    import subprocess
    result = dict(paths={k:v for k,v in tools.items() if k not in ('example',)}, OpenCV=cv2.__version__)
    for package in ['wassgridsurface','wassncplot']:
        result[package] = importlib.metadata.version(package)
    for name, executable in [('FFmpeg',tools['ffmpeg']),('WASS',str(Path(tools['wass_bin'])/'wass_stereo.exe'))]:
        argv = [executable, '-version'] if name=='FFmpeg' else [executable]
        p = subprocess.run(argv, capture_output=True, creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        result[name] = (p.stdout+p.stderr).decode('utf-8',errors='replace')[:1000]
        result[name+'_sha256'] = digest(executable)
    result['wass_lowcost_source_sha256'] = digest(Path(tools['wass_lowcost'])/'wass_sync.py')
    result['core_source_hashes'] = source_snapshot(tools)
    return result


class ProjectService:
    def __init__(self, tools):
        self.tools = tools
        self.store = ProjectStore()

    def create(self, directory, name):
        if not str(Path(directory).resolve()).isascii():
            raise ValueError('本机官方 WASS/NetCDF 工具要求英文项目输出路径，请选择例如 D:/wave-projects/test01。项目名称仍可使用中文。')
        p = self.store.create(directory,name)
        p.toolchain = provenance(self.tools)
        self.store.save(p)
        return p

    def input(self, project, key, filename):
        v = VideoAdapter(filename)
        try:
            record = v.metadata(self.tools['ffmpeg'])
        finally:
            v.close()
        record['sha256'] = digest(filename)
        project.videos[key] = record
        if key.startswith('measurement'):
            project.sync = {}
            project.reference = {}
        else:
            project.calibration = {}
            project.reference = {}
        self.store.save(project)


class BaseService:
    def __init__(self, project, tools, notify=print):
        self.project,self.tools,self.notify = project,tools,notify
        self.root = Path(project.directory)
        self.job = self.root/'jobs'/uuid.uuid4().hex
        self.job.mkdir(parents=True,exist_ok=False)
        self.runner = OfficialRunner(self.job/'logs',notify)

    def save(self):
        ProjectStore().save(self.project)
        write_json(self.job/'calls.json',self.runner.calls)

    def config(self):
        if not self.project.calibration.get('directory'):
            raise ValueError('尚未取得相机内参')
        return Path(self.project.calibration['directory'])


class CalibrationService(BaseService):
    def detect(self, pattern, interval, max_candidates):
        results = {}
        for camera in ['left','right']:
            path = self.project.videos['calibration_'+camera]['path']
            results[camera] = OpenCVCalibrationAdapter().detect(path,self.job/camera,pattern,interval,max_candidates,self.notify)
        write_json(self.root/'candidate_frames.json',results)
        return results

    def calibrate(self, square_m, selected=None):
        detections = json.loads((self.root/'candidate_frames.json').read_text(encoding='utf-8'))
        cfg = self.job/'config'
        cfg.mkdir()
        results = {}
        for i,camera in enumerate(['left','right']):
            d = Path(detections[camera]['records'][0]['preview']).parent/'detections.json'
            results[camera] = OpenCVCalibrationAdapter().calibrate(d,self.job/camera,square_m,
                                      None if selected is None else selected[camera])
            shutil.copy2(self.job/camera/'intrinsics.xml',cfg/f'intrinsics_0{i}.xml')
            shutil.copy2(self.job/camera/'distortion.xml',cfg/f'distortion_0{i}.xml')
        if results['left']['image_size_wh'] != results['right']['image_size_wh']:
            raise ValueError('左右标定图像尺寸不同，当前 WASS 工作流不支持')
        self.official_config(cfg)
        self.project.calibration = dict(directory=str(cfg), identity=calibration_identity(cfg),
                                        intrinsics=results, extrinsics=None, fallback=False)
        self.project.reference = {}
        self.save()
        return self.project.calibration

    def official_config(self, cfg):
        for name, exe in [('matcher_config.txt','wass_match.exe'),('stereo_config.txt','wass_stereo.exe')]:
            self.runner.run('generate_'+name,[Path(self.tools['wass_bin'])/exe,'--genconfig'],cwd=cfg)
        (cfg/'prepare_config.txt').write_text('# Official defaults\n',encoding='ascii')
        # Official output switch, not a reconstruction/model parameter change.
        with (cfg/'stereo_config.txt').open('a',encoding='ascii') as f:
            f.write('\nSAVE_AS_PLY=true\n')

    def load_existing(self, source, provenance_record):
        required = ['intrinsics_00.xml','distortion_00.xml','intrinsics_01.xml','distortion_01.xml','ext_R.xml','ext_T.xml']
        source = Path(source)
        if not provenance_record.get('image_size_wh'):
            raise ValueError('已有标定缺少图像尺寸记录；不能猜测它适用于当前分辨率')
        cfg = self.job/'config'
        cfg.mkdir()
        for name in required:
            load_matrix(source/name)
            shutil.copy2(source/name,cfg/name)
        self.official_config(cfg)
        for name in ['matcher_config.txt','stereo_config.txt','prepare_config.txt']:
            if (source/name).exists():
                shutil.copy2(source/name,cfg/name)
        # Explicit existing official configuration chosen by the user/example.
        selected_config = provenance_record.get('stereo_config')
        if selected_config:
            shutil.copy2(selected_config,cfg/'stereo_config.txt')
        with (cfg/'stereo_config.txt').open('a',encoding='ascii') as f:
            f.write('\nSAVE_AS_PLY=true\n')
        self.project.calibration = dict(directory=str(cfg), identity=calibration_identity(cfg), fallback=True,
                                        provenance=dict(provenance_record,source=str(source),validated=False,
                                                        source_hashes={n:digest(source/n) for n in required}),
                                        extrinsics=self.matrices(cfg), intrinsics=None,
                                        image_size_wh=provenance_record['image_size_wh'])
        self.project.reference = {}
        self.save()
        return self.project.calibration

    @staticmethod
    def matrices(cfg):
        R,T = load_matrix(Path(cfg)/'ext_R.xml'),load_matrix(Path(cfg)/'ext_T.xml')
        return dict(R=R.tolist(),T=T.reshape(-1).tolist(),translation_norm=float(np.linalg.norm(T)),
                    scale='WASS unit-baseline extrinsics; metric baseline supplied separately')

    def autocalibrate(self, start_s, count=3, step_s=0.1):
        cfg = self.config()
        adapter = WassAdapter(self.tools,self.runner)
        paths = []
        for index in range(count):
            left,right,_,_ = extract_pair(self.project,self.tools,self.runner,self.job/f'pair_{index}',start_s+index*step_s)
            wd = self.job/f'{index:06d}_wd'
            adapter.prepare(cfg,wd,left,right)
            adapter.match(cfg,wd)
            paths.append(wd)
        listing = self.job/'workspaces.txt'
        listing.write_text('\n'.join(map(str,paths))+'\n',encoding='utf-8')
        adapter.autocalibrate(listing)
        ext = self.matrices(paths[0])
        # Do not rewrite or swap any R/T. Copy the exact official matrices.
        for name in ['ext_R.xml','ext_T.xml']:
            shutil.copy2(paths[0]/name,cfg/name)
        self.project.calibration.update(identity=calibration_identity(cfg),extrinsics=ext,
                    extrinsics_provenance=dict(method='WASS autocalibrate',workspaces=list(map(str,paths)),
                                              calls=self.runner.calls,validated=False))
        self.project.reference = {}
        self.save()
        return self.project.calibration


def calibration_identity(cfg):
    # Namespace-independent numerical geometry identity, not display name.
    names = ['intrinsics_00.xml','distortion_00.xml','intrinsics_01.xml','distortion_01.xml','ext_R.xml','ext_T.xml']
    return identity({name:load_matrix(Path(cfg)/name).tolist() for name in names if (Path(cfg)/name).exists()})


class SyncService(BaseService):
    def run(self, window_end=30, wind_filter=True):
        result = WassLowcostAdapter().run(self.project.videos['measurement_left']['path'],
                        self.project.videos['measurement_right']['path'],self.job/'sync',self.tools,self.runner,
                        window_end,wind_filter)
        self.project.sync = result
        self.project.reference = {}
        self.save()
        return result


def extract_pair(project,tools,runner,directory,left_time):
    if not project.sync:
        raise ValueError('请先完成官方同步')
    right_time = left_time + project.sync['right_minus_left_s']
    directory = Path(directory)
    directory.mkdir(parents=True,exist_ok=False)
    paths = []
    for camera,t in [('left',left_time),('right',right_time)]:
        video = VideoAdapter(project.videos['measurement_'+camera]['path'])
        file = directory/(camera+'.png')
        try:
            video.extract(t,file,tools['ffmpeg'],runner)
        finally:
            video.close()
        paths.append(file)
    return *paths,left_time,right_time


class ReconstructionService(BaseService):
    def key(self, left_time, baseline_m):
        return frame_identity(self.project,left_time,baseline_m)

    def stereo(self,left_time,directory):
        cfg = self.config()
        if not (cfg/'ext_R.xml').exists() or not (cfg/'ext_T.xml').exists():
            raise ValueError('尚未取得双目外参，请先运行官方外参流程或加载已有结果')
        left,right,lt,rt = extract_pair(self.project,self.tools,self.runner,directory/'inputs',left_time)
        for camera,path in [('left',left),('right',right)]:
            size = cv_image_size(path)
            intrinsics = self.project.calibration.get('intrinsics')
            if intrinsics and size != intrinsics[camera]['image_size_wh']:
                raise ValueError('标定与测量分辨率不同；不自动缩放内参')
            if not intrinsics and size != self.project.calibration.get('image_size_wh'):
                raise ValueError('已有标定与测量图像尺寸不一致；不自动缩放内参')
        wd = directory/'workspaces/000000_wd'
        wd.parent.mkdir()
        adapter = WassAdapter(self.tools,self.runner)
        adapter.prepare(cfg,wd,left,right)
        for name in ['ext_R.xml','ext_T.xml']:
            shutil.copy2(cfg/name,wd/name)
        adapter.stereo(cfg,wd)
        return wd,lt,rt

    def run(self,left_time,baseline_m):
        cfg = self.config()
        ref = self.project.reference
        if not ref or ref['calibration_identity'] != calibration_identity(cfg):
            raise ValueError('没有与当前相机几何一致的参考面')
        if ref['baseline_m'] != baseline_m:
            raise ValueError('基线与参考面不一致，不能自动改变尺度')
        if digest(ref['setup']) != ref['setup_hash']:
            raise ValueError('参考面文件校验失败')
        key = self.key(left_time,baseline_m)
        cached = ResultCache().lookup(self.project,key)
        if cached:
            self.notify('读取该帧自身的已验证缓存')
            return cached
        # Failed attempts are retained; a retry must not collide with them.
        frame = self.root/'workspace/frames'/key/uuid.uuid4().hex
        frame.mkdir(parents=True,exist_ok=False)
        wd,lt,rt = self.stereo(left_time,frame)
        grid = frame/'grid'
        plot = frame/'pixel_map'
        grid.mkdir()
        plot.mkdir()
        WassGridSurfaceAdapter(self.tools,self.runner).grid(wd.parent,grid,ref['setup'])
        nc = grid/'gridded.nc'
        renderer = WassNcPlotAdapter(self.tools,self.runner)
        renderer.render(nc,plot)
        self.notify('官方 WaveView：固定参考面映射')
        mapped = renderer.reference_mapping(nc,plot)
        files = dict(mapped, xyz=str(wd/'mesh_cam.xyzC'),ply=str(wd/'mesh.ply'),netcdf=str(nc),
                     official_centered_overlay=str(plot/'00000000_grid.png'),
                     official_centered_mapping=str(plot/'00000000.mat'),left=str(frame/'inputs/left.png'),
                     right=str(frame/'inputs/right.png'), logs=str(self.job/'logs'))
        result = dict(identity=key,directory=str(frame),left_time_s=lt,right_time_s=rt,files=files,
                      calibration_identity=calibration_identity(cfg),reference=ref,
                      provenance=dict(method=mapped['method'],source='OFFICIAL_GRID_ESTIMATE',
                                      rig_fallback=self.project.calibration.get('fallback',False),
                                      calls=self.runner.calls,physically_validated=False))
        files.pop('method',None)
        result['output_hashes'] = {p:digest(p) for p in files.values() if Path(p).is_file()}
        write_json(frame/'manifest.json',result)
        self.project.frames[key] = result
        self.save()
        return result


def cv_image_size(path):
    import cv2
    image = cv2.imdecode(np.fromfile(path,np.uint8),cv2.IMREAD_GRAYSCALE)
    return [image.shape[1],image.shape[0]]


def frame_identity(project,left_time,baseline_m):
    cfg=Path(project.calibration['directory'])
    return identity(dict(videos={k:v['sha256'] for k,v in project.videos.items() if k.startswith('measurement')},
                         sync=project.sync,calibration=calibration_identity(cfg),left_time_s=left_time,
                         reference=project.reference,baseline_m=baseline_m,
                         stereo_config_sha256=digest(cfg/'stereo_config.txt'),toolchain=project.toolchain))


class ReferenceService(ReconstructionService):
    def establish(self,left_time,baseline_m,area):
        root = self.job/'reference'
        root.mkdir()
        wd,lt,rt = self.stereo(left_time,root)
        plane = np.loadtxt(wd/'plane.txt').reshape(4)
        if not np.isfinite(plane).all():
            raise ValueError('官方 WASS 未输出有效参考平面')
        # Two identical rows preserve the exact official plane while satisfying
        # the official CLI's np.loadtxt matrix contract for one reference frame.
        np.savetxt(wd.parent/'planes.txt',np.vstack([plane,plane]))
        grid = root/'grid'
        grid.mkdir()
        config = grid/'gridconfig.txt'
        config.write_text(f'[Area]\narea_center_x={area[0]}\narea_center_y={area[1]}\narea_size={area[2]}\nN={int(area[3])}\n',encoding='ascii')
        WassGridSurfaceAdapter(self.tools,self.runner).setup(wd.parent,grid,config,baseline_m,
                            self.project.videos['measurement_left']['fps'])
        result = dict(setup=str(grid/'config.mat'),setup_hash=digest(grid/'config.mat'),
                      calibration_identity=calibration_identity(self.config()), baseline_m=baseline_m,
                      plane=plane.tolist(),left_time_s=lt,right_time_s=rt,
                      height_convention='Official wassgridsurface upward Z; opposite signed distance of raw WASS plane normal',
                      provenance=dict(method='Official WASS plane.txt -> wassgridsurface setup mean plane',
                                      reference_is_verified_still_water=False,calls=self.runner.calls,
                                      source_workspace=str(wd),fallback=False,validated=False))
        write_json(root/'reference.json',result)
        self.project.reference = result
        self.save()
        return result

    def load_existing(self,path):
        r = json.loads(Path(path).read_text(encoding='utf-8'))
        if r['calibration_identity'] != calibration_identity(self.config()):
            raise ValueError('参考面与当前标定几何不同')
        if digest(r['setup']) != r['setup_hash']:
            raise ValueError('参考面文件校验失败')
        self.project.reference = r
        self.save()
        return r


class ExportService:
    def run(self,result,destination):
        target = Path(destination)
        if target.exists() and any(target.iterdir()):
            raise ValueError('导出目录必须为空，避免覆盖已有数据')
        target.mkdir(parents=True,exist_ok=True)
        for name,path in result['files'].items():
            source = Path(path)
            if source.is_file():
                shutil.copy2(source,target/(name+source.suffix))
            elif source.is_dir() and name=='logs':
                shutil.copytree(source,target/'logs')
        write_json(target/'manifest.json',result)
        return str(target)
