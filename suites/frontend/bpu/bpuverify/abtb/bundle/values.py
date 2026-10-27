"""bpuverify.abtb.bundle.values components."""

from __future__ import annotations
from typing import Any


def _plain(value: Any) -> Any:
    if hasattr(value, "as_int"):
        return value.as_int()
    if hasattr(value, "items"):
        return {name: _plain(item) for name, item in value.items()}
    if isinstance(value, tuple):
        return tuple(_plain(item) for item in value)
    return value
