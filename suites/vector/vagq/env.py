"""Manager environment: explicit composition and resource ownership, no pytest API."""
from contextlib import asynccontextmanager
from dataclasses import dataclass

from toffee import Execution, XCommClockBackend

from .native import open_dut
from .manager.agent import ManagerAgent
from .manager.checker import ManagerChecker
from .manager.coverage import ManagerCoverage
from .manager.ports import Ports


@dataclass(frozen=True)
class ManagerEnv:
    dut: object
    agent: ManagerAgent
    checker: ManagerChecker
    coverage: ManagerCoverage


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
