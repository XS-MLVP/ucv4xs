"""Single-DUT fixture; implementation imports are deferred until setup."""
import json

import pytest
from toffee import DriveStable, Execution, RisingEdge, SamplingMonitor, XCommClockBackend

from suites.memblock.lsq import ROOT

SPEC = json.loads((ROOT / "manifest/duts.json").read_text())["duts"]["cam_raw"]


@pytest.fixture(params=("cam_raw",), ids=("cam_raw",))
async def cam_raw(request, dut_factory):
    if request.param != "cam_raw":
        raise ValueError("cam_raw fixture cannot load another DUT")
    from suites.memblock.lsq.testbenches.cam_raw.coverage import FunctionalCoverage as CamCoverage
    from suites.memblock.lsq.testbenches.cam_raw.env.driver import CamDriver
    from suites.memblock.lsq.testbenches.cam_raw.env import CamEnv
    from suites.memblock.lsq.testbenches.cam_raw.model import CamModel
    from suites.memblock.lsq.testbenches.cam_raw.env.ports import Ports as CamPorts

    key, spec = request.param, SPEC
    dut = dut_factory.create(key)
    ports = CamPorts(dut, spec)
    model = CamModel(spec)
    coverage = CamCoverage(key, spec, request.node.nodeid)
    before = SamplingMonitor(DriveStable(dut.clock), capture=ports.sample, capacity=8)
    after = SamplingMonitor(RisingEdge(dut.clock), capture=ports.sample, capacity=8)
    driver = CamDriver(ports)
    backend = XCommClockBackend(dut.GetXClock())
    try:
        async with Execution(backend, max_batch_ticks=16) as execution:
            async with driver, before.start(execution), after.start(execution):
                env = CamEnv(key, spec, driver, before, after, model, coverage)
                await env.idle(3)
                yield env
    finally:
        backend.close()
