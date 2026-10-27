"""Explicit StoreDataCtrl driver/model/checker/coverage composition."""
from contextlib import asynccontextmanager
from dataclasses import dataclass

from toffee import Execution, XCommClockBackend

from ..native import open_dut
from .checker import Checker
from .coverage import Coverage
from .driver import Driver
from .model import State
from .probe import bind
from .types import Beat


@dataclass
class Env:
    dut: object
    driver: Driver
    sample: object
    model: State
    checker: Checker
    coverage: Coverage

    async def reset(self):
        await self.driver.reset_dut()
        self.model = State()

    async def step(self, beat: Beat):
        self.driver.drive(beat)
        before_expected = self.model.observe(beat)
        before_actual = self.sample()
        self.checker.compare(before_expected, before_actual, phase='before', beat=beat)
        self.coverage.sample(self.model, beat)
        await self.driver.tick()
        following = self.model.following(beat)
        after_expected = following.observe(beat)
        after_actual = self.sample()
        self.checker.compare(after_expected, after_actual, phase='after', beat=beat)
        self.model = following
        self.checker.complete()

    def finish(self):
        if self.checker.board.status.failed:
            raise AssertionError('StoreDataCtrl scoreboard recorded a mismatch')


@asynccontextmanager
async def session(output, *, register=None):
    with open_dut('StoreDataCtrl', output, clocked=True, register=register) as dut:
        ports, sample = bind(dut)
        backend = XCommClockBackend(dut.GetXClock())
        try:
            async with Execution(backend, max_batch_ticks=128):
                env = Env(dut, Driver(ports), sample, State(), Checker(), Coverage())
                yield env
                env.finish()
        finally:
            backend.close()
