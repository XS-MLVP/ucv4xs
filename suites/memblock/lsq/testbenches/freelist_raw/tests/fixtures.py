"""Single-DUT fixture; implementation imports are deferred until setup."""
import json

import pytest
from toffee import DriveStable, Execution, RisingEdge, SamplingMonitor, XCommClockBackend

from suites.memblock.lsq import ROOT

SPEC = json.loads((ROOT / "manifest/duts.json").read_text())["duts"]["freelist_raw"]


@pytest.fixture(params=("freelist_raw",), ids=("freelist_raw",))
async def freelist_raw(request, dut_factory):
    if request.param != "freelist_raw":
        raise ValueError("freelist_raw fixture cannot load another DUT")
    from suites.memblock.lsq.testbenches.freelist_raw.coverage import FunctionalCoverage
    from suites.memblock.lsq.testbenches.freelist_raw.env.driver import FreeListDriver
    from suites.memblock.lsq.testbenches.freelist_raw.env import FreeListEnv
    from suites.memblock.lsq.testbenches.freelist_raw.model import FreeListModel
    from suites.memblock.lsq.testbenches.freelist_raw.env.ports import Ports

    key, spec = request.param, SPEC
    dut = dut_factory.create(key)
    ports = Ports(dut)
    model = FreeListModel(spec["size"], spec["preallocate"])
    coverage = FunctionalCoverage(key, spec, request.node.nodeid)
    before = SamplingMonitor(DriveStable(dut.clock), capture=ports.sample, capacity=8)
    after = SamplingMonitor(RisingEdge(dut.clock), capture=ports.sample, capacity=8)
    driver = FreeListDriver(ports)
    backend = XCommClockBackend(dut.GetXClock())
    try:
        async with Execution(backend, max_batch_ticks=16) as execution:
            async with driver, before.start(execution), after.start(execution):
                env = FreeListEnv(key, spec, driver, before, after, model, coverage)
                await env.reset()
                yield env
    finally:
        backend.close()
