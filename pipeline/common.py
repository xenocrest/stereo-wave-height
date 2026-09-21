from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any


def sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def copy_file(source: str | Path, destination: str | Path) -> Path:
    source, destination = Path(source), Path(destination)
    if not source.is_file():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination


class StageFailure(RuntimeError):
    def __init__(self, stage: str, message: str):
        super().__init__(message)
        self.stage = stage


class CommandRecorder:
    """Run commands, preserving the exact argv, output, return code and timing."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.calls: list[dict[str, Any]] = []

    @staticmethod
    def _clean_env() -> dict[str, str]:
        env = os.environ.copy()
        for key in list(env):
            upper = key.upper()
            if upper.startswith("PYINSTALLER_") or upper in {"_MEIPASS", "QT_PLUGIN_PATH", "QML2_IMPORT_PATH"}:
                env.pop(key, None)
        return env

    def run(
        self,
        stage: str,
        argv: list[str | Path],
        *,
        cwd: str | Path | None = None,
        check: bool = True,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        command = [str(item) for item in argv]
        index = len(self.calls)
        log = self.root / f"{index:03d}_{stage}.log"
        started = time.perf_counter()
        completed = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            env=self._clean_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        elapsed = time.perf_counter() - started
        record = {
            "stage": stage,
            "argv": command,
            "cwd": str(Path(cwd).resolve()) if cwd else None,
            "return_code": completed.returncode,
            "elapsed_s": elapsed,
            "log": str(log),
        }
        self.calls.append(record)
        log.write_text(
            "COMMAND: " + subprocess.list2cmdline(command) + "\n"
            + f"CWD: {record['cwd']}\nRETURN_CODE: {completed.returncode}\nELAPSED_S: {elapsed:.6f}\n\n"
            + "STDOUT\n" + completed.stdout + "\n\nSTDERR\n" + completed.stderr,
            encoding="utf-8",
        )
        if check and completed.returncode:
            raise StageFailure(stage, f"{stage} failed with return code {completed.returncode}; see {log}")
        return record


def require_empty(directory: str | Path) -> Path:
    path = Path(directory)
    if path.exists() and any(path.iterdir()):
        raise ValueError(f"run directory must be empty: {path}")
    path.mkdir(parents=True, exist_ok=True)
    return path

