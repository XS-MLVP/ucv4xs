"""suites.frontend.bpu.drivers.signal components."""

from __future__ import annotations
from typing import Any
from typing import Callable
from toffee import AsyncSingleCycleDriver as CoreAsyncSingleCycleDriver
from toffee import ClockCycles
from toffee import Bundle
from toffee import SyncDriver
from toffee import as_xdata
from toffee.data import drive_data
from toffee.data import iter_data_leaves
from suites.frontend.bpu.ports.bindings import PortBinding
from suites.frontend.bpu.ports.bindings import PulseBinding
from suites.frontend.bpu.transactions.cycle import CycleTransaction


class _OwnedDriver(SyncDriver[Any]):
    def __init__(self, binding: PortBinding | PulseBinding) -> None:
        self.binding = binding
        leaves = [
            signal
            for _, signal in iter_data_leaves(binding.bits, binding.name)
        ]
        if isinstance(binding, PulseBinding):
            leaves.insert(0, binding.valid)
        super().__init__(leaves, name=binding.name)


class ClockedWriteDriver(_OwnedDriver):
    """Write a persistent level and hide the rise-write launch cycle.

    ``cycles`` is how long send waits; it does not deassert the written value.
    This is a clocked control writer, not an accepted-transfer channel.
    """

    binding: PortBinding

    async def _drive_one(self, transaction: Any):
        tx = transaction if isinstance(transaction, CycleTransaction) else CycleTransaction(transaction)
        drive_data(self.binding.bits, tx.values, self.binding.name)
        return await ClockCycles(self.binding.clock, tx.cycles + 1)


class AsyncSingleCycleDriver(CoreAsyncSingleCycleDriver[Any, Any]):
    """Bind the BPU port description to Reactor's single-cycle driver."""

    def __init__(
        self,
        binding: PortBinding,
        *,
        idle: Any,
        encoder: Callable[[Any], Any] | None = None,
        capacity: int = 64,
    ) -> None:
        self.binding = binding
        super().__init__(
            binding.clock,
            binding.bits,
            idle=idle,
            name=binding.name,
            encoder=encoder,
            capacity=capacity,
        )


class PulseDriver(_OwnedDriver):
    """Drive structured pulse bursts with the framework's exclusive send policy."""

    binding: PulseBinding

    async def send(self, transaction: Any):
        return await self.send_many((transaction,))

    async def send_many(self, transactions: tuple[Any, ...]):
        if not transactions:
            raise ValueError("pulse burst must not be empty")
        return await super().send(transactions)

    async def _drive_one(self, transactions):
        try:
            for transaction in transactions:
                drive_data(self.binding.bits, transaction, f"{self.binding.name}.bits")
                self.binding.valid.Set(1)
                await ClockCycles(self.binding.clock, 1)
        finally:
            self.binding.valid.Set(0)
        return await ClockCycles(self.binding.clock, 1)


class ResetDriver(_OwnedDriver):
    """Own and sequence the common synchronous reset protocol."""

    def __init__(self, dut: Any) -> None:
        self.dut = dut
        super().__init__(PortBinding(
            as_xdata(dut.clock),
            # Bundle keeps reset under the same data abstraction as other drivers.
            Bundle(reset=dut.reset),
            "reset",
        ))

    async def send(self, transaction: int = 3):
        return await super().send(transaction)

    async def _drive_one(self, transaction: int):
        cycles = int(transaction)
        self.binding.bits.drive({"reset": 1})
        await ClockCycles(self.dut.clock, cycles)
        self.binding.bits.drive({"reset": 0})
        # One edge captures the last asserted-reset cycle and commits the
        # deassertion; the next edge is the first active DUT cycle.
        return await ClockCycles(self.dut.clock, 2)
