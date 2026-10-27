"""Explicit opt-in endpoint references; root fixtures/shared models stay frozen."""
import json

import pytest
from toffee import DriveStable, Execution, RisingEdge, SamplingMonitor, XCommClockBackend

from lsqverify.native import ROOT
from lsqverify.raw.coverage import FunctionalCoverage as RawCoverage
from lsqverify.raw.driver import RawDriver
from lsqverify.raw.env import RawEnv
from lsqverify.raw.ports import Ports as RawPorts
from lsqverify.replay.coverage import FunctionalCoverage as ReplayCoverage
from lsqverify.replay.driver import ReplayDriver
from lsqverify.replay.env import ReplayEnv
from lsqverify.replay.ports import Ports as ReplayPorts
from lsqverify.lsq_wrapper.coverage import FunctionalCoverage as WrapperCoverage
from lsqverify.lsq_wrapper.driver import WrapperDriver
from lsqverify.lsq_wrapper.env import WrapperEnv
from lsqverify.lsq_wrapper.ports import Ports as WrapperPorts
from lsqverify.sq_endpoint.model import ExclusiveRawModel, ExclusiveReplayModel, ExclusiveWrapperModel


@pytest.fixture
async def raw(request,dut_factory):
    key="load_queue_raw"
    spec=json.loads((ROOT/"manifest/duts.json").read_text())["duts"][key]
    dut=dut_factory.create(key)
    ports=RawPorts(dut,spec)
    before=SamplingMonitor(DriveStable(dut.clock),capture=ports.sample,capacity=8)
    after=SamplingMonitor(RisingEdge(dut.clock),capture=ports.sample,capacity=8)
    driver,backend=RawDriver(ports),XCommClockBackend(dut.GetXClock())
    try:
        with dut_factory.journal(f"{key}.jsonl") as journal:
            async with Execution(backend,max_batch_ticks=16) as execution:
                async with driver,before.start(execution),after.start(execution):
                    env=RawEnv(key,spec,driver,before,after,ExclusiveRawModel(spec),RawCoverage(key,request.node.nodeid),journal)
                    await env.reset()
                    yield env
    finally:backend.close()


@pytest.fixture
async def replay(request,dut_factory):
    key="load_queue_replay"
    dut=dut_factory.create(key)
    ports=ReplayPorts(dut)
    before=SamplingMonitor(DriveStable(dut.clock),capture=ports.sample,capacity=8)
    after=SamplingMonitor(RisingEdge(dut.clock),capture=ports.sample,capacity=8)
    driver,backend=ReplayDriver(ports),XCommClockBackend(dut.GetXClock())
    try:
        with dut_factory.journal(f"{key}.jsonl") as journal:
            async with Execution(backend,max_batch_ticks=16) as execution:
                async with driver,before.start(execution),after.start(execution):
                    env=ReplayEnv(driver,before,after,ExclusiveReplayModel(),ReplayCoverage(request.node.nodeid),journal)
                    await env.reset()
                    yield env
    finally:backend.close()


@pytest.fixture
async def lsq(request,dut_factory):
    dut=dut_factory.create("lsq_wrapper")
    ports=WrapperPorts(dut)
    before=SamplingMonitor(DriveStable(dut.clock),capture=ports.sample,capacity=8)
    after=SamplingMonitor(RisingEdge(dut.clock),capture=ports.sample,capacity=8)
    driver,backend=WrapperDriver(ports),XCommClockBackend(dut.GetXClock())
    try:
        with dut_factory.journal("lsq_wrapper.jsonl") as journal,dut_factory.journal("lsq_checks.jsonl") as checks,dut_factory.journal("lsq_actor.jsonl") as actor:
            async with Execution(backend,max_batch_ticks=16) as execution:
                async with driver,before.start(execution),after.start(execution):
                    env=WrapperEnv(driver,before,after,ExclusiveWrapperModel(),WrapperCoverage(request.node.nodeid),journal,checks,actor,request.node.nodeid)
                    await env.boot()
                    yield env
    finally:backend.close()
