"""One QProcess, streamed output, and a Windows process-tree lifetime."""
import codecs
import ctypes
from ctypes import wintypes
import os
import time

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal
from minimal_app.progress import ProgressReader


class WindowsJob:
    """Kernel job; descendants die on cancellation or owner exit."""
    def __init__(self, pid):
        class Basic(ctypes.Structure):
            _fields_ = [("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
                ("flags", wintypes.DWORD), ("min_ws", ctypes.c_size_t),
                ("max_ws", ctypes.c_size_t), ("active", wintypes.DWORD),
                ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD),
                ("scheduling", wintypes.DWORD)]
        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in
                ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]
        class Extended(ctypes.Structure):
            _fields_ = [("basic", Basic), ("io", IO), ("process_memory", ctypes.c_size_t),
                ("job_memory", ctypes.c_size_t), ("peak_process", ctypes.c_size_t),
                ("peak_job", ctypes.c_size_t)]
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        for name, args, result in (
            ("CreateJobObjectW", [ctypes.c_void_p, wintypes.LPCWSTR], wintypes.HANDLE),
            ("SetInformationJobObject", [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD], wintypes.BOOL),
            ("OpenProcess", [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
            ("AssignProcessToJobObject", [wintypes.HANDLE, wintypes.HANDLE], wintypes.BOOL),
            ("CloseHandle", [wintypes.HANDLE], wintypes.BOOL)):
            method = getattr(self.api, name)
            method.argtypes, method.restype = args, result
        self.handle = self.api.CreateJobObjectW(None, None)
        process = None
        try:
            if not self.handle:
                raise ctypes.WinError(ctypes.get_last_error())
            limits = Extended()
            limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
                raise ctypes.WinError(ctypes.get_last_error())
            process = self.api.OpenProcess(0x0100 | 0x0001, False, pid)
            if not process or not self.api.AssignProcessToJobObject(self.handle, process):
                raise ctypes.WinError(ctypes.get_last_error())
        except Exception:
            self.close()
            raise
        finally:
            if process:
                self.api.CloseHandle(process)

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


class ProcessRunner(QObject):
    output = Signal(str)
    changed = Signal()
    completed = Signal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_process = None
        self.current_task_name = ""
        self.status = "PROCESS_COMPLETE"
        self.last_task_name = ""
        self.started_at = None
        self.elapsed_s = 0.0
        self._job = None
        self._terminated = False
        self._error = False
        self.progress = {}
        self.exit_code = None

    def start(self, task_name, argv, cwd, *, gated=False):
        if self.current_process is not None:
            raise RuntimeError(f"当前任务：{self.current_task_name}")
        if not argv or not str(argv[0]):
            raise ValueError("External program path is required")
        process = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        for key in env.keys():
            if key.upper().startswith(("PYINSTALLER_", "QT_", "_MEIPASS")) or key.upper() in {"PYTHONHOME", "QML2_IMPORT_PATH"}:
                env.remove(key)
        env.insert("PYTHONUNBUFFERED", "1")
        env.insert("PYTHONIOENCODING", "utf-8")
        env.insert("MINIMAL_PROCESS_GATE", "1" if gated else "0")
        process.setProcessEnvironment(env)
        process.setWorkingDirectory(str(cwd))
        self.current_process = process
        self.current_task_name = task_name
        self.status = "PROCESS_RUNNING"
        self.started_at = time.monotonic()
        self._terminated = self._error = False
        self.progress = {"stage": "starting"}
        self.exit_code = None
        self._progress_reader = ProgressReader()
        self._decoders = {channel: codecs.getincrementaldecoder("utf-8")("replace") for channel in ("stdout", "stderr")}
        process.readyReadStandardOutput.connect(lambda: self._read("stdout", process))
        process.readyReadStandardError.connect(lambda: self._read("stderr", process))
        process.started.connect(lambda: self._started(process, gated))
        process.finished.connect(lambda code, status: self._finish(process, code, status))
        process.errorOccurred.connect(lambda error: self._failed(process, error))
        self.changed.emit()
        self.output.emit(f"\n[启动] {task_name}\n[命令] {argv!r}\n")
        try:
            process.start(str(argv[0]), list(map(str, argv[1:])))
        except Exception:
            self._error = True
            process.kill()
            if process.state() == QProcess.ProcessState.NotRunning:
                self._finish(process, -1, QProcess.ExitStatus.CrashExit)
            raise

    def _started(self, process, gated):
        try:
            if os.name == "nt":
                self._job = WindowsJob(int(process.processId()))
            if self._terminated:
                self.terminate()
            elif gated:
                process.write(b"RUN\n")
        except Exception as error:
            self.output.emit(f"[stderr] 无法绑定进程树：{error}\n")
            self._error = True
            process.kill()  # Worker has not passed its stdin gate.

    def _read(self, channel, process):
        if process is not self.current_process:
            return
        reader = process.readAllStandardOutput if channel == "stdout" else process.readAllStandardError
        chunk = self._decoders[channel].decode(bytes(reader()))
        if chunk:
            if channel == "stdout":
                for event in self._progress_reader.feed(chunk):
                    self.progress = event
                    self.changed.emit()
            self.output.emit(f"[{channel}] {chunk}")

    def _failed(self, process, error):
        if process is not self.current_process:
            return
        self._error = True
        self.output.emit(f"[stderr] {process.errorString()}\n")
        if error == QProcess.ProcessError.FailedToStart:
            self._finish(process, -1, QProcess.ExitStatus.CrashExit)
        elif process.state() != QProcess.ProcessState.NotRunning:
            process.kill()

    def terminate(self):
        process = self.current_process
        if process is None:
            return
        self._terminated = True
        self.output.emit(f"[终止] {self.current_task_name}：停止进程树\n")
        if self._job:
            self._job.close()
            self._job = None
        process.kill()

    def _finish(self, process, code, exit_status):
        if process is not self.current_process:
            return
        try:
            for channel in self._decoders:
                self._read(channel, process)
                tail = self._decoders[channel].decode(b"", final=True)
                if tail:
                    self.output.emit(f"[{channel}] {tail}")
            if self._job:
                self._job.close()
            self.status = ("USER_TERMINATED" if self._terminated else
                "PROCESS_COMPLETE" if code == 0 and exit_status == QProcess.ExitStatus.NormalExit and not self._error
                else "PROCESS_FAILED")
        finally:
            self._job = None
            self.last_task_name = self.current_task_name
            self.exit_code = code
            self.elapsed_s = time.monotonic() - self.started_at
            self.current_process = None
            self.current_task_name = ""
            process.deleteLater()
            self.changed.emit()
        self.output.emit(f"[结束] {self.last_task_name} {self.status} exit={code} elapsed={self.elapsed_s:.1f}s\n")
        self.completed.emit(self.status, code)
