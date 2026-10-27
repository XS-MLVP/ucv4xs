"""Project export policy; the managed runner captures live groups itself."""
from contextvars import ContextVar
from pathlib import Path

_explicit = ContextVar('bpu_explicit_functional_exports', default=True)


def set_functional_exports(enabled):
    return _explicit.set(enabled)


def reset_functional_exports(token):
    _explicit.reset(token)


def write_functional_coverage(coverage, path):
    """Legacy pytest may export; production has no redundant per-case JSON."""
    return coverage.write_json(path) if _explicit.get() else Path(path)
