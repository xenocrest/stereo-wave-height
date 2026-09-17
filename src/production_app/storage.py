import hashlib
import json
import os
from pathlib import Path
from .domain import Project


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def identity(record):
    return hashlib.sha256(json.dumps(record, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def write_json(path, record):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding='utf-8')
    os.replace(temp, path)


class ProjectStore:
    def create(self, directory, name):
        root = Path(directory).resolve()
        if (root / 'project.json').exists():
            raise ValueError('项目已存在，请使用打开项目')
        root.mkdir(parents=True, exist_ok=True)
        p = Project(name, str(root))
        self.save(p)
        return p

    def save(self, project):
        write_json(Path(project.directory) / 'project.json', project.record())
        write_json(Path(project.directory) / 'TOOLCHAIN_PROVENANCE.json', project.toolchain)

    def open(self, filename):
        path = Path(filename).resolve()
        data = json.loads(path.read_text(encoding='utf-8'))
        if data.get('schema') != 1:
            raise ValueError('不支持的项目版本')
        if Path(data['directory']).resolve() != path.parent:
            raise ValueError('项目目录已移动，请先核对结果与引用路径')
        return Project(**data)


class ResultCache:
    def lookup(self, project, key):
        record = project.frames.get(key)
        if not record:
            return None
        for filename, expected in record.get('output_hashes', {}).items():
            if not Path(filename).is_file() or digest(filename) != expected:
                return None
        return record
