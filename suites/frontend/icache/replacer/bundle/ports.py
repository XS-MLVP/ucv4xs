"""Static signal structure of ICacheReplacer.

The adapter exposes two fetch ports of two candidate ways each
(``io.touch.req[request][port]``), plus one victim port whose response is
combinational and whose selection is replayed as a touch one cycle later.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from toffee import Bundle

from suites.frontend.icache.ports.bindings import PortBinding
from suites.frontend.icache.ports.bindings import bind_bundle


@dataclass(frozen=True, slots=True)
class TouchPort:
    """One device port: its two candidate-way beats and the resulting flush."""

    requests: tuple[Any, ...]
    name: str

    @classmethod
    def bind(cls, requests: Any, name: str) -> "TouchPort":
        return cls(requests=tuple(requests), name=name)


@dataclass(frozen=True, slots=True)
class ReplacerPorts:
    touch: tuple[TouchPort, ...]
    victim_request: Any
    victim_way: Any

    @classmethod
    def bind(cls, dut: Any) -> "ReplacerPorts":
        io = bind_bundle(dut, ("io",), name="replacer.io").bits
        # firtool flattens the ``touch.req`` aggregate to a single port name.
        entries = io.touch_req
        touch = tuple(
            TouchPort.bind(
                (entries[request][port] for request in range(len(entries))),
                f"replacer.touch[{port}]",
            )
            for port in range(len(entries[0]))
        )
        return cls(
            touch=touch,
            victim_request=io.victim.req,
            victim_way=io.victim.resp_way,
        )


def touch_binding(dut: Any, port_index: int) -> PortBinding:
    """Bind one device port's whole touch vector as a drivable level."""
    io = bind_bundle(dut, ("io",), name="replacer.io").bits
    entries = io.touch_req
    return PortBinding(
        dut.clock,
        Bundle(
            req=tuple(
                Bundle(
                    valid=entries[request][port_index].valid,
                    vSetIdx=entries[request][port_index].bits.vSetIdx,
                    way=entries[request][port_index].bits.way,
                )
                for request in range(len(entries))
            )
        ),
        f"replacer.touch[{port_index}].req",
    )


def victim_binding(dut: Any) -> PortBinding:
    io = bind_bundle(dut, ("io",), name="replacer.io").bits
    # ``victim`` is a Valid-style bundle whose payload is already a leaf
    # (``vSetIdx``), so the flattened names are ``req_valid``/``req_bits_vSetIdx``.
    return PortBinding(
        dut.clock,
        Bundle(valid=io.victim.req.valid, vSetIdx=io.victim.req.bits_vSetIdx),
        "replacer.victim.req",
    )
