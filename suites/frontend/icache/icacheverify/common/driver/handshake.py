"""Decoupled (valid/ready) driving for ICache subblocks.

The ICache subblocks expose real ``DecoupledIO`` ports, unlike the BPU
predictors whose inputs are fire-signal driven.

Level propagation
-----------------
DUT inputs are rise-write (see ``DutFactory.initialize_dut_inputs``): a level
driven with ``Set`` is sampled at the next rising edge, and deasserting it also
needs one edge to take effect. A one-edge ``valid`` pulse therefore costs two
edges in total — one carrying the beat and one draining the deassert. Tests
account for both so the reference model stays in lockstep with the RTL.
"""

from __future__ import annotations

from typing import Any
from typing import Callable

from toffee import ClockCycles
from toffee import SyncDriver
from toffee import as_xdata
from toffee.data import drive_data
from toffee.data import iter_data_leaves
from toffee.signals import sample_signal

from icacheverify.common.bundle.bindings import PortBinding


class HandshakeDriver(SyncDriver[Any]):
    """Drive one Decoupled channel and report the edges it consumed."""

    def __init__(
        self,
        binding: PortBinding,
        *,
        valid: Any,
        ready: Any,
        encoder: Callable[[Any], Any] | None = None,
        max_wait_cycles: int = 4096,
    ) -> None:
        self.binding = binding
        self.valid = as_xdata(valid)
        self.ready = as_xdata(ready)
        self.encoder = encoder
        self.max_wait_cycles = max_wait_cycles
        # Edges consumed by the last accepted beat, including the deassert
        # drain edge. Tests use this to advance their model exactly.
        self.last_edges = 0
        signals = [signal for _, signal in iter_data_leaves(binding.bits, binding.name)]
        signals.append(self.valid)
        super().__init__(signals, name=binding.name)

    def _ready_high(self) -> bool:
        return bool(int(sample_signal(self.ready).as_int()) & 1)

    async def _drive_one(self, request: Any):
        values = request if self.encoder is None else self.encoder(request)
        drive_data(self.binding.bits, values, self.binding.name)
        self.last_edges = 0
        waited = 0
        try:
            self.valid.Set(1)
            while True:
                event = await ClockCycles(self.binding.clock, 1)
                waited += 1
                if self._ready_high():
                    break
                if waited >= self.max_wait_cycles:
                    raise TimeoutError(
                        f"{self.binding.name} not accepted in {waited} cycles"
                    )
            self.last_edges = waited
            return event
        finally:
            self.valid.Set(0)

    async def drain(self) -> None:
        """Spend the edge that commits the deasserted ``valid`` level."""
        await ClockCycles(self.binding.clock, 1)
        self.last_edges += 1

    async def send(self, request: Any):
        return await super().send(request)
