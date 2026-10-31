from __future__ import annotations

import json
import pytest
from toffee import DriveStable, Execution, RisingEdge, SamplingMonitor, XCommClockBackend

from suites.memblock.lsq.native import DutFactory, ROOT
from suites.memblock.lsq.freelist.coverage import FunctionalCoverage
from suites.memblock.lsq.freelist.driver import FreeListDriver
from suites.memblock.lsq.freelist.env import FreeListEnv
from suites.memblock.lsq.freelist.model import FreeListModel
from suites.memblock.lsq.freelist.ports import Ports
from suites.memblock.lsq.cam.coverage import FunctionalCoverage as CamCoverage
from suites.memblock.lsq.cam.driver import CamDriver
from suites.memblock.lsq.cam.env import CamEnv
from suites.memblock.lsq.cam.model import CamModel
from suites.memblock.lsq.cam.ports import Ports as CamPorts
from suites.memblock.lsq.age.coverage import FunctionalCoverage as AgeCoverage
from suites.memblock.lsq.age.driver import AgeDriver
from suites.memblock.lsq.age.env import AgeEnv
from suites.memblock.lsq.age.model import AgeModel
from suites.memblock.lsq.age.ports import Ports as AgePorts
from suites.memblock.lsq.vlq.coverage import FunctionalCoverage as VlqCoverage
from suites.memblock.lsq.vlq.driver import VirtualLoadQueueDriver
from suites.memblock.lsq.vlq.env import VirtualLoadQueueEnv
from suites.memblock.lsq.vlq.model import VirtualLoadQueueModel
from suites.memblock.lsq.vlq.ports import Ports as VlqPorts
from suites.memblock.lsq.rar.coverage import FunctionalCoverage as RarCoverage
from suites.memblock.lsq.rar.driver import RarDriver
from suites.memblock.lsq.rar.env import RarEnv
from suites.memblock.lsq.rar.model import LoadQueueRarModel
from suites.memblock.lsq.rar.ports import Ports as RarPorts
from suites.memblock.lsq.raw.coverage import FunctionalCoverage as RawCoverage
from suites.memblock.lsq.raw.driver import RawDriver
from suites.memblock.lsq.raw.env import RawEnv
from suites.memblock.lsq.raw.model import LoadQueueRawModel
from suites.memblock.lsq.raw.ports import Ports as RawPorts
from suites.memblock.lsq.uncache_entry.coverage import FunctionalCoverage as EntryCoverage
from suites.memblock.lsq.uncache_entry.driver import EntryDriver
from suites.memblock.lsq.uncache_entry.env import EntryEnv
from suites.memblock.lsq.uncache_entry.model import UncacheEntryModel
from suites.memblock.lsq.uncache_entry.ports import Ports as EntryPorts
from suites.memblock.lsq.load_uncache.probe import ProbeEnv as LoadUncacheProbeEnv, PublicDriver, PublicPorts
from suites.memblock.lsq.load_uncache.env import LoadUncacheEnv
from suites.memblock.lsq.replay.coverage import FunctionalCoverage as ReplayCoverage
from suites.memblock.lsq.replay.driver import ReplayDriver
from suites.memblock.lsq.replay.env import ReplayEnv
from suites.memblock.lsq.replay.model import ReplayModel
from suites.memblock.lsq.replay.ports import Ports as ReplayPorts
from suites.memblock.lsq.enter_sbuffer.coverage import FunctionalCoverage as EnterSbufferCoverage
from suites.memblock.lsq.enter_sbuffer.driver import EnterSbufferDriver
from suites.memblock.lsq.enter_sbuffer.env import EnterSbufferEnv
from suites.memblock.lsq.enter_sbuffer.model import EnterSbufferModel
from suites.memblock.lsq.enter_sbuffer.ports import Ports as EnterSbufferPorts
from suites.memblock.lsq.unalign.coverage import FunctionalCoverage as UnalignCoverage
from suites.memblock.lsq.unalign.driver import UnalignDriver
from suites.memblock.lsq.unalign.env import UnalignEnv
from suites.memblock.lsq.unalign.model import UnalignModel
from suites.memblock.lsq.unalign.ports import Ports as UnalignPorts

pytest_plugins = ("ucv.pytest_selftest",)

SPECS = json.loads((ROOT / "manifest/duts.json").read_text())["duts"]

from suites.memblock.lsq.deq.fixtures import deq, deq_full
from suites.memblock.lsq.fail_review.fixtures import review_dut
from suites.memblock.lsq.forward.fixtures import forward
from suites.memblock.lsq.load_queue.fixtures import lq
from suites.memblock.lsq.local_reset.fixtures import local_reset_lsq
from suites.memblock.lsq.lsq_wrapper.fixtures import lsq_probe, wrapper_lsq
from suites.memblock.lsq.psq.fixtures import psq, psq_full
from suites.memblock.lsq.sq_endpoint.fixtures import sq_lsq, sq_raw, sq_replay
from suites.memblock.lsq.store_queue.fixtures import sq
from suites.memblock.lsq.vsq.fixtures import vsq


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
async def root_raw(request, dut_factory):
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
async def root_replay(request, dut_factory):
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

def _test_path(request):
    return request.node.path.as_posix()


@pytest.fixture
def raw(request):
    """Route the public RAW fixture to the directory-specific implementation."""
    if "/sq_endpoint/" in _test_path(request):
        return request.getfixturevalue("sq_raw")
    return request.getfixturevalue("root_raw")


@pytest.fixture
def replay(request):
    """Route the public replay fixture to the directory-specific implementation."""
    if "/sq_endpoint/" in _test_path(request):
        return request.getfixturevalue("sq_replay")
    return request.getfixturevalue("root_replay")


@pytest.fixture
def lsq(request):
    """Route the whole-LSQ fixture used by wrapper/probe directories."""
    path = _test_path(request)
    if "/local_reset/" in path:
        return request.getfixturevalue("local_reset_lsq")
    if "/sq_endpoint/" in path:
        return request.getfixturevalue("sq_lsq")
    return request.getfixturevalue("wrapper_lsq")
