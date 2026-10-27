"""Explicit, opt-in diagnostic traces; never part of the test verdict."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import gzip
import json
import os
from pathlib import Path
import tempfile
from icacheverify.common.env.artifacts import output_path

_TRACE_EXPORT = ContextVar("bpu_trace_export", default=False)


def trace_exports_enabled() -> bool:
    return _TRACE_EXPORT.get()


def set_trace_exports(enabled: bool):
    if type(enabled) is not bool:
        raise TypeError("trace export must be explicitly enabled with a boolean")
    return _TRACE_EXPORT.set(enabled)


def reset_trace_exports(token) -> None:
    _TRACE_EXPORT.reset(token)


@contextmanager
def trace_exports(enabled: bool = True):
    """Enable diagnostics in this context, including its child async tasks."""
    token = set_trace_exports(enabled)
    try:
        yield
    finally:
        reset_trace_exports(token)


def dump_trace(path, value, *, default=None) -> Path | None:
    """No filesystem or serialization work unless diagnostics were requested.

    Enabled traces are streamed as gzip JSON, then published without replacing
    an existing file. Failed serialization cannot leave a partial final trace.
    Functional summaries and live checker exceptions are deliberately unrelated.
    """
    if not _TRACE_EXPORT.get():
        return None
    target = output_path(path)
    if target.suffix != ".gz":
        target = target.with_name(target.name + ".gz")
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(
        prefix="." + target.name + ".", suffix=".pending", dir=target.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as raw:
            with gzip.GzipFile(filename="", fileobj=raw, mode="wb",
                               compresslevel=1, mtime=0) as compressed:
                encoder = json.JSONEncoder(default=default, ensure_ascii=False,
                                           separators=(",", ":"))
                for fragment in encoder.iterencode(value):
                    compressed.write(fragment.encode("utf-8"))
                compressed.write(b"\n")
        os.link(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return target
