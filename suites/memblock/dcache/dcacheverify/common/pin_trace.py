"""Record which DUT pins the testbench fetches, per DUT.

Why: grepping `env.py` for a pin name is wrong — envs build names like
`f"io_read_resp_{port}_{j}_raw_data"`, so most pins are only touched at runtime.
This records the real attribute fetches on the DUT object and dumps the union at
session end, which is the honest answer to "does the bench ever look at this pin?".

The recorder must not wrap the pin objects: toffee's `Execution` requires real
`xspcomm.XData` for edge triggers, so wrapping them breaks clocking.  Recording at
fetch time is enough for the audit because a pin that is never fetched cannot be
compared at all.

Enable with `DCACHE_PIN_TRACE=<path>`; when unset the factory returns the raw DUT.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

_FETCHED: dict[str, set[str]] = {}
_ENABLED = False


class _DutRecorder:
    """Attribute proxy that records pin names the bench fetches."""

    __slots__ = ("_dut", "_key")

    def __init__(self, dut, key: str) -> None:
        object.__setattr__(self, "_dut", dut)
        object.__setattr__(self, "_key", key)
        _FETCHED.setdefault(key, set())

    def __getattr__(self, name: str):
        dut = object.__getattribute__(self, "_dut")
        if name in ("Step", "Finish", "InitClock", "xclock", "xport"):
            return getattr(dut, name)
        value = getattr(dut, name)
        if hasattr(value, "Set") and hasattr(value, "value"):
            _FETCHED[object.__getattribute__(self, "_key")].add(name)
        return value

    def __setattr__(self, name: str, value) -> None:
        setattr(object.__getattribute__(self, "_dut"), name, value)

    def __dir__(self):
        return dir(object.__getattribute__(self, "_dut"))


def wrap(dut, key: str):
    global _ENABLED
    if not os.environ.get("DCACHE_PIN_TRACE"):
        return dut
    _ENABLED = True
    return _DutRecorder(dut, key)


def dump() -> None:
    path = os.environ.get("DCACHE_PIN_TRACE")
    if not path or not _ENABLED:
        return
    base = Path(path)
    out = base.with_name(f"{base.name}.{os.getpid()}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "schema_version": 2,
        "note": "pins fetched at least once by the bench",
        "duts": {k: sorted(v) for k, v in sorted(_FETCHED.items())},
    }, indent=2) + "\n")


def merge(path: str) -> dict[str, set[str]]:
    """Merge per-process dumps into one {dut: fetched-pins} view."""
    base = Path(path)
    merged: dict[str, set[str]] = {}
    for part in sorted(base.parent.glob(base.name + ".*")):
        data = json.loads(part.read_text())
        for key, pins in data["duts"].items():
            merged.setdefault(key, set()).update(pins)
    return merged
