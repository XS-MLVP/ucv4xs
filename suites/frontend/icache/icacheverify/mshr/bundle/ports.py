"""Static signal structure of ICacheMshr.

The DUT is a one-entry MSHR with flat ports: no TileLink bundle survives
lowering, so the external helper only needs to model the miss unit's side
(accept the acquire, later signal completion).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from toffee import Bundle

from icacheverify.common.bundle.bindings import PortBinding
from icacheverify.common.bundle.bindings import bind_bundle


@dataclass(frozen=True, slots=True)
class MshrPorts:
    request: PortBinding
    lookup: tuple[PortBinding, ...]
    acquire: PortBinding
    acquire_ready: PortBinding
    info: PortBinding
    fencei: PortBinding
    invalid: PortBinding
    victim_way: PortBinding
    wfi: PortBinding
    ready: Any
    hit: tuple[Any, ...]
    wfi_safe: Any

    @classmethod
    def bind(cls, dut: Any) -> "MshrPorts":
        io = bind_bundle(dut, ("io",), name="mshr.io").bits
        return cls(
            request=PortBinding(
                dut.clock,
                Bundle(valid=io.req.valid, blkPAddr=io.req.bits.blkPAddr,
                       vSetIdx=io.req.bits.vSetIdx),
                "mshr.req",
            ),
            lookup=tuple(
                PortBinding(
                    dut.clock,
                    Bundle(blkPAddr=entry.req_bits.blkPAddr,
                           vSetIdx=entry.req_bits.vSetIdx),
                    f"mshr.lookUps[{index}]",
                )
                for index, entry in enumerate(io.lookUps)
            ),
            # Outputs are observed only; the accept level is a separate input
            # binding so a driver never writes an output port.
            acquire=PortBinding(
                dut.clock,
                Bundle(valid=io.acquire.valid,
                       block=io.acquire.bits.acquire.address,
                       vSetIdx=io.acquire.bits.vSetIdx),
                "mshr.acquire",
            ),
            acquire_ready=PortBinding(
                dut.clock, Bundle(ready=io.acquire.ready), "mshr.acquire.ready"
            ),
            info=PortBinding(
                dut.clock,
                Bundle(valid=io.info.valid, blkPAddr=io.info.bits.blkPAddr,
                       vSetIdx=io.info.bits.vSetIdx, way=io.info.bits.way),
                "mshr.info",
            ),
            fencei=PortBinding(dut.clock, Bundle(fencei=io.fencei), "mshr.fencei"),
            invalid=PortBinding(dut.clock, Bundle(invalid=io.invalid), "mshr.invalid"),
            victim_way=PortBinding(dut.clock, Bundle(victimWay=io.victimWay),
                                   "mshr.victimWay"),
            wfi=PortBinding(dut.clock, Bundle(wfiReq=io.wfi.wfiReq), "mshr.wfi"),
            ready=io.req.ready,
            hit=tuple(entry.resp_hit for entry in io.lookUps),
            wfi_safe=io.wfi.wfiSafe,
        )
