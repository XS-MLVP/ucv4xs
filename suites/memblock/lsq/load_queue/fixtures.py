import pytest
from toffee import DriveStable, Execution, RisingEdge, SamplingMonitor, XCommClockBackend

from suites.memblock.lsq.load_queue.coverage import FunctionalCoverage
from suites.memblock.lsq.load_queue.driver import LoadQueueDriver
from suites.memblock.lsq.load_queue.env import LoadQueueEnv
from suites.memblock.lsq.load_queue.model import LoadQueueModel
from suites.memblock.lsq.load_queue.ports import Ports


@pytest.fixture
async def lq(request, dut_factory):
    dut = dut_factory.create("load_queue")
    ports = Ports(dut)
    before = SamplingMonitor(DriveStable(dut.clock), capture=ports.sample, capacity=8)
    after = SamplingMonitor(RisingEdge(dut.clock), capture=ports.sample, capacity=8)
    driver, backend = LoadQueueDriver(ports), XCommClockBackend(dut.GetXClock())
    try:
        with dut_factory.journal("load_queue.jsonl") as journal, dut_factory.journal("lq_actor.jsonl") as actor:
            async with Execution(backend, max_batch_ticks=16) as execution:
                async with driver, before.start(execution), after.start(execution):
                    env = LoadQueueEnv(driver, before, after, LoadQueueModel(), FunctionalCoverage(request.node.nodeid), journal, request.node.nodeid, actor)
                    await env.boot()
                    yield env
    finally:
        backend.close()
