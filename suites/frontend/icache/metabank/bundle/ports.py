"""Static signal structure of ICacheMetaInterleavedBank.

The built DUT exposes only ``flushAll`` (the per-set flush port is pruned during
full-SoC lowering) and additionally carries the SRAM wrappers' BIST bore inputs,
which must be held low in functional mode.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from toffee import Bundle

from suites.frontend.icache.ports.bindings import PortBinding
from suites.frontend.icache.ports.bindings import bind_bundle


def _flat_leaf_names(dut: Any, root: str) -> list[str]:
    """Flatten one signals.json subtree into the generator's leaf names."""
    import json
    from pathlib import Path
    import sys

    module = sys.modules[type(dut).__module__]
    schema = json.loads(Path(module.__file__).with_name("signals.json").read_text())
    names: list[str] = []

    def walk(node: dict, prefix: str) -> None:
        for key, value in node.items():
            flat = f"{prefix}_{key}"
            if isinstance(value, dict) and value.get("_"):
                names.append(flat)
            elif isinstance(value, dict):
                walk(value, flat)

    walk(schema[root], root)
    return names


@dataclass(frozen=True, slots=True)
class MetaBankPorts:
    read: PortBinding
    read_ready: PortBinding
    write: PortBinding
    write_ready: PortBinding
    flush_all: PortBinding
    response: Any
    idle_leaves: tuple[Any, ...]

    @classmethod
    def bind(cls, dut: Any) -> "MetaBankPorts":
        io = bind_bundle(dut, ("io",), name="metabank.io").bits
        return cls(
            read=PortBinding(
                dut.clock,
                Bundle(valid=io.read.req.valid, setIdx=io.read.req.bits_setIdx),
                "metabank.read",
            ),
            read_ready=PortBinding(dut.clock, Bundle(ready=io.read.req.ready),
                                   "metabank.read.ready"),
            write=PortBinding(
                dut.clock,
                Bundle(valid=io.write_req.valid,
                       setIdx=io.write_req.bits.setIdx,
                       waymask=io.write_req.bits.waymask,
                       phyTag=io.write_req.bits.entry.meta.phyTag,
                       maybeRvcMap=io.write_req.bits.entry.meta.maybeRvcMap,
                       code=io.write_req.bits.entry.code),
                "metabank.write",
            ),
            write_ready=PortBinding(dut.clock, Bundle(ready=io.write_req.ready),
                                    "metabank.write.ready"),
            flush_all=PortBinding(dut.clock, Bundle(flushAll=io.flushAll),
                                  "metabank.flushAll"),
            response=io.read.resp_entries,
            # The SRAM wrappers' BIST bore inputs contain Vec indices, which a
            # Bundle cannot name; they are all held low, so they are collected
            # as flat leaves instead of a structured binding.
            idle_leaves=tuple(
                getattr(dut, name) for name in _flat_leaf_names(dut, "sigFromSrams_bore")
            ),
        )
