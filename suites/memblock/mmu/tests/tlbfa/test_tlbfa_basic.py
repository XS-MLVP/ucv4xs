"""TLBFA basic visibility, reset and timing tests."""
from __future__ import annotations

from mmuverify.common.runtime import execution
from mmuverify.tlbfa.model import NO_S2

from .common import lookup_vpn, make_refill


# TLBFA-RESET-01, TLBFA-COMBO-04
async def test_reset_makes_storage_empty_and_idle(tlbfa_env):
    env = tlbfa_env
    async with execution(env.dut):
        await env.reset()
        assert env.observe_valid(0x1234, NO_S2) == 0
        snap = await env.lookup(0x1234, NO_S2, "post-reset lookup")
        assert snap.hit == 0
        await env.settle(2)
        assert env.observe_valid(0x1234, NO_S2) == 0
        env.coverage.sample_timing("idle_hold")


# TLBFA-RESET-01
async def test_reset_removes_previous_translations(tlbfa_env):
    env = tlbfa_env
    async with execution(env.dut):
        await env.reset()
        first = make_refill(NO_S2, 0, 0x100, 0x123456789, asid=3)
        second = make_refill(NO_S2, 0, 0x101, 0x223456789, asid=4)
        await env.refill(first, 0, "first")
        await env.refill(second, 1, "second")
        env.program_context(satp_asid=3)
        assert env.observe_valid(lookup_vpn(NO_S2, 0x100), NO_S2) == 1
        env.program_context(satp_asid=4)
        assert env.observe_valid(lookup_vpn(NO_S2, 0x101), NO_S2) == 1
        await env.reset("with_valid_entries")
        await env.lookup(lookup_vpn(NO_S2, 0x100), NO_S2, "after-reset first")
        await env.lookup(lookup_vpn(NO_S2, 0x101), NO_S2, "after-reset second")


# TLBFA-REFILL-01, TLBFA-PAYLOAD-01, TLBFA-ACCESS-01
async def test_refill_install_and_next_cycle_hit(tlbfa_env):
    env = tlbfa_env
    async with execution(env.dut):
        await env.reset()
        data = make_refill(NO_S2, 0, 0x200, 0x0ABCDEF01, pbmt=2, s1_pf=1, s1_af=1)
        await env.refill(data, 7, "install")
        snap = await env.lookup(lookup_vpn(NO_S2, 0x200), NO_S2, "installed hit")
        assert snap.hit == 1
        assert snap.ppn == env.model.gen_ppn(env.model.entries[7], lookup_vpn(NO_S2, 0x200))
        assert snap.pbmt == 2
        assert snap.perm["pf"] == 1 and snap.perm["af"] == 1


# TLBFA-REFILL-02
async def test_refill_is_invisible_in_the_same_cycle(tlbfa_env):
    env = tlbfa_env
    async with execution(env.dut):
        await env.reset()
        data = make_refill(NO_S2, 0, 0x300, 0x111111111)
        snap, access = await env.refill_and_lookup(
            data, 9, lookup_vpn(NO_S2, 0x300), NO_S2, "same-cycle"
        )
        assert snap.hit == 0
        assert access.valid == 1 and access.bits == 9
        # Next cycle the entry is visible.
        hit = await env.lookup(lookup_vpn(NO_S2, 0x300), NO_S2, "after-same-cycle")
        assert hit.hit == 1


# TLBFA-REFILL-03
async def test_refill_changes_only_target_way(tlbfa_env):
    env = tlbfa_env
    async with execution(env.dut):
        await env.reset()
        a = make_refill(NO_S2, 0, 0x400, 0x101010101)
        b = make_refill(NO_S2, 0, 0x401, 0x202020202)
        await env.refill(a, 2, "way2")
        await env.refill(b, 3, "way3")
        hit_a = await env.lookup(lookup_vpn(NO_S2, 0x400), NO_S2, "old way")
        hit_b = await env.lookup(lookup_vpn(NO_S2, 0x401), NO_S2, "new way")
        assert hit_a.hit and hit_a.access_bits == 2
        assert hit_b.hit and hit_b.access_bits == 3
        assert hit_a.ppn != hit_b.ppn
