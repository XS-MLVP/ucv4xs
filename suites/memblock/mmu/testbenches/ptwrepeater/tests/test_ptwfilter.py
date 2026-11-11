"""PTWFilter UT: pending-request filter, merge, matching and flush."""
from __future__ import annotations

import pytest

from suites.memblock.mmu.testbenches.shared.env.execution import execution
from suites.memblock.mmu.testbenches.ptwrepeater.env.ptw import Req


def s1_values(vpn: int, tag: int | None = None, asid: int = 0, level: int = 0,
              valididx=None) -> dict:
    if tag is None:
        tag = (vpn >> 3) & ((1 << 35) - 1)
    if valididx is None:
        valididx = [1] * 8
    values = {
        "s1_entry_tag": tag,
        "s1_entry_asid": asid,
        "s1_entry_vmid": 0,
        "s1_entry_n": 0,
        "s1_entry_pbmt": 0,
        "s1_entry_perm_a": 1,
        "s1_entry_perm_g": 0,
        "s1_entry_perm_u": 1,
        "s1_entry_perm_x": 1,
        "s1_entry_perm_w": 0,
        "s1_entry_perm_r": 1,
        "s1_entry_level": level,
        "s1_entry_v": 1,
        "s1_entry_ppn": 0x12345,
        "s1_addr_low": 0,
    }
    for index, value in enumerate(valididx):
        values[f"s1_valididx_{index}"] = value
    for index in range(8):
        values[f"s1_ppn_low_{index}"] = index
        values[f"s1_pteidx_{index}"] = 1 if index == 0 else 0
    return values


# PTWFIL-01
async def test_single_request_issue_match_and_release(filter_env):
    env = filter_env
    async with execution(env):
        await env.reset()
        env.set_asid(satp=0)
        await env.send(Req(0x10000, 0), "single")
        assert env.request_ready() == 1
        vpn, stage = await env.wait_ptw_req("issue")
        assert (vpn, stage) == (0x10000, 0)
        if env.coverage is not None:
            env.coverage.sample("issue", 0)
        await env.accept_ptw()
        resp = await env.ptw_respond(s1_values(0x10000, asid=0))
        assert resp["valid"] == 1
        assert resp["s2xlate"] == 0
        assert resp["s1_entry_tag"] == ((0x10000 >> 3) & ((1 << 35) - 1))
        assert resp["s1_entry_ppn"] == 0x12345
        assert resp["valididx"] == [1] * 8
        assert resp["ppn_low"] == list(range(8))
        if env.coverage is not None:
            env.coverage.sample("match_resp", 0)
        # Entry was released; a new request can be accepted and re-issued.
        await env.edge()
        await env.send(Req(0x10000, 0), "re-request")
        assert await env.wait_ptw_req("re-issue") == (0x10000, 0)


# PTWFIL-02
async def test_mismatched_response_does_not_complete_request(filter_env):
    env = filter_env
    async with execution(env):
        await env.reset()
        env.set_asid(satp=0)
        await env.send(Req(0x11000, 0))
        await env.wait_ptw_req("issue")
        await env.accept_ptw()
        # Wrong tag: no TLB response and the entry must still be pending.
        wrong_tag = ((0x11000 >> 3) & ((1 << 35) - 1)) + 1
        bad = await env.ptw_respond(s1_values(0x11000, tag=wrong_tag))
        assert bad["valid"] == 0
        if env.coverage is not None:
            env.coverage.sample("mismatch_resp", 0)
        # A later matching response still completes it.
        resp = await env.ptw_respond(s1_values(0x11000))
        assert resp["valid"] == 1


# PTWFIL-03
async def test_duplicate_request_is_merged(filter_env):
    env = filter_env
    async with execution(env):
        await env.reset()
        env.set_asid(satp=0)
        await env.send(Req(0x12000, 0), "first")
        await env.send(Req(0x12000, 0), "duplicate")
        # Only one PTW request, with one entry outstanding.
        vpn, _stage = await env.wait_ptw_req("merged issue")
        assert vpn == 0x12000
        await env.accept_ptw()
        resp = await env.ptw_respond(s1_values(0x12000))
        assert resp["valid"] == 1
        if env.coverage is not None:
            env.coverage.sample("merge", 0)
        await env.edge()
        # After completion the filter is empty again.
        assert env.request_ready() == 1
        assert env.ptw_request_valid() == 0


# PTWFIL-04
async def test_capacity_eight_and_drain(filter_env):
    env = filter_env
    async with execution(env):
        await env.reset()
        env.set_asid(satp=0)
        entries = [Req(0x20000 + index * 8, 0) for index in range(8)]
        for index, req in enumerate(entries):
            assert env.request_ready() == 1, f"entry {index}"
            await env.send(req, f"entry {index}")
            if env.coverage is not None:
                env.coverage.sample("enqueue", req.s2xlate)
        # The queue is full; a ninth distinct request must not be accepted.
        assert not await env.offer_request(Req(0x30000, 0), "capacity")
        if env.coverage is not None:
            env.coverage.sample("full")
        # Drain all eight through matching PTW responses.
        for index, req in enumerate(entries):
            vpn, stage = await env.wait_ptw_req(f"drain {index}")
            while (vpn, stage) != (req.vpn, req.s2xlate):
                # Filter may issue a previously queued entry first.
                await env.accept_ptw()
                vpn, stage = await env.wait_ptw_req(f"drain skip {index}")
            await env.accept_ptw()
            resp = await env.ptw_respond(s1_values(req.vpn))
            assert resp["valid"] == 1


# PTWFIL-05
async def test_flush_clears_pending_entries(filter_env):
    env = filter_env
    async with execution(env):
        await env.reset()
        env.set_asid(satp=0)
        for index in range(3):
            await env.send(Req(0x40000 + index * 8, 0))
        await env.flush()
        assert env.request_ready() == 1
        if env.coverage is not None:
            env.coverage.sample("flush")
        # A fresh request after flush is issued.
        await env.send(Req(0x41000, 0))
        assert await env.wait_ptw_req("after flush") == (0x41000, 0)


# PTWFIL-06
async def test_getgpa_flag_is_returned_with_matching_response(filter_env):
    env = filter_env
    async with execution(env):
        await env.reset()
        env.set_asid(satp=0)
        await env.send(Req(0x50000, 0, get_gpa=1))
        await env.wait_ptw_req("getGpa issue")
        await env.accept_ptw()
        resp = await env.ptw_respond(s1_values(0x50000))
        assert resp["valid"] == 1
        assert resp["getgpa"] == 1
        if env.coverage is not None:
            env.coverage.sample("match_resp", 0, 1)
        await env.edge()
        await env.send(Req(0x51000, 0, get_gpa=0))
        await env.wait_ptw_req("no getGpa")
        await env.accept_ptw()
        resp = await env.ptw_respond(s1_values(0x51000))
        assert resp["valid"] == 1 and resp["getgpa"] == 0


def staged_values(req: Req, satp: int = 0, vsatp: int = 0, vmid: int = 0) -> dict:
    """Build a PTW response that matches one pending request for any stage."""
    values = {
        "s2xlate": req.s2xlate,
        "s1_entry_asid": vsatp if req.s2xlate != 0 else satp,
        "s1_entry_vmid": vmid,
        "s1_entry_level": 0,
        "s1_entry_v": 1,
        "s1_entry_perm_a": 1,
        "s1_entry_perm_r": 1,
        "s1_entry_perm_x": 1,
    }
    for index in range(8):
        values[f"s1_valididx_{index}"] = 1
        values[f"s1_pteidx_{index}"] = 1 if index == 0 else 0
        values[f"s1_ppn_low_{index}"] = index
    if req.s2xlate == 2:
        values["s1_entry_tag"] = 0
        values["s2_entry_tag"] = req.vpn
        values["s2_entry_vmid"] = vmid
        values["s2_entry_level"] = 0
        values["s2_entry_perm_a"] = 1
        values["s2_entry_perm_x"] = 1
    else:
        values["s1_entry_tag"] = (req.vpn >> 3) & ((1 << 35) - 1)
        values["s2_entry_tag"] = req.vpn
        values["s2_entry_vmid"] = vmid
        values["s2_entry_level"] = 0
        values["s2_entry_perm_a"] = 1
        values["s2_entry_perm_x"] = 1
    return values


# PTWFIL-07: all four translation-stage classes can be matched end to end.
async def test_stage_classes_match(filter_env):
    env = filter_env
    async with execution(env):
        await env.reset()
        env.set_asid(satp=1, vsatp=2, vmid=3)
        for stage in (0, 1, 2, 3):
            req = Req(0x60000 + stage * 8, stage)
            await env.send(req, f"stage {stage}")
            vpn, s2 = await env.wait_ptw_req(f"stage {stage} issue")
            while (vpn, s2) != (req.vpn, req.s2xlate):
                await env.accept_ptw()
                vpn, s2 = await env.wait_ptw_req(f"stage {stage} skip")
            await env.accept_ptw()
            resp = await env.ptw_respond(staged_values(req, satp=1, vsatp=2, vmid=3))
            assert resp["valid"] == 1, f"stage {stage}"
            if env.coverage is not None:
                env.coverage.sample("match_resp", stage)
            await env.edge()


# PTWFIL-08: response payload fields toggle through matching transactions. The
# key fields (tag/asid/vmid/level/valididx) stay valid while the rest vary.
async def test_response_payload_extremes(filter_env):
    env = filter_env
    async with execution(env):
        await env.reset()
        env.set_asid(satp=0)
        req = Req(0x70000, 0)
        for endpoint in (1, 0):
            await env.send(req, "payload extreme")
            vpn, _ = await env.wait_ptw_req("payload issue")
            while vpn != req.vpn:
                await env.accept_ptw()
                vpn, _ = await env.wait_ptw_req("payload skip")
            await env.accept_ptw()
            values = staged_values(req)
            values.update({
                "s1_entry_ppn": (1 << 41) - 1 if endpoint else 0,
                "s1_entry_pbmt": 3 if endpoint else 0,
                "s1_entry_n": endpoint,
                "s1_addr_low": 7 if endpoint else 0,
                "s1_entry_perm_w": endpoint,
                "s1_entry_perm_u": endpoint,
                "s1_entry_perm_g": endpoint,
                "s2_entry_n": endpoint,
                "s2_entry_pbmt": 3 if endpoint else 0,
                "s2_gpf": endpoint,
                "s2_gaf": endpoint,
            })
            for index in range(8):
                values[f"s1_ppn_low_{index}"] = 7 if endpoint else 0
                values[f"s1_pteidx_{index}"] = 1 if (endpoint or index == 0) else 0
            resp = await env.ptw_respond(values)
            assert resp["valid"] == 1
            assert resp["s1_entry_ppn"] == values["s1_entry_ppn"]
            assert resp["s2_gpf"] == endpoint
            await env.edge()


# PTWFIL-09: every interface and queue-state bit toggles through all-ones and
# all-zeros fills. Entries are filled without an intermediate flush (so all
# eight queue slots are written), then flushed before the next endpoint.
@pytest.mark.structural_stress
async def test_all_bits_toggle(filter_env):
    env = filter_env
    async with execution(env):
        await env.reset()
        all_ones = (1 << 38) - 1
        for endpoint in (1, 0):
            env.clear_flush_sources()
            limit = (1 << 16) - 1 if endpoint else 0
            env.set_asid(satp=limit, vsatp=limit, vmid=limit)
            env.begin_request_stream()
            for index in range(8):
                vpn = (all_ones ^ (index << 33)) if endpoint else (index << 33)
                env.stream_request(vpn, 3 if endpoint else 0, endpoint)
                await env.edge()
            await env.end_request_stream()
            await env.edge()
            await env.pulse_sfence(hold=1, settle=4)
        # Fill the response payload registers in both directions.
        for endpoint in (1, 0):
            env.structural_input_sweep(endpoint)
            env.clear_flush_sources()
            env.drive_structural_ptw_response(
                s2xlate=3 if endpoint else 0,
                s1_entry_tag=(1 << 35) - 1 if endpoint else 0,
                s1_entry_ppn=(1 << 41) - 1 if endpoint else 0,
                s2_entry_tag=(1 << 38) - 1 if endpoint else 0,
                s2_entry_ppn=(1 << 38) - 1 if endpoint else 0)
            env.drive_ptw_response_valid(1)
            await env.edge()
            env.clear_ptw_response()
            await env.edge()
        env.structural_input_sweep(0)
        env.clear_ptw_response()
        await env.edge()
        await env.reset()
        await env.send(Req(0x20000, 0), "after structural stress")
        assert await env.wait_ptw_req("after structural stress") == (0x20000, 0)
        restored = await env.ptw_respond(s1_values(0x20000))
        assert restored["valid"] == 1 and restored["s1_entry_tag"] == 0x20000 >> 3


# PTWFIL-10: a PTW response arriving in the same cycle as the head issue
# suppresses that issue and removes the entry (issue_filtered path).
async def test_response_suppresses_same_cycle_issue(filter_env):
    env = filter_env
    async with execution(env):
        await env.reset()
        env.set_asid(satp=0)
        req = Req(0x90000, 0)
        await env.send(req)
        await env.wait_ptw_req("head issue")
        # Head is now visible and would fire if ready. Respond in this cycle.
        env.set_ptw_ready(1)
        values = staged_values(req)
        resp = await env.ptw_respond_same_cycle(values)
        env.set_ptw_ready(0)
        assert resp["valid"] == 1
        await env.edge()
        assert env.ptw_request_valid() == 0


# PTWFIL-11: each CSR-change source independently flushes pending entries.
async def test_csr_change_flush_sources(filter_env):
    env = filter_env
    async with execution(env):
        await env.reset()
        env.set_asid(satp=0)
        for key in ("satp_changed", "vsatp_changed", "hgatp_changed", "virt_changed"):
            await env.send(Req(0xA0000, 0))
            assert env.ptw_request_valid() == 1
            await env.pulse_csr_change(key)
            assert env.ptw_request_valid() == 0
            assert env.request_ready() == 1


# PTWFIL-12: eight outstanding issued requests drive the inflight counter up
# and back down as their responses arrive.
async def test_inflight_counter_eight(filter_env):
    env = filter_env
    async with execution(env):
        await env.reset()
        env.set_asid(satp=0)
        reqs = [Req(0xB0000 + index * 8, 0) for index in range(8)]
        for req in reqs:
            await env.send(req)
        issued = []
        for _ in range(8):
            vpn, _ = await env.wait_ptw_req("inflight")
            issued.append(vpn)
            await env.accept_ptw()
        assert sorted(issued) == sorted(req.vpn for req in reqs)
        for req in reqs:
            resp = await env.ptw_respond(staged_values(req))
            assert resp["valid"] == 1
            await env.edge()
        assert env.request_ready() == 1


# PTWFIL-13: high VPN bits and per-way tag-match directions.  Two rounds of
# eight entries alternate VPN bits 33..35; each entry first receives a
# mismatched tag (match 1->0) and then the matching tag, so the per-way
# tag_match comparators and vpn registers are toggled in both directions.
async def test_high_tag_match_directions(filter_env):
    env = filter_env
    async with execution(env):
        await env.reset()
        env.set_asid(satp=0)
        for round_index in range(2):
            if round_index:
                await env.pulse_sfence()
            reqs = []
            for index in range(8):
                vpn = 0x20000 + index * 8
                if ((index >> 0) & 1) ^ round_index:
                    vpn |= 1 << 33
                if ((index >> 1) & 1) ^ round_index:
                    vpn |= 1 << 34
                if ((index >> 2) & 1) ^ round_index:
                    vpn |= 1 << 35
                req = Req(vpn, 0)
                reqs.append(req)
                await env.send(req, f"high tag {round_index}/{index}")
            for index, req in enumerate(reqs):
                vpn, stage = await env.wait_ptw_req(f"high tag issue {round_index}/{index}")
                assert (vpn, stage) == (req.vpn, 0), (round_index, index)
                await env.accept_ptw()
                wrong_tag = ((req.vpn >> 3) & ((1 << 35) - 1)) + 1
                bad = await env.ptw_respond(
                    s1_values(req.vpn, tag=wrong_tag))
                assert bad["valid"] == 0, (round_index, index)
                good = await env.ptw_respond(s1_values(req.vpn))
                assert good["valid"] == 1, (round_index, index)
                await env.edge()


# PTWFIL-14: onlyStage2 per-way high-tag matching.  Both rounds use vmid=5;
# each entry first sees a mismatched s2 tag/vmid (match 1->0) and then the
# matching onlyStage2 response.
async def test_only_s2_high_tag_match(filter_env):
    env = filter_env
    async with execution(env):
        await env.reset()
        env.set_asid(satp=0, vsatp=0, vmid=5)
        for round_index in range(2):
            if round_index:
                await env.pulse_sfence()
            reqs = []
            for index in range(8):
                vpn = 0x40000 + index * 8
                if ((index >> 0) & 1) ^ round_index:
                    vpn |= 1 << 33
                if ((index >> 1) & 1) ^ round_index:
                    vpn |= 1 << 34
                req = Req(vpn, 2)
                reqs.append(req)
                await env.send(req, f"onlyS2 high tag {round_index}/{index}")
            for index, req in enumerate(reqs):
                vpn, stage = await env.wait_ptw_req(f"onlyS2 issue {round_index}/{index}")
                assert (vpn, stage) == (req.vpn, 2), (round_index, index)
                await env.accept_ptw()
                bad = staged_values(req, vmid=5)
                bad["s2_entry_tag"] = (bad["s2_entry_tag"] + 1) & ((1 << 38) - 1)
                bad["s2_entry_vmid"] = 6
                resp = await env.ptw_respond(bad)
                assert resp["valid"] == 0, (round_index, index)
                good = await env.ptw_respond(staged_values(req, vmid=5))
                assert good["valid"] == 1 and good["s2xlate"] == 2, (round_index, index)
                await env.edge()
