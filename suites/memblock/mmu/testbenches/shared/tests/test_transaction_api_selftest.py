"""Pure-Python self-checks of MMU transaction-API seams.

These do not construct a native DUT.  They exercise the handshake/validation
contracts of the environment methods added during the transaction-boundary
adaptation: acceptance must be sampled on the real firing cycle, response
collection must count completed handshakes and advance the final consume
edge, multi-port input is validated before any write, snapshots are copies,
and named structural channel operations are not generic pin forwarders.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from suites.memblock.mmu.testbenches.bitmap.env.bitmap import BitmapEnv
from suites.memblock.mmu.testbenches.l2tlb.env.l2tlb import L2TlbEnv
from suites.memblock.mmu.testbenches.llptw.env.llptw import LlptwEnv
from suites.memblock.mmu.testbenches.ptw.env.ptw_walker import PtwEnv
from suites.memblock.mmu.testbenches.ptwcache.env.ptwcache import CacheReq, PtwCacheEnv
from suites.memblock.mmu.testbenches.ptwrepeater.env.ptw import FilterEnv, Req, RepeaterEnv
from suites.memblock.mmu.testbenches.tlb.env import TlbEnv
from suites.memblock.mmu.testbenches.tlbn.env import TlbNonBlockEnv

pytestmark = pytest.mark.selftest

READY_CASES = ((1, 1), (1, 0), (0, 1), (0, 0))


class Signal:
    def __init__(self, value: int = 0) -> None:
        self.value = value

    def Set(self, value: int) -> None:
        self.value = value


def _dut() -> SimpleNamespace:
    return SimpleNamespace(RefreshComb=lambda: None)


def _install_ready_cycle(env, signal, before: int, after: int,
                         fires: list[bool]) -> None:
    async def edge() -> None:
        fires.append(bool(signal.value and env.req_ready.value))
        signal.value = after

    env.edge = edge
    env.req_ready.value = before


async def test_offer_acceptance_is_the_same_cycle_fire():
    """0->1 must not report fire and 1->0 must not report a miss.

    The same node also replays the repeater's own request/handshake phase with
    a real ``RepeaterEnv`` over fake signals, so the helper names used by the
    structural-stress case must be actual class methods that drive the frozen
    per-edge levels.
    """
    for env_type, attrs, signal_name in (
            (FilterEnv, ("req_valid", "req_vpn", "req_s2", "req_getgpa"),
             "req_valid"),
            (RepeaterEnv, ("req_valid", "req_vpn", "req_s2"), "req_valid")):
        for before, after in READY_CASES:
            env = env_type.__new__(env_type)
            for name in attrs:
                setattr(env, name, Signal())
            env.req_ready = Signal(before)
            env.dut = _dut()
            fires: list[bool] = []
            _install_ready_cycle(env, getattr(env, signal_name), before, after, fires)
            if env_type is FilterEnv:
                reported = await env.offer_request(Req(0x20000))
            else:
                reported = await env.offer_second_request(0x20000)
            assert reported is fires[0], (env_type.__name__, before, after)

    for name in ("set_ptw_ready", "begin_request_stream", "stream_request",
                 "end_request_stream"):
        assert callable(getattr(RepeaterEnv, name, None)), (
            f"RepeaterEnv.{name} must be a real method")

    env = RepeaterEnv.__new__(RepeaterEnv)
    env.req_valid = Signal()
    env.req_vpn = Signal()
    env.req_s2 = Signal()
    env.req_ready = Signal(1)
    env.resp_ready = Signal(0)
    env.ptw_ready = Signal(0)
    env.dut = _dut()
    levels: list[tuple[int, int, int]] = []

    async def edge() -> None:
        levels.append((env.ptw_ready.value, env.resp_ready.value,
                       env.req_valid.value))

    env.edge = edge
    for endpoint in (1, 0):
        env.req_valid.Set(endpoint)
        env.set_ptw_ready(0)
        env.set_resp_ready(1)
        env.begin_request_stream()
        env.stream_request((1 << 38) - 1 if endpoint else 0,
                           3 if endpoint else 0)
        await env.edge()
        await env.end_request_stream()
        await env.accept_ptw()
    # Frozen trace rows for each endpoint: request, release, PTW accept.
    assert levels == [(0, 1, 1), (0, 1, 0), (1, 1, 0)] * 2, levels


async def test_cache_offer_acceptance_is_the_same_cycle_fire():
    for before, after in READY_CASES:
        env = PtwCacheEnv.__new__(PtwCacheEnv)
        env.req = {name: Signal() for name in
                   ("valid", "ready", "vpn", "s2xlate", "source", "is_first",
                    "is_hptw", "hptw_id")}
        env.req["ready"].Set(before)
        env.dut = _dut()
        fires: list[bool] = []

        async def edge() -> None:
            fires.append(bool(env.req["valid"].value and env.req["ready"].value))
            env.req["ready"].value = after

        env.edge = edge
        reported = await env.offer_request(CacheReq(vpn=0x20000))
        assert reported is fires[0], (before, after)


def _fake_collector(ready: int = 1, valid: int = 1):
    env = L2TlbEnv.__new__(L2TlbEnv)
    env.resp = {"valid": Signal(valid), "ready": Signal(ready), "s1_tag": Signal(17)}
    fires: list[bool] = []
    services: list[int] = []

    async def edge() -> None:
        fires.append(bool(env.resp["valid"].value and env.resp["ready"].value))

    async def service_memory(cycles: int) -> None:
        for _ in range(cycles):
            services.append(1)
            await edge()

    env.edge = edge
    env.service_memory = service_memory
    return env, fires, services


async def test_collect_responses_counts_only_ready_valid_fires():
    env, fires, _services = _fake_collector(ready=0)
    assert await env.collect_responses(1, max_cycles=3) == ()
    assert fires == [False, False, False]


async def test_collect_responses_advances_the_final_consume_edge():
    env, fires, services = _fake_collector(ready=1)
    snaps = await env.collect_responses(2, max_cycles=5)
    assert len(snaps) == 2 and len(services) == 2
    assert fires == [True, True]
    # No de-duplication: a held valid/ready pair is still visible as two
    # samples, so callers' own identity assertions can catch a real duplicate.
    assert snaps[0]["s1_tag"] == snaps[1]["s1_tag"]


async def test_collect_responses_rejects_bad_count_or_port_before_any_edge():
    for count, port in ((0, 0), (-1, 0), (True, 0), (1, 2), (1, -1), (1, True)):
        env, fires, services = _fake_collector()
        with pytest.raises((TypeError, ValueError)):
            await env.collect_responses(count, max_cycles=2, port=port)
        assert fires == [] and services == [], (count, port)


def _l2_ports():
    env = L2TlbEnv.__new__(L2TlbEnv)
    env.req, env.req1 = [
        {name: Signal(int(name == "ready"))
         for name in ("ready", "valid", "vpn", "s2xlate")}
        for _ in range(2)
    ]
    env.dut = _dut()
    fires: list[tuple[int, int, int]] = []

    async def service_memory(cycles: int) -> None:
        for _ in range(cycles):
            for port, req in enumerate((env.req, env.req1)):
                if req["valid"].value and req["ready"].value:
                    fires.append((req["vpn"].value, req["s2xlate"].value, port))

    env.service_memory = service_memory
    return env, fires


async def test_issue_ports_keeps_distinct_port_identity():
    env, fires = _l2_ports()
    accepted = await env.issue_ports([(10, 0, 0), (20, 0, 1)])
    assert accepted == [True, True]
    assert sorted(fires) == [(10, 0, 0), (20, 0, 1)]


async def test_issue_ports_rejects_bad_input_before_any_write():
    for requests in ([(10, 0, 0), (20, 0, 0)], [(10, 0, 99)], [(10, 0, -1)],
                     [(10, 0, True)], [(10, 0)], [("10", 0, 0)],
                     [(10, True, 0)], [], "not-a-list"):
        env, fires = _l2_ports()
        with pytest.raises((TypeError, ValueError)):
            await env.issue_ports(requests)
        assert fires == [], requests
        for req in (env.req, env.req1):
            assert req["valid"].value == 0


def _tlbn_fake():
    env = TlbNonBlockEnv.__new__(TlbNonBlockEnv)
    env.ports = [
        {"req": {"valid": Signal(), "vaddr": Signal(), "fullva": Signal()}}
        for _ in range(4)
    ]
    env.dut = _dut()
    env._set = lambda signal, value: signal.Set(value)
    return env


async def test_tlbn_issue_ports_rejects_bad_lists_before_any_write():
    for vaddrs in ([1, 2, 3, 4, 5], [], [True], "not-a-list"):
        env = _tlbn_fake()
        with pytest.raises((TypeError, ValueError)):
            await env.issue_ports(vaddrs)
        for entry in env.ports:
            assert entry["req"]["valid"].value == 0


async def test_tlbn_issue_rejects_bad_port_before_any_write():
    for port in (-1, 99, True, "0"):
        env = _tlbn_fake()
        with pytest.raises((TypeError, ValueError)):
            await env.issue(port, 0x1000)
        for entry in env.ports:
            assert entry["req"]["valid"].value == 0


def test_response_snapshot_does_not_expose_live_state():
    env = BitmapEnv.__new__(BitmapEnv)
    env.resp = {name: Signal(value) for name, value in
                (("valid", 1), ("cf", 1), ("id", 7))}
    env.cfs = [Signal(1), Signal(0), Signal(1)]
    snap = env.response_snapshot()
    assert snap == {"valid": 1, "cf": 1, "id": 7, "cfs": [1, 0, 1]}
    snap["cfs"][0] = 0
    snap["valid"] = 0
    assert env.cfs[0].value == 1 and env.resp["valid"].value == 1
    again = env.response_snapshot()
    assert again is not snap and again["cfs"] is not snap["cfs"]


def test_nested_response_snapshot_copies_inner_dicts_and_lists():
    env = PtwCacheEnv.__new__(PtwCacheEnv)
    env.resp = {
        "valid": Signal(1),
        "bitmap_cfs": [Signal(1), Signal(0)],
        "bitmap_ptes": [Signal(5)],
        "toHptw": {"tag": Signal(3), "ppn": Signal(9)},
    }
    snap = env.response_snapshot()
    snap["bitmap_cfs"][0] = 0
    snap["bitmap_ptes"].append(1)
    snap["toHptw"]["tag"] = 0
    assert env.resp["bitmap_cfs"][0].value == 1
    assert env.resp["bitmap_ptes"][0].value == 5
    assert env.resp["toHptw"]["tag"].value == 3
    assert len(env.resp["bitmap_ptes"]) == 1


def test_storage_invalid_way_count_is_vacancy_count():
    env = TlbEnv.__new__(TlbEnv)
    env.model = SimpleNamespace(
        storage=SimpleNamespace(tlbfa=SimpleNamespace(valid=[1] * 47 + [0])))
    assert env.storage_invalid_way_count() == 1
    env.model.storage.tlbfa.valid = [1] * 48
    assert env.storage_invalid_way_count() == 0


def test_structural_ptw_response_is_a_named_channel_operation():
    env = FilterEnv.__new__(FilterEnv)
    env.ptw_resp_pins = {name: Signal() for name in
                         ("s2xlate", "s1_entry_tag", "s1_entry_ppn",
                          "s2_entry_tag", "s2_entry_ppn", "s1_entry_asid")}
    env.ptw_resp_valid = Signal()
    env.dut = _dut()
    env.drive_structural_ptw_response(
        s2xlate=3, s1_entry_tag=7, s1_entry_ppn=9, s2_entry_tag=11,
        s2_entry_ppn=13)
    assert env.ptw_resp_pins["s1_entry_asid"].value == 0
    assert {name for name, pin in env.ptw_resp_pins.items() if pin.value} == {
        "s2xlate", "s1_entry_tag", "s1_entry_ppn", "s2_entry_tag",
        "s2_entry_ppn"}
    # Unspecified leaves keep their current stress value; filling selected
    # payload bits must not silently drop the rest of the all-ones endpoint.
    for name in ("s1_entry_asid", "s2xlate", "s1_entry_tag", "s1_entry_ppn",
                 "s2_entry_tag", "s2_entry_ppn"):
        env.ptw_resp_pins[name].Set(1)
    env.drive_structural_ptw_response(s2xlate=0)
    assert env.ptw_resp_pins["s2xlate"].value == 0
    assert all(env.ptw_resp_pins[name].value == 1 for name in
               ("s1_entry_asid", "s1_entry_tag", "s1_entry_ppn",
                "s2_entry_tag", "s2_entry_ppn"))
    # Releasing valid keeps the payload stress levels.
    env.drive_ptw_response_valid(1)
    env.clear_ptw_response()
    assert env.ptw_resp_valid.value == 0
    assert env.ptw_resp_pins["s1_entry_asid"].value == 1
    assert env.ptw_resp_pins["s2_entry_ppn"].value == 1
    # Same contract on the bitmap response channel: dropping valid must not
    # clear the unrelated cf stress bit.
    bitmap_env = PtwEnv.__new__(PtwEnv)
    bitmap_env.bitmap = {"resp_valid": Signal(), "resp_cf": Signal()}
    bitmap_env.dut = _dut()
    bitmap_env.drive_structural_bitmap_resp(1, cf=1)
    assert (bitmap_env.bitmap["resp_valid"].value,
            bitmap_env.bitmap["resp_cf"].value) == (1, 1)
    bitmap_env.drive_structural_bitmap_resp(0)
    assert (bitmap_env.bitmap["resp_valid"].value,
            bitmap_env.bitmap["resp_cf"].value) == (0, 1)
    # A rejected level must not partially drive the channel: validation runs
    # before any Set, so both valid and the untouched cf keep their values.
    with pytest.raises(ValueError):
        bitmap_env.drive_structural_bitmap_resp(1, cf=2)
    assert (bitmap_env.bitmap["resp_valid"].value,
            bitmap_env.bitmap["resp_cf"].value) == (0, 1)
    with pytest.raises(ValueError):
        bitmap_env.drive_structural_bitmap_resp(2)
    assert (bitmap_env.bitmap["resp_valid"].value,
            bitmap_env.bitmap["resp_cf"].value) == (0, 1)


def test_ptw_hptw_queue_takes_named_fields_not_an_open_dict():
    env = PtwEnv.__new__(PtwEnv)
    env.hptw_queue = []
    env.queue_hptw_response(resp_gpf=1, resp_tag=0x1234)
    assert env.hptw_queue == [{
        "resp_gpf": 1, "resp_gaf": 0, "resp_tag": 0x1234, "resp_vmid": 0,
        "resp_ppn": 0, "resp_level": 0, "resp_n": 0, "resp_pbmt": 0,
        "resp_perm_r": 0, "resp_perm_w": 0, "resp_perm_x": 0,
        "resp_perm_a": 0, "resp_perm_d": 0}]


async def test_trimmed_mxr_csr_fails_closed(tmp_path, monkeypatch):
    """MXR is trimmed only when artifact schema and handle agree."""
    def schema(path, *, with_mxr, valid_json=True):
        priv = {"virt_changed": {"Pin": "input", "High": -1, "Low": 0, "_": True}}
        if with_mxr:
            priv["mxr"] = {"Pin": "input", "High": -1, "Low": 0, "_": True}
        path.write_text(json.dumps({"io": {"csr": {"priv": priv}}})
                        if valid_json else "{not-json")
        return path

    for env_type in (PtwEnv, LlptwEnv):
        with_schema = schema(tmp_path / f"{env_type.__name__}-with.json", with_mxr=True)
        without_schema = schema(tmp_path / f"{env_type.__name__}-without.json", with_mxr=False)
        bad_schema = schema(tmp_path / f"{env_type.__name__}-bad.json", with_mxr=True,
                            valid_json=False)
        handle_with = SimpleNamespace(io_csr_priv_mxr=Signal())
        handle_without = SimpleNamespace()

        env = env_type.__new__(env_type)
        env.csr = {"satp_mode": Signal()}
        env._trimmed_csrs = {"mxr": "implicit G-stage read requires R=1"}
        env.dut = _dut()
        with pytest.raises(ValueError, match="requires R=1"):
            env_type.set_csr(env, mxr=1)
        with pytest.raises(ValueError, match="requires R=1"):
            env_type.set_csr(env, mxr=0)
        assert "mxr" not in env.csr
        with pytest.raises(ValueError, match="requires R=1"):
            env_type.set_csr(env, satp_mode=1, mxr=1)
        assert env.csr["satp_mode"].value == 0
        env_type.set_csr(env, satp_mode=1)
        assert env.csr["satp_mode"].value == 1
        with pytest.raises(KeyError):
            env_type.set_csr(env, unknown=0)

        bound = env_type.__new__(env_type)
        bound.csr = {}
        bound._trimmed_csrs = {}
        with pytest.raises(RuntimeError, match="MXR schema is unavailable"):
            bound._register_mxr(handle_without, None)
        with pytest.raises(RuntimeError, match="not valid JSON"):
            bound._register_mxr(handle_with, bad_schema)
        with pytest.raises(RuntimeError, match="schema declares .*does not expose"):
            bound._register_mxr(handle_without, with_schema)
        with pytest.raises(RuntimeError, match="handle exposes .*does not declare"):
            bound._register_mxr(handle_with, without_schema)
        with pytest.raises(RuntimeError, match="schema is unavailable"):
            bound._register_mxr(handle_without, tmp_path / "missing.json")

        bound.csr = {}
        bound._trimmed_csrs = {}
        bound._register_mxr(handle_with, with_schema)
        assert bound.csr["mxr"] is handle_with.io_csr_priv_mxr
        assert bound._trimmed_csrs == {}
        assert bound.has_mxr_input is True
        capability = bound.mxr_input_capability
        assert capability.driveable is True and capability.reason is None
        assert capability is not bound.mxr_input_capability
        assert not hasattr(capability, "csr")
        assert not hasattr(capability, "schema")
        assert not hasattr(capability, "pin")

        bound.csr = {}
        bound._trimmed_csrs = {}
        bound._register_mxr(handle_without, without_schema)
        assert bound.csr == {}
        assert "mxr" in bound._trimmed_csrs
        assert bound.has_mxr_input is False
        capability = bound.mxr_input_capability
        assert capability.driveable is False and capability.reason
        assert capability is not bound.mxr_input_capability
        assert not hasattr(capability, "csr")
        assert not hasattr(capability, "schema")
        assert not hasattr(capability, "pin")
        with pytest.raises(ValueError, match="requires R=1"):
            env_type.set_csr(bound, mxr=1)

    ptw = PtwEnv.__new__(PtwEnv)
    ptw.csr = {}
    ptw._trimmed_csrs = {"mxr": "implicit G-stage read requires R=1"}
    ptw.dut = _dut()
    with pytest.raises(ValueError, match="requires R=1"):
        await ptw.pulse_csr_change("mxr")

    # Default loader API stays the historical pair; only an explicit
    # with_schema=True asks for the artifact schema. The schema must come from
    # the module actually bound, and a cached alias from another artifact
    # directory must fail closed instead of mixing native builds.
    from suites.memblock.mmu.testbenches.shared.env import native as native_mod

    class FakePtwDut:
        pass

    class FakeLlptwDut:
        pass

    def package_for(directory, *, with_file=True):
        attrs = dict(DUTPtwDut=FakePtwDut, DUTLlptwDut=FakeLlptwDut)
        if with_file:
            attrs["__file__"] = str(Path(directory) / "__init__.py")
        return SimpleNamespace(**attrs)

    argv_calls = []

    def fake_argv(seed):
        argv_calls.append(seed)
        return ["argv", seed]

    monkeypatch.setattr(native_mod, "_argv", fake_argv)
    ptw_dir = (tmp_path / "ptw-artifact").resolve()
    llptw_dir = (tmp_path / "llptw-artifact").resolve()
    monkeypatch.setenv("MMU_PTW_DUT_DIR", str(ptw_dir))
    monkeypatch.setenv("MMU_LLPTW_DUT_DIR", str(llptw_dir))

    # A fake package without __file__ is still legal for the default pair;
    # that path must not perform schema verification.
    monkeypatch.setattr(
        native_mod, "_load_package",
        lambda directory, alias: package_for(directory, with_file=False))
    for loader, cls in ((native_mod.load_ptw_dut, FakePtwDut),
                        (native_mod.load_llptw_dut, FakeLlptwDut)):
        pair = loader()
        assert len(pair) == 2 and pair[0] is cls
        seeded = loader(seed=11)
        assert len(seeded) == 2 and seeded[1] == ["argv", 11]

    # Valid with_schema reads the schema of the bound module. Reusing an alias
    # after switching the requested directory returns the cached class; that
    # metadata split must be rejected and requires a fresh process.
    cached = {}

    def fake_load_cached(directory, alias):
        directory = Path(directory).resolve()
        if alias not in cached:
            cached[alias] = package_for(directory)
        return cached[alias]

    monkeypatch.setattr(native_mod, "_load_package", fake_load_cached)
    for loader, cls, env_name, current, other, alias in (
            (native_mod.load_ptw_dut, FakePtwDut, "MMU_PTW_DUT_DIR",
             ptw_dir, llptw_dir, "_ptw_picker_dut"),
            (native_mod.load_llptw_dut, FakeLlptwDut, "MMU_LLPTW_DUT_DIR",
             llptw_dir, ptw_dir, "_llptw_picker_dut")):
        before = len(argv_calls)
        triple = loader(with_schema=True)
        assert len(triple) == 3 and triple[0] is cls
        assert triple[2] == current / "signals.json"
        assert triple[2] == Path(cached[alias].__file__).resolve().parent / "signals.json"
        seeded = loader(with_schema=True, seed=13)
        assert seeded[2] == current / "signals.json"
        assert loader(with_schema=True)[2] == current / "signals.json"
        assert len(loader()) == 2
        monkeypatch.setenv(env_name, str(other))
        with pytest.raises(RuntimeError, match="cached generated DUT package mismatch"):
            loader(with_schema=True)
        monkeypatch.setenv(env_name, str(current))
        assert loader(with_schema=True)[2] == current / "signals.json"
        assert argv_calls[before:] == [None, 13, None, None, None, None]

    monkeypatch.setattr(
        native_mod, "_load_package",
        lambda directory, alias: package_for(directory, with_file=False))
    with pytest.raises(RuntimeError, match="no __file__"):
        native_mod.load_ptw_dut(with_schema=True)
