import pytest
from toffee import DriveStable, Execution, RisingEdge, SamplingMonitor, XCommClockBackend

from suites.memblock.lsq.deq.coverage import FunctionalCoverage
from suites.memblock.lsq.deq.driver import DeqDriver
from suites.memblock.lsq.deq.ports import Ports
from suites.memblock.lsq.deq.probe import ProbeEnv
from suites.memblock.lsq.deq.env import DeqEnv
from suites.memblock.lsq.deq.model import DeqModel


@pytest.fixture
async def deq(request, dut_factory):
    dut = dut_factory.create("deq_module")
    ports = Ports(dut)
    before = SamplingMonitor(DriveStable(dut.clock), capture=ports.sample, capacity=8)
    after = SamplingMonitor(RisingEdge(dut.clock), capture=ports.sample, capacity=8)
    driver, backend = DeqDriver(ports), XCommClockBackend(dut.GetXClock())
    coverage = FunctionalCoverage(request.node.nodeid)
    try:
        with dut_factory.journal("deq_module.jsonl") as journal, dut_factory.journal("deq_checks.jsonl") as checks:
            async with Execution(backend, max_batch_ticks=16) as execution:
                async with driver, before.start(execution), after.start(execution):
                    env = ProbeEnv(driver, before, after, coverage, journal, checks, request.node.nodeid)
                    await env.boot()
                    yield env
    finally:
        backend.close()


@pytest.fixture
async def deq_full(request, dut_factory):
    dut = dut_factory.create("deq_module")
    ports = Ports(dut)
    before = SamplingMonitor(DriveStable(dut.clock), capture=ports.sample, capacity=8)
    after = SamplingMonitor(RisingEdge(dut.clock), capture=ports.sample, capacity=8)
    driver, backend = DeqDriver(ports), XCommClockBackend(dut.GetXClock())
    coverage = FunctionalCoverage(request.node.nodeid)
    try:
        with dut_factory.journal("deq_full.jsonl") as journal, dut_factory.journal("deq_psq.jsonl") as agent_journal:
            async with Execution(backend, max_batch_ticks=16) as execution:
                async with driver, before.start(execution), after.start(execution):
                    env = DeqEnv(driver, before, after, DeqModel(), coverage, journal, request.node.nodeid, agent_journal)
                    await env.boot()
                    yield env
    finally:
        backend.close()
