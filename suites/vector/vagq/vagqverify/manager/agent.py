"""One interface's driver/monitor composition and domain-facing API."""
from contextlib import asynccontextmanager

from toffee import CheckContext, Scoreboard, ScoreboardMode

from .driver import ManagerDriver
from .monitor import ManagerMonitor
from .types import Beat, Offer


class ManagerAgent:
    def __init__(self, ports):
        self.driver = ManagerDriver(ports)
        self.monitor = ManagerMonitor(ports)
        self.launch_board = Scoreboard('manager.intended-beats')
        self.active = False

    @asynccontextmanager
    async def connect(self, execution, on_cycle):
        if self.active:
            raise RuntimeError('Manager agent already connected')
        async with self.driver, self.monitor.observe(execution, on_cycle):
            self.active = True
            try:
                yield self
            finally:
                self.active = False

    async def reset(self, cycles=2):
        if not self.active:
            raise RuntimeError('Manager agent is not connected')
        await self.driver.reset(cycles)

    async def apply(self, beat: Beat):
        """Offer concurrent controls; return the decision, not a fictitious response."""
        if not self.active:
            raise RuntimeError('Manager agent is not connected')
        previous = self.monitor.assembler.completed
        await self.driver.send(beat)
        cycle = self.monitor.latest
        if cycle is None or cycle.index != previous + 1:
            raise AssertionError('control launch has no exactly associated frozen observation')
        self.launch_board.check(expected=beat, actual=cycle.after.beat,
            context=CheckContext(self.launch_board.name, ScoreboardMode.DIRECT,
                                 sequence_id=cycle.index, request=beat))
        return cycle.after.allocation

    async def offer(self, count):
        return await self.apply(Beat(Offer(count)))

    async def recover(self, occupied):
        await self.apply(Beat(recovery=frozenset(occupied)))

    async def stream(self, beats):
        for beat in beats:
            await self.apply(beat)
        # Commit neutral controls, allowing the final preceding beat to act.
        await self.apply(Beat())
