"""Explicit composition for one of the two distinct generated pipe payloads."""
from contextlib import asynccontextmanager
from dataclasses import dataclass

from toffee import Execution, XCommClockBackend

from suites.vector.vagq.testbenches.shared.env.native import open_dut
from suites.vector.vagq.testbenches.pipeline.checker import Checker
from suites.vector.vagq.testbenches.pipeline.coverage import Coverage
from suites.vector.vagq.testbenches.pipeline.env.driver import Driver
from suites.vector.vagq.testbenches.pipeline.model import State
from suites.vector.vagq.testbenches.pipeline.env.probe import bind
from suites.vector.vagq.testbenches.pipeline.env.specs import PIPE1
from suites.vector.vagq.testbenches.pipeline.env.specs import Spec
from suites.vector.vagq.testbenches.pipeline.transactions import Beat


@dataclass
class Env:
    dut: object
    spec: Spec
    driver: Driver
    sample: object
    model: State
    checker: Checker
    coverage: Coverage

    async def reset(self):
        await self.driver.reset_dut()
        self.model = State(payload=self.spec.payload_type())

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

    def assert_clean(self):
        if self.checker.board.status.failed:
            raise AssertionError(f'{self.checker.board.name} recorded a mismatch')

    def assert_coverage(self, percent=100):
        self.coverage.group.assert_coverage(percent)

    def finish(self):
        if self.checker.board.status.failed:
            raise AssertionError(f'{self.spec.module} scoreboard recorded a mismatch')


@asynccontextmanager
async def session(output, spec=PIPE1, *, register=None):
    with open_dut(spec.module, output, clocked=True, register=register) as dut:
        ports, sample = bind(dut, spec)
        backend = XCommClockBackend(dut.GetXClock())
        try:
            async with Execution(backend, max_batch_ticks=128):
                env = Env(dut, spec, Driver(dut, ports, spec), sample,
                          State(payload=spec.payload_type()), Checker(spec.group), Coverage(spec))
                yield env
                env.finish()
        finally:
            backend.close()
