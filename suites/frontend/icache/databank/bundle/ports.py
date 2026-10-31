"""Static signal structure of ICacheDataBank.

The generated adapter flattens the write channel to ``write_req`` and keeps the
read response as ``resp_entries``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from toffee import Bundle

from suites.frontend.icache.ports.bindings import PortBinding
from suites.frontend.icache.ports.bindings import bind_bundle


@dataclass(frozen=True, slots=True)
class DataBankPorts:
    read: PortBinding
    read_ready: PortBinding
    write: PortBinding
    write_ready: PortBinding
    response: Any
    mbist: PortBinding

    @classmethod
    def bind(cls, dut: Any) -> "DataBankPorts":
        io = bind_bundle(dut, ("io",), name="databank.io").bits
        return cls(
            read=PortBinding(
                dut.clock,
                Bundle(valid=io.read.req.valid,
                       setIdx=tuple(io.read.req.bits.setIdx),
                       waymask=io.read.req.bits.waymask),
                "databank.read",
            ),
            read_ready=PortBinding(dut.clock, Bundle(ready=io.read.req.ready),
                                   "databank.read.ready"),
            write=PortBinding(
                dut.clock,
                Bundle(valid=io.write_req.valid,
                       setIdx=io.write_req.bits.setIdx,
                       waymask=io.write_req.bits.waymask,
                       data=io.write_req.bits.entry.data,
                       code=io.write_req.bits.entry.code),
                "databank.write",
            ),
            write_ready=PortBinding(dut.clock, Bundle(ready=io.write_req.ready),
                                    "databank.write.ready"),
            response=io.read.resp_entries,
            # The MBIST bore interface is idle in normal operation; it must be
            # held low so the macro stays in functional mode.
            mbist=PortBinding(
                dut.clock,
                Bundle(
                    req=dut.boreChildrenBd_bore_req,
                    all=dut.boreChildrenBd_bore_all,
                    be=dut.boreChildrenBd_bore_be,
                    array=dut.boreChildrenBd_bore_array,
                    addr=dut.boreChildrenBd_bore_addr,
                    addr_rd=dut.boreChildrenBd_bore_addr_rd,
                    indata=dut.boreChildrenBd_bore_indata,
                    writeen=dut.boreChildrenBd_bore_writeen,
                    readen=dut.boreChildrenBd_bore_readen,
                ),
                "databank.mbist",
            ),
        )
