"""Static signal structure of ICacheMetaArray."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from toffee import Bundle

from suites.frontend.icache.ports.bindings import PortBinding
from suites.frontend.icache.ports.bindings import bind_bundle


@dataclass(frozen=True, slots=True)
class MetaArrayPorts:
    read: PortBinding
    read_ready: PortBinding
    write: PortBinding
    write_ready: PortBinding
    flush_all: PortBinding
    response: Any
    idle_leaves: tuple[Any, ...]

    @classmethod
    def bind(cls, dut: Any) -> "MetaArrayPorts":
        from suites.frontend.icache.ports.bindings import flat_leaf_names

        io = bind_bundle(dut, ("io",), name="metaarray.io").bits
        return cls(
            read=PortBinding(
                dut.clock,
                Bundle(valid=io.read.req.valid,
                       isDoubleLine=io.read.req.bits.isDoubleLine,
                       setIdx=tuple(io.read.req.bits.vSetIdx)),
                "metaarray.read",
            ),
            read_ready=PortBinding(dut.clock, Bundle(ready=io.read.req.ready),
                                   "metaarray.read.ready"),
            write=PortBinding(
                dut.clock,
                Bundle(valid=io.write_req.valid,
                       setIdx=io.write_req.bits.vSetIdx,
                       waymask=io.write_req.bits.waymask,
                       phyTag=io.write_req.bits.entry.meta.phyTag,
                       maybeRvcMap=io.write_req.bits.entry.meta.maybeRvcMap,
                       code=io.write_req.bits.entry.code),
                "metaarray.write",
            ),
            write_ready=PortBinding(dut.clock, Bundle(ready=io.write_req.ready),
                                    "metaarray.write.ready"),
            flush_all=PortBinding(dut.clock, Bundle(flushAll=io.flushAll),
                                  "metaarray.flushAll"),
            response=io.read.resp_entries,
            idle_leaves=tuple(
                getattr(dut, name) for name in flat_leaf_names(dut, "sigFromSrams_bore")
            ),
        )
