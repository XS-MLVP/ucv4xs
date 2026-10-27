"""TlbStorageWrapper composition and PLRU replacement tests."""
from __future__ import annotations

from mmuverify.common.runtime import execution
from mmuverify.tlbfa.model import ALL_STAGE, NO_S2, ONLY_S1, ONLY_S2

from ..tlbfa.common import lookup_vpn, make_refill


def pair_for(kind: int, tag: int, low: int = 0) -> tuple[int, int]:
    if kind == ONLY_S2:
        return tag, kind
    return lookup_vpn(kind, tag, low), kind


async def assert_live(env, pairs, note: str):
    live_expected = [
        index for index, (vpn, stage) in enumerate(pairs) if env.model.tlbfa.hit_ways(vpn, stage)
    ]
    probes = await env.probe(pairs)
    live_actual = [index for index, probe in enumerate(probes) if probe.hit]
    assert live_actual == live_expected, f"{note}: live {live_actual} != {live_expected}"


# WRAP-RESET-01, WRAP-REPLACE-01
async def test_reset_and_initial_plru_victim_sequence(wrapper_env):
    env = wrapper_env
    async with execution(env.dut):
        await env.reset()
        pairs = []
        victims = []
        for index in range(60):
            tag = 0x40000 + index * 0x40
            data = make_refill(NO_S2, 0, tag, 0x100000000 + index)
            victim = await env.refill(data, f"refill {index}")
            victims.append(victim)
            pairs.append(pair_for(NO_S2, tag))
        # PLRU starts at zero; these are the first victims of the real wrapper.
        assert victims[0] == 0
        assert victims[1] == 32
        # The pure tree-PLRU fill order leaves ways 15 and 31 untouched during
        # the first 60 refills. Refill once (way 15), then steer with a read
        # hit on way 32 and refill again (way 31); this covers every victim way.
        tag = 0x42000
        victims.append(await env.refill(make_refill(NO_S2, 0, tag, 0x300000000), "victim 15"))
        pairs.append(pair_for(NO_S2, tag))
        tag = 0x42100
        victims.append(await env.refill(make_refill(NO_S2, 0, tag, 0x300000100), "victim 47"))
        pairs.append(pair_for(NO_S2, tag))
        steer = None
        for vpn, stage in pairs:
            if env.model.tlbfa.hit_ways(vpn, stage) == [32]:
                steer = (vpn, stage)
                break
        assert steer is not None, "way 32 must hold a unique translation"
        assert (await env.lookup(steer[0], steer[1], "steer way 32")).hit == 1
        tag = 0x42200
        victims.append(await env.refill(make_refill(NO_S2, 0, tag, 0x300000200), "victim 31"))
        pairs.append(pair_for(NO_S2, tag))
        assert set(victims) == set(range(48)), sorted(set(range(48)) - set(victims))
        assert env.model.tlbfa.valid.count(0) == 0
        await assert_live(env, pairs, "initial PLRU sequence")
        env.coverage.sample_reset("with_valid_entries")


# WRAP-REPLACE-02
async def test_read_hit_changes_next_plru_victim(wrapper_env):
    env = wrapper_env
    async with execution(env.dut):
        await env.reset()
        pairs = []
        for index in range(12):
            tag = 0x50000 + index * 0x40
            data = make_refill(NO_S2, 0, tag, 0x200000000 + index)
            await env.refill(data, f"fill {index}")
            pairs.append(pair_for(NO_S2, tag))
        # Select a currently valid translation and touch it. The next refill
        # must use the PLRU state updated by that read hit.
        live = [index for index, (vpn, stage) in enumerate(pairs) if env.model.tlbfa.hit_ways(vpn, stage)]
        assert live
        chosen = live[len(live) // 2]
        vpn, stage = pairs[chosen]
        snap = await env.lookup(vpn, stage, "touch for replacement")
        assert snap.hit == 1
        tag = 0x51000
        data = make_refill(NO_S2, 0, tag, 0x300000000)
        await env.refill(data, "refill after hit")
        pairs.append(pair_for(NO_S2, tag))
        await assert_live(env, pairs, "after read-hit update")


# WRAP-REFILL-01
async def test_refill_is_visible_next_cycle_and_same_cycle_read_is_suppressed(wrapper_env):
    env = wrapper_env
    async with execution(env.dut):
        await env.reset()
        tag = 0x52000
        data = make_refill(NO_S2, 0, tag, 0x400000000)
        snap = await env.refill_and_lookup(data, lookup_vpn(NO_S2, tag), NO_S2, "same-cycle")
        assert snap.hit == 0
        hit = await env.lookup(lookup_vpn(NO_S2, tag), NO_S2, "next cycle")
        assert hit.hit == 1


# WRAP-REPLACE-03, WRAP-LOOKUP-01
async def test_contexts_and_stage_forms_pass_through(wrapper_env):
    env = wrapper_env
    async with execution(env.dut):
        await env.reset()
        env.program_context(satp_asid=1, vsatp_asid=2, hgatp_vmid=3)
        specs = [
            (NO_S2, 0x53000, 0x100000011, 1, 0),
            (ONLY_S1, 0x53100, 0x200000012, 2, 3),
            (ONLY_S2, (0x53200 << 3) | 0, 0x300000013, 0, 3),
            (ALL_STAGE, 0x53300, 0x400000014, 2, 3),
        ]
        pairs = []
        for kind, tag, ppn, asid, vmid in specs:
            data = make_refill(kind, 0, tag, ppn, asid=asid, vmid=vmid)
            await env.refill(data, f"stage {kind}")
            pairs.append(pair_for(kind, tag))
        for (kind, tag, _ppn, _asid, _vmid), pair in zip(specs, pairs):
            snap = await env.lookup(pair[0], kind, f"stage {kind} hit")
            assert snap.hit == 1
        miss = await env.lookup(0x3FFFFFFFFFF, NO_S2, "miss")
        assert miss.hit == 0


# WRAP-FENCE-01, WRAP-RESET-01
async def test_sfence_and_hfence_pass_through_without_resetting_plru(wrapper_env):
    env = wrapper_env
    async with execution(env.dut):
        await env.reset()
        env.program_context(satp_asid=1, vsatp_asid=1, hgatp_vmid=3)
        s1 = make_refill(NO_S2, 0, 0x54000, 0x100000021, asid=1)
        s2 = make_refill(ONLY_S2, 0, (0x54100 << 3) | 0, 0x200000022, vmid=3)
        await env.refill(s1, "s1")
        await env.refill(s2, "s2")
        assert (await env.lookup(lookup_vpn(NO_S2, 0x54000), NO_S2, "s1 before")).hit == 1
        assert (await env.lookup((0x54100 << 3), ONLY_S2, "s2 before")).hit == 1
        await env.fence("all_all", 1, 1, 0, 0, note="sfence")
        assert (await env.lookup(lookup_vpn(NO_S2, 0x54000), NO_S2, "s1 cleared")).hit == 0
        env.sample_fence("all_all", ["cleared"])
        # The hfence path clears the stage2 entry, not the already-empty s1 way.
        await env.fence("hfencev", 0, 1, 0, 0, hv=1, note="hfencev")
        assert (await env.lookup((0x54100 << 3), ONLY_S2, "s2 cleared")).hit == 0
        env.sample_fence("hfencev", ["cleared"])
        # rs2=0 form exercises the per-way non-global stage2 invalidation
        # expressions even when no entry currently matches.
        await env.fence("hfencev", 0, 0, 0, 1, hv=1, note="hfencev asid")
        env.sample_fence("hfencev", ["cleared"])
        # All-address specific-ASID sfence evaluates the non-virtualized
        # stage1 clear expression for every way.
        await env.fence("all_asid", 1, 0, 0, 1, note="all asid")
        env.sample_fence("all_asid", ["cleared"])
        # Address-specific, all-ASID form executes the address-only clear
        # expression for every way.
        await env.fence("addr_all_asid", 0, 1, 0, 1, note="addr all asid")
        env.sample_fence("addr_all_asid", ["cleared"])
        await env.reset("with_valid_entries")


# WRAP-FENCE-01
async def test_address_sfence_and_hfenceg_pass_through(wrapper_env):
    env = wrapper_env
    async with execution(env.dut):
        await env.reset()
        env.program_context(satp_asid=1, vsatp_asid=1, hgatp_vmid=3)
        x, y = 0x55000, 0x55100
        sx = make_refill(NO_S2, 0, x, 0x100000031, asid=1)
        sy = make_refill(NO_S2, 0, y, 0x200000032, asid=1)
        d3 = make_refill(ONLY_S2, 0, (0x55200 << 3) | 0, 0x300000033, vmid=3)
        d4 = make_refill(ONLY_S2, 0, (0x55300 << 3) | 0, 0x400000034, vmid=4)
        for data in (sx, sy, d3, d4):
            await env.refill(data, "fence entry")
        assert (await env.lookup(lookup_vpn(NO_S2, x), NO_S2, "X before")).hit == 1
        assert (await env.lookup(lookup_vpn(NO_S2, y), NO_S2, "Y before")).hit == 1
        await env.fence("addr_asid", 0, 0, x << 15, 1, note="address fence")
        assert (await env.lookup(lookup_vpn(NO_S2, x), NO_S2, "X cleared")).hit == 0
        assert (await env.lookup(lookup_vpn(NO_S2, y), NO_S2, "Y survived")).hit == 1
        env.sample_fence("addr_asid", ["cleared", "survived"])
        assert (await env.lookup((0x55200 << 3), ONLY_S2, "D3 before")).hit == 1
        env.program_context(hgatp_vmid=4)
        assert (await env.lookup((0x55300 << 3), ONLY_S2, "D4 before")).hit == 1
        await env.fence("hfenceg", 0, 0, 0, 4, hg=1, note="hfenceg vmid")
        assert (await env.lookup((0x55300 << 3), ONLY_S2, "D4 cleared")).hit == 0
        env.program_context(hgatp_vmid=3)
        assert (await env.lookup((0x55200 << 3), ONLY_S2, "D3 survived")).hit == 1
        env.sample_fence("hfenceg", ["cleared", "survived"])
        await env.fence("hfenceg", 0, 1, 0, 0, hg=1, note="hfenceg all")
        env.sample_fence("hfenceg", ["cleared"])


# WRAP-REPLACE-01: all storage bits in the real TLBFA child must see both
# directions through the wrapper's PLRU-selected write port.
async def test_wrapper_storage_bits_toggle_in_every_selected_way(wrapper_env):
    env = wrapper_env
    async with execution(env.dut):
        await env.reset()
        ones = make_refill(
            ALL_STAGE, 3, (1 << 35) - 1, (1 << 41) - 1, n=1,
            asid=(1 << 16) - 1, vmid=(1 << 14) - 1, perm_g=1,
            valididx=(1,) * 8, pteidx=(1,) * 8, ppn_low=(7,) * 8,
            s1_pf=1, s1_af=1, s2_gpf=1, s2_gaf=1, pbmt=3, g_pbmt=3,
            s2_tag=(1 << 38) - 1, s2_ppn=(1 << 38) - 1,
            s1_perm_r=1, s1_perm_w=1, s1_perm_x=1,
            s2_perm_a=1, s2_perm_x=1, s1_perm_a=1, s1_perm_u=1,
        )
        zeros = make_refill(
            NO_S2, 0, 0, 0, valididx=(0,) * 8, pteidx=(0,) * 8,
            ppn_low=(0,) * 8, s1_perm_r=0, s1_perm_w=0, s1_perm_x=0,
            s2_perm_a=0, s2_perm_x=0, s1_perm_a=0, s1_perm_u=0,
            s1_v=0,
        )
        for index in range(63):
            await env.refill(ones, f"ones {index}")
        assert env.model.tlbfa.valid.count(0) == 0
        await env.reset("with_valid_entries")
        for index in range(63):
            await env.refill(zeros, f"zeros {index}")
        assert env.model.tlbfa.valid.count(0) == 0


# WRAP-LOOKUP-01: input context and fence address bits are all exercised by
# legal stimuli; the anchor entry must survive non-matching address fences.
async def test_wrapper_context_and_fence_input_bits_toggle(wrapper_env):
    env = wrapper_env
    async with execution(env.dut):
        await env.reset()
        await env.edge()
        env.program_context(satp_asid=0xFFFF, vsatp_asid=0xFFFF, hgatp_vmid=0x3FFF, virt=1, bme=1, cmode=1)
        env.drive_raw_csr(hgatp_vmid=0xFFFF)
        await env.edge()
        env.program_context(satp_asid=0, vsatp_asid=0, hgatp_vmid=0, virt=0, bme=0, cmode=0)
        await env.edge()
        env.program_context(satp_asid=1)
        anchor = make_refill(NO_S2, 0, 0x56000, 0x100000041, asid=1)
        await env.refill(anchor, "anchor")
        hit_vpn = lookup_vpn(NO_S2, 0x56000)
        for addr, sfence_id in ((0, 0), ((1 << 50) - 1, 0xFFFF), (0x2AAAAAAAAAAA, 0x5555), (0, 0)):
            await env.fence("addr_asid", 0, 0, addr, sfence_id, note="input bits")
            snap = await env.lookup(hit_vpn, NO_S2, "anchor survives")
            assert snap.hit == 1
