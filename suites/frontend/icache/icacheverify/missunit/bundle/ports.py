"""Static signal structure of ICacheMissUnit.

The TileLink bundles were flattened by the generator, so the memory side is a
plain valid/ready + address/source/data set. Everything else is a direct port.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from toffee import Bundle

from icacheverify.common.bundle.bindings import PortBinding
from icacheverify.common.bundle.bindings import bind_bundle


@dataclass(frozen=True, slots=True)
class MissUnitPorts:
    fetch_req: PortBinding
    fetch_ready: PortBinding
    prefetch_req: PortBinding
    prefetch_ready: PortBinding
    acquire: PortBinding
    acquire_ready: PortBinding
    grant: PortBinding
    victim_req: PortBinding
    victim_way: PortBinding
    resp: PortBinding
    meta_write: PortBinding
    data_write: PortBinding
    fencei: PortBinding
    flush: PortBinding
    wfi_req: PortBinding
    wfi_safe: Any
    idle_leaves: tuple[Any, ...]

    @classmethod
    def bind(cls, dut: Any) -> "MissUnitPorts":
        io = bind_bundle(dut, ("io",), name="missunit.io").bits
        return cls(
            fetch_req=PortBinding(
                dut.clock,
                Bundle(valid=io.fetchReq.valid, blkPAddr=io.fetchReq.bits.blkPAddr,
                       vSetIdx=io.fetchReq.bits.vSetIdx),
                "missunit.fetchReq",
            ),
            fetch_ready=PortBinding(dut.clock, Bundle(ready=io.fetchReq.ready),
                                    "missunit.fetchReq.ready"),
            prefetch_req=PortBinding(
                dut.clock,
                Bundle(valid=io.prefetchReq.valid, blkPAddr=io.prefetchReq.bits.blkPAddr,
                       vSetIdx=io.prefetchReq.bits.vSetIdx),
                "missunit.prefetchReq",
            ),
            prefetch_ready=PortBinding(dut.clock, Bundle(ready=io.prefetchReq.ready),
                                       "missunit.prefetchReq.ready"),
            acquire=PortBinding(
                dut.clock,
                Bundle(valid=io.memAcquire.valid,
                       address=io.memAcquire.bits.address,
                       source=io.memAcquire.bits.source),
                "missunit.memAcquire",
            ),
            acquire_ready=PortBinding(dut.clock, Bundle(ready=io.memAcquire.ready),
                                      "missunit.memAcquire.ready"),
            grant=PortBinding(
                dut.clock,
                Bundle(valid=io.memGrant.valid,
                       source=io.memGrant.bits.source,
                       data=io.memGrant.bits.data,
                       corrupt=io.memGrant.bits.corrupt,
                       denied=io.memGrant.bits.denied,
                       opcode=io.memGrant.bits.opcode),
                "missunit.memGrant",
            ),
            victim_req=PortBinding(
                dut.clock,
                Bundle(valid=io.victim.req.valid, vSetIdx=io.victim.req.bits_vSetIdx),
                "missunit.victim.req",
            ),
            victim_way=PortBinding(dut.clock, Bundle(way=io.victim.resp_way),
                                   "missunit.victim.way"),
            resp=PortBinding(
                dut.clock,
                Bundle(valid=io.resp.valid,
                       blkPAddr=io.resp.bits.blkPAddr,
                       vSetIdx=io.resp.bits.vSetIdx,
                       waymask=io.resp.bits.waymask,
                       corrupt=io.resp.bits.corrupt,
                       denied=io.resp.bits.denied),
                "missunit.resp",
            ),
            meta_write=PortBinding(
                dut.clock,
                Bundle(valid=io.metaWrite_req.valid,
                       vSetIdx=io.metaWrite_req.bits.vSetIdx,
                       waymask=io.metaWrite_req.bits.waymask),
                "missunit.metaWrite",
            ),
            data_write=PortBinding(
                dut.clock,
                Bundle(valid=io.dataWrite_req.valid,
                       vSetIdx=io.dataWrite_req.bits.vSetIdx,
                       waymask=io.dataWrite_req.bits.waymask),
                "missunit.dataWrite",
            ),
            fencei=PortBinding(dut.clock, Bundle(fencei=io.fencei), "missunit.fencei"),
            flush=PortBinding(dut.clock, Bundle(flush=io.flush), "missunit.flush"),
            wfi_req=PortBinding(dut.clock, Bundle(wfiReq=io.wfi.wfiReq), "missunit.wfi"),
            wfi_safe=io.wfi.wfiSafe,
            # This DUT has no SRAM BIST bore ports of its own: the MSHRs read
            # their data through the grant channel, and the arrays are external.
            idle_leaves=tuple(),
        )
