"""Single-DUT fixture; implementation imports are deferred until setup."""
import json

import pytest
from toffee import DriveStable, Execution, RisingEdge, SamplingMonitor, XCommClockBackend

from suites.memblock.lsq import ROOT

SPEC = json.loads((ROOT / "manifest/duts.json").read_text())["duts"]["uncache_entry_14"]


@pytest.fixture(params=("uncache_entry_14",), ids=("uncache_entry_14",))
async def uncache_entry_14(request, dut_factory):
    if request.param != "uncache_entry_14":
        raise ValueError("uncache_entry_14 fixture cannot load another DUT")
    from suites.memblock.lsq.testbenches.uncache_entry_14.coverage import FunctionalCoverage as EntryCoverage
    from suites.memblock.lsq.testbenches.uncache_entry_14.env.driver import EntryDriver
    from suites.memblock.lsq.testbenches.uncache_entry_14.env import EntryEnv
    from suites.memblock.lsq.testbenches.uncache_entry_14.model import UncacheEntryModel
    from suites.memblock.lsq.testbenches.uncache_entry_14.env.ports import Ports as EntryPorts

    key, spec = request.param, SPEC
    dut = dut_factory.create(key)
    ports = EntryPorts(dut, spec)
    model = UncacheEntryModel(spec)
    coverage = EntryCoverage(key, spec, request.node.nodeid)
    before = SamplingMonitor(DriveStable(dut.clock), capture=ports.sample, capacity=8)
    after = SamplingMonitor(RisingEdge(dut.clock), capture=ports.sample, capacity=8)
    driver = EntryDriver(ports)
    backend = XCommClockBackend(dut.GetXClock())
    try:
        with dut_factory.journal(f"{key}.jsonl") as trace:
            async with Execution(backend, max_batch_ticks=16) as execution:
                async with driver, before.start(execution), after.start(execution):
                    env = EntryEnv(key, spec, driver, before, after, model, coverage, trace)
                    await env.reset()
                    yield env
    finally:
        backend.close()
