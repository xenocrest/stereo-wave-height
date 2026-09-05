"""Optional local research runtime; no bundled model weights or changed WASS."""
import json
import os
from pathlib import Path


def runtime_path(repository):
    path=Path(os.environ.get('STEREO_FOUNDATION_RUNTIME',str(Path(repository)/'foundationstereo_runtime.json')))
    return path if path.is_file() else None


def load_runtime(repository):
    path=runtime_path(repository)
    if path is None:
        return None
    data=json.loads(path.read_text(encoding='utf-8'))
    if not data.get('enabled',False):
        return None
    for key in ('python','project_root','source','weights'):
        if not Path(data[key]).exists():
            raise FileNotFoundError(f'FoundationStereo runtime missing {key}: {data[key]}')
    return data
