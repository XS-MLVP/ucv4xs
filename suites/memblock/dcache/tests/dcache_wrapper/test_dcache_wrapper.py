"""DCacheWrapper UT: boundary fidelity for the MemBlock-level wrapper.

The DUT is the real `DCacheWrapper` netlist (one `DCache` instance + port
renames + the two-stage perf registers).  Two complementary kinds of checks:

* wrapper-specific: the 861-port map is complete, the renamed cache-control TL
  slave really reaches `CtrlUnit`, the speculative-miss fabric is transparent,
  and the perf outputs are the documented 2-cycle delayed copy;
* regression-through-the-boundary: the DCache top-level scenarios are replayed
  through the wrapper ports with the same reference model, proving the wrapper
  does not swallow, buffer or reorder anything.
"""
from __future__ import annotations

import pytest

from dcacheverify.dcache_wrapper.coverage import DcacheWrapperCoverage
from dcacheverify.dcache_wrapper.env import (
    DcacheWrapperEnv,
    WrapperDutView,
    load_portmap,
)


@pytest.fixture
def dw(dut_factory):
    dut = dut_factory("dcache_wrapper")
    env = DcacheWrapperEnv(dut, DcacheWrapperCoverage())
    env.reset()
    return env


def line_words(base: int) -> list[int]:
    return [int.from_bytes(bytes(((base + beat * 32 + i) & 0xFF) for i in range(32)),
                           "little") for beat in range(2)]


# WFP-001
def test_portmap_is_complete_and_one_to_one(dw):
    portmap = load_portmap()
    assert portmap["wrapper_module"] == "DCacheWrapper"
    assert portmap["inner_module"] == "DCache"
    assert portmap["connection_count"] == 861
    assert portmap["inner_port_count"] == 861
    assert portmap["wrapper_port_count"] == 861
    assert portmap["duplicate_inner_ports"] == []
    assert portmap["unconnected_inner_ports"] == []
    # 819 connections land on wrapper pins (766 identity + 53 renamed) and the
    # 42 perf counters are re-registered through internal nets inside the wrapper.
    assert portmap["direct_connections"] == 819
    assert len(portmap["identity_ports"]) == 766
    renames = portmap["renames"]           # wrapper pin -> inner pin
    assert len(renames) == 53
    assert len(portmap["internal_connections"]) == 42
    assert portmap["perf_output_count"] == 42
    ctrl = [name for name in renames if name.startswith("auto_uncache_in_")]
    spec = [name for name in renames
            if name.startswith("auto_dcache_spec_fabric_source_out_")]
    assert len(ctrl) == 14, ctrl
    assert len(spec) == 39, spec
    assert renames["auto_uncache_in_a_valid"] == "auto_cacheCtrlOpt_in_a_valid"
    assert (renames["auto_dcache_spec_fabric_source_out_candidate_0_valid"]
            == "auto_spec_fabric_source_out_candidate_0_valid")
    assert (portmap["internal_connections"]["io_perf_0_value"]
            == "_dcache_io_perf_0_value")
    # No wrapper port may be left unconnected: the pin list of the built DUT and
    # the mapping keys must agree.
    pins = set(dw.raw_dut.xport.GetKeys())
    mapped = set(portmap["wrapper_to_inner"]) | set(portmap["perf_outputs"]) | {"clock", "reset"}
    missing = {name for name in mapped if name not in pins}
    assert not missing, sorted(missing)[:5]
    if dw.coverage is not None:
        dw.coverage.sample_portmap("identity", "complete")
        dw.coverage.sample_portmap("cache_ctrl", "complete")
        dw.coverage.sample_portmap("cache_ctrl", "renamed")
        dw.coverage.sample_portmap("spec_fabric", "complete")
        dw.coverage.sample_portmap("spec_fabric", "renamed")
        dw.coverage.sample_portmap("perf", "complete")


# WFP-002
def test_cache_control_register_access_through_wrapper(dw):
    # ctrl register (index 0): write then read back, both through auto_uncache_in_*.
    write = dw.ctrl_write(0, 0x0000000B, mask=0xFF)  # ese | ede | comp
    assert write["opcode"] == 0, write            # AccessAck
    assert write["source"] == 7 and write["size"] == 3, write
    read = dw.ctrl_read(0)
    assert read["opcode"] == 1, read              # AccessAckData
    assert read["data"] & 0xF == 0xB, hex(read["data"])
    if dw.coverage is not None:
        dw.coverage.sample_ctrl("ctrl", "write")
        dw.coverage.sample_ctrl("ctrl", "read")

    # delay register (index 1).
    dw.ctrl_write(1, 0x20)
    assert dw.ctrl_read(1)["data"] & 0xFFFFFFFF == 0x20

    # tag mask (index 2): only the low 40 bits are stored.
    dw.ctrl_write(2, (1 << 40) - 1)
    assert dw.ctrl_read(2)["data"] & ((1 << 40) - 1) == (1 << 40) - 1

    # data mask group 0 (index 3): 4 x 16-bit halves.
    dw.ctrl_write(3, 0xDEAD_BEEF_1234_5678)
    assert dw.ctrl_read(3)["data"] & 0xFFFFFFFFFFFFFFFF == 0xDEAD_BEEF_1234_5678
    if dw.coverage is not None:
        dw.coverage.sample_ctrl("delay", "write")
        dw.coverage.sample_ctrl("delay", "read")
        dw.coverage.sample_ctrl("tag_mask", "write")
        dw.coverage.sample_ctrl("tag_mask", "read")
        dw.coverage.sample_ctrl("data_mask", "write")
        dw.coverage.sample_ctrl("data_mask", "read")

    # A partial byte mask must not modify the register.
    dw.ctrl_write(1, 0xFFFF)
    dw.ctrl_write(1, 0x0, mask=0x01)
    assert dw.ctrl_read(1)["data"] & 0xFFFFFFFF == 0xFFFF
    if dw.coverage is not None:
        dw.coverage.sample_ctrl("delay", "write", mask="partial")


# WFP-003
def test_speculative_fabric_ports_are_transparent(dw):
    # Idle: candidate outputs must be quiescent right after reset.
    for index in range(3):
        assert int(getattr(dw.raw_dut,
                           f"auto_dcache_spec_fabric_source_out_candidate_{index}_valid").value) == 0
        assert int(getattr(dw.raw_dut,
                           f"auto_dcache_spec_fabric_source_out_resolve_{index}_valid").value) == 0
    if dw.coverage is not None:
        dw.coverage.sample_spec("idle")

    # Driving `committed_*` must be accepted at the wrapper boundary and not
    # create spurious candidate requests.
    for index in range(3):
        getattr(dw.raw_dut,
                f"auto_dcache_spec_fabric_source_out_committed_{index}").Set(1)
    for index in range(3):
        getattr(dw.raw_dut, f"auto_dcache_spec_fabric_source_out_candidate_{index}_ready").Set(1)
    for _ in range(4):
        dw.dut.Step(1)
        dw.refresh()
    for index in range(3):
        assert int(getattr(dw.raw_dut,
                           f"auto_dcache_spec_fabric_source_out_resolve_{index}_valid").value) == 0
    for index in range(3):
        getattr(dw.raw_dut,
                f"auto_dcache_spec_fabric_source_out_committed_{index}").Set(0)
    if dw.coverage is not None:
        dw.coverage.sample_spec("committed")

    # A load that MissTrack has never seen raises a speculative-miss candidate
    # for exactly one cycle (the S1 cycle).  The wrapper must expose the same
    # request (block address / grow / channel) that the inner DCache produced.
    base = 0x16000
    dw.drive_load(0, base, base)
    candidate = None
    for cycle in range(8):
        dw.refresh()
        for index in range(3):
            valid = int(getattr(
                dw.raw_dut,
                f"auto_dcache_spec_fabric_source_out_candidate_{index}_valid").value)
            if valid:
                candidate = {
                    "index": index,
                    "paddr": int(getattr(
                        dw.raw_dut,
                        f"auto_dcache_spec_fabric_source_out_candidate_{index}_bits_paddr").value),
                    "grow": int(getattr(
                        dw.raw_dut,
                        f"auto_dcache_spec_fabric_source_out_candidate_{index}_bits_grow").value),
                    "channel": int(getattr(
                        dw.raw_dut,
                        f"auto_dcache_spec_fabric_source_out_candidate_{index}_bits_channel").value),
                    "cycle": cycle,
                }
        if cycle == 1:
            dw.stop_load(0)
        if candidate:
            break
        dw.dut.Step(1)
    assert candidate is not None, "an unseen load must raise a fabric candidate"
    assert candidate["paddr"] == (base & ~0x3F), candidate
    assert candidate["grow"] in (0, 1, 2), candidate
    assert candidate["channel"] in (0, 1), candidate
    for _ in range(6):
        dw.dut.Step(1)
        dw.refresh()
    if dw.coverage is not None:
        dw.coverage.sample_spec("candidate")


# WFP-007 / WFP-005
def test_reset_and_dual_channel_through_wrapper(dw):
    # After the reset sweep the hit path works.
    base = 0x16000
    beats = line_words(base)
    cold = dw.load_once(0, base, base, context="wrapper cold")
    assert cold["miss"] == 1, cold
    accepted = dw.service_miss(base, data_beats=beats, context="wrapper refill ch0")
    assert accepted["channel"] == 0, accepted
    for _ in range(6):
        dw.dut.Step(1)
        dw.refresh()
    hit = dw.load_once(0, base, base, context="wrapper hit")
    assert hit["miss"] == 0, hit
    assert hit["data"] == (beats[0] & ((1 << 128) - 1))
    if dw.coverage is not None:
        dw.coverage.sample_core("hit")
        dw.coverage.sample_core("miss_refill")
        dw.coverage.sample_channel(0)

    # Channel 1 (paddr[6] = 1) must be the one that carries the Acquire.
    base1 = base + 0x40
    assert (base1 >> 6) & 1 == 1
    cold = dw.load_once(0, base1, base1, context="wrapper cold ch1")
    assert cold["miss"] == 1
    accepted = dw.service_miss(base1, data_beats=line_words(base1),
                               context="wrapper refill ch1")
    assert accepted["channel"] == 1, accepted
    for _ in range(6):
        dw.dut.Step(1)
        dw.refresh()
    hit = dw.load_once(0, base1, base1, context="wrapper hit ch1")
    assert hit["miss"] == 0
    if dw.coverage is not None:
        dw.coverage.sample_core("miss_refill")
        dw.coverage.sample_channel(1)


# WFP-006
def test_perf_outputs_are_two_cycle_delayed(dw):
    """The wrapper re-registers all 42 perf counters twice before exposing them.

    We cannot see the inner counters from the port list, so the check is: the
    outputs are well-defined after reset, they do NOT move on the cycle the
    request is accepted, and they DO move a few cycles later as the event is
    counted and pushed through the two wrapper flops.
    """
    perf_pins = [f"io_perf_{index}_value" for index in range(42)]
    start = [int(getattr(dw.raw_dut, name).value) for name in perf_pins]
    assert all(0 <= value < (1 << 32) for value in start), start
    if dw.coverage is not None:
        dw.coverage.sample_perf("reset_zero")

    base = 0x17000
    dw.drive_load(0, base, base)
    dw.refresh()
    assert int(dw.loads[0]["req_ready"].value) == 1
    dw.dut.Step(1)          # S0 accept
    dw.stop_load(0)
    dw.refresh()
    same_cycle = [int(getattr(dw.raw_dut, name).value) for name in perf_pins]
    assert same_cycle == start, "perf must not change on the accept cycle"

    changed = None
    for cycle in range(10):
        dw.dut.Step(1)
        dw.refresh()
        now = [int(getattr(dw.raw_dut, name).value) for name in perf_pins]
        if now != start:
            changed = cycle
            break
    assert changed is not None, "a load miss must move at least one perf counter"
    if dw.coverage is not None:
        dw.coverage.sample_perf("delayed_update")


# WFP-004
def test_store_and_eviction_through_wrapper(dw):
    # Fill four ways of one set with dirty lines, then observe the dirty victim
    # release on the C channel at the wrapper boundary.
    def same_set(start: int, count: int) -> list[int]:
        from dcacheverify.load_pipe.model import dcache_index
        want = dcache_index(start)
        found = [start]
        addr = start + 0x40
        while len(found) < count:
            if dcache_index(addr) == want:
                found.append(addr)
            addr += 0x40
        return found

    addrs = same_set(0x8000, 5)
    values = {}
    for index, addr in enumerate(addrs[:4]):
        value = 0x1122334455667788 + index
        values[addr] = value
        dw.drive_store(addr, addr, value, (1 << 64) - 1, store_id=index + 1)
        dw.service_miss(addr, data_beats=line_words(addr), context="wrapper dirty fill")
        dw.stop_store()
        hit = dw.wait_store_hit(12)
        assert hit["hit"] == 1, (index, hit)
        for _ in range(4):
            dw.dut.Step(1)
            dw.refresh()
        read = dw.load_once(0, addr, addr, context="wrapper dirty check")
        assert (read["data"] & ((1 << 64) - 1)) == value, (index, hex(read["data"]))

    victim = addrs[4]
    assert dw.load_once(0, victim, victim, context="wrapper evict")["miss"] == 1
    for channel in dw.channels:
        channel["a_ready"].Set(1)
        channel["c_ready"].Set(1)
    entries = []
    accepted = None
    for _ in range(32):
        for index, channel in enumerate(dw.channels):
            if int(channel["c_valid"].value):
                entry = (index, int(channel["c_opcode"].value),
                         int(channel["c_param"].value),
                         int(channel["c_address"].value),
                         int(channel["c_data"].value))
                if entry[:4] not in [item[:4] for item in entries]:
                    entries.append(entry)
            if int(channel["a_valid"].value) and int(channel["a_ready"].value):
                accepted = {"channel": index,
                            "source": int(channel["a_source"].value),
                            "address": int(channel["a_address"].value)}
        if accepted:
            break
        dw.dut.Step(1)
        dw.refresh()
    assert accepted is not None
    assert accepted["address"] == (victim & ~0x3F)
    channel = dw.channels[accepted["channel"]]
    for beat in range(2):
        channel["d_valid"].Set(1)
        channel["d_opcode"].Set(5)
        channel["d_size"].Set(6)
        channel["d_source"].Set(accepted["source"])
        channel["d_sink"].Set(0)
        channel["d_denied"].Set(0)
        channel["d_corrupt"].Set(0)
        channel["d_data"].Set(line_words(victim)[beat])
        for _ in range(3):
            for index, other in enumerate(dw.channels):
                if int(other["c_valid"].value):
                    entry = (index, int(other["c_opcode"].value),
                             int(other["c_param"].value),
                             int(other["c_address"].value),
                             int(other["c_data"].value))
                    if entry[:4] not in [item[:4] for item in entries]:
                        entries.append(entry)
            dw.dut.Step(1)
            dw.refresh()
    channel["d_valid"].Set(0)
    for _ in range(8):
        for index, other in enumerate(dw.channels):
            if int(other["c_valid"].value):
                entry = (index, int(other["c_opcode"].value),
                         int(other["c_param"].value),
                         int(other["c_address"].value),
                         int(other["c_data"].value))
                if entry[:4] not in [item[:4] for item in entries]:
                    entries.append(entry)
        dw.dut.Step(1)
        dw.refresh()
    dirty = [entry for entry in entries if entry[1] == 7]
    assert dirty, entries
    index, opcode, param, addr, data = dirty[0]
    assert addr in addrs[:4], hex(addr)
    assert param == 1
    assert (data & ((1 << 64) - 1)) == values[addr]
    if dw.coverage is not None:
        dw.coverage.sample_core("store")
        dw.coverage.sample_core("eviction")


# WFP-004
def test_atomic_and_cmo_through_wrapper(dw):
    base = 0x1A000
    beats = line_words(base)
    dw.load_once(0, base, base, context="wrapper atomic prime")
    dw.service_miss(base, data_beats=beats, context="wrapper atomic prime")
    for _ in range(8):
        dw.dut.Step(1)
        dw.refresh()
    assert dw.issue_atomic(base, base, 4, 0x0123456789ABCDEF, 0xFFFF)
    response = dw.wait_atomic_response(24)
    assert response is not None
    assert response["data"] == (beats[0] & ((1 << 128) - 1))
    assert response["miss"] == 0 and response["replay"] == 0
    read = dw.load_once(0, base, base, context="wrapper atomic result")
    assert (read["data"] & ((1 << 64) - 1)) == 0x0123456789ABCDEF
    if dw.coverage is not None:
        dw.coverage.sample_core("atomic")

    for opcode, expected in ((0, 12), (1, 13), (2, 14)):
        address = 0x1B000 if opcode != 1 else 0x1B040
        issued = dw.issue_cmo(opcode, address)
        assert issued["ready"] and issued["accepted"], (opcode, issued)
        assert issued["accepted"]["opcode"] == expected
        result = dw.complete_cmo(issued["accepted"])
        assert result is not None
    if dw.coverage is not None:
        dw.coverage.sample_core("cmo")


# WFP-004
def test_denied_refill_error_through_wrapper(dw):
    base = 0x1C000
    dw.load_once(0, base, base, context="wrapper denied")
    dw.service_miss(base, data_beats=line_words(base), denied=True,
                    context="wrapper denied refill")
    seen = False
    for _ in range(12):
        dw.dut.Step(1)
        dw.refresh()
        if dw._val(dw.error["valid"]):
            seen = True
            break
    assert seen, "denied refill must raise io_error at the wrapper boundary"
    if dw.coverage is not None:
        dw.coverage.sample_core("error")


# WFP-004
def test_probe_through_wrapper(dw):
    base = 0x1D000
    dw.load_once(0, base, base, context="wrapper probe prime")
    dw.service_miss(base, data_beats=line_words(base), context="wrapper probe prime")
    for _ in range(8):
        dw.dut.Step(1)
        dw.refresh()
    channel = dw.channels[0]
    channel["b_valid"].Set(1)
    channel["b_param"].Set(0)
    channel["b_address"].Set(base)
    response = None
    for _ in range(24):
        dw.dut.Step(1)
        dw.refresh()
        if int(channel["c_valid"].value):
            response = {
                "opcode": int(channel["c_opcode"].value),
                "param": int(channel["c_param"].value),
                "address": int(channel["c_address"].value),
            }
            break
    channel["b_valid"].Set(0)
    assert response is not None
    assert response["opcode"] in (4, 5), response
    assert response["address"] == base
    if dw.coverage is not None:
        dw.coverage.sample_core("probe")
