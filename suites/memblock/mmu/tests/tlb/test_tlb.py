"""TLB (ITLB) parent integration tests."""
from __future__ import annotations

from suites.memblock.mmu.execution import execution
from suites.memblock.mmu.tlbfa.model import ALL_STAGE, NO_S2, ONLY_S2

from ..tlbfa.common import make_refill


def pte_for(vaddr: int, **overrides) -> object:
    vpn = (vaddr >> 12) & ((1 << 38) - 1)
    defaults = dict(
        kind=NO_S2,
        level=0,
        tag=vpn >> 3,
        ppn=0x34567,
        asid=0,
        vmid=0,
        valididx=(1,) * 8,
        pteidx=(1, 0, 0, 0, 0, 0, 0, 0),
        ppn_low=tuple(index & 7 for index in range(8)),
        s1_perm_r=1,
        s1_perm_w=0,
        s1_perm_x=1,
        s2_perm_a=1,
        s2_perm_x=0,
    )
    if "kind" in overrides:
        defaults["kind"] = overrides.pop("kind")
    return make_refill(**{**defaults, **overrides})


# TLB-BARE-01
async def test_bare_mode_passes_address_without_ptw(tlb_env):
    env = tlb_env
    async with execution(env):
        await env.reset()
        env.set_context(satp_mode=0, imode=0)
        await env.settle(3)
        snap = await env.issue(0x12345678, note="bare")
        assert snap.miss == 0 and snap.ptw.valid == 0
        assert snap.paddr == 0x12345678


# TLB-BARE-02
async def test_m_mode_disables_translation_even_with_satp(tlb_env):
    env = tlb_env
    async with execution(env):
        await env.reset()
        env.set_context(satp_mode=8, imode=3, satp_asid=1)
        await env.settle(3)
        snap = await env.issue(0x22223333, note="M mode")
        assert snap.paddr == 0x22223333
        assert snap.miss == 0 and snap.ptw.valid == 0


# TLB-MISS-01, TLB-PTW-01
async def test_sv39_miss_requests_ptw_with_vpn(tlb_env):
    env = tlb_env
    async with execution(env):
        await env.reset()
        env.set_context(satp_mode=8, imode=0)
        await env.settle(3)
        vaddr = 0x12345678
        snap = await env.issue(vaddr, note="sv39 miss")
        assert snap.miss == 1
        assert snap.ptw.valid == 1
        assert snap.ptw.vpn == vaddr >> 12
        assert snap.ptw.s2xlate == NO_S2


# TLB-REFILL-01: matching PTW response installs a translation; a later request
# hits and returns the PPN composed by the real TLBFA child.
async def test_ptw_refill_then_hit(tlb_env):
    env = tlb_env
    async with execution(env):
        await env.reset()
        env.set_context(satp_mode=8, imode=0)
        await env.settle(3)
        vaddr = 0x12345678
        miss = await env.issue(vaddr, note="miss")
        assert miss.miss == 1 and miss.ptw.valid == 1
        pte = pte_for(vaddr, ppn=0x34567)
        await env.ptw_respond(pte, addr_low=(vaddr >> 12) & 7)
        hit = await env.issue(vaddr, note="refilled hit")
        assert hit.miss == 0 and hit.ptw.valid == 0
        assert hit.paddr & 0xFFF == vaddr & 0xFFF
        # A different offset in the same page uses the same translation.
        other = (vaddr & ~0xFFF) | 0xABC
        hit2 = await env.issue(other, note="same page other offset")
        assert hit2.paddr == ((hit.paddr & ~0xFFF) | 0xABC)


# TLB-REFILL-02
async def test_ptw_response_for_a_different_tag_does_not_satisfy_miss(tlb_env):
    env = tlb_env
    async with execution(env):
        await env.reset()
        env.set_context(satp_mode=8, imode=0)
        await env.settle(3)
        vaddr = 0x12345678
        miss = await env.issue(vaddr, note="miss")
        assert miss.miss == 1
        wrong = pte_for(vaddr, tag=((vaddr >> 12) >> 3) + 1)
        await env.ptw_respond(wrong, addr_low=(vaddr >> 12) & 7)
        # The pending translation was still not resolved.
        snap = await env.issue(vaddr, note="mismatched refill")
        assert snap.miss == 1 and snap.ptw.valid == 1


# TLB-FENCE-01
async def test_sfence_all_invalidates_refilled_stage1(tlb_env):
    env = tlb_env
    async with execution(env):
        await env.reset()
        env.set_context(satp_mode=8, imode=0, satp_asid=0)
        await env.settle(3)
        vaddr = 0x23456000
        assert (await env.issue(vaddr, note="miss")).miss == 1
        await env.ptw_respond(pte_for(vaddr), addr_low=(vaddr >> 12) & 7)
        assert (await env.issue(vaddr, note="hit")).miss == 0
        await env.sfence(1, 1, 0, 0, note="all/all")
        snap = await env.issue(vaddr, note="after sfence")
        assert snap.miss == 1 and snap.ptw.valid == 1


# TLB-CTX-01: a stage-2 context miss reports the all-stage class to the PTW.
async def test_virtualized_stage2_miss_requests_all_stage(tlb_env):
    env = tlb_env
    async with execution(env):
        await env.reset()
        env.set_context(
            satp_mode=0, imode=0, virt=1,
            vsatp_mode=8, hgatp_mode=8, hgatp_vmid=3,
        )
        await env.settle(3)
        snap = await env.issue(0x34567000, note="stage2 miss")
        assert snap.miss == 1
        assert snap.ptw.valid == 1
        assert snap.ptw.s2xlate == 3


async def _miss_refill_hit(env, vaddr: int, asid: int = 0, vmid: int = 0, **pte_overrides):
    pte = pte_for(vaddr, asid=asid, vmid=vmid, **pte_overrides)
    miss = await env.issue(vaddr, note="fault miss")
    assert miss.miss == 1
    await env.ptw_respond(pte, addr_low=(vaddr >> 12) & 7)
    return await env.issue(vaddr, note="fault hit")


# TLB-EXCP-01
async def test_instruction_page_fault_on_missing_x_permission(tlb_env):
    env = tlb_env
    async with execution(env):
        await env.reset()
        env.set_context(satp_mode=8, imode=0)
        await env.settle(3)
        hit = await _miss_refill_hit(env, 0x30123000, s1_perm_x=0)
        assert hit.pf == 1 and hit.af == 0
        env.coverage.sample_exception("pf_x")


# TLB-EXCP-02
async def test_instruction_page_fault_on_user_bit_mismatch(tlb_env):
    env = tlb_env
    async with execution(env):
        await env.reset()
        env.set_context(satp_mode=8, imode=0)
        await env.settle(3)
        hit = await _miss_refill_hit(env, 0x30234000, s1_perm_u=0)
        assert hit.pf == 1
        env.coverage.sample_exception("pf_u")


# TLB-EXCP-03
async def test_instruction_page_fault_when_accessed_bit_is_clear(tlb_env):
    env = tlb_env
    async with execution(env):
        await env.reset()
        env.set_context(satp_mode=8, imode=0)
        await env.settle(3)
        hit = await _miss_refill_hit(env, 0x30345000, s1_perm_a=0)
        assert hit.pf == 1
        env.coverage.sample_exception("pf_a")


# TLB-EXCP-04
async def test_access_fault_has_priority_over_page_fault(tlb_env):
    env = tlb_env
    async with execution(env):
        await env.reset()
        env.set_context(satp_mode=8, imode=0)
        await env.settle(3)
        hit = await _miss_refill_hit(env, 0x30456000, s1_af=1, s1_perm_x=0)
        assert hit.af == 1 and hit.pf == 0
        env.coverage.sample_exception("af_set")


# TLB-EXCP-05
async def test_fake_pte_is_reported_as_nonleaf_like(tlb_env):
    env = tlb_env
    async with execution(env):
        await env.reset()
        env.set_context(satp_mode=8, imode=0)
        await env.settle(3)
        hit = await _miss_refill_hit(env, 0x30567000, s1_v=0, s1_perm_x=0)
        assert hit.fake_or_nonleaf == 1
        assert hit.pf == 0
        env.coverage.sample_exception("fake")


# TLB-EXCP-06
async def test_nonleaf_pte_does_not_raise_a_leaf_page_fault(tlb_env):
    env = tlb_env
    async with execution(env):
        await env.reset()
        env.set_context(satp_mode=8, imode=0)
        await env.settle(3)
        hit = await _miss_refill_hit(
            env, 0x30678000, s1_perm_r=0, s1_perm_w=0, s1_perm_x=0
        )
        assert hit.fake_or_nonleaf == 1 and hit.pf == 0
        env.coverage.sample_exception("fake")


# TLB-EXCP-07, TLB-BARE-03
async def test_clean_hit_and_sv48_mode(tlb_env):
    env = tlb_env
    async with execution(env):
        await env.reset()
        env.set_context(satp_mode=9, imode=0)
        await env.settle(3)
        hit = await _miss_refill_hit(env, 0x30789000)
        assert hit.pf == 0 and hit.af == 0 and hit.gpf == 0
        env.coverage.sample_exception("none")
        await env.reset("with_valid_entries")


# TLB-CTX-02, TLB-REFILL-03: two-stage PTW response installs a merged entry and
# a later virtualized request hits with the merged PPN.
async def test_two_stage_refill_and_hit(tlb_env):
    env = tlb_env
    async with execution(env):
        await env.reset()
        env.set_context(
            satp_mode=0, imode=0, virt=1, vsatp_mode=8, hgatp_mode=8,
            satp_asid=1, hgatp_vmid=3,
        )
        await env.settle(3)
        vaddr = 0x40000000
        miss = await env.issue(vaddr, note="two-stage miss")
        assert miss.miss == 1 and miss.ptw.s2xlate == 3
        vpn = vaddr >> 12
        pte = make_refill(
            ALL_STAGE, 0, vpn >> 3, 0x123456789,
            asid=1, vmid=3, s1_perm_r=1, s1_perm_x=1,
            s1_perm_u=1, s2_perm_a=1, s2_perm_x=1,
        )
        await env.ptw_respond(pte, addr_low=vpn & 7)
        hit = await env.issue(vaddr, note="two-stage hit")
        assert hit.miss == 0 and hit.ptw.valid == 0
        env.coverage.sample_exception("none")


# TLB-FENCE-02, TLB-FENCE-03
async def test_sfence_all_asid_and_address_forms(tlb_env):
    env = tlb_env
    async with execution(env):
        await env.reset()
        env.set_context(satp_mode=8, imode=0, satp_asid=1)
        await env.settle(3)
        a, b = 0x50000000, 0x50100000
        await _miss_refill_hit(env, a, asid=1)
        env.set_context(satp_mode=8, imode=0, satp_asid=2)
        await env.settle(3)
        await _miss_refill_hit(env, b, asid=2)
        env.set_context(satp_mode=8, imode=0, satp_asid=1)
        await env.settle(3)
        await env.sfence(1, 0, 0, 1, note="all asid")
        env.sample_fence(1, 0, 0, 0, ("cleared", "survived"))
        miss_a = await env.issue(a, note="A cleared")
        assert miss_a.miss == 1
        env.set_context(satp_mode=8, imode=0, satp_asid=2)
        await env.settle(3)
        hit_b = await env.issue(b, note="B survives")
        assert hit_b.miss == 0

        # Address-specific form on the surviving B and a new C.
        env.set_context(satp_mode=8, imode=0, satp_asid=2)
        await env.settle(3)
        c = 0x50200000
        await _miss_refill_hit(env, c, asid=2)
        await env.sfence(0, 0, (b >> 12) << 12, 2, note="address")
        env.sample_fence(0, 0, 0, 0, ("cleared", "survived"))
        assert (await env.issue(b, note="B cleared by address")).miss == 1
        assert (await env.issue(c, note="C survives address")).miss == 0


# TLB-FENCE-04
async def test_hfence_forms_do_not_clear_no_s2_entries(tlb_env):
    env = tlb_env
    async with execution(env):
        await env.reset()
        env.set_context(satp_mode=8, imode=0)
        await env.settle(3)
        vaddr = 0x60000000
        await _miss_refill_hit(env, vaddr)
        await env.sfence(0, 1, 0, 0, hv=1, note="hfencev")
        env.sample_fence(0, 1, 1, 0, ("survived",))
        assert (await env.issue(vaddr, note="no-s2 survives hfencev")).miss == 0
        await env.sfence(0, 1, 0, 0, hg=1, note="hfenceg")
        env.sample_fence(0, 1, 0, 1, ("survived",))
        assert (await env.issue(vaddr, note="no-s2 survives hfenceg")).miss == 0
        await env.reset("with_valid_entries")


# TLB-FENCE-05: all sfence/hfence forms are accepted and have the expected
# stage-class effect on a no-S2 entry.
async def test_sfence_and_hfence_forms(tlb_env):
    env = tlb_env
    async with execution(env):
        await env.reset()
        env.set_context(satp_mode=8, imode=0)
        await env.settle(3)
        vaddr = 0x61000000
        await _miss_refill_hit(env, vaddr)
        # Address-specific and all-ASID forms all target the no-S2 entry.
        for rs1, rs2, form in ((1, 1, "all_all"), (1, 0, "all_asid")):
            await env.sfence(rs1, rs2, 0, 0, note=form)
            env.sample_fence(rs1, rs2, 0, 0, ("cleared",))
            assert (await env.issue(vaddr, note=form)).miss == 1
            await _miss_refill_hit(env, vaddr)
        await env.sfence(0, 0, (vaddr >> 12) << 12, 0, note="addr")
        env.sample_fence(0, 0, 0, 0, ("cleared",))
        assert (await env.issue(vaddr, note="addr")).miss == 1
        await _miss_refill_hit(env, vaddr)
        # Hardware guest fences do not apply to no-S2 entries.
        await env.sfence(0, 1, 0, 0, hv=1, note="hfencev")
        env.sample_fence(0, 1, 1, 0, ("survived",))
        assert (await env.issue(vaddr, note="hfencev")).miss == 0
        await env.sfence(0, 0, 0, 0, hv=1, note="hfencev asid")
        env.sample_fence(0, 0, 1, 0, ("survived",))
        assert (await env.issue(vaddr, note="hfencev asid")).miss == 0
        await env.sfence(0, 1, 0, 0, hg=1, note="hfenceg")
        env.sample_fence(0, 1, 0, 1, ("survived",))
        assert (await env.issue(vaddr, note="hfenceg")).miss == 0
        await env.sfence(0, 0, 0, 0, hg=1, note="hfenceg vmid")
        env.sample_fence(0, 0, 0, 1, ("survived",))
        assert (await env.issue(vaddr, note="hfenceg vmid")).miss == 0
        await env.sfence(0, 1, (vaddr >> 12) << 12, 0, note="addr all asid")
        env.sample_fence(0, 1, 0, 0, ("cleared",))
        assert (await env.issue(vaddr, note="addr all asid")).miss == 1


# TLB-SWEEP-01: fill enough distinct translations through the real PTW path to
# select all 48 TLBFA ways, then hit each selected way.
async def test_many_ptw_refills_cover_all_storage_ways(tlb_env):
    env = tlb_env
    async with execution(env):
        await env.reset()
        env.set_context(satp_mode=8, imode=0)
        await env.settle(3)
        for index in range(63):
            vaddr = (0x1000 + index * 8) << 12
            miss = await env.issue(vaddr, note=f"fill {index}")
            assert miss.miss == 1
            pte = pte_for(vaddr, ppn=0x100000 + index)
            await env.ptw_respond(pte, addr_low=(vaddr >> 12) & 7)
        assert env.model.storage.tlbfa.valid.count(0) == 0
        for way in range(48):
            entry = env.model.storage.tlbfa.entries[way]
            assert entry is not None
            vaddr = (entry.tag << 3) << 12
            hit = await env.issue(vaddr, note=f"hit way {way}")
            assert hit.miss == 0
        await env.reset("with_valid_entries")


# TLB-SWEEP-02: all-ones and all-zeros PTW patterns toggle every TLBFA state bit
# through the real parent write port.
async def test_parent_storage_toggle_through_ptw(tlb_env):
    env = tlb_env
    async with execution(env):
        await env.reset()
        env.set_context(satp_mode=8, imode=0)
        await env.settle(3)
        ones = make_refill(
            NO_S2, 0, (1 << 35) - 1, (1 << 41) - 1,
            asid=0, valididx=(1,) * 8, pteidx=(1,) * 8,
            ppn_low=(7,) * 8, pbmt=3, g_pbmt=3,
            s1_perm_r=1, s1_perm_w=1, s1_perm_x=1,
            s1_perm_a=1, s1_perm_u=1, perm_g=1,
            s2_perm_a=1, s2_perm_x=1,
        )
        zeros = make_refill(
            NO_S2, 0, 0, 0, asid=0,
            valididx=(0,) * 8, pteidx=(0,) * 8, ppn_low=(0,) * 8,
            s1_perm_r=0, s1_perm_w=0, s1_perm_x=0,
            s1_perm_a=0, s1_perm_u=0, perm_g=0,
            s2_perm_a=0, s2_perm_x=0, s1_v=0,
        )
        for index in range(63):
            vaddr = (0x2000 + index * 8) << 12
            assert (await env.issue(vaddr, note=f"ones miss {index}")).miss == 1
            await env.ptw_respond(ones, addr_low=(vaddr >> 12) & 7)
        await env.reset("with_valid_entries")
        env.set_context(satp_mode=8, imode=0)
        await env.settle(3)
        for index in range(63):
            vaddr = (0x3000 + index * 8) << 12
            assert (await env.issue(vaddr, note=f"zeros miss {index}")).miss == 1
            await env.ptw_respond(zeros, addr_low=(vaddr >> 12) & 7)


# TLB-CTX-03: onlyStage1 and onlyStage2 request classes are both forwarded to
# the PTW with their distinct encodings.
async def test_only_stage1_and_only_stage2_ptw_classes(tlb_env):
    env = tlb_env
    async with execution(env):
        await env.reset()
        env.set_context(satp_mode=0, imode=0, virt=1,
                        vsatp_mode=8, hgatp_mode=0, satp_asid=1, hgatp_vmid=2)
        await env.settle(3)
        s1 = await env.issue(0x70000000, note="only stage1 miss")
        assert s1.miss == 1 and s1.ptw.valid == 1 and s1.ptw.s2xlate == 1
        await env.reset()
        env.set_context(satp_mode=0, imode=0, virt=1,
                        vsatp_mode=0, hgatp_mode=8, satp_asid=1, hgatp_vmid=2)
        await env.settle(3)
        s2 = await env.issue(0x71000000, note="only stage2 miss")
        assert s2.miss == 1 and s2.ptw.valid == 1 and s2.ptw.s2xlate == 2


# TLB-REFILL-04: onlyStage2 uses the GPA as the tag and stores a G-stage-only
# translation; a later request hits and returns the G-stage PPN.
async def test_only_stage2_refill_and_hit(tlb_env):
    env = tlb_env
    async with execution(env):
        await env.reset()
        env.set_context(satp_mode=0, imode=0, virt=1,
                        vsatp_mode=0, hgatp_mode=8, satp_asid=1, hgatp_vmid=2)
        await env.settle(3)
        vaddr = 0x72000000
        miss = await env.issue(vaddr, note="only stage2 miss")
        assert miss.miss == 1 and miss.ptw.s2xlate == 2
        vpn = vaddr >> 12
        pte = make_refill(
            ONLY_S2, 0, vpn, 0x234567890, vmid=2,
            s2_perm_a=1, s2_perm_x=1,
        )
        await env.ptw_respond(pte, addr_low=vpn & 7)
        await env.settle(5)
        hit = await env.issue(vaddr, note="only stage2 hit")
        assert hit.miss == 0 and hit.ptw.valid == 0


# TLB-REFILL-05: a PTW response also completes the outstanding miss in the same
# cycle through the just-back path.
async def test_ptw_response_completes_outstanding_request(tlb_env):
    env = tlb_env
    async with execution(env):
        await env.reset()
        env.set_context(satp_mode=8, imode=0)
        await env.settle(3)
        vaddr = 0x73000000
        miss = await env.issue(vaddr, note="outstanding miss")
        assert miss.miss == 1
        vpn = vaddr >> 12
        pte = pte_for(vaddr, ppn=0x45678)
        env._drive_ptw(pte, addr_low=vpn & 7)
        await env.edge()
        env.model.refill(pte)
        snap = env.read_response()
        expected = env.model.translate(vaddr)
        assert snap.miss == expected.miss
        assert snap.paddr == expected.paddr
        env._drive_ptw(None)
        await env.settle(2)


async def test_two_stage_ptw_response_completes_outstanding_request(tlb_env):
    env = tlb_env
    async with execution(env):
        await env.reset()
        env.set_context(satp_mode=0, imode=0, virt=1,
                        vsatp_mode=8, hgatp_mode=8, satp_asid=1, hgatp_vmid=3)
        await env.settle(3)
        vaddr = 0x74000000
        miss = await env.issue(vaddr, note="two-stage outstanding")
        assert miss.miss == 1 and miss.ptw.s2xlate == 3
        vpn = vaddr >> 12
        pte = make_refill(
            ALL_STAGE, 0, vpn >> 3, 0x567890123,
            asid=1, vmid=3, s1_perm_r=1, s1_perm_x=1,
            s1_perm_u=1, s2_perm_a=1, s2_perm_x=1,
        )
        env._drive_ptw(pte, addr_low=vpn & 7)
        await env.edge()
        env.model.refill(pte)
        snap = env.read_response()
        expected = env.model.translate(vaddr)
        assert snap.miss == expected.miss
        assert snap.paddr == expected.paddr
        env._drive_ptw(None)
        await env.settle(2)


# TLB-GPA-REPLAY-01: an allStage entry whose G stage faults requests the GPA
# with getGpa=1, then reports gpf with the S1 GPA after the GPA response.
async def test_gpa_replay_for_all_stage_gpf(tlb_env):
    from suites.memblock.mmu.tlbfa.model import ALL_STAGE

    env = tlb_env
    async with execution(env):
        await env.reset()
        env.set_context(satp_mode=8, virt=1, vsatp_mode=8, hgatp_mode=8,
                        imode=0)
        await env.settle(4)
        vaddr = 0x12345678
        miss = await env.issue(vaddr, note="gpa miss")
        assert miss.miss == 1
        vpn = (vaddr >> 12) & ((1 << 38) - 1)
        lane = vpn & 7
        data = pte_for(vaddr, kind=ALL_STAGE, ppn=0x34567,
                       ppn_low=tuple(7 for _ in range(8)),
                       pteidx=tuple(1 if index == lane else 0
                                    for index in range(8)))
        data.s2_gpf = 1
        data.s2_perm_a = 0
        data.s2_perm_d = 0
        data.s2_perm_x = 0
        await env.ptw_respond(data, addr_low=lane)
        # Hold the same request; the TLB must ask for the GPA instead of
        # returning a normal translation.
        env._write(env.req_valid, 1)
        env._write(env.req_vaddr, vaddr)
        env._write(env.req_fullva, vaddr)
        saw_get_gpa = False
        for _ in range(12):
            await env.edge()
            if env.read(env.ptw_req["valid"]) and env.read(env.ptw_req["get_gpa"]):
                saw_get_gpa = True
                break
        assert saw_get_gpa, "no getGpa request for the allStage G-stage fault"
        env._write(env.req_valid, 0)
        env._ptw_pins["valid"].Set(0)
        await env.edge()
        await env.ptw_respond(data, addr_low=lane, get_gpa=1, wait=1)
        expected_gpa = (((0x34567 << 3) | 7) << 12) | (vaddr & 0xFFF)
        gpf = None
        seen = []
        for _ in range(20):
            await env.edge()
            seen.append((env.read(env.resp["gpf"]),
                         hex(env.read(env.resp["gpaddr"])),
                         env.read(env.ptw_req["get_gpa"])))
            if env.read(env.resp["gpf"]) and env.read(env.resp["gpaddr"]) == expected_gpa:
                gpf = env.read_response()
                break
        for _ in range(12):
            await env.edge()
        assert gpf is not None, ("GPA response did not update the faulting gpaddr",
                                 hex(expected_gpa), seen)
        assert gpf.gpf == 1, gpf
        assert gpf.gpaddr == expected_gpa, (hex(gpf.gpaddr), hex(expected_gpa))
