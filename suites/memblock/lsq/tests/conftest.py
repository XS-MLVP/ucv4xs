from __future__ import annotations

import json
import pytest
from toffee import DriveStable, Execution, RisingEdge, SamplingMonitor, XCommClockBackend

from lsqverify.native import DutFactory, ROOT
from lsqverify.freelist.coverage import FunctionalCoverage
from lsqverify.freelist.driver import FreeListDriver
from lsqverify.freelist.env import FreeListEnv
from lsqverify.freelist.model import FreeListModel
from lsqverify.freelist.ports import Ports
from lsqverify.cam.coverage import FunctionalCoverage as CamCoverage
from lsqverify.cam.driver import CamDriver
from lsqverify.cam.env import CamEnv
from lsqverify.cam.model import CamModel
from lsqverify.cam.ports import Ports as CamPorts
from lsqverify.age.coverage import FunctionalCoverage as AgeCoverage
from lsqverify.age.driver import AgeDriver
from lsqverify.age.env import AgeEnv
from lsqverify.age.model import AgeModel
from lsqverify.age.ports import Ports as AgePorts
from lsqverify.vlq.coverage import FunctionalCoverage as VlqCoverage
from lsqverify.vlq.driver import VirtualLoadQueueDriver
from lsqverify.vlq.env import VirtualLoadQueueEnv
from lsqverify.vlq.model import VirtualLoadQueueModel
from lsqverify.vlq.ports import Ports as VlqPorts
from lsqverify.rar.coverage import FunctionalCoverage as RarCoverage
from lsqverify.rar.driver import RarDriver
from lsqverify.rar.env import RarEnv
from lsqverify.rar.model import LoadQueueRarModel
from lsqverify.rar.ports import Ports as RarPorts
from lsqverify.raw.coverage import FunctionalCoverage as RawCoverage
from lsqverify.raw.driver import RawDriver
from lsqverify.raw.env import RawEnv
from lsqverify.raw.model import LoadQueueRawModel
from lsqverify.raw.ports import Ports as RawPorts
from lsqverify.uncache_entry.coverage import FunctionalCoverage as EntryCoverage
from lsqverify.uncache_entry.driver import EntryDriver
from lsqverify.uncache_entry.env import EntryEnv
from lsqverify.uncache_entry.model import UncacheEntryModel
from lsqverify.uncache_entry.ports import Ports as EntryPorts
from lsqverify.load_uncache.probe import ProbeEnv as LoadUncacheProbeEnv, PublicDriver, PublicPorts
from lsqverify.load_uncache.env import LoadUncacheEnv
from lsqverify.replay.coverage import FunctionalCoverage as ReplayCoverage
from lsqverify.replay.driver import ReplayDriver
from lsqverify.replay.env import ReplayEnv
from lsqverify.replay.model import ReplayModel
from lsqverify.replay.ports import Ports as ReplayPorts
from lsqverify.enter_sbuffer.coverage import FunctionalCoverage as EnterSbufferCoverage
from lsqverify.enter_sbuffer.driver import EnterSbufferDriver
from lsqverify.enter_sbuffer.env import EnterSbufferEnv
from lsqverify.enter_sbuffer.model import EnterSbufferModel
from lsqverify.enter_sbuffer.ports import Ports as EnterSbufferPorts
from lsqverify.unalign.coverage import FunctionalCoverage as UnalignCoverage
from lsqverify.unalign.driver import UnalignDriver
from lsqverify.unalign.env import UnalignEnv
from lsqverify.unalign.model import UnalignModel
from lsqverify.unalign.ports import Ports as UnalignPorts

SPECS = json.loads((ROOT / "manifest/duts.json").read_text())["duts"]


def pytest_addoption(parser):
    group=parser.getgroup("LSQ diagnostics")
    group.addoption("--lsq-trace",action="store_true",help="Explicit per-cycle JSON debug; OFF by default")
    group.addoption("--lsq-trace-max-mb",type=int,default=16,help="Per journal debug cap in MiB (default16)")
    group.addoption("--lsq-waves",action="store_true",help="Explicit native waveforms; OFF by default")


@pytest.fixture
def dut_factory(request, tmp_path):
    if not request.config.getoption("toffee_output", default=None):
        raise pytest.UsageError("native LSQ tests must run via python -m toffee run")
    limit=request.config.getoption("lsq_trace_max_mb")
    if limit<1:raise pytest.UsageError("--lsq-trace-max-mb must be positive")
    factory = DutFactory(request.getfixturevalue("toffee_register_dut"), tmp_path,nodeid=request.node.nodeid,
                         trace=request.config.getoption("lsq_trace"),trace_max_bytes=limit*1024*1024,
                         waveforms=request.config.getoption("lsq_waves"))
    try:
        yield factory
    finally:
        factory.close()


@pytest.fixture(params=tuple(k for k in SPECS if k.startswith("freelist_")),
                ids=tuple(k for k in SPECS if k.startswith("freelist_")))
async def freelist(request, dut_factory):
    key, spec = request.param, SPECS[request.param]
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


@pytest.fixture(params=tuple(k for k in SPECS if k.startswith("cam_")),
                ids=tuple(k for k in SPECS if k.startswith("cam_")))
async def cam(request, dut_factory):
    key, spec = request.param, SPECS[request.param]
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


@pytest.fixture(params=tuple(k for k in SPECS if k.startswith("uncache_entry_")),
                ids=tuple(k for k in SPECS if k.startswith("uncache_entry_")))
async def entry(request, dut_factory):
    key, spec = request.param, SPECS[request.param]
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
