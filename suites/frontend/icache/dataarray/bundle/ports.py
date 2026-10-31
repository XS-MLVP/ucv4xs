"""Static signal structure of ICacheDataArray."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from toffee import Bundle

from suites.frontend.icache.ports.bindings import PortBinding
from suites.frontend.icache.ports.bindings import bind_bundle
from suites.frontend.icache.ports.bindings import flat_leaf_names


@dataclass(frozen=True, slots=True)
class DataArrayPorts:
    read: PortBinding
    read_ready: PortBinding
    write: PortBinding
    write_ready: PortBinding
    response: Any
    idle_leaves: tuple[Any, ...]

    @classmethod
    def bind(cls, dut: Any) -> "DataArrayPorts":
        io = bind_bundle(dut, ("io",), name="dataarray.io").bits
        requests = io.read.req.bits
        entries = io.write_req.bits.entries
        return cls(
            read=PortBinding(
                dut.clock,
                Bundle(
                    valid=io.read.req.valid,
                    req=tuple(
                        Bundle(
                            valid=getattr(request, "valid", None),
                            bankSel=tuple(request.bits.bankSel),
                            vSetIdx=tuple(request.bits.vSetIdx),
                            waymask=tuple(request.bits.waymask),
                        )
                        if getattr(request, "valid", None) is not None else
                        Bundle(
                            bankSel=tuple(request.bits.bankSel),
                            vSetIdx=tuple(request.bits.vSetIdx),
                            waymask=tuple(request.bits.waymask),
                        )
                        for request in requests
                    ),
                ),
                "dataarray.read",
            ),
            read_ready=PortBinding(dut.clock, Bundle(ready=io.read.req.ready),
                                   "dataarray.read.ready"),
            write=PortBinding(
                dut.clock,
                Bundle(valid=io.write_req.valid,
                       setIdx=io.write_req.bits.vSetIdx,
                       waymask=io.write_req.bits.waymask,
                       entries=tuple(
                           Bundle(data=entry.data, code=entry.code)
                           for entry in entries)),
                "dataarray.write",
            ),
            write_ready=PortBinding(dut.clock, Bundle(ready=io.write_req.ready),
                                    "dataarray.write.ready"),
            response=io.read.resp,
            idle_leaves=tuple(
                getattr(dut, name) for name in flat_leaf_names(dut, "sigFromSrams_bore")
            ),
        )
