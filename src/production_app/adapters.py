"""IO adapters. Numerical work belongs to OpenCV or the official executables."""
import json
import os
from pathlib import Path
import subprocess
import cv2
import numpy as np


class ToolFailure(RuntimeError):
    pass


class OfficialRunner:
    def __init__(self, root, notify=print):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.notify = notify
        self.calls = []

    def run(self, name, argv, cwd=None):
        import time
        self.notify(name)
        start = time.perf_counter()
        result = subprocess.run(list(map(str, argv)), cwd=cwd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        raw = result.stdout
        text = raw.decode('utf-16-le' if b'\x00' in raw[:100] else 'utf-8', errors='replace')
        log = self.root / (name + '.log')
        log.write_text(subprocess.list2cmdline(list(map(str, argv))) + '\n' + text, encoding='utf-8')
        self.calls.append(dict(stage=name, argv=list(map(str, argv)), returncode=result.returncode,
                               elapsed_s=time.perf_counter()-start, log=str(log)))
        if result.returncode:
            raise ToolFailure(f'{name} 失败（返回值 {result.returncode}）：{text[-1200:]}\n日志：{log}')
        return text


class VideoSourceAdapter:
    def __init__(self, filename):
        self.path = str(Path(filename).resolve())
        self.capture = cv2.VideoCapture(self.path)
        if not self.capture.isOpened():
            raise ValueError('视频读取失败：' + self.path)
        self.capture.set(cv2.CAP_PROP_ORIENTATION_AUTO, 1)
        self.fps = self.capture.get(cv2.CAP_PROP_FPS)
        self.count = int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if self.fps <= 0 or self.count <= 0:
            self.close()
            raise ValueError('视频没有有效帧或 FPS')

    def metadata(self, ffmpeg=None):
        result = dict(path=self.path, width=int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
                      height=int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT)), fps=self.fps,
                      frame_count=self.count, duration_s=self.count/self.fps,
                      codec_fourcc=int(self.capture.get(cv2.CAP_PROP_FOURCC)), has_audio=None)
        if ffmpeg:
            p = subprocess.run([ffmpeg, '-hide_banner', '-i', self.path], capture_output=True,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            result['ffmpeg_metadata'] = p.stderr.decode('utf-8', errors='replace')
            result['has_audio'] = 'Audio:' in result['ffmpeg_metadata']
        return result

    def seek(self, index):
        if not 0 <= index < self.count:
            raise ValueError('帧编号超出视频范围')
        if int(self.capture.get(cv2.CAP_PROP_POS_FRAMES)) != index:
            self.capture.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = self.capture.read()
        if not ok:
            raise ValueError(f'无法读取帧 {index}：{self.path}')
        self.last_index=index
        self.last_time_s=float(self.capture.get(cv2.CAP_PROP_POS_MSEC))/1000
        return frame

    def seek_time(self,time_s):
        if not 0<=time_s<self.count/self.fps:
            raise ValueError('同步时刻超出视频范围')
        self.capture.set(cv2.CAP_PROP_POS_MSEC,time_s*1000)
        ok,frame=self.capture.read()
        if not ok:
            raise ValueError('无法读取同步帧')
        self.last_index=max(0,int(self.capture.get(cv2.CAP_PROP_POS_FRAMES))-1)
        self.last_time_s=float(self.capture.get(cv2.CAP_PROP_POS_MSEC))/1000
        return frame

    def extract(self, time_s, filename, ffmpeg, runner):
        if not 0 <= time_s < self.count/self.fps:
            raise ValueError('同步时刻超出视频范围')
        runner.run('extract_' + Path(filename).stem, [ffmpeg, '-hide_banner', '-loglevel', 'error',
                   '-y', '-i', self.path, '-ss', f'{time_s:.9f}', '-frames:v', '1',
                   '-vsync', '0', filename])
        if not Path(filename).is_file():
            raise ToolFailure('FFmpeg 未产生帧：' + str(filename))

    def close(self):
        self.capture.release()


VideoAdapter = VideoSourceAdapter


def load_matrix(path):
    xml = Path(path).read_text(encoding='utf-8')
    fs = cv2.FileStorage(xml, cv2.FILE_STORAGE_READ | cv2.FILE_STORAGE_MEMORY)
    value = fs.getFirstTopLevelNode().mat()
    fs.release()
    if value is None or not np.isfinite(value).all():
        raise ValueError('无效 OpenCV 矩阵：' + str(path))
    return value


def save_matrix(path, value):
    fs = cv2.FileStorage('.xml', cv2.FILE_STORAGE_WRITE | cv2.FILE_STORAGE_MEMORY)
    fs.write('matrix', np.asarray(value, dtype=np.float64))
    Path(path).write_text(fs.releaseAndGetString(), encoding='utf-8')


class OpenCVCalibrationAdapter:
    def detect(self, video, output, pattern, interval_frames=120, max_candidates=80, notify=print):
        from .storage import write_json
        output = Path(output)
        output.mkdir(parents=True, exist_ok=False)
        source = VideoSourceAdapter(video)
        records = []
        size = None
        # Uniform sampling only. No RMS-based selection or altered camera model.
        for index in list(range(0, source.count, max(1, interval_frames)))[:max_candidates]:
            notify(f'棋盘检测：帧 {index}')
            frame = source.seek(index)
            size = [frame.shape[1], frame.shape[0]]
            found, corners = cv2.findChessboardCornersSB(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), tuple(pattern),
                        flags=cv2.CALIB_CB_NORMALIZE_IMAGE|cv2.CALIB_CB_EXHAUSTIVE|cv2.CALIB_CB_ACCURACY)
            filename = output / f'{index:08d}.png'
            preview = frame.copy()
            if found:
                cv2.drawChessboardCorners(preview, tuple(pattern), corners, True)
            cv2.imencode('.png', preview)[1].tofile(str(filename))
            records.append(dict(index=index, found=bool(found), selected=bool(found), preview=str(filename),
                                corners=corners.tolist() if found else None))
        source.close()
        result = dict(source_video=str(video), image_size_wh=size, pattern=list(pattern),
                      opencv_version=cv2.__version__, records=records)
        write_json(output/'detections.json', result)
        return result

    def calibrate(self, detections, output, square_m, selected=None):
        from .storage import write_json, digest
        d = json.loads(Path(detections).read_text(encoding='utf-8'))
        records = [r for r in d['records'] if r['found'] and (selected is None or r['index'] in selected)]
        if len(records) < 10:
            raise ValueError(f'有效棋盘帧仅 {len(records)} 个；至少需要10个不同姿态的完整检测帧')
        if not np.isfinite(square_m) or square_m <= 0:
            raise ValueError('棋盘格边长必须为正数')
        template = np.zeros((np.prod(d['pattern']), 3), np.float32)
        template[:,:2] = np.mgrid[0:d['pattern'][0],0:d['pattern'][1]].T.reshape(-1,2)*square_m
        # OpenCV 4/5 expose N×1×2 or N×2; normalize the IO layout only.
        image_points = [np.asarray(r['corners'], np.float32).reshape(-1,1,2) for r in records]
        rms, K, D, rvecs, tvecs = cv2.calibrateCamera([template.copy() for _ in records], image_points,
                                                    tuple(d['image_size_wh']), None, None)
        if not np.isfinite(K).all() or not np.isfinite(D).all() or not np.isfinite(rms):
            raise ValueError('OpenCV 标定产生无效参数')
        output = Path(output)
        output.mkdir(parents=True, exist_ok=False)
        save_matrix(output/'intrinsics.xml', K)
        save_matrix(output/'distortion.xml', D.reshape(-1,1))
        errors = []
        for points, r, t in zip(image_points, rvecs, tvecs):
            projected, _ = cv2.projectPoints(template, r, t, K, D)
            errors.append(float(cv2.norm(points, projected, cv2.NORM_L2)/np.sqrt(len(template))))
        result = dict(K=K.tolist(), D=D.reshape(-1).tolist(), rms=float(rms), per_view_rms=errors,
                      selected_frames=[r['index'] for r in records], image_size_wh=d['image_size_wh'],
                      source_video=d['source_video'], source_sha256=digest(d['source_video']),
                      detections=str(detections), pattern=d['pattern'], square_m=square_m,
                      method='OpenCV findChessboardCornersSB / calibrateCamera',
                      opencv_version=cv2.__version__, physically_validated=False)
        write_json(output/'calibration.json', result)
        return result


class WassLowcostAdapter:
    """Execute unchanged upstream Praat-generation and optional FIR statements.

    Upstream has no callable API; its monolithic entrypoint renames inputs and
    hardcodes /usr/bin/praat even on Windows. Invoke its original TLCC blocks,
    not a rewritten correlator. Path/process handling stays in this adapter.
    """
    def run(self, left, right, output, tools, runner, window_end=30, wind_filter=True):
        import ast
        from scipy.io import wavfile
        from scipy import signal
        from .storage import digest, write_json
        upstream = Path(tools['wass_lowcost'])/'wass_sync.py'
        code = upstream.read_text(encoding='utf-8')
        tree = ast.parse(code)
        script_nodes = [n for n in tree.body if isinstance(n, ast.If)
                        and 'os.path.isfile' in ast.get_source_segment(code, n).split('\n')[0]
                        and 'crosscorrelate.praat' in ast.get_source_segment(code, n)]
        wind_nodes = [n for n in tree.body if isinstance(n, ast.For)
                      and 'audio_wind_filter' in ast.get_source_segment(code, n)]
        if len(script_nodes) != 1 or len(wind_nodes) != 1:
            raise ToolFailure('官方 wass_lowcost 源码接口已变化，不能自动执行')
        output = Path(output)
        output.mkdir(parents=True, exist_ok=False)
        wavs = []
        for i, path in enumerate([left,right]):
            filename = output/f'wav_file_{i}.wav'
            runner.run(f'audio_{i}', [tools['ffmpeg'], '-hide_banner', '-loglevel', 'error', '-y',
                       '-i', path, '-t', str(window_end), '-vn', '-acodec', 'pcm_s16le',
                       '-ar', '48000', '-ac', '2', filename])
            wavs.append(str(filename))
        env = dict(os=os, np=np, wavfile=wavfile, signal=signal, pathname=str(output)+'/',
                   audio_sync_cc_window_ini=0, audio_sync_cc_window_fin=window_end,
                   wav_list=wavs, audio_wind_filter='on' if wind_filter else 'off', count=0)
        previous = Path.cwd()
        try:
            os.chdir(output)
            for nodes in [script_nodes, wind_nodes]:
                exec(compile(ast.Module(body=nodes, type_ignores=[]), str(upstream), 'exec'), env)
        finally:
            os.chdir(previous)
        text = runner.run('TLCC_Praat', [tools['praat'], '--run', output/'crosscorrelate.praat',
                          wavs[0], wavs[1], '0', str(window_end)], cwd=output)
        offset = round(float(text.strip().splitlines()[0]), 3)  # upstream offset rounding
        result = dict(right_minus_left_s=offset, method='wass_lowcost original TLCC blocks / Praat',
                      upstream_source=str(upstream), upstream_sha256=digest(upstream),
                      praat_sha256=digest(tools['praat']), window_s=[0,window_end], wind_filter=wind_filter,
                      left=left, right=right, left_sha256=digest(left), right_sha256=digest(right),
                      cfr_vfr='Timestamp selection by FFmpeg; original PTS retained. Audio is not exposure sync.',
                      platform_adapter='Original AST blocks unchanged; FFmpeg/Praat paths and stdout decoding adapted')
        write_json(output/'sync.json', result)
        return result


class WassAdapter:
    def __init__(self, tools, runner):
        self.tools, self.runner = tools, runner

    def prepare(self, config, workspace, left, right):
        self.runner.run('prepare_'+Path(workspace).name, [Path(self.tools['wass_bin'])/'wass_prepare.exe',
                        '--workdir', workspace, '--calibdir', config, '--c0', left, '--c1', right])

    def match(self, config, workspace):
        self.runner.run('match_'+Path(workspace).name, [Path(self.tools['wass_bin'])/'wass_match.exe',
                        Path(config)/'matcher_config.txt', workspace])

    def autocalibrate(self, workspaces_file):
        self.runner.run('autocalibrate', [Path(self.tools['wass_bin'])/'wass_autocalibrate.exe', workspaces_file])

    def stereo(self, config, workspace):
        self.runner.run('stereo_'+Path(workspace).name, [Path(self.tools['wass_bin'])/'wass_stereo.exe',
                        Path(config)/'stereo_config.txt', workspace])
        if not (Path(workspace)/'mesh_cam.xyzC').is_file():
            raise ToolFailure('WASS stereo 未生成 mesh_cam.xyzC')


class WassGridSurfaceAdapter:
    def __init__(self, tools, runner):
        self.exe = Path(tools['python']).parent/'wassgridsurface.exe'
        self.runner = runner

    def setup(self, work, out, gridconfig, baseline_m, fps):
        self.runner.run('surface_setup', [self.exe, '--action', 'setup', work, out, '--gridconfig',
                        gridconfig, '--baseline', str(baseline_m), '--fps', str(fps)])

    def grid(self, work, out, setup):
        self.runner.run('surface_grid', [self.exe, '--action', 'grid', work, out, '--gridsetup', setup,
                        '--num_frames', '1', '--parallel', '1', '--stereo_image_idx', '0'])


class WassNcPlotAdapter:
    def __init__(self, tools, runner):
        self.exe = Path(tools['python']).parent/'wassncplot.exe'
        self.runner = runner

    def render(self, nc, output):
        self.runner.run('official_overlay', [self.exe, nc, output, '-f', '0', '-l', '1', '--savexyz',
                        '--save-img', '--no-textoverlay', '--pxscale', '1'])

    def reference_mapping(self, nc, output):
        """Official WaveView API with unchanged reference-frame NC elevations.

        The CLI always subtracts its current sequence zmean. The official
        renderer also accepts the original NC elevations; use this existing
        API to preserve the project's fixed reference, without modifying it.
        """
        import netCDF4
        from scipy.io import savemat
        from wassncplot.WaveFieldVisualize.waveview2 import WaveView
        output = Path(output)
        with netCDF4.Dataset(str(nc), 'r') as ds:
            image = cv2.imdecode(np.asarray(ds['cam0images'][0]), cv2.IMREAD_GRAYSCALE)
            xx, yy = np.asarray(ds['X_grid'][:])/1000, np.asarray(ds['Y_grid'][:])/1000
            height = np.asarray(ds['Z'][0])/1000
            projection = np.asarray(ds['meta']['P0plane'][:])
        view = WaveView(title='官方参考面坐标映射', width=image.shape[1], height=image.shape[0],
                        wireframe=False, pixel_scale=1)
        view.setup_field(xx, yy, projection.T)
        view.set_zrange(float(height.min()), float(height.max()), 0.5)
        rendered, mapping = view.render(image, height)
        view.close()
        # Official wassncplot2 uses this display-only resize for high-DPI output.
        if rendered.shape[:2] != image.shape[:2]:
            image=cv2.resize(image,(rendered.shape[1],rendered.shape[0]))
        savemat(output/'reference_pixel_xyz.mat', {'px_2_3D':mapping}, do_compression=True)
        # Same image encoding convention as the official CLI (RGB float → BGR u8).
        encoded=cv2.cvtColor((rendered*255).astype(np.uint8),cv2.COLOR_RGB2BGR)
        cv2.imencode('.png', encoded)[1].tofile(str(output/'reference_overlay.png'))
        cv2.imencode('.png', image)[1].tofile(str(output/'reference_image.png'))
        return dict(mapping=str(output/'reference_pixel_xyz.mat'), overlay=str(output/'reference_overlay.png'),
                    image=str(output/'reference_image.png'),
                    method='Unmodified official WaveView.setup_field/render; NC Z relative to fixed reference; no recentering')
