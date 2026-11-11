import json

import pytest
from toffee import DriveStable, Execution, RisingEdge, SamplingMonitor, XCommClockBackend

from suites.memblock.lsq.testbenches.forward.coverage import FunctionalCoverage
from suites.memblock.lsq.testbenches.forward.env.driver import ForwardDriver
from suites.memblock.lsq.testbenches.forward.env import ForwardEnv
from suites.memblock.lsq.testbenches.forward.model import ForwardModel
from suites.memblock.lsq.testbenches.forward.env.ports import Ports


@pytest.fixture
async def forward(request, dut_factory):
    # Local fixture keeps this work independent of the frozen 31-DUT progress
    # regression, which names its existing test directories explicitly.
    dut = dut_factory.create("forward_module")
    ports = Ports(dut)
    driver = ForwardDriver(ports)
    before = SamplingMonitor(DriveStable(dut.clock), capture=ports.sample, capacity=8)
    after = SamplingMonitor(RisingEdge(dut.clock), capture=ports.sample, capacity=8)
    model, coverage = ForwardModel(), FunctionalCoverage(request.node.nodeid)
    backend = XCommClockBackend(dut.GetXClock())
    try:
        with dut_factory.journal("forward_module.jsonl") as journal:
            async with Execution(backend, max_batch_ticks=16) as execution:
                async with driver, before.start(execution), after.start(execution):
                    env = ForwardEnv(driver, before, after, model, coverage, journal, nodeid=request.node.nodeid)
                    await env.boot()
                    yield env
    finally:
        backend.close()
        with (dut_factory.output / "forward_semantics.json").open("x") as evidence:
            json.dump({"nodeid": request.node.nodeid, "events": coverage.events, "kill_reuse": coverage.kill_reuse}, evidence)
            evidence.write("\n")


class PropertyOnlyModel(ForwardModel):
    """Keep transaction bookkeeping; give up all pin predictions."""

    def expected(self, inp):
        return {}

    def check_physical_safety(self, inp, observed):
        return []


class _NullJournal:
    def write(self, _):
        pass


class _NullCoverage:
    def observe(self, change, tick):
        pass

    def arm(self, names, uids=None, tick=None):
        pass


@pytest.fixture
async def forward_property(request, dut_factory):
    dut = dut_factory.create("forward_module")
    ports = Ports(dut)
    driver = ForwardDriver(ports)
    before = SamplingMonitor(DriveStable(dut.clock), capture=ports.sample, capacity=8)
    after = SamplingMonitor(RisingEdge(dut.clock), capture=ports.sample, capacity=8)
    backend = XCommClockBackend(dut.GetXClock())
    try:
        with dut_factory.journal("forward_property.jsonl"):
            async with Execution(backend, max_batch_ticks=16) as execution:
                async with driver, before.start(execution), after.start(execution):
                    env = ForwardEnv(driver, before, after, PropertyOnlyModel(), _NullCoverage(), _NullJournal(),
                                     nodeid=request.node.nodeid)
                    await env.boot()
                    yield env
    finally:
        backend.close()
