"""Manager's level-control protocol, using toffee ownership and scheduling."""
from dataclasses import dataclass

from toffee import ClockCycles, SyncDriver

from .encoding import encode
from .types import Beat


@dataclass(frozen=True, slots=True)
class _Reset:
    cycles: int


class ManagerDriver(SyncDriver):
    def __init__(self, ports):
        self.ports = ports
        super().__init__([ports.reset, *ports.stimulus.values()], name='manager.controls')
        for signal in (ports.reset, *ports.stimulus.values()):
            signal.AsRiseWrite()

    async def _drive_one(self, beat):
        if isinstance(beat, _Reset):
            # Reset is serialized with ordinary beats by SyncDriver, not a
            # second coroutine allowed to drive the same interface concurrently.
            self.ports.stimulus.drive(encode(Beat()))
            await ClockCycles(self.ports.clock, 1)
            self.ports.reset.Set(1)
            await ClockCycles(self.ports.clock, beat.cycles)
            self.ports.reset.Set(0)
            return await ClockCycles(self.ports.clock, 2)
        self.ports.stimulus.drive(encode(beat))
        # This event means new levels are committed. The previous levels were
        # consumed by the RTL edge. It is NOT a hardware acceptance response.
        return await ClockCycles(self.ports.clock, 1)

    async def reset(self, cycles=2):
        if not isinstance(cycles, int) or cycles < 1:
            raise ValueError('reset must span at least one cycle')
        return await self.send(_Reset(cycles))
