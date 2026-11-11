"""Static signal structure of ICacheMetaInterleavedBank.

The built DUT exposes only ``flushAll`` (the per-set flush port is pruned during
full-SoC lowering) and additionally carries the SRAM wrappers' BIST bore inputs,
which must be held low in functional mode.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from toffee import Bundle

from suites.frontend.icache.testbenches.shared.env.bundle.bindings import PortBinding
from suites.frontend.icache.testbenches.shared.env.bundle.bindings import bind_bundle


@dataclass(frozen=True, slots=True)
class MetaBankPorts:
    read: PortBinding
    read_ready: PortBinding
    write: PortBinding
    write_ready: PortBinding
    flush_all: PortBinding
    response: Any
    mbist: PortBinding
    mbist_response: PortBinding
    sram_control: PortBinding

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
            mbist=PortBinding(dut.clock, Bundle(**{name: getattr(dut, 'boreChildrenBd_bore_' + name)
                for name in ('req', 'all', 'array', 'readen', 'writeen', 'be', 'addr', 'addr_rd', 'indata')}),
                'metabank.mbist'),
            mbist_response=PortBinding(dut.clock, Bundle(ack=dut.boreChildrenBd_bore_ack,
                outdata=dut.boreChildrenBd_bore_outdata), 'metabank.mbist.response'),
            sram_control=PortBinding(dut.clock, Bundle(ways=tuple(Bundle(**{
                name: getattr(dut, 'sigFromSrams_bore' + (f'_{group}' if group else '') + '_' + leaf)
                for name, leaf in dict(hold='ram_hold', bypass='ram_bypass', bp_clken='ram_bp_clken',
                    aux_clk='ram_aux_clk', aux_ckbp='ram_aux_ckbp', mcp_hold='ram_mcp_hold', cgen='cgen').items()})
                for group in range(2))), 'metabank.sram-control'),
        )
