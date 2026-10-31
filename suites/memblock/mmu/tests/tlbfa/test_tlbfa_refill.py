"""TLBFA refill forms and all-way coverage."""
from __future__ import annotations

from suites.memblock.mmu.execution import execution
from suites.memblock.mmu.tlbfa.model import ALL_STAGE, NO_S2, ONLY_S1, ONLY_S2

from .common import lookup_vpn, make_refill

KINDS = (NO_S2, ONLY_S1, ONLY_S2, ALL_STAGE)


# TLBFA-COMBO-01, TLBFA-REFILL-03
async def test_all_48_ways_are_independently_addressable(tlbfa_env):
    env = tlbfa_env
    async with execution(env):
        await env.reset()
        tags = [0x1000 + way * 3 for way in range(48)]
        for way in range(48):
            data = make_refill(NO_S2, 0, tags[way], 0x100000000 + way)
            await env.refill(data, way, f"way {way}")
        for way in range(48):
            vpn = lookup_vpn(NO_S2, tags[way])
            snap = await env.lookup(vpn, NO_S2, f"way {way} hit")
            assert snap.hit == 1, way
            assert snap.access_bits == way
        for way in range(48):
            assert env.model.valid[way] == 1
        # Clear all hitVecReg bits after the last hit so every bit is observed
        # in both directions.
        miss = await env.lookup(0x3FFFFFFFF, NO_S2, "clear hit vector")
        assert miss.hit == 0


# TLBFA-REFILL-01, TLBFA-REFILL-04, TLBFA-PAGE-05
async def test_every_stage_and_page_form_can_be_installed(tlbfa_env):
    env = tlbfa_env
    async with execution(env):
        await env.reset()
        env.program_context(satp_asid=4, vsatp_asid=4, hgatp_vmid=5)
        way = 0
        for kind in KINDS:
            for page in range(5):
                level = 0 if page == 4 else page
                n = 1 if page == 4 else 0
                high = 0x2000 + (kind * 5 + page) * 0x2000000
                if kind == ONLY_S2:
                    stored_tag = (high << 3) | 0
                else:
                    stored_tag = high
                data = make_refill(
                    kind,
                    level,
                    stored_tag,
                    0x300000000 + way * 0x101,
                    n=n,
                    asid=4,
                    vmid=5,
                    pteidx=(1, 0, 0, 0, 0, 0, 0, 0),
                )
                await env.refill(data, way, f"kind {kind} page {page}")
                if kind == ONLY_S2:
                    vpn = stored_tag
                elif n:
                    vpn = (stored_tag << 3) | 5
                else:
                    vpn = lookup_vpn(kind, stored_tag)
                snap = await env.lookup(vpn, kind, f"kind {kind} page {page} hit")
                assert snap.hit == 1, (kind, page, hex(vpn))
                way += 1
        assert way == 20


# TLBFA-SFENCE-09
async def test_invalidated_way_can_be_refilled_with_a_new_translation(tlbfa_env):
    env = tlbfa_env
    async with execution(env):
        await env.reset()
        env.program_context(satp_asid=1)
        old = make_refill(NO_S2, 0, 0x1800, 0x400000000, asid=1)
        await env.refill(old, 5, "old")
        env.program_context(satp_asid=1)
        await env.fence("all_all", 1, 1, 0, 0, note="invalidate")
        assert env.observe_valid(lookup_vpn(NO_S2, 0x1800), NO_S2) == 0
        await env.lookup(lookup_vpn(NO_S2, 0x1800), NO_S2, "invalidated entry data is still present")
        env.sample_fence("all_all", ["stage1_cleared"])
        new = make_refill(NO_S2, 0, 0x1801, 0x500000000, asid=1)
        await env.refill(new, 5, "reuse way")
        snap = await env.lookup(lookup_vpn(NO_S2, 0x1801), NO_S2, "new translation")
        assert snap.hit == 1
