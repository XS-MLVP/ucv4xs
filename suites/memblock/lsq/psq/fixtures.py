import pytest
from toffee import DriveStable, Execution, RisingEdge, SamplingMonitor, XCommClockBackend

from suites.memblock.lsq.psq.coverage import FunctionalCoverage
from suites.memblock.lsq.psq.driver import PsqDriver
from suites.memblock.lsq.psq.ports import Ports
from suites.memblock.lsq.psq.probe import PsqProbe
from suites.memblock.lsq.psq.env import PsqEnv
from suites.memblock.lsq.psq.model import PsqModel


@pytest.fixture
async def psq(request, dut_factory):
    dut = dut_factory.create("physical_store_queue")
    ports = Ports(dut)
    before = SamplingMonitor(DriveStable(dut.clock), capture=ports.sample, capacity=8)
    after = SamplingMonitor(RisingEdge(dut.clock), capture=ports.sample, capacity=8)
    driver, backend = PsqDriver(ports), XCommClockBackend(dut.GetXClock())
    coverage = FunctionalCoverage(request.node.nodeid)
    try:
        with dut_factory.journal("physical_store_queue.jsonl") as journal, dut_factory.journal("psq_checks.jsonl") as checks:
            async with Execution(backend, max_batch_ticks=16) as execution:
                async with driver, before.start(execution), after.start(execution):
                    env = PsqProbe(driver, before, after, coverage, journal, checks, request.node.nodeid)
                    await env.boot()
                    yield env
    finally:
        backend.close()


@pytest.fixture
async def psq_full(request, dut_factory):
    dut = dut_factory.create("physical_store_queue")
    ports = Ports(dut)
    before = SamplingMonitor(DriveStable(dut.clock), capture=ports.sample, capacity=8)
    after = SamplingMonitor(RisingEdge(dut.clock), capture=ports.sample, capacity=8)
    driver, backend = PsqDriver(ports), XCommClockBackend(dut.GetXClock())
    coverage = FunctionalCoverage(request.node.nodeid)
    try:
        with dut_factory.journal("psq_full.jsonl") as journal, dut_factory.journal("psq_actor.jsonl") as actor_journal:
            async with Execution(backend, max_batch_ticks=16) as execution:
                async with driver, before.start(execution), after.start(execution):
                    env = PsqEnv(driver, before, after, PsqModel(), coverage, journal, actor_journal, request.node.nodeid)
                    await env.boot()
                    yield env
    finally:
        backend.close()
