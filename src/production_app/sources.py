"""Stereo input IO only: videos or already-synchronized original images."""
from pathlib import Path
import shutil
import cv2
import numpy as np
from .adapters import VideoSourceAdapter
from .storage import digest, identity


class StereoImageSequenceSource:
    def __init__(self, record):
        self.files = record['files']
        self.hashes = record['hashes']
        self.fps = float(record['fps'])
        self.count = len(self.files)
        if self.fps <= 0 or not self.count:
            raise ValueError('图像序列缺少有效采样率或帧')

    def seek(self, index):
        if not 0 <= index < self.count:
            raise ValueError('帧编号超出图像序列范围')
        filename = self.files[index]
        if digest(filename) != self.hashes[index]:
            raise ValueError('原始样例图像校验失败：' + filename)
        image = cv2.imdecode(np.fromfile(filename, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError('图像读取失败：' + filename)
        self.last_index, self.last_time_s = index, index / self.fps
        return image

    def seek_time(self, time_s):
        index = round(time_s * self.fps)
        if abs(index / self.fps - time_s) > 1e-6:
            raise ValueError('图像序列时刻不是原始采样帧，不能插值输入')
        return self.seek(index)

    def extract(self, time_s, filename, ffmpeg, runner):
        self.seek_time(time_s)
        source = Path(self.files[self.last_index])
        target = Path(filename).with_suffix(source.suffix)
        shutil.copy2(source, target)
        if digest(target) != self.hashes[self.last_index]:
            raise ValueError('图像序列复制校验失败')
        return target

    def close(self):
        pass


class StereoVideoSource(VideoSourceAdapter):
    pass


def open_source(project, camera):
    record = project.videos['measurement_' + camera]
    if project.source_type == 'stereo_image_sequence':
        return StereoImageSequenceSource(record)
    return StereoVideoSource(record['path'])


def sequence_records(left, right, fps):
    if not np.isfinite(fps) or fps<=0:
        raise ValueError('图像序列采样率必须为正数')
    extensions = {'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp'}
    records = {}
    keys = []
    for camera, folder in [('left', left), ('right', right)]:
        files = sorted(p for p in Path(folder).iterdir() if p.suffix.lower() in extensions)
        if not files:
            raise ValueError('空图像序列：' + str(folder))
        names = [p.stem for p in files]
        if len(set(names)) != len(names):
            raise ValueError('同一图像序列中存在重复帧名')
        keys.append(names)
        hashes = [digest(p) for p in files]
        image = cv2.imdecode(np.fromfile(files[0], np.uint8), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise ValueError('无法读取序列首帧')
        records['measurement_' + camera] = dict(path=str(Path(folder).resolve()),
            files=list(map(lambda p: str(p.resolve()), files)), hashes=hashes,
            sha256=identity(dict(names=names, hashes=hashes, fps=fps)),
            width=image.shape[1], height=image.shape[0], fps=float(fps),
            frame_count=len(files), duration_s=len(files)/fps, has_audio=False, codec_fourcc=None)
    if keys[0] != keys[1]:
        raise ValueError('同步图像序列左右帧名/数量不一致，不能猜测配对')
    if records['measurement_left']['width'] != records['measurement_right']['width'] or records['measurement_left']['height'] != records['measurement_right']['height']:
        raise ValueError('左右图像序列尺寸不一致')
    return records
