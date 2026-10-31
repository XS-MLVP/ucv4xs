import json

import pytest
from toffee import DriveStable, Execution, RisingEdge, SamplingMonitor, XCommClockBackend

from suites.memblock.lsq.vsq.coverage import FunctionalCoverage
from suites.memblock.lsq.vsq.driver import VsqDriver
from suites.memblock.lsq.vsq.env import VsqEnv
from suites.memblock.lsq.vsq.model import VsqModel
from suites.memblock.lsq.vsq.ports import Ports


@pytest.fixture
async def vsq(request, dut_factory):
    dut = dut_factory.create("virtual_store_queue")
    ports = Ports(dut)
    before = SamplingMonitor(DriveStable(dut.clock), capture=ports.sample, capacity=8)
    after = SamplingMonitor(RisingEdge(dut.clock), capture=ports.sample, capacity=8)
    model, coverage = VsqModel(), FunctionalCoverage(request.node.nodeid)
    driver, backend = VsqDriver(ports), XCommClockBackend(dut.GetXClock())
    try:
        with dut_factory.journal("virtual_store_queue.jsonl") as journal:
            async with Execution(backend, max_batch_ticks=16) as execution:
                async with driver, before.start(execution), after.start(execution):
                    env = VsqEnv(driver, before, after, model, coverage, journal, request.node.nodeid)
                    await env.boot()
                    yield env
    finally:
        backend.close()
        with (dut_factory.output / "vsq_semantics.json").open("x") as proof:
            json.dump({"nodeid": request.node.nodeid, "events": coverage.events}, proof)
            proof.write("\n")
