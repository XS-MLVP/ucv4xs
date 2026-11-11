"""Manager environment: explicit composition and resource ownership, no pytest API."""
from contextlib import asynccontextmanager
from dataclasses import dataclass

from toffee import Execution, XCommClockBackend

from suites.vector.vagq.testbenches.shared.env.native import open_dut
from suites.vector.vagq.testbenches.manager.env.agent import ManagerAgent
from suites.vector.vagq.testbenches.manager.checker import ManagerChecker
from suites.vector.vagq.testbenches.manager.coverage import ManagerCoverage
from suites.vector.vagq.testbenches.manager.env.ports import Ports


@dataclass(frozen=True)
class ManagerEnv:
    dut: object
    agent: ManagerAgent
    checker: ManagerChecker
    coverage: ManagerCoverage

    @property
    def checked_cycles(self):
        return self.checker.checked_cycles

    @property
    def checked_count(self):
        return self.checker.board.status.checked

    def assert_clean(self):
        if self.checker.board.status.failed:
            raise AssertionError('ManagerChecker recorded a mismatch')

    def override_comparison(self, hook):
        """Install a test hook at the checker comparison seam.

        Used only by the lifecycle selftest to prove that an injected
        comparison failure escapes the environment and releases resources.
        """
        self.checker.board.check = hook


@asynccontextmanager
async def manager_session(output, *, register=None):
    with open_dut('VAGQManager', output, clocked=True, register=register) as dut:
        agent = ManagerAgent(Ports.bind(dut))
        coverage = ManagerCoverage()
        checker = ManagerChecker(coverage)
        backend = XCommClockBackend(dut.GetXClock())
        try:
            async with Execution(backend, max_batch_ticks=128) as execution:
                # Wiring is here, not embedded in the passive monitor or agent.
                async with agent.connect(execution, checker.observe):
                    yield ManagerEnv(dut, agent, checker, coverage)
                    checker.finish()
        finally:
            backend.close()
