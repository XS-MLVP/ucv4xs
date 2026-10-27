"""Small shared primitives. SPDX-License-Identifier: MPL-2.0."""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid

class UcvError(RuntimeError):
    pass

def read(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError) as error:
        raise UcvError(f"Cannot read {path}: {error}") from error

def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def file_hash(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def now():
    return datetime.now(timezone.utc).isoformat()

def execute(command, *, cwd=None, env=None, log=None, check=True):
    command = [str(x) for x in command]
    if log:
        log = Path(log)
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open('a') as stream:
            stream.write('\n' + json.dumps(command) + '\n')
            stream.flush()
            result = subprocess.run(command, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT)
    else:
        result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True)
    if check and result.returncode:
        details = f'see {log}' if log else (result.stderr or result.stdout)[-4000:]
        raise UcvError(f"Command failed ({result.returncode}): {command}\n{details}")
    return result

@contextmanager
def lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield

def contained(root, relative):
    path = root / relative
    if Path(relative).is_absolute() or not path.resolve().is_relative_to(root.resolve()):
        raise UcvError(f'Path escapes repository: {relative}')
    return path

def activate(link, target):
    link = Path(link)
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.exists() and not link.is_symlink():
        raise UcvError(f'Refusing to replace a real directory: {link}')
    temp = link.with_name(link.name + '.' + uuid.uuid4().hex)
    temp.symlink_to(os.path.relpath(target, link.parent), target_is_directory=True)
    temp.replace(link)
