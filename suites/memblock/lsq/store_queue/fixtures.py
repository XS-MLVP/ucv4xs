import pytest
from toffee import DriveStable, Execution, RisingEdge, SamplingMonitor, XCommClockBackend

from suites.memblock.lsq.store_queue.coverage import FunctionalCoverage
from suites.memblock.lsq.store_queue.driver import StoreQueueDriver
from suites.memblock.lsq.store_queue.env import StoreQueueEnv
from suites.memblock.lsq.store_queue.model import StoreQueueModel
from suites.memblock.lsq.store_queue.ports import Ports


@pytest.fixture(params=(True,))
async def sq(request, dut_factory):
    dut = dut_factory.create("store_queue")
    ports = Ports(dut)
    before = SamplingMonitor(DriveStable(dut.clock), capture=ports.sample, capacity=8)
    after = SamplingMonitor(RisingEdge(dut.clock), capture=ports.sample, capacity=8)
    driver, backend = StoreQueueDriver(ports), XCommClockBackend(dut.GetXClock())
    try:
        with dut_factory.journal("store_queue.jsonl") as journal, dut_factory.journal("sq_checks.jsonl") as checks, dut_factory.journal("sq_actor.jsonl") as actor_journal:
            async with Execution(backend, max_batch_ticks=16) as execution:
                async with driver, before.start(execution), after.start(execution):
                    env = StoreQueueEnv(driver, before, after, StoreQueueModel() if request.param else None,
                                        FunctionalCoverage(request.node.nodeid), journal, checks, request.node.nodeid)
                    env.actor_journal = actor_journal
                    await env.boot()
                    yield env
    finally:
        backend.close()
