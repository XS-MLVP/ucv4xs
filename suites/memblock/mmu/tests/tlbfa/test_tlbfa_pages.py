"""TLBFA page-size, NAPOT, PPN and stage2-index tests."""
from __future__ import annotations
import pytest

from suites.memblock.mmu.execution import execution
from suites.memblock.mmu.tlbfa.model import ALL_STAGE, NO_S2, ONLY_S1, ONLY_S2, TlbfaModel

from .common import lookup_vpn, make_refill


def vpn_for(kind: int, tag: int, low: int) -> int:
    if kind == ONLY_S2:
        return (tag & ((1 << 38) - 1)) + low
    return (tag << 3) | (low & ((1 << 3) - 1))


# TLBFA-PPN-01
async def test_4k_ppn_low_slot_selection(tlbfa_env):
    env = tlbfa_env
    async with execution(env):
        await env.reset()
        ppn = 0x123456789
        low = (1, 3, 5, 7, 2, 4, 6, 0)
        data = make_refill(NO_S2, 0, 0x500, ppn, ppn_low=low)
        await env.refill(data, 0, "4k-low-slots")
        seen = set()
        for index in range(8):
            vpn = lookup_vpn(NO_S2, 0x500, index)
            snap = await env.lookup(vpn, NO_S2, f"low slot {index}")
            assert snap.hit == 1
            entry = env.model.entries[0]
            assert entry is not None
            expected = TlbfaModel.gen_ppn(entry, vpn)
            assert snap.ppn == expected
            assert (snap.ppn & 0x7) == low[index]
            seen.add(snap.ppn)
        assert len(seen) == 8


# TLBFA-PAGE-01, TLBFA-PAGE-02, TLBFA-PAGE-03, TLBFA-PAGE-04
async def test_page_size_boundaries(tlbfa_env):
    env = tlbfa_env
    async with execution(env):
        await env.reset()
        cases = [
            # (way, s1 tag, level, inside offset, boundary offset)
            (0, 0x600, 0, 7, 8),
            (1, 0x640, 1, 0x1FF, 0x200),
            (2, 0x8000, 2, 0x3FFFF, 0x40000),
            (3, 0x1000000, 3, 0x7FFFFFF, 0x8000000),
        ]
        for way, tag, level, inside, boundary in cases:
            base = vpn_for(NO_S2, tag, 0)
            data = make_refill(NO_S2, level, tag, 0x100000 + way)
            await env.refill(data, way, f"level {level}")
            inside_vpn = base + inside
            outside_vpn = base + boundary
            hit = await env.lookup(inside_vpn, NO_S2, f"level {level} inside")
            assert hit.hit == 1, (level, hex(inside_vpn), hex(tag), hit)
            miss = await env.lookup(outside_vpn, NO_S2, f"level {level} boundary")
            assert miss.hit == 0, (level, hex(outside_vpn), miss)


# TLBFA-PAGE-05, TLBFA-PAGE-06
async def test_valididx_gates_small_pages_and_superpages_use_all_sectors(tlbfa_env):
    env = tlbfa_env
    async with execution(env):
        await env.reset()
        valid = (0, 0, 0, 1, 0, 0, 0, 0)
        data = make_refill(NO_S2, 0, 0x900, 0x222222222, valididx=valid)
        await env.refill(data, 0, "small valididx")
        hit = await env.lookup(lookup_vpn(NO_S2, 0x900, 3), NO_S2, "valid sector")
        assert hit.hit == 1
        miss = await env.lookup(lookup_vpn(NO_S2, 0x900, 4), NO_S2, "invalid sector")
        assert miss.hit == 0
        # A large-page refill makes every subpage visible.
        big = make_refill(NO_S2, 1, 0x940, 0x333333333)
        await env.refill(big, 1, "large page")
        base = vpn_for(NO_S2, 0x940, 0)
        for low in (0, 3, 0x1FF):
            snap = await env.lookup(base + low, NO_S2, f"large low {low}")
            assert snap.hit == 1, (low, hex(base + low), snap)


# TLBFA-NAPOT-01, TLBFA-NAPOT-02, TLBFA-PPN-02
async def test_napot_uses_vpn_low_four_bits(tlbfa_env):
    env = tlbfa_env
    async with execution(env):
        await env.reset()
        tag = 0xA00
        data = make_refill(NO_S2, 0, tag, 0x444444000, n=1, ppn_low=(0,) * 8)
        await env.refill(data, 0, "napot")
        seen = set()
        for low4 in range(16):
            vpn = (tag << 3) | low4
            snap = await env.lookup(vpn, NO_S2, f"napot {low4}")
            assert snap.hit == 1
            entry = env.model.entries[0]
            assert entry is not None
            assert snap.ppn == TlbfaModel.gen_ppn(entry, vpn)
            assert (snap.ppn & 0xF) == low4
            seen.add(snap.ppn)
        assert len(seen) == 16
        # Crossing the 64KB page changes the compared 5-bit tag slice.
        miss = await env.lookup((tag << 3) + 16, NO_S2, "napot boundary")
        assert miss.hit == 0


# TLBFA-S2IDX-01, TLBFA-S2IDX-02
async def test_stage2_pte_index_gates_only_stage2_forms(tlbfa_env):
    env = tlbfa_env
    async with execution(env):
        await env.reset()
        env.program_context(hgatp_vmid=3)
        # onlyStage2: one 4KB subpage is installed by the GPA low bits.
        s2tag = (0xB00 << 3) | 5
        only2 = make_refill(ONLY_S2, 0, s2tag, 0x555550000, vmid=3)
        await env.refill(only2, 0, "only stage2")
        hit = await env.lookup(s2tag, ONLY_S2, "stage2 pteidx hit")
        assert hit.hit == 1
        miss = await env.lookup((s2tag & ~7) | 4, ONLY_S2, "stage2 pteidx miss")
        assert miss.hit == 0
        # onlyStage1 does not apply the stage2 pteidx gate.
        only1 = make_refill(ONLY_S1, 0, 0xB10, 0x666660000, asid=1, vmid=3, pteidx=(1, 0, 0, 0, 0, 0, 0, 0))
        await env.refill(only1, 1, "only stage1")
        env.program_context(vsatp_asid=1)
        hit1 = await env.lookup(lookup_vpn(ONLY_S1, 0xB10, 4), ONLY_S1, "stage1 pteidx ignored")
        assert hit1.hit == 1
        # allStage does apply the s1 pteidx for a 4KB non-NAPOT leaf.
        both = make_refill(
            ALL_STAGE, 0, 0xB20, 0x777770000, asid=1, vmid=3,
            pteidx=(0, 0, 1, 0, 0, 0, 0, 0),
        )
        await env.refill(both, 2, "all stage")
        hit2 = await env.lookup(lookup_vpn(ALL_STAGE, 0xB20, 2), ALL_STAGE, "all pteidx hit")
        miss2 = await env.lookup(lookup_vpn(ALL_STAGE, 0xB20, 4), ALL_STAGE, "all pteidx miss")
        assert hit2.hit == 1 and miss2.hit == 0


# TLBFA-HIT-03, TLBFA-CTX-01..04, TLBFA-COMBO-03
async def test_translation_stage_and_context_are_part_of_the_cam_key(tlbfa_env):
    env = tlbfa_env
    async with execution(env):
        await env.reset()
        env.program_context(satp_asid=1, vsatp_asid=2, hgatp_vmid=3)
        tags = {NO_S2: 0xC00, ONLY_S1: 0xC10, ONLY_S2: 0xC20, ALL_STAGE: 0xC30}
        specs = [
            (NO_S2, make_refill(NO_S2, 0, tags[NO_S2], 0x100000001, asid=1)),
            (ONLY_S1, make_refill(ONLY_S1, 0, tags[ONLY_S1], 0x200000002, asid=2, vmid=3)),
            (ONLY_S2, make_refill(ONLY_S2, 0, (tags[ONLY_S2] << 3) | 5, 0x300000003, vmid=3)),
            (ALL_STAGE, make_refill(ALL_STAGE, 0, tags[ALL_STAGE], 0x400000004, asid=2, vmid=3)),
        ]
        for way, (kind, data) in enumerate(specs):
            await env.refill(data, way, f"stage {kind}")
        vpns = {}
        for kind, data in specs:
            vpns[kind] = data.s2_tag if kind == ONLY_S2 else lookup_vpn(kind, tags[kind], 0)
            snap = await env.lookup(vpns[kind], kind, f"same stage {kind}")
            assert snap.hit == 1
        # A VPN installed for one translation stage does not hit under another
        # stage, because the stage is part of the CAM key.
        wrong_stage = {NO_S2: ONLY_S1, ONLY_S1: NO_S2, ONLY_S2: ALL_STAGE, ALL_STAGE: ONLY_S2}
        for kind in (NO_S2, ONLY_S1, ONLY_S2, ALL_STAGE):
            snap = await env.lookup(vpns[kind], wrong_stage[kind], f"wrong stage {kind}")
            assert snap.hit == 0
        # ASID and VMID are checked where the stage requires them.
        env.program_context(satp_asid=9)
        miss = await env.lookup(vpns[NO_S2], NO_S2, "stage1 wrong asid")
        assert miss.hit == 0
        env.program_context(satp_asid=1, vsatp_asid=9)
        miss = await env.lookup(vpns[ONLY_S1], ONLY_S1, "only1 wrong asid")
        assert miss.hit == 0
        env.program_context(vsatp_asid=2, hgatp_vmid=8)
        miss = await env.lookup(vpns[ONLY_S1], ONLY_S1, "only1 wrong vmid")
        assert miss.hit == 0
        miss = await env.lookup(vpns[ONLY_S2], ONLY_S2, "only2 wrong vmid")
        assert miss.hit == 0


# TLBFA-CTX-02, TLBFA-CTX-04, TLBFA-GLOBAL-01
async def test_global_bit_only_relaxes_asid_and_stage2_ignores_stage1_asid(tlbfa_env):
    env = tlbfa_env
    async with execution(env):
        await env.reset()
        env.program_context(satp_asid=2, vsatp_asid=3, hgatp_vmid=4)
        global1 = make_refill(NO_S2, 0, 0xD00, 0x123123123, asid=7, perm_g=1)
        await env.refill(global1, 0, "global stage1")
        for asid in (0, 2, 7, 15):
            env.program_context(satp_asid=asid)
            snap = await env.lookup(lookup_vpn(NO_S2, 0xD00), NO_S2, f"global asid {asid}")
            assert snap.hit == 1
        # Global does not relax VMID for a two-stage entry.
        both = make_refill(ALL_STAGE, 0, 0xD10, 0x223223223, asid=7, vmid=4, perm_g=1)
        await env.refill(both, 1, "global two-stage")
        env.program_context(satp_asid=0, hgatp_vmid=4)
        assert (await env.lookup(lookup_vpn(ALL_STAGE, 0xD10), ALL_STAGE, "global vmid ok")).hit == 1
        env.program_context(hgatp_vmid=5)
        assert (await env.lookup(lookup_vpn(ALL_STAGE, 0xD10), ALL_STAGE, "global vmid bad")).hit == 0
        # onlyStage2 does not use the stage1 ASID.
        only2 = make_refill(ONLY_S2, 0, (0xD20 << 3) | 6, 0x323323323, asid=0, vmid=6)
        await env.refill(only2, 2, "only2")
        env.program_context(satp_asid=9, vsatp_asid=9, hgatp_vmid=6)
        assert (await env.lookup((0xD20 << 3) | 6, ONLY_S2, "only2 asid ignored")).hit == 1


# TLBFA-PAYLOAD-01
async def test_payload_metadata_is_returned_from_selected_entry(tlbfa_env):
    env = tlbfa_env
    async with execution(env):
        await env.reset()
        env.program_context(vsatp_asid=2, hgatp_vmid=3)
        data = make_refill(
            ALL_STAGE, 0, 0xE00, 0x444444444, asid=2, vmid=3,
            pbmt=3, g_pbmt=2, s1_pf=1, s1_af=1, s2_gpf=1, s2_gaf=1,
            s1_perm_r=0, s1_perm_w=1, s1_perm_x=1, s2_perm_a=0, s2_perm_x=0,
        )
        await env.refill(data, 0, "payload")
        snap = await env.lookup(lookup_vpn(ALL_STAGE, 0xE00), ALL_STAGE, "payload hit")
        assert snap.hit == 1
        assert snap.pbmt == 3 and snap.g_pbmt == 2
        assert snap.perm["pf"] == 1 and snap.perm["af"] == 1
        assert snap.g_perm["pf"] == 1 and snap.g_perm["af"] == 1
        assert snap.perm["w"] == 1 and snap.perm["x"] == 1 and snap.perm["r"] == 0
        assert snap.g_perm["a"] == 0 and snap.g_perm["x"] == 0


# TLBFA-HIT-01: characterize the implemented all-stage level merge for a fake
# stage-1 PTE with a stage-2 exception. The generated condition order makes the
# documented "force level 3" arm unreachable; the observed result is s1_level.
@pytest.mark.characterization
async def test_all_stage_fake_pte_with_stage2_exception_uses_s1_level(tlbfa_env):
    env = tlbfa_env
    async with execution(env):
        await env.reset()
        env.program_context(vsatp_asid=1, hgatp_vmid=2)
        data = make_refill(
            ALL_STAGE, 0, 0x2A000, 0x666666666,
            asid=1, vmid=2, s1_v=0,
            s1_perm_r=0, s1_perm_w=0, s1_perm_x=0,
            s2_gpf=1,
        )
        await env.refill(data, 0, "fake PTE + stage2 exception")
        entry = env.model.entries[0]
        assert entry is not None and entry.level == 0
        vpn = lookup_vpn(ALL_STAGE, 0x2A000)
        snap = await env.lookup(vpn, ALL_STAGE, "fake PTE uses s1 level")
        assert snap.hit == 1
