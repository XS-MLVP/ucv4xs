"""Explicit cleanup-only native context for deliberately failing selftests."""
from contextlib import asynccontextmanager
from toffee import Execution, XCommClockBackend
from suites.frontend.icache.databank.agent.main import DataBankAgent


@asynccontextmanager
async def running(factory):
    dut = factory.create('databank', coverage_name='databank-runtime-control.dat')
    backend = XCommClockBackend(dut.GetXClock())
    try:
        async with Execution(backend, max_batch_ticks=64) as execution:
            agent = DataBankAgent(dut)
            await agent.start(execution)
            try:
                yield agent
            finally:
                await agent.aclose()
    finally:
        backend.close()
