"""Process-local testcase output routing; independent of DUT/driver state."""
from contextlib import contextmanager
from contextvars import ContextVar
from hashlib import sha256
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
_case_output = ContextVar('bpu_case_output', default=None)


def case_directory(run: Path, worker: str, nodeid: str) -> Path:
    if not isinstance(worker, str) or re.fullmatch(r'main|gw[0-9]+', worker) is None:
        raise ValueError('invalid pytest worker identity')
    if not isinstance(nodeid, str) or not nodeid:
        raise ValueError('full pytest nodeid is required')
    return Path(run).resolve() / 'workers' / worker / sha256(nodeid.encode()).hexdigest() / 'results'


@contextmanager
def case_outputs(directory: Path):
    """Bind before setup, reset after teardown; child async tasks inherit it."""
    directory = Path(directory)
    if not directory.is_absolute():
        raise ValueError('testcase output directory must be absolute')
    token = _case_output.set(directory)
    try:
        yield directory
    finally:
        _case_output.reset(token)


def output_path(path) -> Path:
    """Route repository results only; explicit independent tmp paths stay put.

    The operation is side-effect free and idempotent. Serial legacy execution
    without a bound testcase directory keeps its original output filenames.
    """
    path = Path(path)
    current = _case_output.get()
    if current is None:
        return path
    absolute = path if path.is_absolute() else ROOT / path
    if absolute.is_relative_to(current):
        return absolute
    original_root = ROOT / 'results'
    if absolute.is_relative_to(original_root):
        return current / absolute.relative_to(original_root)
    return path


def output_directory(root: Path, dut: str) -> Path:
    if not isinstance(dut, str) or re.fullmatch(r'[a-z][a-z0-9_]*', dut) is None:
        raise ValueError('invalid DUT output name')
    return output_path(Path(root) / 'results' / dut)


def write_output(path, text: str, *, encoding: str = 'utf-8') -> Path:
    """Write a routed text artifact, creating only its declared parent.

    ``output_path`` stays side-effect free for callers that only need a name;
    this helper owns the filesystem write so that an isolated case directory
    cannot turn a real verdict into a spurious FileNotFoundError.
    """
    target = output_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding=encoding)
    return target


def isolated_outputs() -> bool:
    return _case_output.get() is not None
