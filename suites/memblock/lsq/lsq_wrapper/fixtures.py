import pytest
from toffee import DriveStable, Execution, RisingEdge, SamplingMonitor, XCommClockBackend

from suites.memblock.lsq.lsq_wrapper.coverage import FunctionalCoverage
from suites.memblock.lsq.lsq_wrapper.driver import WrapperDriver
from suites.memblock.lsq.lsq_wrapper.env import WrapperEnv
from suites.memblock.lsq.lsq_wrapper.model import WrapperModel
from suites.memblock.lsq.lsq_wrapper.ports import Ports
from suites.memblock.lsq.lsq_wrapper.probe import PublicProbeEnv


@pytest.fixture
async def wrapper_lsq(request, dut_factory):
    dut = dut_factory.create("lsq_wrapper")
    ports = Ports(dut)
    before = SamplingMonitor(DriveStable(dut.clock), capture=ports.sample, capacity=8)
    after = SamplingMonitor(RisingEdge(dut.clock), capture=ports.sample, capacity=8)
    driver, backend = WrapperDriver(ports), XCommClockBackend(dut.GetXClock())
    try:
        with dut_factory.journal("lsq_wrapper.jsonl") as journal, dut_factory.journal("lsq_checks.jsonl") as checks, dut_factory.journal("lsq_actor.jsonl") as actor:
            async with Execution(backend, max_batch_ticks=16) as execution:
                async with driver, before.start(execution), after.start(execution):
                    env = WrapperEnv(driver, before, after, WrapperModel(), FunctionalCoverage(request.node.nodeid), journal, checks, actor, request.node.nodeid)
                    await env.boot()
                    yield env
    finally:
        backend.close()


@pytest.fixture
async def lsq_probe(request, dut_factory):
    """Explicit protocol-only scope; never pretends to compare all458 outputs."""
    dut = dut_factory.create("lsq_wrapper")
    ports = Ports(dut)
    before = SamplingMonitor(DriveStable(dut.clock), capture=ports.sample, capacity=8)
    after = SamplingMonitor(RisingEdge(dut.clock), capture=ports.sample, capacity=8)
    driver, backend = WrapperDriver(ports), XCommClockBackend(dut.GetXClock())
    try:
        with dut_factory.journal("lsq_probe.jsonl") as journal, dut_factory.journal("lsq_probe_checks.jsonl") as checks, dut_factory.journal("lsq_probe_actor.jsonl") as actor:
            async with Execution(backend, max_batch_ticks=16) as execution:
                async with driver, before.start(execution), after.start(execution):
                    env = PublicProbeEnv(driver, before, after, FunctionalCoverage(request.node.nodeid), journal, checks, actor, request.node.nodeid)
                    await env.boot()
                    yield env
    finally:
        backend.close()
