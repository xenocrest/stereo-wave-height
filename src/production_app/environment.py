"""Official external-process isolation; no scientific calculations.

Follows PyInstaller's Windows external-program guidance: clear inherited
SetDllDirectory during process creation and remove only bundle PATH entries.
"""
from contextlib import contextmanager
import os
from pathlib import Path
import subprocess
import sys


class ProcessEnvironmentAdapter:
    @staticmethod
    def clean(environ=None, bundle=None):
        env = dict(os.environ if environ is None else environ)
        bundle = bundle or getattr(sys, '_MEIPASS', None)
        if bundle:
            root = os.path.normcase(os.path.abspath(bundle))
            paths = []
            for entry in env.get('PATH', '').split(os.pathsep):
                candidate = os.path.normcase(os.path.abspath(entry))
                if candidate != root and not candidate.startswith(root + os.sep):
                    paths.append(entry)
            env['PATH'] = os.pathsep.join(paths)
        for key in list(env):
            if key.startswith(('QT_', '_PYI_')) or key in ('PYTHONHOME',):
                env.pop(key)
        env['PYTHONUTF8'] = '1'
        return env

    @staticmethod
    @contextmanager
    def launch_scope():
        if sys.platform != 'win32' or not getattr(sys, 'frozen', False):
            yield
            return
        import ctypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.SetDllDirectoryW.argtypes = [ctypes.c_wchar_p]
        kernel.SetDllDirectoryW.restype = ctypes.c_int
        kernel.GetDllDirectoryW.argtypes = [ctypes.c_uint32, ctypes.c_wchar_p]
        buffer = ctypes.create_unicode_buffer(32768)
        kernel.GetDllDirectoryW(len(buffer), buffer)
        if not kernel.SetDllDirectoryW(None):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            yield
        finally:
            if not kernel.SetDllDirectoryW(buffer.value or None):
                raise ctypes.WinError(ctypes.get_last_error())


class ExternalToolRunner:
    @staticmethod
    def run(argv, cwd=None, timeout=None):
        with ProcessEnvironmentAdapter.launch_scope():
            return subprocess.run(list(map(str, argv)), cwd=cwd,
                env=ProcessEnvironmentAdapter.clean(), stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, timeout=timeout,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def check_toolchain(tools):
    """Bounded executable/module probes, not reconstruction or calibration."""
    python = tools.get('python', '')
    binaries = {name: str(Path(tools.get('wass_bin', '')) / (name + '.exe'))
                for name in ('wass_prepare', 'wass_match', 'wass_autocalibrate', 'wass_stereo')}
    binaries.update(ffmpeg=tools.get('ffmpeg', ''), Praat=tools.get('praat', ''), Python=python)
    for name in ('wasscli', 'wassgridsurface', 'wassncplot'):
        binaries[name] = str(Path(python).parent / (name + '.exe'))
    result = []
    for name, path in binaries.items():
        record = dict(name=name, path=path, status='MISSING', version='')
        if path and Path(path).is_file():
            argv = [path, '-version'] if name == 'ffmpeg' else [path, '--version']
            if name.startswith('wass_'):
                argv = [path]
            if name == 'wasscli':
                # wasscli is an interactive menu, not a --version CLI.
                argv = [python, '-c', 'import wasscli; import importlib.metadata as m; print("wasscli",m.version("wasscli"))']
            try:
                p = ExternalToolRunner.run(argv, timeout=15)
                text = p.stdout.decode('utf-16-le' if b'\x00' in p.stdout[:100] else 'utf-8', errors='replace')
                available = p.returncode == 0 or (name.startswith('wass') and 'usage:' in text.lower() and 'traceback' not in text.lower())
                record.update(status='AVAILABLE' if available else 'FAILED', returncode=p.returncode, version=text[:500])
            except Exception as error:
                record.update(status='FAILED', version=f'{type(error).__name__}: {error}')
        result.append(record)
    try:
        p = ExternalToolRunner.run([python, '-c',
            'import cv2,numpy; print("OpenCV",cv2.__version__,"NumPy",numpy.__version__)'], timeout=15)
        result.append(dict(name='OpenCV/NumPy', path=python,
            status='AVAILABLE' if p.returncode == 0 else 'FAILED',
            version=p.stdout.decode('utf-8', errors='replace')[:500]))
    except Exception as error:
        result.append(dict(name='OpenCV/NumPy', path=python, status='FAILED', version=str(error)))
    return result
