"""TLBFA sfence/hfence semantics."""
from __future__ import annotations

from suites.memblock.mmu.execution import execution
from suites.memblock.mmu.tlbfa.model import ALL_STAGE, NO_S2, ONLY_S1, ONLY_S2

from .common import lookup_vpn, make_refill


def addr_of(tag: int, low: int = 0) -> int:
    return (((tag & ((1 << 35) - 1)) << 3) | (low & 7)) << 12


# TLBFA-SFENCE-01
async def test_sfence_all_address_all_asid_clears_no_s2_only(tlbfa_env):
    env = tlbfa_env
    async with execution(env):
        await env.reset()
        env.program_context(satp_asid=1, vsatp_asid=1, hgatp_vmid=3)
        a = make_refill(NO_S2, 0, 0x20000, 0x100000001, asid=1)
        b = make_refill(NO_S2, 0, 0x20100, 0x200000002, asid=1, perm_g=1)
        c = make_refill(ONLY_S1, 0, 0x20200, 0x300000003, asid=1, vmid=3)
        d = make_refill(ONLY_S2, 0, (0x20300 << 3) | 0, 0x400000004, vmid=3)
        await env.refill(a, 0, "no-s2")
        await env.refill(b, 1, "global no-s2")
        await env.refill(c, 2, "only-s1")
        await env.refill(d, 3, "only-s2")
        await env.fence("all_all", 1, 1, 0, 0, note="all/all")
        assert (await env.lookup(lookup_vpn(NO_S2, 0x20000), NO_S2, "A cleared")).hit == 0
        assert (await env.lookup(lookup_vpn(NO_S2, 0x20100), NO_S2, "B cleared")).hit == 0
        assert (await env.lookup(lookup_vpn(ONLY_S1, 0x20200), ONLY_S1, "C survives")).hit == 1
        assert (await env.lookup((0x20300 << 3), ONLY_S2, "D survives")).hit == 1
        env.sample_fence("all_all", ["stage1_cleared", "stage2_survived"])


# TLBFA-SFENCE-02, TLBFA-SFENCE-04
async def test_sfence_all_address_specific_asid_preserves_global_and_other_asid(tlbfa_env):
    env = tlbfa_env
    async with execution(env):
        await env.reset()
        env.program_context(satp_asid=1, vsatp_asid=1, hgatp_vmid=3)
        a = make_refill(NO_S2, 0, 0x21000, 0x100000011, asid=1)
        b = make_refill(NO_S2, 0, 0x21100, 0x200000012, asid=1, perm_g=1)
        c = make_refill(NO_S2, 0, 0x21200, 0x300000013, asid=2)
        d = make_refill(ONLY_S1, 0, 0x21300, 0x400000014, asid=1, vmid=3)
        await env.refill(a, 0, "A")
        await env.refill(b, 1, "B global")
        await env.refill(c, 2, "C other asid")
        await env.refill(d, 3, "D only-s1")
        await env.fence("all_asid", 1, 0, 0, 1, note="all/asid")
        assert (await env.lookup(lookup_vpn(NO_S2, 0x21000), NO_S2, "A cleared")).hit == 0
        assert (await env.lookup(lookup_vpn(NO_S2, 0x21100), NO_S2, "B survives")).hit == 1
        env.program_context(satp_asid=2)
        assert (await env.lookup(lookup_vpn(NO_S2, 0x21200), NO_S2, "C survives")).hit == 1
        env.program_context(satp_asid=1)
        assert (await env.lookup(lookup_vpn(ONLY_S1, 0x21300), ONLY_S1, "D survives")).hit == 1
        env.sample_fence(
            "all_asid",
            ["stage1_cleared", "global_survived", "other_asid_survived", "stage1_survived"],
        )


# TLBFA-SFENCE-03, TLBFA-SFENCE-04
async def test_sfence_exact_address_specific_asid_and_global_survival(tlbfa_env):
    env = tlbfa_env
    async with execution(env):
        await env.reset()
        env.program_context(satp_asid=1, vsatp_asid=1, hgatp_vmid=3)
        x, y, z = 0x22000, 0x22100, 0x22200
        a = make_refill(NO_S2, 0, x, 0x100000021, asid=1)
        d = make_refill(NO_S2, 0, x, 0x400000024, asid=2)
        c = make_refill(NO_S2, 0, z, 0x300000023, asid=1)
        b = make_refill(NO_S2, 0, y, 0x200000022, asid=1, perm_g=1)
        await env.refill(a, 0, "A target")
        await env.refill(d, 1, "D other asid same vpn")
        await env.refill(c, 2, "C other vpn")
        await env.refill(b, 3, "B global other vpn")
        await env.fence("addr_asid", 0, 0, addr_of(x), 1, note="addr/asid")
        assert (await env.lookup(lookup_vpn(NO_S2, x), NO_S2, "A cleared, D does not match asid 1")).hit == 0
        assert (await env.lookup(lookup_vpn(NO_S2, z), NO_S2, "C survives")).hit == 1
        assert (await env.lookup(lookup_vpn(NO_S2, y), NO_S2, "B global survives")).hit == 1
        env.program_context(satp_asid=2)
        assert (await env.lookup(lookup_vpn(NO_S2, x), NO_S2, "D survives")).hit == 1
        # Install a global translation at the same address, then use the
        # address + all-ASID form. In this design that form clears the global
        # entry; the other-ASID entry remains.
        global_x = make_refill(NO_S2, 0, x, 0x500000025, asid=1, perm_g=1)
        await env.refill(global_x, 4, "global at X")
        env.program_context(satp_asid=1)
        assert (await env.lookup(lookup_vpn(NO_S2, x), NO_S2, "global at X before fence")).hit == 1
        await env.fence("addr_all_asid", 0, 1, addr_of(x), 1, note="addr/all-asid")
        assert (await env.lookup(lookup_vpn(NO_S2, x), NO_S2, "global at X cleared")).hit == 0
        assert (await env.lookup(lookup_vpn(NO_S2, z), NO_S2, "C still survives")).hit == 1
        env.program_context(satp_asid=2)
        assert (await env.lookup(lookup_vpn(NO_S2, x), NO_S2, "D cleared by address-only all-ASID form")).hit == 0
        env.program_context(satp_asid=1)
        env.sample_fence("addr_asid", ["stage1_cleared", "global_survived", "other_asid_survived"])
        env.sample_fence("addr_all_asid", ["global_cleared", "other_asid_cleared"])


# TLBFA-SFENCE-05
async def test_hfencev_all_clears_current_vmid_stage2(tlbfa_env):
    env = tlbfa_env
    async with execution(env):
        await env.reset()
        env.program_context(satp_asid=1, vsatp_asid=1, hgatp_vmid=3)
        d1 = make_refill(ONLY_S2, 0, (0x23000 << 3) | 0, 0x100000031, vmid=3)
        d2 = make_refill(ONLY_S2, 0, (0x23100 << 3) | 0, 0x200000032, vmid=4)
        e = make_refill(ALL_STAGE, 0, 0x23200, 0x300000033, asid=1, vmid=3)
        a = make_refill(NO_S2, 0, 0x23300, 0x400000034, asid=1)
        await env.refill(d1, 0, "vmid3")
        await env.refill(d2, 1, "vmid4")
        await env.refill(e, 2, "two-stage vmid3")
        await env.refill(a, 3, "no-s2")
        await env.fence("hfencev_all", 0, 1, 0, 0, hv=1, note="hfencev all")
        assert (await env.lookup((0x23000 << 3), ONLY_S2, "D1 cleared")).hit == 0
        assert (await env.lookup(lookup_vpn(ALL_STAGE, 0x23200), ALL_STAGE, "E cleared")).hit == 0
        env.program_context(hgatp_vmid=4)
        assert (await env.lookup((0x23100 << 3), ONLY_S2, "D2 survives")).hit == 1
        assert (await env.lookup(lookup_vpn(NO_S2, 0x23300), NO_S2, "A survives")).hit == 1
        env.sample_fence("hfencev_all", ["stage2_cleared", "other_vmid_survived", "stage1_survived"])


# TLBFA-SFENCE-05
async def test_hfencev_specific_asid_keeps_other_asid_and_global(tlbfa_env):
    env = tlbfa_env
    async with execution(env):
        await env.reset()
        env.program_context(satp_asid=1, vsatp_asid=1, hgatp_vmid=3)
        e1 = make_refill(ALL_STAGE, 0, 0x24000, 0x100000041, asid=1, vmid=3)
        e2 = make_refill(ALL_STAGE, 0, 0x24100, 0x200000042, asid=2, vmid=3)
        e3 = make_refill(ALL_STAGE, 0, 0x24200, 0x300000043, asid=1, vmid=3, perm_g=1)
        await env.refill(e1, 0, "asid1")
        await env.refill(e2, 1, "asid2")
        await env.refill(e3, 2, "global")
        await env.fence("hfencev_asid", 0, 0, 0, 1, hv=1, note="hfencev asid")
        assert (await env.lookup(lookup_vpn(ALL_STAGE, 0x24000), ALL_STAGE, "E1 cleared")).hit == 0
        assert (await env.lookup(lookup_vpn(ALL_STAGE, 0x24200), ALL_STAGE, "E3 global survives")).hit == 1
        env.program_context(vsatp_asid=2)
        assert (await env.lookup(lookup_vpn(ALL_STAGE, 0x24100), ALL_STAGE, "E2 survives")).hit == 1
        env.sample_fence("hfencev_asid", ["stage2_cleared", "global_survived"])


# TLBFA-SFENCE-06
async def test_hfenceg_all_and_vmid_selection(tlbfa_env):
    env = tlbfa_env
    async with execution(env):
        await env.reset()
        env.program_context(satp_asid=1, vsatp_asid=1, hgatp_vmid=3)
        d1 = make_refill(ONLY_S2, 0, (0x25000 << 3) | 0, 0x100000051, vmid=3)
        d2 = make_refill(ONLY_S2, 0, (0x25100 << 3) | 0, 0x200000052, vmid=4)
        e = make_refill(ALL_STAGE, 0, 0x25200, 0x300000053, asid=1, vmid=3)
        a = make_refill(NO_S2, 0, 0x25300, 0x400000054, asid=1)
        await env.refill(d1, 0, "D1")
        await env.refill(d2, 1, "D2")
        await env.refill(e, 2, "E")
        await env.refill(a, 3, "A")
        await env.fence("hfenceg_vmid", 0, 0, 0, 4, hg=1, note="hfenceg vmid")
        assert (await env.lookup((0x25100 << 3), ONLY_S2, "D2 cleared")).hit == 0
        assert (await env.lookup((0x25000 << 3), ONLY_S2, "D1 survives")).hit == 1
        assert (await env.lookup(lookup_vpn(ALL_STAGE, 0x25200), ALL_STAGE, "E survives")).hit == 1
        assert (await env.lookup(lookup_vpn(NO_S2, 0x25300), NO_S2, "A survives")).hit == 1
        await env.fence("hfenceg_all", 0, 1, 0, 0, hg=1, note="hfenceg all")
        assert (await env.lookup((0x25000 << 3), ONLY_S2, "D1 cleared")).hit == 0
        assert (await env.lookup(lookup_vpn(ALL_STAGE, 0x25200), ALL_STAGE, "E cleared")).hit == 0
        assert (await env.lookup(lookup_vpn(NO_S2, 0x25300), NO_S2, "A survives")).hit == 1
        env.sample_fence("hfenceg_vmid", ["stage2_cleared", "other_vmid_survived"])
        env.sample_fence("hfenceg_all", ["stage2_cleared", "stage1_survived"])


# TLBFA-SFENCE-07
async def test_virtualized_sfence_uses_all_address_stage2_path(tlbfa_env):
    env = tlbfa_env
    async with execution(env):
        await env.reset()
        env.program_context(satp_asid=1, vsatp_asid=1, hgatp_vmid=3, virt=1)
        d1 = make_refill(ONLY_S2, 0, (0x26000 << 3) | 0, 0x100000061, vmid=3)
        d2 = make_refill(ONLY_S2, 0, (0x26100 << 3) | 0, 0x200000062, vmid=4)
        a = make_refill(NO_S2, 0, 0x26200, 0x300000063, asid=1)
        e = make_refill(ONLY_S1, 0, 0x26300, 0x400000064, asid=1, vmid=3)
        await env.refill(d1, 0, "D1")
        await env.refill(d2, 1, "D2")
        await env.refill(a, 2, "A")
        await env.refill(e, 3, "E")
        await env.fence("virt_all", 0, 1, 0, 0, note="virt all")
        assert (await env.lookup((0x26000 << 3), ONLY_S2, "D1 cleared")).hit == 0
        assert (await env.lookup(lookup_vpn(NO_S2, 0x26200), NO_S2, "A survives")).hit == 1
        assert (await env.lookup(lookup_vpn(ONLY_S1, 0x26300), ONLY_S1, "E stage1-only is in the vs-stage class and is cleared")).hit == 0
        env.program_context(hgatp_vmid=4)
        assert (await env.lookup((0x26100 << 3), ONLY_S2, "D2 survives")).hit == 1
        env.program_context(hgatp_vmid=3)
        env.sample_fence("virt_all", ["stage2_cleared", "stage1_survived", "other_vmid_survived"])


# TLBFA-SFENCE-08
async def test_bme_address_path_and_cmode_gate(tlbfa_env):
    env = tlbfa_env
    async with execution(env):
        await env.reset()
        env.program_context(satp_asid=1, vsatp_asid=1, hgatp_vmid=3, bme=1, cmode=0)
        a = make_refill(NO_S2, 0, 0x27000, 0x100000071, asid=1)
        b = make_refill(NO_S2, 0, 0x27100, 0x200000072, asid=1, perm_g=1)
        e = make_refill(ONLY_S1, 0, 0x27200, 0x300000073, asid=1, vmid=3)
        await env.refill(a, 0, "A")
        await env.refill(b, 1, "B")
        await env.refill(e, 2, "E")
        await env.fence("bme_all", 0, 1, 0, 0, note="bme all")
        assert (await env.lookup(lookup_vpn(NO_S2, 0x27000), NO_S2, "A cleared")).hit == 0
        assert (await env.lookup(lookup_vpn(NO_S2, 0x27100), NO_S2, "B cleared")).hit == 0
        assert (await env.lookup(lookup_vpn(ONLY_S1, 0x27200), ONLY_S1, "E survives")).hit == 1
        # CMODE=1 disables the implicit all-address BME path; addr is now used.
        c = make_refill(NO_S2, 0, 0x27300, 0x400000074, asid=1)
        await env.refill(c, 3, "C")
        env.program_context(cmode=1)
        await env.fence("bme_gated", 0, 1, 0, 0, note="bme gated")
        assert (await env.lookup(lookup_vpn(NO_S2, 0x27300), NO_S2, "C survives")).hit == 1
        env.sample_fence("bme_all", ["stage1_cleared", "global_cleared", "stage1_survived"])


# TLBFA-SFENCE-09, TLBFA-REFILL-04, TLBFA-COMBO-02
async def test_sfence_has_priority_over_same_cycle_refill(tlbfa_env):
    env = tlbfa_env
    async with execution(env):
        await env.reset()
        env.program_context(satp_asid=1)
        old = make_refill(NO_S2, 0, 0x28000, 0x100000081, asid=1)
        await env.refill(old, 0, "old")
        new = make_refill(NO_S2, 0, 0x28100, 0x200000082, asid=1)
        await env.fence(
            "all_all",
            1,
            1,
            0,
            0,
            same_cycle_refill=(new, 0),
            note="fence+refill",
        )
        assert env.observe_valid(lookup_vpn(NO_S2, 0x28000), NO_S2) == 0
        assert env.observe_valid(lookup_vpn(NO_S2, 0x28100), NO_S2) == 0
        assert (await env.lookup(lookup_vpn(NO_S2, 0x28100), NO_S2, "new invisible")).hit == 0
        env.sample_fence(
            "all_all", ["stage1_cleared"], timing="same_cycle_with_refill"
        )
        if env.coverage is not None:
            env.coverage.sample_refill("bare_no_s2", "4k", 0, "same_cycle_sfence")
        await env.refill(new, 0, "reinstall")
        assert (await env.lookup(lookup_vpn(NO_S2, 0x28100), NO_S2, "new visible")).hit == 1


# TLBFA-SFENCE-03: the address-specific path has no stage-2 class filter; it
# matches the stored tag and the non-global ASID for every translation form.
async def test_address_specific_sfence_matches_every_translation_stage(tlbfa_env):
    env = tlbfa_env
    async with execution(env):
        await env.reset()
        env.program_context(satp_asid=1, vsatp_asid=1, hgatp_vmid=3)
        x = 0x29000
        one = make_refill(ONLY_S1, 0, x, 0x100000091, asid=1, vmid=3)
        both = make_refill(ALL_STAGE, 0, x, 0x200000092, asid=1, vmid=3)
        other = make_refill(NO_S2, 0, x, 0x300000093, asid=2)
        await env.refill(one, 0, "only-s1")
        await env.refill(both, 1, "two-stage")
        await env.refill(other, 2, "other-asid")
        await env.fence("addr_asid", 0, 0, addr_of(x), 1, note="stage-independent")
        assert (await env.lookup(lookup_vpn(ONLY_S1, x), ONLY_S1, "only-s1 cleared")).hit == 0
        assert (await env.lookup(lookup_vpn(ALL_STAGE, x), ALL_STAGE, "two-stage cleared")).hit == 0
        env.program_context(satp_asid=2)
        assert (await env.lookup(lookup_vpn(NO_S2, x), NO_S2, "other asid survives")).hit == 1
