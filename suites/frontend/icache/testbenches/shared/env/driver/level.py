"""Drive persistent signal levels without consuming a clock edge.

``ClockedWriteDriver`` waits at least one cycle per transaction. For DUTs
whose reference model advances per edge, such a hidden cycle silently
desynchronises expectations from the RTL. This driver only writes the level and
returns immediately; the caller owns the clocking policy.
"""

from __future__ import annotations

from typing import Any
from typing import Mapping

from toffee import ClockCycles, SyncDriver
from toffee.data import drive_data, iter_data_leaves

from suites.frontend.icache.testbenches.shared.env.bundle.bindings import PortBinding


class LevelDriver(SyncDriver):
    """Own persistent inputs using SDK claims, without hidden set() edges.

    set() only changes a level; it is not proof of protocol acceptance. The
    optional awaited send() waits one clock after setting the level and leaves
    it driven. Agents still define actual ready/fire and withdrawal semantics.
    """

    def __init__(self, binding: PortBinding) -> None:
        self.binding = binding
        self._closed = False
        super().__init__((signal for _, signal in iter_data_leaves(binding.bits, binding.name)),
                         name=binding.name)

    def set(self, values: Mapping[str, Any]) -> None:
        if self._closed:
            raise RuntimeError(f"{self.binding.name}: level driver is closed")
        self._claim()
        drive_data(self.binding.bits, values, self.binding.name)

    async def _drive_one(self, values):
        self.set(values)
        return await ClockCycles(self.binding.clock, 1)

    async def send(self, values):
        # SyncDriver.send claims before invoking _drive_one. A closed source
        # must not reacquire released inputs merely to reject the later write.
        if self._closed:
            raise RuntimeError(f"{self.binding.name}: level driver is closed")
        return await super().send(values)

    def close(self) -> None:
        super().close()
        self._closed = True
