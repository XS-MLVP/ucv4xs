"""Static signal structure of ICacheWayLookup.

Only names and shapes live here. ``ready`` stays separate from the payload
binding so a driver never writes a DUT output, and monitors bind ``valid``,
``ready`` and ``bits`` together to mark accepted beats.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from toffee import Bundle

from suites.frontend.icache.ports.bindings import PortBinding
from suites.frontend.icache.ports.bindings import bind_bundle


@dataclass(frozen=True, slots=True)
class DecoupledPort:
    """One bound Decoupled channel split into its three roles."""

    valid: Any
    ready: Any
    payload: PortBinding
    name: str

    def valid_binding(self, clock: Any) -> PortBinding:
        """``valid`` as a bindable level, so several ports can commit together."""
        return PortBinding(clock, Bundle(valid=self.valid), f"{self.name}.valid")

    @classmethod
    def bind(cls, clock: Any, node: Any, name: str, *, ready: Any = None,
             payload_key: str = "bits") -> "DecoupledPort":
        keys = node.keys()
        own_ready = node.ready if "ready" in keys else None
        if ready is None:
            ready = own_ready
        if ready is None:
            raise ValueError(f"{name} has no observable ready")
        if payload_key not in keys:
            raise ValueError(f"{name} has no payload leaf {payload_key!r}; keys={sorted(keys)}")
        return cls(
            valid=node.valid,
            ready=ready,
            payload=PortBinding(clock, node[payload_key], f"{name}.bits"),
            name=name,
        )

    def observe(self, clock: Any) -> PortBinding:
        """Bind the handshake triple so monitors see accepted beats only."""
        return PortBinding(
            clock,
            Bundle(valid=self.valid, ready=self.ready, bits=self.payload.bits),
            f"{self.name}.beat",
        )


@dataclass(frozen=True, slots=True)
class WayLookupPorts:
    write: tuple[DecoupledPort, ...]
    read: DecoupledPort
    read_ready: PortBinding
    update: PortBinding
    control: PortBinding
    status: PortBinding

    @classmethod
    def bind(cls, dut: Any) -> "WayLookupPorts":
        io = bind_bundle(dut, ("io",), name="waylookup.io").bits
        # firtool merges the two identical ready outputs into io_write_0_ready,
        # so the second port observes the first port's ready. Keep that
        # sharing explicit instead of treating the missing leaf as an error.
        first = DecoupledPort.bind(dut.clock, io.write[0], "waylookup.write[0]")
        write = [first]
        for index in range(1, len(io.write)):
            write.append(
                DecoupledPort.bind(
                    dut.clock, io.write[index], f"waylookup.write[{index}]",
                    ready=first.ready,
                )
            )
        read = DecoupledPort.bind(
            dut.clock, io.toMainPipe, "waylookup.toMainPipe",
            payload_key="bits_wayLookupInfo",
        )
        return cls(
            write=tuple(write),
            read=read,
            read_ready=PortBinding(
                dut.clock, Bundle(ready=io.toMainPipe.ready), "waylookup.toMainPipe.ready"
            ),
            update=PortBinding(dut.clock, io.update, "waylookup.update"),
            control=PortBinding(
                dut.clock,
                Bundle(
                    flush=io.flush,
                    flushFromBpu_s3_valid=io.flushFromBpu_s3.valid,
                    flushFromBpu_s3_bits_flag=io.flushFromBpu_s3.bits.flag,
                    flushFromBpu_s3_bits_value=io.flushFromBpu_s3.bits.value,
                    fromMainPipe_realTwoFetchValid=io.fromMainPipe_realTwoFetchValid,
                ),
                "waylookup.control",
            ),
            status=PortBinding(dut.clock, Bundle(empty=io.perf_empty), "waylookup.status"),
        )
