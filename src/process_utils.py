"""Portable subprocess options; Windows GUI launches remain invisible but logged."""
from __future__ import annotations

import os
import subprocess


def hidden_process_kwargs(*, enabled: bool = True) -> dict[str, object]:
    """Return Windows no-console flags without changing stdout/stderr handling."""
    if os.name != "nt" or not enabled:
        return {}
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    return {"creationflags": subprocess.CREATE_NO_WINDOW, "startupinfo": startup}

