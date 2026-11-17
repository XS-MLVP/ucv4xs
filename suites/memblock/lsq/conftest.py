from __future__ import annotations

import json
import pytest
from toffee import DriveStable, Execution, RisingEdge, SamplingMonitor, XCommClockBackend

from suites.memblock.lsq.testbenches.shared.env.dut import DutFactory
from suites.memblock.lsq.testbenches.shared.env.dut import ROOT
from suites.memblock.lsq.testbenches.age.coverage import FunctionalCoverage as AgeCoverage
from suites.memblock.lsq.testbenches.age.env.driver import AgeDriver
from suites.memblock.lsq.testbenches.age.env import AgeEnv
from suites.memblock.lsq.testbenches.age.model import AgeModel
from suites.memblock.lsq.testbenches.age.env.ports import Ports as AgePorts
from suites.memblock.lsq.testbenches.vlq.coverage import FunctionalCoverage as VlqCoverage
from suites.memblock.lsq.testbenches.vlq.env.driver import VirtualLoadQueueDriver
from suites.memblock.lsq.testbenches.vlq.env import VirtualLoadQueueEnv
from suites.memblock.lsq.testbenches.vlq.model import VirtualLoadQueueModel
from suites.memblock.lsq.testbenches.vlq.env.ports import Ports as VlqPorts
from suites.memblock.lsq.testbenches.rar.coverage import FunctionalCoverage as RarCoverage
from suites.memblock.lsq.testbenches.rar.env.driver import RarDriver
from suites.memblock.lsq.testbenches.rar.env import RarEnv
from suites.memblock.lsq.testbenches.rar.model import LoadQueueRarModel
from suites.memblock.lsq.testbenches.rar.env.ports import Ports as RarPorts
from suites.memblock.lsq.testbenches.raw.coverage import FunctionalCoverage as RawCoverage
from suites.memblock.lsq.testbenches.raw.env.driver import RawDriver
from suites.memblock.lsq.testbenches.raw.env import RawEnv
from suites.memblock.lsq.testbenches.raw.model import LoadQueueRawModel
from suites.memblock.lsq.testbenches.raw.env.ports import Ports as RawPorts
from suites.memblock.lsq.testbenches.load_uncache.env.probe import ProbeEnv as LoadUncacheProbeEnv
from suites.memblock.lsq.testbenches.load_uncache.env.probe import PublicDriver
from suites.memblock.lsq.testbenches.load_uncache.env.probe import PublicPorts
from suites.memblock.lsq.testbenches.load_uncache.env import LoadUncacheEnv
from suites.memblock.lsq.testbenches.replay.coverage import FunctionalCoverage as ReplayCoverage
from suites.memblock.lsq.testbenches.replay.env.driver import ReplayDriver
from suites.memblock.lsq.testbenches.replay.env import ReplayEnv
from suites.memblock.lsq.testbenches.replay.model import ReplayModel
from suites.memblock.lsq.testbenches.replay.env.ports import Ports as ReplayPorts
from suites.memblock.lsq.testbenches.enter_sbuffer.coverage import FunctionalCoverage as EnterSbufferCoverage
from suites.memblock.lsq.testbenches.enter_sbuffer.env.driver import EnterSbufferDriver
from suites.memblock.lsq.testbenches.enter_sbuffer.env import EnterSbufferEnv
from suites.memblock.lsq.testbenches.enter_sbuffer.model import EnterSbufferModel
from suites.memblock.lsq.testbenches.enter_sbuffer.env.ports import Ports as EnterSbufferPorts
from suites.memblock.lsq.testbenches.unalign.coverage import FunctionalCoverage as UnalignCoverage
from suites.memblock.lsq.testbenches.unalign.env.driver import UnalignDriver
from suites.memblock.lsq.testbenches.unalign.env import UnalignEnv
from suites.memblock.lsq.testbenches.unalign.model import UnalignModel
from suites.memblock.lsq.testbenches.unalign.env.ports import Ports as UnalignPorts

from suites.memblock.lsq.testbenches.freelist_rar.tests.fixtures import freelist_rar
from suites.memblock.lsq.testbenches.freelist_raw.tests.fixtures import freelist_raw
from suites.memblock.lsq.testbenches.freelist_replay.tests.fixtures import freelist_replay
from suites.memblock.lsq.testbenches.freelist_uncache.tests.fixtures import freelist_uncache
from suites.memblock.lsq.testbenches.cam_rar.tests.fixtures import cam_rar
from suites.memblock.lsq.testbenches.cam_raw.tests.fixtures import cam_raw
from suites.memblock.lsq.testbenches.cam_mask.tests.fixtures import cam_mask
from suites.memblock.lsq.testbenches.uncache_entry_0.tests.fixtures import uncache_entry_0
from suites.memblock.lsq.testbenches.uncache_entry_1.tests.fixtures import uncache_entry_1
from suites.memblock.lsq.testbenches.uncache_entry_2.tests.fixtures import uncache_entry_2
from suites.memblock.lsq.testbenches.uncache_entry_3.tests.fixtures import uncache_entry_3
from suites.memblock.lsq.testbenches.uncache_entry_4.tests.fixtures import uncache_entry_4
from suites.memblock.lsq.testbenches.uncache_entry_5.tests.fixtures import uncache_entry_5
from suites.memblock.lsq.testbenches.uncache_entry_6.tests.fixtures import uncache_entry_6
from suites.memblock.lsq.testbenches.uncache_entry_7.tests.fixtures import uncache_entry_7
from suites.memblock.lsq.testbenches.uncache_entry_8.tests.fixtures import uncache_entry_8
from suites.memblock.lsq.testbenches.uncache_entry_9.tests.fixtures import uncache_entry_9
from suites.memblock.lsq.testbenches.uncache_entry_10.tests.fixtures import uncache_entry_10
from suites.memblock.lsq.testbenches.uncache_entry_11.tests.fixtures import uncache_entry_11
from suites.memblock.lsq.testbenches.uncache_entry_12.tests.fixtures import uncache_entry_12
from suites.memblock.lsq.testbenches.uncache_entry_13.tests.fixtures import uncache_entry_13
from suites.memblock.lsq.testbenches.uncache_entry_14.tests.fixtures import uncache_entry_14
from suites.memblock.lsq.testbenches.uncache_entry_15.tests.fixtures import uncache_entry_15

pytest_plugins = ("ucv.pytest_selftest",)

SPECS = json.loads((ROOT / "manifest/duts.json").read_text())["duts"]

from suites.memblock.lsq.testbenches.deq.tests.fixtures import deq
from suites.memblock.lsq.testbenches.deq.tests.fixtures import deq_full
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.scenarios.fail_review.fixtures import review_dut
from suites.memblock.lsq.testbenches.forward.tests.fixtures import forward
from suites.memblock.lsq.testbenches.forward.tests.fixtures import forward_property
from suites.memblock.lsq.testbenches.load_queue.tests.fixtures import lq
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.scenarios.local_reset.fixtures import local_reset_lsq
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.fixtures import lsq_probe, wrapper_lsq as lsq
from suites.memblock.lsq.testbenches.psq.tests.fixtures import psq
from suites.memblock.lsq.testbenches.psq.tests.fixtures import psq_full
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.scenarios.sq_endpoint.fixtures import sq_lsq
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.scenarios.sq_endpoint.fixtures import sq_raw
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.scenarios.sq_endpoint.fixtures import sq_replay
from suites.memblock.lsq.testbenches.store_queue.tests.fixtures import sq
from suites.memblock.lsq.testbenches.vsq.tests.fixtures import vsq


def pytest_addoption(parser):
    group=parser.getgroup("LSQ diagnostics")
    group.addoption("--lsq-trace",action="store_true",help="Explicit per-cycle JSON debug; OFF by default")
    group.addoption("--lsq-trace-max-mb",type=int,default=16,help="Per journal debug cap in MiB (default16)")
    group.addoption("--lsq-waves",action="store_true",help="Explicit native waveforms; OFF by default")


@pytest.fixture
def dut_factory(request, tmp_path, monkeypatch):
    if not request.config.getoption("toffee_output", default=None):
        raise pytest.UsageError("native LSQ tests must run via python -m toffee run")
    monkeypatch.chdir(tmp_path)
    limit=request.config.getoption("lsq_trace_max_mb")
    if limit<1:raise pytest.UsageError("--lsq-trace-max-mb must be positive")
    factory = DutFactory(request.getfixturevalue("toffee_register_dut"), tmp_path,nodeid=request.node.nodeid,
                         trace=request.config.getoption("lsq_trace"),trace_max_bytes=limit*1024*1024,
                         waveforms=request.config.getoption("lsq_waves"))
    try:
        yield factory
    finally:
        factory.close()




@pytest.fixture
async def age(request, dut_factory):
    key = "age_replay"
    spec = SPECS[key]
    dut = dut_factory.create(key)
    ports = AgePorts(dut, spec)
    model = AgeModel(spec["size"])
    coverage = AgeCoverage(key, request.node.nodeid)
    before = SamplingMonitor(DriveStable(dut.clock), capture=ports.sample, capacity=8)
    after = SamplingMonitor(RisingEdge(dut.clock), capture=ports.sample, capacity=8)
    driver = AgeDriver(ports)
    backend = XCommClockBackend(dut.GetXClock())
    try:
        async with Execution(backend, max_batch_ticks=16) as execution:
            async with driver, before.start(execution), after.start(execution):
                env = AgeEnv(key, spec, driver, before, after, model, coverage)
                await env.reset()
                yield env
    finally:
        backend.close()




@pytest.fixture
async def vlq(request, dut_factory):
    key = "virtual_load_queue"
    spec = SPECS[key]
    dut = dut_factory.create(key)
    ports = VlqPorts(dut, spec)
    model = VirtualLoadQueueModel(spec)
    coverage = VlqCoverage(key, request.node.nodeid)
    before = SamplingMonitor(DriveStable(dut.clock), capture=ports.sample, capacity=8)
    after = SamplingMonitor(RisingEdge(dut.clock), capture=ports.sample, capacity=8)
    driver = VirtualLoadQueueDriver(ports)
    backend = XCommClockBackend(dut.GetXClock())
    try:
        with dut_factory.journal(f"{key}.jsonl") as trace:
            async with Execution(backend, max_batch_ticks=16) as execution:
                async with driver, before.start(execution), after.start(execution):
                    env = VirtualLoadQueueEnv(key, spec, driver, before, after, model, coverage, trace)
                    await env.reset()
                    yield env
    finally:
        backend.close()


@pytest.fixture
async def rar(request, dut_factory):
    key = "load_queue_rar"
    spec = SPECS[key]
    dut = dut_factory.create(key)
    ports = RarPorts(dut, spec)
    model = LoadQueueRarModel(spec)
    coverage = RarCoverage(key, request.node.nodeid)
    before = SamplingMonitor(DriveStable(dut.clock), capture=ports.sample, capacity=8)
    after = SamplingMonitor(RisingEdge(dut.clock), capture=ports.sample, capacity=8)
    driver = RarDriver(ports)
    backend = XCommClockBackend(dut.GetXClock())
    try:
        with dut_factory.journal(f"{key}.jsonl") as trace:
            async with Execution(backend, max_batch_ticks=16) as execution:
                async with driver, before.start(execution), after.start(execution):
                    env = RarEnv(key, spec, driver, before, after, model, coverage, trace)
                    await env.reset()
                    yield env
    finally:
        backend.close()


@pytest.fixture
async def raw(request, dut_factory):
    key = "load_queue_raw"
    spec = SPECS[key]
    dut = dut_factory.create(key)
    ports = RawPorts(dut, spec)
    model = LoadQueueRawModel(spec)
    coverage = RawCoverage(key, request.node.nodeid)
    before = SamplingMonitor(DriveStable(dut.clock), capture=ports.sample, capacity=8)
    after = SamplingMonitor(RisingEdge(dut.clock), capture=ports.sample, capacity=8)
    driver = RawDriver(ports)
    backend = XCommClockBackend(dut.GetXClock())
    try:
        with dut_factory.journal(f"{key}.jsonl") as trace:
            async with Execution(backend, max_batch_ticks=16) as execution:
                async with driver, before.start(execution), after.start(execution):
                    env = RawEnv(key, spec, driver, before, after, model, coverage, trace)
                    await env.reset()
                    yield env
    finally:
        backend.close()




@pytest.fixture
async def load_uncache_probe(request, dut_factory):
    key = "load_queue_uncache"
    dut = dut_factory.create(key)
    ports = PublicPorts(dut)
    before = SamplingMonitor(DriveStable(dut.clock), capture=ports.sample, capacity=8)
    after = SamplingMonitor(RisingEdge(dut.clock), capture=ports.sample, capacity=8)
    driver = PublicDriver(ports)
    backend = XCommClockBackend(dut.GetXClock())
    try:
        with dut_factory.journal(f"{key}.jsonl") as journal, dut_factory.journal("public-checks.jsonl") as checks:
            async with Execution(backend, max_batch_ticks=16) as execution:
                async with driver, before.start(execution), after.start(execution):
                    env = LoadUncacheProbeEnv(ports, driver, before, after, journal, checks, request.node.nodeid)
                    await env.reset()
                    yield env
    finally:
        backend.close()


@pytest.fixture
async def load_uncache(request, dut_factory):
    key = "load_queue_uncache"
    dut = dut_factory.create(key)
    ports = PublicPorts(dut)
    before = SamplingMonitor(DriveStable(dut.clock), capture=ports.sample, capacity=8)
    after = SamplingMonitor(RisingEdge(dut.clock), capture=ports.sample, capacity=8)
    driver = PublicDriver(ports)
    backend = XCommClockBackend(dut.GetXClock())
    try:
        with dut_factory.journal(f"{key}.jsonl") as journal, dut_factory.journal("public-checks.jsonl") as checks:
            async with Execution(backend, max_batch_ticks=16) as execution:
                async with driver, before.start(execution), after.start(execution):
                    env = LoadUncacheEnv(ports, driver, before, after, journal, checks, request.node.nodeid)
                    await env.reset()
                    yield env
    finally:
        backend.close()


@pytest.fixture
async def replay(request, dut_factory):
    dut = dut_factory.create("load_queue_replay")
    ports = ReplayPorts(dut)
    driver = ReplayDriver(ports)
    before = SamplingMonitor(DriveStable(dut.clock), capture=ports.sample, capacity=8)
    after = SamplingMonitor(RisingEdge(dut.clock), capture=ports.sample, capacity=8)
    coverage = ReplayCoverage(request.node.nodeid)
    model = ReplayModel()
    backend = XCommClockBackend(dut.GetXClock())
    try:
        with dut_factory.journal("load_queue_replay.jsonl") as journal:
            async with Execution(backend, max_batch_ticks=16) as execution:
                async with driver, before.start(execution), after.start(execution):
                    env = ReplayEnv(driver, before, after, model, coverage, journal)
                    await env.reset()
                    yield env
    finally:
        backend.close()


@pytest.fixture
async def enter_sbuffer(request, dut_factory):
    key = "enter_sbuffer_queue"
    dut = dut_factory.create(key)
    ports = EnterSbufferPorts(dut)
    driver = EnterSbufferDriver(ports)
    before = SamplingMonitor(DriveStable(dut.clock), capture=ports.sample, capacity=8)
    after = SamplingMonitor(RisingEdge(dut.clock), capture=ports.sample, capacity=8)
    model, coverage = EnterSbufferModel(), EnterSbufferCoverage(request.node.nodeid)
    backend = XCommClockBackend(dut.GetXClock())
    try:
        with dut_factory.journal(f"{key}.jsonl") as journal:
            async with Execution(backend, max_batch_ticks=16) as execution:
                async with driver, before.start(execution), after.start(execution):
                    env = EnterSbufferEnv(driver, before, after, model, coverage, journal)
                    await env.reset()
                    yield env
    finally:
        backend.close()


@pytest.fixture
async def unalign(request, dut_factory):
    key = "unalign_queue"
    dut = dut_factory.create(key)
    ports = UnalignPorts(dut)
    driver = UnalignDriver(ports)
    before = SamplingMonitor(DriveStable(dut.clock), capture=ports.sample, capacity=8)
    after = SamplingMonitor(RisingEdge(dut.clock), capture=ports.sample, capacity=8)
    model, coverage = UnalignModel(), UnalignCoverage(request.node.nodeid)
    backend = XCommClockBackend(dut.GetXClock())
    try:
        with dut_factory.journal(f"{key}.jsonl") as journal:
            async with Execution(backend, max_batch_ticks=16) as execution:
                async with driver, before.start(execution), after.start(execution):
                    env = UnalignEnv(driver, before, after, model, coverage, journal)
                    await env.reset()
                    yield env
    finally:
        backend.close()
